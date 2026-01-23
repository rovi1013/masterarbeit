import json
import sys
import os
from urllib.request import Request, urlopen

JSON_PATH = "./scripts/questions.json"
API_URL = "http://127.0.0.1:8000/ask"
PRINT = os.getenv("RAG_PRINT_RESPONSES", "1") == "1"


def post_question(question: str, q_id: str) -> str:
    data = json.dumps({"question": question, "q_id": q_id}).encode("utf-8")
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

    for item in items:
        question = item.get("question")
        q_id = item.get("q_id")
        if not question:
            continue
        output = post_question(question, q_id)
        if PRINT:
            print(f"{output}\n")


if __name__ == "__main__":
    main()
