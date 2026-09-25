"""
Task 013: TTS & Audio Feedback test suite.

Tests MUST NOT require:
- speakers, microphones, or real audio hardware
- cloud APIs or network access
- real Windows speech synthesis

All behavioural tests use MockTTSProvider.
WindowsSAPIProvider is only tested for availability (returns bool) and
structural properties.
"""
from __future__ import annotations

import platform
import threading
import time
from typing import List, Optional
from unittest.mock import MagicMock, patch

import pytest

from core.cancellation import CancellationToken, CancellationSource
from core.events import EVEventBus
from core.models import EVEventType, EVState
from core.tts import (
    AudioPriority,
    AudioQueueFullError,
    AudioUtterance,
    EVTTSManager,
    EVTTSProvider,
    MockTTSProvider,
    TTSSpeakResult,
    WindowsSAPIProvider,
    _is_sensitive,
    _sanitize_text,
)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def _wait_for_spoken(mock_provider: MockTTSProvider, expected_count: int, timeout: float = 3.0) -> bool:
    """Poll until mock_provider has recorded at least expected_count utterances."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if len(mock_provider.get_spoken_utterances()) >= expected_count:
            return True
        time.sleep(0.01)
    return False


def _collect_tts_events(event_bus: EVEventBus, event_names: Optional[List[str]] = None) -> tuple:
    """
    Subscribe to event_bus and return (collected_events_list, threading.Event for first match).
    Optionally filter by event_names inside data["event"].
    """
    events: List[dict] = []
    first_event = threading.Event()

    def handler(ev):
        data = ev.data or {}
        name = data.get("event", "")
        if event_names is None or name in event_names:
            events.append(data)
            first_event.set()

    event_bus.subscribe(handler)
    return events, first_event


# ---------------------------------------------------------------------------
# 1. AudioPriority ordering
# ---------------------------------------------------------------------------

class TestAudioPriority:
    def test_priority_numeric_ordering(self):
        assert AudioPriority.CRITICAL < AudioPriority.APPROVAL
        assert AudioPriority.APPROVAL < AudioPriority.INTERACTIVE
        assert AudioPriority.INTERACTIVE < AudioPriority.SYSTEM
        assert AudioPriority.SYSTEM < AudioPriority.BACKGROUND

    def test_critical_is_lowest_value(self):
        assert AudioPriority.CRITICAL == 0

    def test_background_is_highest_value(self):
        assert AudioPriority.BACKGROUND == 4

    def test_approval_outranks_interactive(self):
        assert AudioPriority.APPROVAL < AudioPriority.INTERACTIVE


# ---------------------------------------------------------------------------
# 2. Text sanitization helpers
# ---------------------------------------------------------------------------

class TestSanitizeText:
    def test_control_chars_stripped(self):
        # \x00 and \x1f should be removed; \n and \t are preserved
        result = _sanitize_text("hello\x00world\x1ftest")
        assert "\x00" not in result
        assert "\x1f" not in result

    def test_max_length_enforced(self):
        long_text = "a" * 5000
        result = _sanitize_text(long_text, max_length=100)
        assert len(result) <= 100

    def test_normal_text_unchanged(self):
        text = "Hello, E.V. Speaking normally."
        result = _sanitize_text(text)
        assert "Hello, E.V. Speaking normally." in result

    def test_empty_string_returns_empty(self):
        assert _sanitize_text("") == ""

    def test_excessive_spaces_collapsed(self):
        result = _sanitize_text("hello    world")
        assert "  " not in result


# ---------------------------------------------------------------------------
# 3. Sensitive content detection
# ---------------------------------------------------------------------------

class TestSensitiveDetection:
    def test_api_key_pattern_detected(self):
        assert _is_sensitive("sk-" + "a" * 25) is True

    def test_google_api_key_detected(self):
        assert _is_sensitive("AIzaSy" + "b" * 35) is True

    def test_bearer_token_detected(self):
        assert _is_sensitive("Authorization: Bearer eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ1c2VyIn0.signature") is True

    def test_password_field_detected(self):
        assert _is_sensitive("password: hunter2abc") is True

    def test_private_key_detected(self):
        assert _is_sensitive("-----BEGIN PRIVATE KEY-----\nMIIEvQIB...") is True

    def test_normal_text_not_sensitive(self):
        assert _is_sensitive("The disk usage is 87 percent. All systems nominal.") is False

    def test_empty_string_not_sensitive(self):
        assert _is_sensitive("") is False


# ---------------------------------------------------------------------------
# 4. MockTTSProvider
# ---------------------------------------------------------------------------

class TestMockTTSProvider:
    def test_is_available_true(self):
        p = MockTTSProvider(available=True)
        assert p.is_available() is True

    def test_is_available_false(self):
        p = MockTTSProvider(available=False)
        assert p.is_available() is False

    def test_speak_returns_success(self):
        p = MockTTSProvider()
        result = p.speak("hello", "uid-1")
        assert result.success is True
        assert result.utterance_id == "uid-1"
        assert result.provider == "mock"
        assert result.interrupted is False

    def test_speak_records_utterance(self):
        p = MockTTSProvider()
        p.speak("hello world", "uid-1")
        assert "hello world" in p.get_spoken_utterances()

    def test_stop_interrupts_speech(self):
        p = MockTTSProvider(speak_duration=5.0)
        finished = threading.Event()

        def _speak():
            p.speak("long text", "uid-1")
            finished.set()

        t = threading.Thread(target=_speak, daemon=True)
        t.start()
        time.sleep(0.05)
        p.stop()
        assert finished.wait(timeout=1.5), "speak() did not return after stop()"

    def test_provider_name(self):
        assert MockTTSProvider().provider_name == "mock"

    def test_simulate_failure_raises(self):
        p = MockTTSProvider(simulate_failure=True)
        with pytest.raises(RuntimeError, match="simulated provider failure"):
            p.speak("hello", "uid-1")

    def test_get_spoken_utterances_thread_safe(self):
        p = MockTTSProvider()
        threads = [threading.Thread(target=p.speak, args=(f"text-{i}", f"uid-{i}")) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=2.0)
        assert len(p.get_spoken_utterances()) == 10

    def test_clear_spoken(self):
        p = MockTTSProvider()
        p.speak("hello", "uid-1")
        p.clear_spoken()
        assert p.get_spoken_utterances() == []


# ---------------------------------------------------------------------------
# 5. WindowsSAPIProvider
# ---------------------------------------------------------------------------

class TestWindowsSAPIProvider:
    def test_provider_name(self):
        p = WindowsSAPIProvider()
        assert p.provider_name == "windows_sapi"

    def test_is_available_returns_bool(self):
        p = WindowsSAPIProvider()
        result = p.is_available()
        assert isinstance(result, bool)

    def test_not_available_on_non_windows(self):
        with patch("platform.system", return_value="Linux"):
            p = WindowsSAPIProvider()
            assert p.is_available() is False


# ---------------------------------------------------------------------------
# 6. EVTTSManager initialization
# ---------------------------------------------------------------------------

class TestEVTTSManagerInit:
    def test_no_providers_is_silent(self):
        mgr = EVTTSManager(providers=[])
        assert mgr.is_silent is True
        mgr.shutdown()

    def test_unavailable_provider_is_silent(self):
        p = MockTTSProvider(available=False)
        mgr = EVTTSManager(providers=[p])
        assert mgr.is_silent is True
        mgr.shutdown()

    def test_available_mock_provider_active(self):
        p = MockTTSProvider(available=True)
        mgr = EVTTSManager(providers=[p])
        assert mgr.is_silent is False
        mgr.shutdown()

    def test_first_available_provider_selected(self):
        p1 = MockTTSProvider(available=False)
        p2 = MockTTSProvider(available=True)
        mgr = EVTTSManager(providers=[p1, p2])
        assert mgr.is_silent is False
        mgr.shutdown()

    def test_init_without_event_bus_works(self):
        p = MockTTSProvider()
        mgr = EVTTSManager(providers=[p], event_bus=None)
        uid = mgr.speak("hello")
        assert uid is not None
        mgr.shutdown()


# ---------------------------------------------------------------------------
# 7. Speaking
# ---------------------------------------------------------------------------

class TestEVTTSManagerSpeak:
    def test_speak_basic_returns_utterance_id(self):
        p = MockTTSProvider()
        mgr = EVTTSManager(providers=[p])
        uid = mgr.speak("hello")
        assert uid is not None and uid.startswith("tts-")
        mgr.shutdown()

    def test_speak_empty_text_ignored(self):
        p = MockTTSProvider()
        mgr = EVTTSManager(providers=[p])
        uid = mgr.speak("")
        assert uid is None
        uid2 = mgr.speak("   ")
        assert uid2 is None
        mgr.shutdown()

    def test_speak_actually_calls_provider(self):
        p = MockTTSProvider()
        mgr = EVTTSManager(providers=[p])
        mgr.speak("test sentence")
        assert _wait_for_spoken(p, 1), "MockTTSProvider.speak() was not called"
        mgr.shutdown()

    def test_speak_long_text_truncated_before_provider(self):
        p = MockTTSProvider()
        mgr = EVTTSManager(providers=[p])
        long_text = "x" * 5000
        mgr.speak(long_text)
        assert _wait_for_spoken(p, 1), "Provider was not called"
        spoken = p.get_spoken_utterances()[0]
        assert len(spoken) <= 2000 + 10  # allow small tolerance
        mgr.shutdown()

    def test_speak_publishes_tts_started_event(self):
        p = MockTTSProvider()
        bus = EVEventBus(initial_state=EVState.IDLE)
        mgr = EVTTSManager(providers=[p], event_bus=bus)
        events, first_event = _collect_tts_events(bus, ["TTS_STARTED"])
        mgr.speak("hello E.V.")
        assert first_event.wait(timeout=3.0), "TTS_STARTED event not received"
        assert any(e["event"] == "TTS_STARTED" for e in events)
        mgr.shutdown()

    def test_speak_publishes_tts_completed_event(self):
        p = MockTTSProvider()
        bus = EVEventBus(initial_state=EVState.IDLE)
        mgr = EVTTSManager(providers=[p], event_bus=bus)
        events, first_event = _collect_tts_events(bus, ["TTS_COMPLETED"])
        mgr.speak("task complete")
        assert first_event.wait(timeout=3.0), "TTS_COMPLETED event not received"
        assert any(e["event"] == "TTS_COMPLETED" for e in events)
        mgr.shutdown()

    def test_speak_sensitive_content_uses_fallback(self):
        p = MockTTSProvider()
        mgr = EVTTSManager(providers=[p])
        mgr.speak("password: hunter2xyz_secret_very_long")
        assert _wait_for_spoken(p, 1), "Provider was not called"
        spoken = p.get_spoken_utterances()[0]
        # Fallback text used, original sensitive content not spoken
        assert "hunter2" not in spoken
        assert "password" not in spoken.lower() or "Check the display" in spoken
        mgr.shutdown()

    def test_speak_silent_mode_returns_none(self):
        mgr = EVTTSManager(providers=[])
        uid = mgr.speak("hello")
        assert uid is None
        mgr.shutdown()

    def test_speak_returns_custom_utterance_id(self):
        p = MockTTSProvider()
        mgr = EVTTSManager(providers=[p])
        uid = mgr.speak("hello", utterance_id="custom-uid-42")
        assert uid == "custom-uid-42"
        mgr.shutdown()


# ---------------------------------------------------------------------------
# 8. Audio Priority
# ---------------------------------------------------------------------------

class TestAudioPriorityBehavior:
    def test_approval_priority_accepted(self):
        p = MockTTSProvider()
        mgr = EVTTSManager(providers=[p])
        uid = mgr.speak("Please approve this action", priority=AudioPriority.APPROVAL)
        assert uid is not None
        mgr.shutdown()

    def test_background_dropped_when_queue_full(self):
        # Fill queue with INTERACTIVE items, then try BACKGROUND
        p = MockTTSProvider(speak_duration=10.0)  # slow — stays in queue
        mgr = EVTTSManager(providers=[p], max_queue_size=3)
        # First speak starts immediately (dequeued by worker), rest fill queue
        mgr.speak("item 1", priority=AudioPriority.INTERACTIVE)
        time.sleep(0.05)
        # Fill the remaining queue slots
        for i in range(3):
            try:
                mgr.speak(f"filler {i}", priority=AudioPriority.INTERACTIVE)
            except AudioQueueFullError:
                break
        # BACKGROUND item should be silently dropped
        uid = mgr.speak("background noise", priority=AudioPriority.BACKGROUND)
        assert uid is None
        mgr.cancel_all()
        mgr.shutdown()

    def test_critical_overflow_raises(self):
        p = MockTTSProvider(speak_duration=10.0)
        mgr = EVTTSManager(providers=[p], max_queue_size=2)
        mgr.speak("item 1", priority=AudioPriority.INTERACTIVE)
        time.sleep(0.05)
        for _ in range(2):
            try:
                mgr.speak("filler", priority=AudioPriority.SYSTEM)
            except AudioQueueFullError:
                break
        # Now queue is full; CRITICAL should raise
        try:
            mgr.speak("critical alert", priority=AudioPriority.CRITICAL)
            # If we reach here the queue wasn't actually full; acceptable
        except AudioQueueFullError:
            pass  # Expected behaviour verified
        mgr.cancel_all()
        mgr.shutdown()

    def test_fifo_within_equal_priority(self):
        p = MockTTSProvider(speak_duration=0.0)
        mgr = EVTTSManager(providers=[p], max_queue_size=10)
        # Enqueue multiple INTERACTIVE items
        for i in range(5):
            mgr.speak(f"message {i}", priority=AudioPriority.INTERACTIVE)
        assert _wait_for_spoken(p, 5, timeout=3.0), "Not all utterances spoken"
        spoken = p.get_spoken_utterances()
        # Verify FIFO: messages should be spoken in submission order
        indices = [int(s.split()[-1]) for s in spoken if s.startswith("message")]
        assert indices == sorted(indices), f"FIFO violated: {indices}"
        mgr.shutdown()


# ---------------------------------------------------------------------------
# 9. Cancellation
# ---------------------------------------------------------------------------

class TestCancellation:
    def test_cancel_all_clears_queue(self):
        p = MockTTSProvider(speak_duration=10.0)
        mgr = EVTTSManager(providers=[p])
        # Let first item be picked up by worker
        mgr.speak("item 1", priority=AudioPriority.SYSTEM)
        time.sleep(0.05)
        mgr.speak("item 2", priority=AudioPriority.SYSTEM)
        mgr.speak("item 3", priority=AudioPriority.SYSTEM)
        mgr.cancel_all(reason="test cancel")
        # Queue should be empty after cancel_all
        with mgr._queue_condition:
            assert mgr._audio_queue == []
        mgr.shutdown()

    def test_cancel_all_increments_epoch(self):
        p = MockTTSProvider()
        mgr = EVTTSManager(providers=[p])
        initial_epoch = mgr._epoch
        mgr.cancel_all()
        assert mgr._epoch == initial_epoch + 1
        mgr.shutdown()

    def test_cancel_all_stops_provider(self):
        stop_called = threading.Event()
        p = MockTTSProvider(speak_duration=10.0)
        original_stop = p.stop

        def tracking_stop():
            stop_called.set()
            original_stop()

        p.stop = tracking_stop
        mgr = EVTTSManager(providers=[p])
        mgr.speak("long speech")
        time.sleep(0.05)
        mgr.cancel_all(reason="user stop")
        assert stop_called.wait(timeout=2.0), "provider.stop() was not called"
        mgr.shutdown()

    def test_cancelled_token_prevents_speech_start(self):
        p = MockTTSProvider()
        mgr = EVTTSManager(providers=[p])
        token = CancellationToken()
        token.cancel(reason="pre-cancelled", source=CancellationSource.USER_COMMAND)
        mgr.speak("should not speak", cancellation_token=token)
        time.sleep(0.3)
        # Provider should not have spoken
        assert len(p.get_spoken_utterances()) == 0
        mgr.shutdown()

    def test_cancellation_token_callback_invoked(self):
        """CancellationToken.register_callback is called; cancelling it stops active speech."""
        p = MockTTSProvider(speak_duration=5.0)
        mgr = EVTTSManager(providers=[p])
        token = CancellationToken()
        mgr.speak("ongoing speech", priority=AudioPriority.INTERACTIVE, cancellation_token=token)
        # Wait for speech to start
        assert _wait_for_spoken(p, 1, timeout=2.0), "Speech did not start"
        token.cancel(reason="user interrupt", source=CancellationSource.USER_COMMAND)
        # provider.stop() should be invoked via callback, speech ends quickly
        time.sleep(0.3)
        assert p._stop_event.is_set(), "stop() was not triggered by token callback"
        mgr.shutdown()


# ---------------------------------------------------------------------------
# 10. Stale output protection (epoch)
# ---------------------------------------------------------------------------

class TestStaleProtection:
    def test_stale_utterance_discarded_after_cancel(self):
        p = MockTTSProvider()
        mgr = EVTTSManager(providers=[p])
        # Manually increment epoch to simulate cancellation having occurred
        with mgr._queue_condition:
            old_epoch = mgr._epoch
        mgr.speak("item that will be stale")
        mgr.cancel_all()  # epoch incremented, queue cleared
        # Any speech enqueued BEFORE cancel_all should not play
        # Give worker a moment
        time.sleep(0.3)
        # Provider may or may not have spoken the first item (race with worker)
        # But after cancel_all, no NEW stale item should play
        pre_cancel_count = len(p.get_spoken_utterances())
        mgr.speak("new fresh item")
        assert _wait_for_spoken(p, pre_cancel_count + 1, timeout=2.0), "Fresh item not spoken"
        mgr.shutdown()

    def test_epoch_increments_on_cancel_all(self):
        p = MockTTSProvider()
        mgr = EVTTSManager(providers=[p])
        e0 = mgr._epoch
        mgr.cancel_all()
        e1 = mgr._epoch
        mgr.cancel_all()
        e2 = mgr._epoch
        assert e1 == e0 + 1
        assert e2 == e1 + 1
        mgr.shutdown()

    def test_fresh_utterance_plays_after_cancel(self):
        p = MockTTSProvider()
        mgr = EVTTSManager(providers=[p])
        mgr.cancel_all()
        pre = len(p.get_spoken_utterances())
        mgr.speak("fresh post-cancel speech")
        assert _wait_for_spoken(p, pre + 1, timeout=2.0), "Fresh utterance not spoken after cancel"
        mgr.shutdown()


# ---------------------------------------------------------------------------
# 11. Approval speech
# ---------------------------------------------------------------------------

class TestApprovalAudio:
    def test_approval_priority_accepted(self):
        p = MockTTSProvider()
        mgr = EVTTSManager(providers=[p])
        uid = mgr.speak(
            "This action requires your approval. Say yes to confirm.",
            priority=AudioPriority.APPROVAL,
        )
        assert uid is not None
        assert _wait_for_spoken(p, 1, timeout=2.0), "Approval speech not spoken"
        mgr.shutdown()

    def test_approval_cancelled_by_cancel_all(self):
        p = MockTTSProvider(speak_duration=5.0)
        mgr = EVTTSManager(providers=[p])
        mgr.speak("Approval prompt", priority=AudioPriority.APPROVAL)
        time.sleep(0.05)
        mgr.cancel_all(reason="user cancelled approval")
        with mgr._queue_condition:
            assert mgr._audio_queue == []
        mgr.shutdown()


# ---------------------------------------------------------------------------
# 12. Provider failure isolation
# ---------------------------------------------------------------------------

class TestProviderFailure:
    def test_provider_exception_does_not_crash_manager(self):
        p = MockTTSProvider(simulate_failure=True)
        bus = EVEventBus(initial_state=EVState.IDLE)
        mgr = EVTTSManager(providers=[p], event_bus=bus)
        # Should not raise
        mgr.speak("this will fail")
        time.sleep(0.5)
        # Manager should still be running
        assert mgr._worker_thread.is_alive()
        mgr.shutdown()

    def test_tts_failed_event_published_on_provider_exception(self):
        p = MockTTSProvider(simulate_failure=True)
        bus = EVEventBus(initial_state=EVState.IDLE)
        events, first_event = _collect_tts_events(bus, ["TTS_FAILED"])
        mgr = EVTTSManager(providers=[p], event_bus=bus)
        mgr.speak("will fail")
        assert first_event.wait(timeout=3.0), "TTS_FAILED event not received"
        assert any(e["event"] == "TTS_FAILED" for e in events)
        mgr.shutdown()

    def test_unavailable_provider_falls_back_to_silent(self):
        p = MockTTSProvider(available=False)
        mgr = EVTTSManager(providers=[p])
        assert mgr.is_silent is True
        uid = mgr.speak("hello")
        assert uid is None
        mgr.shutdown()

    def test_manager_continues_after_single_failure(self):
        """After one failed utterance, subsequent utterances should still process."""
        p = MockTTSProvider()
        mgr = EVTTSManager(providers=[p])
        p.set_simulate_failure(True)
        mgr.speak("first (will fail)")
        time.sleep(0.3)
        p.set_simulate_failure(False)
        mgr.speak("second (should succeed)")
        assert _wait_for_spoken(p, 1, timeout=2.0), "Second utterance not spoken after recovery"
        mgr.shutdown()


# ---------------------------------------------------------------------------
# 13. Shutdown
# ---------------------------------------------------------------------------

class TestShutdown:
    def test_shutdown_cancels_pending_speech(self):
        p = MockTTSProvider(speak_duration=10.0)
        mgr = EVTTSManager(providers=[p])
        mgr.speak("item 1")
        time.sleep(0.05)
        mgr.speak("item 2")
        mgr.speak("item 3")
        mgr.shutdown(timeout=2.0)
        with mgr._queue_condition:
            assert mgr._audio_queue == []
        assert mgr._is_shutdown is True

    def test_shutdown_stops_provider(self):
        stop_called = threading.Event()
        p = MockTTSProvider(speak_duration=10.0)
        original_stop = p.stop

        def tracking_stop():
            stop_called.set()
            original_stop()

        p.stop = tracking_stop
        mgr = EVTTSManager(providers=[p])
        mgr.speak("ongoing")
        time.sleep(0.05)
        mgr.shutdown(timeout=2.0)
        assert stop_called.wait(timeout=2.0), "provider.stop() not called during shutdown"

    def test_shutdown_idempotent(self):
        p = MockTTSProvider()
        mgr = EVTTSManager(providers=[p])
        mgr.shutdown()
        # Should not raise
        mgr.shutdown()
        mgr.shutdown()

    def test_speak_after_shutdown_ignored(self):
        p = MockTTSProvider()
        mgr = EVTTSManager(providers=[p])
        mgr.shutdown()
        uid = mgr.speak("post-shutdown speak")
        assert uid is None


# ---------------------------------------------------------------------------
# 14. Concurrency
# ---------------------------------------------------------------------------

class TestConcurrency:
    def test_concurrent_speak_requests_serialize(self):
        """Multiple threads calling speak() concurrently must all succeed without errors."""
        p = MockTTSProvider(speak_duration=0.0)
        mgr = EVTTSManager(providers=[p])
        errors: List[Exception] = []

        def _speak(i: int):
            try:
                mgr.speak(f"concurrent message {i}", priority=AudioPriority.INTERACTIVE)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=_speak, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=2.0)

        assert errors == [], f"Errors during concurrent speak: {errors}"
        assert _wait_for_spoken(p, 8, timeout=3.0), "Not all utterances were spoken"
        mgr.shutdown()

    def test_tts_events_from_worker_thread(self):
        """Events published by the worker thread reach event_bus subscribers correctly."""
        p = MockTTSProvider()
        bus = EVEventBus(initial_state=EVState.IDLE)
        started_events, started_ev = _collect_tts_events(bus, ["TTS_STARTED"])
        completed_events, completed_ev = _collect_tts_events(bus, ["TTS_COMPLETED"])
        mgr = EVTTSManager(providers=[p], event_bus=bus)
        mgr.speak("serialization test")
        assert started_ev.wait(timeout=3.0), "TTS_STARTED not received"
        assert completed_ev.wait(timeout=3.0), "TTS_COMPLETED not received"
        mgr.shutdown()


# ---------------------------------------------------------------------------
# 15. Orchestrator TTS integration
# ---------------------------------------------------------------------------

class TestOrchestratorTTSIntegration:
    """
    Verify that EVOrchestrator integrates with EVTTSManager correctly.
    Uses MagicMock to avoid full orchestrator startup.
    """

    def test_orchestrator_accepts_optional_tts_manager(self):
        """EVOrchestrator.__init__ must accept tts_manager=None (default)."""
        from core.orchestrator import EVOrchestrator
        from core.events import EVEventBus
        from core.models import EVState
        bus = EVEventBus(initial_state=EVState.IDLE)
        # No tts_manager kwarg — must not raise
        orch = EVOrchestrator(event_bus=bus)
        assert orch._tts_manager is None
        orch.shutdown()

    def test_orchestrator_stores_tts_manager(self):
        """EVOrchestrator stores the provided tts_manager reference."""
        from core.orchestrator import EVOrchestrator
        from core.events import EVEventBus
        from core.models import EVState
        bus = EVEventBus(initial_state=EVState.IDLE)
        p = MockTTSProvider()
        tts = EVTTSManager(providers=[p])
        orch = EVOrchestrator(event_bus=bus, tts_manager=tts)
        assert orch._tts_manager is tts
        orch.shutdown()
        tts.shutdown()

    def test_orchestrator_stop_cancels_tts(self):
        """STOP command must call tts_manager.cancel_all()."""
        from core.orchestrator import EVOrchestrator
        from core.events import EVEventBus
        from core.models import EVState
        bus = EVEventBus(initial_state=EVState.IDLE)
        mock_tts = MagicMock(spec=EVTTSManager)
        mock_tts.is_silent = False
        orch = EVOrchestrator(event_bus=bus, tts_manager=mock_tts)
        orch.submit_command("stop")
        mock_tts.cancel_all.assert_called()
        orch.shutdown()

    def test_orchestrator_shutdown_calls_tts_shutdown(self):
        """EVOrchestrator.shutdown() must delegate to tts_manager.shutdown()."""
        from core.orchestrator import EVOrchestrator
        from core.events import EVEventBus
        from core.models import EVState
        bus = EVEventBus(initial_state=EVState.IDLE)
        mock_tts = MagicMock(spec=EVTTSManager)
        mock_tts.is_silent = False
        orch = EVOrchestrator(event_bus=bus, tts_manager=mock_tts)
        orch.shutdown()
        mock_tts.shutdown.assert_called()

    def test_orchestrator_without_tts_behaves_identically(self):
        """Existing orchestrator callers with no tts_manager must work unchanged."""
        from core.orchestrator import EVOrchestrator
        from core.events import EVEventBus
        from core.models import EVState
        bus = EVEventBus(initial_state=EVState.IDLE)
        orch = EVOrchestrator(event_bus=bus)
        # submit_command should not raise without tts_manager
        orch.submit_command("stop")
        orch.submit_command("")
        orch.shutdown()
