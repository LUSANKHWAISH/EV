"""Persistent atomic store for 10-band equalizer settings."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import tempfile
from typing import Any, Dict, List, Optional

from core.paths import ensure_dir, get_config_dir
from .chain import EQ_10_BAND_FREQUENCIES

SCHEMA = 1
DEFAULT_GAINS: List[float] = [0.0] * len(EQ_10_BAND_FREQUENCIES)
DEFAULT_EQ_DATA: Dict[str, Any] = {
    "schema": SCHEMA,
    "bypass": False,
    "preamp_db": 0.0,
    "gains": DEFAULT_GAINS,
}


def validate_eq_data(data: Any) -> bool:
    """Validate schema and numerical bounds of EQ settings data."""
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        return False
    if not isinstance(data.get("bypass"), bool):
        return False
    preamp = data.get("preamp_db")
    if not isinstance(preamp, (int, float)) or not math.isfinite(preamp) or not (-18.0 <= preamp <= 18.0):
        return False
    gains = data.get("gains")
    if not isinstance(gains, list) or len(gains) != len(EQ_10_BAND_FREQUENCIES):
        return False
    for g in gains:
        if not isinstance(g, (int, float)) or not math.isfinite(g) or not (-12.0 <= g <= 12.0):
            return False
    return True


class EQStore:
    """Atomic file persistence with corrupted-file fallback for EQ settings."""

    def __init__(self, path: Optional[Path] = None, storage_path: Optional[Path] = None):
        target = path if path is not None else storage_path
        self.path = Path(target) if target is not None else get_config_dir() / "music_eq.json"

    def default_data(self) -> Dict[str, Any]:
        return json.loads(json.dumps(DEFAULT_EQ_DATA))

    def load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return self.default_data()

        try:
            content = self.path.read_text(encoding="utf-8")
            data = json.loads(content)
            if validate_eq_data(data):
                return data
        except Exception:
            pass

        # Try previous backup
        prev = self.path.with_name(self.path.name + ".previous")
        if prev.exists():
            try:
                content = prev.read_text(encoding="utf-8")
                data = json.loads(content)
                if validate_eq_data(data):
                    return data
            except Exception:
                pass

        return self.default_data()

    def save(self, data: Dict[str, Any]) -> Path:
        data = dict(data)
        data.setdefault("schema", SCHEMA)
        if not validate_eq_data(data):
            raise ValueError("Invalid EQ settings data")

        ensure_dir(self.path.parent)
        if self.path.exists():
            backup = self.path.with_name(self.path.name + ".previous")
            try:
                self.path.replace(backup)
            except Exception:
                pass

        temp_fd, temp_name = tempfile.mkstemp(
            prefix="eq_store_",
            suffix=".json",
            dir=str(self.path.parent),
        )
        try:
            with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(temp_name, self.path)
        finally:
            if os.path.exists(temp_name):
                try:
                    os.unlink(temp_name)
                except Exception:
                    pass

        return self.path

    def set_band_gain(self, band_idx: int, gain_db: float) -> None:
        data = self.load()
        if 0 <= band_idx < len(data["gains"]):
            data["gains"][band_idx] = float(gain_db)
            self.save(data)

    def set_preamp(self, preamp_db: float) -> None:
        data = self.load()
        data["preamp_db"] = float(preamp_db)
        self.save(data)

    def set_bypass(self, bypass: bool) -> None:
        data = self.load()
        data["bypass"] = bool(bypass)
        self.save(data)

    def reset_flat(self) -> None:
        data = self.default_data()
        self.save(data)

