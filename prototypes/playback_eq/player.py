"""Isolated audio playback engine with DSP Equalizer and QAudioSink output."""
from __future__ import annotations

import math
from pathlib import Path
import threading
import time
from typing import Callable, Optional
import numpy as np
from PySide6.QtCore import QCoreApplication
from PySide6.QtMultimedia import QAudio, QAudioFormat, QAudioSink, QMediaDevices

from music.dsp import EqualizerDSP
from .wav_reader import WavReader


class EQPlaybackEngine:
    """Manages audio file decoding, DSP filtering, and real-time audio output."""

    def __init__(
        self,
        device=None,
        chunk_frames: int = 1024,
        on_state_change: Optional[Callable[[str], None]] = None,
        on_eof: Optional[Callable[[], None]] = None,
    ):
        self.chunk_frames = chunk_frames
        self.on_state_change = on_state_change
        self.on_eof = on_eof

        # Hardware audio sink configuration
        self._device = device or QMediaDevices.defaultAudioOutput()
        self._sink: Optional[QAudioSink] = None
        self._io_device = None
        self._volume: float = 0.5  # Safe initial level (-6 dB)

        # DSP chain
        self.dsp = EqualizerDSP(sample_rate=48000, channels=2)

        # File reader
        self._reader: Optional[WavReader] = None
        self._file_path: Optional[Path] = None

        # Threading and synchronization
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._lock = threading.Lock()

        # State tracking
        self._is_playing: bool = False
        self._is_paused: bool = False
        self._position_frames: int = 0
        self._sample_rate: int = 48000
        self._channels: int = 2
        self._bytes_per_sample: int = 4  # float32
        self._sample_format = QAudioFormat.SampleFormat.Float

        # Diagnostics & Underrun counters
        self.underrun_count: int = 0
        self.error_count: int = 0
        self.last_error_message: str = ""

    @property
    def is_playing(self) -> bool:
        return self._is_playing and not self._is_paused

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    @property
    def duration_seconds(self) -> float:
        if self._reader:
            return self._reader.duration_seconds
        return 0.0

    @property
    def position_seconds(self) -> float:
        if self._sample_rate > 0:
            return self._position_frames / self._sample_rate
        return 0.0

    @property
    def volume(self) -> float:
        return self._volume

    def set_volume(self, volume: float) -> None:
        """Set playback volume [0.0, 1.0]. Safe clipping prevention."""
        self._volume = float(np.clip(volume, 0.0, 1.0))
        if self._sink is not None:
            self._sink.setVolume(self._volume)

    def set_preamp(self, db: float) -> None:
        """Set equalizer preamp gain in dB."""
        self.dsp.set_preamp_db(db)

    def set_eq_band(self, hz: float, gain_db: float, q: float = 1.0, enabled: bool = True) -> None:
        """Adjust the peaking EQ band parameters."""
        self.dsp.set_eq_band(hz=hz, gain_db=gain_db, q=q, enabled=enabled)

    def set_bypass(self, bypass: bool) -> None:
        """Enable or disable EQ bypass."""
        self.dsp.set_bypass(bypass)

    def load(self, path: str | Path) -> bool:
        """Load a WAV file into the player without autoplaying."""
        self.stop()
        with self._lock:
            try:
                reader = WavReader(path)
                self._reader = reader
                self._file_path = Path(path).resolve()
                self._sample_rate = reader.sample_rate
                self._channels = 2  # Standardize on stereo output
                self._position_frames = 0

                # Configure DSP
                self.dsp.set_sample_rate(self._sample_rate)
                self.dsp.set_channels(self._channels)
                self.dsp.reset_state()

                # Reinitialize sink format
                self._init_sink()
                return True
            except Exception as e:
                self.last_error_message = str(e)
                self.error_count += 1
                return False

    def _init_sink(self) -> None:
        """Initialize QAudioSink with preferred native format."""
        if self._sink is not None:
            self._sink.stop()
            self._sink = None
            self._io_device = None

        fmt = QAudioFormat()
        fmt.setSampleRate(self._sample_rate)
        fmt.setChannelCount(self._channels)
        fmt.setSampleFormat(QAudioFormat.SampleFormat.Float)

        if not self._device.isFormatSupported(fmt):
            # Fallback to Int16 if float not supported
            fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
            self._sample_format = QAudioFormat.SampleFormat.Int16
            self._bytes_per_sample = 2
        else:
            self._sample_format = QAudioFormat.SampleFormat.Float
            self._bytes_per_sample = 4

        self._sink = QAudioSink(self._device, fmt)
        # Bounded device buffer: ~250ms of audio
        buffer_bytes = int(self._sample_rate * self._channels * self._bytes_per_sample * 0.25)
        self._sink.setBufferSize(buffer_bytes)
        self._sink.setVolume(self._volume)

    def play(self) -> bool:
        """Explicitly begin or resume playback."""
        if self._reader is None:
            return False

        if self._is_paused:
            self._is_paused = False
            self._pause_event.clear()
            if self._sink:
                self._sink.resume()
            self._notify_state("playing")
            return True

        if self._is_playing:
            return True

        if self._sink is None:
            self._init_sink()

        self._io_device = self._sink.start()
        if self._io_device is None or not self._io_device.isOpen():
            self.last_error_message = "Failed to start QAudioSink output device"
            self.error_count += 1
            return False

        self._stop_event.clear()
        self._pause_event.clear()
        self._is_playing = True
        self._is_paused = False

        self._thread = threading.Thread(target=self._feeder_worker, name="EQPlaybackWorker", daemon=True)
        self._thread.start()

        self._notify_state("playing")
        return True

    def pause(self) -> None:
        """Pause playback without clearing audio position."""
        if self._is_playing and not self._is_paused:
            self._is_paused = True
            self._pause_event.set()
            if self._sink:
                self._sink.suspend()
            self._notify_state("paused")

    def stop(self) -> None:
        """Stop playback and reset position to 0."""
        self._stop_event.set()
        self._pause_event.clear()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None

        with self._lock:
            if self._sink:
                self._sink.stop()
                self._io_device = None
            if self._reader:
                self._reader.seek(0)
            self._position_frames = 0
            self._is_playing = False
            self._is_paused = False
            self.dsp.reset_state()

        self._notify_state("stopped")

    def seek(self, position_seconds: float) -> None:
        """Seek playback to target position in seconds."""
        if self._reader is None:
            return

        with self._lock:
            target_frame = int(position_seconds * self._sample_rate)
            target_frame = max(0, min(target_frame, self._reader.total_frames))
            self._reader.seek(target_frame)
            self._position_frames = target_frame
            self.dsp.reset_state()

    def _feeder_worker(self) -> None:
        """Background streaming worker thread feeding PCM through DSP to QAudioSink."""
        bytes_per_frame = self._channels * self._bytes_per_sample
        chunk_bytes = self.chunk_frames * bytes_per_frame

        while not self._stop_event.is_set():
            if self._pause_event.is_set():
                time.sleep(0.01)
                continue

            if self._sink is None or self._io_device is None:
                break

            # Handle buffer capacity
            bytes_free = self._sink.bytesFree()
            if bytes_free < chunk_bytes:
                # Device buffer is sufficiently filled; sleep briefly to yield CPU
                time.sleep(0.003)
                continue

            # Read next PCM chunk from file
            with self._lock:
                if self._reader is None:
                    break
                pcm_raw = self._reader.read_frames(self.chunk_frames, upmix_mono=True)

            if len(pcm_raw) == 0:
                # End of file reached
                # Allow buffered audio to play out
                drain_seconds = min(0.3, self._sink.bufferSize() / (self._sample_rate * bytes_per_frame))
                time.sleep(drain_seconds)
                break

            # Apply real-time equalizer DSP outside GUI thread
            pcm_dsp = self.dsp.process(pcm_raw)

            # Convert to appropriate sink format
            if self._sample_format == QAudioFormat.SampleFormat.Float:
                out_bytes = pcm_dsp.astype(np.float32).tobytes()
            else:
                out_int16 = (np.clip(pcm_dsp, -1.0, 1.0) * 32767.0).astype(np.int16)
                out_bytes = out_int16.tobytes()

            # Push audio to hardware
            written = self._io_device.write(out_bytes)
            if written > 0:
                self._position_frames += len(pcm_raw)
            elif written < 0:
                self.error_count += 1
                self.last_error_message = "QIODevice write error"
                break

            # Check for underruns
            if self._sink.state() == QAudio.State.IdleState and self._position_frames > self.chunk_frames:
                self.underrun_count += 1

        # Playback loop terminated
        if not self._stop_event.is_set():
            # Natural EOF
            with self._lock:
                if self._sink:
                    self._sink.stop()
                    self._io_device = None
                self._is_playing = False
                self._is_paused = False
                if self._reader:
                    self._reader.seek(0)
                self._position_frames = 0
            self._notify_state("stopped")
            if self.on_eof:
                self.on_eof()

    def _notify_state(self, state: str) -> None:
        if self.on_state_change:
            try:
                self.on_state_change(state)
            except Exception:
                pass

    def close(self) -> None:
        """Release all audio device and file resources."""
        self.stop()
        with self._lock:
            if self._reader:
                self._reader.close()
                self._reader = None
            if self._sink:
                self._sink.stop()
                self._sink = None
