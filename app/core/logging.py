import logging
import os
from pathlib import Path


def configure_logging() -> None:
    root = logging.getLogger()

    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    log_path = Path(os.getenv("APP_LOG_FILE", "logs/backend.log"))
    log_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_path = str(log_path.resolve())

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )
    root.setLevel(level)

    has_file_handler = any(
        isinstance(handler, logging.FileHandler)
        and str(Path(getattr(handler, "baseFilename", "")).resolve()) == resolved_path
        for handler in root.handlers
    )
    if not has_file_handler:
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    has_stream_handler = any(
        isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler)
        for handler in root.handlers
    )
    if not has_stream_handler:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        root.addHandler(stream_handler)
