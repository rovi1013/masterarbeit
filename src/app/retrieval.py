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
        include=["documents", "metadatas", "distances"],
    )

    docs = retrieval_result.get("documents", [[]])[0]
    metas = retrieval_result.get("metadatas", [[]])[0]
    dists = retrieval_result.get("distances", [[]])[0]
    if not docs:
        logger.warning("Keine Dokumente gefunden.")

    for rank, (meta, dist) in enumerate(zip(metas, dists), start=1):
        logger.debug(
            f"hit#{rank}: "
            f"source={meta.get('source')} "
            f"chunk={meta.get('chunk_index')} "
            f"dist={dist:.4f}"
        )

    logger.debug(f"Retriever hat {len(docs)} Dokumente zurückgegeben.")    # Für dynamisches top_k
    return docs
