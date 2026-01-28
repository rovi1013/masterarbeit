import argparse
import json
import gzip
import ijson
import re
from pathlib import Path
from datetime import datetime

# Filter für die manuell gesetzten marker im GMT stdout
MARK_PREFIX = "##GMT_MARK##"
MARK_RE = re.compile(r".*##GMT_MARK##\s+ts_us=(\d+)\s+event=([A-Z0-9_]+)(?:\s+(.*))?$")

OUT_DIR = Path("gmt-data/processed-data")
BYTES_UNITS = {"Bytes", "bytes", "Byte", "B"}  # GMT gibt Byte mit verschiedenen Namen aus
TEMP_UNITS = {"centi°C"}

# Definitionen der Metriken
METRIC_SPEC = {
    # Energiemetriken (uJ deltas -> SUMME)
    "cpu_energy_rapl_msr_component": {"type": "energy", "unit": "uJ", "entities": ["Package_0"]},
    "memory_energy_rapl_msr_component": {"type": "energy", "unit": "uJ", "entities": ["DRAM_TOTAL"]},
    "gpu_energy_nvidia_nvml_component": {"type": "energy", "unit": "uJ", "entities": ["GPU_TOTAL"]},
    "psu_energy_ac_mcp_machine": {"type": "energy", "unit": "uJ", "entities": ["PSU_TOTAL"]},
    # Auslastungsmetriken (Ratio -> MEAN/MAX)
    "cpu_utilization_procfs_system": {"type": "meanmax", "unit": "Ratio", "entities": ["[SYSTEM]"]},
    "cpu_utilization_cgroup_container": {"type": "meanmax", "unit": "Ratio", "entities": ["rag-app", "ollama"]},
    "memory_used_cgroup_container": {"type": "meanmax", "unit": "Bytes", "entities": ["rag-app", "ollama"]},
    # Netzwerk IO Metrik (Bytes deltas -> SUMME/MAX
    "network_io_cgroup_container": {"type": "summax_bytes", "unit": "Bytes", "entities": ["rag-app", "ollama"]},
    # Temperatur (centi°C -> MEAN/MAX)
    "lmsensors_temperature_component": {"type": "meanmax", "unit": "C", "entities": ["TEMP_CORE", "TEMP_PACKAGE"]},
}


def parse_args():
    ap = argparse.ArgumentParser(description="Fasse die Measurement und Phase-Data Daten zusammen.")
    ap.add_argument("-m", "--measurements", required=True, help="Pfad zu *_measurements.json")
    ap.add_argument("-p", "--phase-data", required=True, help="Pfad zu *_phase-data.json")
    ap.add_argument("-c", "--compress-lvl", type=int, default=9, help="Gzip compression level (1-9)")
    return ap.parse_args()


def parse_markers(stdout: str):
    out = []
    if not stdout:
        return out

    for line in stdout.splitlines():
        if MARK_PREFIX not in line:
            continue
        m = MARK_RE.match(line.strip())
        if not m:
            continue
        ts_us = int(m.group(1))
        event = m.group(2)
        rest = m.group(3) or ""

        meta = {}
        for tok in rest.split():
            if "=" not in tok:
                continue
            k, v = tok.split("=", 1)
            meta[k] = v

        out.append({"ts_us": ts_us, "event": event, "meta": meta})
    out.sort(key=lambda x: x["ts_us"])
    return out


def extract_stdout_from_cmd(logs_rag_app: list, needles) -> str:
    if isinstance(needles, str):
        needles = [needles]

    for e in logs_rag_app or []:
        cmd = e.get("cmd") or ""
        if any(n in cmd for n in needles):
            return e.get("stdout") or ""

    return ""


def make_key(base: str, meta: dict, allow_qid: bool):
    if allow_qid and base == "RETRIEVAL":
        qid = meta.get("q_id")
        return base, qid
    return base, None


def build_subwindows_from_markers(parent_name: str, markers: list, allow_qid: bool):
    starts = {}
    windows = []

    for m in markers:
        ev = m["event"]
        ts = m["ts_us"]
        meta = m.get("meta") or {}

        if ev.endswith("_START"):
            base = ev[:-6]
            k = make_key(base, meta, allow_qid)
            starts[k] = ts

        elif ev.endswith("_END"):
            base = ev[:-4]
            k = make_key(base, meta, allow_qid)
            s = starts.pop(k, None)
            if s is None:
                continue
            e = ts
            if e <= s:
                continue

            base_name = base
            if allow_qid and base == "RETRIEVAL":
                qid = (meta.get("q_id") or "unknown")
                wname = f"{parent_name}/{base_name}/{qid}"
            else:
                wname = f"{parent_name}/{base_name}"

            windows.append({
                "name": wname,
                "kind": "sub_window",
                "start_us": int(s),
                "end_us": int(e),
                "duration_s": (e - s) / 1e6,
            })

    windows.sort(key=lambda w: w["start_us"])
    return windows


def date_prefix(path: Path) -> str:
    try:
        prefix = path.name.split("_", 1)[0]
        datetime.strptime(prefix, "%Y-%m-%d")
        return prefix
    except Exception:
        return datetime.now().strftime("%Y-%m-%d")


def load_run_and_windows(phase_path: Path):
    data = json.load(open(phase_path, "r", encoding="utf-8")).get("data", {})

    # Metadaten der Messung
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

    windows = []
    for p in data.get("phases", []) or []:
        if p.get("hidden") is True:
            continue
        name = p.get("name")
        if not name:
            continue
        s, e = int(p["start"]), int(p["end"])
        kind = "gmt_phase" if (name.startswith("[") and name.endswith("]")) else "workflow_step"
        windows.append({
            "name": name,
            "kind": kind,
            "start_us": s,
            "end_us": e,
            "duration_s": (e - s) / 1e6,
        })

    logs = data.get("logs", {}) or {}
    rag_logs = logs.get("rag-app", []) or []
    indexing_stdout = extract_stdout_from_cmd(rag_logs, "python -m app.indexing")
    rag_stdout = extract_stdout_from_cmd(rag_logs, "docker run -it -d --name rag-app")
    indexing_markers = parse_markers(indexing_stdout)
    rag_markers = parse_markers(rag_stdout)

    sub_windows = []
    # Indexing: EMBEDDING_* und PERSIST_IN_DB_*
    sub_windows += build_subwindows_from_markers("Indexing", indexing_markers, allow_qid=False)

    # RAG Querries: RETRIEVAL_* mit q_id
    sub_windows += build_subwindows_from_markers("RAG Querries", rag_markers, allow_qid=True)

    windows.extend(sub_windows)
    windows.sort(key=lambda w: w["start_us"])

    marker_map = {
        "Indexing": indexing_markers,
        "RAG Querries": rag_markers,
    }

    return run, windows, marker_map


def iter_measurements(path: Path):
    if path.suffix != ".json":
        raise ValueError(f"Measurements müssen als .json vorliegen.\nFehlerhalftes Dateiformat: {path}")

    with open(path, "rb") as fin:
        for row in ijson.items(fin, "data.item"):
            if not isinstance(row, list) or len(row) != 5:
                continue
            entity, timestamp, metric, value, unit = row
            yield str(entity), int(timestamp), str(metric), value, str(unit)


def normalize(metric: str, entity: str, unit: str, value, mappings: dict):
    if metric not in METRIC_SPEC:
        return None

    # Energie Metriken (uJ)
    if metric == "cpu_energy_rapl_msr_component":
        return ("Package_0", float(value)) if (unit == "uJ" and entity == "Package_0") else None

    if metric == "memory_energy_rapl_msr_component":
        if unit == "uJ" and entity.startswith("DRAM"):
            mappings["DRAM_TOTAL"].add(entity)
            return "DRAM_TOTAL", float(value)
        return None

    if metric == "gpu_energy_nvidia_nvml_component":
        if unit == "uJ":
            mappings["GPU_TOTAL"].add(entity)
            return "GPU_TOTAL", float(value)
        return None

    if metric == "psu_energy_ac_mcp_machine":
        return ("PSU_TOTAL", float(value)) if (unit == "uJ" and entity == "[MACHINE]") else None

    # MEAN/MAX
    if metric == "cpu_utilization_procfs_system":
        return ("[SYSTEM]", float(value)) if (unit == "Ratio" and entity == "[SYSTEM]") else None

    if metric == "cpu_utilization_cgroup_container":
        return (entity, float(value)) if (unit == "Ratio" and entity in {"rag-app", "ollama"}) else None

    if metric == "memory_used_cgroup_container":
        return (entity, float(value)) if (entity in {"rag-app", "ollama"} and unit in BYTES_UNITS) else None

    if metric == "network_io_cgroup_container":
        return (entity, float(value)) if (entity in {"rag-app", "ollama"} and unit in BYTES_UNITS) else None

    # Temperatur
    if metric == "lmsensors_temperature_component":
        if unit not in TEMP_UNITS:
            return None
        if "_Core-" in entity:
            mappings["TEMP_CORE"].add(entity)
            return "TEMP_CORE", float(value) / 100.0
        if "Package-id" in entity:
            mappings["TEMP_PACKAGE"].add(entity)
            return "TEMP_PACKAGE", float(value) / 100.0
        mappings["TEMP_IGNORED"].add(entity)
        return None

    return None


def empty_agg(mtype: str):
    if mtype == "energy":
        return {"sum": None, "sum_Wh": None, "count": 0}
    if mtype == "summax_bytes":
        return {"sum": None, "sum_MiB": None, "max": None, "count": 0}
    return {"mean": None, "max": None, "count": 0}


def main():
    args = parse_args()

    measurements_path = Path(args.measurements)
    phase_path = Path(args.phase_data)

    run, windows, marker_map = load_run_and_windows(phase_path)
    run_id = run.get("id") or "unknown"

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{run.get('date', date_prefix(phase_path))}_{run_id}_summary.json.gz"

    mappings = {
        "DRAM_TOTAL": set(),
        "GPU_TOTAL": set(),
        "TEMP_CORE": set(),
        "TEMP_PACKAGE": set(),
        "TEMP_IGNORED": set()
    }
    stats = {}

    total_rows = 0
    used_updates = 0

    for raw_entity, timestamp, metric, value, unit in iter_measurements(measurements_path):
        total_rows += 1
        n = normalize(metric, raw_entity, unit, value, mappings)
        if not n:
            continue
        ent, v = n

        matched = [window for window in windows if window["start_us"] <= timestamp < window["end_us"]]
        if not matched:
            continue

        track_max = METRIC_SPEC[metric]["type"] != "energy"
        for w in matched:
            b = (stats.setdefault(w["name"], {})
                 .setdefault(metric, {})
                 .setdefault(ent, {"sum": 0.0, "count": 0, "max": None}))
            b["sum"] += v
            b["count"] += 1
            if track_max:
                b["max"] = v if b["max"] is None else (v if v > b["max"] else b["max"])
            used_updates += 1

    records = []
    for w in windows:
        wname = w["name"]
        metrics_out = {}
        wstats = stats.get(wname, {})

        for metric, spec in METRIC_SPEC.items():
            mtype = spec["type"]
            mstats = wstats.get(metric, {})
            entities = {}
            for ent in spec["entities"]:
                b = mstats.get(ent)
                if not b or b["count"] == 0:
                    entities[ent] = empty_agg(mtype)
                    continue

                if mtype == "energy":
                    s = b["sum"]
                    entities[ent] = {"sum": s, "sum_Wh": s / 3.6e9, "count": b["count"]}
                elif mtype == "summax_bytes":
                    s = b["sum"]
                    entities[ent] = {"sum": s, "sum_MiB": s / (1024.0 * 1024.0), "max": b["max"], "count": b["count"]}
                else:
                    entities[ent] = {"mean": b["sum"] / b["count"], "max": b["max"], "count": b["count"]}

            metrics_out[metric] = {"unit": spec["unit"], "entities": entities}

        records.append({"window": wname, "kind": w["kind"], "metrics": metrics_out})

    summary = {
        "schema_version": "1.0",
        "run": run,
        "source_files": {
            "phase_data": str(phase_path),
            "measurements": str(measurements_path),
        },
        "windows": windows,
        "records": records,
        "markers": marker_map,
        "entity_mappings": {
            k: sorted(v) for k, v in mappings.items()
        },
        "stats": {
            "total_rows_seen": total_rows,
            "updates_written": used_updates
        },
        "notes": {
            "timebase": "unix_us"
        },
    }

    with gzip.open(out_path, "wt", encoding="utf-8", compresslevel=args.compress_lvl) as fout:
        json.dump(summary, fout, ensure_ascii=False)

    print(f"Measurements Summary erfolgreich gespeichert: {out_path}.")
    print(f"Anzahl der Phasen: {len(windows)}\nMesspunkte gesehen: {total_rows}")
    print("########## SUMMARY DONE ##########")


if __name__ == "__main__":
    main()
