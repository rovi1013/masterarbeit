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
    model.encode(["Kleines Warmup"], convert_to_numpy=True)


if __name__ == '__main__':
    main()
    logger.info("========== WARMUP INDEXING FERTIG ==========")
