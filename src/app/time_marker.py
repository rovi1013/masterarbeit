import time
import logging

logger = logging.getLogger(__name__)

PREFIX = "##TIME_MARK##"


def mark(event: str, **kv):
    ts_us = time.time_ns() // 1000  # Mikrosekunden wie GMT
    meta = " ".join(f"{k}={v}" for k, v in kv.items())
    line = f"{PREFIX} ts_us={ts_us} event={event}" + (f"{meta}" if meta else "")
    logger.info(line)
    return ts_us
