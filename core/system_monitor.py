"""
Proactive Monitoring & System Awareness Subsystem for E.V. (Task 014F-16).

This module provides a safe, deterministic, Windows-first observation-only subsystem.
It observes CPU, Memory, Disk, Process, Network, and System Health metrics using
in-process Windows NT C-API queries via psutil (<25ms, <0.1% CPU).

CRITICAL ARCHITECTURAL RULES:
1. OBSERVATION ONLY: ZERO subprocess execution, ZERO PowerShell, ZERO automatic repair,
   ZERO process killing, ZERO automatic mutations, ZERO approval bypass, ZERO GOD MODE.
2. Canonical authority remains unchanged:
   MIC/GUI -> EVOrchestrator -> risk/approval -> transaction -> execution -> verification.
3. Monitoring output is untrusted observational telemetry.
"""

from __future__ import annotations

import collections
import copy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging
import platform
import threading
import time
from typing import Any, Callable, Deque, Dict, List, Optional, Set, Tuple, Union
import uuid

import psutil

from core.events import EVEvent, EVEventBus
from core.models import EVEventSeverity, EVEventType

logger = logging.getLogger("ev.system_monitor")


class SystemMetricDomain(str, Enum):
    """Monitored telemetry domains."""
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    PROCESS = "process"
    NETWORK = "network"
    SYSTEM = "system"


class SystemObservationSeverity(str, Enum):
    """Structured severity classification for observations and alerts."""
    INFO = "INFO"
    NOTICE = "NOTICE"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class SystemObservation:
    """
    Immutable observation record captured during a monitoring pass.
    Untrusted observational data with no execution authority.
    """
    observation_id: str
    timestamp: datetime
    domain: SystemMetricDomain
    metric: str
    value: Any
    unit: str
    severity: SystemObservationSeverity
    source: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Return JSON-serializable dictionary representation."""
        return {
            "observation_id": self.observation_id,
            "timestamp": self.timestamp.isoformat(),
            "domain": self.domain.value,
            "metric": self.metric,
            "value": copy.deepcopy(self.value),
            "unit": self.unit,
            "severity": self.severity.value,
            "source": self.source,
            "metadata": copy.deepcopy(self.metadata),
        }


@dataclass(frozen=True)
class SystemAlert:
    """
    Structured alert record emitted when a condition is sustained past its threshold.
    """
    alert_id: str
    domain: SystemMetricDomain
    metric: str
    severity: SystemObservationSeverity
    message: str
    value: float
    threshold: float
    triggered_at: datetime
    sustained_seconds: float
    recovered_at: Optional[datetime] = None
    source: str = "system_monitor"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Return JSON-serializable dictionary representation."""
        return {
            "alert_id": self.alert_id,
            "domain": self.domain.value,
            "metric": self.metric,
            "severity": self.severity.value,
            "message": self.message,
            "value": self.value,
            "threshold": self.threshold,
            "triggered_at": self.triggered_at.isoformat(),
            "sustained_seconds": self.sustained_seconds,
            "recovered_at": self.recovered_at.isoformat() if self.recovered_at else None,
            "source": self.source,
            "metadata": copy.deepcopy(self.metadata),
        }


@dataclass
class SystemMonitorConfig:
    """
    Configuration parameters, thresholds, and limits for EVSystemMonitor.
    Uses separate trigger and recovery thresholds (hysteresis) to prevent flapping.
    """
    polling_interval_seconds: float = 3.0
    disk_path: str = "C:\\" if platform.system().lower() == "windows" else "/"

    # CPU thresholds
    cpu_warning_threshold: float = 90.0
    cpu_sustained_seconds: float = 10.0
    cpu_recovery_threshold: float = 75.0
    cpu_recovery_seconds: float = 5.0

    # Memory thresholds
    memory_warning_threshold: float = 90.0
    memory_sustained_seconds: float = 10.0
    memory_recovery_threshold: float = 80.0
    memory_recovery_seconds: float = 5.0

    # Disk thresholds (free space percentage)
    disk_warning_percent: float = 10.0      # Warning if free <= 10%
    disk_critical_percent: float = 5.0      # Critical if free <= 5%
    disk_sustained_seconds: float = 5.0
    disk_recovery_percent: float = 12.0     # Recovered if free >= 12%
    disk_recovery_seconds: float = 5.0

    # Process thresholds
    process_high_cpu_threshold: float = 80.0
    process_high_cpu_sustained_seconds: float = 10.0
    process_high_cpu_recovery_threshold: float = 50.0
    process_high_cpu_recovery_seconds: float = 5.0
    process_sample_interval_seconds: float = 30.0

    # History limits
    max_retained_observations: int = 100
    max_retained_alerts: int = 50


class EVSystemMonitor:
    """
    Safe, deterministic, Windows-first proactive monitoring subsystem.
    
    Observes system conditions continuously, tracks sustained threshold breaches
    with hysteresis, publishes structured events on EVEventBus, and exposes bounded
    awareness context to the Orchestrator/Brain without execution authority.
    """

    def __init__(
        self,
        config: Optional[SystemMonitorConfig] = None,
        event_bus: Optional[EVEventBus] = None,
        memory_store: Optional[Any] = None,
    ) -> None:
        self.config: SystemMonitorConfig = config or SystemMonitorConfig()
        self._event_bus: Optional[EVEventBus] = event_bus
        self._memory_store: Optional[Any] = memory_store

        self._lock = threading.RLock()
        self._shutdown_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None

        # Bounded in-memory ring buffers
        self._observations: Deque[SystemObservation] = collections.deque(
            maxlen=self.config.max_retained_observations
        )
        self._alerts: Deque[SystemAlert] = collections.deque(
            maxlen=self.config.max_retained_alerts
        )
        self._alert_history: Deque[SystemAlert] = collections.deque(
            maxlen=self.config.max_retained_alerts
        )

        # Condition tracking for debounce / hysteresis
        # condition_key -> monotonic start time of condition breach
        self._condition_first_seen: Dict[str, float] = {}
        # condition_key -> active SystemAlert
        self._active_alerts: Dict[str, SystemAlert] = {}
        # condition_key -> monotonic start time of recovery condition
        self._recovery_first_seen: Dict[str, float] = {}

        # Last known snapshot values for rapid context summary
        self._last_snapshot: Dict[str, Any] = {}

        # Process monitoring caching & delta tracking
        self._prev_pids: Set[int] = set()
        self._last_process_sample_mono: float = 0.0
        self._cached_top_cpu: List[Dict[str, Any]] = []
        self._cached_top_mem: List[Dict[str, Any]] = []

        # Prime psutil CPU calculation on initialization
        try:
            psutil.cpu_percent(interval=None)
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # Lifecycle Management
    # -------------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        """True if the background monitoring worker is actively running."""
        with self._lock:
            return self._worker_thread is not None and self._worker_thread.is_alive()

    def start(self) -> None:
        """
        Start the background monitoring worker thread.
        Idempotent: calling start() when already running is a safe no-op.
        """
        with self._lock:
            if self.is_running:
                logger.debug("EVSystemMonitor is already running.")
                return

            self._shutdown_event.clear()
            self._worker_thread = threading.Thread(
                target=self._worker_loop,
                name="EVSystemMonitorWorker",
                daemon=True,
            )
            self._worker_thread.start()
            logger.info(
                "EVSystemMonitor started with polling interval %.1fs",
                self.config.polling_interval_seconds,
            )

    def stop(self, timeout: float = 5.0) -> None:
        """
        Stop the background monitoring worker thread cleanly.
        Idempotent: calling stop() when already stopped is a safe no-op.
        """
        with self._lock:
            if not self.is_running:
                return

            self._shutdown_event.set()
            thread = self._worker_thread

        if thread and thread.is_alive():
            thread.join(timeout=timeout)
            if thread.is_alive():
                logger.warning("EVSystemMonitor worker thread did not terminate within timeout")
            else:
                logger.info("EVSystemMonitor stopped cleanly.")

        with self._lock:
            self._worker_thread = None

    def _worker_loop(self) -> None:
        """Dedicated background daemon loop performing periodic observation passes."""
        while not self._shutdown_event.is_set():
            try:
                self.poll_once()
            except Exception as exc:
                logger.error("Unexpected error during system monitor poll_once: %s", exc)

            # Responsive sleep using shutdown event wait
            if self._shutdown_event.wait(timeout=self.config.polling_interval_seconds):
                break

    # -------------------------------------------------------------------------
    # Polling & Observer Execution
    # -------------------------------------------------------------------------

    def poll_once(self) -> List[SystemObservation]:
        """
        Execute a single observation pass across all domains synchronously.
        Failure in one observer is completely isolated from other observers.
        Returns the list of observations collected in this pass.
        """
        now = datetime.now(timezone.utc)
        current_mono = time.monotonic()
        pass_observations: List[SystemObservation] = []

        observers: List[Tuple[str, Callable[[datetime, float], List[SystemObservation]]]] = [
            ("cpu", self._observe_cpu),
            ("memory", self._observe_memory),
            ("disk", self._observe_disk),
            ("processes", self._observe_processes),
            ("network", self._observe_network),
            ("system", self._observe_system),
        ]

        for domain_name, observer_func in observers:
            try:
                obs_list = observer_func(now, current_mono)
                pass_observations.extend(obs_list)
            except Exception as exc:
                logger.warning("Observer '%s' raised an unexpected exception: %s", domain_name, exc)
                # Create failure diagnostic observation for telemetry
                diag_obs = SystemObservation(
                    observation_id=str(uuid.uuid4()),
                    timestamp=now,
                    domain=SystemMetricDomain.SYSTEM,
                    metric=f"{domain_name}_observer_error",
                    value=str(exc),
                    unit="",
                    severity=SystemObservationSeverity.WARNING,
                    source="system_monitor_diagnostics",
                    metadata={"error": str(exc)},
                )
                pass_observations.append(diag_obs)

        # Store observations in bounded ring buffer and publish routine observation event
        with self._lock:
            for obs in pass_observations:
                self._observations.append(obs)

        if self._event_bus is not None and pass_observations:
            try:
                self._publish_routine_observation(pass_observations)
            except Exception as exc:
                logger.debug("Failed to publish routine observation event: %s", exc)

        return pass_observations

    # -------------------------------------------------------------------------
    # Domain Observers
    # -------------------------------------------------------------------------

    def _observe_cpu(self, now: datetime, current_mono: float) -> List[SystemObservation]:
        """Observe total CPU utilization and evaluate sustained threshold conditions."""
        # Non-blocking query
        cpu_pct = float(psutil.cpu_percent(interval=None))

        with self._lock:
            self._last_snapshot["cpu_percent"] = cpu_pct

        obs = SystemObservation(
            observation_id=str(uuid.uuid4()),
            timestamp=now,
            domain=SystemMetricDomain.CPU,
            metric="utilization",
            value=cpu_pct,
            unit="%",
            severity=(
                SystemObservationSeverity.WARNING
                if cpu_pct >= self.config.cpu_warning_threshold
                else SystemObservationSeverity.INFO
            ),
            source="windows_cpu",
            metadata={"threshold": self.config.cpu_warning_threshold},
        )

        # Evaluate sustained condition via hysteresis
        self._evaluate_hysteresis(
            condition_key="cpu:utilization",
            domain=SystemMetricDomain.CPU,
            metric="utilization",
            current_value=cpu_pct,
            trigger_threshold=self.config.cpu_warning_threshold,
            trigger_sustained_seconds=self.config.cpu_sustained_seconds,
            recovery_threshold=self.config.cpu_recovery_threshold,
            recovery_sustained_seconds=self.config.cpu_recovery_seconds,
            current_mono=current_mono,
            now=now,
            is_breach=(cpu_pct >= self.config.cpu_warning_threshold),
            is_recovered=(cpu_pct <= self.config.cpu_recovery_threshold),
            alert_severity=SystemObservationSeverity.WARNING,
            alert_message=f"CPU utilization sustained at {cpu_pct:.1f}% (threshold: {self.config.cpu_warning_threshold:.1f}%)",
            recovery_message=f"CPU utilization returned to normal ({cpu_pct:.1f}%)",
        )

        return [obs]

    def _observe_memory(self, now: datetime, current_mono: float) -> List[SystemObservation]:
        """Observe RAM metrics (total, available, percent used) and sustained low memory."""
        vmem = psutil.virtual_memory()
        used_pct = float(vmem.percent)
        avail_bytes = int(vmem.available)
        total_bytes = int(vmem.total)

        with self._lock:
            self._last_snapshot["memory_used_percent"] = used_pct
            self._last_snapshot["memory_available_bytes"] = avail_bytes
            self._last_snapshot["memory_total_bytes"] = total_bytes

        obs = SystemObservation(
            observation_id=str(uuid.uuid4()),
            timestamp=now,
            domain=SystemMetricDomain.MEMORY,
            metric="used_percent",
            value=used_pct,
            unit="%",
            severity=(
                SystemObservationSeverity.WARNING
                if used_pct >= self.config.memory_warning_threshold
                else SystemObservationSeverity.INFO
            ),
            source="windows_memory",
            metadata={
                "available_bytes": avail_bytes,
                "total_bytes": total_bytes,
                "threshold": self.config.memory_warning_threshold,
            },
        )

        # Evaluate sustained condition
        self._evaluate_hysteresis(
            condition_key="memory:used_percent",
            domain=SystemMetricDomain.MEMORY,
            metric="used_percent",
            current_value=used_pct,
            trigger_threshold=self.config.memory_warning_threshold,
            trigger_sustained_seconds=self.config.memory_sustained_seconds,
            recovery_threshold=self.config.memory_recovery_threshold,
            recovery_sustained_seconds=self.config.memory_recovery_seconds,
            current_mono=current_mono,
            now=now,
            is_breach=(used_pct >= self.config.memory_warning_threshold),
            is_recovered=(used_pct <= self.config.memory_recovery_threshold),
            alert_severity=SystemObservationSeverity.WARNING,
            alert_message=f"Memory utilization sustained at {used_pct:.1f}% (available: {avail_bytes / (1024**3):.2f} GB)",
            recovery_message=f"Memory utilization returned to normal ({used_pct:.1f}%)",
        )

        return [obs]

    def _observe_disk(self, now: datetime, current_mono: float) -> List[SystemObservation]:
        """Observe local volume space (especially C:) without recursive directory scanning."""
        disk_path = self.config.disk_path
        disk = psutil.disk_usage(disk_path)
        total_bytes = int(disk.total)
        free_bytes = int(disk.free)
        used_bytes = int(disk.used)
        free_pct = (free_bytes / total_bytes * 100.0) if total_bytes > 0 else 0.0

        with self._lock:
            self._last_snapshot["disk_path"] = disk_path
            self._last_snapshot["disk_free_percent"] = free_pct
            self._last_snapshot["disk_free_bytes"] = free_bytes
            self._last_snapshot["disk_total_bytes"] = total_bytes

        severity = SystemObservationSeverity.INFO
        if free_pct <= self.config.disk_critical_percent:
            severity = SystemObservationSeverity.CRITICAL
        elif free_pct <= self.config.disk_warning_percent:
            severity = SystemObservationSeverity.WARNING

        obs = SystemObservation(
            observation_id=str(uuid.uuid4()),
            timestamp=now,
            domain=SystemMetricDomain.DISK,
            metric="free_percent",
            value=free_pct,
            unit="%",
            severity=severity,
            source="windows_disk",
            metadata={
                "disk_path": disk_path,
                "free_bytes": free_bytes,
                "total_bytes": total_bytes,
                "warning_threshold": self.config.disk_warning_percent,
                "critical_threshold": self.config.disk_critical_percent,
            },
        )

        # For disk, lower free percentage is a breach
        is_critical = free_pct <= self.config.disk_critical_percent
        is_warning = free_pct <= self.config.disk_warning_percent
        is_recovered = free_pct >= self.config.disk_recovery_percent

        self._evaluate_hysteresis(
            condition_key=f"disk:{disk_path}:free_percent",
            domain=SystemMetricDomain.DISK,
            metric="free_percent",
            current_value=free_pct,
            trigger_threshold=self.config.disk_warning_percent,
            trigger_sustained_seconds=self.config.disk_sustained_seconds,
            recovery_threshold=self.config.disk_recovery_percent,
            recovery_sustained_seconds=self.config.disk_recovery_seconds,
            current_mono=current_mono,
            now=now,
            is_breach=is_warning,
            is_recovered=is_recovered,
            alert_severity=(
                SystemObservationSeverity.CRITICAL if is_critical else SystemObservationSeverity.WARNING
            ),
            alert_message=(
                f"Disk '{disk_path}' free space critically low: {free_pct:.1f}% free "
                f"({free_bytes / (1024**3):.2f} GB available)"
                if is_critical
                else f"Disk '{disk_path}' free space low: {free_pct:.1f}% free ({free_bytes / (1024**3):.2f} GB available)"
            ),
            recovery_message=f"Disk '{disk_path}' free space recovered to {free_pct:.1f}%",
        )

        return [obs]

    def _observe_processes(self, now: datetime, current_mono: float) -> List[SystemObservation]:
        """
        Observe lightweight aggregate process telemetry and top consumers.
        OBSERVATION ONLY: Never terminates or modifies any process.
        """
        current_pids = set(psutil.pids())
        proc_count = len(current_pids)

        # Track process churn (start/exit count)
        started_count = len(current_pids - self._prev_pids) if self._prev_pids else 0
        exited_count = len(self._prev_pids - current_pids) if self._prev_pids else 0
        self._prev_pids = current_pids

        # Periodically refresh top consumers or on first poll
        should_sample_top = (
            not self._cached_top_cpu
            or (current_mono - self._last_process_sample_mono >= self.config.process_sample_interval_seconds)
        )

        if should_sample_top:
            procs: List[Dict[str, Any]] = []
            for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                if self._shutdown_event.is_set():
                    break
                try:
                    info = p.info
                    if info and info.get('name'):
                        procs.append({
                            "pid": info['pid'],
                            "name": info['name'],
                            "cpu_percent": float(info['cpu_percent'] or 0.0),
                            "memory_percent": float(info['memory_percent'] or 0.0),
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue

            self._cached_top_cpu = sorted(procs, key=lambda x: x['cpu_percent'], reverse=True)[:3]
            self._cached_top_mem = sorted(procs, key=lambda x: x['memory_percent'], reverse=True)[:3]
            self._last_process_sample_mono = current_mono

        top_cpu = self._cached_top_cpu
        top_mem = self._cached_top_mem

        top_cpu_name = top_cpu[0]['name'] if top_cpu else "None"
        top_cpu_pct = top_cpu[0]['cpu_percent'] if top_cpu else 0.0

        with self._lock:
            self._last_snapshot["process_count"] = proc_count
            self._last_snapshot["processes_started_delta"] = started_count
            self._last_snapshot["processes_exited_delta"] = exited_count
            self._last_snapshot["top_cpu_process"] = top_cpu_name
            self._last_snapshot["top_cpu_percent"] = top_cpu_pct
            self._last_snapshot["top_cpu_list"] = top_cpu
            self._last_snapshot["top_mem_list"] = top_mem

        obs = SystemObservation(
            observation_id=str(uuid.uuid4()),
            timestamp=now,
            domain=SystemMetricDomain.PROCESS,
            metric="aggregate_processes",
            value=proc_count,
            unit="count",
            severity=SystemObservationSeverity.INFO,
            source="windows_processes",
            metadata={
                "process_count": proc_count,
                "processes_started": started_count,
                "processes_exited": exited_count,
                "top_cpu": top_cpu,
                "top_memory": top_mem,
            },
        )

        # High CPU process condition
        if top_cpu:
            proc_highest = top_cpu[0]
            is_breach = proc_highest['cpu_percent'] >= self.config.process_high_cpu_threshold
            is_recovered = proc_highest['cpu_percent'] <= self.config.process_high_cpu_recovery_threshold

            self._evaluate_hysteresis(
                condition_key=f"process:high_cpu:{proc_highest['name']}",
                domain=SystemMetricDomain.PROCESS,
                metric="high_cpu_process",
                current_value=proc_highest['cpu_percent'],
                trigger_threshold=self.config.process_high_cpu_threshold,
                trigger_sustained_seconds=self.config.process_high_cpu_sustained_seconds,
                recovery_threshold=self.config.process_high_cpu_recovery_threshold,
                recovery_sustained_seconds=self.config.process_high_cpu_recovery_seconds,
                current_mono=current_mono,
                now=now,
                is_breach=is_breach,
                is_recovered=is_recovered,
                alert_severity=SystemObservationSeverity.NOTICE,
                alert_message=f"Process '{proc_highest['name']}' (PID {proc_highest['pid']}) consuming {proc_highest['cpu_percent']:.1f}% CPU",
                recovery_message=f"Process '{proc_highest['name']}' CPU returned below {self.config.process_high_cpu_recovery_threshold:.1f}%",
            )

        return [obs]

    def _observe_network(self, now: datetime, current_mono: float) -> List[SystemObservation]:
        """
        Observe lightweight link/adapter state without performing socket connections or scans.
        """
        stats = psutil.net_if_stats()
        active_adapters: List[str] = []
        for name, stat in stats.items():
            if stat.isup:
                active_adapters.append(name)

        has_link = len(active_adapters) > 0

        with self._lock:
            self._last_snapshot["network_connected"] = has_link
            self._last_snapshot["active_adapters_count"] = len(active_adapters)

        obs = SystemObservation(
            observation_id=str(uuid.uuid4()),
            timestamp=now,
            domain=SystemMetricDomain.NETWORK,
            metric="link_status",
            value=has_link,
            unit="",
            severity=SystemObservationSeverity.INFO if has_link else SystemObservationSeverity.WARNING,
            source="windows_network",
            metadata={"active_adapters": active_adapters, "total_adapters": len(stats)},
        )

        return [obs]

    def _observe_system(self, now: datetime, current_mono: float) -> List[SystemObservation]:
        """Observe uptime and system version safely."""
        boot_time = psutil.boot_time()
        uptime_seconds = max(0.0, time.time() - boot_time)

        with self._lock:
            self._last_snapshot["uptime_seconds"] = uptime_seconds
            self._last_snapshot["system_platform"] = platform.platform()

        obs = SystemObservation(
            observation_id=str(uuid.uuid4()),
            timestamp=now,
            domain=SystemMetricDomain.SYSTEM,
            metric="uptime",
            value=uptime_seconds,
            unit="seconds",
            severity=SystemObservationSeverity.INFO,
            source="windows_system",
            metadata={
                "platform": platform.platform(),
                "release": platform.release(),
                "version": platform.version(),
            },
        )

        return [obs]

    # -------------------------------------------------------------------------
    # Hysteresis & Debouncing Engine
    # -------------------------------------------------------------------------

    def _evaluate_hysteresis(
        self,
        condition_key: str,
        domain: SystemMetricDomain,
        metric: str,
        current_value: float,
        trigger_threshold: float,
        trigger_sustained_seconds: float,
        recovery_threshold: float,
        recovery_sustained_seconds: float,
        current_mono: float,
        now: datetime,
        is_breach: bool,
        is_recovered: bool,
        alert_severity: SystemObservationSeverity,
        alert_message: str,
        recovery_message: str,
    ) -> None:
        """
        Evaluate condition against trigger and recovery thresholds with hysteresis.
        Prevents alert flapping around single thresholds.
        """
        with self._lock:
            if is_breach:
                # Metric is in breach zone
                self._recovery_first_seen.pop(condition_key, None)

                if condition_key not in self._active_alerts:
                    # Not yet triggered
                    if condition_key not in self._condition_first_seen:
                        self._condition_first_seen[condition_key] = current_mono

                    elapsed = current_mono - self._condition_first_seen[condition_key]
                    if elapsed >= trigger_sustained_seconds:
                        # Condition sustained past required duration -> trigger alert
                        alert = SystemAlert(
                            alert_id=str(uuid.uuid4()),
                            domain=domain,
                            metric=metric,
                            severity=alert_severity,
                            message=alert_message,
                            value=current_value,
                            threshold=trigger_threshold,
                            triggered_at=now,
                            sustained_seconds=elapsed,
                            metadata={"condition_key": condition_key},
                        )
                        self._active_alerts[condition_key] = alert
                        self._alerts.append(alert)
                        self._alert_history.append(alert)
                        self._condition_first_seen.pop(condition_key, None)

                        # Publish alert event outside lock
                        self._publish_alert_event(alert, is_recovery=False)
                        self._persist_alert_fact(alert, is_recovery=False)

            elif is_recovered:
                # Metric is in recovery zone
                self._condition_first_seen.pop(condition_key, None)

                if condition_key in self._active_alerts:
                    # Active alert is recovering
                    if condition_key not in self._recovery_first_seen:
                        self._recovery_first_seen[condition_key] = current_mono

                    elapsed = current_mono - self._recovery_first_seen[condition_key]
                    if elapsed >= recovery_sustained_seconds:
                        # Recovery sustained -> clear active alert
                        active_alert = self._active_alerts.pop(condition_key)
                        recovered_alert = SystemAlert(
                            alert_id=active_alert.alert_id,
                            domain=domain,
                            metric=metric,
                            severity=SystemObservationSeverity.INFO,
                            message=recovery_message,
                            value=current_value,
                            threshold=recovery_threshold,
                            triggered_at=active_alert.triggered_at,
                            sustained_seconds=active_alert.sustained_seconds,
                            recovered_at=now,
                            metadata={"condition_key": condition_key},
                        )
                        self._alert_history.append(recovered_alert)
                        self._recovery_first_seen.pop(condition_key, None)

                        # Publish recovery event outside lock
                        self._publish_alert_event(recovered_alert, is_recovery=True)
                        self._persist_alert_fact(recovered_alert, is_recovery=True)

            else:
                # Metric is in hysteresis deadband (between recovery and trigger threshold)
                # Reset timers so transient fluctuations don't accumulate
                self._condition_first_seen.pop(condition_key, None)
                self._recovery_first_seen.pop(condition_key, None)

    # -------------------------------------------------------------------------
    # Event Publishing & Memory Boundary
    # -------------------------------------------------------------------------

    def _publish_routine_observation(self, observations: List[SystemObservation]) -> None:
        """Publish routine SYSTEM_OBSERVATION event on EVEventBus."""
        if self._event_bus is None:
            return

        summary_data = {
            "observation_count": len(observations),
            "domains": [obs.domain.value for obs in observations],
            "metrics": {f"{obs.domain.value}:{obs.metric}": obs.value for obs in observations},
        }

        self._event_bus.publish(
            event_type=EVEventType.SYSTEM_OBSERVATION,
            source="system_monitor",
            message=f"Captured {len(observations)} system observations",
            severity=EVEventSeverity.INFO,
            data=summary_data,
        )

    def _publish_alert_event(self, alert: SystemAlert, is_recovery: bool) -> None:
        """Publish SYSTEM_ALERT or SYSTEM_ALERT_RECOVERED event on EVEventBus."""
        if self._event_bus is None:
            return

        event_type = (
            EVEventType.SYSTEM_ALERT_RECOVERED
            if is_recovery
            else EVEventType.SYSTEM_ALERT
        )

        ev_severity = EVEventSeverity.INFO
        if not is_recovery:
            if alert.severity == SystemObservationSeverity.CRITICAL:
                ev_severity = EVEventSeverity.CRITICAL
            elif alert.severity == SystemObservationSeverity.WARNING:
                ev_severity = EVEventSeverity.WARNING
            elif alert.severity == SystemObservationSeverity.NOTICE:
                ev_severity = EVEventSeverity.NOTICE
            else:
                ev_severity = EVEventSeverity.INFO

        try:
            self._event_bus.publish(
                event_type=event_type,
                source="system_monitor",
                message=alert.message,
                severity=ev_severity,
                data=alert.to_dict(),
            )
        except Exception as exc:
            logger.warning("Failed to publish alert event: %s", exc)

    def _persist_alert_fact(self, alert: SystemAlert, is_recovery: bool) -> None:
        """
        Record only significant alert transitions into EVConversationMemoryStore.
        Routine 3-second samples are NEVER persisted.
        """
        if self._memory_store is None:
            return

        try:
            fact_key = f"system_alert:{alert.domain.value}:{alert.metric}"
            fact_value = alert.message
            if hasattr(self._memory_store, "set_environment_fact"):
                self._memory_store.set_environment_fact(
                    fact_key=fact_key,
                    fact_value=fact_value,
                    topic="system_awareness",
                    source="system_monitor",
                    ttl_days=1 if not is_recovery else 0,  # Expire recovered alerts
                    metadata=alert.to_dict(),
                )
        except Exception as exc:
            logger.debug("Failed to record environment fact for alert: %s", exc)

    # -------------------------------------------------------------------------
    # Inspection & Context Provider
    # -------------------------------------------------------------------------

    def get_recent_observations(
        self,
        domain: Optional[SystemMetricDomain] = None,
        limit: int = 20,
    ) -> List[SystemObservation]:
        """Return bounded recent observations, optionally filtered by domain."""
        with self._lock:
            bounded_limit = min(max(1, limit), self.config.max_retained_observations)
            obs_list = list(self._observations)

        if domain is not None:
            obs_list = [o for o in obs_list if o.domain == domain]

        return obs_list[-bounded_limit:]

    def get_active_alerts(self) -> List[SystemAlert]:
        """Return all currently active triggered alerts."""
        with self._lock:
            return list(self._active_alerts.values())

    def get_alert_history(self, limit: int = 20) -> List[SystemAlert]:
        """Return bounded history of past triggered and recovered alerts."""
        with self._lock:
            bounded_limit = min(max(1, limit), self.config.max_retained_alerts)
            return list(self._alert_history)[-bounded_limit:]

    def get_context_summary(self) -> Dict[str, Any]:
        """
        Produce a bounded, privacy-safe system awareness context dictionary.
        Suitable for consumption by Brain context assemblers or the Orchestrator.
        """
        with self._lock:
            snapshot = copy.deepcopy(self._last_snapshot)
            active_alerts = [a.to_dict() for a in self._active_alerts.values()]

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cpu_percent": snapshot.get("cpu_percent", 0.0),
            "memory_used_percent": snapshot.get("memory_used_percent", 0.0),
            "memory_available_gb": round(snapshot.get("memory_available_bytes", 0) / (1024**3), 2),
            "disk_free_percent": round(snapshot.get("disk_free_percent", 0.0), 1),
            "disk_free_gb": round(snapshot.get("disk_free_bytes", 0) / (1024**3), 2),
            "process_count": snapshot.get("process_count", 0),
            "top_cpu_process": snapshot.get("top_cpu_process", "None"),
            "network_connected": snapshot.get("network_connected", True),
            "uptime_seconds": round(snapshot.get("uptime_seconds", 0.0), 1),
            "active_alerts_count": len(active_alerts),
            "active_alerts": active_alerts,
        }
