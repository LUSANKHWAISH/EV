"""
core/voice_manager.py - E.V. Voice Runtime Integration Foundation (Task 014E-1)

Central coordinator connecting:
  - Audio Capture (EVAudioCaptureProvider, SoundDeviceAudioCaptureProvider)
  - Audio Ring Buffer (AudioRingBuffer)
  - Wake-Word Detection (EVWakeWordProvider)
  - Voice Activity Detection (EVVADProvider)
  - Utterance Assembly (Pre-roll, speech detection, silence timeout, speech floor)
  - ASR (EVASRProvider)
  - Command Submission (EVOrchestrator.submit_command)
  - TTS Integration (EVTTSManager)
  - Barge-In / STOP Detection (EVBargeInStopDetector)

Security Invariants:
  - Untrusted text input boundary: only calls EVOrchestrator.submit_command(...).
  - Never directly invokes EVAgent, EVRiskEngine, EVTaskQueue, PowerShell,
    transactions, rollback, or Windows execution tools.
  - Zero execution authority, zero autonomy level changes, zero GOD MODE.
  - Raw audio is memory-only: zero disk writes, zero WAV/PCM files, zero telemetry.
"""

from __future__ import annotations

import logging
import math
import queue
import re
import threading
import time
from enum import Enum
from typing import Any, Callable, List, Optional, Sequence, Union

from core.asr import ASRResult, EVASRProvider
from core.models import EVEventType, EVState
from core.voice_capture import (
    DEFAULT_BYTES_PER_FRAME,
    DEFAULT_CHANNELS,
    DEFAULT_SAMPLE_RATE,
    DEFAULT_SAMPLES_PER_FRAME,
    DEFAULT_SAMPLE_WIDTH,
    AudioFrame,
    AudioRingBuffer,
    EVAudioCaptureProvider,
)
from core.voice_vad import EVVADProvider, VADResult
from core.voice_wakeword import EVBargeInStopDetector, EVWakeWordProvider, WakeWordResult
from core.wake_verifier import EVWakeVerifier, WakeVerificationResult

logger = logging.getLogger(__name__)

# Canonical timing & configuration constants
DEFAULT_PRE_ROLL_SECONDS: float = 0.75  # ~750 ms default pre-roll
DEFAULT_SILENCE_TIMEOUT_SECONDS: float = 1.1  # ~1.1 s silence terminates utterance
DEFAULT_MAX_UTTERANCE_SECONDS: float = 8.0  # 8.0 s max utterance window
DEFAULT_MIN_SPEECH_SECONDS: float = 0.3  # ~300 ms minimum speech floor
DEFAULT_INITIAL_SILENCE_TIMEOUT_SECONDS: float = 3.0  # Max silence waiting for speech
DEFAULT_WAKE_PHRASE: str = "Hey EV"

from core.paths import get_wakeword_model_dir

# Stage-2 Two-Stage Wake Verification Configuration
ENABLE_STAGE2_WAKE_VERIFICATION: bool = True
DEFAULT_STAGE1_WAKEWORD_MODEL: str = str(get_wakeword_model_dir() / "candidates" / "hey_ev_human_v2.onnx")
DEFAULT_STAGE1_THRESHOLD: float = 0.50
DEFAULT_STAGE2_VERIFICATION_BUFFER_SECONDS: float = 2.0  # ~2.0s rolling audio for Stage-2 phrase check
DEFAULT_STAGE2_TIMEOUT_SECONDS: float = 2.5


# ============================================================================
# Voice State Enum
# ============================================================================
class VoiceState(str, Enum):
    """Voice runtime local state machine."""
    IDLE = "IDLE"
    VERIFYING_WAKE = "VERIFYING_WAKE"
    LISTENING = "LISTENING"
    TRANSCRIBING = "TRANSCRIBING"
    PROCESSING = "PROCESSING"
    SPEAKING = "SPEAKING"
    PAUSED = "PAUSED"
    ERROR = "ERROR"


# ============================================================================
# Wake Phrase Stripping Utility
# ============================================================================
def strip_wake_phrase(transcript: str, wake_phrases: Sequence[str] = (DEFAULT_WAKE_PHRASE,)) -> str:
    """
    Conservatively strip a configured wake phrase from the beginning of a transcript.

    Rules:
      - Case-insensitive prefix matching.
      - Matches optional trailing punctuation (,, :, !, -, .) and whitespace.
      - Never performs global substring replacement (e.g. "open EV documentation" remains unchanged).
      - Returns cleaned, stripped command string.
    """
    if not transcript or not isinstance(transcript, str):
        return ""

    trimmed = transcript.strip()
    for phrase in wake_phrases:
        if not phrase or not phrase.strip():
            continue
        cleaned_phrase = phrase.strip()
        pattern = r"(?i)^" + re.escape(cleaned_phrase) + r"[\s,:\.!\-]*"
        if re.match(pattern, trimmed):
            return re.sub(pattern, "", trimmed, count=1).strip()

    return trimmed


# ============================================================================
# Real Windows Microphone Provider (SoundDevice / PortAudio)
# ============================================================================
class SoundDeviceAudioCaptureProvider(EVAudioCaptureProvider):
    """
    Real Windows microphone capture provider using sounddevice / PortAudio.

    Delivers canonical 16 kHz mono 16-bit PCM AudioFrames (30 ms, 480 samples, 960 bytes).
    Thread-safe bounded queue ensures zero memory leaks if reader falls behind.
    """

    def __init__(
        self,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        channels: int = DEFAULT_CHANNELS,
        block_size: int = DEFAULT_SAMPLES_PER_FRAME,
        device: Optional[Union[int, str]] = None,
        max_queue_frames: int = 100,
    ) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self.block_size = block_size
        self.device = device
        self._max_queue_frames = max(10, max_queue_frames)
        self._frame_queue: queue.Queue = queue.Queue(maxsize=self._max_queue_frames)
        self._stream: Optional[Any] = None
        self._is_active: bool = False
        self._lock = threading.Lock()

    @property
    def provider_name(self) -> str:
        """Human-readable provider identifier."""
        return "sounddevice"

    def is_running(self) -> bool:
        """Return True if capture stream is currently active."""
        with self._lock:
            return self._is_active

    def is_available(self) -> bool:
        """Check if sounddevice and underlying PortAudio host are available."""
        try:
            import sounddevice as sd  # type: ignore
            # Test query devices without raising
            sd.query_devices()
            return True
        except Exception:
            return False

    def start(self) -> None:
        """Open and start the microphone capture stream. Idempotent."""
        with self._lock:
            if self._is_active:
                return

            try:
                import sounddevice as sd  # type: ignore
            except ImportError as err:
                raise RuntimeError("sounddevice is not installed in the environment") from err

            def _audio_callback(indata: Any, frames: int, time_info: Any, status: Any) -> None:
                if status:
                    logger.warning("SoundDevice status warning: %s", status)
                try:
                    raw_bytes = bytes(indata)
                    frame = AudioFrame(
                        data=raw_bytes,
                        sample_rate=self.sample_rate,
                        channels=self.channels,
                        sample_width=DEFAULT_SAMPLE_WIDTH,
                        timestamp=time.monotonic(),
                    )
                    try:
                        self._frame_queue.put_nowait(frame)
                    except queue.Full:
                        # Drop oldest frame to maintain real-time bounded queue
                        try:
                            self._frame_queue.get_nowait()
                            self._frame_queue.put_nowait(frame)
                        except Exception:
                            pass
                except Exception as exc:
                    logger.debug("Error in sounddevice callback: %s", exc)

            try:
                self._stream = sd.RawInputStream(
                    samplerate=self.sample_rate,
                    channels=self.channels,
                    dtype="int16",
                    blocksize=self.block_size,
                    device=self.device,
                    callback=_audio_callback,
                )
                self._stream.start()
                self._is_active = True
                logger.info("SoundDeviceAudioCaptureProvider: microphone stream started")
            except Exception as exc:
                self._is_active = False
                self._stream = None
                raise RuntimeError(f"Failed to start sounddevice microphone capture: {exc}") from exc

    def stop(self) -> None:
        """Stop and close the microphone stream. Idempotent."""
        with self._lock:
            if not self._is_active:
                return
            self._is_active = False

            if self._stream is not None:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception as exc:
                    logger.debug("Error closing sounddevice stream: %s", exc)
                finally:
                    self._stream = None

            # Clear frame queue
            while not self._frame_queue.empty():
                try:
                    self._frame_queue.get_nowait()
                except Exception:
                    break

            logger.info("SoundDeviceAudioCaptureProvider: microphone stream stopped")

    def is_active(self) -> bool:
        """Return True if capture stream is running."""
        with self._lock:
            return self._is_active

    def read_frame(self, timeout: Optional[float] = None) -> Optional[AudioFrame]:
        """Read the next captured AudioFrame from the queue."""
        if not self._is_active and self._frame_queue.empty():
            return None
        try:
            return self._frame_queue.get(timeout=timeout)
        except queue.Empty:
            return None


# ============================================================================
# EVVoiceManager
# ============================================================================
class EVVoiceManager:
    """
    Central coordinator connecting:
      - Audio Capture
      - Ring Buffer
      - Wake-Word Detection
      - VAD
      - Utterance Assembly
      - ASR
      - EVOrchestrator
      - TTS
      - Barge-in / STOP detection

    Architectural Boundary:
      VoiceManager receives audio, detects wake words, assembles utterances,
      transcribes via ASR, strips wake phrases, and forwards untrusted text
      strictly to `orchestrator.submit_command(...)`.
    """

    def __init__(
        self,
        capture_provider: EVAudioCaptureProvider,
        wake_word_provider: EVWakeWordProvider,
        vad_provider: EVVADProvider,
        asr_provider: EVASRProvider,
        orchestrator: Any,
        tts_manager: Optional[Any] = None,
        barge_in_detector: Optional[EVBargeInStopDetector] = None,
        event_bus: Optional[Any] = None,
        ring_buffer: Optional[AudioRingBuffer] = None,
        wake_verifier: Optional[EVWakeVerifier] = None,
        enable_stage2_verification: bool = ENABLE_STAGE2_WAKE_VERIFICATION,
        stage2_verification_buffer_seconds: float = DEFAULT_STAGE2_VERIFICATION_BUFFER_SECONDS,
        stage2_timeout_seconds: float = DEFAULT_STAGE2_TIMEOUT_SECONDS,
        wake_phrases: Sequence[str] = (DEFAULT_WAKE_PHRASE,),
        pre_roll_seconds: float = DEFAULT_PRE_ROLL_SECONDS,
        silence_timeout_seconds: float = DEFAULT_SILENCE_TIMEOUT_SECONDS,
        max_utterance_seconds: float = DEFAULT_MAX_UTTERANCE_SECONDS,
        min_speech_seconds: float = DEFAULT_MIN_SPEECH_SECONDS,
        initial_silence_timeout_seconds: float = DEFAULT_INITIAL_SILENCE_TIMEOUT_SECONDS,
        on_state_change: Optional[Callable[[VoiceState], None]] = None,
        on_transcript: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ) -> None:
        if capture_provider is None:
            raise ValueError("capture_provider is required")
        if wake_word_provider is None:
            raise ValueError("wake_word_provider is required")
        if vad_provider is None:
            raise ValueError("vad_provider is required")
        if asr_provider is None:
            raise ValueError("asr_provider is required")
        if orchestrator is None:
            raise ValueError("orchestrator is required")

        self._capture_provider = capture_provider
        self._wake_word_provider = wake_word_provider
        self._vad_provider = vad_provider
        self._asr_provider = asr_provider
        self._orchestrator = orchestrator
        self._tts_manager = tts_manager
        self._barge_in_detector = barge_in_detector
        self._event_bus = event_bus

        # Stage-2 Two-Stage Phrase Verification
        self._wake_verifier = wake_verifier
        self._enable_stage2_verification = enable_stage2_verification
        self._stage2_verification_buffer_seconds = max(0.1, stage2_verification_buffer_seconds)
        self._stage2_timeout_seconds = max(0.1, stage2_timeout_seconds)
        self._verification_epoch: int = 0
        self._interaction_epoch: int = 0
        self._active_verification_worker: Optional[threading.Thread] = None
        self._last_verification_result: Optional[WakeVerificationResult] = None
        self._total_verifications_attempted: int = 0
        self._total_verifications_passed: int = 0
        self._total_verifications_rejected: int = 0

        # Timing configurations
        self._wake_phrases = list(wake_phrases) if wake_phrases else [DEFAULT_WAKE_PHRASE]
        self._pre_roll_seconds = max(0.03, pre_roll_seconds)
        self._silence_timeout_seconds = max(0.05, silence_timeout_seconds)
        self._max_utterance_seconds = max(0.1, max_utterance_seconds)
        self._min_speech_seconds = max(0.03, min_speech_seconds)
        self._initial_silence_timeout_seconds = max(0.05, initial_silence_timeout_seconds)

        # Callbacks
        self._on_state_change = on_state_change
        self._on_transcript = on_transcript
        self._on_error = on_error

        # Ring buffer for rolling history (~3s default)
        self._ring_buffer = ring_buffer or AudioRingBuffer(max_frames=100)

        # Concurrency & state management
        self._lock = threading.RLock()
        self._state: VoiceState = VoiceState.IDLE
        self._is_running: bool = False
        self._stop_event = threading.Event()
        self._paused_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None

        # Active utterance assembly state (strictly memory-only)
        self._active_utterance_frames: List[AudioFrame] = []
        self._speech_frames_count: int = 0
        self._consecutive_silence_frames: int = 0
        self._initial_silence_frames: int = 0
        self._has_speech_started: bool = False
        self._utterance_started_ts: float = 0.0

        # Telemetry & Diagnostics
        self._last_error: Optional[str] = None
        self._last_transcript: Optional[str] = None
        self._total_utterances_processed: int = 0
        self._total_commands_submitted: int = 0

    # ------------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------------
    @property
    def state(self) -> VoiceState:
        with self._lock:
            return self._state

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._is_running

    @property
    def is_paused(self) -> bool:
        return self._paused_event.is_set()

    @property
    def last_error(self) -> Optional[str]:
        with self._lock:
            return self._last_error

    @property
    def last_transcript(self) -> Optional[str]:
        with self._lock:
            return self._last_transcript

    @property
    def total_utterances_processed(self) -> int:
        with self._lock:
            return self._total_utterances_processed

    @property
    def total_commands_submitted(self) -> int:
        with self._lock:
            return self._total_commands_submitted

    @property
    def capture_provider(self) -> EVAudioCaptureProvider:
        return self._capture_provider

    @property
    def wake_word_provider(self) -> EVWakeWordProvider:
        return self._wake_word_provider

    @property
    def wake_verifier(self) -> Optional[EVWakeVerifier]:
        return self._wake_verifier

    @property
    def enable_stage2_verification(self) -> bool:
        return self._enable_stage2_verification

    @property
    def last_verification_result(self) -> Optional[WakeVerificationResult]:
        with self._lock:
            return self._last_verification_result

    @property
    def total_verifications_attempted(self) -> int:
        with self._lock:
            return self._total_verifications_attempted

    @property
    def total_verifications_passed(self) -> int:
        with self._lock:
            return self._total_verifications_passed

    @property
    def total_verifications_rejected(self) -> int:
        with self._lock:
            return self._total_verifications_rejected

    @property
    def vad_provider(self) -> EVVADProvider:
        return self._vad_provider

    @property
    def asr_provider(self) -> EVASRProvider:
        return self._asr_provider

    @property
    def ring_buffer(self) -> AudioRingBuffer:
        return self._ring_buffer

    # ------------------------------------------------------------------------
    # Lifecycle Operations
    # ------------------------------------------------------------------------
    def start(self) -> None:
        """Start voice capture and the background processing worker. Idempotent."""
        with self._lock:
            if self._is_running:
                logger.debug("EVVoiceManager: already running, start() is no-op")
                return

            self._stop_event.clear()
            self._paused_event.clear()
            self._last_error = None

            try:
                self._capture_provider.start()
            except Exception as exc:
                self._state = VoiceState.ERROR
                self._last_error = f"Failed to start capture provider: {exc}"
                logger.error("EVVoiceManager: %s", self._last_error)
                if self._on_error:
                    self._on_error(self._last_error)
                raise

            self._is_running = True
            self._set_state(VoiceState.IDLE)

            self._worker_thread = threading.Thread(
                target=self._worker_loop,
                name="EVVoiceManagerWorker",
                daemon=True,
            )
            self._worker_thread.start()
            logger.info("EVVoiceManager: voice runtime started successfully")

    def stop(self, timeout: float = 2.0) -> None:
        """Stop voice capture, terminate worker loop, and clean up buffers. Idempotent."""
        with self._lock:
            was_running = self._is_running
            self._is_running = False
            self._stop_event.set()

        # Stop hardware/mock capture provider
        try:
            self._capture_provider.stop()
        except Exception as exc:
            logger.debug("EVVoiceManager: error stopping capture provider: %s", exc)

        # Wait for worker thread to exit cleanly
        if self._worker_thread is not None and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=timeout)
            if self._worker_thread.is_alive():
                logger.warning("EVVoiceManager: worker thread did not exit within %.1fs", timeout)
            self._worker_thread = None

        with self._lock:
            self._verification_epoch += 1
            self._interaction_epoch += 1
            self._active_utterance_frames.clear()
            self._ring_buffer.clear()
            self._wake_word_provider.reset()
            self._vad_provider.reset()
            if self._wake_verifier is not None:
                try:
                    self._wake_verifier.reset()
                except Exception:
                    pass
            if self._barge_in_detector:
                self._barge_in_detector.reset()
            self._set_state(VoiceState.IDLE)

        logger.info("EVVoiceManager: voice runtime stopped cleanly")

    def pause(self) -> None:
        """Pause frame processing. Capture remains active, but input is ignored. Idempotent."""
        with self._lock:
            if not self._is_running or self._paused_event.is_set():
                return
            self._verification_epoch += 1
            self._interaction_epoch += 1
            self._paused_event.set()
            self._active_utterance_frames.clear()
            self._set_state(VoiceState.PAUSED)
            logger.info("EVVoiceManager: voice processing paused")

    def resume(self) -> None:
        """Resume frame processing after pause. Idempotent."""
        with self._lock:
            if not self._is_running or not self._paused_event.is_set():
                return
            self._paused_event.clear()
            self._set_state(VoiceState.IDLE)
            logger.info("EVVoiceManager: voice processing resumed")

    # ------------------------------------------------------------------------
    # Internal State & Events
    # ------------------------------------------------------------------------
    def _set_state(self, new_state: VoiceState) -> None:
        """Update internal state and publish notifications."""
        old_state = self._state
        self._state = new_state
        if old_state != new_state:
            logger.debug("EVVoiceManager: state %s -> %s", old_state.value, new_state.value)
            if self._on_state_change:
                try:
                    self._on_state_change(new_state)
                except Exception as exc:
                    logger.debug("EVVoiceManager: on_state_change callback error: %s", exc)
            if self._event_bus is not None:
                try:
                    self._event_bus.publish(
                        event_type=EVEventType.VOICE_STATE_CHANGED,
                        source="voice_manager",
                        data={
                            "voice_state": new_state.value,
                            "old_state": old_state.value,
                        },
                    )
                except Exception as exc:
                    logger.debug("EVVoiceManager: event_bus publish VOICE_STATE_CHANGED error: %s", exc)

    # ------------------------------------------------------------------------
    # Worker Thread Loop
    # ------------------------------------------------------------------------
    def _worker_loop(self) -> None:
        """Background thread reading frames from capture provider and processing them."""
        logger.debug("EVVoiceManager: worker loop started")
        while not self._stop_event.is_set():
            if self._paused_event.is_set():
                time.sleep(0.02)
                continue

            frame = None
            if hasattr(self._capture_provider, "read_frame"):
                try:
                    frame = self._capture_provider.read_frame(timeout=0.05)
                except Exception as exc:
                    with self._lock:
                        self._set_state(VoiceState.ERROR)
                        self._last_error = f"Capture read error: {exc}"
                    logger.error("EVVoiceManager: %s", self._last_error)
                    if self._on_error:
                        self._on_error(self._last_error)
                    break
            elif hasattr(self._capture_provider, "read"):
                try:
                    frame = self._capture_provider.read()
                except Exception as exc:
                    with self._lock:
                        self._set_state(VoiceState.ERROR)
                        self._last_error = f"Capture read error: {exc}"
                    logger.error("EVVoiceManager: %s", self._last_error)
                    if self._on_error:
                        self._on_error(self._last_error)
                    break
            else:
                time.sleep(0.02)
                continue

            if frame is None:
                continue

            try:
                self.process_frame(frame)
            except Exception as exc:
                logger.error("EVVoiceManager: unexpected error processing frame: %s", exc, exc_info=True)

        logger.debug("EVVoiceManager: worker loop terminated")

    # ------------------------------------------------------------------------
    # Frame Processing Engine (Callable synchronously or via worker)
    # ------------------------------------------------------------------------
    def process_frame(self, frame: AudioFrame) -> None:
        """
        Process a single canonical AudioFrame through the voice pipeline.
        Exposed publicly for deterministic unit tests and internal worker calls.
        """
        if not isinstance(frame, AudioFrame):
            raise TypeError(f"Expected AudioFrame, got {type(frame).__name__}")

        with self._lock:
            if self._paused_event.is_set():
                return

            # Step 1: Barge-in / STOP detection evaluated on EVERY frame
            if self._barge_in_detector is not None:
                try:
                    if self._barge_in_detector.process_frame(frame):
                        self._handle_stop_barge_in()
                        return
                except Exception as exc:
                    logger.debug("EVVoiceManager: barge-in detector error: %s", exc)

            # Step 2: Push frame to rolling history ring buffer
            self._ring_buffer.write(frame)

            # Step 2.5: Acoustic self-trigger protection: suppress wake detection and command capture while TTS is speaking
            if self._tts_manager is not None and getattr(self._tts_manager, "is_speaking", False):
                return

            # Step 3: State-dependent processing
            if self._state == VoiceState.IDLE:
                self._handle_idle_frame(frame)
            elif self._state == VoiceState.VERIFYING_WAKE:
                # Frame continues buffering in ring buffer; Stage 1 wake word evaluation is
                # suppressed to prevent duplicate candidate triggers for the same acoustic event.
                pass
            elif self._state == VoiceState.LISTENING:
                self._handle_listening_frame(frame)
            elif self._state in (VoiceState.TRANSCRIBING, VoiceState.PROCESSING, VoiceState.SPEAKING):
                # Audio continues buffering in ring buffer during ASR inference and response output
                pass

    def _handle_idle_frame(self, frame: AudioFrame) -> None:
        """Evaluate wake-word detector on frame while in IDLE state."""
        try:
            # Wake-word detection operates independently of VAD gating
            wake_res: Optional[WakeWordResult] = self._wake_word_provider.process_frame(frame)
        except Exception as exc:
            logger.warning("EVVoiceManager: wake provider error: %s", exc)
            return

        if wake_res is not None and wake_res.detected:
            if self._enable_stage2_verification and self._wake_verifier is not None:
                logger.info(
                    "EVVoiceManager: Stage 1 candidate detected '%s' (conf=%.2f) -> VERIFYING_WAKE",
                    wake_res.keyword, wake_res.confidence
                )
                # Extract verification audio window (~2.0s rolling buffer)
                buffer_frame_count = int(math.ceil(self._stage2_verification_buffer_seconds / 0.030))
                verification_frames = self._ring_buffer.peek_recent(buffer_frame_count)
                if not verification_frames:
                    verification_frames = [frame]

                self._set_state(VoiceState.VERIFYING_WAKE)
                self._verification_epoch += 1
                epoch = self._verification_epoch
                self._total_verifications_attempted += 1

                t = threading.Thread(
                    target=self._run_stage2_verification,
                    args=(list(verification_frames), epoch),
                    name="EVVoiceVerificationWorker",
                    daemon=True,
                )
                self._active_verification_worker = t
                t.start()
            else:
                logger.info("EVVoiceManager: wake word '%s' detected (conf=%.2f) -> LISTENING",
                            wake_res.keyword, wake_res.confidence)
                self._transition_to_listening()

    def _run_stage2_verification(self, frames: List[AudioFrame], epoch: int) -> None:
        """
        Background worker executing Stage-2 phrase verification on candidate wake frames.
        Zero execution authority. Only produces an immutable WakeVerificationResult.
        """
        t0 = time.monotonic()
        try:
            res: WakeVerificationResult = self._wake_verifier.verify_phrase(frames)
        except Exception as exc:
            logger.error("EVVoiceManager: Stage-2 verifier exception: %s", exc)
            res = WakeVerificationResult(
                verified=False,
                confidence=0.0,
                reason=f"VERIFIER_EXCEPTION_{type(exc).__name__}",
                raw_transcript="",
                latency_ms=(time.monotonic() - t0) * 1000.0,
                provider=getattr(self._wake_verifier, "provider_name", "unknown"),
                timestamp=time.monotonic(),
            )

        with self._lock:
            # Check epoch & state validity (cancellation / stale result protection)
            if (
                self._stop_event.is_set()
                or self._paused_event.is_set()
                or self._verification_epoch != epoch
                or self._state != VoiceState.VERIFYING_WAKE
            ):
                logger.debug(
                    "EVVoiceManager: Discarding stale Stage-2 result (epoch=%d, current=%d, state=%s)",
                    epoch, self._verification_epoch, self._state.value
                )
                return

            self._last_verification_result = res

            if res.verified:
                self._total_verifications_passed += 1
                logger.info(
                    "EVVoiceManager: Stage-2 VERIFIED '%s' (conf=%.2f, reason='%s', lat=%.1fms) -> LISTENING",
                    res.raw_transcript, res.confidence, res.reason, res.latency_ms
                )
                self._transition_to_listening()
            else:
                self._total_verifications_rejected += 1
                logger.info(
                    "EVVoiceManager: Stage-2 REJECTED '%s' (conf=%.2f, reason='%s', lat=%.1fms) -> IDLE",
                    res.raw_transcript, res.confidence, res.reason, res.latency_ms
                )
                self._set_state(VoiceState.IDLE)

    def _transition_to_listening(self) -> None:
        """Transition from IDLE/VERIFYING_WAKE to LISTENING and assemble pre-roll audio."""
        pre_roll_count = int(math.ceil(self._pre_roll_seconds / 0.030))
        recent_frames = self._ring_buffer.peek_recent(pre_roll_count)

        # Seed utterance collection with rolling history pre-roll
        self._active_utterance_frames = list(recent_frames)

        self._speech_frames_count = 0
        self._consecutive_silence_frames = 0
        self._initial_silence_frames = 0
        self._has_speech_started = False
        self._utterance_started_ts = time.monotonic()

        # Reset VAD for fresh utterance detection
        try:
            self._vad_provider.reset()
        except Exception as exc:
            logger.debug("EVVoiceManager: VAD reset error: %s", exc)

        self._set_state(VoiceState.LISTENING)

        # Notify event bus of global state change if available
        if self._event_bus is not None:
            try:
                self._event_bus.set_state(EVState.LISTENING)
            except Exception as exc:
                logger.debug("EVVoiceManager: event_bus.set_state error: %s", exc)

    def _handle_listening_frame(self, frame: AudioFrame) -> None:
        """Accumulate frames and monitor VAD speech/silence endpoints."""
        self._active_utterance_frames.append(frame)

        # Process frame through VAD
        try:
            vad_res: VADResult = self._vad_provider.process_frame(frame)
        except Exception as exc:
            logger.warning("EVVoiceManager: VAD error during listening: %s", exc)
            vad_res = VADResult(
                is_speech=False, confidence=0.0, energy=0.0, timestamp=frame.timestamp
            )

        if vad_res.is_speech:
            self._has_speech_started = True
            self._speech_frames_count += 1
            self._consecutive_silence_frames = 0
        else:
            if self._has_speech_started:
                self._consecutive_silence_frames += 1
            else:
                self._initial_silence_frames += 1

        # Endpoint Condition 1: Initial silence timeout (user woke E.V. but said nothing)
        initial_silence_sec = self._initial_silence_frames * 0.030
        if not self._has_speech_started and initial_silence_sec >= self._initial_silence_timeout_seconds:
            logger.info("EVVoiceManager: no speech detected after wake word (%.1fs timeout), aborting",
                        initial_silence_sec)
            self._abort_utterance()
            return

        # Endpoint Condition 2: Max utterance duration ceiling reached
        total_duration_sec = len(self._active_utterance_frames) * 0.030
        if total_duration_sec >= self._max_utterance_seconds:
            logger.info("EVVoiceManager: max utterance duration reached (%.1fs), finalizing", total_duration_sec)
            self._finalize_utterance()
            return

        # Endpoint Condition 3: Silence timeout after speech detected
        silence_sec = self._consecutive_silence_frames * 0.030
        if self._has_speech_started and silence_sec >= self._silence_timeout_seconds:
            logger.info("EVVoiceManager: speech completed (trailing silence: %.1fs), finalizing", silence_sec)
            self._finalize_utterance()
            return

    def _abort_utterance(self) -> None:
        """Abort listening/verification, discard frames, and return to IDLE."""
        self._verification_epoch += 1
        self._interaction_epoch += 1
        self._active_utterance_frames.clear()
        self._set_state(VoiceState.IDLE)
        if self._event_bus is not None:
            try:
                if getattr(self._event_bus, "current_state", None) in (EVState.LISTENING, EVState.PROCESSING):
                    self._event_bus.set_state(EVState.IDLE)
            except Exception as exc:
                logger.debug("EVVoiceManager: event_bus reset error: %s", exc)

    def _finalize_utterance(self) -> None:
        """Evaluate speech floor, extract utterance snapshot, and trigger ASR transcription."""
        speech_sec = self._speech_frames_count * 0.030
        if speech_sec < self._min_speech_seconds:
            logger.info("EVVoiceManager: speech duration (%.2fs) below minimum floor (%.2fs), discarding",
                        speech_sec, self._min_speech_seconds)
            self._abort_utterance()
            return

        # Snapshot frames and clear member list immediately for privacy & memory safety
        utterance_snapshot = list(self._active_utterance_frames)
        self._active_utterance_frames.clear()

        self._set_state(VoiceState.TRANSCRIBING)
        epoch = self._interaction_epoch

        # Dispatch transcription in a background thread so audio ingestion remains non-blocking
        threading.Thread(
            target=self._transcribe_and_submit,
            args=(utterance_snapshot, epoch),
            name="EVVoiceTranscribeWorker",
            daemon=True,
        ).start()

    def _transcribe_and_submit(self, utterance_frames: List[AudioFrame], epoch: int) -> None:
        """Run ASR on captured utterance, strip wake phrase, and submit untrusted text to orchestrator."""
        raw_text = ""
        try:
            asr_res: ASRResult = self._asr_provider.transcribe(utterance_frames)
            if asr_res and asr_res.text:
                raw_text = asr_res.text.strip()
        except Exception as exc:
            logger.error("EVVoiceManager: ASR transcription error: %s", exc)
            with self._lock:
                self._last_error = f"ASR error: {exc}"
            if self._on_error:
                self._on_error(self._last_error)
        finally:
            # Memory & privacy guarantee: clear raw audio frames immediately
            utterance_frames.clear()

        with self._lock:
            # Stale result & cancellation check:
            if (
                self._stop_event.is_set()
                or self._paused_event.is_set()
                or self._interaction_epoch != epoch
                or self._state != VoiceState.TRANSCRIBING
            ):
                logger.debug("EVVoiceManager: Discarding stale ASR result (epoch=%d, current=%d)",
                             epoch, self._interaction_epoch)
                return

        # Step 4: Conservative wake phrase removal
        cleaned_command = strip_wake_phrase(raw_text, self._wake_phrases)

        with self._lock:
            self._last_transcript = cleaned_command
            self._total_utterances_processed += 1

        # Step 5: Submission to EVOrchestrator strictly through submit_command(...)
        if cleaned_command:
            logger.info("EVVoiceManager: submitting voice command: '%s'", cleaned_command)
            with self._lock:
                self._set_state(VoiceState.PROCESSING)
            try:
                self._orchestrator.submit_command(cleaned_command)
                with self._lock:
                    self._total_commands_submitted += 1
            except Exception as exc:
                logger.error("EVVoiceManager: orchestrator.submit_command failed: %s", exc)
                with self._lock:
                    self._last_error = f"Orchestrator error: {exc}"
                if self._on_error:
                    self._on_error(self._last_error)

            if self._on_transcript:
                try:
                    self._on_transcript(cleaned_command)
                except Exception as exc:
                    logger.debug("EVVoiceManager: on_transcript callback error: %s", exc)
        else:
            logger.debug("EVVoiceManager: empty or whitespace-only transcript after stripping, nothing submitted")

        # Step 6: Wait for active response speech if TTS manager is speaking
        if cleaned_command and self._tts_manager is not None:
            # Allow speech subsystem up to 150ms to enqueue/start speech if initiated asynchronously
            t_check = time.monotonic()
            while time.monotonic() - t_check < 0.20:
                if getattr(self._tts_manager, "is_speaking", False):
                    break
                time.sleep(0.02)

            if getattr(self._tts_manager, "is_speaking", False):
                with self._lock:
                    if self._interaction_epoch == epoch and not self._stop_event.is_set():
                        self._set_state(VoiceState.SPEAKING)

                # Wait for TTS to finish speaking or be cancelled
                t_speak_start = time.monotonic()
                max_wait = 15.0
                while time.monotonic() - t_speak_start < max_wait:
                    if not getattr(self._tts_manager, "is_speaking", False):
                        break
                    if self._stop_event.is_set() or self._interaction_epoch != epoch:
                        break
                    time.sleep(0.04)

        # Step 7: Return to IDLE
        with self._lock:
            if self._interaction_epoch == epoch and not self._stop_event.is_set():
                self._set_state(VoiceState.IDLE)
                if self._event_bus is not None:
                    try:
                        if getattr(self._event_bus, "current_state", None) in (EVState.LISTENING, EVState.PROCESSING):
                            self._event_bus.set_state(EVState.IDLE)
                    except Exception as exc:
                        logger.debug("EVVoiceManager: event_bus set_state error: %s", exc)

    def _handle_stop_barge_in(self) -> None:
        """Handle STOP event from barge-in detector."""
        logger.info("EVVoiceManager: STOP barge-in event triggered")

        # 1. Stop active/queued TTS immediately if TTS manager present
        if self._tts_manager is not None:
            try:
                if hasattr(self._tts_manager, "cancel_all"):
                    self._tts_manager.cancel_all(reason="Voice barge-in STOP detected")
                elif hasattr(self._tts_manager, "stop"):
                    self._tts_manager.stop()
            except Exception as exc:
                logger.debug("EVVoiceManager: TTS cancellation error: %s", exc)

        # 2. Forward cancellation to orchestrator via control command "stop"
        if self._orchestrator is not None:
            try:
                self._orchestrator.submit_command("stop")
            except Exception as exc:
                logger.debug("EVVoiceManager: orchestrator cancel error: %s", exc)

        # 3. Discard active utterance and return to IDLE
        self._abort_utterance()
