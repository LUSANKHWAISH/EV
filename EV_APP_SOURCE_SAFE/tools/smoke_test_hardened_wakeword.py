"""
Physical Smoke Test for Hardened "Hey EV" Wake-Word Model (Task 014F-5).

Tests the newly trained D:\\EV\\models\\wakeword\\hey_ev.onnx model on the physical JBL headset
microphone against the demonstrated failure phrases:
  - "Hey EV" (true positive targets)
  - "Hey Everyone" (previously triggered false alarms)
  - "Hey Evan" (previously triggered false alarms)
  - "Hey Stevie"
  - Standard non-wake commands ("Open the browser", "What time is it", "Cancel that command")
"""
from __future__ import annotations

import logging
import os
import sys
import threading
import time
from typing import Dict, List, Optional, Tuple

import numpy as np
import sounddevice as sd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from core.tts import WindowsSAPIProvider
from core.voice_capture import AudioFrame
from core.voice_manager import SoundDeviceAudioCaptureProvider
from core.voice_wakeword_openwakeword import OpenWakeWordProvider

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ev.wakeword.smoke")

MODEL_PATH = r"D:\EV\models\wakeword\hey_ev.onnx"
DEVICE_INDEX = 1


def run_physical_smoke_trial(
    trial_id: str,
    phrase: str,
    voice: str = "Microsoft David Desktop",
    threshold: float = 0.50,
) -> Tuple[str, float, bool, float]:
    """Execute acoustic emission into room and live microphone capture."""
    tts = WindowsSAPIProvider()
    capture = SoundDeviceAudioCaptureProvider(device=DEVICE_INDEX)
    provider = OpenWakeWordProvider(
        wakeword_models=[MODEL_PATH],
        threshold=0.01,  # Record full score distribution
        inference_framework="onnx",
    )

    captured_frames: List[AudioFrame] = []
    stop_evt = threading.Event()

    def worker():
        capture.start()
        while not stop_evt.is_set():
            f = capture.read_frame(timeout=0.05)
            if f:
                captured_frames.append(f)
        capture.stop()

    t = threading.Thread(target=worker, daemon=True)
    t.start()

    time.sleep(0.4)
    tts.speak(phrase, f"smoke-{trial_id}")
    time.sleep(0.8)

    stop_evt.set()
    t.join(timeout=3.0)

    max_score = 0.0
    pcm = bytearray()
    for f in captured_frames:
        pcm.extend(f.data)
        res = provider.process_frame(f)
        if res and res.confidence > max_score:
            max_score = res.confidence

    provider.close()

    arr = np.frombuffer(pcm, dtype=np.int16)
    rms = float(np.sqrt(np.mean(arr.astype(float) ** 2))) if len(arr) > 0 else 0.0
    detected = max_score >= threshold

    return phrase, max_score, detected, rms


def main():
    print("=" * 65)
    print("PHYSICAL SMOKE TEST: HARDENED 'HEY EV' MODEL ON JBL MICROPHONE")
    print("=" * 65)

    test_cases = [
        # Target true positives
        ("tp_1", "Hey EV", "Microsoft David Desktop"),
        ("tp_2", "Hey EV", "Microsoft Zira Desktop"),
        ("tp_3", "Hey E.V.", "Microsoft David Desktop"),
        ("tp_4", "Hey EV", "Microsoft David Desktop"),
        # Demonstrated hard-negative failure phrases
        ("hn_1", "Hey Everyone", "Microsoft David Desktop"),
        ("hn_2", "Hey Everyone", "Microsoft Zira Desktop"),
        ("hn_3", "Hey Evan", "Microsoft David Desktop"),
        ("hn_4", "Hey Evan", "Microsoft Zira Desktop"),
        ("hn_5", "Hey Stevie", "Microsoft David Desktop"),
        ("hn_6", "Hey Evie", "Microsoft Zira Desktop"),
        # General non-wake commands
        ("cmd_1", "Open the browser", "Microsoft David Desktop"),
        ("cmd_2", "What time is it", "Microsoft David Desktop"),
        ("cmd_3", "Cancel that command", "Microsoft Zira Desktop"),
    ]

    for tid, phrase, voice in test_cases:
        p, score, det, rms = run_physical_smoke_trial(tid, phrase, voice=voice)
        status = "TRIGGERED" if det else "REJECTED"
        is_target_pos = ("Hey EV" in phrase or "Hey E.V." in phrase)
        correctness = "CORRECT" if (det == is_target_pos) else "ERROR"
        print(f"  [{tid:5s}] '{phrase:20s}' ({voice.split()[1]:5s}): Max Score = {score:.3f} -> {status:9s} [{correctness}] (RMS={rms:.1f})")
        time.sleep(0.5)

    print("=" * 65)


if __name__ == "__main__":
    main()
