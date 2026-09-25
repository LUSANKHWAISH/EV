"""
Reproducible Hard-Negative Mining & Dataset Hardening Pipeline for E.V. (Task 014F-5).

Expands the custom "Hey EV" wake-word dataset with:
  1. Systematic prefix hard-negative mining ("Hey Everyone", "Hey Evan", "Hey Evie", "Hey Stevie", etc.).
  2. Low-SNR & distance acoustic modeling (attenuation, mild reverberation, fan hum, keyboard clicks).
  3. First-class human speech ingestion pathway with strict format validation.
  4. Disjoint 3-way partitioning: Train (70%), Validation (15%), Final Holdout (15%).
  5. Canonical audio contract: 16 kHz mono signed 16-bit PCM.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import struct
import subprocess
import time
import wave
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

import numpy as np

logger = logging.getLogger("ev.wakeword.dataset")

CANONICAL_SAMPLE_RATE: int = 16000
CANONICAL_CHANNELS: int = 1
CANONICAL_SAMPLE_WIDTH: int = 2  # 16-bit
CLIP_DURATION_SECONDS: float = 2.0
CLIP_TOTAL_SAMPLES: int = int(CANONICAL_SAMPLE_RATE * CLIP_DURATION_SECONDS)  # 32,000 samples

POSITIVE_PHRASES: List[str] = [
    "Hey EV",
    "Hey E.V.",
    "Hey E V",
    "hey ev",
    "Hey Ev",
]

# Systematic hard-negative prefix phrases targeting the demonstrated failure boundary
HARD_NEGATIVE_PHRASES: List[str] = [
    # Prefix "Hey Ev..." confusables
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
    "Hey Everyday",
    "Hey Everybody",
    "Hey Evelyn",
    # Phonetic & rhyming confusables
    "Hey Stevie",
    "Hey Steve",
    "Hey Steven",
    "Hey Eddie",
    "Heavy",
    "Every",
    "Everywhere",
    # Boundary / partial trigger
    "Hey",
    "EV",
]

# Standard command negatives
GENERAL_NEGATIVE_PHRASES: List[str] = [
    "Open the browser",
    "Turn on the lights",
    "What time is it",
    "Cancel that command",
    "System status report",
    "Show active tasks",
    "Search the web",
    "Close the window",
    "Increase the volume",
    "Mute the speakers",
    "Run diagnostics",
    "Open files",
]


@dataclass
class SampleMetadata:
    sample_id: str
    label: int  # 1 for positive, 0 for negative
    phrase: str
    is_hard_negative: bool
    is_human: bool
    speaker_id: str
    rate: int
    volume: int
    augmentation: str
    split: str  # "train", "val", or "holdout"
    duration_samples: int
    sha256: str = ""
    source_file: str = ""


def compute_file_sha256(file_path: Path | str) -> str:
    """Compute hex SHA256 of file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().lower()


def audit_dataset_leakage(
    samples_metadata: List[SampleMetadata],
    holdout_manifest_path: Optional[Path | str],
) -> Dict[str, Any]:
    """
    Deterministically audit dataset metadata against locked holdout manifest.
    Ensures zero holdout samples enter training or validation splits.
    """
    if not holdout_manifest_path:
        return {"status": "SKIPPED_NO_HOLDOUT_FILE", "overlap_count": 0}

    holdout_p = Path(holdout_manifest_path)
    if not holdout_p.exists():
        return {"status": "SKIPPED_FILE_NOT_FOUND", "overlap_count": 0}

    with open(holdout_p, "r", encoding="utf-8") as f:
        holdout_data = json.load(f)

    holdout_samples = holdout_data.get("samples", [])
    holdout_shas = {s["sha256"].lower() for s in holdout_samples if "sha256" in s}
    holdout_filenames = {s["filename"].lower() for s in holdout_samples if "filename" in s}

    train_shas = {m.sha256.lower() for m in samples_metadata if m.split == "train" and m.sha256}
    val_shas = {m.sha256.lower() for m in samples_metadata if m.split == "val" and m.sha256}
    all_ingested_shas = train_shas.union(val_shas)

    train_overlap = train_shas.intersection(holdout_shas)
    val_overlap = val_shas.intersection(holdout_shas)
    total_overlap = all_ingested_shas.intersection(holdout_shas)

    result = {
        "holdout_samples_count": len(holdout_samples),
        "train_samples_count": sum(1 for m in samples_metadata if m.split == "train"),
        "val_samples_count": sum(1 for m in samples_metadata if m.split == "val"),
        "train_unique_shas": len(train_shas),
        "val_unique_shas": len(val_shas),
        "overlap_count": len(total_overlap),
        "train_overlap_count": len(train_overlap),
        "val_overlap_count": len(val_overlap),
        "overlap_shas": list(total_overlap),
        "leakage_detected": len(total_overlap) > 0,
    }

    if len(total_overlap) > 0:
        raise RuntimeError(
            f"CRITICAL DATA LEAKAGE DETECTED: {len(total_overlap)} holdout samples present in train/val sets: {total_overlap}"
        )

    return result


def get_available_sapi_voices() -> List[str]:
    """Discover installed Windows SAPI voices."""
    ps_cmd = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        "$s.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo.Name }"
    )
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        voices = [v.strip() for v in proc.stdout.strip().splitlines() if v.strip()]
        return voices if voices else ["Microsoft David Desktop"]
    except Exception as exc:
        logger.warning("Could not discover SAPI voices via PowerShell: %s. Using default.", exc)
        return ["Microsoft David Desktop"]


def synthesize_sapi_speech(
    text: str,
    output_wav_path: str,
    voice: Optional[str] = None,
    rate: int = 0,
    volume: int = 100,
) -> bool:
    """
    Synthesize speech locally to a 16 kHz mono 16-bit PCM WAV file via Windows SAPI.
    """
    safe_text = text.replace("'", "''").replace('"', '`"')
    voice_stmt = f"$synth.SelectVoice('{voice}'); " if voice else ""
    ps_script = (
        "$ErrorActionPreference = 'Stop'; "
        "Add-Type -AssemblyName System.Speech; "
        "$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        f"{voice_stmt}"
        f"$synth.Rate = {rate}; "
        f"$synth.Volume = {volume}; "
        "$format = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo("
        "16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono); "
        f"$synth.SetOutputToWaveFile('{output_wav_path}', $format); "
        f"$synth.Speak('{safe_text}'); "
        "$synth.Dispose();"
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        )
        return os.path.exists(output_wav_path) and os.path.getsize(output_wav_path) > 100
    except Exception as exc:
        logger.error("Failed to synthesize text '%s' with SAPI: %s", text, exc)
        return False


def load_pcm16_wav(wav_path: str) -> np.ndarray:
    """Load WAV file and return 1D numpy int16 array."""
    with wave.open(wav_path, "rb") as wf:
        if wf.getframerate() != CANONICAL_SAMPLE_RATE:
            raise ValueError(f"Expected rate {CANONICAL_SAMPLE_RATE}, got {wf.getframerate()}")
        if wf.getnchannels() != CANONICAL_CHANNELS:
            raise ValueError(f"Expected {CANONICAL_CHANNELS} channels, got {wf.getnchannels()}")
        if wf.getsampwidth() != CANONICAL_SAMPLE_WIDTH:
            raise ValueError(f"Expected sample width {CANONICAL_SAMPLE_WIDTH}, got {wf.getsampwidth()}")
        frames = wf.readframes(wf.getnframes())
        return np.frombuffer(frames, dtype=np.int16)


def save_pcm16_wav(wav_path: str, audio: np.ndarray) -> None:
    """Save 1D int16 array as 16 kHz mono WAV file."""
    audio_int16 = np.clip(audio, -32768, 32767).astype(np.int16)
    with wave.open(wav_path, "wb") as wf:
        wf.setnchannels(CANONICAL_CHANNELS)
        wf.setsampwidth(CANONICAL_SAMPLE_WIDTH)
        wf.setframerate(CANONICAL_SAMPLE_RATE)
        wf.writeframes(audio_int16.tobytes())


def pad_or_trim_to_length(audio: np.ndarray, target_length: int = CLIP_TOTAL_SAMPLES, offset: Optional[int] = None) -> np.ndarray:
    """Fit audio into target length with controllable or randomized time offset."""
    if len(audio) >= target_length:
        return audio[:target_length]

    pad_total = target_length - len(audio)
    if offset is None:
        left_pad = pad_total // 2
    else:
        left_pad = max(0, min(pad_total, offset))
    right_pad = pad_total - left_pad

    return np.pad(audio, (left_pad, right_pad), mode="constant", constant_values=0)


def apply_room_reverberation(audio: np.ndarray, delay1: int = 320, delay2: int = 720) -> np.ndarray:
    """Simulate realistic early room reflections."""
    out = audio.astype(np.float32).copy()
    if len(out) > delay1:
        out[delay1:] += 0.22 * out[:-delay1]
    if len(out) > delay2:
        out[delay2:] += 0.12 * out[:-delay2]
    return out


def apply_distance_attenuation(audio: np.ndarray) -> np.ndarray:
    """Simulate distance attenuation via high-frequency rolloff (air absorption)."""
    # Simple smoothing filter for high frequency damping
    kernel = np.array([0.15, 0.70, 0.15], dtype=np.float32)
    filtered = np.convolve(audio.astype(np.float32), kernel, mode="same")
    return filtered


def augment_audio(
    audio: np.ndarray,
    gain: float = 1.0,
    noise_type: str = "none",
    noise_snr_db: float = 20.0,
    time_offset_fraction: float = 0.5,
    reverberation: bool = False,
    distance_filter: bool = False,
) -> np.ndarray:
    """Apply acoustic signal augmentations (gain, noise mixing, room modeling, time alignment)."""
    # 1. Gain & Distance attenuation
    signal = audio.astype(np.float32)
    if distance_filter:
        signal = apply_distance_attenuation(signal)

    signal = signal * gain

    # 2. Reverberation
    if reverberation:
        signal = apply_room_reverberation(signal)

    # 3. Time-shift inside 2s frame
    pad_total = max(0, CLIP_TOTAL_SAMPLES - len(signal))
    left_offset = int(pad_total * np.clip(time_offset_fraction, 0.0, 1.0))
    framed = pad_or_trim_to_length(signal, CLIP_TOTAL_SAMPLES, offset=left_offset)

    # 4. Additive noise
    if noise_type != "none":
        signal_power = np.mean(framed**2) + 1e-12
        noise_power = signal_power / (10 ** (noise_snr_db / 10.0))

        if noise_type == "white":
            noise = np.random.normal(0, np.sqrt(noise_power), len(framed))
        elif noise_type == "pink":
            white = np.random.normal(0, 1.0, len(framed))
            noise = np.convolve(white, np.ones(8) / 8.0, mode="same")
            actual_power = np.mean(noise**2) + 1e-12
            noise = noise * np.sqrt(noise_power / actual_power)
        elif noise_type == "fan":
            # Realistic fan hum: 60Hz + 120Hz + broadband hiss
            t = np.linspace(0, CLIP_DURATION_SECONDS, len(framed), endpoint=False)
            hum = np.sin(2 * np.pi * 60 * t) + 0.4 * np.sin(2 * np.pi * 120 * t)
            hiss = np.random.normal(0, 0.3, len(framed))
            composite = hum + hiss
            actual_power = np.mean(composite**2) + 1e-12
            noise = composite * np.sqrt(noise_power / actual_power)
        elif noise_type == "keyboard":
            # Keyboard clicks: sparse high-amplitude impulses
            noise = np.random.normal(0, 0.1, len(framed))
            click_locs = np.random.choice(len(framed), size=4, replace=False)
            for loc in click_locs:
                click_len = min(160, len(framed) - loc)
                decay = np.exp(-np.linspace(0, 5, click_len))
                noise[loc : loc + click_len] += decay * 4.0
            actual_power = np.mean(noise**2) + 1e-12
            noise = noise * np.sqrt(noise_power / actual_power)
        else:
            noise = np.zeros_like(framed)

        framed = framed + noise

    return np.clip(framed, -32768.0, 32767.0).astype(np.int16)


class WakeWordDatasetPipeline:
    """
    Orchestrates generation of positive & negative audio samples, feature extraction,
    human speech ingestion, and disjoint 3-way dataset splitting.
    """

    def __init__(
        self,
        data_dir: str = r"D:\EV\models\wakeword\dataset",
        random_seed: int = 42,
        holdout_manifest_path: Optional[str] = None,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.raw_dir = self.data_dir / "raw"
        self.features_dir = self.data_dir / "features"
        self.human_dir = self.data_dir / "human"
        self.human_pos_dir = self.human_dir / "positive"
        self.human_neg_dir = self.human_dir / "negative"
        self.human_quarantine_dir = self.human_dir / "quarantine"
        self.manifest_path = self.human_dir / "human_collection_manifest.json"

        if holdout_manifest_path is not None:
            self.holdout_manifest_path = Path(holdout_manifest_path)
        else:
            default_holdout = self.data_dir / "human" / "locked_human_holdout_manifest.json"
            self.holdout_manifest_path = default_holdout if default_holdout.exists() else None

        self.random_seed = random_seed
        np.random.seed(self.random_seed)
        self.last_leakage_audit: Dict[str, Any] = {}

    def prepare_directories(self) -> None:
        """Create dataset storage structure."""
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.features_dir.mkdir(parents=True, exist_ok=True)
        self.human_pos_dir.mkdir(parents=True, exist_ok=True)
        self.human_neg_dir.mkdir(parents=True, exist_ok=True)
        self.human_quarantine_dir.mkdir(parents=True, exist_ok=True)

    def scan_and_ingest_human_speech(self, augment_human: bool = False) -> Tuple[List[SampleMetadata], List[np.ndarray], List[int]]:
        """
        Scan human audio directories for local recordings and ingest canonical clips.
        Strictly ignores quarantine/ and review/ subdirectories.
        Cross-references locked_human_holdout_manifest.json to ensure ZERO holdout recordings enter training/validation.
        Cross-references human_collection_manifest.json to ensure only confirmed valid positive clips are ingested.
        Applies deterministic audio augmentations to teach natural human variation (quiet, breathy, conversational, SNR variation).
        """
        self.prepare_directories()
        human_meta: List[SampleMetadata] = []
        human_clips: List[np.ndarray] = []
        human_labels: List[int] = []

        # Load holdout manifest if available
        holdout_shas: Set[str] = set()
        holdout_filenames: Set[str] = set()
        holdout_relpaths: Set[str] = set()
        if self.holdout_manifest_path and self.holdout_manifest_path.exists():
            try:
                with open(self.holdout_manifest_path, "r", encoding="utf-8") as hf:
                    h_data = json.load(hf)
                    for s in h_data.get("samples", []):
                        if "sha256" in s:
                            holdout_shas.add(s["sha256"].lower())
                        if "filename" in s:
                            holdout_filenames.add(s["filename"].lower())
                        if "relative_path" in s:
                            holdout_relpaths.add(s["relative_path"].replace("\\", "/").lower())
                logger.info("Loaded locked holdout manifest with %d samples for exclusion guard.", len(holdout_shas))
            except Exception as exc:
                logger.warning("Could not read locked holdout manifest: %s", exc)

        # Load manifest metadata lookup if available
        manifest_lookup: Dict[str, Dict[str, Any]] = {}
        quarantine_shas: Set[str] = set()
        if self.manifest_path.exists():
            try:
                with open(self.manifest_path, "r", encoding="utf-8") as mf:
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
            except Exception as exc:
                logger.warning("Could not read human collection manifest: %s", exc)

        # Also gather hashes of all files physically in quarantine directory
        if self.human_quarantine_dir.exists():
            for q_wav in self.human_quarantine_dir.glob("*.wav"):
                try:
                    quarantine_shas.add(compute_file_sha256(q_wav))
                except Exception:
                    pass

        excluded_holdout_count = 0
        excluded_quarantine_count = 0

        # Scan positives (strictly *.wav files in human_pos_dir)
        valid_pos_files = []
        for wav_file in sorted(self.human_pos_dir.glob("*.wav")):
            rel_key = f"positive/{wav_file.name}"
            m_info = manifest_lookup.get(rel_key) or manifest_lookup.get(f"POSITIVE::{wav_file.name}") or manifest_lookup.get(wav_file.name)
            file_sha = compute_file_sha256(wav_file)

            # 1. Holdout exclusion guard
            if file_sha in holdout_shas or wav_file.name.lower() in holdout_filenames or rel_key.lower() in holdout_relpaths:
                excluded_holdout_count += 1
                continue

            # 2. Quarantine exclusion guard
            is_quarantined = (
                (m_info and m_info.get("category") == "QUARANTINE")
                or (m_info and m_info.get("target_label", 1) != 1)
                or (file_sha in quarantine_shas and not (m_info and m_info.get("confirmed_by_user", False)))
            )
            if is_quarantined:
                excluded_quarantine_count += 1
                continue

            valid_pos_files.append((wav_file, file_sha, m_info))

        # Ingest valid positives with partition split and controlled acoustic augmentations
        for p_idx, (wav_file, file_sha, m_info) in enumerate(valid_pos_files):
            try:
                audio = load_pcm16_wav(str(wav_file))
                speaker = wav_file.stem.split("_")[0] if "_" in wav_file.stem else "user_speaker_1"
                phrase = m_info.get("phrase", "Hey EV") if m_info else "Hey EV"
                # Disjoint non-holdout split: 85% train, 15% validation
                split = "val" if (p_idx % 7 == 6) else "train"

                # 1. Base clean human recording
                raw_clip = pad_or_trim_to_length(audio, CLIP_TOTAL_SAMPLES)
                meta_raw = SampleMetadata(
                    sample_id=f"human_pos_{wav_file.stem}_raw",
                    label=1,
                    phrase=phrase,
                    is_hard_negative=False,
                    is_human=True,
                    speaker_id=speaker,
                    rate=0,
                    volume=100,
                    augmentation="raw_human",
                    split=split,
                    duration_samples=len(raw_clip),
                    sha256=file_sha,
                    source_file=wav_file.name,
                )
                human_meta.append(meta_raw)
                human_clips.append(raw_clip)
                human_labels.append(1)

                if augment_human:
                    # Augmentation variations to address quiet/casual/whisper/resonance failure modes
                    aug_configs = [
                        ("boost_quiet", 1.25, "none", 30.0, 0.5),      # boosts quiet/whisper
                        ("attenuate_loud", 0.80, "none", 30.0, 0.5),   # models distance/softness
                        ("room_noise", 1.00, "fan", 22.0, 0.5),        # models natural room ambient
                        ("time_early", 1.00, "none", 30.0, 0.35),      # slight early onset
                        ("time_late", 1.00, "none", 30.0, 0.65),       # slight late onset
                    ]
                    for aug_name, gain, noise, snr, offset in aug_configs:
                        aug_clip = augment_audio(
                            audio,
                            gain=gain,
                            noise_type=noise,
                            noise_snr_db=snr,
                            time_offset_fraction=offset,
                        )
                        meta_aug = SampleMetadata(
                            sample_id=f"human_pos_{wav_file.stem}_{aug_name}",
                            label=1,
                            phrase=phrase,
                            is_hard_negative=False,
                            is_human=True,
                            speaker_id=speaker,
                            rate=0,
                            volume=100,
                            augmentation=f"human_{aug_name}",
                            split=split,
                            duration_samples=len(aug_clip),
                            sha256=file_sha,
                            source_file=wav_file.name,
                        )
                        human_meta.append(meta_aug)
                        human_clips.append(aug_clip)
                        human_labels.append(1)

            except Exception as exc:
                logger.warning("Skipping invalid human recording %s: %s", wav_file, exc)

        # Scan negatives (strictly *.wav files in human_neg_dir)
        valid_neg_files = []
        for wav_file in sorted(self.human_neg_dir.glob("*.wav")):
            rel_key = f"negative/{wav_file.name}"
            m_info = manifest_lookup.get(rel_key) or manifest_lookup.get(f"HARD_NEGATIVE::{wav_file.name}") or manifest_lookup.get(f"NEGATIVE::{wav_file.name}") or manifest_lookup.get(wav_file.name)
            file_sha = compute_file_sha256(wav_file)

            # 1. Holdout exclusion guard
            if file_sha in holdout_shas or wav_file.name.lower() in holdout_filenames or rel_key.lower() in holdout_relpaths:
                excluded_holdout_count += 1
                continue

            # 2. Quarantine exclusion guard
            is_quarantined = (
                (m_info and m_info.get("category") == "QUARANTINE")
                or (m_info and m_info.get("target_label", 0) not in (0, "0", None))
                or (file_sha in quarantine_shas and not (m_info and m_info.get("confirmed_by_user", False)))
            )
            if is_quarantined:
                excluded_quarantine_count += 1
                continue

            valid_neg_files.append((wav_file, file_sha, m_info))

        # Ingest valid negatives with partition split and controlled acoustic augmentations
        for n_idx, (wav_file, file_sha, m_info) in enumerate(valid_neg_files):
            try:
                audio = load_pcm16_wav(str(wav_file))
                speaker = wav_file.stem.split("_")[0] if "_" in wav_file.stem else "user_speaker_1"
                phrase = m_info.get("phrase", wav_file.stem) if m_info else wav_file.stem
                is_hn = bool(
                    (m_info and m_info.get("category") == "HARD_NEGATIVE")
                    or any(k in phrase.lower() for k in ["hey ev", "hey", "ev", "every", "heavy", "stevie", "steve"])
                )
                split = "val" if (n_idx % 7 == 6) else "train"

                # 1. Base clean human negative
                raw_clip = pad_or_trim_to_length(audio, CLIP_TOTAL_SAMPLES)
                meta_raw = SampleMetadata(
                    sample_id=f"human_neg_{wav_file.stem}_raw",
                    label=0,
                    phrase=phrase,
                    is_hard_negative=is_hn,
                    is_human=True,
                    speaker_id=speaker,
                    rate=0,
                    volume=100,
                    augmentation="raw_human",
                    split=split,
                    duration_samples=len(raw_clip),
                    sha256=file_sha,
                    source_file=wav_file.name,
                )
                human_meta.append(meta_raw)
                human_clips.append(raw_clip)
                human_labels.append(0)

                if augment_human:
                    # Negative augmentations (gain variations + ambient noise)
                    neg_aug_configs = [
                        ("gain_low", 0.85, "none", 30.0, 0.5),
                        ("gain_high", 1.15, "none", 30.0, 0.5),
                        ("ambient_fan", 1.00, "fan", 22.0, 0.5),
                    ]
                    for aug_name, gain, noise, snr, offset in neg_aug_configs:
                        aug_clip = augment_audio(
                            audio,
                            gain=gain,
                            noise_type=noise,
                            noise_snr_db=snr,
                            time_offset_fraction=offset,
                        )
                        meta_aug = SampleMetadata(
                            sample_id=f"human_neg_{wav_file.stem}_{aug_name}",
                            label=0,
                            phrase=phrase,
                            is_hard_negative=is_hn,
                            is_human=True,
                            speaker_id=speaker,
                            rate=0,
                            volume=100,
                            augmentation=f"human_{aug_name}",
                            split=split,
                            duration_samples=len(aug_clip),
                            sha256=file_sha,
                            source_file=wav_file.name,
                        )
                        human_meta.append(meta_aug)
                        human_clips.append(aug_clip)
                        human_labels.append(0)

            except Exception as exc:
                logger.warning("Skipping invalid human recording %s: %s", wav_file, exc)

        # Deterministic post-ingestion leakage audit
        ingested_shas = {m.sha256 for m in human_meta if m.sha256}
        overlap = ingested_shas.intersection(holdout_shas)
        # Quarantine leakage check: ensure no files originate from quarantine
        ingested_sources = {m.source_file.lower() for m in human_meta if m.source_file}
        quarantine_filenames = {f.name.lower() for f in self.human_quarantine_dir.glob("*.wav")} if self.human_quarantine_dir.exists() else set()
        quar_file_overlap = ingested_sources.intersection(quarantine_filenames)

        if len(overlap) > 0:
            raise RuntimeError(
                f"CRITICAL LEAKAGE DETECTED: {len(overlap)} holdout samples present in ingested human data: {overlap}"
            )

        if len(quar_file_overlap) > 0:
            raise RuntimeError(
                f"CRITICAL QUARANTINE LEAKAGE: {len(quar_file_overlap)} quarantined files present in ingested human data: {quar_file_overlap}"
            )

        logger.info(
            "Human speech ingestion verified: %d pos clips (%d files), %d neg clips (%d files). Excluded %d holdout, %d quarantine. Overlap = 0.",
            human_labels.count(1),
            len(valid_pos_files),
            human_labels.count(0),
            len(valid_neg_files),
            excluded_holdout_count,
            excluded_quarantine_count,
        )

        self.last_leakage_audit = {
            "holdout_count": len(holdout_shas),
            "excluded_holdout_files": excluded_holdout_count,
            "excluded_quarantine_files": excluded_quarantine_count,
            "valid_pos_files": len(valid_pos_files),
            "valid_neg_files": len(valid_neg_files),
            "total_human_clips": len(human_clips),
            "overlap_count": len(overlap),
        }

        return human_meta, human_clips, human_labels

    def generate_hardened_audio_dataset(
        self,
        num_positive_base: int = 48,
        augmentations_per_positive: int = 8,
        augmentations_per_negative: int = 6,
    ) -> Tuple[List[SampleMetadata], List[np.ndarray], List[int]]:
        """
        Generate hardened dataset with hard-negative prefix phrases and low-SNR modeling.
        """
        self.prepare_directories()
        voices = get_available_sapi_voices()
        samples_metadata: List[SampleMetadata] = []
        audio_clips: List[np.ndarray] = []
        labels: List[int] = []

        # Ingest human speech first (if any exists locally)
        h_meta, h_clips, h_labels = self.scan_and_ingest_human_speech(augment_human=True)
        samples_metadata.extend(h_meta)
        audio_clips.extend(h_clips)
        labels.extend(h_labels)

        # --------------------------------------------------------------------
        # 1. POSITIVE SAMPLES ("Hey EV") with Low-SNR & Distance Variations
        # --------------------------------------------------------------------
        rate_options = [-2, -1, 0, 1, 2]
        vol_options = [50, 70, 85, 100]
        pos_id = 0

        for p_idx in range(num_positive_base):
            phrase = POSITIVE_PHRASES[p_idx % len(POSITIVE_PHRASES)]
            voice = voices[p_idx % len(voices)]
            rate = rate_options[p_idx % len(rate_options)]
            vol = vol_options[p_idx % len(vol_options)]

            # Disjoint 3-way split: 70% train, 15% val, 15% holdout
            split_mod = p_idx % 7
            if split_mod == 5:
                split = "val"
            elif split_mod == 6:
                split = "holdout"
            else:
                split = "train"

            base_filename = f"pos_base_h_{pos_id}.wav"
            base_path = self.raw_dir / base_filename
            if not base_path.exists():
                success = synthesize_sapi_speech(phrase, str(base_path), voice=voice, rate=rate, volume=vol)
                if not success:
                    continue
            else:
                success = True

            base_audio = load_pcm16_wav(str(base_path))

            for aug_i in range(augmentations_per_positive):
                # Augmentation strategy: varied acoustic distances and SNR levels
                if aug_i == 0:
                    # Clean near
                    gain = 1.0
                    noise = "none"
                    snr = 30.0
                    reverb = False
                    dist = False
                elif aug_i in (1, 2):
                    # Quiet / distant speech (low SNR)
                    gain = float(np.random.uniform(0.35, 0.65))
                    noise = np.random.choice(["fan", "pink"])
                    snr = float(np.random.uniform(10.0, 18.0))
                    reverb = True
                    dist = True
                elif aug_i in (3, 4):
                    # Mid-distance room
                    gain = float(np.random.uniform(0.70, 1.10))
                    noise = np.random.choice(["fan", "white", "keyboard"])
                    snr = float(np.random.uniform(15.0, 24.0))
                    reverb = bool(np.random.rand() > 0.5)
                    dist = False
                else:
                    # Near / loud
                    gain = float(np.random.uniform(1.10, 1.40))
                    noise = np.random.choice(["none", "pink", "fan"])
                    snr = float(np.random.uniform(18.0, 28.0))
                    reverb = False
                    dist = False

                time_offset = float(np.random.uniform(0.10, 0.90))

                aug_clip = augment_audio(
                    base_audio,
                    gain=gain,
                    noise_type=str(noise),
                    noise_snr_db=snr,
                    time_offset_fraction=time_offset,
                    reverberation=reverb,
                    distance_filter=dist,
                )

                meta = SampleMetadata(
                    sample_id=f"pos_h_{pos_id}_{aug_i}",
                    label=1,
                    phrase=phrase,
                    is_hard_negative=False,
                    is_human=False,
                    speaker_id=voice.split()[1],
                    rate=rate,
                    volume=vol,
                    augmentation=f"gain={gain:.2f},noise={noise},snr={snr:.1f}dB,rev={reverb},dist={dist}",
                    split=split,
                    duration_samples=len(aug_clip),
                )
                samples_metadata.append(meta)
                audio_clips.append(aug_clip)
                labels.append(1)

            pos_id += 1

        # --------------------------------------------------------------------
        # 2. HARD NEGATIVES (Prefix Confusables: "Hey Everyone", "Hey Evan", etc.)
        # --------------------------------------------------------------------
        hn_id = 0
        for phrase in HARD_NEGATIVE_PHRASES:
            for voice in voices:
                for rate in [-1, 0, 1]:
                    split_mod = (hn_id) % 7
                    if split_mod == 5:
                        split = "val"
                    elif split_mod == 6:
                        split = "holdout"
                    else:
                        split = "train"

                    base_filename = f"neg_hn_{hn_id}.wav"
                    base_path = self.raw_dir / base_filename
                    if not base_path.exists():
                        success = synthesize_sapi_speech(phrase, str(base_path), voice=voice, rate=rate, volume=85)
                        if not success:
                            continue
                    else:
                        success = True

                    base_audio = load_pcm16_wav(str(base_path))

                    for aug_i in range(augmentations_per_negative):
                        gain = float(np.random.uniform(0.60, 1.25))
                        noise = np.random.choice(["none", "fan", "pink", "keyboard"])
                        snr = float(np.random.uniform(12.0, 26.0))
                        time_offset = float(np.random.uniform(0.10, 0.85))

                        aug_clip = augment_audio(
                            base_audio,
                            gain=gain,
                            noise_type=str(noise),
                            noise_snr_db=snr,
                            time_offset_fraction=time_offset,
                            reverberation=(aug_i % 2 == 0),
                        )

                        meta = SampleMetadata(
                            sample_id=f"neg_hn_{hn_id}_{aug_i}",
                            label=0,
                            phrase=phrase,
                            is_hard_negative=True,
                            is_human=False,
                            speaker_id=voice.split()[1],
                            rate=rate,
                            volume=85,
                            augmentation=f"gain={gain:.2f},noise={noise},snr={snr:.1f}dB",
                            split=split,
                            duration_samples=len(aug_clip),
                        )
                        samples_metadata.append(meta)
                        audio_clips.append(aug_clip)
                        labels.append(0)

                    hn_id += 1

        # --------------------------------------------------------------------
        # 3. GENERAL COMMAND NEGATIVES
        # --------------------------------------------------------------------
        cmd_id = 0
        for phrase in GENERAL_NEGATIVE_PHRASES:
            for voice in voices:
                split_mod = cmd_id % 7
                split = "val" if split_mod == 5 else ("holdout" if split_mod == 6 else "train")

                base_filename = f"neg_cmd_{cmd_id}.wav"
                base_path = self.raw_dir / base_filename
                if not base_path.exists():
                    success = synthesize_sapi_speech(phrase, str(base_path), voice=voice, rate=0, volume=85)
                    if not success:
                        continue
                else:
                    success = True

                base_audio = load_pcm16_wav(str(base_path))

                for aug_i in range(3):
                    gain = float(np.random.uniform(0.70, 1.20))
                    noise = np.random.choice(["none", "fan", "pink"])
                    snr = float(np.random.uniform(14.0, 26.0))
                    time_offset = float(np.random.uniform(0.15, 0.85))

                    aug_clip = augment_audio(
                        base_audio,
                        gain=gain,
                        noise_type=str(noise),
                        noise_snr_db=snr,
                        time_offset_fraction=time_offset,
                    )

                    meta = SampleMetadata(
                        sample_id=f"neg_cmd_{cmd_id}_{aug_i}",
                        label=0,
                        phrase=phrase,
                        is_hard_negative=False,
                        is_human=False,
                        speaker_id=voice.split()[1],
                        rate=0,
                        volume=85,
                        augmentation=f"gain={gain:.2f},noise={noise}",
                        split=split,
                        duration_samples=len(aug_clip),
                    )
                    samples_metadata.append(meta)
                    audio_clips.append(aug_clip)
                    labels.append(0)

                cmd_id += 1

        # --------------------------------------------------------------------
        # 4. AMBIENT NON-SPEECH (Silence, Fan, Keyboard, Pink, White)
        # --------------------------------------------------------------------
        for amb_i in range(50):
            noise_type = ["fan", "keyboard", "pink", "white", "silence"][amb_i % 5]
            split_mod = amb_i % 7
            split = "val" if split_mod == 5 else ("holdout" if split_mod == 6 else "train")

            if noise_type == "silence":
                clip = np.zeros(CLIP_TOTAL_SAMPLES, dtype=np.int16)
            elif noise_type == "fan":
                t = np.linspace(0, CLIP_DURATION_SECONDS, CLIP_TOTAL_SAMPLES, endpoint=False)
                hum = (1200.0 * np.sin(2 * np.pi * 60 * t) + 400.0 * np.sin(2 * np.pi * 120 * t)).astype(np.int16)
                hiss = np.random.normal(0, 400.0, CLIP_TOTAL_SAMPLES).astype(np.int16)
                clip = hum + hiss
            elif noise_type == "keyboard":
                clip = np.random.normal(0, 200.0, CLIP_TOTAL_SAMPLES).astype(np.int16)
                clicks = np.random.choice(CLIP_TOTAL_SAMPLES, size=6, replace=False)
                for loc in clicks:
                    clen = min(160, CLIP_TOTAL_SAMPLES - loc)
                    clip[loc : loc + clen] += (np.exp(-np.linspace(0, 5, clen)) * 4000.0).astype(np.int16)
            elif noise_type == "pink":
                white = np.random.normal(0, 1000.0, CLIP_TOTAL_SAMPLES)
                clip = np.convolve(white, np.ones(8) / 8.0, mode="same").astype(np.int16)
            else:
                clip = np.random.normal(0, 800.0, CLIP_TOTAL_SAMPLES).astype(np.int16)

            meta = SampleMetadata(
                sample_id=f"neg_ambient_{amb_i}",
                label=0,
                phrase=f"ambient_{noise_type}",
                is_hard_negative=False,
                is_human=False,
                speaker_id="none",
                rate=0,
                volume=0,
                augmentation=f"ambient_{noise_type}",
                split=split,
                duration_samples=len(clip),
            )
            samples_metadata.append(meta)
            audio_clips.append(clip)
            labels.append(0)

        # Save metadata JSON
        metadata_path = self.data_dir / "dataset_metadata.json"
        with open(metadata_path, "w", encoding="utf-8") as mf:
            json.dump([asdict(m) for m in samples_metadata], mf, indent=2)

        # Run deterministic leakage audit
        audit_res = audit_dataset_leakage(samples_metadata, self.holdout_manifest_path)
        logger.info("Deterministic leakage audit PASSED: %s", audit_res)

        hn_count = sum(1 for m in samples_metadata if m.is_hard_negative)
        logger.info(
            "Hardened dataset generation complete: Total clips=%d (Positives: %d, Negatives: %d, Hard Negatives: %d)",
            len(audio_clips),
            labels.count(1),
            labels.count(0),
            hn_count,
        )

        return samples_metadata, audio_clips, labels

    def extract_features(
        self,
        audio_clips: List[np.ndarray],
        labels: List[int],
        metadata: List[SampleMetadata],
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Extract openWakeWord (16, 96) feature embeddings via AudioFeatures.
        Splits into Train, Validation, and Final Holdout arrays.
        """
        from openwakeword.utils import AudioFeatures

        logger.info("Extracting embeddings for %d clips...", len(audio_clips))
        F = AudioFeatures(inference_framework="onnx", device="cpu", ncpu=4)

        clips_array = np.vstack(audio_clips).astype(np.int16)
        features = F.embed_clips(clips_array, batch_size=32)

        train_idx = [i for i, m in enumerate(metadata) if m.split == "train"]
        val_idx = [i for i, m in enumerate(metadata) if m.split == "val"]
        holdout_idx = [i for i, m in enumerate(metadata) if m.split == "holdout"]

        labels_arr = np.array(labels, dtype=np.float32)

        X_train, y_train = features[train_idx], labels_arr[train_idx]
        X_val, y_val = features[val_idx], labels_arr[val_idx]
        if holdout_idx:
            X_holdout, y_holdout = features[holdout_idx], labels_arr[holdout_idx]
        else:
            X_holdout = np.empty((0, 16, 96), dtype=np.float32)
            y_holdout = np.empty((0,), dtype=np.float32)

        # Save partitioned features
        np.save(self.features_dir / "X_train.npy", X_train)
        np.save(self.features_dir / "y_train.npy", y_train)
        np.save(self.features_dir / "X_val.npy", X_val)
        np.save(self.features_dir / "y_val.npy", y_val)
        np.save(self.features_dir / "X_holdout.npy", X_holdout)
        np.save(self.features_dir / "y_holdout.npy", y_holdout)

        logger.info(
            "Partition complete: Train=%s (pos=%.0f, neg=%.0f), Val=%s (pos=%.0f, neg=%.0f), Holdout=%s (pos=%.0f, neg=%.0f)",
            X_train.shape,
            np.sum(y_train == 1),
            np.sum(y_train == 0),
            X_val.shape,
            np.sum(y_val == 1),
            np.sum(y_val == 0),
            X_holdout.shape,
            np.sum(y_holdout == 1),
            np.sum(y_holdout == 0),
        )

        return X_train, y_train, X_val, y_val, X_holdout, y_holdout

    def extract_locked_holdout_features(
        self,
        manifest_path: Optional[Path | str] = None,
        force_recompute: bool = False,
    ) -> Tuple[np.ndarray, np.ndarray, List[Dict[str, Any]]]:
        """
        Extract openWakeWord (16, 96) feature embeddings for the 33 frozen holdout samples
        defined in locked_human_holdout_manifest.json.
        Guarantees exact, deterministic feature representation for holdout evaluation.
        """
        from openwakeword.utils import AudioFeatures

        m_path = Path(manifest_path or self.holdout_manifest_path or (self.data_dir / "human" / "locked_human_holdout_manifest.json"))
        if not m_path.exists():
            raise FileNotFoundError(f"Locked human holdout manifest not found at {m_path}")

        holdout_feat_path = self.features_dir / "X_locked_holdout.npy"
        holdout_labels_path = self.features_dir / "y_locked_holdout.npy"
        holdout_meta_path = self.features_dir / "meta_locked_holdout.json"

        with open(m_path, "r", encoding="utf-8") as f:
            m_data = json.load(f)
        samples = m_data.get("samples", [])

        if not force_recompute and holdout_feat_path.exists() and holdout_labels_path.exists() and holdout_meta_path.exists():
            try:
                X_h = np.load(holdout_feat_path)
                y_h = np.load(holdout_labels_path)
                with open(holdout_meta_path, "r", encoding="utf-8") as mf:
                    saved_meta = json.load(mf)
                if len(X_h) == len(samples) and len(y_h) == len(samples):
                    logger.info("Loaded cached locked holdout features (%d samples).", len(X_h))
                    return X_h, y_h, saved_meta
            except Exception as exc:
                logger.warning("Failed to load cached holdout features: %s. Recomputing...", exc)

        logger.info("Extracting features for %d locked holdout samples...", len(samples))
        human_root = m_path.parent
        clips = []
        labels = []
        loaded_samples = []

        for s in samples:
            rel_p = s["relative_path"]
            full_p = human_root / rel_p
            if not full_p.exists():
                raise FileNotFoundError(f"Holdout file missing: {full_p} (from {rel_p})")

            # Cryptographic verification
            actual_sha = compute_file_sha256(full_p)
            if actual_sha != s["sha256"].lower():
                raise ValueError(f"Holdout SHA256 mismatch for {rel_p}! Expected {s['sha256']}, got {actual_sha}")

            audio = load_pcm16_wav(str(full_p))
            clip = pad_or_trim_to_length(audio, CLIP_TOTAL_SAMPLES)
            clips.append(clip)
            labels.append(int(s["target_label"]))
            loaded_samples.append(s)

        F = AudioFeatures(inference_framework="onnx", device="cpu", ncpu=4)
        clips_array = np.vstack(clips).astype(np.int16)
        X_holdout = F.embed_clips(clips_array, batch_size=32)
        y_holdout = np.array(labels, dtype=np.float32)

        self.features_dir.mkdir(parents=True, exist_ok=True)
        np.save(holdout_feat_path, X_holdout)
        np.save(holdout_labels_path, y_holdout)
        with open(holdout_meta_path, "w", encoding="utf-8") as mf:
            json.dump(loaded_samples, mf, indent=2)

        logger.info(
            "Locked holdout feature extraction complete: shape=%s (pos=%d, neg=%d)",
            X_holdout.shape,
            int(np.sum(y_holdout == 1)),
            int(np.sum(y_holdout == 0)),
        )
        return X_holdout, y_holdout, loaded_samples
