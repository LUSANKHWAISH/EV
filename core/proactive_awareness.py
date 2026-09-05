"""
Proactive Awareness Intelligence & Event Correlation Engine for E.V. (Task 014F-18).

Consumes system telemetry and alerts from EVSystemMonitor, applies conservative
event correlation and deterministic deduplication, evaluates contextual significance
according to experience modes and user interaction states, enforces speech cooldowns,
exposes bounded untrusted context to the Brain, and publishes structured AwarenessEvent
records to the HUD and EVTTSManager.

CRITICAL ARCHITECTURAL RULES:
1. "E.V. may NOTICE. E.V. may REASON. E.V. may INFORM. E.V. may SUGGEST. E.V. must NOT independently ACT."
2. ZERO autonomous execution, ZERO automatic repair, ZERO subprocess calls, ZERO PowerShell,
   ZERO process killing, ZERO automatic file mutation, ZERO approval bypass, ZERO GOD MODE.
3. Canonical authority remains unchanged:
   User / Voice / GUI -> EVOrchestrator -> risk/approval -> transaction -> execution -> verification.
4. Awareness data is untrusted context with zero execution privileges.
5. Audio output is routed exclusively through EVTTSManager (never direct SAPI/PowerShell).
"""

from __future__ import annotations

import collections
import copy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging
import threading
import time
from typing import Any, Callable, Deque, Dict, List, Optional, Set, Tuple, Union
import uuid

from core.events import EVEvent, EVEventBus
from core.models import EVEventSeverity, EVEventType

logger = logging.getLogger("ev.proactive_awareness")


class AwarenessState(str, Enum):
    """Deterministic lifecycle state of an awareness condition."""
    DETECTED = "DETECTED"
    ACTIVE = "ACTIVE"
    UPDATED = "UPDATED"
    RECOVERED = "RECOVERED"
    DISMISSED = "DISMISSED"


class AwarenessCategory(str, Enum):
    """Broad category of the observed condition."""
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    PROCESS = "process"
    NETWORK = "network"
    SYSTEM = "system"


class AwarenessSeverity(str, Enum):
    """Severity classification for awareness items (CRITICAL > WARNING > NOTICE > INFO)."""
    INFO = "INFO"
    NOTICE = "NOTICE"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"

    @property
    def rank(self) -> int:
        """Numeric rank for priority comparison."""
        ranks = {
            AwarenessSeverity.INFO: 1,
            AwarenessSeverity.NOTICE: 2,
            AwarenessSeverity.WARNING: 3,
            AwarenessSeverity.CRITICAL: 4,
        }
        return ranks.get(self, 0)

    def __gt__(self, other: Any) -> bool:
        if isinstance(other, AwarenessSeverity):
            return self.rank > other.rank
        return NotImplemented

    def __ge__(self, other: Any) -> bool:
        if isinstance(other, AwarenessSeverity):
            return self.rank >= other.rank
        return NotImplemented

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, AwarenessSeverity):
            return self.rank < other.rank
        return NotImplemented

    def __le__(self, other: Any) -> bool:
        if isinstance(other, AwarenessSeverity):
            return self.rank <= other.rank
        return NotImplemented


class NotificationPolicy(str, Enum):
    """Presentation and audio notification policy determined by the significance engine."""
    SILENT = "SILENT"
    HUD = "HUD"
    HUD_AND_NOTIFICATION = "HUD_AND_NOTIFICATION"
    SPEAK = "SPEAK"


@dataclass(frozen=True)
class AwarenessEvent:
    """
    Immutable structured record representing meaningful user-facing awareness.
    Untrusted presentation-level data with ZERO execution authority.
    """
    awareness_id: str
    timestamp: datetime
    condition_key: str
    category: AwarenessCategory
    severity: AwarenessSeverity
    title: str
    message: str
    source: str = "proactive_awareness"
    evidence: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    state: AwarenessState = AwarenessState.ACTIVE
    first_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    occurrence_count: int = 1
    recurrence_count: int = 0
    notification_policy: NotificationPolicy = NotificationPolicy.HUD
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Return JSON-serializable dictionary representation."""
        return {
            "awareness_id": self.awareness_id,
            "timestamp": self.timestamp.isoformat(),
            "condition_key": self.condition_key,
            "category": self.category.value,
            "severity": self.severity.value,
            "title": self.title,
            "message": self.message,
            "source": self.source,
            "evidence": copy.deepcopy(self.evidence),
            "confidence": self.confidence,
            "state": self.state.value,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "occurrence_count": self.occurrence_count,
            "recurrence_count": self.recurrence_count,
            "notification_policy": self.notification_policy.value,
            "metadata": copy.deepcopy(self.metadata),
        }


@dataclass
class ProactiveAwarenessConfig:
    """Configuration, limits, and tuning parameters for EVProactiveAwarenessEngine."""
    max_active_awareness: int = 25
    max_resolved_history: int = 50
    speech_cooldown_seconds: float = 120.0
    recurrence_window_seconds: float = 900.0  # 15 minutes
    min_recurrence_for_memory: int = 3
    cpu_correlation_process_threshold: float = 25.0
    memory_correlation_process_threshold: float = 15.0


class EVProactiveAwarenessEngine:
    """
    Intelligence and event correlation engine for proactive system awareness.
    
    Transforms raw observations and alerts into deduplicated, correlated,
    prioritized awareness events with contextual significance.
    """

    def __init__(
        self,
        config: Optional[ProactiveAwarenessConfig] = None,
        event_bus: Optional[EVEventBus] = None,
        system_monitor: Optional[Any] = None,
        experience_manager: Optional[Any] = None,
        tts_manager: Optional[Any] = None,
        memory_store: Optional[Any] = None,
    ) -> None:
        self.config: ProactiveAwarenessConfig = config or ProactiveAwarenessConfig()
        self._event_bus: Optional[EVEventBus] = event_bus
        self._system_monitor: Optional[Any] = system_monitor
        self._experience_manager: Optional[Any] = experience_manager
        self._tts_manager: Optional[Any] = tts_manager
        self._memory_store: Optional[Any] = memory_store

        self._lock = threading.RLock()
        self._is_running = False
        self._subscription_tokens: List[str] = []

        # Bounded in-memory active awareness and history
        self._active_awareness: Dict[str, AwarenessEvent] = {}
        self._resolved_history: Deque[AwarenessEvent] = collections.deque(
            maxlen=self.config.max_resolved_history
        )

        # Telemetry caches for conservative correlation
        self._cached_top_cpu: Optional[Dict[str, Any]] = None
        self._cached_top_mem: Optional[Dict[str, Any]] = None
        self._last_observations_by_domain: Dict[str, Any] = {}

        # Cooldown and recurrence tracking
        # condition_key -> monotonic timestamp of last spoken notification
        self._last_speech_time: Dict[str, float] = {}
        # condition_key -> list of monotonic timestamps of past occurrences
        self._condition_recurrence_history: Dict[str, List[float]] = collections.defaultdict(list)

        # Contextual state tracking
        self._current_experience_mode: str = "STANDARD"
        self._current_voice_state: str = "IDLE"
        self._current_operational_state: str = "IDLE"

    # -------------------------------------------------------------------------
    # Lifecycle Management
    # -------------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        """True if the awareness engine is actively running and subscribed."""
        with self._lock:
            return self._is_running

    def start(self) -> None:
        """
        Start the proactive awareness engine and attach event bus subscriptions.
        Idempotent: calling start() when already running is a safe no-op.
        """
        with self._lock:
            if self._is_running:
                logger.debug("EVProactiveAwarenessEngine is already running.")
                return

            self._is_running = True

            # Query current experience mode if manager is attached
            if self._experience_manager is not None:
                try:
                    mode = getattr(self._experience_manager, "current_mode", None)
                    if mode is not None:
                        self._current_experience_mode = mode.value if hasattr(mode, "value") else str(mode)
                except Exception:
                    pass

            # Setup event bus subscriptions
            if self._event_bus is not None:
                self._setup_event_subscriptions()

            logger.info("EVProactiveAwarenessEngine started successfully.")

    def stop(self) -> None:
        """
        Stop the awareness engine and remove all event subscriptions cleanly.
        Idempotent: calling stop() when already stopped is a safe no-op.
        """
        with self._lock:
            if not self._is_running:
                return

            self._is_running = False

            # Unsubscribe from event bus
            if self._event_bus is not None:
                for token in self._subscription_tokens:
                    try:
                        self._event_bus.unsubscribe(token)
                    except Exception as exc:
                        logger.debug("Error unsubscribing token %s: %s", token, exc)
                self._subscription_tokens.clear()

            logger.info("EVProactiveAwarenessEngine stopped cleanly.")

    def _setup_event_subscriptions(self) -> None:
        """Subscribe to relevant EVEventBus topics."""
        if self._event_bus is None:
            return

        events_to_subscribe = [
            EVEventType.SYSTEM_ALERT,
            EVEventType.SYSTEM_ALERT_RECOVERED,
            EVEventType.SYSTEM_OBSERVATION,
            EVEventType.EXPERIENCE_MODE_CHANGED,
            EVEventType.VOICE_STATE_CHANGED,
            EVEventType.STATE_CHANGED,
        ]

        token = self._event_bus.subscribe(
            callback=self._handle_bus_event,
            event_types=events_to_subscribe,
        )
        self._subscription_tokens.append(token)

    def _handle_bus_event(self, event: EVEvent) -> None:
        """Thread-safe event bus listener dispatching incoming events."""
        try:
            self.process_event(event)
        except Exception as exc:
            logger.warning("Error processing bus event in awareness engine: %s", exc)

    # -------------------------------------------------------------------------
    # Ingestion & Dispatch
    # -------------------------------------------------------------------------

    def process_event(self, event: EVEvent) -> Optional[AwarenessEvent]:
        """
        Ingest an EVEvent and route to the appropriate awareness handler.
        Returns the generated AwarenessEvent, if any.
        """
        if event.event_type == EVEventType.EXPERIENCE_MODE_CHANGED:
            if event.data and "current_mode" in event.data:
                with self._lock:
                    self._current_experience_mode = str(event.data["current_mode"])
            return None

        elif event.event_type == EVEventType.VOICE_STATE_CHANGED:
            if event.data and "voice_state" in event.data:
                with self._lock:
                    self._current_voice_state = str(event.data["voice_state"])
            return None

        elif event.event_type == EVEventType.STATE_CHANGED:
            if event.state is not None:
                with self._lock:
                    self._current_operational_state = (
                        event.state.value if hasattr(event.state, "value") else str(event.state)
                    )
            return None

        elif event.event_type == EVEventType.SYSTEM_OBSERVATION:
            if event.data and "metrics" in event.data:
                # Update telemetry cache for correlation
                metrics = event.data["metrics"]
                with self._lock:
                    for key, val in metrics.items():
                        self._last_observations_by_domain[key] = val
            return None

        elif event.event_type == EVEventType.SYSTEM_ALERT:
            if event.data:
                return self._process_alert_dict(event.data, is_recovery=False)
            return None

        elif event.event_type == EVEventType.SYSTEM_ALERT_RECOVERED:
            if event.data:
                return self._process_alert_dict(event.data, is_recovery=True)
            return None

        return None

    def process_alert(self, alert: Any) -> Optional[AwarenessEvent]:
        """
        Direct programmatic entry point for SystemAlert objects.
        Allows deterministic, isolated unit testing without requiring background threads.
        """
        alert_dict = alert.to_dict() if hasattr(alert, "to_dict") else alert
        return self._process_alert_dict(alert_dict, is_recovery=False)

    def process_recovery(self, alert: Any) -> Optional[AwarenessEvent]:
        """
        Direct programmatic entry point for recovered SystemAlert objects.
        """
        alert_dict = alert.to_dict() if hasattr(alert, "to_dict") else alert
        return self._process_alert_dict(alert_dict, is_recovery=True)

    def update_process_cache(
        self,
        top_cpu: Optional[Dict[str, Any]] = None,
        top_mem: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Update cached top process information for correlation."""
        with self._lock:
            if top_cpu is not None:
                self._cached_top_cpu = copy.deepcopy(top_cpu)
            if top_mem is not None:
                self._cached_top_mem = copy.deepcopy(top_mem)

    # -------------------------------------------------------------------------
    # Core Correlation, Deduplication, & Significance Logic
    # -------------------------------------------------------------------------

    def _process_alert_dict(self, alert_data: Dict[str, Any], is_recovery: bool) -> Optional[AwarenessEvent]:
        """Core processing pipeline for raw alert dictionaries."""
        now = datetime.now(timezone.utc)
        current_mono = time.monotonic()

        domain_str = str(alert_data.get("domain", "system")).lower()
        metric_str = str(alert_data.get("metric", "metric"))
        metadata = alert_data.get("metadata", {})
        condition_key = str(metadata.get("condition_key", f"{domain_str}:{metric_str}"))

        with self._lock:
            if is_recovery:
                return self._handle_recovery(
                    condition_key=condition_key,
                    domain_str=domain_str,
                    metric_str=metric_str,
                    alert_data=alert_data,
                    now=now,
                    current_mono=current_mono,
                )
            else:
                return self._handle_alert(
                    condition_key=condition_key,
                    domain_str=domain_str,
                    metric_str=metric_str,
                    alert_data=alert_data,
                    now=now,
                    current_mono=current_mono,
                )

    def _handle_alert(
        self,
        condition_key: str,
        domain_str: str,
        metric_str: str,
        alert_data: Dict[str, Any],
        now: datetime,
        current_mono: float,
    ) -> Optional[AwarenessEvent]:
        """Handle a triggered alert with correlation, deduplication, and policy evaluation."""
        # 1. Map category & determine baseline severity
        category = self._map_category(domain_str)
        raw_severity = str(alert_data.get("severity", "WARNING")).upper()
        severity = self._map_severity(raw_severity)

        # 2. Correlate with other domains
        title, message, evidence, correlated_severity = self._correlate_condition(
            category=category,
            metric=metric_str,
            alert_data=alert_data,
            base_severity=severity,
        )
        final_severity = correlated_severity

        # 3. Check recurrence
        recurrence_count = self._calculate_recurrence(condition_key, current_mono)
        if recurrence_count >= 2:
            evidence["recurrence_count"] = recurrence_count
            message = f"{message} (Condition observed {recurrence_count} times recently.)"

        # 4. Deduplicate against active awareness
        existing_event = self._active_awareness.get(condition_key)
        if existing_event is not None:
            # Condition is already active — update occurrence count and last seen
            new_occurrence_count = existing_event.occurrence_count + 1
            first_seen = existing_event.first_seen

            # Check if severity escalated
            is_escalation = final_severity > existing_event.severity

            # Determine policy
            if is_escalation:
                notification_policy = self._determine_notification_policy(
                    severity=final_severity,
                    condition_key=condition_key,
                    current_mono=current_mono,
                    is_escalation=True,
                )
                state = AwarenessState.UPDATED
            else:
                # Repeated notification is suppressed to prevent spam
                notification_policy = NotificationPolicy.SILENT
                state = AwarenessState.UPDATED
                final_severity = existing_event.severity

            updated_event = AwarenessEvent(
                awareness_id=existing_event.awareness_id,
                timestamp=now,
                condition_key=condition_key,
                category=category,
                severity=final_severity,
                title=title,
                message=message,
                source="proactive_awareness",
                evidence=evidence,
                confidence=1.0,
                state=state,
                first_seen=first_seen,
                last_seen=now,
                occurrence_count=new_occurrence_count,
                recurrence_count=recurrence_count,
                notification_policy=notification_policy,
                metadata=alert_data.get("metadata", {}),
            )
            self._active_awareness[condition_key] = updated_event

            # Dispatch notification if policy allows
            self._dispatch_notification(updated_event, current_mono)
            return updated_event

        else:
            # New active awareness condition
            notification_policy = self._determine_notification_policy(
                severity=final_severity,
                condition_key=condition_key,
                current_mono=current_mono,
                is_escalation=False,
            )

            new_event = AwarenessEvent(
                awareness_id=str(uuid.uuid4()),
                timestamp=now,
                condition_key=condition_key,
                category=category,
                severity=final_severity,
                title=title,
                message=message,
                source="proactive_awareness",
                evidence=evidence,
                confidence=1.0,
                state=AwarenessState.ACTIVE,
                first_seen=now,
                last_seen=now,
                occurrence_count=1,
                recurrence_count=recurrence_count,
                notification_policy=notification_policy,
                metadata=alert_data.get("metadata", {}),
            )

            # Enforce bounded capacity in active awareness
            if len(self._active_awareness) >= self.config.max_active_awareness:
                oldest_key = next(iter(self._active_awareness))
                evicted = self._active_awareness.pop(oldest_key)
                self._resolved_history.append(evicted)

            self._active_awareness[condition_key] = new_event

            # Persist long-lived environment fact if recurrence threshold met
            if recurrence_count >= self.config.min_recurrence_for_memory:
                self._persist_recurrence_fact(new_event)

            # Dispatch notification
            self._dispatch_notification(new_event, current_mono)
            return new_event

    def _handle_recovery(
        self,
        condition_key: str,
        domain_str: str,
        metric_str: str,
        alert_data: Dict[str, Any],
        now: datetime,
        current_mono: float,
    ) -> Optional[AwarenessEvent]:
        """Handle a condition recovery, clearing the active condition and emitting recovery."""
        existing_event = self._active_awareness.pop(condition_key, None)
        category = self._map_category(domain_str)

        recovery_msg = str(alert_data.get("message", "Condition returned to normal."))
        title = f"{existing_event.title if existing_event else category.value.upper()} Recovered"

        recovered_event = AwarenessEvent(
            awareness_id=existing_event.awareness_id if existing_event else str(uuid.uuid4()),
            timestamp=now,
            condition_key=condition_key,
            category=category,
            severity=AwarenessSeverity.INFO,
            title=title,
            message=recovery_msg,
            source="proactive_awareness",
            evidence={"recovered_at": now.isoformat()},
            confidence=1.0,
            state=AwarenessState.RECOVERED,
            first_seen=existing_event.first_seen if existing_event else now,
            last_seen=now,
            occurrence_count=existing_event.occurrence_count if existing_event else 1,
            recurrence_count=existing_event.recurrence_count if existing_event else 0,
            notification_policy=NotificationPolicy.HUD,
            metadata=alert_data.get("metadata", {}),
        )

        # Store in resolved history
        self._resolved_history.append(recovered_event)

        # Reset speech cooldown for this condition so a future new occurrence can notify
        self._last_speech_time.pop(condition_key, None)

        # Publish recovery event to event bus
        if self._event_bus is not None:
            try:
                self._event_bus.publish(
                    event_type=EVEventType.AWARENESS_RESOLVED,
                    source="proactive_awareness",
                    message=recovered_event.message,
                    severity=EVEventSeverity.INFO,
                    data=recovered_event.to_dict(),
                )
            except Exception as exc:
                logger.debug("Failed to publish awareness recovery event: %s", exc)

        return recovered_event

    # -------------------------------------------------------------------------
    # Correlation Engine
    # -------------------------------------------------------------------------

    def _correlate_condition(
        self,
        category: AwarenessCategory,
        metric: str,
        alert_data: Dict[str, Any],
        base_severity: AwarenessSeverity,
    ) -> Tuple[str, str, Dict[str, Any], AwarenessSeverity]:
        """
        Conservative correlation synthesizing multi-domain evidence.
        Uses non-causal evidence phrasing: 'appears associated with', 'largest observed consumer'.
        """
        evidence = copy.deepcopy(alert_data)
        raw_msg = str(alert_data.get("message", ""))
        value = alert_data.get("value", 0.0)

        # 1. CPU Correlation
        if category == AwarenessCategory.CPU or "cpu" in metric:
            top_proc = self._get_top_cpu_process()
            if top_proc and top_proc.get("cpu_percent", 0.0) >= self.config.cpu_correlation_process_threshold:
                proc_name = top_proc.get("name", "Unknown")
                proc_pid = top_proc.get("pid", 0)
                proc_cpu = top_proc.get("cpu_percent", 0.0)
                evidence["correlated_top_process"] = top_proc
                title = "Elevated CPU Utilization"
                message = (
                    f"CPU usage is elevated ({value:.1f}%); process '{proc_name}' "
                    f"(PID {proc_pid}) is currently the largest observed consumer ({proc_cpu:.1f}%)."
                )
                return title, message, evidence, base_severity
            else:
                title = "Elevated CPU Utilization"
                message = f"CPU usage has remained unusually high ({value:.1f}%)."
                return title, message, evidence, base_severity

        # 2. Memory Correlation
        elif category == AwarenessCategory.MEMORY or "memory" in metric:
            top_mem = self._get_top_mem_process()
            if top_mem and top_mem.get("memory_percent", 0.0) >= self.config.memory_correlation_process_threshold:
                proc_name = top_mem.get("name", "Unknown")
                proc_pid = top_mem.get("pid", 0)
                proc_mem = top_mem.get("memory_percent", 0.0)
                evidence["correlated_top_process"] = top_mem
                title = "System Memory Pressure"
                message = (
                    f"System memory usage is elevated ({value:.1f}% used); process '{proc_name}' "
                    f"(PID {proc_pid}) is currently the largest observed memory consumer ({proc_mem:.1f}%)."
                )
                return title, message, evidence, base_severity
            else:
                title = "System Memory Pressure"
                message = f"System memory usage is elevated ({value:.1f}% used)."
                return title, message, evidence, base_severity

        # 3. Disk Space Escalation
        elif category == AwarenessCategory.DISK or "disk" in metric:
            free_pct = float(value)
            if free_pct <= 5.0:
                title = "Critical Disk Space Warning"
                message = f"C: drive space is critically low ({free_pct:.1f}% free, below 5.0% threshold)."
                return title, message, evidence, AwarenessSeverity.CRITICAL
            else:
                title = "Low Disk Space"
                message = f"C: drive space has fallen below warning threshold ({free_pct:.1f}% free)."
                return title, message, evidence, AwarenessSeverity.WARNING

        # 4. Network Link Status
        elif category == AwarenessCategory.NETWORK or "network" in metric or "link" in metric:
            title = "Network Connectivity Lost"
            message = "Network link status is down; no active network adapters detected."
            return title, message, evidence, AwarenessSeverity.WARNING

        # 5. Process Specific
        elif category == AwarenessCategory.PROCESS or "process" in metric:
            title = "High Process Resource Usage"
            return title, raw_msg or "Process resource utilization elevated.", evidence, base_severity

        # Fallback
        title = f"System {category.value.capitalize()} Alert"
        return title, raw_msg or f"{category.value} condition threshold breach.", evidence, base_severity

    def _get_top_cpu_process(self) -> Optional[Dict[str, Any]]:
        """Retrieve top CPU process from cache or system monitor."""
        if self._cached_top_cpu is not None:
            return self._cached_top_cpu
        if self._system_monitor is not None:
            try:
                summary = self._system_monitor.get_context_summary()
                top_name = summary.get("top_cpu_process")
                if top_name and top_name != "None":
                    return {"name": top_name, "pid": 0, "cpu_percent": summary.get("cpu_percent", 0.0)}
            except Exception:
                pass
        return None

    def _get_top_mem_process(self) -> Optional[Dict[str, Any]]:
        """Retrieve top memory process from cache."""
        return self._cached_top_mem

    # -------------------------------------------------------------------------
    # Recurrence & Significance Engine
    # -------------------------------------------------------------------------

    def _calculate_recurrence(self, condition_key: str, current_mono: float) -> int:
        """Count occurrences of this condition within the configured sliding time window."""
        window_start = current_mono - self.config.recurrence_window_seconds
        history = self._condition_recurrence_history[condition_key]
        # Prune old occurrences and record current occurrence
        pruned = [t for t in history if t >= window_start]
        pruned.append(current_mono)
        self._condition_recurrence_history[condition_key] = pruned
        return len(pruned)

    def _determine_notification_policy(
        self,
        severity: AwarenessSeverity,
        condition_key: str,
        current_mono: float,
        is_escalation: bool,
    ) -> NotificationPolicy:
        """
        Deterministic significance rules engine mapping severity, cooldown,
        experience mode, and user interaction state to a notification policy.
        """
        # 1. Base policy from severity
        if severity == AwarenessSeverity.CRITICAL:
            candidate_policy = NotificationPolicy.SPEAK
        elif severity == AwarenessSeverity.WARNING:
            candidate_policy = NotificationPolicy.HUD
        elif severity == AwarenessSeverity.NOTICE:
            candidate_policy = NotificationPolicy.HUD
        else:
            candidate_policy = NotificationPolicy.SILENT

        # 2. Check Cooldown for speech
        if candidate_policy == NotificationPolicy.SPEAK:
            last_speech = self._last_speech_time.get(condition_key, 0.0)
            elapsed_since_speech = current_mono - last_speech
            if elapsed_since_speech < self.config.speech_cooldown_seconds and not is_escalation:
                # Cooldown active and not an escalation: downgrade to HUD_AND_NOTIFICATION
                candidate_policy = NotificationPolicy.HUD_AND_NOTIFICATION

        # 3. Experience Mode Policy Influences
        mode = self._current_experience_mode.upper()
        if mode == "WORK":
            # Minimize interruptions: downgrade speech to HUD unless critical
            if candidate_policy == NotificationPolicy.SPEAK and severity < AwarenessSeverity.CRITICAL:
                candidate_policy = NotificationPolicy.HUD_AND_NOTIFICATION
        elif mode == "MUSIC":
            # Strongly suppress speech interruptions
            if candidate_policy == NotificationPolicy.SPEAK and severity < AwarenessSeverity.CRITICAL:
                candidate_policy = NotificationPolicy.HUD
        elif mode == "SLEEP":
            # Suppress non-critical notifications
            if severity < AwarenessSeverity.CRITICAL:
                candidate_policy = NotificationPolicy.SILENT
            else:
                candidate_policy = NotificationPolicy.HUD
        elif mode == "APPROVAL":
            # User is in active approval decision: avoid speech interruptions
            if candidate_policy == NotificationPolicy.SPEAK and severity < AwarenessSeverity.CRITICAL:
                candidate_policy = NotificationPolicy.HUD_AND_NOTIFICATION

        # 4. Active User Voice / Operational Interaction Check
        # If user is speaking, listening, transcribing, or awaiting approval, do not interrupt with routine speech
        if candidate_policy == NotificationPolicy.SPEAK and severity < AwarenessSeverity.CRITICAL:
            if self._current_voice_state in ("LISTENING", "TRANSCRIBING", "SPEAKING") or \
               self._current_operational_state in ("AWAITING_APPROVAL", "EXECUTING"):
                candidate_policy = NotificationPolicy.HUD_AND_NOTIFICATION

        return candidate_policy

    def _dispatch_notification(self, event: AwarenessEvent, current_mono: float) -> None:
        """Route notification to HUD (via EventBus) and audio (via EVTTSManager)."""
        # 1. Publish AwarenessEvent on EVEventBus for HUD presentation
        if self._event_bus is not None and event.notification_policy != NotificationPolicy.SILENT:
            ev_severity = self._to_bus_severity(event.severity)
            try:
                self._event_bus.publish(
                    event_type=EVEventType.AWARENESS_EVENT,
                    source="proactive_awareness",
                    message=f"{event.title}: {event.message}",
                    severity=ev_severity,
                    data=event.to_dict(),
                )
            except Exception as exc:
                logger.debug("Failed to publish awareness event: %s", exc)

        # 2. Audio speech notification through EVTTSManager
        if event.notification_policy == NotificationPolicy.SPEAK and self._tts_manager is not None:
            try:
                if not getattr(self._tts_manager, "is_silent", False):
                    # Formulate concise, user-friendly spoken text
                    spoken_text = f"Notice: {event.title}. {event.message}"
                    # Map priority: CRITICAL if critical, else SYSTEM
                    audio_priority = 0 if event.severity == AwarenessSeverity.CRITICAL else 3
                    self._tts_manager.speak(
                        text=spoken_text,
                        priority=audio_priority,
                    )
                    self._last_speech_time[event.condition_key] = current_mono
            except Exception as exc:
                logger.warning("Failed to route awareness speech to TTSManager: %s", exc)

    def _persist_recurrence_fact(self, event: AwarenessEvent) -> None:
        """Record recurring problem patterns into conversation memory store."""
        if self._memory_store is None:
            return
        try:
            fact_key = f"recurring_issue:{event.category.value}:{event.condition_key}"
            fact_val = f"Repeated {event.title}: {event.message}"
            if hasattr(self._memory_store, "set_environment_fact"):
                self._memory_store.set_environment_fact(
                    fact_key=fact_key,
                    fact_value=fact_val,
                    topic="system_awareness",
                    source="proactive_awareness",
                    ttl_days=7,
                    metadata=event.to_dict(),
                )
        except Exception as exc:
            logger.debug("Failed to persist recurrence memory fact: %s", exc)

    # -------------------------------------------------------------------------
    # Context Providers for Brain and GUI
    # -------------------------------------------------------------------------

    def get_active_awareness(self) -> List[AwarenessEvent]:
        """Return all currently active awareness items."""
        with self._lock:
            return list(self._active_awareness.values())

    def get_recent_awareness(self, limit: int = 20) -> List[AwarenessEvent]:
        """Return bounded recent resolved awareness history."""
        with self._lock:
            bounded_limit = min(max(1, limit), self.config.max_resolved_history)
            return list(self._resolved_history)[-bounded_limit:]

    def get_context_summary(self) -> Dict[str, Any]:
        """
        Produce a bounded, privacy-safe awareness context dictionary.
        Strictly untrusted context data with ZERO execution authority.
        """
        with self._lock:
            active_items = [e.to_dict() for e in self._active_awareness.values()]
            resolved_items = [e.to_dict() for e in list(self._resolved_history)[-5:]]

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "active_count": len(active_items),
            "active_awareness": active_items,
            "recent_resolved": resolved_items,
            "experience_mode": self._current_experience_mode,
        }

    def get_active_awareness_for_brain(self) -> List[Dict[str, Any]]:
        """
        Return bounded, sanitized active awareness records for BrainContext.
        Untrusted context data for advisory intent-interpretation only.
        """
        with self._lock:
            items = []
            for ev in list(self._active_awareness.values())[:self.config.max_active_awareness]:
                items.append({
                    "category": ev.category.value,
                    "severity": ev.severity.value,
                    "title": ev.title,
                    "summary": ev.message,
                    "occurrence_count": ev.occurrence_count,
                    "recurrence_count": ev.recurrence_count,
                })
            return items

    # -------------------------------------------------------------------------
    # Enum & Type Helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _map_category(domain_str: str) -> AwarenessCategory:
        mapping = {
            "cpu": AwarenessCategory.CPU,
            "memory": AwarenessCategory.MEMORY,
            "disk": AwarenessCategory.DISK,
            "process": AwarenessCategory.PROCESS,
            "processes": AwarenessCategory.PROCESS,
            "network": AwarenessCategory.NETWORK,
            "system": AwarenessCategory.SYSTEM,
        }
        return mapping.get(domain_str.lower(), AwarenessCategory.SYSTEM)

    @staticmethod
    def _map_severity(sev_str: str) -> AwarenessSeverity:
        mapping = {
            "CRITICAL": AwarenessSeverity.CRITICAL,
            "WARNING": AwarenessSeverity.WARNING,
            "NOTICE": AwarenessSeverity.NOTICE,
            "INFO": AwarenessSeverity.INFO,
        }
        return mapping.get(sev_str.upper(), AwarenessSeverity.WARNING)

    @staticmethod
    def _to_bus_severity(severity: AwarenessSeverity) -> EVEventSeverity:
        mapping = {
            AwarenessSeverity.CRITICAL: EVEventSeverity.CRITICAL,
            AwarenessSeverity.WARNING: EVEventSeverity.WARNING,
            AwarenessSeverity.NOTICE: EVEventSeverity.NOTICE,
            AwarenessSeverity.INFO: EVEventSeverity.INFO,
        }
        return mapping.get(severity, EVEventSeverity.INFO)
