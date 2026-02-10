import argparse
import asyncio
import gzip
import json
import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, stdev, quantiles
from tqdm import tqdm
from typing import Any

from openai import AsyncOpenAI
from ragas.embeddings.base import embedding_factory
from ragas.llms import llm_factory
from ragas.metrics.collections import AnswerRelevancy, ContextUtilization, Faithfulness


JUDGE_MODEL = "gpt-4o-mini"
EMBEDDING_MODEL = "text-embedding-3-small"
JUDGE_TEMPERATURE = 0.0
ANSWER_RELEVANCY_STRICTNESS = 3
CONCURRENCY = 4


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def dump_json_gz(path: Path, obj: dict[str, Any]) -> None:
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


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

    return {
        "n": n,
        "mean": m,
        "stdev": sd,
        "cv_pct": cv_pct,
        "min": vals[0],
        "max": vals[-1],
        "p10": p10,
        "p25": p25,
        "p50": p50,
        "p75": p75,
        "p90": p90,
    }


async def call_with_retries(coro_factory, *, retries: int = 6, base_delay: float = 1.0):
    delay = base_delay
    last_err = None
    for attempt in range(retries):
        try:
            return await coro_factory()
        except Exception as e:
            msg = str(e)
            rate_limit_429 = "429" in msg or "rate limit" in msg.lower()
            kind = "RATE_LIMIT" if rate_limit_429 else "ERROR"
            print(f"[{kind}] retry {attempt+1}/{retries} in {delay:.1f}s: {msg}")
            if attempt == retries - 1:
                raise
            await asyncio.sleep(delay)
            delay = min(delay * 2, 30.0)


@dataclass
class ScoredRecord:
    idx: int
    q_id: str
    item: dict[str, Any]


async def score_one_record(
    idx: int,
    r: dict[str, Any],
    sem: asyncio.Semaphore,
    faithfulness: Faithfulness,
    answer_rel: AnswerRelevancy,
    ctx_util: ContextUtilization,
) -> ScoredRecord:
    async with sem:
        q_id = r["q_id"]
        question = r["question"]
        answer = r["answer"]
        contexts = r.get("contexts") or []
        context_meta = r.get("context_meta") or []

        f_res = await call_with_retries(
            lambda: faithfulness.ascore(
                user_input=question,
                response=answer,
                retrieved_contexts=contexts,
            )
        )
        ar_res = await call_with_retries(
            lambda: answer_rel.ascore(
                user_input=question,
                response=answer,
            )
        )
        cu_res = await call_with_retries(
            lambda: ctx_util.ascore(
                user_input=question,
                response=answer,
                retrieved_contexts=contexts,
            )
        )

        item = {
            "q_id": q_id,
            "question": question,
            "answer": answer,
            "context_meta": context_meta,
            "gold_doc": r.get("gold_doc"),
            "ground_truth": r.get("ground_truth"),
            "metrics": {
                "faithfulness": f_res.value,
                "answer_relevancy": ar_res.value,
                "context_utilization": cu_res.value,
            },
        }
        return ScoredRecord(idx=idx, q_id=q_id, item=item)


async def main():
    ap = argparse.ArgumentParser(description="RAGAS Evaluation via OpenAI API.")
    ap.add_argument("-i", "--input", required=True, help="Pfad zu *_answers.json.")
    ap.add_argument("-k", "--openai-api-key", required=True, help="OpenAI API Key.")
    args = ap.parse_args()

    in_path = Path(args.input)
    data = load_json(in_path)

    meta_in = data.get("meta", {})
    records = data.get("records", [])

    out_path = in_path.with_name(f"{in_path.stem}_eval.json.gz")

    client = AsyncOpenAI(api_key=args.openai_api_key)

    llm = llm_factory(
        JUDGE_MODEL,
        provider="openai",
        client=client,
        temperature=JUDGE_TEMPERATURE,
    )
    embeddings = embedding_factory(
        "openai",
        model=EMBEDDING_MODEL,
        client=client,
    )

    faithfulness = Faithfulness(llm=llm)
    answer_rel = AnswerRelevancy(llm=llm, embeddings=embeddings, strictness=ANSWER_RELEVANCY_STRICTNESS)
    ctx_util = ContextUtilization(llm=llm)

    sem = asyncio.Semaphore(max(1, int(CONCURRENCY)))

    tasks = [
        asyncio.create_task(score_one_record(i, r, sem, faithfulness, answer_rel, ctx_util))
        for i, r in enumerate(records)
    ]

    scored: list[dict[str, Any] | None] = [None] * len(records)
    with tqdm(total=len(tasks)) as pbar:
        for fut in asyncio.as_completed(tasks):
            res: ScoredRecord = await fut
            scored[res.idx] = res.item
            pbar.set_description(f"Evaluation von Frage {res.q_id} abgeschlossen")
            pbar.update(1)

    scored_records = [x for x in scored if x is not None]

    f_vals = [r["metrics"]["faithfulness"] for r in scored_records]
    ar_vals = [r["metrics"]["answer_relevancy"] for r in scored_records]
    cu_vals = [r["metrics"]["context_utilization"] for r in scored_records]

    out = {
        "meta": {
            "run_id": meta_in.get("run_id"),
            "run_date": meta_in.get("run_date"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "input_file": in_path.name,
            "judge": {
                "provider": "openai",
                "model": JUDGE_MODEL,
                "temperature": JUDGE_TEMPERATURE,
            },
            "embedding_model": EMBEDDING_MODEL,
            "answer_relevancy_strictness": ANSWER_RELEVANCY_STRICTNESS,
            "concurrency": int(CONCURRENCY),
            "metrics": ["faithfulness", "answer_relevancy", "context_utilization"],
        },
        "summary": {
            "faithfulness": metric_summary(f_vals),
            "answerRelevancy": metric_summary(ar_vals),
            "contextUtilization": metric_summary(cu_vals),
        },
        "records": scored_records,
    }

    dump_json_gz(out_path, out)
    print("========== EVALUATION DONE ==========")


if __name__ == "__main__":
    asyncio.run(main())
