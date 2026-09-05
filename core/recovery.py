"""
Contextual Action Planning & Recovery Intelligence Subsystem for E.V. (Task 017).

This module provides deterministic diagnosis of system conditions and execution/verification
failures, evidence correlation with strict epistemic segregation (Fact vs. Inference vs. Speculation),
root-cause hypothesis evaluation, safe-first recovery option generation, and canonical
Plan generation.

CANONICAL ARCHITECTURAL RULES:
1. "E.V. must ONLY PROPOSE recovery actions. It must NOT autonomously execute recovery actions."
2. ZERO autonomous execution, ZERO automatic repair, ZERO subprocess calls, ZERO PowerShell,
   ZERO process killing, ZERO automatic file mutation, ZERO approval bypass, ZERO GOD MODE.
3. Canonical authority remains unchanged:
   Observation / Failure -> Diagnosis -> Recovery Proposal -> Structured Plan ->
   PlanValidator -> EVRiskEngine -> Approval -> CompoundTransaction -> EVAgent -> Verification.
4. Epistemic Segregation:
   FACT: Authoritative measurement, alert, or verified system state.
   INFERENCE: Deterministic deduction or rule-based derivation from facts.
   SPECULATION: Untrusted Brain claim or unverified heuristic. Hypotheses are NEVER facts.
5. Safe-First Ordering:
   OBSERVE -> COLLECT_EVIDENCE -> EXPLAIN -> NON_MUTATING_ACTION -> REVERSIBLE_MUTATION -> IRREVERSIBLE_MUTATION.
6. Unknown Outcome Safety:
   Ambiguous or timed-out mutations NEVER trigger automated retries. Must observe first.
7. Verification-Aware Recovery:
   Execution Succeeded + Verification Failed = OVERALL FAILURE (VERIFICATION_FAILURE).
   Preserves both facts in evidence; never misclassifies as simple execution failure.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
import logging
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import uuid

from core.events import EVEvent, EVEventBus
from core.models import (
    ActionCategory,
    ActionReversibility,
    AgentAction,
    AgentTask,
    Diagnosis,
    DiagnosisCategory,
    DiagnosisStatus,
    EpistemicType,
    EvidenceItem,
    EvidenceType,
    EVEventSeverity,
    EVEventType,
    ExecutionResult,
    ExecutionStatus,
    FailureClassification,
    Hypothesis,
    RecoveryOption,
    RecoveryStage,
    RiskLevel,
    VerificationResult,
    VerificationStatus,
    VerificationType,
    sanitize_metadata,
)
from core.plan import Plan, PlanStatus, PlanStep, StepStatus
from core.plan_validator import PlanValidator, READ_ONLY_ACTIONS, NON_COMPENSABLE_ACTIONS
from core.risk import EVRiskEngine
from core.risk_intelligence import map_action_to_category

try:
    from core.system_monitor import SystemAlert, SystemObservation
except ImportError:
    SystemAlert = Any  # type: ignore
    SystemObservation = Any  # type: ignore

logger = logging.getLogger("ev.recovery")



class EVDiagnosticEngine:
    """
    Deterministic diagnostic engine for E.V.
    Analyzes system alerts, telemetry, execution results, and verification failures
    to construct evidence-backed structured Diagnoses with ranked root-cause hypotheses.

    Strictly read-only with ZERO execution authority.
    """

    def __init__(self, event_bus: Optional[EVEventBus] = None) -> None:
        self.event_bus: Optional[EVEventBus] = event_bus

    # -------------------------------------------------------------------------
    # 1. System Alert & Awareness Diagnosis
    # -------------------------------------------------------------------------
    def diagnose_system_alert(
        self,
        alert: SystemAlert,
        related_observations: Optional[List[SystemObservation]] = None,
    ) -> Diagnosis:
        """
        Deterministically diagnose a system alert from EVSystemMonitor or EVAwarenessEngine.
        Correlates metric values, thresholds, and process consumers into structured evidence.
        """
        diag_id = f"diag-{uuid.uuid4().hex[:8]}"
        cond_id = getattr(alert, "alert_id", f"alert-{uuid.uuid4().hex[:6]}")
        domain = getattr(alert, "domain", None)
        domain_val = domain.value if hasattr(domain, "value") else str(domain).lower()

        evidence_items: List[EvidenceItem] = []
        hypotheses: List[Hypothesis] = []
        affected_resources: List[str] = []

        # 1. Primary alert evidence (FACT)
        alert_val = getattr(alert, "value", 0.0)
        alert_thresh = getattr(alert, "threshold", 0.0)
        alert_msg = getattr(alert, "message", "System condition detected")
        primary_ev = EvidenceItem(
            evidence_id=f"ev-{uuid.uuid4().hex[:6]}",
            evidence_type=EvidenceType.SYSTEM_ALERT,
            description=f"Alert: {alert_msg} (value={alert_val}, threshold={alert_thresh})",
            source="system_monitor",
            timestamp=getattr(alert, "triggered_at", datetime.now()),
            confidence=1.0,
            epistemic_type=EpistemicType.FACT,
            data={
                "metric": getattr(alert, "metric", "unknown"),
                "value": alert_val,
                "threshold": alert_thresh,
                "sustained_seconds": getattr(alert, "sustained_seconds", 0.0),
            },
        )
        evidence_items.append(primary_ev)

        # 2. Correlate domain-specific telemetry
        meta = getattr(alert, "metadata", {}) or {}
        cat = DiagnosisCategory.RESOURCE_PRESSURE
        severity = EVEventSeverity.WARNING
        if getattr(alert, "severity", None) and hasattr(alert.severity, "value"):
            sev_name = alert.severity.value.upper()
            if sev_name in EVEventSeverity.__members__:
                severity = EVEventSeverity(sev_name)

        if domain_val == "cpu":
            cat = DiagnosisCategory.RESOURCE_PRESSURE
            top_proc = meta.get("highest_process") or meta.get("process_name")
            top_pct = meta.get("highest_process_cpu") or meta.get("cpu_percent")

            if top_proc:
                affected_resources.append(str(top_proc))
                ev_proc = EvidenceItem(
                    evidence_id=f"ev-{uuid.uuid4().hex[:6]}",
                    evidence_type=EvidenceType.PROCESS_STATE,
                    description=f"Process '{top_proc}' CPU utilization is {top_pct}%",
                    source="system_monitor",
                    confidence=1.0,
                    epistemic_type=EpistemicType.FACT,
                    data={"process_name": top_proc, "cpu_percent": top_pct},
                )
                evidence_items.append(ev_proc)

                # Primary hypothesis: top process is primary contributor
                hypotheses.append(
                    Hypothesis(
                        hypothesis_id=f"hyp-{uuid.uuid4().hex[:6]}",
                        description=f"Process '{top_proc}' is consuming excessive CPU ({top_pct}%)",
                        confidence=0.85,
                        epistemic_type=EpistemicType.INFERENCE,
                        supporting_evidence_ids=[primary_ev.evidence_id, ev_proc.evidence_id],
                        is_primary=True,
                    )
                )
                # Secondary hypothesis
                hypotheses.append(
                    Hypothesis(
                        hypothesis_id=f"hyp-{uuid.uuid4().hex[:6]}",
                        description="Multiple concurrent processes are contributing to aggregate CPU pressure",
                        confidence=0.45,
                        epistemic_type=EpistemicType.INFERENCE,
                        supporting_evidence_ids=[primary_ev.evidence_id],
                        is_primary=False,
                    )
                )
            else:
                hypotheses.append(
                    Hypothesis(
                        hypothesis_id=f"hyp-{uuid.uuid4().hex[:6]}",
                        description="Aggregate system background workload exceeds CPU threshold",
                        confidence=0.70,
                        epistemic_type=EpistemicType.INFERENCE,
                        supporting_evidence_ids=[primary_ev.evidence_id],
                        is_primary=True,
                    )
                )

        elif domain_val == "memory":
            cat = DiagnosisCategory.RESOURCE_PRESSURE
            top_proc = meta.get("highest_process") or meta.get("process_name")
            mem_pct = meta.get("memory_percent", alert_val)
            if top_proc:
                affected_resources.append(str(top_proc))
                ev_mem = EvidenceItem(
                    evidence_id=f"ev-{uuid.uuid4().hex[:6]}",
                    evidence_type=EvidenceType.PROCESS_STATE,
                    description=f"Process '{top_proc}' is primary memory consumer ({meta.get('highest_process_memory_mb', 0)} MB)",
                    source="system_monitor",
                    confidence=1.0,
                    epistemic_type=EpistemicType.FACT,
                    data={"process_name": top_proc, "metadata": meta},
                )
                evidence_items.append(ev_mem)
                hypotheses.append(
                    Hypothesis(
                        hypothesis_id=f"hyp-{uuid.uuid4().hex[:6]}",
                        description=f"Process '{top_proc}' memory footprint is driving system memory exhaustion ({mem_pct}%)",
                        confidence=0.80,
                        epistemic_type=EpistemicType.INFERENCE,
                        supporting_evidence_ids=[primary_ev.evidence_id, ev_mem.evidence_id],
                        is_primary=True,
                    )
                )
            else:
                hypotheses.append(
                    Hypothesis(
                        hypothesis_id=f"hyp-{uuid.uuid4().hex[:6]}",
                        description="System physical RAM usage exceeds threshold without a single dominant process",
                        confidence=0.75,
                        epistemic_type=EpistemicType.INFERENCE,
                        supporting_evidence_ids=[primary_ev.evidence_id],
                        is_primary=True,
                    )
                )

        elif domain_val == "disk":
            cat = DiagnosisCategory.RESOURCE_PRESSURE
            disk_path = meta.get("path") or meta.get("disk_path") or "C:\\"
            affected_resources.append(str(disk_path))
            hypotheses.append(
                Hypothesis(
                    hypothesis_id=f"hyp-{uuid.uuid4().hex[:6]}",
                    description=f"Volume '{disk_path}' free space depleted below threshold ({alert_thresh}%)",
                    confidence=0.90,
                    epistemic_type=EpistemicType.INFERENCE,
                    supporting_evidence_ids=[primary_ev.evidence_id],
                    is_primary=True,
                )
            )

        elif domain_val in ("service", "system"):
            svc_name = meta.get("service_name") or meta.get("target")
            if svc_name:
                cat = DiagnosisCategory.SERVICE_FAILURE
                affected_resources.append(str(svc_name))
                hypotheses.append(
                    Hypothesis(
                        hypothesis_id=f"hyp-{uuid.uuid4().hex[:6]}",
                        description=f"Windows service '{svc_name}' is stopped or failed",
                        confidence=0.90,
                        epistemic_type=EpistemicType.INFERENCE,
                        supporting_evidence_ids=[primary_ev.evidence_id],
                        is_primary=True,
                    )
                )
            else:
                cat = DiagnosisCategory.RESOURCE_PRESSURE
                hypotheses.append(
                    Hypothesis(
                        hypothesis_id=f"hyp-{uuid.uuid4().hex[:6]}",
                        description="System health anomaly reported by system monitor",
                        confidence=0.60,
                        epistemic_type=EpistemicType.INFERENCE,
                        supporting_evidence_ids=[primary_ev.evidence_id],
                        is_primary=True,
                    )
                )

        diag = Diagnosis(
            diagnosis_id=diag_id,
            condition_id=cond_id,
            category=cat,
            severity=severity,
            confidence=0.90,
            evidence=evidence_items,
            probable_causes=hypotheses,
            affected_resources=affected_resources,
            detected_at=datetime.now(),
            status=DiagnosisStatus.CONFIRMED,
            metadata={"alert_metadata": sanitize_metadata(meta)},
        )

        self._publish_diagnosis_event(diag)
        return diag

    # -------------------------------------------------------------------------
    # 2. Execution & Verification Failure Diagnosis
    # -------------------------------------------------------------------------
    def diagnose_execution_result(
        self,
        execution: ExecutionResult,
        verification: Optional[VerificationResult] = None,
        action_name: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Diagnosis:
        """
        Deterministically diagnose an execution and/or verification failure.

        CANONICAL INVARIANT:
        If execution SUCCEEDED and verification FAILED:
        Diagnosis is VERIFICATION_FAILURE (never pure execution failure).
        Both facts are preserved in evidence.
        """
        diag_id = f"diag-{uuid.uuid4().hex[:8]}"
        cond_id = f"exec-{execution.action_id}"
        act_name = action_name or str(execution.action_type)
        params = sanitize_metadata(parameters or {})

        evidence_items: List[EvidenceItem] = []
        hypotheses: List[Hypothesis] = []
        affected_resources: List[str] = []

        # Target resource extraction
        target = params.get("path") or params.get("name") or params.get("process_name") or params.get("hostname")
        if target:
            affected_resources.append(str(target))

        # 1. Execution Evidence (FACT)
        ev_exec = EvidenceItem(
            evidence_id=f"ev-{uuid.uuid4().hex[:6]}",
            evidence_type=EvidenceType.EXECUTION_RESULT,
            description=f"Action '{act_name}' finished with status={execution.status.value}",
            source="agent_execution",
            timestamp=execution.finished_at,
            confidence=1.0,
            epistemic_type=EpistemicType.FACT,
            data={
                "action_id": execution.action_id,
                "action_type": act_name,
                "status": execution.status.value,
                "duration": execution.duration,
                "error": execution.error,
            },
        )
        evidence_items.append(ev_exec)

        # 2. Verification Evidence (if present, FACT)
        ev_verif: Optional[EvidenceItem] = None
        if verification is not None:
            ev_verif = EvidenceItem(
                evidence_id=f"ev-{uuid.uuid4().hex[:6]}",
                evidence_type=EvidenceType.VERIFICATION_RESULT,
                description=f"Verification status={verification.status.value}: {verification.message or verification.error or 'Check completed'}",
                source="verifier",
                timestamp=verification.timestamp,
                confidence=1.0,
                epistemic_type=EpistemicType.FACT,
                data={
                    "status": verification.status.value,
                    "verification_type": verification.verification_type.value if verification.verification_type else None,
                    "success": verification.success,
                    "message": verification.message,
                    "error": verification.error,
                    "observed_state": sanitize_metadata(verification.observed_state),
                },
            )
            evidence_items.append(ev_verif)

        # 3. Classify Failure Mode
        classification = self.classify_failure(execution, verification)

        # 4. Determine Category & Severity & Hypotheses
        if classification == FailureClassification.VERIFICATION_FAILED:
            category = DiagnosisCategory.VERIFICATION_FAILURE
            severity = EVEventSeverity.ERROR
            hypotheses.append(
                Hypothesis(
                    hypothesis_id=f"hyp-{uuid.uuid4().hex[:6]}",
                    description=(
                        f"Action '{act_name}' command completed, but target state verification failed: "
                        f"{verification.message if verification else 'Mismatch detected'}"
                    ),
                    confidence=0.95,
                    epistemic_type=EpistemicType.INFERENCE,
                    supporting_evidence_ids=[ev_exec.evidence_id, ev_verif.evidence_id] if ev_verif else [ev_exec.evidence_id],
                    is_primary=True,
                )
            )
            hypotheses.append(
                Hypothesis(
                    hypothesis_id=f"hyp-{uuid.uuid4().hex[:6]}",
                    description="Windows OS or target subsystem has asynchronous delay in applying requested change",
                    confidence=0.50,
                    epistemic_type=EpistemicType.INFERENCE,
                    supporting_evidence_ids=[ev_exec.evidence_id],
                    is_primary=False,
                )
            )

        elif classification == FailureClassification.TIMEOUT:
            category = DiagnosisCategory.TIMEOUT
            severity = EVEventSeverity.ERROR
            hypotheses.append(
                Hypothesis(
                    hypothesis_id=f"hyp-{uuid.uuid4().hex[:6]}",
                    description=f"Action '{act_name}' execution timed out; final Windows state is ambiguous",
                    confidence=0.90,
                    epistemic_type=EpistemicType.INFERENCE,
                    supporting_evidence_ids=[ev_exec.evidence_id],
                    is_primary=True,
                )
            )

        elif classification == FailureClassification.UNKNOWN_OUTCOME:
            category = DiagnosisCategory.UNKNOWN_FAILURE
            severity = EVEventSeverity.ERROR
            hypotheses.append(
                Hypothesis(
                    hypothesis_id=f"hyp-{uuid.uuid4().hex[:6]}",
                    description=f"Action '{act_name}' outcome is UNKNOWN; safe observation required before any mutation",
                    confidence=0.90,
                    epistemic_type=EpistemicType.INFERENCE,
                    supporting_evidence_ids=[ev_exec.evidence_id],
                    is_primary=True,
                )
            )

        elif classification == FailureClassification.CANCELLED:
            category = DiagnosisCategory.UNKNOWN_FAILURE
            severity = EVEventSeverity.INFO
            hypotheses.append(
                Hypothesis(
                    hypothesis_id=f"hyp-{uuid.uuid4().hex[:6]}",
                    description=f"Action '{act_name}' was cooperatively CANCELLED by user or cancellation token",
                    confidence=1.0,
                    epistemic_type=EpistemicType.INFERENCE,
                    supporting_evidence_ids=[ev_exec.evidence_id],
                    is_primary=True,
                )
            )

        elif classification == FailureClassification.PERMISSION_DENIED:
            category = DiagnosisCategory.PERMISSION_FAILURE
            severity = EVEventSeverity.ERROR
            hypotheses.append(
                Hypothesis(
                    hypothesis_id=f"hyp-{uuid.uuid4().hex[:6]}",
                    description=f"Action '{act_name}' failed due to insufficient Windows permissions or elevation requirement",
                    confidence=0.95,
                    epistemic_type=EpistemicType.INFERENCE,
                    supporting_evidence_ids=[ev_exec.evidence_id],
                    is_primary=True,
                )
            )

        elif classification == FailureClassification.RESOURCE_UNAVAILABLE:
            category = (
                DiagnosisCategory.FILE_FAILURE if "FILE" in act_name
                else DiagnosisCategory.SERVICE_FAILURE if "SERVICE" in act_name
                else DiagnosisCategory.PROCESS_FAILURE if "PROCESS" in act_name
                else DiagnosisCategory.NETWORK_FAILURE if ("DNS" in act_name or "PORT" in act_name)
                else DiagnosisCategory.PROCESS_FAILURE
            )
            severity = EVEventSeverity.ERROR
            hypotheses.append(
                Hypothesis(
                    hypothesis_id=f"hyp-{uuid.uuid4().hex[:6]}",
                    description=f"Target resource '{target or act_name}' was not found or unavailable on this system",
                    confidence=0.90,
                    epistemic_type=EpistemicType.INFERENCE,
                    supporting_evidence_ids=[ev_exec.evidence_id],
                    is_primary=True,
                )
            )

        else:
            # Ordinary execution failure
            category = (
                DiagnosisCategory.FILE_FAILURE if "FILE" in act_name
                else DiagnosisCategory.SERVICE_FAILURE if "SERVICE" in act_name
                else DiagnosisCategory.PROCESS_FAILURE if "PROCESS" in act_name
                else DiagnosisCategory.NETWORK_FAILURE if ("DNS" in act_name or "PORT" in act_name)
                else DiagnosisCategory.PROCESS_FAILURE
            )
            severity = EVEventSeverity.ERROR
            err_msg = execution.error or "Unknown execution error"
            hypotheses.append(
                Hypothesis(
                    hypothesis_id=f"hyp-{uuid.uuid4().hex[:6]}",
                    description=f"Action '{act_name}' execution failed: {err_msg}",
                    confidence=0.85,
                    epistemic_type=EpistemicType.INFERENCE,
                    supporting_evidence_ids=[ev_exec.evidence_id],
                    is_primary=True,
                )
            )

        diag = Diagnosis(
            diagnosis_id=diag_id,
            condition_id=cond_id,
            category=category,
            severity=severity,
            confidence=0.90,
            evidence=evidence_items,
            probable_causes=hypotheses,
            affected_resources=affected_resources,
            detected_at=datetime.now(),
            status=DiagnosisStatus.CONFIRMED,
            metadata={
                "action_id": execution.action_id,
                "action_type": act_name,
                "parameters": params,
                "failure_classification": classification.value,
            },
        )

        self._publish_diagnosis_event(diag)
        return diag

    # -------------------------------------------------------------------------
    # 3. Failure Classification Logic
    # -------------------------------------------------------------------------
    def classify_failure(
        self,
        execution: ExecutionResult,
        verification: Optional[VerificationResult] = None,
    ) -> FailureClassification:
        """
        Deterministically classify the root failure mode.
        """
        if execution.status == ExecutionStatus.CANCELLED:
            return FailureClassification.CANCELLED

        if execution.status == ExecutionStatus.UNKNOWN:
            return FailureClassification.UNKNOWN_OUTCOME

        # Execution Succeeded + Verification Failed = VERIFICATION_FAILED
        if execution.status == ExecutionStatus.SUCCEEDED:
            if verification is not None and not verification.is_verified:
                return FailureClassification.VERIFICATION_FAILED
            return FailureClassification.EXECUTION_FAILED

        # Check execution error text for specific signatures
        err = (execution.error or "").lower()
        if "timed out" in err or "timeout" in err or getattr(execution, "timed_out", False):
            return FailureClassification.TIMEOUT
        if "permission" in err or "access denied" in err or "unauthorized" in err or "elevation" in err or "admin" in err:
            return FailureClassification.PERMISSION_DENIED
        if "not found" in err or "does not exist" in err or "no such" in err:
            return FailureClassification.RESOURCE_UNAVAILABLE
        if "invalid parameter" in err or "invalid argument" in err or "syntax" in err:
            return FailureClassification.INVALID_PARAMETERS

        return FailureClassification.EXECUTION_FAILED

    # -------------------------------------------------------------------------
    # 4. Brain Hypothesis Evaluation & Boundary Enforcement
    # -------------------------------------------------------------------------
    def evaluate_brain_hypothesis(
        self,
        brain_claim: Dict[str, Any],
        existing_evidence: List[EvidenceItem],
    ) -> Hypothesis:
        """
        Evaluate an untrusted hypothesis suggested by the Brain.

        SECURITY BOUNDARY:
        1. Brain claims are UNTRUSTED context.
        2. Brain claims can NEVER be classified as FACT.
        3. If corroborated by deterministic FACT evidence, classified as INFERENCE.
        4. If uncorroborated or speculative, classified as SPECULATION with low confidence.
        """
        desc = str(brain_claim.get("description") or brain_claim.get("claim") or "Unspecified Brain hypothesis").strip()
        claimed_resource = str(brain_claim.get("affected_resource") or "").lower().strip()
        claimed_cause = str(brain_claim.get("cause") or "").lower().strip()

        # Find corroborating evidence
        corroborating_ids: List[str] = []
        is_corroborated = False

        for ev in existing_evidence:
            ev_desc = ev.description.lower()
            ev_data_str = str(ev.data).lower()
            if claimed_resource and (claimed_resource in ev_desc or claimed_resource in ev_data_str):
                corroborating_ids.append(ev.evidence_id)
                if ev.epistemic_type == EpistemicType.FACT:
                    is_corroborated = True
            elif claimed_cause and (claimed_cause in ev_desc or claimed_cause in ev_data_str):
                corroborating_ids.append(ev.evidence_id)
                if ev.epistemic_type == EpistemicType.FACT:
                    is_corroborated = True

        if is_corroborated:
            return Hypothesis(
                hypothesis_id=f"hyp-brain-{uuid.uuid4().hex[:6]}",
                description=f"[Corroborated Brain Inference] {desc}",
                confidence=min(0.70, float(brain_claim.get("confidence", 0.60))),
                epistemic_type=EpistemicType.INFERENCE,
                supporting_evidence_ids=corroborating_ids,
                is_primary=False,
            )
        else:
            return Hypothesis(
                hypothesis_id=f"hyp-brain-{uuid.uuid4().hex[:6]}",
                description=f"[Uncorroborated Brain Speculation] {desc}",
                confidence=min(0.25, float(brain_claim.get("confidence", 0.25))),
                epistemic_type=EpistemicType.SPECULATION,
                supporting_evidence_ids=[],
                is_primary=False,
            )

    def _publish_diagnosis_event(self, diagnosis: Diagnosis) -> None:
        """Publish DIAGNOSIS_CREATED event to EVEventBus if configured."""
        if not self.event_bus:
            return
        try:
            self.event_bus.publish(
                event_type=EVEventType.DIAGNOSIS_CREATED,
                source="diagnostic_engine",
                severity=diagnosis.severity,
                message=f"Diagnosis: {diagnosis.category.value} detected",
                data={
                    "diagnosis_id": diagnosis.diagnosis_id,
                    "condition_id": diagnosis.condition_id,
                    "category": diagnosis.category.value,
                    "confidence": diagnosis.confidence,
                    "affected_resources": diagnosis.affected_resources,
                    "probable_causes_count": len(diagnosis.probable_causes),
                },
            )
        except Exception as exc:
            logger.warning("Failed to publish diagnosis event: %s", exc)




class EVRecoveryPlanner:
    """
    Deterministic recovery proposal planner for E.V.

    Generates structured, safe-first recovery proposals from a Diagnosis.
    Converts proposals into canonical, validated, risk-assessed Plans.

    CRITICAL INVARIANT:
    PROPOSAL ONLY. ZERO autonomous execution.
    Mutating options strictly require human approval and transaction wrapping.
    """

    def __init__(
        self,
        risk_engine: Optional[EVRiskEngine] = None,
        plan_validator: Optional[PlanValidator] = None,
        event_bus: Optional[EVEventBus] = None,
    ) -> None:
        self.risk_engine: EVRiskEngine = risk_engine or EVRiskEngine()
        self.plan_validator: PlanValidator = plan_validator or PlanValidator(self.risk_engine)
        self.event_bus: Optional[EVEventBus] = event_bus

    # -------------------------------------------------------------------------
    # 1. Recovery Option Generation
    # -------------------------------------------------------------------------
    def generate_recovery_options(self, diagnosis: Diagnosis) -> List[RecoveryOption]:
        """
        Generate structured RecoveryOptions for a Diagnosis.
        Guarantees Safe-First ordering:
        OBSERVE (1) -> COLLECT_EVIDENCE (2) -> EXPLAIN (3) -> NON_MUTATING_ACTION (4)
        -> REVERSIBLE_MUTATION (5) -> IRREVERSIBLE_MUTATION (6)
        """
        options: List[RecoveryOption] = []
        cat = diagnosis.category
        meta = diagnosis.metadata or {}
        diag_id = diagnosis.diagnosis_id
        affected = diagnosis.affected_resources[0] if diagnosis.affected_resources else None

        # ---------------------------------------------------------------------
        # Case A: CANCELLED -> Zero retry mutation, explain/observe only
        # ---------------------------------------------------------------------
        if meta.get("failure_classification") == FailureClassification.CANCELLED.value:
            options.append(
                RecoveryOption(
                    option_id=f"rec-{uuid.uuid4().hex[:6]}",
                    diagnosis_id=diag_id,
                    description="Explain that the action was safely cancelled and previous steps were rolled back",
                    stage=RecoveryStage.EXPLAIN,
                    safe_order_rank=3,
                    action=None,
                    expected_effect="User informed of cancellation status; system remains idle",
                    risk_level=RiskLevel.NONE,
                    requires_approval=False,
                )
            )
            return options

        # ---------------------------------------------------------------------
        # Case B: UNKNOWN OUTCOME / TIMEOUT -> Zero blind retry! Observe only
        # ---------------------------------------------------------------------
        if (
            cat in (DiagnosisCategory.TIMEOUT, DiagnosisCategory.UNKNOWN_FAILURE)
            or meta.get("failure_classification") in (FailureClassification.TIMEOUT.value, FailureClassification.UNKNOWN_OUTCOME.value)
        ):
            options.append(
                RecoveryOption(
                    option_id=f"rec-{uuid.uuid4().hex[:6]}",
                    diagnosis_id=diag_id,
                    description="Re-observe system state to verify if background operation took effect without new mutation",
                    stage=RecoveryStage.OBSERVE,
                    safe_order_rank=1,
                    action=AgentAction.FIND_PROCESS if affected and ".exe" in affected.lower() else AgentAction.GET_FILE_INFO if affected else None,
                    parameters={"name": affected} if affected and ".exe" in affected.lower() else {"path": affected} if affected else {},
                    expected_effect="Determine actual Windows state without issuing duplicate mutating commands",
                    risk_level=RiskLevel.NONE,
                    requires_approval=False,
                )
            )
            options.append(
                RecoveryOption(
                    option_id=f"rec-{uuid.uuid4().hex[:6]}",
                    diagnosis_id=diag_id,
                    description="Explain timeout/ambiguous outcome to user and wait for human instruction",
                    stage=RecoveryStage.EXPLAIN,
                    safe_order_rank=3,
                    action=None,
                    expected_effect="User receives explanation of unknown outcome; blind re-execution prevented",
                    risk_level=RiskLevel.NONE,
                    requires_approval=False,
                )
            )
            return sorted(options, key=lambda o: o.safe_order_rank)

        # ---------------------------------------------------------------------
        # Case C: VERIFICATION_FAILURE -> Observe & Explain (No blind re-mutation)
        # ---------------------------------------------------------------------
        if cat == DiagnosisCategory.VERIFICATION_FAILURE:
            options.append(
                RecoveryOption(
                    option_id=f"rec-{uuid.uuid4().hex[:6]}",
                    diagnosis_id=diag_id,
                    description=f"Inspect actual state of resource '{affected or 'target'}' to identify discrepancy",
                    stage=RecoveryStage.OBSERVE,
                    safe_order_rank=1,
                    action=AgentAction.GET_FILE_INFO if affected and ("\\" in affected or "/" in affected) else AgentAction.FIND_PROCESS if affected else None,
                    parameters={"path": affected} if affected and ("\\" in affected or "/" in affected) else {"name": affected} if affected else {},
                    expected_effect="Confirm discrepancy between command exit status and actual observed OS state",
                    risk_level=RiskLevel.NONE,
                    requires_approval=False,
                )
            )
            options.append(
                RecoveryOption(
                    option_id=f"rec-{uuid.uuid4().hex[:6]}",
                    diagnosis_id=diag_id,
                    description="Explain verification mismatch to user; previous changes have been rolled back",
                    stage=RecoveryStage.EXPLAIN,
                    safe_order_rank=3,
                    action=None,
                    expected_effect="User notified that operation was not verified and was safely rolled back",
                    risk_level=RiskLevel.NONE,
                    requires_approval=False,
                )
            )
            return sorted(options, key=lambda o: o.safe_order_rank)

        # ---------------------------------------------------------------------
        # Case D: RESOURCE_PRESSURE (CPU / Memory / Disk)
        # ---------------------------------------------------------------------
        if cat == DiagnosisCategory.RESOURCE_PRESSURE:
            # 1. OBSERVE
            if affected and ".exe" in affected.lower():
                options.append(
                    RecoveryOption(
                        option_id=f"rec-{uuid.uuid4().hex[:6]}",
                        diagnosis_id=diag_id,
                        description=f"Inspect process '{affected}' details and resource consumption",
                        stage=RecoveryStage.OBSERVE,
                        safe_order_rank=1,
                        action=AgentAction.FIND_PROCESS,
                        parameters={"name": affected},
                        expected_effect="Retrieve PID, process path, and live status of top consumer",
                        risk_level=RiskLevel.NONE,
                        requires_approval=False,
                    )
                )

            # 2. COLLECT_EVIDENCE
            options.append(
                RecoveryOption(
                    option_id=f"rec-{uuid.uuid4().hex[:6]}",
                    diagnosis_id=diag_id,
                    description="Collect detailed process list to identify other contributing consumers",
                    stage=RecoveryStage.COLLECT_EVIDENCE,
                    safe_order_rank=2,
                    action=AgentAction.FIND_PROCESS,
                    parameters={},
                    expected_effect="Audit top process resource consumers across system",
                    risk_level=RiskLevel.NONE,
                    requires_approval=False,
                )
            )

            # 3. EXPLAIN
            options.append(
                RecoveryOption(
                    option_id=f"rec-{uuid.uuid4().hex[:6]}",
                    diagnosis_id=diag_id,
                    description=f"Explain resource pressure condition and candidate processes to user",
                    stage=RecoveryStage.EXPLAIN,
                    safe_order_rank=3,
                    action=None,
                    expected_effect="User receives advisory notification on CPU/memory workload",
                    risk_level=RiskLevel.NONE,
                    requires_approval=False,
                )
            )

            # 4. IRREVERSIBLE_MUTATION (Stop process) — STRICTLY REQUIRES APPROVAL
            if affected and ".exe" in affected.lower():
                options.append(
                    RecoveryOption(
                        option_id=f"rec-{uuid.uuid4().hex[:6]}",
                        diagnosis_id=diag_id,
                        description=f"Terminate runaway process '{affected}' (Requires Human Approval)",
                        stage=RecoveryStage.IRREVERSIBLE_MUTATION,
                        safe_order_rank=6,
                        action=AgentAction.STOP_PROCESS,
                        parameters={"process_name": affected},
                        expected_effect=f"Terminate '{affected}' to immediately relieve resource pressure",
                        risk_level=RiskLevel.HIGH,
                        reversible=False,
                        reversibility=ActionReversibility.NON_REVERSIBLE,
                        verification_type=VerificationType.PROCESS_NOT_EXISTS,
                        requires_approval=True,
                    )
                )

        # ---------------------------------------------------------------------
        # Case E: FILE_FAILURE
        # ---------------------------------------------------------------------
        elif cat == DiagnosisCategory.FILE_FAILURE:
            # 1. OBSERVE
            if affected:
                options.append(
                    RecoveryOption(
                        option_id=f"rec-{uuid.uuid4().hex[:6]}",
                        diagnosis_id=diag_id,
                        description=f"Inspect file attributes and presence at '{affected}'",
                        stage=RecoveryStage.OBSERVE,
                        safe_order_rank=1,
                        action=AgentAction.GET_FILE_INFO,
                        parameters={"path": affected},
                        expected_effect="Verify if file exists, size, or path permission block",
                        risk_level=RiskLevel.NONE,
                        requires_approval=False,
                    )
                )

            # 2. EXPLAIN
            options.append(
                RecoveryOption(
                    option_id=f"rec-{uuid.uuid4().hex[:6]}",
                    diagnosis_id=diag_id,
                    description=f"Explain file failure to user and present recovery options",
                    stage=RecoveryStage.EXPLAIN,
                    safe_order_rank=3,
                    action=None,
                    expected_effect="User informed of missing or inaccessible file",
                    risk_level=RiskLevel.NONE,
                    requires_approval=False,
                )
            )

            # 3. REVERSIBLE_MUTATION (Write / recreate file) — REQUIRES APPROVAL
            if affected:
                options.append(
                    RecoveryOption(
                        option_id=f"rec-{uuid.uuid4().hex[:6]}",
                        diagnosis_id=diag_id,
                        description=f"Recreate file at '{affected}' with default content (Requires Human Approval)",
                        stage=RecoveryStage.REVERSIBLE_MUTATION,
                        safe_order_rank=5,
                        action=AgentAction.WRITE_FILE,
                        parameters={"path": affected, "content": ""},
                        expected_effect=f"Recreate file with pre-execution SHA-256 backup",
                        risk_level=RiskLevel.MEDIUM,
                        reversible=True,
                        reversibility=ActionReversibility.REVERSIBLE,
                        verification_type=VerificationType.FILE_EXISTS,
                        requires_approval=True,
                    )
                )

        # ---------------------------------------------------------------------
        # Case F: SERVICE_FAILURE
        # ---------------------------------------------------------------------
        elif cat == DiagnosisCategory.SERVICE_FAILURE:
            # 1. OBSERVE
            if affected:
                options.append(
                    RecoveryOption(
                        option_id=f"rec-{uuid.uuid4().hex[:6]}",
                        diagnosis_id=diag_id,
                        description=f"Inspect status and startup type of service '{affected}'",
                        stage=RecoveryStage.OBSERVE,
                        safe_order_rank=1,
                        action=AgentAction.FIND_SERVICE,
                        parameters={"name": affected},
                        expected_effect="Query current Windows service state without mutating",
                        risk_level=RiskLevel.NONE,
                        requires_approval=False,
                    )
                )

            # 2. EXPLAIN
            options.append(
                RecoveryOption(
                    option_id=f"rec-{uuid.uuid4().hex[:6]}",
                    diagnosis_id=diag_id,
                    description=f"Explain service failure for '{affected or 'service'}' to user",
                    stage=RecoveryStage.EXPLAIN,
                    safe_order_rank=3,
                    action=None,
                    expected_effect="User notified of stopped Windows service",
                    risk_level=RiskLevel.NONE,
                    requires_approval=False,
                )
            )

            # 3. IRREVERSIBLE_MUTATION (Restart Service) — REQUIRES APPROVAL
            if affected:
                options.append(
                    RecoveryOption(
                        option_id=f"rec-{uuid.uuid4().hex[:6]}",
                        diagnosis_id=diag_id,
                        description=f"Restart Windows service '{affected}' (Requires Human Approval)",
                        stage=RecoveryStage.IRREVERSIBLE_MUTATION,
                        safe_order_rank=6,
                        action=AgentAction.RESTART_SERVICE,
                        parameters={"name": affected},
                        expected_effect=f"Attempt service start/restart",
                        risk_level=RiskLevel.HIGH,
                        reversible=False,
                        reversibility=ActionReversibility.NON_REVERSIBLE,
                        verification_type=VerificationType.SERVICE_RUNNING,
                        requires_approval=True,
                    )
                )

        # ---------------------------------------------------------------------
        # Default / Fallback: Observe + Explain
        # ---------------------------------------------------------------------
        if not options:
            options.append(
                RecoveryOption(
                    option_id=f"rec-{uuid.uuid4().hex[:6]}",
                    diagnosis_id=diag_id,
                    description="Observe system state and diagnose failure cause",
                    stage=RecoveryStage.OBSERVE,
                    safe_order_rank=1,
                    action=None,
                    expected_effect="Review system telemetry to identify cause",
                    risk_level=RiskLevel.NONE,
                    requires_approval=False,
                )
            )
            options.append(
                RecoveryOption(
                    option_id=f"rec-{uuid.uuid4().hex[:6]}",
                    diagnosis_id=diag_id,
                    description="Explain condition to user and await instruction",
                    stage=RecoveryStage.EXPLAIN,
                    safe_order_rank=3,
                    action=None,
                    expected_effect="Inform user without mutation",
                    risk_level=RiskLevel.NONE,
                    requires_approval=False,
                )
            )

        # Strictly sort by safe-first rank
        sorted_options = sorted(options, key=lambda o: o.safe_order_rank)

        # Publish proposal event
        self._publish_recovery_proposed_event(diagnosis, sorted_options)
        return sorted_options

    # -------------------------------------------------------------------------
    # 2. Canonical Plan Generation from Recovery Option
    # -------------------------------------------------------------------------
    def create_recovery_plan(
        self,
        option: RecoveryOption,
        goal_override: Optional[str] = None,
    ) -> Plan:
        """
        Convert a structured RecoveryOption containing an action into a canonical Plan.

        SECURITY & INTEGRATION INVARIANTS:
        1. Translates RecoveryOption into Plan and PlanStep instances.
        2. Validates plan via PlanValidator.
        3. Authoritatively assesses plan risk via EVRiskEngine.
        4. Enforces: plan.risk_level = MAX(step_risks).
        5. Prohibits any risk downgrades.
        6. Mutating plans have transaction_required=True and approval_required=True.
        """
        if option.action is None:
            # Non-action option (e.g. EXPLAIN) -> single informational step or empty plan
            p_id = f"plan-rec-{uuid.uuid4().hex[:8]}"
            plan = Plan(
                plan_id=p_id,
                goal=goal_override or f"Explain: {option.description}",
                steps=[],
                status=PlanStatus.READY,
                risk_level=RiskLevel.NONE,
                approval_required=False,
                transaction_required=False,
                metadata={"recovery_option_id": option.option_id, "stage": option.stage.value},
            )
            option.plan_id = p_id
            return plan

        p_id = f"plan-rec-{uuid.uuid4().hex[:8]}"
        step_id = f"step-{uuid.uuid4().hex[:6]}"
        is_mutating = option.action not in READ_ONLY_ACTIONS

        step = PlanStep(
            step_id=step_id,
            action=option.action,
            parameters=copy.deepcopy(option.parameters),
            verification_type=option.verification_type,
            is_compensable=(option.action not in NON_COMPENSABLE_ACTIONS),
            reversibility=option.reversibility,
            description=option.description,
        )

        plan = Plan(
            plan_id=p_id,
            goal=goal_override or f"Recovery: {option.description}",
            steps=[step],
            status=PlanStatus.CREATED,
            transaction_required=is_mutating,
            verification_required=(option.verification_type is not None),
            metadata={
                "recovery_option_id": option.option_id,
                "diagnosis_id": option.diagnosis_id,
                "stage": option.stage.value,
                "safe_order_rank": option.safe_order_rank,
            },
        )

        # 1. Authoritative Validation via PlanValidator (which evaluates risk and approval)
        val_result = self.plan_validator.validate(plan)
        if not val_result.is_valid:
            raise ValueError(f"Recovery plan failed validation: {'; '.join(val_result.errors)}")

        validated_plan = val_result.validated_plan or plan
        validated_plan.risk_level = val_result.aggregate_risk
        validated_plan.approval_required = val_result.approval_required or is_mutating
        validated_plan.transaction_required = val_result.transaction_required

        # If mutating, enforce AWAITING_APPROVAL status
        if validated_plan.approval_required:
            validated_plan.status = PlanStatus.AWAITING_APPROVAL
        else:
            validated_plan.status = PlanStatus.READY

        option.plan_id = validated_plan.plan_id
        return validated_plan

    def _publish_recovery_proposed_event(
        self,
        diagnosis: Diagnosis,
        options: List[RecoveryOption],
    ) -> None:
        """Publish RECOVERY_PROPOSED event to EVEventBus if configured."""
        if not self.event_bus:
            return
        try:
            self.event_bus.publish(
                event_type=EVEventType.RECOVERY_PROPOSED,
                source="recovery_planner",
                severity=diagnosis.severity,
                message=f"Recovery proposed for diagnosis {diagnosis.diagnosis_id} ({len(options)} options)",
                data={
                    "diagnosis_id": diagnosis.diagnosis_id,
                    "category": diagnosis.category.value,
                    "options_count": len(options),
                    "options_summary": [
                        {
                            "option_id": o.option_id,
                            "stage": o.stage.value,
                            "rank": o.safe_order_rank,
                            "action": o.action.value if o.action else None,
                            "requires_approval": o.requires_approval,
                            "risk_level": o.risk_level.value,
                        }
                        for o in options
                    ],
                },
            )
        except Exception as exc:
            logger.warning("Failed to publish recovery proposed event: %s", exc)


