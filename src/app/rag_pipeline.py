from app.config import Config, load_config
from app.retrieval import retrieve
from app.llm_client import OllamaClient
from app.prompt_template import BASE_PROMPT


class RagPipeline:
    def __init__(self, cfg: Config | None = None):
        if cfg is None:
            cfg = load_config()
        self.cfg = cfg
        self.llm = OllamaClient(cfg)

    def answer(self, q_id: str, question: str) -> dict:
        docs, metas = retrieve(self.cfg, question)
        context = "\n\n".join(docs)

        prompt = BASE_PROMPT.format(context=context, question=question)
        answer = self.llm.generate(prompt)

        return {
            "q_id": q_id,
            "question": question,
            "answer": answer,
            "context": docs,
            "context_meta": metas,
        }
