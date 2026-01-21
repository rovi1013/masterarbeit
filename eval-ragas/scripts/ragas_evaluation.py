import argparse
import asyncio
import json
import gzip
from pathlib import Path
from statistics import mean
from datetime import datetime, timezone

from openai import AsyncOpenAI
from ragas.llms import llm_factory
from ragas.embeddings.base import embedding_factory
from ragas.metrics.collections import Faithfulness, AnswerRelevancy, ContextUtilization


OLLAMA_BASE_URL = "http://localhost:11434/v1"
OLLAMA_API_KEY = "ollama"
JUDGE_MODEL = "mistral-small:24b-instruct-2501-q4_K_M"
EMBEDDING_MODEL = "bge-m3:567m"


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def dump_json_gz(path: Path, obj):
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-i", "--input", required=True, help="Pfad zu *_answers.json.")
    args = ap.parse_args()

    in_path = Path(args.input)
    data = load_json(in_path)

    meta = data["meta"]
    records = data["records"]

    run_id = meta["run_id"]
    run_date = meta["run_date"]

    out_path = in_path.with_name(f"{in_path.stem}_eval.json.gz")

    client = AsyncOpenAI(api_key=OLLAMA_API_KEY, base_url=OLLAMA_BASE_URL)
    llm = llm_factory(JUDGE_MODEL, provider="openai", client=client)
    embeddings = embedding_factory("openai", model=EMBEDDING_MODEL, client=client)

    faithfulness = Faithfulness(llm=llm)
    answer_rel = AnswerRelevancy(llm=llm, embeddings=embeddings)
    ctx_util = ContextUtilization(llm=llm)

    scored = []
    for r in records:
        question = r["question"]
        answer = r["answer"]
        contexts = r.get("contexts") or []
        context_meta = r.get("context_meta") or []

        f = (await faithfulness.ascore(
            user_input=question,
            response=answer,
            retrieved_contexts=contexts
        )).value

        ar = (await answer_rel.ascore(
            user_input=question,
            response=answer
        )).value

        cu = (await ctx_util.ascore(
            user_input=question,
            response=answer,
            retrieved_contexts=contexts
        )).value

        scored.append({
            "id": r["id"],
            "category": r.get("category"),
            "question": question,
            "answer": answer,
            "context_meta": context_meta,
            "metrics": {
                "faithfulness": f,
                "answer_relevancy": ar,
                "context_utilization": cu,
            }
        })

        print(f"Frage [{r["id"]}] evaluiert.")

    def mavg(name):
        vals = [x["metrics"][name] for x in scored]
        return mean(vals) if vals else None

    out = {
        "meta": {
            "run_id": run_id,
            "run_date": run_date,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "input_file": in_path.name,
            "judge": {
                "base_url": OLLAMA_BASE_URL,
                "model": JUDGE_MODEL,
            },
            "embeddings": {
                "model": EMBEDDING_MODEL,
            },
            "metrics": ["faithfulness", "answer_relevancy", "context_utilization"],
        },
        "summary": {
            "faithfulness_mean": mavg("faithfulness"),
            "answer_relevancy_mean": mavg("answer_relevancy"),
            "context_utilization_mean": mavg("context_utilization"),
            "answers_scored": len(scored),
        },
        "records": scored,
    }

    dump_json_gz(out_path, out)
    print(f"Ergebnisse der Evaluation: {out_path}\n########## EVALUATION DONE ##########")


if __name__ == "__main__":
    asyncio.run(main())
