from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from app.core.settings import get_log_dir


def configure_logging() -> None:
    root = logging.getLogger()
    if getattr(root, "_factory_counter_configured", False):
        return

    log_dir = get_log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "factory_counter.log"

    formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")

    file_handler = RotatingFileHandler(log_path, maxBytes=1_000_000, backupCount=3)
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    root.setLevel(logging.INFO)
    root.addHandler(file_handler)
    root.addHandler(stream_handler)
    root._factory_counter_configured = True  # type: ignore[attr-defined]
