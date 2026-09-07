"""
Deterministic Unit Tests for E.V. Canonical Path Resolution (Phase 018-J.1).

Tests:
1. Source mode path resolution.
2. Simulated frozen/packaged mode resolution (sys.frozen, sys._MEIPASS).
3. Runtime data root resolution (%LOCALAPPDATA%\\EV).
4. Environment variable overrides for all resource and data paths.
5. Directory creation safety (ensure_dir).
6. Total absence of hardcoded 'D:\\EV' paths in production modules.
7. Test isolation guarantee: tests never write to real user %LOCALAPPDATA%\\EV.
"""
import os
from pathlib import Path
import sys
import tempfile
import pytest

import core.paths as paths


class TestPathResolutionSourceMode:
    """Verify default resolution when running from source repository."""

    def test_resource_root_source_mode(self, monkeypatch):
        monkeypatch.delenv("EV_RESOURCE_ROOT", raising=False)
        monkeypatch.setattr(sys, "frozen", False, raising=False)
        if hasattr(sys, "_MEIPASS"):
            monkeypatch.delattr(sys, "_MEIPASS")

        root = paths.get_resource_root()
        assert root.is_dir()
        # Source tree should contain core and gui directories
        assert (root / "core").is_dir()
        assert (root / "gui").is_dir()

    def test_qml_root_source_mode(self, monkeypatch):
        monkeypatch.delenv("EV_RESOURCE_ROOT", raising=False)
        monkeypatch.setattr(sys, "frozen", False, raising=False)

        qml_root = paths.get_qml_root()
        assert qml_root.is_dir()
        assert (qml_root / "Main.qml").is_file()

    def test_models_dir_source_mode(self, monkeypatch):
        monkeypatch.delenv("EV_MODELS_DIR", raising=False)
        monkeypatch.delenv("EV_RESOURCE_ROOT", raising=False)
        monkeypatch.setattr(sys, "frozen", False, raising=False)

        models_dir = paths.get_models_dir()
        assert models_dir == paths.get_resource_root() / "models"

    def test_wakeword_model_dir_source_mode(self, monkeypatch):
        monkeypatch.delenv("EV_WAKEWORD_MODEL_DIR", raising=False)
        monkeypatch.delenv("EV_MODELS_DIR", raising=False)

        ww_dir = paths.get_wakeword_model_dir()
        assert ww_dir == paths.get_models_dir() / "wakeword"

    def test_asr_model_dir_source_mode(self, monkeypatch):
        monkeypatch.delenv("EV_ASR_MODEL_DIR", raising=False)
        monkeypatch.delenv("EV_MODELS_DIR", raising=False)

        asr_dir = paths.get_asr_model_dir()
        assert asr_dir == paths.get_models_dir() / "asr"


class TestPathResolutionFrozenMode:
    """Verify resource resolution when running in simulated PyInstaller bundle."""

    def test_resource_root_frozen_meipass(self, monkeypatch, tmp_path):
        fake_bundle = tmp_path / "pyinstaller_bundle"
        fake_bundle.mkdir()

        monkeypatch.delenv("EV_RESOURCE_ROOT", raising=False)
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "_MEIPASS", str(fake_bundle), raising=False)

        assert paths.is_frozen() is True
        assert paths.get_resource_root() == fake_bundle.resolve()
        assert paths.get_qml_root() == (fake_bundle / "gui" / "qml").resolve()
        assert paths.get_models_dir() == (fake_bundle / "models").resolve()
        assert paths.get_wakeword_model_dir() == (fake_bundle / "models" / "wakeword").resolve()
        assert paths.get_asr_model_dir() == (fake_bundle / "models" / "asr").resolve()

    def test_resource_root_frozen_standalone(self, monkeypatch, tmp_path):
        fake_bin_dir = tmp_path / "installed_app"
        fake_bin_dir.mkdir()
        fake_exe = fake_bin_dir / "EV.exe"
        fake_exe.touch()

        monkeypatch.delenv("EV_RESOURCE_ROOT", raising=False)
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        if hasattr(sys, "_MEIPASS"):
            monkeypatch.delattr(sys, "_MEIPASS")
        monkeypatch.setattr(sys, "executable", str(fake_exe), raising=False)

        assert paths.is_frozen() is True
        assert paths.get_resource_root() == fake_bin_dir.resolve()


class TestUserDataPathResolution:
    """Verify runtime user data path resolution and environment overrides."""

    def test_user_data_root_default_windows(self, monkeypatch, tmp_path):
        fake_local_appdata = tmp_path / "AppData" / "Local"
        fake_local_appdata.mkdir(parents=True)

        monkeypatch.delenv("EV_USER_DATA_DIR", raising=False)
        monkeypatch.setenv("LOCALAPPDATA", str(fake_local_appdata))

        user_data = paths.get_user_data_root()
        assert user_data == (fake_local_appdata / "EV").resolve()
        assert paths.get_data_dir() == user_data / "data"
        assert paths.get_memory_db_path() == user_data / "data" / "ev_memory.sqlite3"
        assert paths.get_history_db_path() == user_data / "data" / "ev_history.sqlite3"
        assert paths.get_log_dir() == user_data / "logs"
        assert paths.get_log_file_path() == user_data / "logs" / "ev.log"
        assert paths.get_backup_dir() == user_data / "backups"
        assert paths.get_config_dir() == user_data / "config"

    def test_user_data_root_override(self, monkeypatch, tmp_path):
        custom_root = tmp_path / "custom_ev_data"
        monkeypatch.setenv("EV_USER_DATA_DIR", str(custom_root))

        assert paths.get_user_data_root() == custom_root.resolve()
        assert paths.get_data_dir() == custom_root.resolve() / "data"
        assert paths.get_log_dir() == custom_root.resolve() / "logs"
        assert paths.get_backup_dir() == custom_root.resolve() / "backups"

    def test_granular_directory_overrides(self, monkeypatch, tmp_path):
        d_dir = tmp_path / "my_data"
        l_dir = tmp_path / "my_logs"
        b_dir = tmp_path / "my_backups"
        c_dir = tmp_path / "my_config"
        m_db = tmp_path / "custom_memory.sqlite3"
        h_db = tmp_path / "custom_history.sqlite3"
        l_file = tmp_path / "custom.log"

        monkeypatch.setenv("EV_DATA_DIR", str(d_dir))
        monkeypatch.setenv("EV_LOG_DIR", str(l_dir))
        monkeypatch.setenv("EV_BACKUP_DIR", str(b_dir))
        monkeypatch.setenv("EV_CONFIG_DIR", str(c_dir))
        monkeypatch.setenv("EV_MEMORY_DB_PATH", str(m_db))
        monkeypatch.setenv("EV_HISTORY_DB_PATH", str(h_db))
        monkeypatch.setenv("EV_LOG_FILE", str(l_file))

        assert paths.get_data_dir() == d_dir.resolve()
        assert paths.get_log_dir() == l_dir.resolve()
        assert paths.get_backup_dir() == b_dir.resolve()
        assert paths.get_config_dir() == c_dir.resolve()
        assert paths.get_memory_db_path() == m_db.resolve()
        assert paths.get_history_db_path() == h_db.resolve()
        assert paths.get_log_file_path() == l_file.resolve()

    def test_ensure_dir(self, tmp_path):
        target = tmp_path / "sub1" / "sub2" / "target"
        assert not target.exists()
        created = paths.ensure_dir(target)
        assert created == target.resolve()
        assert target.is_dir()


class TestNoHardcodedProductionPaths:
    """Verify that no production modules contain hardcoded D:\\EV paths."""

    def test_production_modules_have_no_hardcoded_dev_drive(self):
        repo_root = paths.get_resource_root()
        production_dirs = ["core", "gui", "config", "providers"]
        hardcoded_matches = []

        for pdir in production_dirs:
            dir_path = repo_root / pdir
            for pyfile in dir_path.rglob("*.py"):
                if "__pycache__" in pyfile.parts:
                    continue
                content = pyfile.read_text(encoding="utf-8", errors="ignore")
                for line_idx, line in enumerate(content.splitlines(), 1):
                    # Check for D:\EV or D:/EV literal references
                    if "D:\\EV" in line or "D:/EV" in line:
                        hardcoded_matches.append(
                            f"{pyfile.relative_to(repo_root)}:{line_idx} -> {line.strip()}"
                        )

        assert not hardcoded_matches, (
            f"Found hardcoded D:\\EV in production code:\n" + "\n".join(hardcoded_matches)
        )
