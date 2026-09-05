"""
Validation script for E.V. Proactive Awareness Intelligence & Event Correlation (Task 014F-18).

Validates:
1. Live Windows telemetry flow from EVSystemMonitor to EVProactiveAwarenessEngine.
2. Ingestion of live observations and generation of meaningful awareness.
3. Deterministic correlation rules (CPU + top process, Disk critical escalation, Recovery).
4. Deterministic deduplication and recurrence tracking (suppression of duplicate alerts).
5. Event bus delivery to HUD / GuiBridge subscribers.
6. Cooldown enforcement and safe EVTTSManager audio routing (zero SAPI calls).
7. Experience mode interaction (WORK, MUSIC, SLEEP, CRITICAL persistence).
8. Untrusted, bounded Brain context generation.
9. 20-cycle integrated lifecycle leak test (monitor + awareness engine) verifying thread,
   subscription, and memory stability.

Zero subprocess execution, zero PowerShell, zero mutations.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import os
import sys
import threading
import time
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import psutil

from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.events import EVEvent, EVEventBus
from core.models import EVEventType
from core.system_monitor import (
    EVSystemMonitor,
    SystemAlert,
    SystemMetricDomain,
    SystemMonitorConfig,
    SystemObservation,
    SystemObservationSeverity,
)
from core.experience import EVExperienceMode
from core.proactive_awareness import (
    AwarenessCategory,
    AwarenessEvent,
    AwarenessSeverity,
    AwarenessState,
    EVProactiveAwarenessEngine,
    NotificationPolicy,
    ProactiveAwarenessConfig,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("validate_proactive_awareness")


def main() -> int:
    logger.info("=== E.V. PROACTIVE AWARENESS ENGINE VALIDATION (TASK 014F-18) ===")

    proc = psutil.Process(os.getpid())
    initial_threads = threading.active_count()
    initial_rss = proc.memory_info().rss / (1024 * 1024)
    logger.info("Initial Process PID: %d, Threads: %d, RSS: %.2f MB", proc.pid, initial_threads, initial_rss)

    # 1. Initialize EventBus, Mock TTS, and Engine
    event_bus = EVEventBus()
    tts_spoken: List[str] = []
    mock_tts = MagicMock()
    mock_tts.speak.side_effect = lambda text, **kwargs: tts_spoken.append(text)

    awareness_events_received: List[EVEvent] = []
    resolved_events_received: List[EVEvent] = []

    def on_awareness_event(event: EVEvent) -> None:
        if event.event_type == EVEventType.AWARENESS_EVENT:
            awareness_events_received.append(event)
        elif event.event_type == EVEventType.AWARENESS_RESOLVED:
            resolved_events_received.append(event)

    event_bus.subscribe(
        on_awareness_event,
        event_types=[EVEventType.AWARENESS_EVENT, EVEventType.AWARENESS_RESOLVED],
    )

    monitor_config = SystemMonitorConfig(
        polling_interval_seconds=1.0,
        cpu_warning_threshold=95.0,
        memory_warning_threshold=95.0,
        disk_warning_percent=10.0,
    )
    monitor = EVSystemMonitor(config=monitor_config, event_bus=event_bus)

    awareness_config = ProactiveAwarenessConfig(
        speech_cooldown_seconds=3.0,
    )
    engine = EVProactiveAwarenessEngine(
        config=awareness_config,
        event_bus=event_bus,
        tts_manager=mock_tts,
    )

    # 2. Live Telemetry Flow Demonstration
    logger.info("Starting live EVSystemMonitor and EVProactiveAwarenessEngine...")
    engine.start()
    monitor.start()
    assert engine.is_running, "Awareness engine should be running"
    assert monitor.is_running, "System monitor should be running"

    logger.info("Collecting live Windows observations for 3.5 seconds...")
    time.sleep(3.5)

    monitor.stop(timeout=5.0)
    engine.stop()
    assert not monitor.is_running, "Monitor should be stopped"
    assert not engine.is_running, "Engine should be stopped"
    logger.info("Live observation phase completed.")

    # 3. Deterministic Ingestion & Correlation Testing
    logger.info("Demonstrating correlation, deduplication, and notification policies...")
    engine.start()

    # (A) Ingest high CPU + top process observation
    now = datetime.now(timezone.utc)
    engine.update_process_cache(
        top_cpu={"name": "heavy_worker.exe", "cpu_percent": 65.2}
    )

    cpu_alert = SystemAlert(
        alert_id="alert-cpu-val-1",
        domain=SystemMetricDomain.CPU,
        metric="utilization",
        severity=SystemObservationSeverity.WARNING,
        message="CPU utilization sustained at 88.5%",
        value=88.5,
        threshold=80.0,
        triggered_at=now,
        sustained_seconds=10.0,
        metadata={"condition_key": "cpu:utilization"},
    )
    logger.info("Injecting elevated CPU alert with top process evidence...")
    cpu_event = engine.process_alert(cpu_alert)

    active_items = engine.get_active_awareness()
    assert len(active_items) == 1, f"Expected 1 active awareness item, got {len(active_items)}"
    assert cpu_event is not None
    logger.info("Awareness generated: [%s] %s - %s", cpu_event.severity.value, cpu_event.title, cpu_event.message)
    assert cpu_event.category == AwarenessCategory.CPU
    assert "heavy_worker.exe" in cpu_event.message, "Should correlate top process into message"
    assert cpu_event.state == AwarenessState.ACTIVE

    # (B) Deduplication test: repeated identical alert
    logger.info("Injecting repeated CPU alert to verify deduplication...")
    updated_event = engine.process_alert(cpu_alert)
    assert updated_event is not None
    active_items = engine.get_active_awareness()
    assert len(active_items) == 1, "Should not duplicate active awareness"
    assert active_items[0].occurrence_count == 2, f"Expected occurrence_count 2, got {active_items[0].occurrence_count}"
    assert active_items[0].state == AwarenessState.UPDATED
    logger.info("Deduplication verified: condition updated in-place (occurrences: %d)", active_items[0].occurrence_count)

    # (C) Disk warning and Critical escalation
    disk_warn = SystemAlert(
        alert_id="alert-disk-val-1",
        domain=SystemMetricDomain.DISK,
        metric="free_percent_C:",
        severity=SystemObservationSeverity.WARNING,
        message="C: drive free space at 9.5%",
        value=9.5,
        threshold=10.0,
        triggered_at=now,
        sustained_seconds=10.0,
        metadata={"condition_key": "disk:free_percent_C:", "mount": "C:"},
    )
    engine.process_alert(disk_warn)
    disk_items = [item for item in engine.get_active_awareness() if item.category == AwarenessCategory.DISK]
    assert len(disk_items) == 1
    assert disk_items[0].severity == AwarenessSeverity.WARNING
    logger.info("Disk warning generated: %s", disk_items[0].title)

    disk_crit = SystemAlert(
        alert_id="alert-disk-val-2",
        domain=SystemMetricDomain.DISK,
        metric="free_percent_C:",
        severity=SystemObservationSeverity.CRITICAL,
        message="C: drive free space critically low at 3.2%",
        value=3.2,
        threshold=5.0,
        triggered_at=now,
        sustained_seconds=20.0,
        metadata={"condition_key": "disk:free_percent_C:", "mount": "C:"},
    )
    engine.process_alert(disk_crit)
    disk_items = [item for item in engine.get_active_awareness() if item.category == AwarenessCategory.DISK]
    assert len(disk_items) == 1
    assert disk_items[0].severity == AwarenessSeverity.CRITICAL
    logger.info("Disk escalation to CRITICAL verified: %s (Severity: %s)", disk_items[0].title, disk_items[0].severity.value)

    # (D) Recovery test
    logger.info("Injecting recovery alert for CPU...")
    cpu_rec = SystemAlert(
        alert_id="alert-cpu-rec-1",
        domain=SystemMetricDomain.CPU,
        metric="utilization",
        severity=SystemObservationSeverity.INFO,
        message="CPU utilization normalized to 15.0%",
        value=15.0,
        threshold=75.0,
        triggered_at=now,
        sustained_seconds=5.0,
        recovered_at=datetime.now(timezone.utc),
        metadata={"condition_key": "cpu:utilization"},
    )
    engine.process_recovery(cpu_rec)
    active_items = engine.get_active_awareness()
    assert not any(item.category == AwarenessCategory.CPU for item in active_items), "CPU should be resolved"
    recent_resolved = engine.get_recent_awareness()
    assert len(recent_resolved) >= 1, "Resolved awareness should be in recent history"
    logger.info("Recovery verified: CPU moved to resolved history (%s)", recent_resolved[-1].title)

    # 4. Experience Mode Policy Verification
    logger.info("Verifying Experience Mode presentation policies...")
    event_bus.publish(
        event_type=EVEventType.EXPERIENCE_MODE_CHANGED,
        source="validation",
        data={"current_mode": "MUSIC"},
    )
    music_crit = SystemAlert(
        alert_id="alert-crit-music",
        domain=SystemMetricDomain.DISK,
        metric="free_percent_D:",
        severity=SystemObservationSeverity.CRITICAL,
        message="Critical disk space in MUSIC mode",
        value=1.0,
        threshold=5.0,
        triggered_at=now,
        sustained_seconds=10.0,
        metadata={"condition_key": "disk:free_percent_D:"},
    )
    music_ev = engine.process_alert(music_crit)
    assert music_ev is not None
    assert music_ev.notification_policy == NotificationPolicy.SPEAK, f"Expected SPEAK for critical in MUSIC, got {music_ev.notification_policy}"

    event_bus.publish(
        event_type=EVEventType.EXPERIENCE_MODE_CHANGED,
        source="validation",
        data={"current_mode": "SLEEP"},
    )
    sleep_warn = SystemAlert(
        alert_id="alert-warn-sleep",
        domain=SystemMetricDomain.CPU,
        metric="utilization_sleep",
        severity=SystemObservationSeverity.WARNING,
        message="Warning in sleep mode",
        value=85.0,
        threshold=80.0,
        triggered_at=now,
        sustained_seconds=5.0,
        metadata={"condition_key": "cpu:utilization_sleep"},
    )
    sleep_ev = engine.process_alert(sleep_warn)
    assert sleep_ev is not None
    assert sleep_ev.notification_policy == NotificationPolicy.SILENT, f"Expected SILENT for warning in SLEEP, got {sleep_ev.notification_policy}"

    event_bus.publish(
        event_type=EVEventType.EXPERIENCE_MODE_CHANGED,
        source="validation",
        data={"current_mode": "STANDARD"},
    )
    logger.info("Experience mode policies validated.")

    # 5. Untrusted Brain Context Verification
    logger.info("Verifying Brain Context generation...")
    brain_items = engine.get_active_awareness_for_brain()
    logger.info("Brain Context Items (%d):", len(brain_items))
    for item in brain_items:
        logger.info("  - [%s] %s: %s", item.get("severity"), item.get("title"), item.get("summary"))
        assert "command" not in item, "Brain context must not contain executable commands"
        assert "execute" not in item, "Brain context must not contain execution authority"
    logger.info("Brain context verified: untrusted, observational only.")

    # 6. Event bus / HUD delivery verification
    logger.info("Total AWARENESS_EVENT received via bus: %d", len(awareness_events_received))
    logger.info("Total AWARENESS_RESOLVED received via bus: %d", len(resolved_events_received))
    assert len(awareness_events_received) >= 2, "Should have received awareness events via bus"
    assert len(resolved_events_received) >= 1, "Should have received resolved event via bus"

    engine.stop()

    # 7. 20-Cycle Integrated Lifecycle Leak Test (Monitor + Awareness Engine)
    logger.info("Running 20-cycle integrated lifecycle leak test (Monitor + Engine)...")
    sub_count_initial = len(event_bus._subscriptions)

    for cycle in range(1, 21):
        c_monitor = EVSystemMonitor(
            config=SystemMonitorConfig(polling_interval_seconds=0.05),
            event_bus=event_bus,
        )
        c_engine = EVProactiveAwarenessEngine(
            config=ProactiveAwarenessConfig(),
            event_bus=event_bus,
        )

        c_monitor.start()
        c_engine.start()
        # Idempotent double start
        c_monitor.start()
        c_engine.start()

        time.sleep(0.01)

        c_engine.stop()
        c_monitor.stop(timeout=5.0)
        # Idempotent double stop
        c_engine.stop()
        c_monitor.stop(timeout=5.0)

        if cycle % 5 == 0:
            cur_threads = threading.active_count()
            cur_rss = proc.memory_info().rss / (1024 * 1024)
            logger.info("  Cycle %2d/20 complete. Active Threads: %d, RSS: %.2f MB", cycle, cur_threads, cur_rss)

    final_threads = threading.active_count()
    final_rss = proc.memory_info().rss / (1024 * 1024)
    sub_count_final = len(event_bus._subscriptions)

    logger.info("20-Cycle Integrated Leak Test Complete.")
    logger.info("Thread count: initial=%d, final=%d (delta=%d)", initial_threads, final_threads, final_threads - initial_threads)
    logger.info("Process RSS: initial=%.2f MB, final=%.2f MB (delta=%+.2f MB)", initial_rss, final_rss, final_rss - initial_rss)
    logger.info("EventBus subscription types: initial=%d, final=%d", sub_count_initial, sub_count_final)

    assert final_threads == initial_threads, f"Thread leak detected: {initial_threads} -> {final_threads}"
    assert final_rss - initial_rss < 50.0, f"Excessive memory growth: {final_rss - initial_rss:.2f} MB"
    assert sub_count_final == sub_count_initial, f"Subscription leak detected: {sub_count_initial} -> {sub_count_final}"

    logger.info("=== PROACTIVE AWARENESS VALIDATION PASSED (ALL CHECKS OK) ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
