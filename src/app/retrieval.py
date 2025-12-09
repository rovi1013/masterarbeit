import logging
import chromadb

from app.config import Config, load_config
from app.embedding import get_embed_model

logger = logging.getLogger(__name__)


def get_collection(cfg: Config | None = None):
    if cfg is None:
        cfg = load_config()

    client = chromadb.PersistentClient(path=cfg.index_dir)
    return client.get_or_create_collection("rag")


def retrieve(cfg: Config, question: str) -> list[str]:
    collection = get_collection(cfg)

    model = get_embed_model(cfg)
    query_emb = model.encode(
        [question],
        convert_to_numpy=True,
        normalize_embeddings=True,
    ).tolist()

    retrieval_result = collection.query(
        query_embeddings=query_emb,
        n_results=cfg.top_k,
    )

    docs = retrieval_result.get("documents", [[]])[0]
    if not docs:
        logger.warning("Keine Dokumente gefunden.")

    logger.debug(f"Retriever hat {len(docs)} Dokumente zurückgegeben.")    # Für dynamisches top_k
    return docs
