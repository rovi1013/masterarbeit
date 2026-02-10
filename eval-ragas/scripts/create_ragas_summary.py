from __future__ import annotations

import argparse
import gzip
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, stdev, quantiles
from typing import Any


RAGAS_METRICS: tuple[str, ...] = (
    "faithfulness",
    "answer_relevancy",
    "context_utilization",
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


def find_eval_files(input_dir: Path) -> list[Path]:
    files: list[Path] = []
    for pat in ("*_eval.json", "*_eval.json.gz"):
        files.extend(input_dir.rglob(pat))
    return sorted(set(files), key=lambda p: p.as_posix())


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
        return round(float(x), 5)

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
    ap = argparse.ArgumentParser(description="Aggregiert mehrere RAGAS *_eval.json(.gz) pro q_id über Runs.")
    ap.add_argument("-i", "--input-dir", required=True, help="Ordner mit *_eval.json oder *_eval.json.gz Dateien.")
    ap.add_argument(
        "-o",
        "--output-name",
        default="ragas_runs_aggregated",
        help="Ausgabename ohne Endung (.json.gz wird angehängt).",
    )
    args = ap.parse_args()

    input_dir = Path(args.input_dir)
    if not input_dir.is_dir():
        raise SystemExit(f"Kein Ordner: {input_dir}")

    out_path = input_dir / f"{args.output_name}.json.gz"

    files = find_eval_files(input_dir)
    if not files:
        raise SystemExit(f"Keine *_eval.json(.gz) Dateien in: {input_dir}")

    # data[q_id][metric] -> Liste der Werte über Runs
    data: dict[str, dict[str, list[float | None]]] = {}
    run_files_used: list[str] = []

    # run metadata
    run_info: list[dict[str, Any]] = []

    pooled: dict[str, list[float | None]] = {m: [] for m in RAGAS_METRICS}
    run_means: dict[str, list[float | None]] = {m: [] for m in RAGAS_METRICS}

    for f in files:
        obj = load_json(f)
        records = obj.get("records", [])
        run_files_used.append(f.name)

        run_info.append({
            "run_name": f.stem.replace(".json", ""),
            "file": str(f),
        })

        per_run_vals: dict[str, list[float]] = {m: [] for m in RAGAS_METRICS}

        for r in records:
            q_id = r.get("q_id")
            if not q_id:
                continue

            metrics = r.get("metrics", {})
            if not isinstance(metrics, dict):
                continue

            data.setdefault(q_id, {})

            for m in RAGAS_METRICS:
                v = metrics.get(m)
                if v is None:
                    continue

                fv = float(v)
                data[q_id].setdefault(m, []).append(fv)
                pooled[m].append(fv)
                per_run_vals[m].append(fv)

        # pro run: mean über alle fragen
        for m in RAGAS_METRICS:
            vals = per_run_vals[m]
            run_means[m].append(float(mean(vals)) if vals else None)

    # pro frage: stats über runs
    out_records: list[dict[str, Any]] = []
    for q_id in sorted(data.keys()):
        out_item = {"q_id": q_id, "metrics": {}}
        for m in RAGAS_METRICS:
            out_item["metrics"][m] = metric_summary(data[q_id].get(m, []))
        out_records.append(out_item)

    # overall: (1) gepoolt über alle werte, (2) per-run-mean, (3) verteilung der frage-means
    overall: dict[str, Any] = {}
    for m in RAGAS_METRICS:
        question_means = [
            rec["metrics"][m]["mean"]
            for rec in out_records
            if rec["metrics"].get(m, {}).get("mean") is not None
        ]

        overall[m] = {
            # Alle Fragen aus allen Runs zusammen ausgewertet
            "pooled": metric_summary(pooled.get(m, [])),
            # Erst Mittelwerte über alle Fragen eines Runs, dann alle Runs aggregiert
            "per_run_mean": metric_summary(run_means.get(m, [])),
            # Erst Mittelwerte über alle Runs einer Frage, dann alle Fragen aggregiert
            "per_question_mean": metric_summary(question_means),
        }

    payload = {
        "meta": {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "input_dir": str(input_dir),
            "input_files": run_files_used,
            "runs": len(run_files_used),
            "questions": len(out_records),
            "metrics": list(RAGAS_METRICS),
        },
        "run_info": run_info,
        "overall": overall,
        "records": out_records,
    }

    dump_json_gz(out_path, payload)
    print("========== SUMMARY DONE ==========")


if __name__ == "__main__":
    main()
