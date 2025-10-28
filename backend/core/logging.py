# backend/core/logging.py

import logging
from logging.handlers import RotatingFileHandler
from core.config import get_settings
import sys
import json

settings = get_settings()


class JsonFormatter(logging.Formatter):
    """
    Optional JSON formatter for structured logging.
    Useful if you want logs parsed by Grafana / Loki / ELK stack.
    """
    def format(self, record):
        log_record = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "funcName": record.funcName,
            "lineNo": record.lineno
        }
        return json.dumps(log_record)


def setup_logging():
    """
    Configure logging for console and file with rotation.
    """
    logger = logging.getLogger()
    logger.setLevel(settings.LOG_LEVEL.upper())

    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(settings.LOG_LEVEL.upper())
    console_formatter = logging.Formatter(
        fmt="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # Rotating file handler
    file_handler = RotatingFileHandler(
        settings.LOG_FILE_PATH,
        maxBytes=5*1024*1024,  # 5 MB
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setLevel(settings.LOG_LEVEL.upper())

    # Use JSON logs for file (optional, comment if not needed)
    json_formatter = JsonFormatter()
    file_handler.setFormatter(json_formatter)

    logger.addHandler(file_handler)

    # Suppress noisy third-party logs if needed
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)

    logger.info("Logging initialized.")
    return logger


# Initialize logger
logger = setup_logging()
