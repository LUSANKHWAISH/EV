"""Standalone interactive prototype proving real playback EQ on Windows audio hardware.

Usage:
    python -m prototypes.playback_eq.cli_prototype [path/to/audio.wav] [--demo]
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from PySide6.QtGui import QGuiApplication
from PySide6.QtMultimedia import QMediaDevices

from prototypes.playback_eq import EQPlaybackEngine, WavReader


def run_interactive_demo(file_path: Path, auto_demo: bool = False) -> None:
    app = QGuiApplication.instance()
    if app is None:
        app = QGuiApplication(sys.argv)

    dev = QMediaDevices.defaultAudioOutput()
    print("=" * 70)
    print("  EV AUDIO PLAYBACK EQUALIZER PROTOTYPE (M3 PROOF)")
    print("=" * 70)
    print(f"Target file:        {file_path.name}")
    print(f"Audio device:       {dev.description()} (isNull={dev.isNull()})")

    with WavReader(file_path) as r:
        print(f"Format:             {r.sample_rate} Hz, {r.channels} ch, {r.sample_width*8}-bit PCM")
        print(f"Duration:           {r.duration_seconds:.2f} s ({r.total_frames} frames)")

    engine = EQPlaybackEngine()
    if not engine.load(file_path):
        print(f"ERROR: Failed to load {file_path}: {engine.last_error_message}")
        return

    print("-" * 70)
    print("Starting real-time audio playback through peaking EQ filter...")
    print(f"Initial settings: Volume={engine.volume*100:.0f}%, Preamp={engine.dsp.preamp_db:+.1f}dB, "
          f"EQ={engine.dsp.band.hz:.0f}Hz @ {engine.dsp.band.gain_db:+.1f}dB (Q={engine.dsp.band.q:.1f}), "
          f"Bypass={engine.dsp.bypass}")
    print("-" * 70)

    engine.play()

    if auto_demo:
        # Automated demonstration stepping through parameters
        print("\n[AUTO-DEMO] Running parameter change sequence:")
        steps = [
            (0.8, "Normal flat playback (bypass=False, gain=0dB)"),
            (0.8, "Applying +8.0 dB BASS boost at 120 Hz...", lambda: engine.set_eq_band(120, 8.0, 1.0)),
            (0.8, "Applying +6.0 dB MID boost at 1000 Hz...", lambda: engine.set_eq_band(1000, 6.0, 1.2)),
            (0.8, "Applying +8.0 dB TREBLE boost at 6000 Hz...", lambda: engine.set_eq_band(6000, 8.0, 1.0)),
            (0.8, "Applying -12.0 dB CUT at 1000 Hz...", lambda: engine.set_eq_band(1000, -12.0, 2.0)),
            (0.8, "Toggling BYPASS = TRUE (instant click-free unity)...", lambda: engine.set_bypass(True)),
            (0.8, "Toggling BYPASS = FALSE (restoring EQ cut)...", lambda: engine.set_bypass(False)),
            (0.6, "Preamp adjustment to -3.0 dB (headroom protection)...", lambda: engine.set_preamp(-3.0)),
        ]
        for duration, label, *action in steps:
            print(f" -> {label}")
            if action and callable(action[0]):
                action[0]()
            t_end = time.time() + duration
            while time.time() < t_end and engine.is_playing:
                time.sleep(0.05)
                app.processEvents()
                print(f"\r    pos: {engine.position_seconds:5.2f}s | "
                      f"peak: {engine.dsp.peak_dbfs:5.1f} dBFS | "
                      f"headroom: {engine.dsp.headroom_db:5.1f} dB | "
                      f"DSP latency: {engine.dsp.last_processing_time_ms:5.3f}ms | "
                      f"underruns: {engine.underrun_count}", end="", flush=True)
            print()
    else:
        # Non-blocking status loop
        try:
            while engine.is_playing and engine.position_seconds < engine.duration_seconds:
                time.sleep(0.1)
                app.processEvents()
                print(f"\rpos: {engine.position_seconds:5.2f}s / {engine.duration_seconds:5.2f}s | "
                      f"peak: {engine.dsp.peak_dbfs:5.1f} dBFS | "
                      f"headroom: {engine.dsp.headroom_db:5.1f} dB | "
                      f"DSP: {engine.dsp.last_processing_time_ms:5.3f}ms | "
                      f"underruns: {engine.underrun_count}", end="", flush=True)
        except KeyboardInterrupt:
            print("\nPlayback interrupted by user.")

    print("\n" + "=" * 70)
    print("Stopping playback and releasing device resources...")
    engine.stop()
    engine.close()
    print("Clean shutdown complete.")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="EV Playback EQ Prototype")
    parser.add_argument("file", nargs="?", default="prototypes/cinematic_v4/assets/startup/arrival.wav",
                        help="Path to WAV audio file")
    parser.add_argument("--demo", action="store_true", help="Run automated parameter demonstration")
    args = parser.parse_args()

    file_path = Path(args.file)
    if not file_path.exists():
        fallback = Path("prototypes/cinematic_v4/evidence/music_foundation/fixture.wav")
        if fallback.exists():
            file_path = fallback
        else:
            print(f"Error: audio file {file_path} not found.")
            sys.exit(1)

    run_interactive_demo(file_path, auto_demo=args.demo)


if __name__ == "__main__":
    main()
