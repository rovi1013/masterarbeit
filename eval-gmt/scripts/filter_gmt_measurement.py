import json
import argparse
import ijson
import gzip
from pathlib import Path

DATA_DIR = Path("gmt-data/raw-data")

METRICS = {
    # Energie
    "cpu_energy_rapl_msr_component": {
        "units": {"uJ"},
        "entities": None,  # None = alle Entities behalten
    },
    "memory_energy_rapl_msr_component": {
        "units": {"uJ"},
        "entities": None,
    },

    # Utilization
    "cpu_utilization_cgroup_container": {
        "units": {"Ratio"},
        "entities": {"rag-app", "ollama"},  # ollama optional
    },
    "cpu_utilization_procfs_system": {
        "units": {"Ratio"},
        "entities": {"[SYSTEM]"},
    },

    # Memory used cgroup
    "memory_used_cgroup_container": {
        "units": {"Bytes", "bytes", "Byte", "B"},
        "entities": {"rag-app", "ollama"},
    },

    # GPU Energie
    "gpu_energy_nvidia_nvml_component": {
        "units": {"uJ"},
        "entities": None,
    },
}


def should_keep(entity: str, metric: str, unit: str) -> bool:
    rule = METRICS.get(metric)
    if not rule:
        return False
    units = rule.get("units")
    if units and unit not in units:
        return False
    entities = rule.get("entities")
    if entities is not None and entity not in entities:
        return False
    return True


def check_output(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "wt", compresslevel=9, encoding="utf-8")
    return open(path, "w", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-i", "--input", required=True, help="Input JSON Datei von GMT.")
    ap.add_argument(
        "-p", "--plain",
        action="store_true",
        help="Output als plain .json (sonst komprimiert zu .json.gz)."
    )
    args = ap.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    in_path = DATA_DIR / args.input

    base = args.input
    if base.endswith(".gz"):
        base = base[:-3]
    if base.endswith(".json"):
        base = base[:-5]
    out_path = DATA_DIR / (f"{base}_filtered.json" if args.plain else f"{base}_filtered.json.gz")

    kept = 0
    total = 0
    first = True

    with open(in_path, "rb") as fin, check_output(out_path) as fout:
        # Header
        fout.write('{"success": true,"data":[')

        # Streaming über data.item
        for row in ijson.items(fin, "data.item"):
            total += 1
            # row ist [entity, ts_us, metric, value, unit]
            try:
                entity, ts_us, metric, value, unit = row
            except ValueError:
                continue

            if not should_keep(str(entity), str(metric), str(unit)):
                continue

            if not first:
                fout.write(",")
            else:
                first = False

            fout.write(json.dumps([entity, ts_us, metric, value, unit], ensure_ascii=False))
            kept += 1

        # Footer
        fout.write("]}\n")

    print(f"JSON von {total} Reihen auf {kept} Reihen reduziert.\n########## FILTERING DONE ##########")


if __name__ == "__main__":
    main()
