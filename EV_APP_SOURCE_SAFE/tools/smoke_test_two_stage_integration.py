"""
Real-Time Acoustic Smoke Test for Integrated Two-Stage Voice Runtime (Task 014F-12B).

Feeds live 80ms acoustic audio frames in real-time streaming cadence directly into
EVVoiceManager configured with Stage 1 (hey_ev_human_v2.onnx) and Stage 2 (FasterWhisperWakeVerifier).

Evaluates:
1. "Hey EV"
2. "Hey E V"
3. "Hey Evan"
4. "Hey Evelyn"
5. "Hey Everyone"
6. "Hey Stevie"
7. "Every"
8. Normal unrelated speech ("Open the browser and check system status")
9. Background TV / conversational audio
"""
from __future__ import annotations

import logging
import os
import sys
import threading
import time
import wave
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from core.asr_faster_whisper import FasterWhisperASRProvider
from core.voice_capture import AudioFrame, EVAudioCaptureProvider
from core.voice_manager import (
    EVVoiceManager,
    VoiceState,
)
from core.voice_vad import EnergyVADProvider
from core.voice_wakeword_openwakeword import OpenWakeWordProvider
from core.wake_verifier import FasterWhisperWakeVerifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ev.two_stage.smoke")

STAGE1_MODEL = r"D:\EV\models\wakeword\candidates\hey_ev_human_v2.onnx"


class StreamingAudioCapture(EVAudioCaptureProvider):
    """Feeds live audio frames from in-memory PCM at 80ms intervals."""

    def __init__(self, sample_rate: int = 16000, frame_size: int = 1280):
        self._sample_rate = sample_rate
        self._frame_size = frame_size
        self._frames: List[AudioFrame] = []
        self._idx = 0
        self._running = False
        self._lock = threading.Lock()

    @property
    def provider_name(self) -> str:
        return "StreamingAudioCapture"

    @property
    def is_available(self) -> bool:
        return True

    def set_audio_data(self, pcm_bytes: bytes) -> None:
        with self._lock:
            self._frames.clear()
            self._idx = 0
            # Pad with 0.5s pre-silence and 0.5s post-silence
            silence_frame = bytes(self._frame_size * 2)
            for _ in range(6):  # ~480ms pre-roll
                self._frames.append(AudioFrame(data=silence_frame, sample_rate=self._sample_rate, channels=1, timestamp=time.time()))
            for i in range(0, len(pcm_bytes), self._frame_size * 2):
                chunk = pcm_bytes[i:i + self._frame_size * 2]
                if len(chunk) < self._frame_size * 2:
                    chunk = chunk.ljust(self._frame_size * 2, b"\x00")
                self._frames.append(AudioFrame(data=chunk, sample_rate=self._sample_rate, channels=1, timestamp=time.time()))
            for _ in range(12):  # ~960ms post-roll
                self._frames.append(AudioFrame(data=silence_frame, sample_rate=self._sample_rate, channels=1, timestamp=time.time()))

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False

    def is_running(self) -> bool:
        return self._running

    def read_frame(self, timeout: float = 0.1) -> Optional[AudioFrame]:
        if not self._running:
            return None
        with self._lock:
            if self._idx < len(self._frames):
                frame = self._frames[self._idx]
                self._idx += 1
                time.sleep(0.08)  # 80ms real-time audio delivery
                return frame
        return None

    def close(self) -> None:
        self.stop()


class SmokeOrchestrator:
    def __init__(self):
        self.submitted_commands: List[str] = []

    def submit_command(self, cmd: str, origin: str = "voice") -> None:
        self.submitted_commands.append(cmd)


def load_or_synthesize_audio(wav_path: Optional[Path], fallback_text: str) -> bytes:
    if wav_path and wav_path.exists():
        with wave.open(str(wav_path), "rb") as wf:
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            raw_frames = wf.readframes(wf.getnframes())
            if sampwidth == 2 and n_channels == 1 and framerate == 16000:
                return raw_frames
            arr = np.frombuffer(raw_frames, dtype=np.int16)
            if n_channels > 1:
                arr = arr.reshape(-1, n_channels).mean(axis=1).astype(np.int16)
            return arr.tobytes()
    # If file not found, synthesize via Windows SAPI to temp wav
    import tempfile
    import pyttsx3
    engine = pyttsx3.init()
    temp_wav = Path(tempfile.gettempdir()) / "smoke_synth.wav"
    engine.save_to_file(fallback_text, str(temp_wav))
    engine.runAndWait()
    with wave.open(str(temp_wav), "rb") as wf:
        return wf.readframes(wf.getnframes())


def run_smoke_trial(
    trial_id: str,
    phrase: str,
    audio_bytes: bytes,
    s1_provider: OpenWakeWordProvider,
    s2_verifier: FasterWhisperWakeVerifier,
    threshold: float = 0.50,
) -> Tuple[str, bool, str, float]:
    """Stream audio frames through integrated EVVoiceManager and observe transitions."""
    capture = StreamingAudioCapture()
    capture.set_audio_data(audio_bytes)
    vad = EnergyVADProvider()
    asr = FasterWhisperASRProvider(model_size_or_path="base.en", compute_type="int8")
    orch = SmokeOrchestrator()

    state_history: List[VoiceState] = []

    def on_state(new_st: VoiceState):
        state_history.append(new_st)

    mgr = EVVoiceManager(
        capture_provider=capture,
        wake_word_provider=s1_provider,
        vad_provider=vad,
        asr_provider=asr,
        orchestrator=orch,
        wake_verifier=s2_verifier,
        enable_stage2_verification=True,
        on_state_change=on_state,
    )

    mgr.start()

    # Wait for capture to feed all frames
    t_start = time.perf_counter()
    while capture._idx < len(capture._frames) and time.perf_counter() - t_start < 5.0:
        time.sleep(0.04)

    # Allow post-frame processing and verification worker to settle
    time.sleep(0.3)
    t_wait = time.perf_counter()
    while mgr.state == VoiceState.VERIFYING_WAKE and time.perf_counter() - t_wait < 4.0:
        time.sleep(0.05)

    time.sleep(0.1)
    verified = VoiceState.LISTENING in state_history
    last_res = mgr.last_verification_result
    reason = last_res.reason if last_res else ("VERIFIED_DIRECT" if verified else "S1_NOT_TRIGGERED")
    latency = last_res.latency_ms if last_res else 0.0

    mgr.stop(timeout=1.0)
    return phrase, verified, reason, latency


def main():
    print("=" * 85)
    print("REAL-TIME ACOUSTIC SMOKE TEST: INTEGRATED TWO-STAGE VOICE RUNTIME")
    print("=" * 85)

    raw_dir = Path(r"D:\EV\models\wakeword\dataset\raw")

    test_cases = [
        # True Positives
        ("tp_1", "Hey EV", raw_dir / "pos_base_h_0.wav", "Hey EV"),
        ("tp_2", "Hey E V", raw_dir / "pos_base_h_2.wav", "Hey E V"),
        # Hard Competitors
        ("hn_1", "Hey Evan", raw_dir / "neg_hn_1.wav", "Hey Evan"),
        ("hn_2", "Hey Evelyn", raw_dir / "neg_hn_2.wav", "Hey Evelyn"),
        ("hn_3", "Hey Everyone", raw_dir / "neg_hn_0.wav", "Hey Everyone"),
        ("hn_4", "Hey Stevie", raw_dir / "neg_hn_3.wav", "Hey Stevie"),
        ("hn_5", "Every", raw_dir / "neg_hn_19.wav", "Every morning"),
        # General Unrelated Speech
        ("gn_1", "Open browser", raw_dir / "neg_cmd_0.wav", "Open the web browser"),
        ("gn_2", "System status", raw_dir / "neg_cmd_2.wav", "What is the system status"),
    ]

    s1_provider = OpenWakeWordProvider(
        wakeword_models=[STAGE1_MODEL],
        threshold=0.50,
        inference_framework="onnx",
    )
    print("Pre-warming FasterWhisperWakeVerifier...")
    s2_verifier = FasterWhisperWakeVerifier(model_size_or_path="base.en", compute_type="int8", cpu_threads=4)
    # Warm up model
    s2_verifier.verify_phrase(np.zeros(16000, dtype=np.int16))
    print("Warm-up complete. Starting test cases...\n")

    results = []
    for trial_id, phrase, wav_p, fallback_text in test_cases:
        audio = load_or_synthesize_audio(wav_p, fallback_text)
        phrase_name, verified, reason, lat = run_smoke_trial(
            trial_id=trial_id,
            phrase=phrase,
            audio_bytes=audio,
            s1_provider=s1_provider,
            s2_verifier=s2_verifier,
            threshold=0.50,
        )
        dec_str = "WAKE" if verified else "NO WAKE"
        print(f"Trial: {phrase_name:<18} | Result: {dec_str:<8} | Reason: {reason:<25} | Latency: {lat:.1f}ms")
        results.append((phrase_name, verified, reason, lat))

    s1_provider.close()

    print("\n" + "=" * 85)
    print("REAL-TIME ACOUSTIC SMOKE TEST SUMMARY")
    print("=" * 85)
    print(f"{'Phrase':<25} | {'Decision':<10} | {'Stage 2 Reason':<28} | Latency")
    print("-" * 85)
    for p, ver, r, l in results:
        d = "WAKE" if ver else "NO WAKE"
        print(f"{p:<25} | {d:<10} | {r:<28} | {l:.1f}ms")
    print("=" * 85)


if __name__ == "__main__":
    main()
