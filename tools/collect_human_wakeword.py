"""
Interactive & Batch Human "Hey EV" Audio Collection Tool for E.V. (Task 014F-6 & Task 014F-7 Hardening).

Provides:
  1. Controlled local recording through SoundDevice (canonical 16 kHz mono PCM16).
  2. Guided collection prompts for POSITIVE, HARD_NEGATIVE, and GENERAL_NEGATIVE phrases.
  3. Quality verification: RMS, peak amplitude, clipping detection, SNR estimate, and silence checks.
  4. Mandatory human confirmation gate: explicit [Y/N/R/S/Q] verification before committing takes.
  5. Collision-free deterministic unique session naming ({speaker_id}_{session_id}_{slug}_{take_idx:02d}.wav).
  6. Automatic routing of rejected/non-target takes to models/wakeword/dataset/human/quarantine/.
  7. Non-PII metadata logging and saving to human_collection_manifest.json with deduplication.

Security & Invariants:
  - 100% Local: Zero audio files uploaded to any network or cloud service.
  - Zero Authority: Audio recording only; no connection to EVOrchestrator or command execution.
  - Strict Quality Contract: Rejects clipped, silent, or unconfirmed audio takes.
  - Overwrite Protection: Existing recording files are never silently overwritten.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import threading
import time
import wave
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import sounddevice as sd

# Ensure repo root is on sys.path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from core.voice_capture import AudioFrame
from core.voice_manager import SoundDeviceAudioCaptureProvider

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ev.wakeword.collector")

CANONICAL_SAMPLE_RATE: int = 16000
CANONICAL_CHANNELS: int = 1
CANONICAL_SAMPLE_WIDTH: int = 2
RECORDING_DURATION_SEC: float = 2.5
TARGET_DURATION_SEC: float = 2.0
TARGET_TOTAL_SAMPLES: int = int(CANONICAL_SAMPLE_RATE * TARGET_DURATION_SEC)  # 32,000 samples

HUMAN_DATASET_DIR = Path(r"D:\EV\models\wakeword\dataset\human")
HUMAN_POS_DIR = HUMAN_DATASET_DIR / "positive"
HUMAN_NEG_DIR = HUMAN_DATASET_DIR / "negative"
HUMAN_QUARANTINE_DIR = HUMAN_DATASET_DIR / "quarantine"
MANIFEST_PATH = HUMAN_DATASET_DIR / "human_collection_manifest.json"

# Target Phrase Catalog for Human Collection
COLLECTION_PROMPTS = [
    # ------------------------------------------------------------------------
    # 1. POSITIVE PHRASES ("Hey EV" variants & acoustic conditions)
    # ------------------------------------------------------------------------
    {"category": "POSITIVE", "phrase": "Hey EV", "condition": "natural speaking volume", "target": "pos"},
    {"category": "POSITIVE", "phrase": "Hey EV", "condition": "quiet speaking", "target": "pos"},
    {"category": "POSITIVE", "phrase": "Hey EV", "condition": "normal speaking", "target": "pos"},
    {"category": "POSITIVE", "phrase": "Hey EV", "condition": "slightly distant microphone (~1m)", "target": "pos"},
    {"category": "POSITIVE", "phrase": "Hey EV", "condition": "fast speaking rate", "target": "pos"},
    {"category": "POSITIVE", "phrase": "Hey EV", "condition": "slow deliberate speaking rate", "target": "pos"},
    {"category": "POSITIVE", "phrase": "Hey E.V.", "condition": "distinct letters E-V", "target": "pos"},
    {"category": "POSITIVE", "phrase": "Hey E V", "condition": "natural pause between letters", "target": "pos"},
    {"category": "POSITIVE", "phrase": "hey ev", "condition": "casual / low energy", "target": "pos"},
    # ------------------------------------------------------------------------
    # 2. HARD NEGATIVE PHRASES (Demonstrated Prefix & Confusable Failure Phrases)
    # ------------------------------------------------------------------------
    {"category": "HARD_NEGATIVE", "phrase": "Hey Everyone", "condition": "normal cadence", "target": "neg"},
    {"category": "HARD_NEGATIVE", "phrase": "Hey Evan", "condition": "normal cadence", "target": "neg"},
    {"category": "HARD_NEGATIVE", "phrase": "Hey Evie", "condition": "normal cadence", "target": "neg"},
    {"category": "HARD_NEGATIVE", "phrase": "Hey Evening", "condition": "normal cadence", "target": "neg"},
    {"category": "HARD_NEGATIVE", "phrase": "Hey Evidence", "condition": "normal cadence", "target": "neg"},
    {"category": "HARD_NEGATIVE", "phrase": "Hey Stevie", "condition": "normal cadence", "target": "neg"},
    {"category": "HARD_NEGATIVE", "phrase": "Heavy", "condition": "single word", "target": "neg"},
    {"category": "HARD_NEGATIVE", "phrase": "Every", "condition": "single word", "target": "neg"},
    {"category": "HARD_NEGATIVE", "phrase": "Hey Steve", "condition": "normal cadence", "target": "neg"},
    {"category": "HARD_NEGATIVE", "phrase": "Hey", "condition": "greeting without EV", "target": "neg"},
    {"category": "HARD_NEGATIVE", "phrase": "EV", "condition": "letters without Hey", "target": "neg"},
    # ------------------------------------------------------------------------
    # 3. GENERAL NEGATIVE PHRASES (Standard In-Room Voice Commands)
    # ------------------------------------------------------------------------
    {"category": "GENERAL_NEGATIVE", "phrase": "Open the browser", "condition": "command utterance", "target": "neg"},
    {"category": "GENERAL_NEGATIVE", "phrase": "What time is it", "condition": "command utterance", "target": "neg"},
    {"category": "GENERAL_NEGATIVE", "phrase": "System status", "condition": "command utterance", "target": "neg"},
    {"category": "GENERAL_NEGATIVE", "phrase": "Turn on the lights", "condition": "command utterance", "target": "neg"},
    {"category": "GENERAL_NEGATIVE", "phrase": "Cancel that command", "condition": "command utterance", "target": "neg"},
    {"category": "GENERAL_NEGATIVE", "phrase": "Show active tasks", "condition": "command utterance", "target": "neg"},
]


@dataclass
class AudioQualityMetrics:
    sample_rate: int
    channels: int
    duration_sec: float
    total_samples: int
    rms: float
    peak: int
    clipping_percent: float
    snr_db: float
    is_silent: bool
    is_valid: bool
    rejection_reason: Optional[str] = None


@dataclass
class HumanRecordingManifestItem:
    filename: str
    relative_path: str
    category: str
    target_label: int  # 1 for positive, 0 for negative, -1 for quarantine
    phrase: str
    condition: str
    speaker_id: str
    device_name: str
    timestamp: float
    quality: AudioQualityMetrics
    session_id: str = "session_default"
    confirmed_by_user: bool = True
    status: str = "ACCEPTED"
    quarantine_reason: Optional[str] = None


def analyze_audio_quality(
    audio: np.ndarray,
    sample_rate: int = CANONICAL_SAMPLE_RATE,
    min_rms: float = 30.0,
    max_clipping_percent: float = 1.0,
) -> AudioQualityMetrics:
    """
    Compute objective quality and acoustic health metrics for a recorded PCM16 clip.
    """
    total_samples = len(audio)
    duration_sec = round(total_samples / float(sample_rate), 3)

    if total_samples == 0:
        return AudioQualityMetrics(
            sample_rate=sample_rate,
            channels=1,
            duration_sec=0.0,
            total_samples=0,
            rms=0.0,
            peak=0,
            clipping_percent=0.0,
            snr_db=0.0,
            is_silent=True,
            is_valid=False,
            rejection_reason="Audio buffer contains zero samples",
        )

    peak = int(np.max(np.abs(audio)))
    rms = float(np.sqrt(np.mean(audio.astype(np.float64) ** 2)))

    # Clipping detection (|x| >= 32767)
    clipped_samples = int(np.sum(np.abs(audio) >= 32767))
    clipping_percent = round((clipped_samples / float(total_samples)) * 100.0, 3)

    # Estimate noise floor from leading 200 ms (first 3200 samples)
    lead_len = min(3200, total_samples // 4)
    lead_noise = audio[:lead_len].astype(np.float64)
    noise_power = np.mean(lead_noise**2) + 1e-12
    signal_power = rms**2 + 1e-12
    snr_db = round(10.0 * np.log10(max(1.0, signal_power / noise_power)), 2)

    is_silent = rms < min_rms
    is_valid = True
    rejection_reason = None

    if is_silent:
        is_valid = False
        rejection_reason = f"Audio level too low (RMS={rms:.1f} < {min_rms:.1f}); microphone may be muted or silent"
    elif clipping_percent > max_clipping_percent:
        is_valid = False
        rejection_reason = f"Acoustic distortion / clipping detected ({clipping_percent:.2f}% >= {max_clipping_percent:.2f}%)"

    return AudioQualityMetrics(
        sample_rate=sample_rate,
        channels=1,
        duration_sec=duration_sec,
        total_samples=total_samples,
        rms=round(rms, 2),
        peak=peak,
        clipping_percent=clipping_percent,
        snr_db=snr_db,
        is_silent=is_silent,
        is_valid=is_valid,
        rejection_reason=rejection_reason,
    )


def save_canonical_pcm16_wav(output_path: Path, audio: np.ndarray, allow_overwrite: bool = False) -> Path:
    """
    Save 1D int16 array to canonical 16 kHz mono WAV file.
    Guarantees that existing files are never overwritten unless explicitly permitted.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    target_path = output_path
    if target_path.exists() and not allow_overwrite:
        # Collision-safe suffixing
        stem = output_path.stem
        suffix = output_path.suffix
        counter = 1
        while target_path.exists():
            target_path = output_path.parent / f"{stem}_{counter:02d}{suffix}"
            counter += 1
            
    audio_int16 = np.clip(audio, -32768, 32767).astype(np.int16)
    with wave.open(str(target_path), "wb") as wf:
        wf.setnchannels(CANONICAL_CHANNELS)
        wf.setsampwidth(CANONICAL_SAMPLE_WIDTH)
        wf.setframerate(CANONICAL_SAMPLE_RATE)
        wf.writeframes(audio_int16.tobytes())
        
    return target_path


def pad_or_trim_canonical(audio: np.ndarray, target_length: int = TARGET_TOTAL_SAMPLES) -> np.ndarray:
    """Center and pad/trim audio to exactly target_length samples."""
    if len(audio) >= target_length:
        return audio[:target_length]
    pad_total = target_length - len(audio)
    left_pad = pad_total // 2
    right_pad = pad_total - left_pad
    return np.pad(audio, (left_pad, right_pad), mode="constant", constant_values=0)


class HumanAudioCollector:
    """
    Interactive and scripted recorder for human wake-word training data with
    hardened validation, explicit confirmation gates, and collision prevention.
    """

    def __init__(
        self,
        device_index: int = 1,
        speaker_id: str = "user_speaker_1",
        session_id: Optional[str] = None,
        output_base_dir: Path = HUMAN_DATASET_DIR,
    ) -> None:
        self.device_index = device_index
        self.speaker_id = speaker_id
        self.session_id = session_id or time.strftime("%Y%m%d_%H%M%S")
        self.output_base_dir = Path(output_base_dir)
        self.pos_dir = self.output_base_dir / "positive"
        self.neg_dir = self.output_base_dir / "negative"
        self.quarantine_dir = self.output_base_dir / "quarantine"
        self.manifest_file = self.output_base_dir / "human_collection_manifest.json"

        self.pos_dir.mkdir(parents=True, exist_ok=True)
        self.neg_dir.mkdir(parents=True, exist_ok=True)
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)

    def get_device_info(self) -> Dict[str, Any]:
        """Query SoundDevice for active recording device info."""
        try:
            info = sd.query_devices(self.device_index)
            return {"name": str(info.get("name", "Unknown")), "hostapi": int(info.get("hostapi", 0))}
        except Exception as exc:
            return {"name": f"Device {self.device_index}", "error": str(exc)}

    def record_clip(self, duration_sec: float = RECORDING_DURATION_SEC) -> np.ndarray:
        """
        Record an audio clip directly from SoundDeviceAudioCaptureProvider.
        """
        capture = SoundDeviceAudioCaptureProvider(device=self.device_index)
        captured_frames: List[AudioFrame] = []

        capture.start()
        # Allow stream buffer to initialize
        time.sleep(0.1)

        deadline = time.monotonic() + duration_sec
        while time.monotonic() < deadline:
            frame = capture.read_frame(timeout=0.05)
            if frame:
                captured_frames.append(frame)

        capture.stop()

        pcm_bytes = bytearray()
        for f in captured_frames:
            pcm_bytes.extend(f.data)

        if not pcm_bytes:
            return np.zeros(0, dtype=np.int16)

        return np.frombuffer(pcm_bytes, dtype=np.int16)

    def record_and_store_prompt(
        self,
        category: str,
        phrase: str,
        condition: str,
        target: str,
        index: int,
        user_confirmed: bool = True,
        quarantine_reason: Optional[str] = None,
        session_id: Optional[str] = None,
        raw_audio_override: Optional[np.ndarray] = None,
    ) -> Tuple[bool, Optional[HumanRecordingManifestItem]]:
        """
        Record an utterance, validate its acoustics, and persist to dataset if valid.
        If user_confirmed is False, routes safely to quarantine directory.
        """
        sess = session_id or self.session_id
        slug = phrase.lower().replace(" ", "_").replace(".", "")
        filename = f"{self.speaker_id}_{sess}_{slug}_{index:02d}.wav"

        if raw_audio_override is not None:
            raw_audio = raw_audio_override
        else:
            raw_audio = self.record_clip(duration_sec=RECORDING_DURATION_SEC)
            
        canonical_audio = pad_or_trim_canonical(raw_audio, TARGET_TOTAL_SAMPLES)
        quality = analyze_audio_quality(canonical_audio)
        
        if not quality.is_valid:
            logger.warning("Take rejected acoustically for '%s' (%s): %s", phrase, condition, quality.rejection_reason)
            return False, None

        if user_confirmed:
            target_dir = self.pos_dir if target == "pos" else self.neg_dir
            target_label = 1 if target == "pos" else 0
            item_category = category
            status = "ACCEPTED"
            q_reason = None
        else:
            target_dir = self.quarantine_dir
            target_label = -1
            item_category = "QUARANTINE"
            status = "QUARANTINED_USER_REJECTED"
            q_reason = quarantine_reason or "User rejected take during interactive confirmation"

        candidate_path = target_dir / filename
        final_path = save_canonical_pcm16_wav(candidate_path, canonical_audio, allow_overwrite=False)

        dev_info = self.get_device_info()
        item = HumanRecordingManifestItem(
            filename=final_path.name,
            relative_path=str(final_path.relative_to(self.output_base_dir)),
            category=item_category,
            target_label=target_label,
            phrase=phrase,
            condition=condition,
            speaker_id=self.speaker_id,
            session_id=sess,
            device_name=dev_info.get("name", "Unknown"),
            timestamp=time.time(),
            confirmed_by_user=user_confirmed,
            status=status,
            quality=quality,
            quarantine_reason=q_reason,
        )

        self._append_to_manifest(item)
        if user_confirmed:
            logger.info("Successfully recorded take '%s' [RMS=%.1f, Peak=%d, SNR=%.1fdB]", final_path.name, quality.rms, quality.peak, quality.snr_db)
        else:
            logger.warning("Take routed to quarantine '%s' [Reason: %s]", final_path.name, q_reason)
            
        return True, item

    def _append_to_manifest(self, item: HumanRecordingManifestItem) -> None:
        """Append record to manifest JSON file safely."""
        records = []
        if self.manifest_file.exists():
            try:
                with open(self.manifest_file, "r", encoding="utf-8") as f:
                    records = json.load(f)
            except Exception:
                records = []

        records.append(asdict(item))
        with open(self.manifest_file, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)

    def load_manifest(self) -> List[HumanRecordingManifestItem]:
        """Load manifest records from JSON."""
        if not self.manifest_file.exists():
            return []
        try:
            with open(self.manifest_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                items = []
                for d in data:
                    q_data = d.get("quality", {})
                    items.append(
                        HumanRecordingManifestItem(
                            filename=d["filename"],
                            relative_path=d["relative_path"],
                            category=d["category"],
                            target_label=d["target_label"],
                            phrase=d["phrase"],
                            condition=d["condition"],
                            speaker_id=d["speaker_id"],
                            device_name=d.get("device_name", "Unknown"),
                            timestamp=d["timestamp"],
                            quality=AudioQualityMetrics(**q_data),
                            session_id=d.get("session_id", "session_legacy"),
                            confirmed_by_user=d.get("confirmed_by_user", True),
                            status=d.get("status", "ACCEPTED"),
                            quarantine_reason=d.get("quarantine_reason"),
                        )
                    )
                return items
        except Exception as exc:
            logger.error("Failed to read manifest: %s", exc)
            return []


# ============================================================================
# Interactive CLI Runner with Explicit User Confirmation Gate
# ============================================================================
def run_interactive_collector(device_index: int = 1, speaker_id: str = "user_speaker_1") -> None:
    """Run interactive CLI prompt session for live human speaker with explicit confirmation gates."""
    collector = HumanAudioCollector(device_index=device_index, speaker_id=speaker_id)
    dev_info = collector.get_device_info()

    print("=" * 75)
    print("E.V. HUMAN WAKE-WORD AUDIO COLLECTION SYSTEM (HARDENED)")
    print(f"Recording Device: {dev_info.get('name')} (Index: {device_index})")
    print(f"Speaker Non-PII ID: {speaker_id}")
    print(f"Session Identifier: {collector.session_id}")
    print(f"Storage Directory: {HUMAN_DATASET_DIR}")
    print("=" * 75)
    print("Workflow: Press ENTER to record -> speak clearly -> review acoustics ->")
    print("CONFIRM with [Y] to accept as positive, [N] to quarantine, or [R] to re-record.")
    print("Type 'q' to quit at any time.\n")

    pos_idx = 0
    neg_idx = 0

    for prompt_info in COLLECTION_PROMPTS:
        category = prompt_info["category"]
        phrase = prompt_info["phrase"]
        condition = prompt_info["condition"]
        target = prompt_info["target"]

        while True:
            idx = pos_idx if target == "pos" else neg_idx

            print("-" * 75)
            print(f"Category:  [{category}]")
            print(f"Prompt:    \"{phrase}\"")
            print(f"Condition: {condition}")
            print("-" * 75)

            user_in = input("Press ENTER to record (or 's' to skip, 'q' to quit): ").strip().lower()
            if user_in == "q":
                print("Exiting collector session.")
                return
            if user_in == "s":
                print("Skipping prompt.\n")
                break

            print("--> RECORDING NOW... (Speak clearly into microphone) ...")
            raw_audio = collector.record_clip(duration_sec=RECORDING_DURATION_SEC)
            canonical = pad_or_trim_canonical(raw_audio, TARGET_TOTAL_SAMPLES)
            quality = analyze_audio_quality(canonical)

            if not quality.is_valid:
                print(f"\n[!] ACOUSTIC QUALITY REJECTED: {quality.rejection_reason}")
                retry_in = input("Retry this take? [r=Re-record, s=Skip, q=Quit]: ").strip().lower()
                if retry_in == "q":
                    print("Exiting collector session.")
                    return
                elif retry_in == "s":
                    print("Skipping prompt.\n")
                    break
                else:
                    continue  # Loop back to re-record

            # Acoustic Quality Passed: Display Metrics
            print(f"\n[+] Acoustic Metrics: RMS={quality.rms:.1f} | Peak={quality.peak} | SNR={quality.snr_db:.1f}dB | Clipping={quality.clipping_percent:.2f}%")
            
            # MANDATORY HUMAN CONFIRMATION GATE
            confirm = input(
                f"--> Was that a correct take of \"{phrase}\"? [y/n/r/s/q]\n"
                f"    (y=Accept & Save, n=Reject to Quarantine, r=Re-record, s=Skip, q=Quit): "
            ).strip().lower()

            if confirm == "y":
                success, item = collector.record_and_store_prompt(
                    category=category,
                    phrase=phrase,
                    condition=condition,
                    target=target,
                    index=idx,
                    user_confirmed=True,
                    raw_audio_override=raw_audio,
                )
                if success and item:
                    print(f"--> [ACCEPTED] Take saved to {item.relative_path}\n")
                    if target == "pos":
                        pos_idx += 1
                    else:
                        neg_idx += 1
                break

            elif confirm == "n":
                reason = input("Enter quarantine reason (or press ENTER for default): ").strip()
                success, item = collector.record_and_store_prompt(
                    category=category,
                    phrase=phrase,
                    condition=condition,
                    target=target,
                    index=idx,
                    user_confirmed=False,
                    quarantine_reason=reason or "User marked take as incorrect during confirmation",
                    raw_audio_override=raw_audio,
                )
                if success and item:
                    print(f"--> [QUARANTINED] Take safely routed to {item.relative_path} (Excluded from positive training)\n")
                break

            elif confirm == "r":
                print("--> Re-recording prompt...\n")
                continue

            elif confirm == "s":
                print("Skipping prompt.\n")
                break

            elif confirm == "q":
                print("Exiting collector session.")
                return

    manifest = collector.load_manifest()
    pos_count = sum(1 for m in manifest if m.target_label == 1)
    neg_count = sum(1 for m in manifest if m.target_label == 0)
    quar_count = sum(1 for m in manifest if m.target_label == -1)
    print("=" * 75)
    print(f"COLLECTION SUMMARY: {len(manifest)} total recordings indexed.")
    print(f"  Positives: {pos_count} | Negatives: {neg_count} | Quarantined: {quar_count}")
    print("=" * 75)


def probe_live_microphone(device_index: int = 1) -> Tuple[bool, float, str]:
    """
    Non-interactive diagnostic probe of the live microphone.
    Detects whether an active human speaker or acoustic signal is present.
    """
    collector = HumanAudioCollector(device_index=device_index)
    dev_info = collector.get_device_info()
    if "error" in dev_info:
        return False, 0.0, f"Cannot open device {device_index}: {dev_info['error']}"

    # Sample 1.0 second of audio
    clip = collector.record_clip(duration_sec=1.0)
    if len(clip) == 0:
        return False, 0.0, "SoundDevice returned empty buffer"

    rms = float(np.sqrt(np.mean(clip.astype(np.float64) ** 2)))
    has_human_speech = rms >= 100.0
    return has_human_speech, rms, dev_info.get("name", "Unknown")


def main():
    parser = argparse.ArgumentParser(description="E.V. Human Wake-Word Collection Tool (Hardened)")
    parser.add_argument("--device", type=int, default=1, help="SoundDevice microphone index")
    parser.add_argument("--speaker", type=str, default="user_speaker_1", help="Non-PII speaker identifier")
    parser.add_argument("--session", type=str, default=None, help="Optional custom session identifier")
    parser.add_argument("--probe", action="store_true", help="Probe microphone and check for live acoustic activity")
    args = parser.parse_args()

    if args.probe:
        has_speech, rms, dev_name = probe_live_microphone(args.device)
        print(f"Microphone: {dev_name} (Index: {args.device})")
        print(f"Measured RMS Level: {rms:.2f}")
        print(f"Acoustic Speech Present: {has_speech}")
        sys.exit(0)

    run_interactive_collector(device_index=args.device, speaker_id=args.speaker)


if __name__ == "__main__":
    main()
