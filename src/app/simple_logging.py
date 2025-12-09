import logging
import os
import sys
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler

from app.config import load_config


def setup_logging():
    cfg = load_config()
    level_name = cfg.log_level.upper().strip()
    level = getattr(logging, level_name, logging.INFO)

    log_path = Path(os.getenv("LOG_DIR", "/logs")).resolve()
    log_path.mkdir(parents=True, exist_ok=True)
    log_file = log_path / "rag_app.log"

    logger = logging.getLogger()
    if logger.handlers:
        return

    logger.setLevel(level)

    logging_format = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging_format)
    logger.addHandler(console)

    file_handler = TimedRotatingFileHandler(
        log_file,
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
        utc=False,
    )
    file_handler.suffix = "%Y-%m-%d"
    file_handler.setFormatter(logging_format)
    logger.addHandler(file_handler)

    logger.info(f"Logging started (Lvl={level_name}; File={log_file})")
