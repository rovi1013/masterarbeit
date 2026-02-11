import json
import sys
import os
from tqdm import tqdm
from urllib.request import Request, urlopen

JSON_PATH = "./scripts/questions.json"
API_URL = "http://127.0.0.1:8000/ask"
PRINT = False   # os.getenv("RAG_PRINT_RESPONSES", "1") == "1"


def post_question(question: str, q_id: str) -> str:
    data = json.dumps({"q_id": q_id, "question": question}).encode("utf-8")
    req = Request(
        API_URL,
        data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=120) as response:
        return response.read().decode("utf-8", errors="replace")


def main():
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        items = json.load(f)

    with tqdm(total=len(items)) as pbar:
        for item in items:
            question = item.get("question")
            q_id = item.get("q_id")
            pbar.set_description(f"Frage #{q_id} wird bearbeitet")
            if not question:
                continue
            output = post_question(question, q_id)
            if PRINT:
                print(f"{output}\n")
            pbar.update(1)


if __name__ == "__main__":
    main()
