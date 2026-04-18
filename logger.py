import logging
from logging.handlers import RotatingFileHandler
import os
from datetime import datetime
from config import TIME_ZONE


td = datetime.now(TIME_ZONE).date()
LOG_DIR = "logs"
LOG_FILE = f"Dhan_{td}.log"


def setup_logging(
    level=logging.DEBUG,
    console_level=logging.INFO,
    filename=LOG_FILE,
):
    """
    Configure logging for the entire application.
    Call this ONCE from main.py
    """

    # Create log directory if not exists
    os.makedirs(LOG_DIR, exist_ok=True)

    log_path = os.path.join(LOG_DIR, filename)

    # Formatter (same for console & file)
    formatter = logging.Formatter(
        "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
    )

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Prevent duplicate handlers (important)
    if root_logger.handlers:
        return

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(formatter)

    # File handler with rotation
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=5
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)