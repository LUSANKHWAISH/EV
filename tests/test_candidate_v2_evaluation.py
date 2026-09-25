"""
Test Candidate V2 Evaluation, Leakage Audit, and Immutability Guard (Task 014F-11).

Verifies:
  1. Active model hey_ev.onnx immutability (SHA256).
  2. Candidate V1 hey_ev_human_v2.onnx immutability (SHA256).
  3. Candidate V2 hey_ev_human_v3.onnx existence and SHA256 integrity.
  4. Locked holdout manifest SHA256 integrity.
  5. Programmatic holdout leakage audit (0 overlap).
  6. Quarantine exclusion (0 quarantine samples).
  7. OpenWakeWordProvider runtime compatibility for Candidate V2.
  8. Model non-promotion verification (hey_ev.onnx is untouched).
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
CANDIDATE_V1_PATH = Path(r"D:\EV\models\wakeword\candidates\hey_ev_human_v2.onnx")
CANDIDATE_V2_PATH = Path(r"D:\EV\models\wakeword\candidates\hey_ev_human_v3.onnx")
HOLDOUT_MANIFEST_PATH = Path(r"D:\EV\models\wakeword\dataset\human\locked_human_holdout_manifest.json")

EXPECTED_ACTIVE_SHA = "9b11e3db5ca4118a19a35618f91db66aabc66c1ffe762cd69b215c9a1204f377"
EXPECTED_CANDIDATE_V1_SHA = "9286c84a97b31a0934947dd56500ba5295937cc65d0be1126aff54039a2cea9d"
EXPECTED_CANDIDATE_V2_SHA = "1862f8f3e313146bf6e717ee3c97a34f2c7fff9409605e6a54a743da1b5443fb"
EXPECTED_HOLDOUT_SHA = "03a59c13fa35fa932065e364e0b4bde2c3d174efc8f774f9f03ba96dfefe18ba"


class TestCandidateV2EvaluationAndSafety:
    """Test suite verifying Candidate V2 evaluation, immutability, and runtime isolation."""

    def test_active_model_immutability(self):
        """Verify active baseline model has not been modified."""
        assert ACTIVE_MODEL_PATH.exists(), f"Active model missing at {ACTIVE_MODEL_PATH}"
        current_sha = compute_file_sha256(ACTIVE_MODEL_PATH)
        assert current_sha == EXPECTED_ACTIVE_SHA, (
            f"CRITICAL IMMUTABILITY VIOLATION: Active model SHA256 altered!\n"
            f"Expected: {EXPECTED_ACTIVE_SHA}\n"
            f"Actual:   {current_sha}"
        )

    def test_candidate_v1_immutability(self):
        """Verify Candidate V1 has not been modified or overwritten."""
        assert CANDIDATE_V1_PATH.exists(), f"Candidate V1 missing at {CANDIDATE_V1_PATH}"
        cand1_sha = compute_file_sha256(CANDIDATE_V1_PATH)
        assert cand1_sha == EXPECTED_CANDIDATE_V1_SHA, f"Candidate V1 SHA mismatch: {cand1_sha}"

    def test_candidate_v2_existence_and_hash(self):
        """Verify Candidate V2 exists and matches calculated hash."""
        assert CANDIDATE_V2_PATH.exists(), f"Candidate V2 missing at {CANDIDATE_V2_PATH}"
        cand2_sha = compute_file_sha256(CANDIDATE_V2_PATH)
        assert cand2_sha == EXPECTED_CANDIDATE_V2_SHA, f"Candidate V2 SHA mismatch: {cand2_sha}"

    def test_models_are_distinct(self):
        """Verify all three models have distinct cryptographic hashes and paths."""
        act_sha = compute_file_sha256(ACTIVE_MODEL_PATH)
        v1_sha = compute_file_sha256(CANDIDATE_V1_PATH)
        v2_sha = compute_file_sha256(CANDIDATE_V2_PATH)

        assert len({act_sha, v1_sha, v2_sha}) == 3, "Model SHA hashes must all be distinct!"
        assert ACTIVE_MODEL_PATH.resolve() != CANDIDATE_V1_PATH.resolve()
        assert ACTIVE_MODEL_PATH.resolve() != CANDIDATE_V2_PATH.resolve()
        assert CANDIDATE_V1_PATH.resolve() != CANDIDATE_V2_PATH.resolve()

    def test_holdout_manifest_integrity(self):
        """Verify holdout manifest has not been modified."""
        assert HOLDOUT_MANIFEST_PATH.exists(), f"Holdout manifest missing at {HOLDOUT_MANIFEST_PATH}"
        manifest_sha = compute_file_sha256(HOLDOUT_MANIFEST_PATH)
        assert manifest_sha == EXPECTED_HOLDOUT_SHA, f"Holdout manifest SHA changed: {manifest_sha}"

    def test_leakage_and_quarantine_exclusion(self):
        """Verify 0 holdout leakage and 0 quarantine samples in training data."""
        pipeline = WakeWordDatasetPipeline(random_seed=42)
        meta, clips, labels = pipeline.scan_and_ingest_human_speech(augment_human=False)

        audit = audit_dataset_leakage(meta, HOLDOUT_MANIFEST_PATH)
        assert audit["leakage_detected"] is False
        assert audit["overlap_count"] == 0
        assert not any("quarantine" in m.source_file.lower() for m in meta)

    def test_candidate_v2_runtime_provider_compatibility(self):
        """Verify Candidate V2 loads and executes in OpenWakeWordProvider without errors."""
        pytest.importorskip("openwakeword")
        from core.voice_capture import AudioFrame

        provider = OpenWakeWordProvider(
            wakeword_models=[str(CANDIDATE_V2_PATH)],
            target_phrase="hey_ev_human_v3",
            threshold=0.50,
            inference_framework="onnx",
        )
        assert provider.is_available is True
        assert "hey_ev_human_v3" in provider.loaded_models

        # Stream 10 frames of 30ms PCM16 silence
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
        provider.close()
