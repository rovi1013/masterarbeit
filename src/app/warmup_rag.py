import logging

from app.config import load_config
from app.simple_logging import setup_logging
from app.rag_pipeline import RagPipeline
from app.retrieval import get_collection
from app.embedding import get_embed_model

logger = logging.getLogger(__name__)


def main():
    setup_logging()
    cfg = load_config()

    # Collection öffnen (pre-loading)
    collection = get_collection(cfg)
    logger.debug(f"[WARMUP] Collection Größe: {collection.count()} Chunks.")
    result_10 = collection.get(ids="10")
    logger.debug(f"[WARMUP] Collection-Eintrag der ID #10:\n{result_10.get("documents", [[]])}\n====================")

    # Embedding Model vorladen und ein einfaches embedding ausführen
    model = get_embed_model(cfg)
    embedding_1 = model.encode(["Kleines Warmup"], convert_to_numpy=True)
    embedding_2 = model.encode(["Kleines Warmup_"], convert_to_numpy=True)
    similarity = model.similarity(embedding_1, embedding_2)
    logger.debug(f"[WARMUP] Ergebnis der Test-Ähnlichkeitsmessung: {similarity.item()}.")

    # LLM einmal aufrufen
    pipeline = RagPipeline(cfg)
    response = pipeline.llm.generate("Das ist ein Warmup. Antworte mit 'OK'")
    logger.debug(f"[WARMUP] Antwort der LLM: {response}.")


if __name__ == '__main__':
    main()
    logger.info("========== WARMUP RAG-APP FERTIG ==========")
