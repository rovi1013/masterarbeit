from __future__ import annotations

import argparse
import gzip
import json
import ijson
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple

OUT_DIR = Path("gmt-data/processed-data")

BYTES_UNITS = {"Bytes", "bytes", "Byte", "B"}  # GMT may emit different spellings
TEMP_INPUT_UNITS = {"centi°C"}  # temperature values come as centi°C

MARK_PREFIX = "##GMT_MARK##"
MARK_RE = re.compile(r".*##GMT_MARK##\s+ts_us=(\d+)\s+event=([A-Z0-9_]+)(?:\s+(.*))?$")

CONTAINERS = {"rag-app", "ollama"}

# Keep the original spelling to avoid breaking downstream consumers.
PARENT_INDEXING = "Indexing"
PARENT_RAG = "RAG Querries"

CMD_INDEXING = "python -m app.indexing"
CMD_RAG = "docker run -it -d --name rag-app"


# Daten Klassen
@dataclass(frozen=True)
class Window:
    name: str
    kind: str
    start_us: int
    end_us: int

    @property
    def duration_s(self) -> float:
        return (self.end_us - self.start_us) / 1e6

    def to_json(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "start_us": int(self.start_us),
            "end_us": int(self.end_us),
            "duration_s": self.duration_s,
        }


@dataclass(frozen=True)
class Marker:
    ts_us: int
    event: str
    meta: Dict[str, str]

    def to_json(self) -> Dict[str, Any]:
        return {"ts_us": int(self.ts_us), "event": self.event, "meta": dict(self.meta)}


@dataclass(frozen=True)
class MetricSpec:
    mtype: str
    out_unit: str
    out_entities: Tuple[str, ...]


@dataclass
class AggBucket:
    sum: float = 0.0
    count: int = 0
    max: Optional[float] = None

    def update(self, value: float, track_max: bool) -> None:
        self.sum += value
        self.count += 1
        if track_max:
            if self.max is None or value > self.max:
                self.max = value


# Metriken von GMT
METRIC_SPEC: Dict[str, MetricSpec] = {
    # Energie (uJ deltas -> SUM)
    "cpu_energy_rapl_msr_component": MetricSpec("energy", "uJ", ("Package_0",)),
    "memory_energy_rapl_msr_component": MetricSpec("energy", "uJ", ("DRAM_TOTAL",)),
    "gpu_energy_nvidia_nvml_component": MetricSpec("energy", "uJ", ("GPU_TOTAL",)),
    "psu_energy_ac_mcp_machine": MetricSpec("energy", "uJ", ("PSU_TOTAL",)),
    # CPU/RAM Auslastung (Ratio/Bytes -> MEAN/MAX)
    "cpu_utilization_procfs_system": MetricSpec("meanmax", "Ratio", ("[SYSTEM]",)),
    "cpu_utilization_cgroup_container": MetricSpec("meanmax", "Ratio", ("rag-app", "ollama")),
    "memory_used_cgroup_container": MetricSpec("meanmax_B", "Bytes", ("rag-app", "ollama")),
    # Network IO (Bytes deltas -> SUM/MAX)
    "network_io_cgroup_container": MetricSpec("summax_bytes", "Bytes", ("rag-app", "ollama")),
    # Temperatur (centi°C -> °C -> MEAN/MAX)
    "lmsensors_temperature_component": MetricSpec("meanmax", "C", ("TEMP_CORE", "TEMP_PACK")),
}


# ================ #
# Aufruf Parameter #
# ================ #
def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Fasse die Measurement und Phase-Data Daten zusammen.")
    ap.add_argument("-m", "--measurements", required=True, help="Pfad zu *_measurements.json")
    ap.add_argument("-p", "--phase-data", required=True, help="Pfad zu *_phase-data.json")
    ap.add_argument("-c", "--compress-lvl", type=int, default=9, help="Gzip compression level (1-9)")
    return ap.parse_args()


# ==================== #
# Markers ##GMT_MARK## #
# ==================== #
def parse_markers(stdout: str) -> List[Marker]:
    if not stdout:
        return []

    markers: List[Marker] = []
    for line in stdout.splitlines():
        if MARK_PREFIX not in line:
            continue
        m = MARK_RE.match(line.strip())
        if not m:
            continue

        ts_us = int(m.group(1))
        event = m.group(2)
        rest = m.group(3) or ""

        meta: Dict[str, str] = {}
        for tok in rest.split():
            if "=" not in tok:
                continue
            k, v = tok.split("=", 1)
            meta[k] = v

        markers.append(Marker(ts_us=ts_us, event=event, meta=meta))

    markers.sort(key=lambda x: x.ts_us)
    return markers


def extract_stdout_from_cmd(logs: List[Dict[str, Any]], needles: Iterable[str]) -> str:
    needles = list(needles)
    for entry in logs or []:
        cmd = entry.get("cmd") or ""
        if any(n in cmd for n in needles):
            return entry.get("stdout") or ""
    return ""


def _marker_key(base: str, meta: Dict[str, str], allow_qid: bool) -> Tuple[str, Optional[str]]:
    if allow_qid and base == "RETRIEVAL":
        return base, meta.get("q_id")
    return base, None


def build_subwindows_from_markers(parent_name: str, markers: List[Marker], allow_qid: bool, ) -> List[Window]:
    starts: Dict[Tuple[str, Optional[str]], int] = {}
    out: List[Window] = []

    for m in markers:
        ev = m.event
        ts = m.ts_us

        if ev.endswith("_START"):
            base = ev[:-6]
            starts[_marker_key(base, m.meta, allow_qid)] = ts
            continue

        if ev.endswith("_END"):
            base = ev[:-4]
            key = _marker_key(base, m.meta, allow_qid)
            start_ts = starts.pop(key, None)
            if start_ts is None:
                continue
            if ts <= start_ts:
                continue

            if allow_qid and base == "RETRIEVAL":
                qid = m.meta.get("q_id") or "unknown"
                name = f"{parent_name}/{base}/{qid}"
            else:
                name = f"{parent_name}/{base}"

            out.append(Window(name=name, kind="sub_window", start_us=int(start_ts), end_us=int(ts)))

    out.sort(key=lambda w: w.start_us)
    return out


# =================== #
# Phase-Data Auslesen #
# =================== #
def date_prefix(path: Path) -> str:
    try:
        prefix = path.name.split("_", 1)[0]
        datetime.strptime(prefix, "%Y-%m-%d")
        return prefix
    except Exception:
        return datetime.now().strftime("%Y-%m-%d")


def load_run_and_windows(phase_path: Path) -> Tuple[Dict[str, Any], List[Window], Dict[str, List[Dict[str, Any]]]]:
    with open(phase_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    data = (raw or {}).get("data", {}) or {}

    run = {
        "id": data.get("id"),
        "name": data.get("name"),
        "date": date_prefix(phase_path),
        "uri": data.get("uri"),
        "branch": data.get("branch"),
        "commit_hash": data.get("commit_hash"),
        "filename": data.get("filename"),
        "machine_id": data.get("machine_id"),
        "gmt_hash": data.get("gmt_hash"),
        "created_at": data.get("created_at"),
        "failed": data.get("failed"),
        "warnings": len(data.get("warnings") or []),
        "start_measurement": data.get("start_measurement"),
        "end_measurement": data.get("end_measurement"),
        "usage_scenario_variables": data.get("usage_scenario_variables"),
    }
    run = {k: v for k, v in run.items() if v is not None}

    windows: List[Window] = []
    for p in (data.get("phases") or []):
        if p.get("hidden") is True:
            continue
        name = p.get("name")
        if not name:
            continue
        start_us, end_us = int(p["start"]), int(p["end"])
        kind = "gmt_phase" if (name.startswith("[") and name.endswith("]")) else "workflow_step"
        windows.append(Window(name=name, kind=kind, start_us=start_us, end_us=end_us))

    logs = (data.get("logs") or {})
    rag_logs = logs.get("rag-app") or []

    indexing_stdout = extract_stdout_from_cmd(rag_logs, [CMD_INDEXING])
    rag_stdout = extract_stdout_from_cmd(rag_logs, [CMD_RAG])

    indexing_markers = parse_markers(indexing_stdout)
    rag_markers = parse_markers(rag_stdout)

    windows.extend(build_subwindows_from_markers(PARENT_INDEXING, indexing_markers, allow_qid=False))
    windows.extend(build_subwindows_from_markers(PARENT_RAG, rag_markers, allow_qid=True))
    windows.sort(key=lambda w: w.start_us)

    marker_map = {
        PARENT_INDEXING: [m.to_json() for m in indexing_markers],
        PARENT_RAG: [m.to_json() for m in rag_markers],
    }
    return run, windows, marker_map


# ===================== #
# Measurements Auslesen #
# ===================== #
def iter_measurements(path: Path) -> Iterator[Tuple[str, int, str, Any, str]]:
    if path.suffix != ".json":
        raise ValueError(f"Measurements müssen als .json vorliegen.\nFehlerhalftes Dateiformat: {path}")

    with open(path, "rb") as fin:
        for row in ijson.items(fin, "data.item"):
            if not isinstance(row, list) or len(row) != 5:
                continue
            entity, timestamp, metric, value, unit = row
            yield str(entity), int(timestamp), str(metric), value, str(unit)


# ====================== #
# Metriken normalisieren #
# ====================== #
def normalize(metric: str, raw_entity: str, unit: str, value: Any, entity_mappings: Dict[str, set], ) \
        -> Optional[Tuple[str, float]]:
    if metric not in METRIC_SPEC:
        return None

    # Energie
    if metric == "cpu_energy_rapl_msr_component":
        if unit == "uJ" and raw_entity == "Package_0":
            return "Package_0", float(value)
        return None

    if metric == "memory_energy_rapl_msr_component":
        if unit == "uJ" and raw_entity.startswith("DRAM"):
            entity_mappings["DRAM_TOTAL"].add(raw_entity)
            return "DRAM_TOTAL", float(value)
        return None

    if metric == "gpu_energy_nvidia_nvml_component":
        if unit == "uJ":
            entity_mappings["GPU_TOTAL"].add(raw_entity)
            return "GPU_TOTAL", float(value)
        return None

    if metric == "psu_energy_ac_mcp_machine":
        if unit == "uJ" and raw_entity == "[MACHINE]":
            return "PSU_TOTAL", float(value)
        return None

    # Auslastung in %
    if metric == "cpu_utilization_procfs_system":
        if unit == "Ratio" and raw_entity == "[SYSTEM]":
            return "[SYSTEM]", float(value)
        return None

    if metric == "cpu_utilization_cgroup_container":
        if unit == "Ratio" and raw_entity in CONTAINERS:
            return raw_entity, float(value)
        return None

    # RAM/Netzwerk Auslastung in Byte
    if metric in {"memory_used_cgroup_container", "network_io_cgroup_container"}:
        if raw_entity in CONTAINERS and unit in BYTES_UNITS:
            return raw_entity, float(value)
        return None

    # Temperatur
    if metric == "lmsensors_temperature_component":
        if unit not in TEMP_INPUT_UNITS:
            return None

        if "_Core-" in raw_entity:
            entity_mappings["TEMP_CORE"].add(raw_entity)
            return "TEMP_CORE", float(value) / 100.0

        if "Package-id" in raw_entity:
            entity_mappings["TEMP_PACK"].add(raw_entity)
            return "TEMP_PACK", float(value) / 100.0

        entity_mappings["TEMP_IGNORED"].add(raw_entity)
        return None

    return None


# ========================== #
# Window-Timestamp Zuordnung #
# ========================== #
class WindowMatcher:
    def __init__(self, windows: List[Window]):
        self._windows = sorted(windows, key=lambda w: w.start_us)
        self._i = 0
        self._active: List[Window] = []
        self._last_ts: Optional[int] = None
        self._fallback = False

    def match(self, ts_us: int) -> List[Window]:
        if self._fallback or (self._last_ts is not None and ts_us < self._last_ts):
            self._fallback = True
            return [w for w in self._windows if w.start_us <= ts_us < w.end_us]

        self._last_ts = ts_us

        # Activate new windows
        while self._i < len(self._windows) and self._windows[self._i].start_us <= ts_us:
            self._active.append(self._windows[self._i])
            self._i += 1

        # Drop expired
        if self._active:
            self._active = [w for w in self._active if ts_us < w.end_us]

        return [w for w in self._active if w.start_us <= ts_us < w.end_us]


# =================== #
# Output Formatierung #
# =================== #
def empty_agg(mtype: str) -> Dict[str, Any]:
    if mtype == "energy":
        return {"sum": None, "sum_Wh": None, "count": 0}
    if mtype == "meanmax_B":
        return {"mean": None, "mean_MiB": None, "max": None, "count": 0}
    if mtype == "summax_bytes":
        return {"sum": None, "sum_MiB": None, "max": None, "count": 0}
    return {"mean": None, "max": None, "count": 0}


def finalize_bucket(mtype: str, b: Optional[AggBucket]) -> Dict[str, Any]:
    if b is None or b.count == 0:
        return empty_agg(mtype)

    if mtype == "energy":
        s = b.sum
        return {"sum": s, "sum_Wh": s / 3.6e9, "count": b.count}

    if mtype == "meanmax_B":
        s = b.sum / b.count
        return {"mean": s, "mean_MiB": s / (1024.0 * 1024.0), "max": b.max, "count": b.count}

    if mtype == "summax_bytes":
        s = b.sum
        return {"sum": s, "sum_MiB": s / (1024.0 * 1024.0), "max": b.max, "count": b.count}

    # meanmax
    return {"mean": b.sum / b.count, "max": b.max, "count": b.count}


def main() -> None:
    args = parse_args()

    measurements_path = Path(args.measurements)
    phase_path = Path(args.phase_data)

    run, windows, marker_map = load_run_and_windows(phase_path)
    run_id = run.get("id") or "unknown"

    out_dir: Path = OUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{run.get('date', date_prefix(phase_path))}_{run_id}_merged.json.gz"

    entity_mappings: Dict[str, set] = {
        "DRAM_TOTAL": set(),
        "GPU_TOTAL": set(),
        "TEMP_CORE": set(),
        "TEMP_PACK": set(),
        "TEMP_IGNORED": set(),
    }

    # stats[window_name][metric][entity] -> AggBucket
    stats: Dict[str, Dict[str, Dict[str, AggBucket]]] = {}

    total_rows = 0
    used_updates = 0

    matcher = WindowMatcher(windows)

    for raw_entity, ts_us, metric, value, unit in iter_measurements(measurements_path):
        total_rows += 1

        norm = normalize(metric, raw_entity, unit, value, entity_mappings)
        if not norm:
            continue
        entity, v = norm

        matched = matcher.match(ts_us)
        if not matched:
            continue

        spec = METRIC_SPEC[metric]
        track_max = spec.mtype != "energy"

        for w in matched:
            bucket = (
                stats.setdefault(w.name, {})
                .setdefault(metric, {})
                .setdefault(entity, AggBucket())
            )
            bucket.update(v, track_max=track_max)
            used_updates += 1

    # Einträge erstellen
    records: List[Dict[str, Any]] = []
    for w in windows:
        wstats = stats.get(w.name, {})
        metrics_out: Dict[str, Any] = {}

        for metric, spec in METRIC_SPEC.items():
            mstats = wstats.get(metric, {})
            entities_out: Dict[str, Any] = {}
            for ent in spec.out_entities:
                entities_out[ent] = finalize_bucket(spec.mtype, mstats.get(ent))

            metrics_out[metric] = {"unit": spec.out_unit, "entities": entities_out}

        records.append({"window": w.name, "kind": w.kind, "metrics": metrics_out})

    summary = {
        "run": run,
        "source_files": {
            "phase_data": str(phase_path),
            "measurements": str(measurements_path),
        },
        "windows": [w.to_json() for w in windows],
        "records": records,
        "markers": marker_map,
        "entity_mappings": {k: sorted(v) for k, v in entity_mappings.items()},
        "stats": {
            "total_rows_seen": total_rows,
            "updates_written": used_updates,
        },
        "notes": {"timebase": "unix_us"},
    }

    with gzip.open(out_path, "wt", encoding="utf-8", compresslevel=args.compress_lvl) as fout:
        json.dump(summary, fout, ensure_ascii=False)

    print("========== MERGE DONE ==========")


if __name__ == "__main__":
    main()
