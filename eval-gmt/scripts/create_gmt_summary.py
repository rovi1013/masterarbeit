from __future__ import annotations

import argparse
import gzip
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, stdev, quantiles
from typing import Any, Callable, Dict, List, Tuple, Union


@dataclass(frozen=True)
class FieldSpec:
    field_id: str
    raw_field: str
    agg: str    # Aggregation: "sum" | "mean" | "max"
    unit_raw: str | None = None
    unit_converted: str | None = None
    convert: Callable[[float], float] | None = None


@dataclass(frozen=True)
class MetricSpec:
    metric: str
    fields: tuple[FieldSpec, ...]
    add_total_entity_for_sum_fields: bool = False


def _u_j_to_j(v: float) -> float:
    return v / 1e6


def _bytes_to_mib(v: float) -> float:
    return v / (1024.0 * 1024.0)


def _ratio_scaled_to_pct(v: float) -> float:
    return v / 100.0


METRIC_SPECS: dict[str, MetricSpec] = {
    # --- Energie (Summe) ---
    "cpu_energy_rapl_msr_component": MetricSpec(
        metric="cpu_energy_rapl_msr_component",
        fields=(
            FieldSpec("sum", "sum", "sum", unit_raw="uJ", unit_converted="J", convert=_u_j_to_j),
            FieldSpec("sum_Wh", "sum_Wh", "sum", unit_raw="Wh"),
        ),
        add_total_entity_for_sum_fields=True,
    ),
    "memory_energy_rapl_msr_component": MetricSpec(
        metric="memory_energy_rapl_msr_component",
        fields=(
            FieldSpec("sum", "sum", "sum", unit_raw="uJ", unit_converted="J", convert=_u_j_to_j),
            FieldSpec("sum_Wh", "sum_Wh", "sum", unit_raw="Wh"),
        ),
        add_total_entity_for_sum_fields=True,
    ),
    "gpu_energy_nvidia_nvml_component": MetricSpec(
        metric="gpu_energy_nvidia_nvml_component",
        fields=(
            FieldSpec("sum", "sum", "sum", unit_raw="uJ", unit_converted="J", convert=_u_j_to_j),
            FieldSpec("sum_Wh", "sum_Wh", "sum", unit_raw="Wh"),
        ),
        add_total_entity_for_sum_fields=True,
    ),
    "psu_energy_ac_mcp_machine": MetricSpec(
        metric="psu_energy_ac_mcp_machine",
        fields=(
            FieldSpec("sum", "sum", "sum", unit_raw="uJ", unit_converted="J", convert=_u_j_to_j),
            FieldSpec("sum_Wh", "sum_Wh", "sum", unit_raw="Wh"),
        ),
        add_total_entity_for_sum_fields=True,
    ),

    # --- CPU Util (mean/max) ---
    "cpu_utilization_procfs_system": MetricSpec(
        metric="cpu_utilization_procfs_system",
        fields=(
            FieldSpec("mean", "mean", "mean", unit_raw="Ratio(*1e4)", unit_converted="%", convert=_ratio_scaled_to_pct),
            FieldSpec("max", "max", "max", unit_raw="Ratio(*1e4)", unit_converted="%", convert=_ratio_scaled_to_pct),
        ),
    ),
    "cpu_utilization_cgroup_container": MetricSpec(
        metric="cpu_utilization_cgroup_container",
        fields=(
            FieldSpec("mean", "mean", "mean", unit_raw="Ratio(*1e4)", unit_converted="%", convert=_ratio_scaled_to_pct),
            FieldSpec("max", "max", "max", unit_raw="Ratio(*1e4)", unit_converted="%", convert=_ratio_scaled_to_pct),
        ),
    ),

    # --- RAM Util (mean/max) ---
    "memory_used_cgroup_container": MetricSpec(
        metric="memory_used_cgroup_container",
        fields=(
            FieldSpec("mean", "mean", "mean", unit_raw="Bytes", unit_converted="MiB", convert=_bytes_to_mib),
            FieldSpec("max", "max", "max", unit_raw="Bytes", unit_converted="MiB", convert=_bytes_to_mib),
        ),
    ),

    # --- Netzwerk (sum/max) ---
    "network_io_cgroup_container": MetricSpec(
        metric="network_io_cgroup_container",
        fields=(
            FieldSpec("sum", "sum", "sum", unit_raw="Bytes", unit_converted="MiB", convert=_bytes_to_mib),
            FieldSpec("max", "max", "max", unit_raw="Bytes", unit_converted="MiB", convert=_bytes_to_mib),
        ),
    ),

    # --- CPU Temp (mean/max) ---
    "lmsensors_temperature_component": MetricSpec(
        metric="lmsensors_temperature_component",
        fields=(
            FieldSpec("mean", "mean", "mean", unit_raw="C"),
            FieldSpec("max", "max", "max", unit_raw="C"),
        ),
    ),
}

PHASE_WINDOWS: tuple[str, ...] = (
    "[INSTALLATION]",
    "[RUNTIME]",
    "Download Dataset",
    "Indexing",
    "Indexing/CHUNKING",
    "Indexing/EMBEDDING",
    "Indexing/PERSIST_IN_DB",
    "RAG Querries",
)


def load_json(path: Path) -> dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def dump_json_gz(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


# Gruppierung der Records über Windows
def build_window_records(summary: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for r in summary.get("records", []):
        w = r.get("window")
        if not w:
            continue
        out.setdefault(str(w), []).append(r)
    return out


# Summe von duration_s pro Window
def build_duration_map(summary: dict[str, Any]) -> dict[str, float]:
    dur: dict[str, float] = {}
    for w in summary.get("windows", []):
        name = w.get("name")
        d = w.get("duration_s")
        if name is None or d is None:
            continue
        dur[str(name)] = dur.get(str(name), 0.0) + float(d)
    return dur


def _list_entities(records: list[dict[str, Any]], metric_name: str) -> set[str]:
    out: set[str] = set()
    for rec in records:
        metrics = rec.get("metrics") or {}
        mb = metrics.get(metric_name)
        if not isinstance(mb, dict):
            continue
        entities = mb.get("entities") or {}
        if not isinstance(entities, dict):
            continue
        for k, v in entities.items():
            if isinstance(v, dict):
                out.add(str(k))
    return out


# Aggregation über Entity aus einem Window und Metrik
def _aggregate_by_entity(records: list[dict[str, Any]], metric_name: str, raw_field: str, agg: str) -> dict[str, float]:

    sum_state: dict[str, float] = {}
    max_state: dict[str, float] = {}
    mean_num: dict[str, float] = {}
    mean_den: dict[str, float] = {}

    for rec in records:
        metrics = rec.get("metrics") or {}
        mb = metrics.get(metric_name)
        if not isinstance(mb, dict):
            continue
        entities = mb.get("entities") or {}
        if not isinstance(entities, dict):
            continue

        for ent_name, ent in entities.items():
            if not isinstance(ent, dict):
                continue
            v = ent.get(raw_field)
            if v is None:
                continue

            name = str(ent_name)
            fv = float(v)

            if agg == "sum":
                sum_state[name] = sum_state.get(name, 0.0) + fv
            elif agg == "max":
                max_state[name] = fv if name not in max_state else max(max_state[name], fv)
            elif agg == "mean":
                c = ent.get("count")
                try:
                    w = float(c) if c is not None else 1.0
                except Exception:
                    w = 1.0
                if w <= 0:
                    w = 1.0
                mean_num[name] = mean_num.get(name, 0.0) + fv * w
                mean_den[name] = mean_den.get(name, 0.0) + w
            else:
                raise ValueError(f"Unknown agg: {agg}")

    if agg == "sum":
        return sum_state
    if agg == "max":
        return max_state

    out: dict[str, float] = {}
    for k in mean_num:
        den = mean_den.get(k, 0.0)
        if den > 0:
            out[k] = mean_num[k] / den
    return out


def metric_summary(values: list[float | None]) -> dict[str, Any]:
    vals = [float(v) for v in values if v is not None and not math.isnan(float(v))]
    vals.sort()
    n = len(vals)

    if n == 0:
        return {
            "n": 0,
            "mean": None,
            "stdev": None,
            "cv_pct": None,
            "min": None,
            "max": None,
            "p10": None,
            "p25": None,
            "p50": None,
            "p75": None,
            "p90": None,
        }

    m = float(mean(vals))
    sd = float(stdev(vals)) if n >= 2 else 0.0
    cv_pct = (100.0 * sd / abs(m)) if m != 0 else None

    if n == 1:
        p10 = p25 = p50 = p75 = p90 = vals[0]
    else:
        qs = quantiles(vals, n=20, method="inclusive")  # 5%-Schritte
        p10, p25, p50, p75, p90 = qs[1], qs[4], qs[9], qs[14], qs[17]

    def r(x: float) -> float:
        return round(float(x), 2)

    return {
        "n": n,
        "mean": r(m),
        "stdev": r(sd) if n >= 2 else None,
        "cv_pct": r(cv_pct) if cv_pct else None,
        "min": r(vals[0]),
        "max": r(vals[-1]),
        "p10": r(p10),
        "p25": r(p25),
        "p50": r(p50),
        "p75": r(p75),
        "p90": r(p90),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Aggregiert mehrere GMT *_merged.json.gz über Runs.")
    ap.add_argument("-i", "--input-dir", required=True, help="Ordner mit *_merged.json.gz Dateien.")
    ap.add_argument("-o", "--output", default="gmt_runs_aggregated", help="Ausgabename ohne Endung (wird .json.gz).")
    args = ap.parse_args()

    input_dir = Path(args.input_dir)
    if not input_dir.is_dir():
        raise SystemExit(f"Kein Ordner: {input_dir}")

    files = [input_dir / p.name for p in input_dir.glob("*.json.gz")]
    if not files:
        raise SystemExit("Keine *.json.gz) Datei gefunden.")

    out_path = input_dir / f"{args.output}.json.gz"

    runs: list[dict[str, Any]] = []

    loaded: list[tuple[Path, dict[str, Any]]] = []
    runs: list[dict[str, Any]] = []
    input_files_used: list[str] = []

    # entities_map[(metric, field_id)] -> set(entities)
    entities_map: dict[tuple[str, str], set[str]] = {}

    for f in files:
        s = load_json(f)
        loaded.append((f, s))
        input_files_used.append(f.name)

        run_name = (s.get("run") or {}).get("name") or f.stem
        run_id = (s.get("run") or {}).get("id") or f.stem
        runs.append({"run_id": run_id, "run_name": run_name, "file": str(f)})

        window_records = build_window_records(s)

        for ph in PHASE_WINDOWS:
            recs = window_records.get(ph, [])
            if not recs:
                continue

            for metric_name, mspec in METRIC_SPECS.items():
                ent_names = _list_entities(recs, metric_name)
                for fs in mspec.fields:
                    entities_map.setdefault((metric_name, fs.field_id), set()).update(ent_names)
                    if mspec.add_total_entity_for_sum_fields and fs.agg == "sum":
                        entities_map[(metric_name, fs.field_id)].add("TOTAL")

    duration_series_s: dict[str, list[float | None]] = {ph: [] for ph in PHASE_WINDOWS}
    raw_series: dict[tuple[str, str, str, str], list[float | None]] = {}
    for ph in PHASE_WINDOWS:
        for metric_name, mspec in METRIC_SPECS.items():
            for fs in mspec.fields:
                for ent in sorted(entities_map[(metric_name, fs.field_id)]):
                    raw_series[(ph, metric_name, fs.field_id, ent)] = []

    for _, s in loaded:
        duration_map = build_duration_map(s)
        window_records = build_window_records(s)

        for ph in PHASE_WINDOWS:
            duration_series_s[ph].append(duration_map.get(ph))
            recs = window_records.get(ph, [])

            for metric_name, mspec in METRIC_SPECS.items():
                for fs in mspec.fields:
                    vals = _aggregate_by_entity(recs, metric_name, fs.raw_field, fs.agg) if recs else {}

                    if mspec.add_total_entity_for_sum_fields and fs.agg == "sum":
                        total = 0.0
                        found = False
                        for k, v in vals.items():
                            if k == "TOTAL":
                                continue
                            total += float(v)
                            found = True
                        if found:
                            vals["TOTAL"] = total

                    for ent in sorted(entities_map[(metric_name, fs.field_id)]):
                        v = vals.get(ent)
                        raw_series[(ph, metric_name, fs.field_id, ent)].append(float(v) if v is not None else None)

    # OUTPUT
    out_records: list[dict[str, Any]] = []

    for ph in PHASE_WINDOWS:
        phase_block: dict[str, Any] = {
            "phase": ph,
            "durations_s": duration_series_s[ph],
            "stats_duration_s": metric_summary(duration_series_s[ph]),
            "metrics": {},
        }

        for metric_name, mspec in METRIC_SPECS.items():
            metric_block = {
                "metric": metric_name,
                "fields": {},
            }

            for fs in mspec.fields:
                ents = sorted(entities_map[(metric_name, fs.field_id)])
                field_block: dict[str, Any] = {
                    "field_id": fs.field_id,
                    "raw_field": fs.raw_field,
                    "agg": fs.agg,
                    "unit_raw": fs.unit_raw,
                    "unit_converted": fs.unit_converted,
                    "entities": {},
                }

                for ent in ents:
                    values_raw = raw_series[(ph, metric_name, fs.field_id, ent)]

                    if fs.convert is not None:
                        values_conv: list[float | None] = [fs.convert(v) if v is not None else None for v in values_raw]
                    else:
                        # keep as-is
                        values_conv = list(values_raw)

                    field_block["entities"][ent] = {
                        "values_raw": values_raw,
                        "values_converted": values_conv,
                        "stats_converted": metric_summary(values_conv),
                    }

                metric_block["fields"][fs.field_id] = field_block

            phase_block["metrics"][metric_name] = metric_block

        out_records.append(phase_block)

    payload = {
        "meta": {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "input_dir": str(input_dir),
            "input_files": input_files_used,
            "runs": len(runs),
            "phases": list(PHASE_WINDOWS),
            "metrics": list(METRIC_SPECS.keys()),
            "metric_fields": {m: [fs.field_id for fs in METRIC_SPECS[m].fields] for m in METRIC_SPECS},
        },
        "run_info": runs,
        "records": out_records,
    }

    dump_json_gz(out_path, payload)
    print("========== SUMMARY DONE ==========")


if __name__ == "__main__":
    main()
