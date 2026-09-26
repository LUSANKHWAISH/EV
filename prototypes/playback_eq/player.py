"""Isolated audio playback engine with DSP Equalizer and QAudioSink output."""
from __future__ import annotations

import math
from pathlib import Path
import threading
import time
from typing import Callable, Optional, Sequence
import numpy as np
import scipy.signal as signal
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
        on_pcm_processed: Optional[Callable[[np.ndarray, int], None]] = None,
    ):
        self.chunk_frames = chunk_frames
        self.on_state_change = on_state_change
        self.on_eof = on_eof
        self.on_pcm_processed = on_pcm_processed

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
        self._sink_sample_rate: int = 48000
        self._channels: int = 2
        self._bytes_per_sample: int = 4  # float32
        self._sample_format = QAudioFormat.SampleFormat.Float

        # Resampling state
        self._resample_up: int = 1
        self._resample_down: int = 1
        self.resampled_frames_in: int = 0
        self.resampled_frames_out: int = 0

        # Frame & Byte accounting (strictly distinct)
        self.total_source_frames_read: int = 0
        self.total_bytes_accepted: int = 0
        self.total_frames_accepted: int = 0
        self.last_processed_usecs: int = 0

        # State and error history
        self.state_transitions: list[dict] = []
        self.error_transitions: list[dict] = []

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

    def set_band_gain(self, band_idx: int, gain_db: float) -> None:
        """Adjust a specific band's gain (-12 dB to +12 dB)."""
        self.dsp.set_band_gain(band_idx, gain_db)

    def get_band_gain(self, band_idx: int) -> float:
        return self.dsp.get_band_gain(band_idx)

    def set_all_gains(self, gains: Sequence[float]) -> None:
        """Set all 10 band gains simultaneously."""
        self.dsp.set_all_gains(gains)

    def get_all_gains(self) -> list[float]:
        return self.dsp.get_all_gains()

    def reset_flat(self) -> None:
        """Reset all 10 bands and preamp to 0 dB flat response."""
        self.dsp.reset_flat()

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

    @property
    def headroom_db(self) -> float:
        return self.dsp.headroom_db

    @property
    def is_clipping(self) -> bool:
        return self.dsp.is_clipping

    def set_device(self, device) -> None:
        """Update audio output device."""
        with self._lock:
            self._device = device or QMediaDevices.defaultAudioOutput()
            if self._sink is not None:
                was_playing = self.is_playing
                self._init_sink()
                if was_playing:
                    self.play()

    def _on_sink_state_changed(self, state: QAudio.State) -> None:
        self.state_transitions.append({
            "timestamp": time.time(),
            "state": str(state),
        })
        if self._sink and self._sink.error() != QAudio.Error.NoError:
            self.error_transitions.append({
                "timestamp": time.time(),
                "error": str(self._sink.error()),
            })

    def _init_sink(self) -> None:
        """Initialize QAudioSink with preferred native format, with automatic resampling if needed."""
        if self._sink is not None:
            self._sink.stop()
            self._sink = None
            self._io_device = None

        if self._device is None or self._device.isNull():
            return

        fmt = QAudioFormat()
        fmt.setSampleRate(self._sample_rate)
        fmt.setChannelCount(self._channels)
        fmt.setSampleFormat(QAudioFormat.SampleFormat.Float)

        # Check format compatibility
        target_rate = self._sample_rate
        if not self._device.isFormatSupported(fmt):
            # Try Int16 with target rate
            fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
            if not self._device.isFormatSupported(fmt):
                # Device cannot accept source sample rate; fallback to preferred rate
                pref = self._device.preferredFormat()
                target_rate = pref.sampleRate() if pref.sampleRate() > 0 else 44100
                fmt.setSampleRate(target_rate)
                fmt.setSampleFormat(QAudioFormat.SampleFormat.Float)
                if not self._device.isFormatSupported(fmt):
                    fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)

        if fmt.sampleFormat() == QAudioFormat.SampleFormat.Int16:
            self._sample_format = QAudioFormat.SampleFormat.Int16
            self._bytes_per_sample = 2
        else:
            self._sample_format = QAudioFormat.SampleFormat.Float
            self._bytes_per_sample = 4

        self._sink_sample_rate = fmt.sampleRate()
        self._sink = QAudioSink(self._device, fmt)
        self._sink.stateChanged.connect(self._on_sink_state_changed)

        # Calculate rational resampling factors if sink rate != source rate
        if self._sink_sample_rate != self._sample_rate and self._sink_sample_rate > 0 and self._sample_rate > 0:
            gcd = math.gcd(int(self._sample_rate), int(self._sink_sample_rate))
            self._resample_up = int(self._sink_sample_rate // gcd)
            self._resample_down = int(self._sample_rate // gcd)
        else:
            self._resample_up = 1
            self._resample_down = 1

        # Bounded device buffer: ~250ms of audio at sink rate
        buffer_bytes = int(self._sink_sample_rate * self._channels * self._bytes_per_sample * 0.25)
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

        if self._sink is None:
            self.last_error_message = "No valid audio output device available"
            self.error_count += 1
            return False

        self._io_device = self._sink.start()
        if self._io_device is None or not self._io_device.isOpen():
            self.last_error_message = "Failed to start QAudioSink output device"
            self.error_count += 1
            return False

        # Reset counters for fresh stream
        self.total_source_frames_read = 0
        self.total_bytes_accepted = 0
        self.total_frames_accepted = 0
        self.resampled_frames_in = 0
        self.resampled_frames_out = 0
        self.last_processed_usecs = 0
        self.state_transitions.clear()
        self.error_transitions.clear()

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
                try:
                    self.last_processed_usecs = max(self.last_processed_usecs, self._sink.processedUSecs())
                except (RuntimeError, AttributeError):
                    pass
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
            try:
                bytes_free = self._sink.bytesFree()
                self.last_processed_usecs = max(self.last_processed_usecs, self._sink.processedUSecs())
            except (RuntimeError, AttributeError):
                break

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
                try:
                    if self._sink:
                        self.last_processed_usecs = max(self.last_processed_usecs, self._sink.processedUSecs())
                    drain_seconds = min(0.3, self._sink.bufferSize() / (self._sink_sample_rate * bytes_per_frame))
                    time.sleep(drain_seconds)
                    if self._sink:
                        self.last_processed_usecs = max(self.last_processed_usecs, self._sink.processedUSecs())
                except (RuntimeError, AttributeError):
                    pass
                break

            self.total_source_frames_read += len(pcm_raw)

            # Apply real-time equalizer DSP outside GUI thread
            pcm_dsp = self.dsp.process(pcm_raw)

            if self.on_pcm_processed is not None:
                try:
                    self.on_pcm_processed(pcm_dsp, self._sample_rate)
                except Exception:
                    pass

            # Rational polyphase resampling if sink sample rate differs from source
            if self._resample_up != self._resample_down:
                self.resampled_frames_in += len(pcm_dsp)
                pcm_out = signal.resample_poly(pcm_dsp, self._resample_up, self._resample_down, axis=0).astype(np.float32)
                self.resampled_frames_out += len(pcm_out)
            else:
                pcm_out = pcm_dsp

            # Convert to appropriate sink format
            if self._sample_format == QAudioFormat.SampleFormat.Float:
                out_bytes = pcm_out.astype(np.float32).tobytes()
            else:
                out_int16 = (np.clip(pcm_out, -1.0, 1.0) * 32767.0).astype(np.int16)
                out_bytes = out_int16.tobytes()

            # Push audio to hardware with complete write guarantee
            bytes_to_write = out_bytes
            while len(bytes_to_write) > 0 and not self._stop_event.is_set():
                try:
                    written = self._io_device.write(bytes_to_write)
                except (RuntimeError, AttributeError):
                    written = -1

                if written > 0:
                    self.total_bytes_accepted += written
                    self.total_frames_accepted += (written // bytes_per_frame)
                    bytes_to_write = bytes_to_write[written:]
                    if len(bytes_to_write) > 0:
                        time.sleep(0.002)
                elif written == 0:
                    time.sleep(0.002)
                else:
                    self.error_count += 1
                    self.last_error_message = "QIODevice write error"
                    break

            self._position_frames += len(pcm_raw)

            # Check for underruns
            try:
                if self._sink.state() == QAudio.State.IdleState and self._position_frames > self.chunk_frames:
                    self.underrun_count += 1
            except (RuntimeError, AttributeError):
                break

        # Playback loop terminated
        if not self._stop_event.is_set():
            # Natural EOF
            with self._lock:
                try:
                    if self._sink:
                        self.last_processed_usecs = max(self.last_processed_usecs, self._sink.processedUSecs())
                        self._sink.stop()
                except (RuntimeError, AttributeError):
                    pass
                self._sink = None
                self._io_device = None
                self._is_playing = False
                self._is_paused = False
                if self._reader:
                    self._reader.seek(0)
                self._position_frames = 0
            self._notify_state("stopped")
            if self.on_eof:
                try:
                    self.on_eof()
                except Exception:
                    pass

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
