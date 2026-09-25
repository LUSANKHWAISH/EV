"""
Focused Unit & Integration Test Suite for Human Wake-Word Collection Hardening (Task 014F-7).

Tests:
  1. VAD/high RMS activity alone does NOT mark a take as positive without user confirmation.
  2. Positive labeling requires explicit confirmation (user_confirmed=True).
  3. Rejection (user_confirmed=False) routes take safely to quarantine with target_label=-1.
  4. Unique session IDs prevent filename collisions across collection sessions.
  5. Overwrite protection prevents clobbering existing WAV files on disk.
  6. Dataset ingestion (WakeWordDatasetPipeline) strictly excludes quarantined recordings.
  7. Manifest entries maintain schema integrity and audit tracking.
  8. Acoustic quality validation correctly flags silence and clipping on test fixtures.
"""
from __future__ import annotations

import json
import shutil
import tempfile
import wave
from pathlib import Path
from typing import Generator

import numpy as np
import pytest

from tools.collect_human_wakeword import (
    CANONICAL_SAMPLE_RATE,
    TARGET_TOTAL_SAMPLES,
    VALID_CONFIRMATION_CHOICES,
    AudioQualityMetrics,
    HumanAudioCollector,
    HumanRecordingManifestItem,
    analyze_audio_quality,
    estimate_speech_snr,
    normalize_and_validate_confirmation_input,
    pad_or_trim_canonical,
    save_canonical_pcm16_wav,
)
from tools.wakeword_dataset import WakeWordDatasetPipeline


@pytest.fixture
def temp_dataset_env() -> Generator[Path, None, None]:
    """Provide isolated temporary directory structure for collector & dataset tests."""
    temp_dir = Path(tempfile.mkdtemp(prefix="ev_test_human_collector_"))
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


def create_synthetic_pcm16_audio(
    duration_sec: float = 2.0,
    sample_rate: int = 16000,
    amplitude: float = 10000.0,
    freq: float = 440.0,
) -> np.ndarray:
    """Generate synthetic sinusoidal 16-bit PCM waveform for deterministic tests."""
    t = np.linspace(0, duration_sec, int(sample_rate * duration_sec), endpoint=False)
    sig = (amplitude * np.sin(2 * np.pi * freq * t)).astype(np.int16)
    return sig


class TestHumanCollectionHardening:
    """Test suite verifying collection pipeline hardening and dataset integrity."""

    def test_acoustic_quality_validation(self):
        """Verify quality checks correctly identify valid, silent, and clipped audio."""
        # 1. Valid test tone
        valid_audio = create_synthetic_pcm16_audio(amplitude=8000.0)
        q_valid = analyze_audio_quality(valid_audio)
        assert q_valid.is_valid is True
        assert q_valid.is_silent is False
        assert q_valid.rms > 100.0
        assert q_valid.clipping_percent == 0.0

        # 2. Silent audio (all zeros)
        silent_audio = np.zeros(32000, dtype=np.int16)
        q_silent = analyze_audio_quality(silent_audio, min_rms=30.0)
        assert q_silent.is_valid is False
        assert q_silent.is_silent is True
        assert "too low" in (q_silent.rejection_reason or "")

        # 3. Heavily clipped audio
        clipped_audio = np.full(32000, 32767, dtype=np.int16)
        q_clipped = analyze_audio_quality(clipped_audio, max_clipping_percent=1.0)
        assert q_clipped.is_valid is False
        assert q_clipped.clipping_percent > 90.0
        assert "clipping" in (q_clipped.rejection_reason or "").lower()

    def test_vad_activity_alone_does_not_label_positive_without_confirmation(self, temp_dataset_env: Path):
        """
        Bug Class Test: Merely having high RMS / speech energy must NOT result in a positive
        take if user confirmation is False.
        """
        collector = HumanAudioCollector(
            speaker_id="test_speaker",
            session_id="session_test_001",
            output_base_dir=temp_dataset_env,
        )

        # High energy conversational speech simulation
        speech_audio = create_synthetic_pcm16_audio(amplitude=12000.0)
        
        # Take recorded with high RMS but user rejected confirmation
        success, item = collector.record_and_store_prompt(
            category="POSITIVE",
            phrase="Hey EV",
            condition="normal",
            target="pos",
            index=0,
            user_confirmed=False,  # User rejected
            quarantine_reason="User spoke conversational words instead of Hey EV",
            raw_audio_override=speech_audio,
        )

        assert success is True
        assert item is not None
        assert item.target_label == -1  # Quarantined, NOT positive (1)
        assert item.category == "QUARANTINE"
        assert item.confirmed_by_user is False
        assert item.status == "QUARANTINED_USER_REJECTED"

        # Verify physical file location: MUST be in quarantine, NOT positive
        assert not (collector.pos_dir / item.filename).exists()
        assert (collector.quarantine_dir / item.filename).exists()

    def test_positive_requires_explicit_confirmation(self, temp_dataset_env: Path):
        """Verify that when explicitly confirmed (user_confirmed=True), take is stored as positive."""
        collector = HumanAudioCollector(
            speaker_id="test_speaker",
            session_id="session_test_002",
            output_base_dir=temp_dataset_env,
        )

        speech_audio = create_synthetic_pcm16_audio(amplitude=8000.0)
        success, item = collector.record_and_store_prompt(
            category="POSITIVE",
            phrase="Hey EV",
            condition="normal",
            target="pos",
            index=0,
            user_confirmed=True,  # User confirmed
            raw_audio_override=speech_audio,
        )

        assert success is True
        assert item is not None
        assert item.target_label == 1
        assert item.category == "POSITIVE"
        assert item.confirmed_by_user is True
        assert item.status == "ACCEPTED"
        assert (collector.pos_dir / item.filename).exists()

    def test_session_id_prevents_filename_collisions(self, temp_dataset_env: Path):
        """
        Bug Class Test: Two distinct collection sessions with the same speaker and prompt index
        must NOT overwrite each other.
        """
        # Session 1
        col_1 = HumanAudioCollector(speaker_id="speaker_1", session_id="session_alpha", output_base_dir=temp_dataset_env)
        audio_1 = create_synthetic_pcm16_audio(amplitude=6000.0, freq=300.0)
        succ_1, item_1 = col_1.record_and_store_prompt("POSITIVE", "Hey EV", "cond", "pos", index=0, user_confirmed=True, raw_audio_override=audio_1)
        assert succ_1 and item_1 is not None

        # Session 2 (same speaker, same prompt index 0, different session)
        col_2 = HumanAudioCollector(speaker_id="speaker_1", session_id="session_beta", output_base_dir=temp_dataset_env)
        audio_2 = create_synthetic_pcm16_audio(amplitude=9000.0, freq=600.0)
        succ_2, item_2 = col_2.record_and_store_prompt("POSITIVE", "Hey EV", "cond", "pos", index=0, user_confirmed=True, raw_audio_override=audio_2)
        assert succ_2 and item_2 is not None

        # Both files must coexist on disk with distinct filenames
        assert item_1.filename != item_2.filename
        assert (col_1.pos_dir / item_1.filename).exists()
        assert (col_2.pos_dir / item_2.filename).exists()
        assert "session_alpha" in item_1.filename
        assert "session_beta" in item_2.filename

    def test_overwrite_protection_guards_existing_files(self, temp_dataset_env: Path):
        """Verify save_canonical_pcm16_wav with allow_overwrite=False prevents file clobbering."""
        out_path = temp_dataset_env / "test_file.wav"
        audio_a = create_synthetic_pcm16_audio(amplitude=5000.0)
        audio_b = create_synthetic_pcm16_audio(amplitude=15000.0)

        # Save initial file
        final_a = save_canonical_pcm16_wav(out_path, audio_a, allow_overwrite=False)
        assert final_a == out_path
        assert final_a.exists()

        # Attempt to save to same path without overwrite permission
        final_b = save_canonical_pcm16_wav(out_path, audio_b, allow_overwrite=False)
        assert final_b != out_path
        assert final_b.exists()
        assert final_a.exists()  # Original file remains preserved

    def test_dataset_ingestion_ignores_quarantine_and_respects_manifest(self, temp_dataset_env: Path):
        """
        Integration Test: Verify WakeWordDatasetPipeline ignores quarantine files and
        respects manifest categories.
        """
        human_dir = temp_dataset_env / "human"
        collector = HumanAudioCollector(
            speaker_id="user_speaker_1",
            session_id="session_test_pipeline",
            output_base_dir=human_dir,
        )

        audio = create_synthetic_pcm16_audio(amplitude=8000.0)

        # 1. Add 1 valid confirmed positive take
        collector.record_and_store_prompt("POSITIVE", "Hey EV", "cond1", "pos", index=0, user_confirmed=True, raw_audio_override=audio)

        # 2. Add 1 valid confirmed negative take
        collector.record_and_store_prompt("HARD_NEGATIVE", "Hey Everyone", "cond2", "neg", index=1, user_confirmed=True, raw_audio_override=audio)

        # 3. Add 1 quarantined take (rejected by user)
        collector.record_and_store_prompt("POSITIVE", "Hey EV", "cond3", "pos", index=2, user_confirmed=False, raw_audio_override=audio)

        # Run pipeline ingestion
        pipeline = WakeWordDatasetPipeline(data_dir=str(temp_dataset_env))
        meta, clips, labels = pipeline.scan_and_ingest_human_speech()

        assert len(meta) == 2  # Exactly 1 positive and 1 negative (quarantined excluded!)
        assert labels.count(1) == 1
        assert labels.count(0) == 1

        # Check sample IDs
        sample_ids = [m.sample_id for m in meta]
        assert any("pos" in s for s in sample_ids)
        assert any("neg" in s for s in sample_ids)
        assert not any("quarantine" in s.lower() for s in sample_ids)

    def test_confirmation_input_validation(self):
        """
        Task 014F-8C Requirement: Test strict confirmation gate input validation.
        Only exact choices [y, n, r, s, q] are valid; arbitrary strings (e.g. 't') MUST be rejected.
        """
        # Valid inputs with whitespace and casing variants
        assert normalize_and_validate_confirmation_input("y") == "y"
        assert normalize_and_validate_confirmation_input("Y") == "y"
        assert normalize_and_validate_confirmation_input("  y  ") == "y"
        assert normalize_and_validate_confirmation_input("n") == "n"
        assert normalize_and_validate_confirmation_input("N\n") == "n"
        assert normalize_and_validate_confirmation_input("r") == "r"
        assert normalize_and_validate_confirmation_input("  R  ") == "r"
        assert normalize_and_validate_confirmation_input("s") == "s"
        assert normalize_and_validate_confirmation_input("S") == "s"
        assert normalize_and_validate_confirmation_input("q") == "q"
        assert normalize_and_validate_confirmation_input("Q\t") == "q"

        # Invalid inputs must return None (rejected)
        assert normalize_and_validate_confirmation_input("t") is None
        assert normalize_and_validate_confirmation_input("yes") is None
        assert normalize_and_validate_confirmation_input("no") is None
        assert normalize_and_validate_confirmation_input("quit") is None
        assert normalize_and_validate_confirmation_input("1") is None
        assert normalize_and_validate_confirmation_input("") is None
        assert normalize_and_validate_confirmation_input("   ") is None
        assert normalize_and_validate_confirmation_input(None) is None
        assert normalize_and_validate_confirmation_input("invalid_choice") is None

    def test_estimate_speech_snr_synthetic(self):
        """
        Task 014F-8C Requirement: Test frame-based SNR calculation with known synthetic signals.
        Verifies divide-by-zero prevention, zero-noise handling, and physical bounds [0, 80] dB.
        """
        # 1. Pure digital silence (all zeros) -> None (undefined)
        zeros = np.zeros(32000, dtype=np.int16)
        assert estimate_speech_snr(zeros) is None

        # 2. Empty buffer -> None
        assert estimate_speech_snr(np.zeros(0, dtype=np.int16)) is None

        # 3. Flat uniform noise (equal signal & noise floor across frames) -> ~0.0 dB
        np.random.seed(42)
        flat_noise = np.random.normal(0, 100, 32000).astype(np.int16)
        snr_flat = estimate_speech_snr(flat_noise)
        assert snr_flat is not None
        assert 0.0 <= snr_flat <= 3.0

        # 4. Synthetic speech burst (1.0s sine wave amplitude=5000 in background noise std=50)
        # Expected ratio: Speech RMS = 5000 / sqrt(2) = 3535.5; Noise RMS = 50 -> Expected SNR = 20*log10(70.7) = 37.0 dB
        t = np.linspace(0, 1.0, 16000, endpoint=False)
        sine_burst = (5000 * np.sin(2 * np.pi * 440 * t)).astype(np.float64)
        noise_full = np.random.normal(0, 50, 32000).astype(np.float64)
        synthetic_signal = noise_full.copy()
        synthetic_signal[8000:24000] += sine_burst
        synthetic_pcm16 = np.clip(synthetic_signal, -32768, 32767).astype(np.int16)

        snr_burst = estimate_speech_snr(synthetic_pcm16)
        assert snr_burst is not None
        assert 35.0 <= snr_burst <= 40.0  # Closely matches 37.0 dB theoretical

        # 5. Quality metrics integration
        q = analyze_audio_quality(synthetic_pcm16)
        assert q.is_valid is True
        assert q.snr_db is not None
        assert 35.0 <= q.snr_db <= 40.0

    def test_manifest_schema_and_path_resolution(self, temp_dataset_env: Path):
        """
        Verify manifest records serialize, deserialize, and resolve relative paths correctly.
        """
        collector = HumanAudioCollector(
            speaker_id="speaker_audit",
            session_id="session_audit_001",
            output_base_dir=temp_dataset_env,
        )
        audio = create_synthetic_pcm16_audio(amplitude=6000.0)
        success, item = collector.record_and_store_prompt(
            category="POSITIVE",
            phrase="Hey EV",
            condition="desk baseline",
            target="pos",
            index=0,
            user_confirmed=True,
            raw_audio_override=audio,
        )
        assert success and item is not None

        # Verify relative path resolves relative to dataset root
        resolved_path = temp_dataset_env / item.relative_path
        assert resolved_path.exists()
        assert resolved_path.name == item.filename

        # Load back from manifest
        manifest_items = collector.load_manifest()
        assert len(manifest_items) == 1
        loaded = manifest_items[0]
        assert loaded.filename == item.filename
        assert loaded.relative_path == item.relative_path
        assert loaded.target_label == 1
        assert loaded.confirmed_by_user is True
        assert loaded.status == "ACCEPTED"
        assert loaded.quality.snr_db is not None

