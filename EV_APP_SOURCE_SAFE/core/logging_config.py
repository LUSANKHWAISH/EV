import logging
import os
from pathlib import Path
from config.settings import settings
from core.paths import ensure_dir, get_log_dir, get_log_file_path

def setup_logging(name: str = "ev") -> logging.Logger:
    """
    Set up logging for E.V.
    Returns a logger configured with:
      - Console handler
      - File handler at %LOCALAPPDATA%\\EV\\logs\\ev.log (or configured log path)
    Respects EV_LOG_LEVEL from settings.
    Avoids adding duplicate handlers if called multiple times.
    """
    logger = logging.getLogger(name)
    # If the logger already has handlers, we assume it's been set up.
    if logger.handlers:
        return logger

    # Set level from settings (string like "INFO")
    log_level = getattr(logging, settings.EV_LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(log_level)

    # Create formatter
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler
    log_dir = ensure_dir(get_log_dir())
    log_file = get_log_file_path()
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger

# Example usage: if you want a default logger for the module, you can call setup_logging()
# But we leave it to the user to call and get a logger.
