"""
Canonical Path & Directory Resolution for E.V.

Provides deterministic resolution for:
1. Application resources (read-only bundled assets, QML, AI models).
2. User runtime data (writable databases, logs, backups, configuration).

Supports both source/development execution and packaged/frozen execution
(PyInstaller, cx_Freeze) with explicit environment variable overrides
for testing and deployment isolation.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys
from typing import Union


def is_frozen() -> bool:
    """Return True if running in a frozen/packaged Python bundle."""
    return getattr(sys, "frozen", False)


def get_resource_root() -> Path:
    """
    Resolve the root directory containing bundled application resources.

    Order of precedence:
    1. EV_RESOURCE_ROOT environment variable (if set and non-empty).
    2. sys._MEIPASS (when running in a PyInstaller bundle).
    3. Directory containing sys.executable (if frozen without _MEIPASS).
    4. Repository/project root (source execution, derived from this file).
    """
    env_root = os.getenv("EV_RESOURCE_ROOT")
    if env_root and env_root.strip():
        return Path(env_root.strip()).resolve()

    if is_frozen():
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass).resolve()
        return Path(sys.executable).parent.resolve()

    # Source tree: core/paths.py -> parent is core/ -> parent is project root
    return Path(__file__).resolve().parent.parent


def get_qml_root() -> Path:
    """Return the directory containing QML root files and components."""
    return get_resource_root() / "gui" / "qml"


def get_models_dir() -> Path:
    """
    Return the base directory for bundled AI models.
    Supports EV_MODELS_DIR override.
    """
    env_models = os.getenv("EV_MODELS_DIR")
    if env_models and env_models.strip():
        return Path(env_models.strip()).resolve()
    return get_resource_root() / "models"


def get_wakeword_model_dir() -> Path:
    """
    Return the directory for wake-word ONNX models.
    Supports EV_WAKEWORD_MODEL_DIR override.
    """
    env_ww = os.getenv("EV_WAKEWORD_MODEL_DIR")
    if env_ww and env_ww.strip():
        return Path(env_ww.strip()).resolve()
    return get_models_dir() / "wakeword"


def get_asr_model_dir() -> Path:
    """
    Return the directory for ASR models (faster-whisper).
    Supports EV_ASR_MODEL_DIR override.
    """
    env_asr = os.getenv("EV_ASR_MODEL_DIR")
    if env_asr and env_asr.strip():
        return Path(env_asr.strip()).resolve()
    return get_models_dir() / "asr"


def get_user_data_root() -> Path:
    """
    Resolve the root directory for user-writable runtime data.

    Order of precedence:
    1. EV_USER_DATA_DIR environment variable (if set and non-empty).
    2. Windows %LOCALAPPDATA%\\EV (standard Windows user data location).
    3. Fallback to ~/.ev (or ~/AppData/Local/EV).
    """
    env_data_root = os.getenv("EV_USER_DATA_DIR")
    if env_data_root and env_data_root.strip():
        return Path(env_data_root.strip()).resolve()

    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data and local_app_data.strip():
        return (Path(local_app_data.strip()) / "EV").resolve()

    # Safe fallback when LOCALAPPDATA is absent
    home = Path.home().resolve()
    win_local = home / "AppData" / "Local"
    if win_local.exists():
        return win_local / "EV"
    return home / ".ev"


def get_data_dir() -> Path:
    """
    Return the directory for writable databases (SQLite stores).
    Supports EV_DATA_DIR override.
    """
    env_dir = os.getenv("EV_DATA_DIR")
    if env_dir and env_dir.strip():
        return Path(env_dir.strip()).resolve()
    return get_user_data_root() / "data"


def get_memory_db_path() -> Path:
    """
    Return the path to the conversation memory SQLite database.
    Supports EV_MEMORY_DB_PATH override.
    """
    env_path = os.getenv("EV_MEMORY_DB_PATH")
    if env_path and env_path.strip():
        return Path(env_path.strip()).resolve()
    return get_data_dir() / "ev_memory.sqlite3"


def get_history_db_path() -> Path:
    """
    Return the path to the task and event history SQLite database.
    Supports EV_HISTORY_DB_PATH override.
    """
    env_path = os.getenv("EV_HISTORY_DB_PATH")
    if env_path and env_path.strip():
        return Path(env_path.strip()).resolve()
    return get_data_dir() / "ev_history.sqlite3"


def get_log_dir() -> Path:
    """
    Return the directory for application logs.
    Supports EV_LOG_DIR override.
    """
    env_dir = os.getenv("EV_LOG_DIR")
    if env_dir and env_dir.strip():
        return Path(env_dir.strip()).resolve()
    return get_user_data_root() / "logs"


def get_log_file_path() -> Path:
    """
    Return the canonical path to the primary application log file.
    Supports EV_LOG_FILE override.
    """
    env_file = os.getenv("EV_LOG_FILE")
    if env_file and env_file.strip():
        return Path(env_file.strip()).resolve()
    return get_log_dir() / "ev.log"


def get_backup_dir() -> Path:
    """
    Return the root directory for transaction and file-level rollback backups.
    Supports EV_BACKUP_DIR override.
    """
    env_dir = os.getenv("EV_BACKUP_DIR")
    if env_dir and env_dir.strip():
        return Path(env_dir.strip()).resolve()
    return get_user_data_root() / "backups"


def get_config_dir() -> Path:
    """
    Return the directory for runtime configuration files.
    Supports EV_CONFIG_DIR override.
    """
    env_dir = os.getenv("EV_CONFIG_DIR")
    if env_dir and env_dir.strip():
        return Path(env_dir.strip()).resolve()
    return get_user_data_root() / "config"


def ensure_dir(directory: Union[str, Path]) -> Path:
    """
    Ensure the given directory exists, creating parents if necessary.
    Returns the resolved Path instance.
    """
    p = Path(directory).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p
