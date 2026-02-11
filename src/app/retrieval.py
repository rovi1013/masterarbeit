import logging
import chromadb
from pathlib import Path

from app.config import Config, load_config
from app.embedding import get_embed_model

logger = logging.getLogger(__name__)


def get_collection(cfg: Config | None = None):
    if cfg is None:
        cfg = load_config()

    client = chromadb.PersistentClient(path=cfg.index_dir)
    return client.get_or_create_collection("rag")


def retrieve(cfg: Config, question: str):
    collection = get_collection(cfg)

    model = get_embed_model(cfg)
    query_emb = model.encode(
        [question],
        batch_size=128,
        convert_to_numpy=True,
        normalize_embeddings=cfg.normalize_embeddings,
    )

    retrieval_result = collection.query(
        query_embeddings=query_emb,
        n_results=cfg.top_k,
        include=["metadatas", "distances"],
    )

    metas = retrieval_result.get("metadatas", [[]])[0]
    dists = retrieval_result.get("distances", [[]])[0]

    file_cache: dict[str, str] = {}

    docs: list[str] = []
    for rank, (meta, dist) in enumerate(zip(metas, dists), start=1):
        src = meta.get("source")
        start = int(meta.get("chunk_start", 0))
        end = int(meta.get("chunk_end", 0))

        if not src or end <= start:
            docs.append("")
        else:
            try:
                if src not in file_cache:
                    file_cache[src] = Path(src).read_text(encoding="utf-8", errors="ignore")
                docs.append(file_cache[src][start:end])
            except Exception as e:
                logger.warning(f"Chunk konnte nicht geladen werden: {src} ({e})")
                docs.append("")

        logger.debug(
            f"hit#{rank}: "
            f"source={meta.get('source')} "
            f"chunk={meta.get('chunk_index')} "
            f"dist={dist:.4f}"
        )

    logger.debug(f"Retriever hat {len(docs)} Dokumente zurückgegeben.")
    return docs, metas
