"""
Physical Hardware Diagnostic Tool for E.V. Wake-Word Engine (Task 014F-1).

Streams live audio from the physical microphone using SoundDeviceAudioCaptureProvider
and processes frames through OpenWakeWordProvider to validate real-time wake-word
detection behavior on physical hardware.

Usage:
  python tools/test_wakeword.py
  python tools/test_wakeword.py --model alexa --threshold 0.5 --duration 30
  python tools/test_wakeword.py --list-devices
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Optional

# Ensure repo root is on sys.path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from core.voice_capture import DEFAULT_SAMPLE_RATE, AudioFrame
from core.voice_manager import SoundDeviceAudioCaptureProvider
from core.voice_wakeword_openwakeword import (
    DEFAULT_DETECTION_THRESHOLD,
    DEFAULT_INFERENCE_FRAMEWORK,
    OpenWakeWordProvider,
)


def list_audio_devices() -> None:
    """Print available audio capture devices."""
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        print("\nAvailable Audio Input Devices:")
        print("------------------------------------------------------------")
        for idx, dev in enumerate(devices):
            if dev.get("max_input_channels", 0) > 0:
                print(f"  [{idx}] {dev.get('name')} (inputs: {dev.get('max_input_channels')}, default rate: {dev.get('default_samplerate')})")
        print("------------------------------------------------------------\n")
    except Exception as exc:
        print(f"Error querying audio devices: {exc}")


def run_wake_word_diagnostic(
    model_name: str = "alexa",
    threshold: float = DEFAULT_DETECTION_THRESHOLD,
    duration: float = 30.0,
    device: Optional[int] = None,
    framework: str = DEFAULT_INFERENCE_FRAMEWORK,
) -> None:
    """Run real-time wake-word detection loop with physical microphone."""
    print("=" * 60)
    print("WAKE WORD ENGINE DIAGNOSTIC")
    print(f"Provider:    openwakeword")
    print(f"Model:       {model_name}")
    print(f"Input:       {device if device is not None else 'Default Microphone'}")
    print(f"Sample rate: {DEFAULT_SAMPLE_RATE} Hz")
    print(f"Threshold:   {threshold:.2f}")
    print(f"Framework:   {framework}")
    print("=" * 60)
    print("NOTE: This diagnostic validates the openWakeWord ENGINE ADAPTER.")
    print("      Custom 'Hey EV' model training occurs in Task 014F-2.")
    print("-" * 60)

    # Initialize Audio Capture
    capture = SoundDeviceAudioCaptureProvider(
        sample_rate=DEFAULT_SAMPLE_RATE,
        channels=1,
        device=device,
    )

    if not capture.is_available():
        print("ERROR: sounddevice audio capture is not available on this host.")
        return

    # Initialize Wake Word Provider
    try:
        provider = OpenWakeWordProvider(
            wakeword_models=[model_name],
            threshold=threshold,
            inference_framework=framework,
            target_phrase=model_name,
        )
    except Exception as exc:
        print(f"ERROR: Failed to initialize OpenWakeWordProvider: {exc}")
        return

    print("Listening... (Speak the wake word, or press Ctrl+C to stop)\n")

    capture.start()
    start_time = time.monotonic()
    detections_count = 0
    frames_processed = 0

    try:
        while True:
            elapsed = time.monotonic() - start_time
            if duration > 0 and elapsed >= duration:
                print(f"\nCompleted duration limit ({duration:.1f}s).")
                break

            frame: Optional[AudioFrame] = capture.read_frame(timeout=0.1)
            if frame is None:
                continue

            frames_processed += 1
            result = provider.process_frame(frame)

            if result is not None and result.detected:
                detections_count += 1
                curr_time = time.strftime("%H:%M:%S")
                print(
                    f"[{curr_time}] >>> WAKE WORD DETECTED! <<< "
                    f"Keyword='{result.keyword}', Confidence={result.confidence:.3f}, "
                    f"Elapsed={elapsed:.1f}s"
                )

    except KeyboardInterrupt:
        print("\nDiagnostic interrupted by user.")
    finally:
        capture.stop()
        total_elapsed = time.monotonic() - start_time

        print("\n" + "=" * 60)
        print("DIAGNOSTIC SUMMARY")
        print(f"Provider:         openwakeword")
        print(f"Model:            {model_name}")
        print(f"Total Detections: {detections_count}")
        print(f"Frames Ingested:  {frames_processed}")
        print(f"Elapsed Time:     {total_elapsed:.2f}s")
        print("=" * 60)


def main() -> None:
    default_model = r"D:\EV\models\wakeword\hey_ev.onnx" if os.path.exists(r"D:\EV\models\wakeword\hey_ev.onnx") else "alexa"
    default_framework = "onnx" if default_model.endswith(".onnx") else DEFAULT_INFERENCE_FRAMEWORK
    parser = argparse.ArgumentParser(description="E.V. Wake-Word Hardware Diagnostic Tool")
    parser.add_argument("--model", type=str, default=default_model, help=f"Model name or file path (default: {default_model})")
    parser.add_argument("--threshold", type=float, default=DEFAULT_DETECTION_THRESHOLD, help="Detection threshold (0.0 - 1.0)")
    parser.add_argument("--duration", type=float, default=30.0, help="Listening duration in seconds (0 = indefinite)")
    parser.add_argument("--device", type=int, default=None, help="Input device index")
    parser.add_argument("--framework", type=str, default=default_framework, choices=["tflite", "onnx"], help="Inference framework")
    parser.add_argument("--list-devices", action="store_true", help="List audio input devices and exit")

    args = parser.parse_args()

    if args.list_devices:
        list_audio_devices()
        return

    run_wake_word_diagnostic(
        model_name=args.model,
        threshold=args.threshold,
        duration=args.duration,
        device=args.device,
        framework=args.framework,
    )


if __name__ == "__main__":
    main()
