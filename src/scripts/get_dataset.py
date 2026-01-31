import json
import re
from tqdm import tqdm
from pathlib import Path
from datasets import load_dataset

DATASET_SELECTION_PATH = "scripts/dataset.json"


def main():
    dataset_selction = json.loads(Path(DATASET_SELECTION_PATH).read_text(encoding="utf-8"))

    dataset = dataset_selction["dataset"]
    split = dataset_selction["split"]
    revision = dataset_selction["revision"]
    total_ids = dataset_selction["n"]
    ids = set(dataset_selction["ids"])

    out_dir = Path("/src/data/raw")
    out_dir.mkdir(parents=True, exist_ok=True)

    # Alte Dokumente löschen
    for p in out_dir.glob("*.txt"):
        p.unlink()

    ds = load_dataset(dataset, split=split, streaming=True, revision=revision)

    found = 0
    missing = set(ids)

    with tqdm(total=total_ids) as pbar:
        pbar.set_description(f"Datensatz {dataset} wird gespeichert")
        for row in ds:
            doc_id = row.get("id")
            if doc_id not in missing:
                continue

            text = row.get("text", "")
            file_name = out_dir / f"arxiv_{doc_id}.txt"
            file_name.write_text(text, encoding="utf-8", errors="ignore")

            missing.remove(doc_id)
            found += 1

            if not missing:
                break
            pbar.update(1)

    if missing:
        raise RuntimeError(
            f"{len(missing)}/{total_ids} Dokumente konnten nicht geladen werden."
        )

    print(f"{found}/{total_ids} Dokumente erfolgreich gespeichert.\n========== DATASET DOWNLOAD DONE ==========")


if __name__ == "__main__":
    main()
