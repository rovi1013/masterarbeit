import argparse
import asyncio
import json
import gzip
from tqdm import tqdm
from pathlib import Path
from statistics import mean, stdev
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
    ap = argparse.ArgumentParser(description="Evaluation der RAG Antworten mit RAGAS.")
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
    llm = llm_factory(JUDGE_MODEL, provider="openai", client=client, temperature=0)
    embeddings = embedding_factory("openai", model=EMBEDDING_MODEL, client=client)

    faithfulness = Faithfulness(llm=llm)
    answer_rel = AnswerRelevancy(llm=llm, embeddings=embeddings)
    ctx_util = ContextUtilization(llm=llm)

    scored = []
    with tqdm(total=len(records)) as pbar:
        for r in records:
            q_id = r["q_id"]
            question = r["question"]
            answer = r["answer"]
            contexts = r.get("contexts") or []
            context_meta = r.get("context_meta") or []
            pbar.set_description(f"Frage {q_id} wird bearbeitet")

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
                "q_id": q_id,
                "question": question,
                "answer": answer,
                "context_meta": context_meta,
                "gold_doc": r["gold_doc"],
                "ground_truth": r["ground_truth"],
                "metrics": {
                    "faithfulness": f,
                    "answer_relevancy": ar,
                    "context_utilization": cu,
                }
            })

            pbar.update(1)

    def mavg(name):
        vals = [x["metrics"][name] for x in scored]
        return mean(vals) if vals else None

    def mstdev(name):
        vals = [x["metrics"][name] for x in scored]
        return stdev(vals) if vals else None

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
            "embedding_model": EMBEDDING_MODEL,
            "metrics": ["faithfulness", "answer_relevancy", "context_utilization"],
        },
        "summary": {
            "faithfulness_mean": mavg("faithfulness"),
            "faithfulness_stdev": mstdev("faithfulness"),
            "answer_relevancy_mean": mavg("answer_relevancy"),
            "answer_relevancy_stdev": mstdev("answer_relevancy"),
            "context_utilization_mean": mavg("context_utilization"),
            "context_utilization_stdev": mstdev("context_utilization"),
            "answers_scored": len(scored),
        },
        "records": scored,
    }

    dump_json_gz(out_path, out)
    print("========== EVALUATION DONE ==========")


if __name__ == "__main__":
    asyncio.run(main())
