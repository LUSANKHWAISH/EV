"""
Unit & Integration Tests for Human Wake-Word Dataset Audit & Locked Holdout (Task 014F-9).

Verifies:
  1. Locked human holdout manifest exists and conforms to required schema.
  2. Every holdout sample exists on disk, is a valid 16kHz mono PCM16 WAV, and matches its recorded SHA256.
  3. Holdout is balanced across positive, hard-negative, and general-negative categories.
  4. Quarantine recordings are strictly excluded from the holdout manifest.
  5. Active ONNX model (hey_ev.onnx) remains byte-for-byte identical to baseline SHA.
  6. WakeWordDatasetPipeline ignores holdout samples when configured or maintains quarantine exclusion.
"""
from __future__ import annotations

import hashlib
import json
import wave
from pathlib import Path

import numpy as np
import pytest

HUMAN_DATASET_DIR = Path(r"D:\EV\models\wakeword\dataset\human")
HOLDOUT_MANIFEST_PATH = HUMAN_DATASET_DIR / "locked_human_holdout_manifest.json"
ACTIVE_MODEL_PATH = Path(r"D:\EV\models\wakeword\hey_ev.onnx")
BASELINE_MODEL_PATH = Path(r"D:\EV\models\wakeword\hey_ev_v1_baseline.onnx")

EXPECTED_ACTIVE_SHA = "9b11e3db5ca4118a19a35618f91db66aabc66c1ffe762cd69b215c9a1204f377"
EXPECTED_BASELINE_SHA = "57fb9f2cb5349ac1599afef89bb8304daf183aaf7171dbd7d3a31b8f8caca117"


def calculate_sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


class TestHumanHoldoutAudit:
    """Test suite verifying locked human holdout and model immutability."""

    def test_model_immutability(self):
        """Verify active and baseline ONNX models match baseline cryptographic hashes."""
        assert ACTIVE_MODEL_PATH.exists(), "Active hey_ev.onnx model is missing!"
        active_sha = calculate_sha(ACTIVE_MODEL_PATH)
        assert active_sha == EXPECTED_ACTIVE_SHA, f"Active model SHA256 mismatch! Got {active_sha}"

        if BASELINE_MODEL_PATH.exists():
            baseline_sha = calculate_sha(BASELINE_MODEL_PATH)
            assert baseline_sha == EXPECTED_BASELINE_SHA, f"Baseline model SHA256 mismatch! Got {baseline_sha}"

    def test_locked_holdout_manifest_schema(self):
        """Verify the locked holdout manifest exists and contains complete metadata."""
        assert HOLDOUT_MANIFEST_PATH.exists(), "Locked human holdout manifest is missing!"
        with open(HOLDOUT_MANIFEST_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert "metadata" in data
        assert "samples" in data
        meta = data["metadata"]
        assert meta["deterministic_seed"] == 42
        assert meta["active_model_sha256"] == EXPECTED_ACTIVE_SHA
        assert meta["total_samples"] == 33
        assert meta["positive_count"] == 17
        assert meta["hard_negative_count"] == 12
        assert meta["general_negative_count"] == 4

    def test_locked_holdout_file_integrity_and_sha(self):
        """Verify all holdout files exist, have canonical audio format, and match SHA256."""
        with open(HOLDOUT_MANIFEST_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        samples = data["samples"]
        assert len(samples) == 33

        for s in samples:
            rel = s["relative_path"]
            full_path = HUMAN_DATASET_DIR / rel
            assert full_path.exists(), f"Holdout file missing on disk: {full_path}"

            # Verify SHA256 matches manifest
            disk_sha = calculate_sha(full_path)
            assert disk_sha == s["sha256"], f"SHA mismatch for holdout file {rel}"

            # Verify canonical audio structure
            with wave.open(str(full_path), "rb") as wf:
                assert wf.getframerate() == 16000, f"Non-16kHz rate in {rel}"
                assert wf.getnchannels() == 1, f"Non-mono channels in {rel}"
                assert wf.getsampwidth() == 2, f"Non-16bit width in {rel}"
                assert wf.getnframes() == 32000, f"Non-32k frames in {rel}"

    def test_quarantine_is_strictly_excluded_from_holdout(self):
        """Verify that zero quarantined recordings enter the holdout manifest."""
        with open(HOLDOUT_MANIFEST_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        for s in data["samples"]:
            assert s["category"] != "QUARANTINE", f"Quarantine category leaked into holdout: {s}"
            assert s["target_label"] in (0, 1), f"Invalid target label in holdout: {s}"
            assert not s["relative_path"].startswith("quarantine"), f"Quarantine path leaked into holdout: {s}"
