"""
TTS (Text-to-Speech) and Audio Feedback subsystem for E.V. (Phase 6 Task 013).

Provides a safe, cancellable, queue-aware audio output layer isolated behind a
clean provider abstraction.

Security and Architectural Invariants:
1. TTS is OUTPUT PRESENTATION ONLY. It NEVER authorizes actions, resolves
   approvals, bypasses EVRiskEngine, submits commands, or modifies task
   authorization, queue priority, or Brain routing.
2. EVTTSManager holds no reference to EVOrchestrator and cannot call
   submit_command() or resolve_approval().
3. EVTTSManager does NOT call event_bus.set_state(). EVState transitions
   remain the exclusive domain of EVOrchestrator.
4. Text sanitization: control characters stripped, length bounded before any
   provider call or subprocess execution.
5. Sensitive content detection: passwords, tokens, API keys, and credential
   patterns are blocked from TTS output and replaced with a safe fallback.
6. Epoch-based stale protection: cancelled contexts cannot resume speech.
7. Subprocess isolation: WindowsSAPIProvider spawns a dedicated transient
   PowerShell process that owns no E.V. resources. Text is transported via
   stdin only; no user text is interpolated into any shell command string.
   Termination on Windows is forceful process termination -- the subprocess
   is fully isolated and this is safe and expected.
8. Zero new third-party dependencies: all functionality uses Python stdlib.
"""
from __future__ import annotations

import logging
import os
import re
import subprocess
import threading
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, List, Optional, Tuple

from core.cancellation import CancellationToken
from core.events import EVEventBus
from core.models import EVEventType

logger = logging.getLogger("ev.tts")

# Constants
MAX_TTS_TEXT_LENGTH: int = 2000
MAX_AUDIO_QUEUE_SIZE: int = 10
DEFAULT_SAPI_TIMEOUT: float = 60.0

_SAPI_POWERSHELL_SCRIPT: str = (
    "$ErrorActionPreference = 'Stop'; "
    "Add-Type -AssemblyName System.Speech; "
    "$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
    "if ($env:EV_TTS_VOICE -and $env:EV_TTS_VOICE.Length -gt 0) { "
    "    try { $synth.SelectVoice($env:EV_TTS_VOICE) } catch {} "
    "}; "
    "$text = [Console]::In.ReadToEnd(); "
    "if ($text -and $text.Trim().Length -gt 0) { "
    "    $synth.Speak($text.Trim()) "
    "}; "
    "$synth.Dispose()"
)

_SAPI_PROBE_SCRIPT: str = (
    "Add-Type -AssemblyName System.Speech; "
    "[System.Speech.Synthesis.SpeechSynthesizer]::new().Dispose(); "
    "Write-Output 'OK'"
)

_SENSITIVE_REGEX_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"sk-[a-zA-Z0-9_\-]{20,}", re.IGNORECASE), "API key"),
    (re.compile(r"AIzaSy[a-zA-Z0-9_\-]{30,}", re.IGNORECASE), "API key"),
    (re.compile(r"-----BEGIN (?:[A-Z ]+)?PRIVATE KEY-----", re.IGNORECASE), "private key"),
    (re.compile(r"Bearer\s+[a-zA-Z0-9_\-\.]{20,}", re.IGNORECASE), "bearer token"),
    (re.compile(r"eyJ[a-zA-Z0-9_\-]{10,}\.eyJ[a-zA-Z0-9_\-]{10,}", re.IGNORECASE), "JWT token"),
    (re.compile(r"(?:password|passwd|secret|api_?key|access_token|refresh_token|client_secret)\s*[=:]\s*\S{4,}", re.IGNORECASE), "credential"),
    (re.compile(r"ghp_[a-zA-Z0-9]{36,}", re.IGNORECASE), "GitHub token"),
    (re.compile(r"xoxb-[a-zA-Z0-9\-]{20,}", re.IGNORECASE), "Slack token"),
]

_SENSITIVE_KEYWORDS: frozenset = frozenset({
    "password:", "passwd:", "secret:", "api_key:", "apikey=",
    "access_token:", "refresh_token:", "bearer ", "private_key",
    "client_secret", "session_token:", "authorization: basic",
})

_SENSITIVE_FALLBACK_TEXT: str = "Response ready. Check the display."


def _is_sensitive(text: str) -> bool:
    lowered = text.lower()
    for keyword in _SENSITIVE_KEYWORDS:
        if keyword in lowered:
            return True
    for pattern, _ in _SENSITIVE_REGEX_PATTERNS:
        if pattern.search(text):
            return True
    return False


def _sanitize_text(text: str, max_length: int = MAX_TTS_TEXT_LENGTH) -> str:
    sanitized = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    sanitized = re.sub(r"[ \t]+", " ", sanitized).strip()
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    return sanitized


class AudioPriority(IntEnum):
    """
    Audio scheduling priority. Lower value = higher priority.
    Independent from TaskPriority (core/task_queue.py).
    """
    CRITICAL    = 0
    APPROVAL    = 1
    INTERACTIVE = 2
    SYSTEM      = 3
    BACKGROUND  = 4


@dataclass
class TTSSpeakResult:
    """Structured result of a single TTS utterance."""
    utterance_id: str
    provider: str
    success: bool
    interrupted: bool = False
    duration_seconds: Optional[float] = None
    error: Optional[str] = None


@dataclass
class AudioUtterance:
    """Pending speech item in the EVTTSManager audio queue."""
    text: str
    priority: AudioPriority
    utterance_id: str
    request_epoch: int
    created_at: float = field(default_factory=time.monotonic)
    cancellation_token: Optional[CancellationToken] = None

    def order_key(self) -> Tuple[int, float]:
        return (int(self.priority), self.created_at)


class AudioQueueFullError(Exception):
    """Raised when a high-priority utterance cannot be accepted due to queue capacity."""
    def __init__(self, message: str = "Audio queue at capacity") -> None:
        super().__init__(message)
        self.message = message


class EVTTSProvider(ABC):
    """Abstract TTS provider interface."""

    @abstractmethod
    def speak(self, text: str, utterance_id: str, cancellation_token: Optional[CancellationToken] = None) -> TTSSpeakResult:
        """Speak text synchronously. Block until complete, interrupted, or failed."""

    @abstractmethod
    def stop(self) -> None:
        """Interrupt any currently active speech immediately."""

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if this provider can produce audio on this system."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider identifier."""


class MockTTSProvider(EVTTSProvider):
    """
    Deterministic in-process TTS provider for testing.
    No audio device, subprocess, or OS resources required.
    """

    def __init__(self, available: bool = True, simulate_failure: bool = False, speak_duration: float = 0.0) -> None:
        self._available = available
        self._simulate_failure = simulate_failure
        self._speak_duration = speak_duration
        self._lock = threading.Lock()
        self._spoken: List[str] = []
        self._stop_event = threading.Event()

    def speak(self, text: str, utterance_id: str, cancellation_token: Optional[CancellationToken] = None) -> TTSSpeakResult:
        if self._simulate_failure:
            raise RuntimeError("MockTTSProvider: simulated provider failure")
        self._stop_event.clear()
        start = time.monotonic()
        with self._lock:
            self._spoken.append(text)
        interrupted = False
        if self._speak_duration > 0:
            interrupted = self._stop_event.wait(timeout=self._speak_duration)
        return TTSSpeakResult(
            utterance_id=utterance_id,
            provider=self.provider_name,
            success=True,
            interrupted=interrupted,
            duration_seconds=time.monotonic() - start,
        )

    def stop(self) -> None:
        self._stop_event.set()

    def is_available(self) -> bool:
        return self._available

    @property
    def provider_name(self) -> str:
        return "mock"

    def get_spoken_utterances(self) -> List[str]:
        with self._lock:
            return list(self._spoken)

    def clear_spoken(self) -> None:
        with self._lock:
            self._spoken.clear()

    def set_simulate_failure(self, value: bool) -> None:
        self._simulate_failure = value


class WindowsSAPIProvider(EVTTSProvider):
    """
    Windows-only TTS provider using System.Speech via powershell.exe subprocess.
    Text is transported via stdin only. No user text in shell command strings.
    Subprocess termination on Windows is forceful -- the subprocess is isolated
    and owns no E.V. resources.
    """

    def __init__(self, timeout: float = DEFAULT_SAPI_TIMEOUT) -> None:
        self._timeout = timeout
        self._lock = threading.Lock()
        self._active_proc: Optional[subprocess.Popen] = None
        self._voice_name: str = os.environ.get("EV_TTS_VOICE", "")

    @property
    def provider_name(self) -> str:
        return "windows_sapi"

    def is_available(self) -> bool:
        import platform
        if platform.system() != "Windows":
            return False
        try:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", _SAPI_PROBE_SCRIPT],
                capture_output=True, text=True, timeout=10.0,
            )
            return result.returncode == 0 and "OK" in result.stdout
        except Exception as exc:
            logger.debug("WindowsSAPIProvider: availability probe failed: %s", exc)
            return False

    def speak(self, text: str, utterance_id: str, cancellation_token: Optional[CancellationToken] = None) -> TTSSpeakResult:
        start = time.monotonic()
        proc: Optional[subprocess.Popen] = None
        interrupted = False

        def _on_cancel() -> None:
            nonlocal interrupted
            interrupted = True
            self._terminate_subprocess()

        try:
            if cancellation_token is not None and cancellation_token.is_cancelled():
                return TTSSpeakResult(utterance_id=utterance_id, provider=self.provider_name,
                                      success=False, interrupted=True,
                                      duration_seconds=time.monotonic() - start,
                                      error="Cancelled before speech started")

            env = {**os.environ, "EV_TTS_VOICE": self._voice_name}
            proc = subprocess.Popen(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", _SAPI_POWERSHELL_SCRIPT],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
            )
            with self._lock:
                self._active_proc = proc

            if cancellation_token is not None:
                cancellation_token.register_callback(_on_cancel)

            if cancellation_token is not None and cancellation_token.is_cancelled():
                _on_cancel()

            try:
                _stdout, stderr = proc.communicate(input=text.encode("utf-8", errors="replace"), timeout=self._timeout)
            except subprocess.TimeoutExpired:
                logger.warning("WindowsSAPIProvider: utterance %s timed out after %.1fs", utterance_id, self._timeout)
                self._terminate_subprocess()
                return TTSSpeakResult(utterance_id=utterance_id, provider=self.provider_name,
                                      success=False, interrupted=True,
                                      duration_seconds=time.monotonic() - start,
                                      error=f"TTS timeout after {self._timeout:.0f}s")

            duration = time.monotonic() - start

            if interrupted:
                return TTSSpeakResult(utterance_id=utterance_id, provider=self.provider_name,
                                      success=False, interrupted=True, duration_seconds=duration,
                                      error="Speech interrupted by cancellation")

            if proc.returncode != 0:
                err_text = ""
                if stderr:
                    try:
                        err_text = stderr.decode("utf-8", errors="replace").strip()[:200]
                    except Exception:
                        pass
                logger.warning("WindowsSAPIProvider: subprocess exit %d for utterance %s: %s",
                               proc.returncode, utterance_id, err_text)
                return TTSSpeakResult(utterance_id=utterance_id, provider=self.provider_name,
                                      success=False, interrupted=False, duration_seconds=duration,
                                      error=f"SAPI process failed (exit {proc.returncode}): {err_text[:100]}")

            return TTSSpeakResult(utterance_id=utterance_id, provider=self.provider_name,
                                  success=True, interrupted=False, duration_seconds=duration)

        except FileNotFoundError:
            logger.error("WindowsSAPIProvider: powershell.exe not found on PATH")
            return TTSSpeakResult(utterance_id=utterance_id, provider=self.provider_name,
                                  success=False, interrupted=False,
                                  duration_seconds=time.monotonic() - start,
                                  error="powershell.exe not found")
        except Exception as exc:
            logger.exception("WindowsSAPIProvider: unexpected error for utterance %s: %s", utterance_id, exc)
            return TTSSpeakResult(utterance_id=utterance_id, provider=self.provider_name,
                                  success=False, interrupted=False,
                                  duration_seconds=time.monotonic() - start,
                                  error=str(exc)[:200])
        finally:
            with self._lock:
                if self._active_proc is proc:
                    self._active_proc = None
            if proc is not None and proc.poll() is None:
                try:
                    proc.terminate()
                    proc.wait(timeout=3.0)
                except subprocess.TimeoutExpired:
                    try:
                        proc.kill()
                        proc.wait(timeout=1.0)
                    except Exception:
                        pass
                except Exception:
                    pass

    def stop(self) -> None:
        self._terminate_subprocess()

    def _terminate_subprocess(self) -> None:
        """Terminate the active subprocess. On Windows this is TerminateProcess (forceful, expected)."""
        with self._lock:
            proc = self._active_proc
            self._active_proc = None
        if proc is None:
            return
        try:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=3.0)
                except subprocess.TimeoutExpired:
                    try:
                        proc.kill()
                        proc.wait(timeout=1.0)
                    except Exception:
                        pass
        except Exception as exc:
            logger.debug("WindowsSAPIProvider: _terminate_subprocess: %s", exc)


class EVTTSManager:
    """
    Central audio output coordinator for E.V.

    Maintains a bounded priority audio queue independent of EVTaskQueue.
    Runs a dedicated daemon worker that serializes utterances.
    Uses epoch-based stale protection to discard speech from cancelled contexts.
    Publishes TTS_STARTED/COMPLETED/INTERRUPTED/FAILED via EVEventType.STATUS.
    Cannot call set_state(), submit_command(), or resolve_approval().
    """

    def __init__(self, providers: List[EVTTSProvider], event_bus: Optional[EVEventBus] = None,
                 max_queue_size: int = MAX_AUDIO_QUEUE_SIZE) -> None:
        self._event_bus = event_bus
        self._max_queue_size = max(1, max_queue_size)
        self._lock = threading.Lock()
        self._queue_condition = threading.Condition(self._lock)
        self._epoch: int = 0
        self._is_shutdown: bool = False
        self._shutdown_event = threading.Event()
        self._active_priority: Optional[AudioPriority] = None
        self._audio_queue: List[AudioUtterance] = []

        self._provider: Optional[EVTTSProvider] = None
        for p in providers:
            try:
                if p.is_available():
                    self._provider = p
                    logger.info("EVTTSManager: selected provider '%s'", p.provider_name)
                    break
            except Exception as exc:
                logger.warning("EVTTSManager: provider '%s' is_available() raised: %s",
                               getattr(p, "provider_name", repr(p)), exc)

        if self._provider is None:
            logger.info("EVTTSManager: no available provider -- operating in silent mode")

        self._worker_thread = threading.Thread(
            target=self._audio_worker_loop, name="EVTTSWorker", daemon=True
        )
        self._worker_thread.start()

    @property
    def is_silent(self) -> bool:
        return self._provider is None

    def speak(self, text: str, priority: AudioPriority = AudioPriority.INTERACTIVE,
              utterance_id: Optional[str] = None,
              cancellation_token: Optional[CancellationToken] = None) -> Optional[str]:
        """
        Enqueue speech. Returns utterance_id or None if silently dropped.
        Raises AudioQueueFullError for CRITICAL/APPROVAL when queue is full.
        Never raises for BACKGROUND callers.
        """
        if self._provider is None:
            return None
        if not text or not isinstance(text, str) or not text.strip():
            return None

        uid = utterance_id or f"tts-{uuid.uuid4().hex[:8]}"

        if _is_sensitive(text):
            logger.warning("EVTTSManager: sensitive content in utterance %s -- using fallback", uid)
            text = _SENSITIVE_FALLBACK_TEXT

        clean_text = _sanitize_text(text)
        if not clean_text:
            return None

        preempt_needed = False
        with self._queue_condition:
            if self._is_shutdown:
                return None

            current_epoch = self._epoch
            utterance = AudioUtterance(
                text=clean_text, priority=priority, utterance_id=uid,
                request_epoch=current_epoch, cancellation_token=cancellation_token,
            )

            if len(self._audio_queue) >= self._max_queue_size:
                if priority == AudioPriority.BACKGROUND:
                    logger.debug("EVTTSManager: BACKGROUND item %s dropped -- queue full", uid)
                    return None
                raise AudioQueueFullError(
                    f"Audio queue full ({self._max_queue_size} items); "
                    f"cannot accept {priority.name} utterance"
                )

            inserted = False
            for idx, existing in enumerate(self._audio_queue):
                if utterance.order_key() < existing.order_key():
                    self._audio_queue.insert(idx, utterance)
                    inserted = True
                    break
            if not inserted:
                self._audio_queue.append(utterance)

            active_prio = self._active_priority
            if (active_prio is not None and priority < active_prio
                    and priority <= AudioPriority.APPROVAL):
                preempt_needed = True
                logger.debug("EVTTSManager: preempting active %s for %s utterance %s",
                             active_prio.name, priority.name, uid)

            logger.debug("EVTTSManager: enqueued %s [priority=%s, queue=%d]",
                         uid, priority.name, len(self._audio_queue))
            self._queue_condition.notify()

        if preempt_needed and self._provider is not None:
            try:
                self._provider.stop()
            except Exception as exc:
                logger.debug("EVTTSManager: preemption stop failed: %s", exc)

        return uid

    def cancel_all(self, reason: str = "Cancelled") -> None:
        """Increment epoch, clear queue, stop active speech."""
        with self._queue_condition:
            self._epoch += 1
            self._audio_queue.clear()
            logger.debug("EVTTSManager: cancel_all -- epoch -> %d, reason='%s'", self._epoch, reason)

        if self._provider is not None:
            try:
                self._provider.stop()
            except Exception as exc:
                logger.debug("EVTTSManager: provider.stop() error in cancel_all: %s", exc)

    def shutdown(self, timeout: float = 3.0) -> None:
        """Cancel pending speech, stop provider, join worker. Idempotent."""
        with self._queue_condition:
            if self._is_shutdown:
                return
            self._is_shutdown = True
            self._epoch += 1
            self._audio_queue.clear()
            self._queue_condition.notify_all()

        self._shutdown_event.set()

        if self._provider is not None:
            try:
                self._provider.stop()
            except Exception as exc:
                logger.debug("EVTTSManager: provider.stop() error in shutdown: %s", exc)

        if self._worker_thread.is_alive():
            self._worker_thread.join(timeout=timeout)
            if self._worker_thread.is_alive():
                logger.warning("EVTTSManager: worker did not exit within %.1fs", timeout)

        logger.info("EVTTSManager: shutdown complete")

    def _audio_worker_loop(self) -> None:
        logger.debug("EVTTSManager: audio worker started")
        while not self._shutdown_event.is_set():
            utterance: Optional[AudioUtterance] = None
            with self._queue_condition:
                while not self._audio_queue and not self._is_shutdown:
                    self._queue_condition.wait(timeout=0.5)
                if self._is_shutdown:
                    break
                if self._audio_queue:
                    utterance = self._audio_queue.pop(0)
            if utterance is not None:
                self._process_utterance(utterance)
        logger.debug("EVTTSManager: audio worker terminated")

    def _process_utterance(self, utterance: AudioUtterance) -> None:
        with self._lock:
            current_epoch = self._epoch

        if utterance.request_epoch != current_epoch:
            logger.debug("EVTTSManager: stale utterance %s discarded (epoch %d != %d)",
                         utterance.utterance_id, utterance.request_epoch, current_epoch)
            return

        if utterance.cancellation_token is not None and utterance.cancellation_token.is_cancelled():
            logger.debug("EVTTSManager: utterance %s cancelled before start", utterance.utterance_id)
            self._publish_status("TTS_INTERRUPTED", utterance.utterance_id, utterance.priority)
            return

        if self._provider is None:
            return

        with self._lock:
            self._active_priority = utterance.priority

        self._publish_status("TTS_STARTED", utterance.utterance_id, utterance.priority)

        # Register manager-level cancellation callback so stop() fires regardless of provider type.
        # This is the canonical cancellation path — works for MockTTSProvider and WindowsSAPIProvider alike.
        _provider_ref = self._provider

        def _cancel_callback() -> None:
            if _provider_ref is not None:
                try:
                    _provider_ref.stop()
                except Exception as cb_exc:
                    logger.debug("EVTTSManager: cancel callback stop() failed: %s", cb_exc)

        if utterance.cancellation_token is not None:
            utterance.cancellation_token.register_callback(_cancel_callback)

        result: Optional[TTSSpeakResult] = None
        start_time = time.monotonic()
        try:
            result = self._provider.speak(
                text=utterance.text,
                utterance_id=utterance.utterance_id,
                cancellation_token=utterance.cancellation_token,
            )
        except Exception as exc:
            duration = time.monotonic() - start_time
            logger.error("EVTTSManager: provider raised for %s: %s", utterance.utterance_id, exc)
            self._publish_status("TTS_FAILED", utterance.utterance_id, utterance.priority,
                                 extra={"error": str(exc)[:200], "duration_seconds": round(duration, 3)})
            return
        finally:
            with self._lock:
                if self._active_priority == utterance.priority:
                    self._active_priority = None

        if result is None:
            self._publish_status("TTS_FAILED", utterance.utterance_id, utterance.priority,
                                 extra={"error": "provider returned None"})
            return

        with self._lock:
            post_epoch = self._epoch

        if result.interrupted or utterance.request_epoch != post_epoch:
            self._publish_status("TTS_INTERRUPTED", utterance.utterance_id, utterance.priority,
                                 extra={"duration_seconds": round(result.duration_seconds or 0.0, 3)})
        elif result.success:
            self._publish_status("TTS_COMPLETED", utterance.utterance_id, utterance.priority,
                                 extra={"duration_seconds": round(result.duration_seconds or 0.0, 3)})
        else:
            self._publish_status("TTS_FAILED", utterance.utterance_id, utterance.priority,
                                 extra={"error": (result.error or "unknown error")[:200],
                                        "duration_seconds": round(result.duration_seconds or 0.0, 3)})

    def _publish_status(self, event_name: str, utterance_id: str, priority: AudioPriority,
                        extra: Optional[dict] = None) -> None:
        """Publish TTS STATUS event. Never includes full spoken text to prevent credential leakage."""
        if self._event_bus is None:
            return
        data: dict = {"event": event_name, "utterance_id": utterance_id, "priority": priority.name}
        if extra:
            data.update({k: v for k, v in extra.items() if k != "text"})
        try:
            self._event_bus.publish(event_type=EVEventType.STATUS, source="tts", data=data)
        except Exception as exc:
            logger.debug("EVTTSManager: failed to publish %s: %s", event_name, exc)
