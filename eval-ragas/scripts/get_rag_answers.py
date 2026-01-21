import argparse
import json
import datetime
from pathlib import Path
from urllib.request import Request, urlopen

QUESTIONS_PATH = Path("questions.json")
OUT_DIR = Path("ragas-data")
API_URL = "http://localhost:8000/ask"


def parse_args():
    p = argparse.ArgumentParser(description="Lade Antworten der RAG API für RAGAS Messungen.")
    p.add_argument("-r", "--run-id", required=True, help="Dazugehörige GMT Messlauf ID.")
    p.add_argument("-d", "--date", required=True, help="Datum des Messlaufs YYYY-MM-DD (gleich wie GMT).")
    return p.parse_args()


def read_questions(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def fetch_json(question: str, timeout_s: int):
    try:
        payload = json.dumps({"question": question}).encode("utf-8")
        req = Request(
            API_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read()
            return json.loads(raw.decode("utf-8"))

    except Exception as e:
        raise RuntimeError(f"Request fehlgeschlagen: {e}") from e


def main():
    args = parse_args()

    try:
        run_date = datetime.date.fromisoformat(args.date)
    except ValueError:
        print("Falsches Datumsformat, richtig: YYYY-MM-DD.")
        return

    run_id = str(args.run_id).strip()

    try:
        questions = read_questions(QUESTIONS_PATH)
    except Exception as e:
        print(f"{QUESTIONS_PATH} kann nicht gelesen werden: {e}.")
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{run_date.isoformat()}_{run_id}_answers.json"

    records = []
    ok = 0

    for idx, q in enumerate(questions, start=1):
        qid = q.get("id")
        question = q.get("question")
        category = q.get("category", None)

        record = {
            "id": qid,
            "category": category,
            "question": question,
            "answer": None,
            "contexts": [],
            "context_meta": [],
            "ground_truth": None,
            "error": None,
        }

        res = fetch_json(question, 60)
        record["answer"] = res.get("answer")
        record["contexts"] = res.get("context", []) or []
        record["context_meta"] = res.get("context_meta", []) or []
        ok += 1

        records.append(record)

    out_json = {
        "meta": {
            "run_id": run_id,
            "run_date": run_date.isoformat(),
            "api_url": API_URL,
        },
        "records": records,
    }

    json.dump(out_json, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))

    print(f"Erfolgereiche Fragen: {ok}/{len(questions)}.\n########## DOWNLOAD DONE ##########")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(e)
        raise SystemExit(1)
