"""
E.V. Task 014F-11 Controlled Experiment Suite: Targeted Hard-Negative Recovery.

Executes controlled candidate training experiments evaluated strictly on the
non-holdout Development Validation Partition.
Selects the single optimal Candidate V2 based on Dev metrics, exports to
D:\\EV\\models\\wakeword\\candidates\\hey_ev_human_v3.onnx, and executes a 3-way
locked holdout benchmark across 7 thresholds against Active Baseline and Candidate V1.
"""
from __future__ import annotations

import copy
import json
import logging
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
import onnx
import onnxruntime as ort
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset

# Ensure repo root is on sys.path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from core.voice_wakeword_openwakeword import OpenWakeWordProvider
from tools.wakeword_dataset import (
    CANONICAL_SAMPLE_RATE,
    CLIP_DURATION_SECONDS,
    CLIP_TOTAL_SAMPLES,
    HARD_NEGATIVE_PHRASES,
    POSITIVE_PHRASES,
    SampleMetadata,
    WakeWordDatasetPipeline,
    augment_audio,
    audit_dataset_leakage,
    compute_file_sha256,
    load_pcm16_wav,
    pad_or_trim_to_length,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ev.wakeword.experiment_014f11")

DEFAULT_ACTIVE_MODEL = r"D:\EV\models\wakeword\hey_ev.onnx"
DEFAULT_BASELINE_MODEL = r"D:\EV\models\wakeword\hey_ev_v1_baseline.onnx"
DEFAULT_CANDIDATE_V1_MODEL = r"D:\EV\models\wakeword\candidates\hey_ev_human_v2.onnx"
CANDIDATES_DIR = r"D:\EV\models\wakeword\candidates"
NEW_CANDIDATE_OUTPUT_PATH = r"D:\EV\models\wakeword\candidates\hey_ev_human_v3.onnx"

EXPECTED_ACTIVE_SHA = "9b11e3db5ca4118a19a35618f91db66aabc66c1ffe762cd69b215c9a1204f377"
EXPECTED_CANDIDATE_V1_SHA = "9286c84a97b31a0934947dd56500ba5295937cc65d0be1126aff54039a2cea9d"
EXPECTED_HOLDOUT_SHA = "03a59c13fa35fa932065e364e0b4bde2c3d174efc8f774f9f03ba96dfefe18ba"


class FCNBlock(nn.Module):
    def __init__(self, layer_dim: int) -> None:
        super().__init__()
        self.fcn_layer = nn.Linear(layer_dim, layer_dim)
        self.relu = nn.ReLU()
        self.layer_norm = nn.LayerNorm(layer_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.relu(self.layer_norm(self.fcn_layer(x)))


class OpenWakeWordNet(nn.Module):
    def __init__(
        self,
        input_shape: Tuple[int, int] = (16, 96),
        layer_dim: int = 128,
        n_blocks: int = 1,
        n_classes: int = 1,
    ) -> None:
        super().__init__()
        self.input_shape = input_shape
        self.flatten = nn.Flatten()
        self.layer1 = nn.Linear(input_shape[0] * input_shape[1], layer_dim)
        self.relu1 = nn.ReLU()
        self.layernorm1 = nn.LayerNorm(layer_dim)
        self.blocks = nn.ModuleList([FCNBlock(layer_dim) for _ in range(n_blocks)])
        self.last_layer = nn.Linear(layer_dim, n_classes)
        self.last_act = nn.Sigmoid() if n_classes == 1 else nn.ReLU()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.relu1(self.layernorm1(self.layer1(self.flatten(x))))
        for block in self.blocks:
            x = block(x)
        return self.last_act(self.last_layer(x))


def verify_active_model_hash() -> str:
    active_p = Path(DEFAULT_ACTIVE_MODEL)
    if not active_p.exists():
        raise FileNotFoundError(f"Active model hey_ev.onnx missing at {DEFAULT_ACTIVE_MODEL}")
    actual_sha = compute_file_sha256(active_p)
    if actual_sha != EXPECTED_ACTIVE_SHA.lower():
        raise RuntimeError(
            f"CRITICAL IMMUTABILITY VIOLATION: Active model SHA256 mismatch!\n"
            f"Expected: {EXPECTED_ACTIVE_SHA}\n"
            f"Actual:   {actual_sha}"
        )
    return actual_sha


def verify_candidate_v1_hash() -> str:
    v1_p = Path(DEFAULT_CANDIDATE_V1_MODEL)
    if not v1_p.exists():
        raise FileNotFoundError(f"Candidate V1 missing at {DEFAULT_CANDIDATE_V1_MODEL}")
    actual_sha = compute_file_sha256(v1_p)
    if actual_sha != EXPECTED_CANDIDATE_V1_SHA.lower():
        raise RuntimeError(
            f"CRITICAL CANDIDATE V1 TAMPERING DETECTED!\n"
            f"Expected: {EXPECTED_CANDIDATE_V1_SHA}\n"
            f"Actual:   {actual_sha}"
        )
    return actual_sha


def generate_targeted_dataset(
    random_seed: int = 42,
    hn_aug_level: str = "enhanced",  # "standard", "enhanced", "phonetic_oversample"
) -> Tuple[List[SampleMetadata], List[np.ndarray], List[int]]:
    """
    Generate dataset with controlled hard-negative augmentation levels.
    """
    pipeline = WakeWordDatasetPipeline(random_seed=random_seed)
    pipeline.prepare_directories()

    holdout_shas = set()
    holdout_filenames = set()
    holdout_relpaths = set()
    if pipeline.holdout_manifest_path and pipeline.holdout_manifest_path.exists():
        with open(pipeline.holdout_manifest_path, "r", encoding="utf-8") as hf:
            h_data = json.load(hf)
            for s in h_data.get("samples", []):
                if "sha256" in s:
                    holdout_shas.add(s["sha256"].lower())
                if "filename" in s:
                    holdout_filenames.add(s["filename"].lower())
                if "relative_path" in s:
                    holdout_relpaths.add(s["relative_path"].replace("\\", "/").lower())

    manifest_lookup = {}
    quarantine_shas = set()
    if pipeline.manifest_path.exists():
        with open(pipeline.manifest_path, "r", encoding="utf-8") as mf:
            m_data = json.load(mf)
            for item in m_data:
                rel = str(item.get("relative_path", "")).replace("\\", "/")
                if rel:
                    manifest_lookup[rel] = item
                cat = str(item.get("category", "")).upper()
                fn = str(item.get("filename", ""))
                if cat and fn:
                    manifest_lookup[f"{cat}::{fn}"] = item
                if fn and fn not in manifest_lookup:
                    manifest_lookup[fn] = item
                if cat == "QUARANTINE" and "sha256" in item:
                    quarantine_shas.add(item["sha256"].lower())

    if pipeline.human_quarantine_dir.exists():
        for q_wav in pipeline.human_quarantine_dir.glob("*.wav"):
            try:
                quarantine_shas.add(compute_file_sha256(q_wav))
            except Exception:
                pass

    human_meta: List[SampleMetadata] = []
    human_clips: List[np.ndarray] = []
    human_labels: List[int] = []

    # Valid Positives (52 files)
    valid_pos_files = []
    for wav_file in sorted(pipeline.human_pos_dir.glob("*.wav")):
        rel_key = f"positive/{wav_file.name}"
        m_info = manifest_lookup.get(rel_key) or manifest_lookup.get(f"POSITIVE::{wav_file.name}") or manifest_lookup.get(wav_file.name)
        file_sha = compute_file_sha256(wav_file)
        if file_sha in holdout_shas or wav_file.name.lower() in holdout_filenames or rel_key.lower() in holdout_relpaths:
            continue
        if (m_info and m_info.get("category") == "QUARANTINE") or (file_sha in quarantine_shas and not (m_info and m_info.get("confirmed_by_user", False))):
            continue
        valid_pos_files.append((wav_file, file_sha, m_info))

    for p_idx, (wav_file, file_sha, m_info) in enumerate(valid_pos_files):
        audio = load_pcm16_wav(str(wav_file))
        speaker = wav_file.stem.split("_")[0] if "_" in wav_file.stem else "user_speaker_1"
        phrase = m_info.get("phrase", "Hey EV") if m_info else "Hey EV"
        split = "val" if (p_idx % 7 == 6) else "train"

        raw_clip = pad_or_trim_to_length(audio, CLIP_TOTAL_SAMPLES)
        human_meta.append(SampleMetadata(
            sample_id=f"human_pos_{wav_file.stem}_raw",
            label=1, phrase=phrase, is_hard_negative=False, is_human=True, speaker_id=speaker,
            rate=0, volume=100, augmentation="raw_human", split=split, duration_samples=len(raw_clip),
            sha256=file_sha, source_file=wav_file.name,
        ))
        human_clips.append(raw_clip)
        human_labels.append(1)

        aug_configs = [
            ("boost_quiet", 1.25, "none", 30.0, 0.5),
            ("attenuate_loud", 0.80, "none", 30.0, 0.5),
            ("room_noise", 1.00, "fan", 22.0, 0.5),
            ("time_early", 1.00, "none", 30.0, 0.35),
            ("time_late", 1.00, "none", 30.0, 0.65),
        ]
        for aug_name, gain, noise, snr, offset in aug_configs:
            aug_clip = augment_audio(audio, gain=gain, noise_type=noise, noise_snr_db=snr, time_offset_fraction=offset)
            human_meta.append(SampleMetadata(
                sample_id=f"human_pos_{wav_file.stem}_{aug_name}",
                label=1, phrase=phrase, is_hard_negative=False, is_human=True, speaker_id=speaker,
                rate=0, volume=100, augmentation=f"human_{aug_name}", split=split, duration_samples=len(aug_clip),
                sha256=file_sha, source_file=wav_file.name,
            ))
            human_clips.append(aug_clip)
            human_labels.append(1)

    # Valid Negatives (48 files)
    valid_neg_files = []
    for wav_file in sorted(pipeline.human_neg_dir.glob("*.wav")):
        rel_key = f"negative/{wav_file.name}"
        m_info = manifest_lookup.get(rel_key) or manifest_lookup.get(f"HARD_NEGATIVE::{wav_file.name}") or manifest_lookup.get(f"NEGATIVE::{wav_file.name}") or manifest_lookup.get(wav_file.name)
        file_sha = compute_file_sha256(wav_file)
        if file_sha in holdout_shas or wav_file.name.lower() in holdout_filenames or rel_key.lower() in holdout_relpaths:
            continue
        if (m_info and m_info.get("category") == "QUARANTINE") or (file_sha in quarantine_shas and not (m_info and m_info.get("confirmed_by_user", False))):
            continue
        valid_neg_files.append((wav_file, file_sha, m_info))

    for n_idx, (wav_file, file_sha, m_info) in enumerate(valid_neg_files):
        audio = load_pcm16_wav(str(wav_file))
        speaker = wav_file.stem.split("_")[0] if "_" in wav_file.stem else "user_speaker_1"
        phrase = m_info.get("phrase", wav_file.stem) if m_info else wav_file.stem
        is_hn = bool(
            (m_info and m_info.get("category") == "HARD_NEGATIVE")
            or any(k in phrase.lower() for k in ["hey ev", "hey", "ev", "every", "heavy", "stevie", "steve"])
        )
        split = "val" if (n_idx % 7 == 6) else "train"

        raw_clip = pad_or_trim_to_length(audio, CLIP_TOTAL_SAMPLES)
        human_meta.append(SampleMetadata(
            sample_id=f"human_neg_{wav_file.stem}_raw",
            label=0, phrase=phrase, is_hard_negative=is_hn, is_human=True, speaker_id=speaker,
            rate=0, volume=100, augmentation="raw_human", split=split, duration_samples=len(raw_clip),
            sha256=file_sha, source_file=wav_file.name,
        ))
        human_clips.append(raw_clip)
        human_labels.append(0)

        # Negative Augmentations based on experiment level
        if hn_aug_level == "standard":
            neg_aug_configs = [
                ("gain_low", 0.85, "none", 30.0, 0.5),
                ("gain_high", 1.15, "none", 30.0, 0.5),
                ("ambient_fan", 1.00, "fan", 22.0, 0.5),
            ]
        elif hn_aug_level in ("enhanced", "phonetic_oversample"):
            neg_aug_configs = [
                ("gain_low", 0.80, "none", 30.0, 0.5),
                ("gain_high", 1.20, "none", 30.0, 0.5),
                ("ambient_fan", 1.00, "fan", 22.0, 0.5),
                ("ambient_pink", 1.00, "pink", 24.0, 0.5),
                ("time_early", 1.00, "none", 30.0, 0.35),
                ("time_late", 1.00, "none", 30.0, 0.65),
                ("reverb", 1.00, "none", 30.0, 0.5),
            ]
            if is_hn and hn_aug_level == "phonetic_oversample":
                neg_aug_configs.extend([
                    ("dist_filter", 0.90, "none", 30.0, 0.5),
                    ("quiet_confusable", 0.65, "fan", 20.0, 0.45),
                    ("loud_confusable", 1.30, "none", 30.0, 0.55),
                ])

        for aug_name, gain, noise, snr, offset in neg_aug_configs:
            aug_clip = augment_audio(
                audio,
                gain=gain,
                noise_type=noise,
                noise_snr_db=snr,
                time_offset_fraction=offset,
                reverberation=(aug_name == "reverb"),
                distance_filter=(aug_name == "dist_filter"),
            )
            human_meta.append(SampleMetadata(
                sample_id=f"human_neg_{wav_file.stem}_{aug_name}",
                label=0, phrase=phrase, is_hard_negative=is_hn, is_human=True, speaker_id=speaker,
                rate=0, volume=100, augmentation=f"human_{aug_name}", split=split, duration_samples=len(aug_clip),
                sha256=file_sha, source_file=wav_file.name,
            ))
            human_clips.append(aug_clip)
            human_labels.append(0)

    # Synthetic data
    voices = ["Microsoft David Desktop"]
    samples_metadata: List[SampleMetadata] = list(human_meta)
    audio_clips: List[np.ndarray] = list(human_clips)
    labels: List[int] = list(human_labels)

    # Synthetic Positives (48 base * 8 augs = 384)
    for p_idx in range(48):
        phrase = POSITIVE_PHRASES[p_idx % len(POSITIVE_PHRASES)]
        voice = voices[0]
        rate = [-2, -1, 0, 1, 2][p_idx % 5]
        vol = [50, 70, 85, 100][p_idx % 4]
        split = "val" if (p_idx % 7 == 5) else ("holdout" if (p_idx % 7 == 6) else "train")
        base_path = pipeline.raw_dir / f"pos_base_h_{p_idx}.wav"
        if not base_path.exists():
            continue
        base_audio = load_pcm16_wav(str(base_path))

        for aug_i in range(8):
            gain = 1.0 if aug_i == 0 else float(np.random.uniform(0.5, 1.3))
            noise = "none" if aug_i == 0 else np.random.choice(["none", "fan", "pink", "keyboard"])
            snr = 30.0 if aug_i == 0 else float(np.random.uniform(12.0, 26.0))
            time_offset = float(np.random.uniform(0.15, 0.85))
            aug_clip = augment_audio(base_audio, gain=gain, noise_type=str(noise), noise_snr_db=snr, time_offset_fraction=time_offset)
            samples_metadata.append(SampleMetadata(
                sample_id=f"pos_synth_{p_idx}_{aug_i}", label=1, phrase=phrase, is_hard_negative=False,
                is_human=False, speaker_id="David", rate=rate, volume=vol, augmentation="synth_pos",
                split=split, duration_samples=len(aug_clip),
            ))
            audio_clips.append(aug_clip)
            labels.append(1)

    # Synthetic Hard Negatives
    hn_id = 0
    for phrase in HARD_NEGATIVE_PHRASES:
        for rate in [-1, 0, 1]:
            split = "val" if (hn_id % 7 == 5) else ("holdout" if (hn_id % 7 == 6) else "train")
            base_path = pipeline.raw_dir / f"neg_hn_{hn_id}.wav"
            if not base_path.exists():
                hn_id += 1
                continue
            base_audio = load_pcm16_wav(str(base_path))
            num_synth_augs = 8 if hn_aug_level in ("enhanced", "phonetic_oversample") else 6
            for aug_i in range(num_synth_augs):
                gain = float(np.random.uniform(0.60, 1.25))
                noise = np.random.choice(["none", "fan", "pink", "keyboard"])
                snr = float(np.random.uniform(12.0, 26.0))
                time_offset = float(np.random.uniform(0.10, 0.85))
                aug_clip = augment_audio(base_audio, gain=gain, noise_type=str(noise), noise_snr_db=snr, time_offset_fraction=time_offset)
                samples_metadata.append(SampleMetadata(
                    sample_id=f"neg_hn_synth_{hn_id}_{aug_i}", label=0, phrase=phrase, is_hard_negative=True,
                    is_human=False, speaker_id="David", rate=rate, volume=85, augmentation="synth_hn",
                    split=split, duration_samples=len(aug_clip),
                ))
                audio_clips.append(aug_clip)
                labels.append(0)
            hn_id += 1

    # Synthetic Command Negatives
    for cmd_id, phrase in enumerate(["Open the browser", "Turn on the lights", "What time is it", "Cancel that command", "System status report", "Show active tasks", "Search the web", "Close the window", "Increase the volume", "Mute the speakers", "Run diagnostics", "Open files"]):
        split = "val" if (cmd_id % 7 == 5) else ("holdout" if (cmd_id % 7 == 6) else "train")
        base_path = pipeline.raw_dir / f"neg_cmd_{cmd_id}.wav"
        if not base_path.exists():
            continue
        base_audio = load_pcm16_wav(str(base_path))
        for aug_i in range(3):
            gain = float(np.random.uniform(0.70, 1.20))
            noise = np.random.choice(["none", "fan", "pink"])
            snr = float(np.random.uniform(14.0, 26.0))
            aug_clip = augment_audio(base_audio, gain=gain, noise_type=str(noise), noise_snr_db=snr, time_offset_fraction=0.5)
            samples_metadata.append(SampleMetadata(
                sample_id=f"neg_cmd_synth_{cmd_id}_{aug_i}", label=0, phrase=phrase, is_hard_negative=False,
                is_human=False, speaker_id="David", rate=0, volume=85, augmentation="synth_cmd",
                split=split, duration_samples=len(aug_clip),
            ))
            audio_clips.append(aug_clip)
            labels.append(0)

    # Ambient non-speech
    for amb_i in range(50):
        noise_type = ["fan", "keyboard", "pink", "white", "silence"][amb_i % 5]
        split = "val" if (amb_i % 7 == 5) else ("holdout" if (amb_i % 7 == 6) else "train")
        if noise_type == "silence":
            clip = np.zeros(CLIP_TOTAL_SAMPLES, dtype=np.int16)
        elif noise_type == "fan":
            t = np.linspace(0, CLIP_DURATION_SECONDS, CLIP_TOTAL_SAMPLES, endpoint=False)
            clip = (1200.0 * np.sin(2 * np.pi * 60 * t) + 400.0 * np.sin(2 * np.pi * 120 * t) + np.random.normal(0, 400.0, CLIP_TOTAL_SAMPLES)).astype(np.int16)
        elif noise_type == "keyboard":
            clip = np.random.normal(0, 200.0, CLIP_TOTAL_SAMPLES).astype(np.int16)
        elif noise_type == "pink":
            white = np.random.normal(0, 1000.0, CLIP_TOTAL_SAMPLES)
            clip = np.convolve(white, np.ones(8) / 8.0, mode="same").astype(np.int16)
        else:
            clip = np.random.normal(0, 800.0, CLIP_TOTAL_SAMPLES).astype(np.int16)

        samples_metadata.append(SampleMetadata(
            sample_id=f"neg_amb_{amb_i}", label=0, phrase=f"ambient_{noise_type}", is_hard_negative=False,
            is_human=False, speaker_id="none", rate=0, volume=0, augmentation=f"amb_{noise_type}",
            split=split, duration_samples=len(clip),
        ))
        audio_clips.append(clip)
        labels.append(0)

    audit_dataset_leakage(samples_metadata, pipeline.holdout_manifest_path)
    return samples_metadata, audio_clips, labels


def evaluate_on_dev_val_set(
    model: nn.Module,
    X_val: np.ndarray,
    y_val: np.ndarray,
    meta_val: List[SampleMetadata],
    threshold: float = 0.50,
) -> Dict[str, Any]:
    model.eval()
    with torch.no_grad():
        inputs = torch.from_numpy(X_val).float()
        scores = model(inputs).numpy().flatten()

    preds_bin = (scores >= threshold).astype(int)
    targets_bin = y_val.astype(int)

    tp = int(np.sum((preds_bin == 1) & (targets_bin == 1)))
    fp = int(np.sum((preds_bin == 1) & (targets_bin == 0)))
    tn = int(np.sum((preds_bin == 0) & (targets_bin == 0)))
    fn = int(np.sum((preds_bin == 0) & (targets_bin == 1)))

    total = len(targets_bin)
    acc = (tp + tn) / max(1, total)
    prec = tp / max(1, tp + fp)
    rec = tp / max(1, tp + fn)
    f1 = (2 * prec * rec) / max(1e-6, prec + rec)
    fpr = fp / max(1, fp + tn)
    fnr = fn / max(1, fn + tp)

    human_pos_idx = [i for i, m in enumerate(meta_val) if m.is_human and m.label == 1]
    human_hn_idx = [i for i, m in enumerate(meta_val) if m.is_human and m.is_hard_negative]
    human_gn_idx = [i for i, m in enumerate(meta_val) if m.is_human and not m.is_hard_negative and m.label == 0]
    synth_pos_idx = [i for i, m in enumerate(meta_val) if not m.is_human and m.label == 1]
    synth_hn_idx = [i for i, m in enumerate(meta_val) if not m.is_human and m.is_hard_negative]
    synth_gn_idx = [i for i, m in enumerate(meta_val) if not m.is_human and not m.is_hard_negative and m.label == 0]

    human_pos_tp = int(np.sum(preds_bin[human_pos_idx] == 1)) if human_pos_idx else 0
    human_pos_total = len(human_pos_idx)
    human_pos_recall = human_pos_tp / max(1, human_pos_total)

    human_hn_fp = int(np.sum(preds_bin[human_hn_idx] == 1)) if human_hn_idx else 0
    human_hn_total = len(human_hn_idx)
    human_hn_fpr = human_hn_fp / max(1, human_hn_total)

    human_gn_fp = int(np.sum(preds_bin[human_gn_idx] == 1)) if human_gn_idx else 0
    human_gn_total = len(human_gn_idx)
    human_gn_fpr = human_gn_fp / max(1, human_gn_total)

    synth_pos_recall = (int(np.sum(preds_bin[synth_pos_idx] == 1)) / max(1, len(synth_pos_idx))) if synth_pos_idx else 0.0
    synth_hn_fpr = (int(np.sum(preds_bin[synth_hn_idx] == 1)) / max(1, len(synth_hn_idx))) if synth_hn_idx else 0.0
    synth_gn_fpr = (int(np.sum(preds_bin[synth_gn_idx] == 1)) / max(1, len(synth_gn_idx))) if synth_gn_idx else 0.0

    return {
        "threshold": threshold,
        "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        "accuracy": round(float(acc), 4),
        "precision": round(float(prec), 4),
        "recall": round(float(rec), 4),
        "f1": round(float(f1), 4),
        "fpr": round(float(fpr), 4),
        "fnr": round(float(fnr), 4),
        "human_pos_recall": round(float(human_pos_recall), 4),
        "human_pos_tp": human_pos_tp,
        "human_pos_total": human_pos_total,
        "human_hn_fpr": round(float(human_hn_fpr), 4),
        "human_hn_fp": human_hn_fp,
        "human_hn_total": human_hn_total,
        "human_gn_fpr": round(float(human_gn_fpr), 4),
        "human_gn_fp": human_gn_fp,
        "human_gn_total": human_gn_total,
        "synth_pos_recall": round(float(synth_pos_recall), 4),
        "synth_hn_fpr": round(float(synth_hn_fpr), 4),
        "synth_gn_fpr": round(float(synth_gn_fpr), 4),
    }


def train_and_eval_configuration(
    config_name: str,
    X_train: np.ndarray,
    y_train: np.ndarray,
    meta_train: List[SampleMetadata],
    X_val: np.ndarray,
    y_val: np.ndarray,
    meta_val: List[SampleMetadata],
    epochs: int = 45,
    batch_size: int = 32,
    lr: float = 8e-4,
    weight_decay: float = 1e-4,
    loss_type: str = "weighted_bce",
    neg_weight: float = 1.4,
    hn_weight: float = 3.5,
    focal_gamma: float = 1.5,
    seed: int = 42,
) -> Tuple[OpenWakeWordNet, Dict[str, Any]]:
    torch.manual_seed(seed)
    np.random.seed(seed)

    zero_train = np.zeros((48, 16, 96), dtype=np.float32)
    zero_train_y = np.zeros(48, dtype=np.float32)
    X_train_ext = np.vstack([X_train, zero_train])
    y_train_ext = np.concatenate([y_train, zero_train_y])

    is_hn_flags = np.array([1.0 if m.is_hard_negative else 0.0 for m in meta_train] + [0.0]*48, dtype=np.float32)
    is_human_flags = np.array([1.0 if m.is_human else 0.0 for m in meta_train] + [0.0]*48, dtype=np.float32)

    train_dataset = TensorDataset(
        torch.from_numpy(X_train_ext).float(),
        torch.from_numpy(y_train_ext).float().unsqueeze(1),
        torch.from_numpy(is_hn_flags).float().unsqueeze(1),
        torch.from_numpy(is_human_flags).float().unsqueeze(1),
    )
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)

    model = OpenWakeWordNet(input_shape=(16, 96), layer_dim=128, n_blocks=1)
    optimizer = optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)

    def compute_loss(preds: torch.Tensor, targets: torch.Tensor, is_hn: torch.Tensor, is_human: torch.Tensor) -> torch.Tensor:
        eps = 1e-7
        preds = torch.clamp(preds, eps, 1.0 - eps)

        if loss_type == "weighted_bce":
            loss = -(targets * torch.log(preds) + neg_weight * (1.0 - targets) * torch.log(1.0 - preds))
            return torch.mean(loss)

        elif loss_type == "two_tier_hn":
            sample_neg_w = torch.where(
                is_hn > 0.5,
                torch.full_like(targets, hn_weight),
                torch.full_like(targets, neg_weight)
            )
            # Emphasize human confusables
            sample_neg_w = torch.where(
                (is_hn > 0.5) & (is_human > 0.5),
                sample_neg_w * 1.35,
                sample_neg_w
            )
            loss = -(targets * torch.log(preds) + sample_neg_w * (1.0 - targets) * torch.log(1.0 - preds))
            return torch.mean(loss)

        elif loss_type == "focal_loss":
            p_t = targets * preds + (1.0 - targets) * (1.0 - preds)
            focal_mod = torch.pow(1.0 - p_t, focal_gamma)
            sample_w = torch.where(
                targets > 0.5,
                torch.tensor(1.0),
                torch.where(is_hn > 0.5, torch.tensor(hn_weight), torch.tensor(neg_weight))
            )
            bce = -(targets * torch.log(preds) + (1.0 - targets) * torch.log(1.0 - preds))
            loss = sample_w * focal_mod * bce
            return torch.mean(loss)

        else:
            raise ValueError(f"Unknown loss type: {loss_type}")

    best_dev_score = -float("inf")
    best_weights = copy.deepcopy(model.state_dict())
    best_dev_metrics: Dict[str, Any] = {}
    best_epoch = 0

    for epoch in range(1, epochs + 1):
        model.train()
        train_loss = 0.0
        for b_x, b_y, b_hn, b_hum in train_loader:
            optimizer.zero_grad()
            preds = model(b_x)
            loss = compute_loss(preds, b_y, b_hn, b_hum)
            loss.backward()
            optimizer.step()
            train_loss += loss.item() * len(b_x)
        train_loss /= len(train_dataset)

        val_eval = evaluate_on_dev_val_set(model, X_val, y_val, meta_val, threshold=0.50)
        # Multi-objective dev score: reward human positive recall, heavily penalize human hard-negative FPR
        dev_score = val_eval["human_pos_recall"] * 1.5 - val_eval["human_hn_fpr"] * 2.0 + val_eval["f1"] * 0.5

        if dev_score > best_dev_score:
            best_dev_score = dev_score
            best_weights = copy.deepcopy(model.state_dict())
            best_dev_metrics = val_eval
            best_epoch = epoch

    model.load_state_dict(best_weights)
    model.eval()

    dev_threshold_sweep = {}
    for t in (0.30, 0.40, 0.50, 0.55, 0.60, 0.65, 0.70):
        dev_threshold_sweep[str(t)] = evaluate_on_dev_val_set(model, X_val, y_val, meta_val, threshold=t)

    result_summary = {
        "config_name": config_name,
        "seed": seed,
        "epochs": epochs,
        "best_epoch": best_epoch,
        "batch_size": batch_size,
        "lr": lr,
        "weight_decay": weight_decay,
        "loss_type": loss_type,
        "neg_weight": neg_weight,
        "hn_weight": hn_weight,
        "focal_gamma": focal_gamma if loss_type == "focal_loss" else None,
        "dev_score": round(float(best_dev_score), 4),
        "dev_metrics_at_05": best_dev_metrics,
        "dev_threshold_sweep": dev_threshold_sweep,
    }

    logger.info(
        "%-20s | BestEp: %2d | PosRec: %5.1f%% | HN_FPR: %5.1f%% | GN_FPR: %5.1f%% | F1: %5.3f | DevScore: %6.3f",
        config_name, best_epoch,
        best_dev_metrics["human_pos_recall"] * 100,
        best_dev_metrics["human_hn_fpr"] * 100,
        best_dev_metrics["human_gn_fpr"] * 100,
        best_dev_metrics["f1"],
        best_dev_score,
    )
    return model, result_summary


def export_model_to_onnx(model: OpenWakeWordNet, output_onnx_path: str) -> Path:
    output_path = Path(output_onnx_path)
    if output_path.resolve() == Path(DEFAULT_ACTIVE_MODEL).resolve():
        raise PermissionError(f"CRITICAL SAFETY VIOLATION: Cannot overwrite {DEFAULT_ACTIVE_MODEL}")
    if output_path.resolve() == Path(DEFAULT_CANDIDATE_V1_MODEL).resolve():
        raise PermissionError(f"CRITICAL SAFETY VIOLATION: Cannot overwrite Candidate V1 at {DEFAULT_CANDIDATE_V1_MODEL}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    model.eval()
    model.to("cpu")
    dummy_input = torch.randn(1, 16, 96, dtype=torch.float32)

    logger.info("Exporting Candidate V2 model to ONNX at %s...", output_path)
    torch.onnx.export(
        model,
        dummy_input,
        str(output_path),
        opset_version=13,
        input_names=["input"],
        output_names=["output"],
        dynamo=False,
        dynamic_axes={"input": {0: "batch"}, "output": {0: "batch"}},
    )

    onnx_model = onnx.load(str(output_path))
    onnx.checker.check_model(onnx_model)
    logger.info("Candidate V2 ONNX checker passed!")
    return output_path


def evaluate_onnx_model_on_locked_holdout(
    onnx_path: str,
    X_holdout: np.ndarray,
    y_holdout: np.ndarray,
    holdout_samples: List[Dict[str, Any]],
    thresholds: Sequence[float] = (0.30, 0.40, 0.50, 0.55, 0.60, 0.65, 0.70),
    human_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    scores: np.ndarray
    used_streaming = False

    if human_dir is not None and Path(human_dir).exists():
        try:
            from openwakeword.model import Model
            oww = Model(wakeword_models=[onnx_path], inference_framework="onnx")
            computed_scores = []
            for s in holdout_samples:
                wav_p = str(Path(human_dir) / s["relative_path"])
                if os.path.exists(wav_p):
                    oww.reset()
                    preds = oww.predict_clip(wav_p, padding=0)
                    m = float(max([x[list(x.keys())[0]] for x in preds])) if preds else 0.0
                    computed_scores.append(m)
                else:
                    raise FileNotFoundError(f"Missing holdout wav: {wav_p}")
            scores = np.array(computed_scores)
            used_streaming = True
        except Exception as exc:
            logger.warning("Streaming holdout evaluation unavailable (%s); using static embedding features.", exc)
            session = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
            in_name = session.get_inputs()[0].name
            out_name = session.get_outputs()[0].name
            scores = session.run([out_name], {in_name: X_holdout.astype(np.float32)})[0].flatten()
    else:
        session = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
        in_name = session.get_inputs()[0].name
        out_name = session.get_outputs()[0].name
        scores = session.run([out_name], {in_name: X_holdout.astype(np.float32)})[0].flatten()

    targets_bin = y_holdout.astype(int)
    results_by_thresh: Dict[str, Dict[str, Any]] = {}

    hard_neg_indices = [i for i, s in enumerate(holdout_samples) if s.get("category") == "HARD_NEGATIVE"]
    gen_neg_indices = [i for i, s in enumerate(holdout_samples) if s.get("category") == "GENERAL_NEGATIVE"]
    pos_indices = [i for i, s in enumerate(holdout_samples) if s.get("category") == "POSITIVE"]

    for thresh in thresholds:
        preds_bin = (scores >= thresh).astype(int)
        tp = int(np.sum((preds_bin == 1) & (targets_bin == 1)))
        fp = int(np.sum((preds_bin == 1) & (targets_bin == 0)))
        tn = int(np.sum((preds_bin == 0) & (targets_bin == 0)))
        fn = int(np.sum((preds_bin == 0) & (targets_bin == 1)))

        total = max(1, len(targets_bin))
        acc = (tp + tn) / total
        precision = tp / max(1, tp + fp)
        recall = tp / max(1, tp + fn)
        f1 = (2 * precision * recall) / max(1e-6, precision + recall)
        fpr = fp / max(1, fp + tn)
        fnr = fn / max(1, fn + tp)

        hn_fps = int(np.sum(preds_bin[hard_neg_indices] == 1))
        gn_fps = int(np.sum(preds_bin[gen_neg_indices] == 1))
        pos_detected = int(np.sum(preds_bin[pos_indices] == 1))

        results_by_thresh[str(thresh)] = {
            "threshold": thresh,
            "tp": tp,
            "tn": tn,
            "fp": fp,
            "fn": fn,
            "accuracy": round(float(acc), 4),
            "precision": round(float(precision), 4),
            "recall": round(float(recall), 4),
            "f1": round(float(f1), 4),
            "fpr": round(float(fpr), 4),
            "fnr": round(float(fnr), 4),
            "positive_recall_count": pos_detected,
            "positive_total": len(pos_indices),
            "hard_neg_fp_count": hn_fps,
            "hard_neg_total": len(hard_neg_indices),
            "gen_neg_fp_count": gn_fps,
            "gen_neg_total": len(gen_neg_indices),
        }

    sample_details = []
    for i, s in enumerate(holdout_samples):
        sample_details.append({
            "filename": s.get("filename"),
            "phrase": s.get("phrase"),
            "category": s.get("category"),
            "condition": s.get("condition"),
            "target_label": int(s.get("target_label", 0)),
            "score": round(float(scores[i]), 4),
        })

    return {
        "model_path": onnx_path,
        "model_sha256": compute_file_sha256(onnx_path),
        "evaluation_mode": "streaming" if used_streaming else "static_embeddings",
        "thresholds": results_by_thresh,
        "sample_details": sample_details,
    }


def main() -> None:
    start_time = time.monotonic()
    logger.info("=== E.V. TASK 014F-11: CONTROLLED TARGETED HARD-NEGATIVE REFINEMENT ===")

    # Immutability pre-checks
    pre_active_sha = verify_active_model_hash()
    pre_cand_v1_sha = verify_candidate_v1_hash()
    logger.info("Active Baseline SHA256: %s (VERIFIED)", pre_active_sha)
    logger.info("Candidate V1 SHA256:    %s (VERIFIED)", pre_cand_v1_sha)

    # 1. Prepare Features for Dataset Variations
    from openwakeword.utils import AudioFeatures
    F = AudioFeatures(inference_framework="onnx", device="cpu", ncpu=4)

    logger.info("Generating dataset with enhanced human hard-negative representations...")
    meta_enh, clips_enh, labels_enh = generate_targeted_dataset(random_seed=42, hn_aug_level="enhanced")
    clips_arr_enh = np.vstack(clips_enh).astype(np.int16)
    features_enh = F.embed_clips(clips_arr_enh, batch_size=32)

    train_idx_enh = [i for i, m in enumerate(meta_enh) if m.split == "train"]
    val_idx_enh = [i for i, m in enumerate(meta_enh) if m.split == "val"]
    labels_enh_arr = np.array(labels_enh, dtype=np.float32)

    X_train_enh, y_train_enh = features_enh[train_idx_enh], labels_enh_arr[train_idx_enh]
    X_val_enh, y_val_enh = features_enh[val_idx_enh], labels_enh_arr[val_idx_enh]
    meta_train_enh = [meta_enh[i] for i in train_idx_enh]
    meta_val_enh = [meta_enh[i] for i in val_idx_enh]

    logger.info(
        "Dataset Partition (Enhanced): Train=%s (pos=%d, neg=%d), Val=%s (pos=%d, neg=%d)",
        X_train_enh.shape, int(np.sum(y_train_enh == 1)), int(np.sum(y_train_enh == 0)),
        X_val_enh.shape, int(np.sum(y_val_enh == 1)), int(np.sum(y_val_enh == 0)),
    )

    # Controlled Configurations to execute
    configurations = [
        {
            "name": "Config_1_BaselineReplication",
            "epochs": 45,
            "lr": 8e-4,
            "weight_decay": 1e-4,
            "loss_type": "weighted_bce",
            "neg_weight": 1.4,
            "hn_weight": 1.4,
            "seed": 42,
        },
        {
            "name": "Config_2_NegWeight_2.5",
            "epochs": 45,
            "lr": 8e-4,
            "weight_decay": 1e-4,
            "loss_type": "weighted_bce",
            "neg_weight": 2.5,
            "hn_weight": 2.5,
            "seed": 42,
        },
        {
            "name": "Config_3_TwoTier_HN3.5",
            "epochs": 45,
            "lr": 6e-4,
            "weight_decay": 1e-4,
            "loss_type": "two_tier_hn",
            "neg_weight": 1.5,
            "hn_weight": 3.5,
            "seed": 42,
        },
        {
            "name": "Config_4_TwoTier_HN5.0",
            "epochs": 45,
            "lr": 5e-4,
            "weight_decay": 1e-4,
            "loss_type": "two_tier_hn",
            "neg_weight": 1.8,
            "hn_weight": 5.0,
            "seed": 42,
        },
        {
            "name": "Config_5_FocalLoss_G1.5",
            "epochs": 45,
            "lr": 6e-4,
            "weight_decay": 1e-4,
            "loss_type": "focal_loss",
            "neg_weight": 1.8,
            "hn_weight": 4.0,
            "focal_gamma": 1.5,
            "seed": 42,
        },
    ]

    logger.info("==========================================================================================")
    logger.info("                    CONTROLLED DEVELOPMENT EXPERIMENT RUNS")
    logger.info("==========================================================================================")
    logger.info(
        "%-20s | %-7s | %-13s | %-13s | %-13s | %-7s | %-8s",
        "Config", "BestEp", "PosRec (Dev)", "HN_FPR (Dev)", "GN_FPR (Dev)", "F1", "DevScore"
    )
    logger.info("-" * 90)

    trained_models: Dict[str, OpenWakeWordNet] = {}
    experiment_results: List[Dict[str, Any]] = []

    for cfg in configurations:
        model, res = train_and_eval_configuration(
            config_name=cfg["name"],
            X_train=X_train_enh,
            y_train=y_train_enh,
            meta_train=meta_train_enh,
            X_val=X_val_enh,
            y_val=y_val_enh,
            meta_val=meta_val_enh,
            epochs=cfg["epochs"],
            lr=cfg["lr"],
            weight_decay=cfg["weight_decay"],
            loss_type=cfg["loss_type"],
            neg_weight=cfg["neg_weight"],
            hn_weight=cfg["hn_weight"],
            focal_gamma=cfg.get("focal_gamma", 1.5),
            seed=cfg["seed"],
        )
        trained_models[cfg["name"]] = model
        experiment_results.append(res)

    # Candidate Selection on Dev Set
    # Sort by dev_score (which balances positive recall and hard negative rejection)
    ranked_configs = sorted(experiment_results, key=lambda x: x["dev_score"], reverse=True)
    best_config_name = ranked_configs[0]["config_name"]
    best_model = trained_models[best_config_name]
    logger.info("=" * 90)
    logger.info("SELECTED OPTIMAL CANDIDATE BASED ON DEV METRICS: %s (DevScore: %.3f)", best_config_name, ranked_configs[0]["dev_score"])
    logger.info("=" * 90)

    # Export Candidate V2 to hey_ev_human_v3.onnx
    output_cand_v2 = export_model_to_onnx(best_model, NEW_CANDIDATE_OUTPUT_PATH)
    cand_v2_sha = compute_file_sha256(output_cand_v2)
    logger.info("Candidate V2 exported: %s (SHA256: %s)", output_cand_v2, cand_v2_sha)

    # OpenWakeWord runtime compatibility check
    logger.info("Checking runtime compatibility of Candidate V2...")
    provider = OpenWakeWordProvider(
        wakeword_models=[str(output_cand_v2)],
        model_dir=str(output_cand_v2.parent),
        target_phrase="Hey EV",
        threshold=0.50,
    )
    assert provider.is_available is True
    from core.voice_capture import create_silence_frame
    for _ in range(3):
        res = provider.process_frame(create_silence_frame())
    assert res is None
    provider.close()
    logger.info("OpenWakeWordProvider compatibility verification PASSED!")

    # Execute Locked Human Holdout Benchmark: 3-Way Comparison
    # (Baseline vs Candidate V1 vs Candidate V2)
    pipeline = WakeWordDatasetPipeline(random_seed=42)
    X_holdout, y_holdout, holdout_samples = pipeline.extract_locked_holdout_features()

    logger.info("Evaluating 3 Models on Locked Human Holdout across 7 Thresholds...")
    active_eval = evaluate_onnx_model_on_locked_holdout(
        DEFAULT_ACTIVE_MODEL, X_holdout, y_holdout, holdout_samples, human_dir=pipeline.human_dir
    )
    v1_eval = evaluate_onnx_model_on_locked_holdout(
        DEFAULT_CANDIDATE_V1_MODEL, X_holdout, y_holdout, holdout_samples, human_dir=pipeline.human_dir
    )
    v2_eval = evaluate_onnx_model_on_locked_holdout(
        str(output_cand_v2), X_holdout, y_holdout, holdout_samples, human_dir=pipeline.human_dir
    )

    thresholds = (0.30, 0.40, 0.50, 0.55, 0.60, 0.65, 0.70)
    logger.info("==========================================================================================================")
    logger.info("                       LOCKED HUMAN HOLDOUT 3-WAY BENCHMARK COMPARISON")
    logger.info("==========================================================================================================")
    logger.info(
        "%-6s | %-12s | %-17s | %-17s | %-13s | %-6s | %-6s",
        "Thresh", "Model", "Human Recall", "HardNeg FP(/12)", "GenNeg FP(/4)", "Acc", "F1"
    )
    logger.info("-" * 105)

    for t in thresholds:
        ts = str(t)
        a_m = active_eval["thresholds"][ts]
        v1_m = v1_eval["thresholds"][ts]
        v2_m = v2_eval["thresholds"][ts]

        logger.info(
            "%-6.2f | %-12s | %2d/%-2d (%5.1f%%)    | %2d/%-2d (%5.1f%%)     | %2d/%-2d (%5.1f%%)  | %5.3f  | %5.3f",
            t, "Active Base",
            a_m["positive_recall_count"], a_m["positive_total"], a_m["recall"] * 100,
            a_m["hard_neg_fp_count"], a_m["hard_neg_total"], (a_m["hard_neg_fp_count"] / a_m["hard_neg_total"]) * 100,
            a_m["gen_neg_fp_count"], a_m["gen_neg_total"], (a_m["gen_neg_fp_count"] / a_m["gen_neg_total"]) * 100,
            a_m["accuracy"], a_m["f1"]
        )
        logger.info(
            "%-6.2f | %-12s | %2d/%-2d (%5.1f%%)    | %2d/%-2d (%5.1f%%)     | %2d/%-2d (%5.1f%%)  | %5.3f  | %5.3f",
            t, "Candidate V1",
            v1_m["positive_recall_count"], v1_m["positive_total"], v1_m["recall"] * 100,
            v1_m["hard_neg_fp_count"], v1_m["hard_neg_total"], (v1_m["hard_neg_fp_count"] / v1_m["hard_neg_total"]) * 100,
            v1_m["gen_neg_fp_count"], v1_m["gen_neg_total"], (v1_m["gen_neg_fp_count"] / v1_m["gen_neg_total"]) * 100,
            v1_m["accuracy"], v1_m["f1"]
        )
        logger.info(
            "%-6.2f | %-12s | %2d/%-2d (%5.1f%%)    | %2d/%-2d (%5.1f%%)     | %2d/%-2d (%5.1f%%)  | %5.3f  | %5.3f",
            t, "Candidate V2",
            v2_m["positive_recall_count"], v2_m["positive_total"], v2_m["recall"] * 100,
            v2_m["hard_neg_fp_count"], v2_m["hard_neg_total"], (v2_m["hard_neg_fp_count"] / v2_m["hard_neg_total"]) * 100,
            v2_m["gen_neg_fp_count"], v2_m["gen_neg_total"], (v2_m["gen_neg_fp_count"] / v2_m["gen_neg_total"]) * 100,
            v2_m["accuracy"], v2_m["f1"]
        )
        logger.info("-" * 105)

    # Immutability post-checks
    post_active_sha = verify_active_model_hash()
    post_cand_v1_sha = verify_candidate_v1_hash()
    assert post_active_sha == pre_active_sha == EXPECTED_ACTIVE_SHA
    assert post_cand_v1_sha == pre_cand_v1_sha == EXPECTED_CANDIDATE_V1_SHA
    logger.info("Immutability verified: hey_ev.onnx and hey_ev_human_v2.onnx remain 100%% byte-for-byte identical.")

    # Save complete reproducibility record
    reproducibility_record = {
        "task": "TASK_014F_11",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "baseline_model": {
            "path": DEFAULT_ACTIVE_MODEL,
            "sha256": post_active_sha,
        },
        "candidate_v1_model": {
            "path": DEFAULT_CANDIDATE_V1_MODEL,
            "sha256": post_cand_v1_sha,
        },
        "candidate_v2_model": {
            "path": str(output_cand_v2),
            "sha256": cand_v2_sha,
            "selected_config": best_config_name,
            "architecture": "OpenWakeWordNet(16,96 -> 128 -> FCNBlock(128) -> Sigmoid)",
        },
        "holdout_manifest": {
            "path": str(pipeline.holdout_manifest_path),
            "sha256": compute_file_sha256(pipeline.holdout_manifest_path),
            "samples_count": len(holdout_samples),
        },
        "dataset_summary": {
            "train_clips": len(X_train_enh),
            "val_clips": len(X_val_enh),
            "human_pos_files": len(set(m.source_file for m in meta_enh if m.is_human and m.label == 1)),
            "human_neg_files": len(set(m.source_file for m in meta_enh if m.is_human and m.label == 0)),
        },
        "experimental_configurations": experiment_results,
        "selected_configuration": ranked_configs[0],
        "locked_holdout_3way_comparison": {
            "active_baseline": active_eval,
            "candidate_v1": v1_eval,
            "candidate_v2": v2_eval,
        },
    }

    rep_path = Path(CANDIDATES_DIR) / "reproducibility_record_014f11.json"
    with open(rep_path, "w", encoding="utf-8") as rf:
        json.dump(reproducibility_record, rf, indent=2)
    logger.info("Reproducibility record saved to: %s", rep_path)

    elapsed = time.monotonic() - start_time
    logger.info("=== TASK 014F-11 COMPLETE in %.2f seconds ===", elapsed)


if __name__ == "__main__":
    main()
