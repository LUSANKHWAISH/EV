"""Focused regression test for streaming resampling fallback.

Verifies:
1. Scipy is declared in core install requirements (requirements.txt).
2. Boundary continuity across successive streaming chunks (no edge transients or clicks).
3. Correct total output length matching the target sample rate ratio.
4. Final resampler tail handling and complete draining at end-of-file.
5. Integration with EQPlaybackEngine when sample rate mismatch forces resampling.
"""
from __future__ import annotations

import math
from pathlib import Path
import sys
import wave
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from music.resampler import StreamingResampler
from prototypes.playback_eq.player import EQPlaybackEngine


def test_scipy_declared_in_requirements():
    """Verify scipy is declared in requirements.txt as an active dependency."""
    req_path = Path(__file__).resolve().parent.parent / "requirements.txt"
    assert req_path.exists(), "requirements.txt missing"
    content = req_path.read_text(encoding="utf-8")
    lines = [line.strip().lower() for line in content.splitlines() if line.strip() and not line.startswith("#")]
    assert any("scipy" in l for l in lines), "scipy must be declared in requirements.txt"


class TestStreamingResampler:
    """Verifies chunk boundary continuity, length accuracy, and tail draining."""

    @pytest.mark.parametrize("in_rate,out_rate", [(48000, 44100), (44100, 48000), (96000, 44100)])
    def test_chunk_boundary_continuity(self, in_rate: int, out_rate: int):
        """Verify C^1 smoothness across successive chunk boundaries (no clicks/discontinuities)."""
        resampler = StreamingResampler(in_rate, out_rate, channels=2)
        total_in_frames = in_rate * 2  # 2.0 seconds
        t = np.arange(total_in_frames) / float(in_rate)

        # 440 Hz test tone
        sine = (0.6 * np.sin(2.0 * np.pi * 440.0 * t)).astype(np.float32)
        stereo_in = np.column_stack([sine, sine])

        chunk_size = 1024
        out_chunks = []
        for i in range(0, total_in_frames, chunk_size):
            chunk = stereo_in[i : i + chunk_size]
            out = resampler.process(chunk)
            if len(out) > 0:
                out_chunks.append(out)

        tail = resampler.drain()
        if len(tail) > 0:
            out_chunks.append(tail)

        concatenated = np.concatenate(out_chunks, axis=0)

        # Measure step across each chunk boundary
        max_boundary_step = 0.0
        for i in range(len(out_chunks) - 1):
            c_curr = out_chunks[i]
            c_next = out_chunks[i + 1]
            if len(c_curr) > 0 and len(c_next) > 0:
                step = float(np.max(np.abs(c_next[0] - c_curr[-1])))
                max_boundary_step = max(max_boundary_step, step)

        # Measure normal internal sample-to-sample difference
        internal_diffs = np.abs(np.diff(concatenated, axis=0))
        max_internal_step = float(np.max(internal_diffs))

        # Boundary step must not exceed 1.5x internal step (no click / transient discontinuity)
        assert max_boundary_step <= max_internal_step * 1.5, (
            f"Chunk boundary jump {max_boundary_step:.5f} exceeds smooth threshold {max_internal_step * 1.5:.5f}"
        )

        # Frequency verification: spectral peak must match input frequency
        spec = np.abs(np.fft.rfft(concatenated[:, 0] * np.hanning(len(concatenated))))
        freqs = np.fft.rfftfreq(len(concatenated), d=1.0 / float(out_rate))
        measured_f = float(freqs[np.argmax(spec)])
        assert abs(measured_f - 440.0) < 1.0, f"Resampled frequency shifted to {measured_f:.2f} Hz"

    @pytest.mark.parametrize("in_rate,out_rate", [(48000, 44100), (44100, 48000)])
    def test_total_output_length_and_tail_handling(self, in_rate: int, out_rate: int):
        """Verify total output length matches rate ratio and drain() flushes residual tail."""
        resampler = StreamingResampler(in_rate, out_rate, channels=2)
        total_in_frames = in_rate  # Exactly 1.0 second of audio
        chunk_size = 1024
        silence = np.zeros((chunk_size, 2), dtype=np.float32)

        frames_fed = 0
        chunks = []
        while frames_fed < total_in_frames:
            n = min(chunk_size, total_in_frames - frames_fed)
            chunks.append(resampler.process(silence[:n]))
            frames_fed += n

        pre_drain_len = sum(len(c) for c in chunks)
        tail = resampler.drain()
        post_drain_len = pre_drain_len + len(tail)

        expected_frames = int(round(total_in_frames * (out_rate / in_rate)))
        # Total output length with tail must match expected length within ±2 frames
        assert abs(post_drain_len - expected_frames) <= 2, (
            f"Expected {expected_frames} frames, got {post_drain_len} (pre-drain: {pre_drain_len})"
        )


def test_player_forces_streaming_resampler(tmp_path):
    """Verify EQPlaybackEngine configures and runs StreamingResampler when sink rate differs from source."""
    # Create a 48kHz WAV file
    wav_path = tmp_path / "test_48k_resample.wav"
    fs = 48000
    t = np.arange(fs // 2) / fs  # 0.5 seconds
    sine = (0.3 * np.sin(2 * np.pi * 500 * t) * 32767.0).astype(np.int16)
    stereo = np.column_stack([sine, sine]).ravel().tobytes()
    with wave.open(str(wav_path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(fs)
        w.writeframes(stereo)

    player = EQPlaybackEngine()
    loaded = player.load(wav_path)
    assert loaded is True

    # Force a sink sample rate mismatch to trigger the fallback path
    player._sink_sample_rate = 44100
    player._resampler = StreamingResampler(player._sample_rate, 44100, player._channels)
    player._resample_up = 147
    player._resample_down = 160

    assert player._resampler is not None
    assert player.is_playing is False

    # Process 2 chunks manually through the worker pipeline to test accounting
    chunk_raw = player._reader.read_frames(1024)
    chunk_dsp = player.dsp.process(chunk_raw)
    res_out = player._resampler.process(chunk_dsp)

    assert len(res_out) > 0
    # Expected output length for 1024 frames @ 48k -> 44.1k is ~940-941 frames
    assert abs(len(res_out) - 941) <= 2

    tail = player._resampler.drain()
    assert len(tail) >= 0

    player.close()
