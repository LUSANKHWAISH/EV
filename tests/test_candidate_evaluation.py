"""
Test Candidate Evaluation and Immutability Guard (Task 014F-10).

Verifies:
  1. Active model hey_ev.onnx immutability (SHA256).
  2. Candidate model hey_ev_human_v2.onnx existence and SHA256 integrity.
  3. Programmatic holdout leakage audit: Overlap between training set and holdout set == 0.
  4. Quarantine exclusion: 0 quarantine files in training or holdout sets.
  5. OpenWakeWordProvider runtime compatibility:
     - Model loads successfully into OpenWakeWordProvider.
     - Streaming PCM16 processing succeeds without errors.
     - Output bounds [0.0, 1.0].
     - Provider reset works cleanly.
  6. Candidate demonstrates human positive recall improvement on locked holdout.
  7. Active model hey_ev.onnx is NOT replaced (Candidate isolated in candidates/ dir).
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
import pytest

from core.voice_wakeword_openwakeword import OpenWakeWordProvider
from tools.wakeword_dataset import (
    WakeWordDatasetPipeline,
    audit_dataset_leakage,
    compute_file_sha256,
)

ACTIVE_MODEL_PATH = Path(r"D:\EV\models\wakeword\hey_ev.onnx")
CANDIDATE_MODEL_PATH = Path(r"D:\EV\models\wakeword\candidates\hey_ev_human_v2.onnx")
HOLDOUT_MANIFEST_PATH = Path(r"D:\EV\models\wakeword\dataset\human\locked_human_holdout_manifest.json")

EXPECTED_ACTIVE_SHA = "9b11e3db5ca4118a19a35618f91db66aabc66c1ffe762cd69b215c9a1204f377"
EXPECTED_HOLDOUT_SHA = "03a59c13fa35fa932065e364e0b4bde2c3d174efc8f774f9f03ba96dfefe18ba"
EXPECTED_CANDIDATE_SHA = "9286c84a97b31a0934947dd56500ba5295937cc65d0be1126aff54039a2cea9d"


class TestCandidateEvaluationAndSafety:
    """Test suite verifying candidate model evaluation, leakage prevention, and safety boundaries."""

    def test_active_model_immutability(self):
        """Verify active production model has not been overwritten."""
        assert ACTIVE_MODEL_PATH.exists(), f"Active model missing at {ACTIVE_MODEL_PATH}"
        current_sha = compute_file_sha256(ACTIVE_MODEL_PATH)
        assert current_sha == EXPECTED_ACTIVE_SHA, (
            f"CRITICAL IMMUTABILITY VIOLATION: Active model SHA256 altered!\n"
            f"Expected: {EXPECTED_ACTIVE_SHA}\n"
            f"Actual:   {current_sha}"
        )

    def test_candidate_model_existence_and_hash(self):
        """Verify candidate model exists at candidates/ and matches recorded hash."""
        assert CANDIDATE_MODEL_PATH.exists(), f"Candidate model missing at {CANDIDATE_MODEL_PATH}"
        cand_sha = compute_file_sha256(CANDIDATE_MODEL_PATH)
        assert cand_sha == EXPECTED_CANDIDATE_SHA, f"Candidate model SHA256 mismatch: {cand_sha}"

    def test_candidate_distinct_from_active_model(self):
        """Verify candidate model is physically distinct from active model."""
        active_sha = compute_file_sha256(ACTIVE_MODEL_PATH)
        cand_sha = compute_file_sha256(CANDIDATE_MODEL_PATH)
        assert active_sha != cand_sha, "Candidate model has the same hash as active baseline model!"
        assert CANDIDATE_MODEL_PATH.resolve() != ACTIVE_MODEL_PATH.resolve()

    def test_holdout_manifest_hash(self):
        """Verify holdout manifest integrity."""
        assert HOLDOUT_MANIFEST_PATH.exists(), f"Holdout manifest missing at {HOLDOUT_MANIFEST_PATH}"
        manifest_sha = compute_file_sha256(HOLDOUT_MANIFEST_PATH)
        assert manifest_sha == EXPECTED_HOLDOUT_SHA, f"Holdout manifest SHA256 changed: {manifest_sha}"

    def test_zero_leakage_audit(self):
        """Verify programmatic leakage audit ensures 0 holdout samples in training/val data."""
        pipeline = WakeWordDatasetPipeline(random_seed=42)
        meta, clips, labels = pipeline.scan_and_ingest_human_speech(augment_human=False)

        # Audit against locked holdout manifest
        audit = audit_dataset_leakage(meta, HOLDOUT_MANIFEST_PATH)
        assert audit["leakage_detected"] is False, f"Data leakage detected! Audit: {audit}"
        assert audit["overlap_count"] == 0, f"Overlap count must be 0, got {audit['overlap_count']}"
        assert audit["holdout_samples_count"] == 33
        # Ensure zero quarantine files are ingested into dataset
        assert not any("quarantine" in m.source_file.lower() for m in meta), "Quarantine files leaked into dataset!"

    def test_candidate_runtime_provider_compatibility(self):
        """Verify candidate model loads and executes in OpenWakeWordProvider without errors."""
        from core.voice_capture import AudioFrame

        provider = OpenWakeWordProvider(
            wakeword_models=[str(CANDIDATE_MODEL_PATH)],
            target_phrase="hey_ev_human_v2",
            threshold=0.50,
            inference_framework="onnx",
        )
        assert provider.is_available is True
        assert "hey_ev_human_v2" in provider.loaded_models

        # Stream 10 frames of canonical 30ms silence (480 samples = 960 bytes @ 16kHz mono 16-bit)
        silent_frame = AudioFrame(
            data=b"\x00" * 960,
            sample_rate=16000,
            channels=1,
            sample_width=2,
        )
        for _ in range(10):
            res = provider.process_frame(silent_frame)
            if res is not None:
                assert 0.0 <= res.confidence <= 1.0

        provider.reset()
        assert provider.processed_frames_count == 0

    def test_candidate_holdout_positive_recall_improvement(self):
        """Verify candidate achieves higher recall than active baseline on locked holdout."""
        from openwakeword.model import Model

        with open(HOLDOUT_MANIFEST_PATH, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        human_dir = HOLDOUT_MANIFEST_PATH.parent
        pos_samples = [s for s in manifest["samples"] if s["category"] == "POSITIVE"]

        cand_oww = Model(wakeword_models=[str(CANDIDATE_MODEL_PATH)], inference_framework="onnx")

        pos_scores = []
        for s in pos_samples:
            wav_p = str(human_dir / s["relative_path"])
            cand_oww.reset()
            preds = cand_oww.predict_clip(wav_p, padding=0)
            m = float(max([x[list(x.keys())[0]] for x in preds])) if preds else 0.0
            pos_scores.append(m)

        # Baseline recall at 0.50 was 8/17 (47.1%). Candidate must achieve >= 14/17 (>= 80%).
        tp_count = sum(1 for sc in pos_scores if sc >= 0.50)
        assert tp_count >= 14, f"Candidate recall too low: {tp_count}/{len(pos_samples)} at 0.50 threshold"
