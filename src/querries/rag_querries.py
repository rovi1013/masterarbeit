import json
import sys
import urllib.request

JSON_PATH = "./querries/questions.json"
API_URL = "http://127.0.0.1:8000/ask"


def post_question(question: str) -> str:
    data = json.dumps({"question": question}).encode("utf-8")
    req = urlib.request.Request(
        API_URL,
        data,
        headers={"Content-Type": "application/json"},
        method=POST,
    )
    with urlib.request.urlopen(req, timeout=120) as response:
        return response.read().decode("utf-8", errors="replace")


def main():
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        items = json.load(f)

    for item in items:
        question = item.get("question")
        if not question:
            continue
        output = post_question(question)
        print(f"{output}\n")


if __name__ == "__main__":
    main()
