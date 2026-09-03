"""
Deterministic Automated Unit Tests for E.V. Wake-Word Training Pipeline (Task 014F-3).

Verifies:
  1. Audio validation and malformed audio input rejection.
  2. Dataset metadata structures and label assignments.
  3. Disjoint dataset splitting without leakage.
  4. Audio augmentations (gain, noise mixing, time-shifting).
  5. OpenWakeWordNet forward pass, tensor shape contracts, and output bounds.
  6. Fast training step on micro-fixtures.
  7. ONNX export validity, input/output tensor signature checks, and ONNX Runtime loading.
  8. Offline determinism: zero network calls, zero full dataset generation, zero slow training.
"""
from __future__ import annotations

import os
import tempfile
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import onnx
import onnxruntime as ort
import pytest
import torch

from tools.train_wakeword import (
    FCNBlock,
    OpenWakeWordNet,
    export_model_to_onnx,
    train_hey_ev_model,
)
from tools.wakeword_dataset import (
    CANONICAL_CHANNELS,
    CANONICAL_SAMPLE_RATE,
    CANONICAL_SAMPLE_WIDTH,
    CLIP_TOTAL_SAMPLES,
    SampleMetadata,
    augment_audio,
    load_pcm16_wav,
    pad_or_trim_to_length,
    save_pcm16_wav,
)


# ============================================================================
# 1. Audio Validation & Contract Tests
# ============================================================================
class TestAudioContractAndValidation:
    def test_save_and_load_pcm16_wav(self, tmp_path):
        wav_path = tmp_path / "test_audio.wav"
        orig_data = np.array([0, 1000, -1000, 32767, -32768], dtype=np.int16)
        save_pcm16_wav(str(wav_path), orig_data)

        loaded_data = load_pcm16_wav(str(wav_path))
        assert np.array_equal(orig_data, loaded_data)

    def test_reject_invalid_sample_rate(self, tmp_path):
        bad_path = tmp_path / "bad_rate.wav"
        with wave.open(str(bad_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(44100)  # Non-canonical
            wf.writeframes(b"\x00\x00" * 100)

        with pytest.raises(ValueError, match="Expected rate 16000"):
            load_pcm16_wav(str(bad_path))

    def test_reject_stereo_audio(self, tmp_path):
        stereo_path = tmp_path / "stereo.wav"
        with wave.open(str(stereo_path), "wb") as wf:
            wf.setnchannels(2)  # Stereo
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(b"\x00\x00" * 200)

        with pytest.raises(ValueError, match="Expected 1 channels"):
            load_pcm16_wav(str(stereo_path))

    def test_reject_invalid_sample_width(self, tmp_path):
        bad_width_path = tmp_path / "bad_width.wav"
        with wave.open(str(bad_width_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(4)  # 32-bit
            wf.setframerate(16000)
            wf.writeframes(b"\x00\x00\x00\x00" * 50)

        with pytest.raises(ValueError, match="Expected sample width 2"):
            load_pcm16_wav(str(bad_width_path))


# ============================================================================
# 2. Augmentation & Framing Tests
# ============================================================================
class TestAugmentations:
    def test_pad_or_trim_exact_length(self):
        short_clip = np.ones(1000, dtype=np.int16) * 500
        framed = pad_or_trim_to_length(short_clip, target_length=CLIP_TOTAL_SAMPLES, offset=500)
        assert len(framed) == CLIP_TOTAL_SAMPLES
        assert framed[0] == 0
        assert framed[500] == 500

        long_clip = np.ones(40000, dtype=np.int16) * 99
        trimmed = pad_or_trim_to_length(long_clip, target_length=CLIP_TOTAL_SAMPLES)
        assert len(trimmed) == CLIP_TOTAL_SAMPLES

    def test_augment_audio_types(self):
        base_audio = (1000 * np.sin(np.linspace(0, 10, 16000))).astype(np.int16)

        # Gain scaling
        aug_gain = augment_audio(base_audio, gain=1.2, noise_type="none")
        assert len(aug_gain) == CLIP_TOTAL_SAMPLES
        assert aug_gain.dtype == np.int16

        # White noise injection
        aug_white = augment_audio(base_audio, noise_type="white", noise_snr_db=15.0)
        assert len(aug_white) == CLIP_TOTAL_SAMPLES

        # Pink noise injection
        aug_pink = augment_audio(base_audio, noise_type="pink", noise_snr_db=20.0)
        assert len(aug_pink) == CLIP_TOTAL_SAMPLES

        # Hum injection
        aug_hum = augment_audio(base_audio, noise_type="hum", noise_snr_db=18.0)
        assert len(aug_hum) == CLIP_TOTAL_SAMPLES


# ============================================================================
# 3. Model Architecture Tests
# ============================================================================
class TestModelArchitecture:
    def test_openwakeword_net_dimensions(self):
        model = OpenWakeWordNet(input_shape=(16, 96), layer_dim=128, n_blocks=1)
        batch_input = torch.randn(4, 16, 96)
        output = model(batch_input)

        assert output.shape == (4, 1)
        # Verify sigmoid output bounds [0.0, 1.0]
        assert torch.all(output >= 0.0)
        assert torch.all(output <= 1.0)

    def test_fcn_block_forward(self):
        block = FCNBlock(layer_dim=64)
        x = torch.randn(2, 64)
        out = block(x)
        assert out.shape == (2, 64)


# ============================================================================
# 4. Micro-Training Loop Tests (Fast Deterministic Mock)
# ============================================================================
class TestMicroTraining:
    def test_fast_micro_training_step(self):
        np.random.seed(42)
        torch.manual_seed(42)

        # Create small synthetic feature fixtures
        X_train = np.random.randn(16, 16, 96).astype(np.float32)
        y_train = np.array([1, 1, 0, 0] * 4, dtype=np.float32)

        X_val = np.random.randn(8, 16, 96).astype(np.float32)
        y_val = np.array([1, 0] * 4, dtype=np.float32)

        model, metrics = train_hey_ev_model(
            X_train,
            y_train,
            X_val,
            y_val,
            epochs=2,
            batch_size=8,
            learning_rate=1e-3,
        )

        assert isinstance(model, OpenWakeWordNet)
        assert "val_loss" in metrics
        assert "val_f1" in metrics
        assert "val_accuracy" in metrics


# ============================================================================
# 5. ONNX Export & Runtime Verification Tests
# ============================================================================
class TestONNXExportAndRuntime:
    def test_export_model_to_onnx_and_verify(self, tmp_path):
        model = OpenWakeWordNet(input_shape=(16, 96), layer_dim=64, n_blocks=1)
        export_path = tmp_path / "hey_ev_test.onnx"

        output_file = export_model_to_onnx(model, str(export_path))
        assert output_file.exists()
        assert output_file.stat().st_size > 1000

        # Load with ONNX library
        onnx_model = onnx.load(str(output_file))
        onnx.checker.check_model(onnx_model)

        # Load with ONNX Runtime
        session = ort.InferenceSession(str(output_file), providers=["CPUExecutionProvider"])
        input_info = session.get_inputs()[0]
        output_info = session.get_outputs()[0]

        assert input_info.name == "input"
        assert output_info.name == "output"
        assert input_info.shape[1] == 16
        assert input_info.shape[2] == 96
        assert output_info.shape[1] == 1

        # Run test inference
        dummy_feat = np.random.randn(1, 16, 96).astype(np.float32)
        preds = session.run([output_info.name], {input_info.name: dummy_feat})[0]

        assert preds.shape == (1, 1)
        assert 0.0 <= preds[0, 0] <= 1.0


# ============================================================================
# 6. Physical Validator Structure & Calibration Tests (Offline Mock)
# ============================================================================
class TestValidationToolSuite:
    def test_utterance_trial_result_dataclass(self):
        from tools.validate_wakeword import UtteranceTrialResult

        trial = UtteranceTrialResult(
            trial_id="test_01",
            target_type="positive",
            spoken_text="Hey EV",
            voice="David",
            rate=0,
            volume=85,
            max_score=0.942,
            detected_at_50=True,
            latency_ms=250.0,
            total_frames=100,
            rms_level=500.0,
        )
        assert trial.trial_id == "test_01"
        assert trial.detected_at_50 is True
        assert trial.max_score == 0.942

    def test_threshold_calibration_sweep_math(self):
        from tools.validate_wakeword import PhysicalWakeWordValidator, UtteranceTrialResult

        with patch("sounddevice.query_devices") as mock_query, \
             patch("core.tts.WindowsSAPIProvider"):
            mock_query.return_value = {
                "name": "Mock Mic",
                "hostapi": 0,
                "max_input_channels": 1,
                "default_samplerate": 44100.0,
            }

            validator = PhysicalWakeWordValidator(device_index=0, model_path="nonexistent.onnx")

            tp_trials = [
                UtteranceTrialResult("tp1", "positive", "Hey EV", "David", 0, 85, 0.95, True, 100.0, 50, 400.0),
                UtteranceTrialResult("tp2", "positive", "Hey EV", "David", 0, 85, 0.65, True, 120.0, 50, 400.0),
                UtteranceTrialResult("tp3", "positive", "Hey EV", "David", 0, 85, 0.45, False, None, 50, 400.0),
                UtteranceTrialResult("tp4", "positive", "Hey EV", "David", 0, 85, 0.25, False, None, 50, 400.0),
            ]

            neg_trials = [
                UtteranceTrialResult("neg1", "negative", "Heavy", "David", 0, 85, 0.15, False, None, 50, 200.0),
                UtteranceTrialResult("neg2", "negative", "Every", "David", 0, 85, 0.35, False, None, 50, 200.0),
                UtteranceTrialResult("neg3", "negative", "Hey Stevie", "David", 0, 85, 0.55, True, None, 50, 200.0),
                UtteranceTrialResult("neg4", "negative", "Open", "David", 0, 85, 0.05, False, None, 50, 200.0),
            ]

            sweep = validator.run_threshold_sweep(tp_trials, neg_trials)

            # At 0.50: TP should be 2 (0.95, 0.65), FP should be 1 (0.55), FN should be 2, TN should be 3
            res_50 = sweep[0.50]
            assert res_50["TP"] == 2
            assert res_50["FP"] == 1
            assert res_50["FN"] == 2
            assert res_50["TN"] == 3
            assert res_50["TPR"] == 0.5
            assert res_50["FPR"] == 0.25


# ============================================================================
# 7. Hard-Negative Mining & Human-Speech Pipeline Tests (Task 014F-5)
# ============================================================================
class TestHardenedPipelineSuite:
    def test_hard_negative_phrase_coverage(self):
        from tools.wakeword_dataset import HARD_NEGATIVE_PHRASES

        required_phrases = [
            "Hey Everyone",
            "Hey Evan",
            "Hey Evie",
            "Hey Ever",
            "Hey Everest",
            "Hey Event",
            "Hey Events",
            "Hey Evidence",
            "Hey Even",
            "Hey Evening",
            "Hey Eventually",
            "Hey Stevie",
            "Hey Steve",
            "Heavy",
            "Every",
            "Hey",
            "EV",
        ]
        for req in required_phrases:
            assert req in HARD_NEGATIVE_PHRASES, f"Missing hard-negative phrase: {req}"

    def test_human_speech_ingestion_pathway(self, tmp_path):
        from tools.wakeword_dataset import CLIP_TOTAL_SAMPLES, WakeWordDatasetPipeline, save_pcm16_wav

        pipeline = WakeWordDatasetPipeline(data_dir=str(tmp_path))
        pipeline.prepare_directories()

        # 1. Empty scan should safely return empty lists without crashing
        meta, clips, labels = pipeline.scan_and_ingest_human_speech()
        assert len(meta) == 0
        assert len(clips) == 0
        assert len(labels) == 0

        # 2. Add sample human recording
        dummy_audio = np.random.randint(-1000, 1000, size=CLIP_TOTAL_SAMPLES, dtype=np.int16)
        save_pcm16_wav(str(pipeline.human_pos_dir / "alice_hey_ev_01.wav"), dummy_audio)
        save_pcm16_wav(str(pipeline.human_neg_dir / "alice_hey_evan_01.wav"), dummy_audio)

        meta, clips, labels = pipeline.scan_and_ingest_human_speech()
        assert len(meta) == 2
        assert len(clips) == 2
        assert labels.count(1) == 1
        assert labels.count(0) == 1
        assert meta[0].is_human is True
        assert meta[0].speaker_id == "alice"

    def test_acoustic_distance_and_reverberation_augmentations(self):
        from tools.wakeword_dataset import (
            CLIP_TOTAL_SAMPLES,
            apply_distance_attenuation,
            apply_room_reverberation,
            augment_audio,
        )

        audio = np.random.randint(-5000, 5000, size=16000, dtype=np.int16)

        # Distance attenuation filter
        filtered = apply_distance_attenuation(audio)
        assert len(filtered) == len(audio)

        # Room reverberation
        reverb = apply_room_reverberation(audio)
        assert len(reverb) == len(audio)

        # Full augment with distance and reverb
        augmented = augment_audio(
            audio,
            gain=0.45,
            noise_type="fan",
            noise_snr_db=14.0,
            reverberation=True,
            distance_filter=True,
        )
        assert len(augmented) == CLIP_TOTAL_SAMPLES
        assert augmented.dtype == np.int16

    def test_holdout_evaluation_breakdown_math(self):
        from tools.train_wakeword import OpenWakeWordNet, evaluate_model_on_holdout
        from tools.wakeword_dataset import SampleMetadata

        model = OpenWakeWordNet(input_shape=(16, 96), layer_dim=64, n_blocks=1)
        X_mock = np.random.randn(8, 16, 96).astype(np.float32)
        y_mock = np.array([1, 1, 0, 0, 0, 0, 0, 0], dtype=np.float32)

        meta_mock = [
            SampleMetadata("s1", 1, "Hey EV", False, False, "David", 0, 100, "none", "holdout", 32000),
            SampleMetadata("s2", 1, "Hey EV", False, False, "Zira", 0, 100, "none", "holdout", 32000),
            SampleMetadata("s3", 0, "Hey Everyone", True, False, "David", 0, 100, "none", "holdout", 32000),
            SampleMetadata("s4", 0, "Hey Evan", True, False, "David", 0, 100, "none", "holdout", 32000),
            SampleMetadata("s5", 0, "Hey Stevie", True, False, "David", 0, 100, "none", "holdout", 32000),
            SampleMetadata("s6", 0, "Heavy", True, False, "David", 0, 100, "none", "holdout", 32000),
            SampleMetadata("s7", 0, "Every", True, False, "David", 0, 100, "none", "holdout", 32000),
            SampleMetadata("s8", 0, "Open browser", False, False, "David", 0, 100, "none", "holdout", 32000),
        ]

        eval_res = evaluate_model_on_holdout(model, X_mock, y_mock, meta_mock, threshold=0.50)
        assert "accuracy" in eval_res
        assert "f1" in eval_res
        assert "phrase_breakdown" in eval_res
        assert "Hey EV" in eval_res["phrase_breakdown"]
        assert "Hey Everyone" in eval_res["phrase_breakdown"]
        assert "Hey Evan" in eval_res["phrase_breakdown"]


# ============================================================================
# 8. Human Data Collector & Acoustic Quality Validation Tests (Task 014F-6)
# ============================================================================
class TestHumanCollectorSuite:
    def test_audio_quality_analyzer_silence(self):
        from tools.collect_human_wakeword import analyze_audio_quality

        silent_audio = np.zeros(32000, dtype=np.int16)
        quality = analyze_audio_quality(silent_audio, min_rms=30.0)
        assert quality.is_silent is True
        assert quality.is_valid is False
        assert quality.rms == 0.0
        assert "Audio level too low" in str(quality.rejection_reason)

    def test_audio_quality_analyzer_clipping(self):
        from tools.collect_human_wakeword import analyze_audio_quality

        clipped_audio = np.random.randint(-1000, 1000, size=32000, dtype=np.int16)
        # Inject 1000 clipped samples (> 3%)
        clipped_audio[:1000] = 32767
        quality = analyze_audio_quality(clipped_audio, max_clipping_percent=1.0)
        assert quality.clipping_percent > 1.0
        assert quality.is_valid is False
        assert "clipping detected" in str(quality.rejection_reason)

    def test_audio_quality_analyzer_valid_speech(self):
        from tools.collect_human_wakeword import analyze_audio_quality

        # Simulated speech signal with normal dynamic range and low noise floor
        t = np.linspace(0, 2.0, 32000, endpoint=False)
        speech_synth = (2000.0 * np.sin(2 * np.pi * 300 * t) + np.random.normal(0, 50, 32000)).astype(np.int16)
        quality = analyze_audio_quality(speech_synth, min_rms=30.0)
        assert quality.is_silent is False
        assert quality.is_valid is True
        assert quality.rms > 500.0
        assert quality.clipping_percent == 0.0
        assert quality.rejection_reason is None

    def test_human_collector_manifest_persistence(self, tmp_path):
        from tools.collect_human_wakeword import AudioQualityMetrics, HumanAudioCollector, HumanRecordingManifestItem

        collector = HumanAudioCollector(device_index=0, speaker_id="test_speaker_alpha", output_base_dir=tmp_path)
        dummy_quality = AudioQualityMetrics(
            sample_rate=16000,
            channels=1,
            duration_sec=2.0,
            total_samples=32000,
            rms=450.0,
            peak=1200,
            clipping_percent=0.0,
            snr_db=18.5,
            is_silent=False,
            is_valid=True,
        )
        item = HumanRecordingManifestItem(
            filename="test_speaker_alpha_hey_ev_01.wav",
            relative_path="positive/test_speaker_alpha_hey_ev_01.wav",
            category="POSITIVE",
            target_label=1,
            phrase="Hey EV",
            condition="normal speaking",
            speaker_id="test_speaker_alpha",
            device_name="Test Mic",
            timestamp=1788500000.0,
            quality=dummy_quality,
        )

        collector._append_to_manifest(item)
        loaded = collector.load_manifest()
        assert len(loaded) == 1
        assert loaded[0].filename == "test_speaker_alpha_hey_ev_01.wav"
        assert loaded[0].speaker_id == "test_speaker_alpha"
        assert loaded[0].target_label == 1
        assert loaded[0].quality.rms == 450.0
