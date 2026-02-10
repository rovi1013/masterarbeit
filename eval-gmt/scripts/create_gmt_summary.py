from __future__ import annotations

import argparse
import gzip
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, stdev, quantiles
from typing import Any


ENERGY_METRICS: tuple[str, ...] = (
    "cpu_energy_rapl_msr_component",
    "memory_energy_rapl_msr_component",
    "gpu_energy_nvidia_nvml_component",
    "psu_energy_ac_mcp_machine",
)

PHASE_WINDOWS: tuple[str, ...] = (
    "[RUNTIME]",
    "Download Dataset",
    "Warmup Indexing",
    "Indexing",
    "Indexing/CHUNKING",
    "Indexing/EMBEDDING",
    "Indexing/PERSIST_IN_DB",
    "Warmup RAG",
    "RAG Querries",
)


def load_json(path: Path) -> dict[str, Any]:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return json.load(f)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def dump_json_gz(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def find_merged_files(input_dir: Path) -> list[Path]:
    files: list[Path] = []
    for pat in ("*_merged.json", "*_merged.json.gz"):
        files.extend(input_dir.rglob(pat))
    return sorted(set(files), key=lambda p: p.as_posix())


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


# Summe des Energieverbrauchs (mikrojoule) über alle Entities einem Window und Metrik
def extract_energy_u_j(records: list[dict[str, Any]], metric_name: str) -> int | None:
    total = 0.0
    found = False

    for rec in records:
        metrics = rec.get("metrics") or {}
        mb = metrics.get(metric_name)
        if not isinstance(mb, dict):
            continue

        entities = mb.get("entities") or {}
        if not isinstance(entities, dict):
            continue

        for ent in entities.values():
            if not isinstance(ent, dict):
                continue
            v = ent.get("sum")
            if v is None:
                continue
            total += float(v)
            found = True

    return int(round(total)) if found else None


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
    ap = argparse.ArgumentParser(description="Aggregiert mehrere GMT *_merged.json(.gz) über Runs.")
    ap.add_argument("-i", "--input-dir", required=True, help="Ordner mit *_merged.json oder *_merged.json.gz Dateien.")
    ap.add_argument("-o", default="gmt_runs_aggregated", help="Ausgabename ohne Endung (.json.gz wird angehaengt).")
    args = ap.parse_args()

    input_dir = Path(args.input_dir)
    if not input_dir.is_dir():
        raise SystemExit(f"Kein Ordner: {input_dir}")

    files = find_merged_files(input_dir)
    if not files:
        raise SystemExit("Keine *_merged.json(.gz) Datei gefunden.")

    out_path = input_dir / f"{args.output_name}.json.gz"

    runs: list[dict[str, Any]] = []

    duration_series_s: dict[str, list[float | None]] = {ph: [] for ph in PHASE_WINDOWS}
    energy_series_u_j: dict[tuple[str, str], list[int | None]] = {
        (ph, m): [] for ph in PHASE_WINDOWS for m in ENERGY_METRICS
    }
    energy_series_j: dict[tuple[str, str], list[float | None]] = {
        (ph, m): [] for ph in PHASE_WINDOWS for m in ENERGY_METRICS
    }

    input_files_used: list[str] = []

    for f in files:
        s = load_json(f)
        input_files_used.append(f.name)

        run_name = (s.get("run") or {}).get("name") or f.stem
        run_id = (s.get("run") or {}).get("id") or f.stem
        runs.append({"run_id": run_id, "run_name": run_name, "file": str(f)})

        duration_map = build_duration_map(s)
        window_records = build_window_records(s)

        for ph in PHASE_WINDOWS:
            dur_s = duration_map.get(ph)
            duration_series_s[ph].append(dur_s)

            recs = window_records.get(ph, [])
            for m in ENERGY_METRICS:
                u_j = extract_energy_u_j(recs, m)
                j = (u_j / 1e6) if u_j is not None else None
                energy_series_u_j[(ph, m)].append(u_j)
                energy_series_j[(ph, m)].append(j)

    # records
    out_records: list[dict[str, Any]] = []
    flat_results: list[dict[str, Any]] = []
    for ph in PHASE_WINDOWS:
        phase_block: dict[str, Any] = {
            "phase": ph,
            "durations_s": duration_series_s[ph],
            "stats_duration_s": metric_summary(duration_series_s[ph]),
            "metrics": {},
        }

        for m in ENERGY_METRICS:
            values_u_j = energy_series_u_j[(ph, m)]
            values_j = energy_series_j[(ph, m)]

            phase_block["metrics"][m] = {
                "unit_raw": "uJ",
                "unit_converted": "J",
                "raw_field_energy": "sum",
                "values_uJ": values_u_j,
                "values_J": values_j,
                "stats_J": metric_summary(values_j),
            }

            flat_results.append(
                {
                    "phase": ph,
                    "metric": m,
                    "unit_raw": "uJ",
                    "unit_converted": "J",
                    "raw_field_energy": "sum",
                    "durations_s": duration_series_s[ph],
                    "stats_duration_s": phase_block["stats_duration_s"],
                    "values_uJ": values_u_j,
                    "values_J": values_j,
                    "stats_J": phase_block["metrics"][m]["stats_J"],
                }
            )

        out_records.append(phase_block)

    payload = {
        "meta": {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "input_dir": str(input_dir),
            "input_files": input_files_used,
            "runs": len(runs),
            "phases": list(PHASE_WINDOWS),
            "metrics": list(ENERGY_METRICS),
        },
        "run_info": runs,
        "records": out_records,
        "results": flat_results,
    }

    dump_json_gz(out_path, payload)
    print("========== SUMMARY DONE ==========")


if __name__ == "__main__":
    main()
