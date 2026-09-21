"""Validated deterministic Music workspace layouts."""
from __future__ import annotations

import json
import math
import os
import tempfile
from pathlib import Path

from core.paths import ensure_dir, get_config_dir

SCHEMA = 1
PRESETS = frozenset(("ceiling-rain", "flow-trace", "segment-stack"))
DEFAULT_LAYOUT = {
    "schema": SCHEMA,
    "layout": "reference-trio",
    "columns": 12,
    "panels": [
        {"id": "rain-1", "preset": "ceiling-rain", "x": 0, "y": 0, "w": 12, "h": 2},
        {"id": "trace-1", "preset": "flow-trace", "x": 0, "y": 2, "w": 8, "h": 4},
        {"id": "stack-1", "preset": "segment-stack", "x": 8, "y": 2, "w": 4, "h": 4},
    ],
}


def _finite_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate_layout(value):
    if not isinstance(value, dict) or value.get("schema") != SCHEMA:
        return False
    if value.get("layout") != "reference-trio" or value.get("columns") != 12:
        return False
    panels = value.get("panels")
    if not isinstance(panels, list) or not 1 <= len(panels) <= 4:
        return False
    occupied = set()
    ids = set()
    for panel in panels:
        if not isinstance(panel, dict):
            return False
        panel_id = panel.get("id")
        if not isinstance(panel_id, str) or not panel_id or panel_id in ids:
            return False
        ids.add(panel_id)
        if panel.get("preset") not in PRESETS:
            return False
        if any(not isinstance(panel.get(key), int) for key in ("x", "y", "w", "h")):
            return False
        x, y, width, height = (panel[key] for key in ("x", "y", "w", "h"))
        if not (0 <= x < 12 and 0 <= y < 12 and 1 <= width <= 12 and 1 <= height <= 12):
            return False
        if x + width > 12 or y + height > 12:
            return False
        cells = {(column, row) for column in range(x, x + width) for row in range(y, y + height)}
        if occupied.intersection(cells):
            return False
        occupied.update(cells)
    return True


def default_layout():
    return json.loads(json.dumps(DEFAULT_LAYOUT))


class WorkspaceStore:
    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path is not None else get_config_dir() / "music_workspace.json"
        self.previous_path = self.path.with_suffix(self.path.suffix + ".previous")

    def load(self):
        for candidate in (self.path, self.previous_path):
            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError):
                continue
            if validate_layout(data):
                return data
        return default_layout()

    def save(self, layout):
        if not validate_layout(layout):
            raise ValueError("invalid Music workspace layout")
        ensure_dir(self.path.parent)
        payload = json.dumps(layout, separators=(",", ":"), sort_keys=True).encode("utf-8")
        fd, temp_name = tempfile.mkstemp(prefix=self.path.name + ".", dir=self.path.parent)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            if self.path.exists():
                os.replace(self.path, self.previous_path)
            os.replace(temp_name, self.path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
        return self.path
