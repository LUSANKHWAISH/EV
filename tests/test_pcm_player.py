"""Unit and integration tests for WavReader, EQPlaybackEngine, and audio output lifecycle."""
from __future__ import annotations

import io
from pathlib import Path
import time
import wave
import numpy as np
import pytest

from prototypes.playback_eq.player import EQPlaybackEngine
from prototypes.playback_eq.wav_reader import WavReader


@pytest.fixture
def test_wav_16bit(tmp_path) -> Path:
    """Create a temporary 1-second 48kHz stereo 16-bit WAV file."""
    path = tmp_path / "test_stereo_48k.wav"
    fs = 48000
    t = np.arange(fs) / fs
    left = (0.2 * np.sin(2 * np.pi * 440 * t) * 32767.0).astype(np.int16)
    right = (0.2 * np.sin(2 * np.pi * 880 * t) * 32767.0).astype(np.int16)
    interleaved = np.column_stack([left, right]).ravel().tobytes()

    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(fs)
        w.writeframes(interleaved)

    return path


@pytest.fixture
def test_wav_mono_44k(tmp_path) -> Path:
    """Create a temporary 1-second 44.1kHz mono 16-bit WAV file."""
    path = tmp_path / "test_mono_44k.wav"
    fs = 44100
    t = np.arange(fs) / fs
    samples = (0.2 * np.sin(2 * np.pi * 1000 * t) * 32767.0).astype(np.int16)

    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(fs)
        w.writeframes(samples.tobytes())

    return path


class TestWavReader:
    """Verifies multi-format WAV decoding and streaming reads."""

    def test_stereo_wav_metadata_and_reading(self, test_wav_16bit):
        reader = WavReader(test_wav_16bit)
        assert reader.channels == 2
        assert reader.sample_rate == 48000
        assert reader.sample_width == 2
        assert reader.total_frames == 48000
        assert reader.duration_seconds == pytest.approx(1.0, abs=0.01)

        # Read 1024 frames
        chunk = reader.read_frames(1024)
        assert chunk.shape == (1024, 2)
        assert chunk.dtype == np.float32
        assert reader.tell() == 1024

        # Read remaining
        remaining = reader.read_frames(50000)
        assert remaining.shape == (48000 - 1024, 2)

        # EOF read
        eof_chunk = reader.read_frames(1024)
        assert eof_chunk.shape == (0, 2)

        reader.close()

    def test_mono_wav_upmixing_to_stereo(self, test_wav_mono_44k):
        reader = WavReader(test_wav_mono_44k)
        assert reader.channels == 1
        assert reader.sample_rate == 44100

        chunk = reader.read_frames(512, upmix_mono=True)
        assert chunk.shape == (512, 2), "Mono should be upmixed to 2 channels"
        np.testing.assert_allclose(chunk[:, 0], chunk[:, 1])

        reader.close()

    def test_seeking(self, test_wav_16bit):
        reader = WavReader(test_wav_16bit)
        reader.seek(24000)
        assert reader.tell() == 24000
        chunk = reader.read_frames(1000)
        assert len(chunk) == 1000
        assert reader.tell() == 25000
        reader.close()


class TestEQPlaybackEngine:
    """Verifies audio engine lifecycle, explicit playback start, threading, and cleanup."""

    def test_initial_state_is_safe_and_explicit(self, test_wav_16bit):
        engine = EQPlaybackEngine()
        assert engine.volume == 0.5  # Safe initial level (-6 dB)
        assert engine.is_playing is False
        assert engine.is_paused is False

        ok = engine.load(test_wav_16bit)
        assert ok is True
        assert engine.duration_seconds == pytest.approx(1.0, abs=0.01)
        # Must NOT auto-play on load
        assert engine.is_playing is False

        engine.close()

    def test_repeated_start_stop_cycles(self, test_wav_16bit):
        engine = EQPlaybackEngine()
        engine.load(test_wav_16bit)

        for _ in range(3):
            assert engine.play() is True
            time.sleep(0.08)
            assert engine.is_playing is True
            engine.stop()
            assert engine.is_playing is False
            assert engine.position_seconds == 0.0

        engine.close()

    def test_pause_and_resume_preserves_position(self, test_wav_16bit):
        engine = EQPlaybackEngine()
        engine.load(test_wav_16bit)

        engine.play()
        time.sleep(0.1)
        engine.pause()
        assert engine.is_paused is True

        pos = engine.position_seconds
        assert pos > 0.0

        # Resume
        engine.play()
        assert engine.is_paused is False
        assert engine.is_playing is True
        time.sleep(0.05)
        assert engine.position_seconds >= pos

        engine.stop()
        engine.close()

    def test_parameter_updates_during_active_playback(self, test_wav_16bit):
        engine = EQPlaybackEngine()
        engine.load(test_wav_16bit)
        engine.play()

        # Update volume
        engine.set_volume(0.4)
        assert engine.volume == 0.4

        # Update preamp
        engine.set_preamp(-3.0)
        assert engine.dsp.preamp_db == -3.0

        # Update EQ band
        engine.set_eq_band(hz=800, gain_db=6.0, q=1.5)
        assert engine.dsp.band.hz == 800
        assert engine.dsp.band.gain_db == 6.0

        # Toggle bypass
        engine.set_bypass(True)
        assert engine.dsp.bypass is True
        engine.set_bypass(False)
        assert engine.dsp.bypass is False

        time.sleep(0.1)
        engine.stop()
        engine.close()
