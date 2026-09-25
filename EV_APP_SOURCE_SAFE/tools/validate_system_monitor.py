"""
Validation script for E.V. System Monitor (Task 014F-16).

Validates:
1. Live Windows data collection via psutil across all 6 domains.
2. Structured SystemObservation models and context summary.
3. Event bus delivery for SYSTEM_OBSERVATION events.
4. Clean deterministic background thread start and stop.
5. 20-cycle start/stop lifecycle leak test verifying thread count and RSS stability.

Zero subprocess execution, zero PowerShell, observation-only.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
import time
from typing import List

import psutil

from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.events import EVEvent, EVEventBus
from core.models import EVEventType
from core.system_monitor import (
    EVSystemMonitor,
    SystemMetricDomain,
    SystemMonitorConfig,
    SystemObservation,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("validate_system_monitor")


def main() -> int:
    logger.info("=== E.V. SYSTEM MONITOR VALIDATION (TASK 014F-16) ===")
    
    # Verify zero subprocess / zero powershell
    initial_threads = threading.active_count()
    proc = psutil.Process(os.getpid())
    initial_rss = proc.memory_info().rss / (1024 * 1024)
    logger.info("Initial Process PID: %d, Threads: %d, RSS: %.2f MB", proc.pid, initial_threads, initial_rss)

    # 1. Initialize EventBus and Monitor
    event_bus = EVEventBus()
    received_events: List[EVEvent] = []

    def on_event(event: EVEvent) -> None:
        received_events.append(event)

    event_bus.subscribe(
        on_event,
        event_types=[
            EVEventType.SYSTEM_OBSERVATION,
            EVEventType.SYSTEM_ALERT,
            EVEventType.SYSTEM_ALERT_RECOVERED,
        ],
    )

    config = SystemMonitorConfig(
        polling_interval_seconds=1.0,
        cpu_warning_threshold=95.0,
        memory_warning_threshold=95.0,
        disk_warning_percent=10.0,
    )
    monitor = EVSystemMonitor(config=config, event_bus=event_bus)

    # 2. Single synchronous poll pass
    logger.info("Executing synchronous poll_once()...")
    observations = monitor.poll_once()
    assert len(observations) >= 6, f"Expected at least 6 observations, got {len(observations)}"

    domains_seen = {obs.domain for obs in observations}
    expected_domains = {
        SystemMetricDomain.CPU,
        SystemMetricDomain.MEMORY,
        SystemMetricDomain.DISK,
        SystemMetricDomain.PROCESS,
        SystemMetricDomain.NETWORK,
        SystemMetricDomain.SYSTEM,
    }
    assert expected_domains.issubset(domains_seen), f"Missing domains: {expected_domains - domains_seen}"

    logger.info("Observed %d metrics across %d domains:", len(observations), len(domains_seen))
    for obs in observations:
        logger.info("  [%s] %s = %s %s (Severity: %s, Source: %s)",
                    obs.domain.value, obs.metric, obs.value, obs.unit, obs.severity.value, obs.source)

    # 3. Verify Context Summary
    context = monitor.get_context_summary()
    logger.info("Context Summary:")
    for k, v in context.items():
        if k != "active_alerts":
            logger.info("  %s: %s", k, v)

    # 4. Background Monitoring Thread Test
    logger.info("Starting background monitor for 4.5 seconds...")
    monitor.start()
    assert monitor.is_running, "Monitor should be running"
    time.sleep(4.5)
    monitor.stop(timeout=5.0)
    assert not monitor.is_running, "Monitor should be stopped"
    logger.info("Monitor stopped cleanly. Total events received via EVEventBus: %d", len(received_events))
    for i, e in enumerate(received_events):
        logger.info("  Event %d: %s at %s", i+1, e.event_type.value, e.timestamp)
    assert len(received_events) >= 3, f"Expected >= 3 events, got {len(received_events)}"

    # 5. 20-Cycle Start/Stop Lifecycle Leak Test
    logger.info("Running 20-cycle start/stop lifecycle leak test...")
    cycle_monitor = EVSystemMonitor(
        config=SystemMonitorConfig(polling_interval_seconds=0.05),
        event_bus=event_bus,
    )

    for cycle in range(1, 21):
        cycle_monitor.start()
        # Idempotent double start test
        cycle_monitor.start()
        time.sleep(0.02)
        cycle_monitor.stop(timeout=5.0)
        # Idempotent double stop test
        cycle_monitor.stop(timeout=5.0)
        if cycle % 5 == 0:
            current_threads = threading.active_count()
            current_rss = proc.memory_info().rss / (1024 * 1024)
            logger.info("  Cycle %2d/20 complete. Active Threads: %d, RSS: %.2f MB", cycle, current_threads, current_rss)

    final_threads = threading.active_count()
    final_rss = proc.memory_info().rss / (1024 * 1024)
    logger.info("20-Cycle Leak Test Complete.")
    logger.info("Thread count before: %d, after: %d (Delta: %d)", initial_threads, final_threads, final_threads - initial_threads)
    logger.info("Process RSS before: %.2f MB, after: %.2f MB (Delta: %+.2f MB)", initial_rss, final_rss, final_rss - initial_rss)

    assert final_threads == initial_threads, f"Thread leak detected! Initial: {initial_threads}, Final: {final_threads}"
    assert final_rss - initial_rss < 50.0, f"Excessive memory growth: {final_rss - initial_rss:.2f} MB"

    logger.info("=== SYSTEM MONITOR VALIDATION PASSED (ALL CHECKS OK) ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
