import logging

from app.config import load_config
from app.simple_logging import setup_logging
from app.indexing import reset_index_dir
from app.embedding import get_embed_model

logger = logging.getLogger(__name__)


def main():
    setup_logging()
    cfg = load_config()

    # Alte DB löschen
    reset_index_dir(cfg.index_dir)

    # Embedding Model vorladen und ein einfaches embedding ausführen
    model = get_embed_model(cfg)
    embedding_1 = model.encode(["Kleines Warmup"], convert_to_numpy=True)
    embedding_2 = model.encode(["Kleines Warmup_"], convert_to_numpy=True)
    similarity = model.similarity(embedding_1, embedding_2)
    logger.debug(f"[WARMUP] Ergebnisse der Ähnlichkeitsmessung: {similarity.item()}")
    model.encode(["Kleines Warmup"], convert_to_numpy=True)


if __name__ == '__main__':
    main()
    logger.info("========== WARMUP INDEXING FERTIG ==========")
