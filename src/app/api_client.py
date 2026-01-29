from fastapi import FastAPI
from pydantic import BaseModel
from app.config import load_config
from app.rag_pipeline import RagPipeline
from app.simple_logging import setup_logging
from app.time_marker import mark

setup_logging()

cfg = load_config()
pipeline = RagPipeline(cfg)

app = FastAPI(title="RAG Baseline API")


class Question(BaseModel):
    q_id: str
    question: str


# Einfacher POST endpoint für RAG-APP
@app.post("/ask")
async def ask(payload: Question):
    q_id = payload.q_id
    mark("ASK_START", q_id=q_id)

    try:
        result = pipeline.answer(payload.q_id, payload.question)
        return result
    finally:
        mark("ASK_ENDT", q_id=q_id)
