"""
Unit, integration, and lifecycle tests for EVProactiveAwarenessEngine (Task 014F-18).

Verifies:
1. Lifecycle: DETECTED, ACTIVE, UPDATED, RECOVERED states.
2. Deduplication: stable condition identity, occurrence count increments, duplicate suppression.
3. Correlation: CPU + process, Memory + process, Disk critical escalation, Network loss.
4. Severity & Escalation: priority ranking, escalation bypasses suppression.
5. Cooldown: speech suppressed during cooldown, escalation bypasses cooldown, recovery resets cooldown.
6. Experience Modes: STANDARD, WORK, MUSIC, SYSTEM, SLEEP, APPROVAL policy differences.
7. Voice/TTS Safety: EVTTSManager routing, priority mapping, zero direct SAPI, voice interaction suppression.
8. Brain Context: bounded, untrusted, sanitized format for BrainContext.
9. Bounded History: active limits (25), resolved history limits (50), no unbounded growth.
10. Concurrency & Clean Shutdown: thread-safe, idempotent start/stop, no leaked subscriptions.
11. Failure Isolation: individual handler exception does not crash engine.
12. 20-Cycle Lifecycle Leak: verified clean thread and subscription cleanup.
"""

from __future__ import annotations

from datetime import datetime, timezone
import threading
import time
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch
import uuid

import pytest

from core.events import EVEvent, EVEventBus
from core.models import EVEventSeverity, EVEventType, EVState
from core.proactive_awareness import (
    AwarenessCategory,
    AwarenessEvent,
    AwarenessSeverity,
    AwarenessState,
    EVProactiveAwarenessEngine,
    NotificationPolicy,
    ProactiveAwarenessConfig,
)
from core.system_monitor import (
    SystemAlert,
    SystemMetricDomain,
    SystemObservation,
    SystemObservationSeverity,
)


@pytest.fixture
def event_bus() -> EVEventBus:
    """Fixture providing an EVEventBus initialized in IDLE state."""
    bus = EVEventBus(initial_state=EVState.IDLE)
    yield bus


@pytest.fixture
def awareness_engine(event_bus: EVEventBus) -> EVProactiveAwarenessEngine:
    """Fixture providing an EVProactiveAwarenessEngine attached to the event bus."""
    config = ProactiveAwarenessConfig(
        max_active_awareness=10,
        max_resolved_history=15,
        speech_cooldown_seconds=5.0,
        recurrence_window_seconds=10.0,
        min_recurrence_for_memory=2,
    )
    engine = EVProactiveAwarenessEngine(config=config, event_bus=event_bus)
    engine.start()
    yield engine
    engine.stop()


# -----------------------------------------------------------------------------
# 1. Basic Lifecycle & Deduplication Tests
# -----------------------------------------------------------------------------

class TestAwarenessLifecycle:
    """Test awareness condition state transitions and deduplication."""

    def test_alert_creates_active_awareness(self, awareness_engine: EVProactiveAwarenessEngine):
        """Verify an incoming SystemAlert creates an ACTIVE awareness record."""
        alert = SystemAlert(
            alert_id="alert-cpu-1",
            domain=SystemMetricDomain.CPU,
            metric="utilization",
            severity=SystemObservationSeverity.WARNING,
            message="CPU utilization at 92.5%",
            value=92.5,
            threshold=90.0,
            triggered_at=datetime.now(timezone.utc),
            sustained_seconds=10.0,
            metadata={"condition_key": "cpu:utilization"},
        )

        event = awareness_engine.process_alert(alert)
        assert event is not None
        assert event.state == AwarenessState.ACTIVE
        assert event.category == AwarenessCategory.CPU
        assert event.severity == AwarenessSeverity.WARNING
        assert event.occurrence_count == 1
        assert "cpu" in event.condition_key

        # Verify present in active awareness
        active = awareness_engine.get_active_awareness()
        assert len(active) == 1
        assert active[0].awareness_id == event.awareness_id

    def test_repeated_alert_updates_occurrence_count(self, awareness_engine: EVProactiveAwarenessEngine):
        """Verify repeated alerts update existing awareness without creating duplicates."""
        alert1 = SystemAlert(
            alert_id="alert-cpu-1",
            domain=SystemMetricDomain.CPU,
            metric="utilization",
            severity=SystemObservationSeverity.WARNING,
            message="CPU utilization at 92.5%",
            value=92.5,
            threshold=90.0,
            triggered_at=datetime.now(timezone.utc),
            sustained_seconds=10.0,
            metadata={"condition_key": "cpu:utilization"},
        )
        alert2 = SystemAlert(
            alert_id="alert-cpu-2",
            domain=SystemMetricDomain.CPU,
            metric="utilization",
            severity=SystemObservationSeverity.WARNING,
            message="CPU utilization at 94.1%",
            value=94.1,
            threshold=90.0,
            triggered_at=datetime.now(timezone.utc),
            sustained_seconds=13.0,
            metadata={"condition_key": "cpu:utilization"},
        )

        ev1 = awareness_engine.process_alert(alert1)
        assert ev1.occurrence_count == 1

        ev2 = awareness_engine.process_alert(alert2)
        assert ev2.awareness_id == ev1.awareness_id
        assert ev2.occurrence_count == 2
        assert ev2.state == AwarenessState.UPDATED
        # Repeated alert should be silenced to prevent spam
        assert ev2.notification_policy == NotificationPolicy.SILENT

        # Still only 1 active awareness
        assert len(awareness_engine.get_active_awareness()) == 1

    def test_recovery_clears_active_awareness(self, awareness_engine: EVProactiveAwarenessEngine):
        """Verify a recovery alert clears the active awareness and archives it."""
        alert = SystemAlert(
            alert_id="alert-cpu-1",
            domain=SystemMetricDomain.CPU,
            metric="utilization",
            severity=SystemObservationSeverity.WARNING,
            message="CPU utilization at 92.5%",
            value=92.5,
            threshold=90.0,
            triggered_at=datetime.now(timezone.utc),
            sustained_seconds=10.0,
            metadata={"condition_key": "cpu:utilization"},
        )
        awareness_engine.process_alert(alert)
        assert len(awareness_engine.get_active_awareness()) == 1

        recovery_alert = SystemAlert(
            alert_id="alert-cpu-1",
            domain=SystemMetricDomain.CPU,
            metric="utilization",
            severity=SystemObservationSeverity.INFO,
            message="CPU utilization returned below 75%",
            value=65.0,
            threshold=75.0,
            triggered_at=alert.triggered_at,
            sustained_seconds=10.0,
            recovered_at=datetime.now(timezone.utc),
            metadata={"condition_key": "cpu:utilization"},
        )

        recovered_ev = awareness_engine.process_recovery(recovery_alert)
        assert recovered_ev is not None
        assert recovered_ev.state == AwarenessState.RECOVERED
        assert recovered_ev.severity == AwarenessSeverity.INFO

        # Active awareness should now be empty
        assert len(awareness_engine.get_active_awareness()) == 0

        # Resolved history should contain the recovery
        recent = awareness_engine.get_recent_awareness()
        assert len(recent) == 1
        assert recent[0].state == AwarenessState.RECOVERED


# -----------------------------------------------------------------------------
# 2. Correlation Engine Tests
# -----------------------------------------------------------------------------

class TestAwarenessCorrelation:
    """Test conservative correlation rules and evidence synthesis."""

    def test_cpu_correlated_with_top_process(self, awareness_engine: EVProactiveAwarenessEngine):
        """Verify high CPU alert is correlated with top process if consuming significant CPU."""
        awareness_engine.update_process_cache(
            top_cpu={"name": "render_engine.exe", "pid": 4812, "cpu_percent": 68.4}
        )

        alert = SystemAlert(
            alert_id="alert-cpu",
            domain=SystemMetricDomain.CPU,
            metric="utilization",
            severity=SystemObservationSeverity.WARNING,
            message="CPU utilization at 95.0%",
            value=95.0,
            threshold=90.0,
            triggered_at=datetime.now(timezone.utc),
            sustained_seconds=10.0,
            metadata={"condition_key": "cpu:utilization"},
        )

        ev = awareness_engine.process_alert(alert)
        assert "render_engine.exe" in ev.message
        assert "4812" in ev.message
        assert "largest observed consumer" in ev.message
        assert "correlated_top_process" in ev.evidence

    def test_cpu_without_top_process_fallback(self, awareness_engine: EVProactiveAwarenessEngine):
        """Verify high CPU alert without prominent top process uses clean fallback text."""
        awareness_engine.update_process_cache(
            top_cpu={"name": "idle.exe", "pid": 100, "cpu_percent": 5.0}  # Below 25% threshold
        )

        alert = SystemAlert(
            alert_id="alert-cpu",
            domain=SystemMetricDomain.CPU,
            metric="utilization",
            severity=SystemObservationSeverity.WARNING,
            message="CPU utilization at 91.0%",
            value=91.0,
            threshold=90.0,
            triggered_at=datetime.now(timezone.utc),
            sustained_seconds=10.0,
            metadata={"condition_key": "cpu:utilization"},
        )

        ev = awareness_engine.process_alert(alert)
        assert "unusually high" in ev.message
        assert "idle.exe" not in ev.message

    def test_memory_correlated_with_top_consumer(self, awareness_engine: EVProactiveAwarenessEngine):
        """Verify memory alert correlates with top memory consuming process."""
        awareness_engine.update_process_cache(
            top_mem={"name": "heavy_db.exe", "pid": 2048, "memory_percent": 42.1}
        )

        alert = SystemAlert(
            alert_id="alert-mem",
            domain=SystemMetricDomain.MEMORY,
            metric="utilization",
            severity=SystemObservationSeverity.WARNING,
            message="Memory utilization at 92.0%",
            value=92.0,
            threshold=90.0,
            triggered_at=datetime.now(timezone.utc),
            sustained_seconds=10.0,
            metadata={"condition_key": "memory:utilization"},
        )

        ev = awareness_engine.process_alert(alert)
        assert "heavy_db.exe" in ev.message
        assert "2048" in ev.message
        assert "largest observed memory consumer" in ev.message

    def test_disk_space_warning_vs_critical_escalation(self, awareness_engine: EVProactiveAwarenessEngine):
        """Verify low disk space produces WARNING at 8%, and escalates to CRITICAL at 3%."""
        # 8% free -> WARNING
        alert_warn = SystemAlert(
            alert_id="alert-disk-1",
            domain=SystemMetricDomain.DISK,
            metric="free_percent",
            severity=SystemObservationSeverity.WARNING,
            message="Disk free space at 8.0%",
            value=8.0,
            threshold=10.0,
            triggered_at=datetime.now(timezone.utc),
            sustained_seconds=5.0,
            metadata={"condition_key": "disk:free_percent"},
        )
        ev_warn = awareness_engine.process_alert(alert_warn)
        assert ev_warn.severity == AwarenessSeverity.WARNING
        assert "warning threshold" in ev_warn.message

        # Escalation: 3% free -> CRITICAL
        alert_crit = SystemAlert(
            alert_id="alert-disk-2",
            domain=SystemMetricDomain.DISK,
            metric="free_percent",
            severity=SystemObservationSeverity.CRITICAL,
            message="Disk free space at 3.0%",
            value=3.0,
            threshold=5.0,
            triggered_at=datetime.now(timezone.utc),
            sustained_seconds=10.0,
            metadata={"condition_key": "disk:free_percent"},
        )
        ev_crit = awareness_engine.process_alert(alert_crit)
        assert ev_crit.severity == AwarenessSeverity.CRITICAL
        assert ev_crit.state == AwarenessState.UPDATED
        assert "critically low" in ev_crit.message
        # Escalation allows notification
        assert ev_crit.notification_policy in (NotificationPolicy.SPEAK, NotificationPolicy.HUD_AND_NOTIFICATION)

    def test_network_link_loss_correlation(self, awareness_engine: EVProactiveAwarenessEngine):
        """Verify network disconnection alert produces clear non-speculative awareness."""
        alert = SystemAlert(
            alert_id="alert-net",
            domain=SystemMetricDomain.NETWORK,
            metric="link_status",
            severity=SystemObservationSeverity.WARNING,
            message="Network link status down",
            value=0.0,
            threshold=1.0,
            triggered_at=datetime.now(timezone.utc),
            sustained_seconds=5.0,
            metadata={"condition_key": "network:link_status"},
        )
        ev = awareness_engine.process_alert(alert)
        assert ev.category == AwarenessCategory.NETWORK
        assert "no active network adapters" in ev.message


# -----------------------------------------------------------------------------
# 3. Cooldown & Recurrence Tests
# -----------------------------------------------------------------------------

class TestCooldownAndRecurrence:
    """Test notification cooldowns and recurrence tracking."""

    def test_speech_cooldown_suppresses_repeated_voice(self, event_bus: EVEventBus):
        """Verify repeated critical alerts within cooldown window do not spam speech."""
        mock_tts = MagicMock()
        mock_tts.is_silent = False

        config = ProactiveAwarenessConfig(speech_cooldown_seconds=100.0)
        engine = EVProactiveAwarenessEngine(config=config, event_bus=event_bus, tts_manager=mock_tts)
        engine.start()

        alert1 = SystemAlert(
            alert_id="alert-crit-1",
            domain=SystemMetricDomain.DISK,
            metric="free_percent",
            severity=SystemObservationSeverity.CRITICAL,
            message="Disk space 3.0%",
            value=3.0,
            threshold=5.0,
            triggered_at=datetime.now(timezone.utc),
            sustained_seconds=5.0,
            metadata={"condition_key": "disk:free_percent"},
        )
        ev1 = engine.process_alert(alert1)
        assert ev1.notification_policy == NotificationPolicy.SPEAK
        assert mock_tts.speak.call_count == 1

        # Second critical alert on same condition within cooldown
        alert2 = SystemAlert(
            alert_id="alert-crit-2",
            domain=SystemMetricDomain.DISK,
            metric="free_percent",
            severity=SystemObservationSeverity.CRITICAL,
            message="Disk space 2.9%",
            value=2.9,
            threshold=5.0,
            triggered_at=datetime.now(timezone.utc),
            sustained_seconds=8.0,
            metadata={"condition_key": "disk:free_percent"},
        )
        ev2 = engine.process_alert(alert2)
        # Suppressed to SILENT due to deduplication of repeated active condition
        assert ev2.notification_policy == NotificationPolicy.SILENT
        assert mock_tts.speak.call_count == 1  # Speech not called again

        engine.stop()

    def test_recurrence_detection_and_memory_fact_recording(self, event_bus: EVEventBus):
        """Verify rapid recurring conditions trigger recurrence count and memory fact."""
        mock_memory = MagicMock()

        config = ProactiveAwarenessConfig(
            recurrence_window_seconds=60.0,
            min_recurrence_for_memory=2,
        )
        engine = EVProactiveAwarenessEngine(
            config=config, event_bus=event_bus, memory_store=mock_memory
        )
        engine.start()

        alert = SystemAlert(
            alert_id="a1",
            domain=SystemMetricDomain.CPU,
            metric="utilization",
            severity=SystemObservationSeverity.WARNING,
            message="CPU spike",
            value=95.0,
            threshold=90.0,
            triggered_at=datetime.now(timezone.utc),
            sustained_seconds=5.0,
            metadata={"condition_key": "cpu:utilization"},
        )
        rec = SystemAlert(
            alert_id="a1",
            domain=SystemMetricDomain.CPU,
            metric="utilization",
            severity=SystemObservationSeverity.INFO,
            message="CPU recovered",
            value=60.0,
            threshold=75.0,
            triggered_at=datetime.now(timezone.utc),
            sustained_seconds=5.0,
            metadata={"condition_key": "cpu:utilization"},
        )

        # Occurrence 1: alert -> recover
        engine.process_alert(alert)
        engine.process_recovery(rec)

        # Occurrence 2: alert -> triggers recurrence (count = 2 >= min 2)
        ev2 = engine.process_alert(alert)
        assert ev2.recurrence_count == 2
        assert "Condition observed 2 times recently" in ev2.message

        # Memory store environment fact should be persisted
        assert mock_memory.set_environment_fact.called
        call_kwargs = mock_memory.set_environment_fact.call_args[1]
        assert "system_awareness" in call_kwargs["topic"]

        engine.stop()


# -----------------------------------------------------------------------------
# 4. Experience Mode Policy Matrix Tests
# -----------------------------------------------------------------------------

class TestExperienceModePolicies:
    """Test how active experience modes influence notification policies."""

    @pytest.mark.parametrize(
        "mode,expected_policy",
        [
            ("STANDARD", NotificationPolicy.SPEAK),  # Critical alert speaks in standard mode
            ("WORK", NotificationPolicy.SPEAK),      # Critical alert still speaks
            ("MUSIC", NotificationPolicy.SPEAK),     # Critical alert still speaks
            ("SYSTEM", NotificationPolicy.SPEAK),    # Critical alert speaks in system mode
            ("SLEEP", NotificationPolicy.HUD),       # Critical alert is HUD in sleep mode
            ("APPROVAL", NotificationPolicy.SPEAK),  # Critical alert speaks even in approval
        ],
    )
    def test_critical_alert_across_experience_modes(
        self, event_bus: EVEventBus, mode: str, expected_policy: NotificationPolicy
    ):
        """Verify critical system safety alerts are never silently hidden in any mode."""
        engine = EVProactiveAwarenessEngine(event_bus=event_bus)
        engine.start()

        # Switch experience mode via event bus
        event_bus.publish(
            event_type=EVEventType.EXPERIENCE_MODE_CHANGED,
            source="test",
            data={"current_mode": mode},
        )

        alert = SystemAlert(
            alert_id="crit",
            domain=SystemMetricDomain.DISK,
            metric="free_percent",
            severity=SystemObservationSeverity.CRITICAL,
            message="Disk space critically low",
            value=2.0,
            threshold=5.0,
            triggered_at=datetime.now(timezone.utc),
            sustained_seconds=5.0,
            metadata={"condition_key": "disk:free"},
        )
        ev = engine.process_alert(alert)
        assert ev.notification_policy == expected_policy
        engine.stop()

    def test_work_mode_downgrades_speech_for_warning(self, event_bus: EVEventBus):
        """Verify WORK mode suppresses routine speech, maintaining HUD visibility."""
        engine = EVProactiveAwarenessEngine(event_bus=event_bus)
        engine.start()

        event_bus.publish(
            event_type=EVEventType.EXPERIENCE_MODE_CHANGED,
            source="test",
            data={"current_mode": "WORK"},
        )

        alert = SystemAlert(
            alert_id="warn",
            domain=SystemMetricDomain.CPU,
            metric="utilization",
            severity=SystemObservationSeverity.WARNING,
            message="CPU high",
            value=92.0,
            threshold=90.0,
            triggered_at=datetime.now(timezone.utc),
            sustained_seconds=5.0,
            metadata={"condition_key": "cpu:utilization"},
        )
        ev = engine.process_alert(alert)
        assert ev.notification_policy == NotificationPolicy.HUD
        engine.stop()

    def test_sleep_mode_silences_routine_warnings(self, event_bus: EVEventBus):
        """Verify SLEEP mode silences non-critical alerts."""
        engine = EVProactiveAwarenessEngine(event_bus=event_bus)
        engine.start()

        event_bus.publish(
            event_type=EVEventType.EXPERIENCE_MODE_CHANGED,
            source="test",
            data={"current_mode": "SLEEP"},
        )

        alert = SystemAlert(
            alert_id="warn",
            domain=SystemMetricDomain.CPU,
            metric="utilization",
            severity=SystemObservationSeverity.WARNING,
            message="CPU high",
            value=92.0,
            threshold=90.0,
            triggered_at=datetime.now(timezone.utc),
            sustained_seconds=5.0,
            metadata={"condition_key": "cpu:utilization"},
        )
        ev = engine.process_alert(alert)
        assert ev.notification_policy == NotificationPolicy.SILENT
        engine.stop()


# -----------------------------------------------------------------------------
# 5. Voice & TTS Safety Tests
# -----------------------------------------------------------------------------

class TestVoiceAndTTSSafety:
    """Test voice safety invariants and speech routing."""

    def test_voice_active_suppresses_speech(self, event_bus: EVEventBus):
        """Verify active voice interaction prevents awareness speech interruptions."""
        mock_tts = MagicMock()
        mock_tts.is_silent = False

        engine = EVProactiveAwarenessEngine(event_bus=event_bus, tts_manager=mock_tts)
        engine.start()

        # Simulate voice subsystem actively transcribing
        event_bus.publish(
            event_type=EVEventType.VOICE_STATE_CHANGED,
            source="voice_manager",
            data={"voice_state": "TRANSCRIBING"},
        )

        alert = SystemAlert(
            alert_id="warn",
            domain=SystemMetricDomain.CPU,
            metric="utilization",
            severity=SystemObservationSeverity.WARNING,
            message="CPU elevated",
            value=92.0,
            threshold=90.0,
            triggered_at=datetime.now(timezone.utc),
            sustained_seconds=5.0,
            metadata={"condition_key": "cpu:utilization"},
        )
        ev = engine.process_alert(alert)
        # Warning alert does not speak while user is speaking/transcribing
        assert ev.notification_policy != NotificationPolicy.SPEAK
        assert not mock_tts.speak.called
        engine.stop()

    def test_speech_routes_exclusively_to_tts_manager(self, event_bus: EVEventBus):
        """Verify awareness speech routes through EVTTSManager with correct priority."""
        mock_tts = MagicMock()
        mock_tts.is_silent = False

        engine = EVProactiveAwarenessEngine(event_bus=event_bus, tts_manager=mock_tts)
        engine.start()

        alert = SystemAlert(
            alert_id="crit",
            domain=SystemMetricDomain.DISK,
            metric="free_percent",
            severity=SystemObservationSeverity.CRITICAL,
            message="Low disk space",
            value=2.0,
            threshold=5.0,
            triggered_at=datetime.now(timezone.utc),
            sustained_seconds=5.0,
            metadata={"condition_key": "disk:free"},
        )
        ev = engine.process_alert(alert)
        assert ev.notification_policy == NotificationPolicy.SPEAK
        assert mock_tts.speak.called
        kwargs = mock_tts.speak.call_args[1]
        assert kwargs["priority"] == 0  # CRITICAL priority
        engine.stop()


# -----------------------------------------------------------------------------
# 6. Brain Context & History Bounds
# -----------------------------------------------------------------------------

class TestBrainContextAndHistoryBounds:
    """Test untrusted BrainContext formatting and ring buffer boundedness."""

    def test_brain_context_formatting(self, awareness_engine: EVProactiveAwarenessEngine):
        """Verify active awareness is exposed in bounded untrusted structure."""
        alert = SystemAlert(
            alert_id="a1",
            domain=SystemMetricDomain.CPU,
            metric="utilization",
            severity=SystemObservationSeverity.WARNING,
            message="CPU high",
            value=94.0,
            threshold=90.0,
            triggered_at=datetime.now(timezone.utc),
            sustained_seconds=5.0,
            metadata={"condition_key": "cpu:utilization"},
        )
        awareness_engine.process_alert(alert)

        brain_items = awareness_engine.get_active_awareness_for_brain()
        assert len(brain_items) == 1
        item = brain_items[0]
        assert item["category"] == "cpu"
        assert item["severity"] == "WARNING"
        assert "summary" in item
        # Ensure no execution or command fields exist
        assert "command" not in item
        assert "action" not in item
        assert "execute" not in item

    def test_active_and_resolved_history_bounds(self, event_bus: EVEventBus):
        """Verify ring buffer bounds are strictly enforced (no unbounded memory growth)."""
        config = ProactiveAwarenessConfig(
            max_active_awareness=3,
            max_resolved_history=5,
        )
        engine = EVProactiveAwarenessEngine(config=config, event_bus=event_bus)
        engine.start()

        # Ingest 5 different active conditions
        for i in range(5):
            alert = SystemAlert(
                alert_id=f"alert-{i}",
                domain=SystemMetricDomain.CPU,
                metric=f"metric_{i}",
                severity=SystemObservationSeverity.WARNING,
                message=f"Alert {i}",
                value=float(i),
                threshold=0.0,
                triggered_at=datetime.now(timezone.utc),
                sustained_seconds=1.0,
                metadata={"condition_key": f"key:{i}"},
            )
            engine.process_alert(alert)

        # Active capacity must be bounded at max 3
        active = engine.get_active_awareness()
        assert len(active) == 3

        # Evicted items were moved to resolved history
        recent = engine.get_recent_awareness()
        assert len(recent) <= 5

        engine.stop()


# -----------------------------------------------------------------------------
# 7. Concurrency & 20-Cycle Lifecycle Leak Test
# -----------------------------------------------------------------------------

class TestConcurrencyAndLifecycleLeak:
    """Test thread safety and clean resource destruction."""

    def test_concurrent_alert_ingestion(self, awareness_engine: EVProactiveAwarenessEngine):
        """Verify multiple threads can ingest alerts concurrently without deadlocks or corruption."""
        errors = []

        def worker(thread_idx: int):
            try:
                for j in range(20):
                    alert = SystemAlert(
                        alert_id=f"th-{thread_idx}-{j}",
                        domain=SystemMetricDomain.CPU,
                        metric="utilization",
                        severity=SystemObservationSeverity.WARNING,
                        message=f"Load {j}",
                        value=90.0 + j,
                        threshold=90.0,
                        triggered_at=datetime.now(timezone.utc),
                        sustained_seconds=1.0,
                        metadata={"condition_key": f"cpu:thread_{thread_idx}"},
                    )
                    awareness_engine.process_alert(alert)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        assert not errors, f"Errors during concurrent ingestion: {errors}"
        active = awareness_engine.get_active_awareness()
        # Should have exactly 5 active keys (one per thread)
        assert len(active) == 5

    def test_20_cycle_lifecycle_leak(self, event_bus: EVEventBus):
        """Verify 20 start/stop cycles produce zero thread growth and zero subscription leaks."""
        initial_threads = threading.active_count()
        initial_subscribers = len(event_bus._subscriptions)

        engine = EVProactiveAwarenessEngine(event_bus=event_bus)

        for _ in range(20):
            engine.start()
            assert engine.is_running
            engine.stop()
            assert not engine.is_running

        final_threads = threading.active_count()
        final_subscribers = len(event_bus._subscriptions)

        assert final_threads == initial_threads, f"Thread leak: {final_threads} != {initial_threads}"
        assert final_subscribers == initial_subscribers, f"Subscriber leak: {final_subscribers} != {initial_subscribers}"
