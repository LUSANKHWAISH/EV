"""
Comprehensive Unit and Integration Tests for Task 017:
Contextual Action Planning & Recovery Intelligence.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import unittest
from unittest.mock import MagicMock, patch
import pytest

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
from core.plan_validator import PlanValidator
from core.recovery import EVDiagnosticEngine, EVRecoveryPlanner
from core.risk import EVRiskEngine
from core.system_monitor import SystemAlert, SystemMetricDomain, SystemObservation, SystemObservationSeverity


# =============================================================================
# 1. Diagnosis Engine Tests
# =============================================================================

class TestDiagnosticEngine(unittest.TestCase):
    """Test deterministic multi-evidence diagnosis generation and correlation."""

    def setUp(self) -> None:
        self.bus = EVEventBus()
        self.engine = EVDiagnosticEngine(event_bus=self.bus)

    def test_cpu_pressure_diagnosis(self) -> None:
        """Test CPU alert correlated with top process consumer."""
        alert = SystemAlert(
            alert_id="alert-cpu-1",
            domain=SystemMetricDomain.CPU,
            metric="cpu_percent",
            severity=SystemObservationSeverity.WARNING,
            message="CPU utilization sustained above 85%",
            value=92.5,
            threshold=85.0,
            triggered_at=datetime.now(timezone.utc),
            sustained_seconds=12.0,
            metadata={
                "highest_process": "ffmpeg.exe",
                "highest_process_cpu": 78.4,
            },
        )
        diag = self.engine.diagnose_system_alert(alert)

        self.assertEqual(diag.category, DiagnosisCategory.RESOURCE_PRESSURE)
        self.assertIn("ffmpeg.exe", diag.affected_resources)
        self.assertTrue(len(diag.evidence) >= 2)
        self.assertTrue(len(diag.probable_causes) >= 2)

        # Primary hypothesis should identify top process
        primary_hyp = next((h for h in diag.probable_causes if h.is_primary), None)
        self.assertIsNotNone(primary_hyp)
        self.assertIn("ffmpeg.exe", primary_hyp.description)
        self.assertEqual(primary_hyp.epistemic_type, EpistemicType.INFERENCE)

    def test_memory_pressure_diagnosis(self) -> None:
        """Test Memory alert correlated with top process footprint."""
        alert = SystemAlert(
            alert_id="alert-mem-1",
            domain=SystemMetricDomain.MEMORY,
            metric="memory_percent",
            severity=SystemObservationSeverity.CRITICAL,
            message="Memory utilization sustained above 90%",
            value=94.2,
            threshold=90.0,
            triggered_at=datetime.now(timezone.utc),
            sustained_seconds=20.0,
            metadata={
                "highest_process": "node.exe",
                "highest_process_memory_mb": 4200,
                "memory_percent": 94.2,
            },
        )
        diag = self.engine.diagnose_system_alert(alert)

        self.assertEqual(diag.category, DiagnosisCategory.RESOURCE_PRESSURE)
        self.assertIn("node.exe", diag.affected_resources)
        self.assertEqual(diag.severity, EVEventSeverity.CRITICAL)

    def test_disk_pressure_diagnosis(self) -> None:
        """Test Disk alert for low free space."""
        alert = SystemAlert(
            alert_id="alert-disk-1",
            domain=SystemMetricDomain.DISK,
            metric="disk_free_percent",
            severity=SystemObservationSeverity.WARNING,
            message="Disk free space below 10%",
            value=8.4,
            threshold=10.0,
            triggered_at=datetime.now(timezone.utc),
            sustained_seconds=30.0,
            metadata={"path": "C:\\"},
        )
        diag = self.engine.diagnose_system_alert(alert)

        self.assertEqual(diag.category, DiagnosisCategory.RESOURCE_PRESSURE)
        self.assertIn("C:\\", diag.affected_resources)

    def test_service_failure_diagnosis(self) -> None:
        """Test Windows service failure diagnosis."""
        alert = SystemAlert(
            alert_id="alert-svc-1",
            domain=SystemMetricDomain.SYSTEM,
            metric="service_status",
            severity=SystemObservationSeverity.CRITICAL,
            message="Critical service stopped",
            value=0.0,
            threshold=1.0,
            triggered_at=datetime.now(timezone.utc),
            sustained_seconds=5.0,
            metadata={"service_name": "wuauserv"},
        )
        diag = self.engine.diagnose_system_alert(alert)

        self.assertEqual(diag.category, DiagnosisCategory.SERVICE_FAILURE)
        self.assertIn("wuauserv", diag.affected_resources)

    def test_timeout_execution_diagnosis(self) -> None:
        """Test timeout on mutating action maps to TIMEOUT / UNKNOWN_OUTCOME."""
        exec_res = ExecutionResult(
            action_id="act-timeout-1",
            action_type=AgentAction.STOP_PROCESS,
            status=ExecutionStatus.UNKNOWN,
            duration=30.0,
            error="Execution timed out after 30.0s",
        )
        diag = self.engine.diagnose_execution_result(
            exec_res,
            action_name="STOP_PROCESS",
            parameters={"process_name": "stuck_worker.exe"},
        )

        self.assertEqual(diag.category, DiagnosisCategory.UNKNOWN_FAILURE)
        self.assertIn("stuck_worker.exe", diag.affected_resources)
        self.assertEqual(diag.metadata["failure_classification"], FailureClassification.UNKNOWN_OUTCOME.value)

    def test_permission_denied_diagnosis(self) -> None:
        """Test permission error mapped to PERMISSION_FAILURE."""
        exec_res = ExecutionResult(
            action_id="act-perm-1",
            action_type=AgentAction.WRITE_FILE,
            status=ExecutionStatus.FAILED,
            duration=0.1,
            error="Access denied: Administrator elevation required to write to C:\\Windows\\test.txt",
        )
        diag = self.engine.diagnose_execution_result(
            exec_res,
            action_name="WRITE_FILE",
            parameters={"path": "C:\\Windows\\test.txt"},
        )

        self.assertEqual(diag.category, DiagnosisCategory.PERMISSION_FAILURE)
        self.assertEqual(diag.metadata["failure_classification"], FailureClassification.PERMISSION_DENIED.value)

    def test_verification_failure_diagnosis(self) -> None:
        """
        CANONICAL INVARIANT:
        Execution Succeeded + Verification Failed = OVERALL FAILURE (VERIFICATION_FAILURE).
        Both facts must be preserved in evidence.
        """
        exec_res = ExecutionResult(
            action_id="act-vf-1",
            action_type=AgentAction.WRITE_FILE,
            status=ExecutionStatus.SUCCEEDED,
            duration=0.05,
            result={"bytes_written": 100},
        )
        verif_res = VerificationResult(
            verification_type=VerificationType.FILE_CONTENT_MATCH,
            status=VerificationStatus.FAILED,
            success=False,
            message="Content mismatch: expected hash does not match file on disk",
            observed_state={"file_exists": True, "size_bytes": 100},
        )
        diag = self.engine.diagnose_execution_result(
            exec_res,
            verification=verif_res,
            action_name="WRITE_FILE",
            parameters={"path": "D:\\EV\\test.txt"},
        )

        self.assertEqual(diag.category, DiagnosisCategory.VERIFICATION_FAILURE)
        self.assertEqual(diag.metadata["failure_classification"], FailureClassification.VERIFICATION_FAILED.value)

        # Confirm both execution success and verification failure are present as FACTS
        types = [e.evidence_type for e in diag.evidence]
        self.assertIn(EvidenceType.EXECUTION_RESULT, types)
        self.assertIn(EvidenceType.VERIFICATION_RESULT, types)

        for ev in diag.evidence:
            self.assertEqual(ev.epistemic_type, EpistemicType.FACT)

    def test_cancelled_plan_diagnosis(self) -> None:
        """Test cancelled execution maps to CANCELLED classification."""
        exec_res = ExecutionResult(
            action_id="act-canc-1",
            action_type=AgentAction.WRITE_FILE,
            status=ExecutionStatus.CANCELLED,
            duration=0.01,
            error="Action cancelled before dispatch by CancellationToken",
        )
        diag = self.engine.diagnose_execution_result(
            exec_res,
            action_name="WRITE_FILE",
            parameters={"path": "D:\\EV\\test.txt"},
        )

        self.assertEqual(diag.metadata["failure_classification"], FailureClassification.CANCELLED.value)


# =============================================================================
# 2. Epistemics, Evidence & Brain Boundary Tests
# =============================================================================

class TestEpistemicsAndBrainBoundary(unittest.TestCase):
    """Test Fact vs. Inference vs. Speculation handling and Brain boundaries."""

    def setUp(self) -> None:
        self.engine = EVDiagnosticEngine()

    def test_hypothesis_cannot_be_fact(self) -> None:
        """Ensure Hypothesis model raises ValueError if epistemic_type is FACT."""
        with self.assertRaises(ValueError):
            Hypothesis(
                hypothesis_id="hyp-bad",
                description="This claim is a fact",
                confidence=1.0,
                epistemic_type=EpistemicType.FACT,  # Illegal!
            )

    def test_corroborated_brain_claim_becomes_inference(self) -> None:
        """Test Brain claim supported by evidence is accepted as INFERENCE."""
        existing_evidence = [
            EvidenceItem(
                evidence_id="ev-1",
                evidence_type=EvidenceType.PROCESS_STATE,
                description="Process 'python.exe' is utilizing 88% CPU",
                source="system_monitor",
                confidence=1.0,
                epistemic_type=EpistemicType.FACT,
                data={"process_name": "python.exe", "cpu_percent": 88.0},
            )
        ]
        brain_claim = {
            "description": "python.exe is running an unthrottled worker loop",
            "affected_resource": "python.exe",
            "confidence": 0.80,
        }
        hyp = self.engine.evaluate_brain_hypothesis(brain_claim, existing_evidence)

        self.assertEqual(hyp.epistemic_type, EpistemicType.INFERENCE)
        self.assertIn("Corroborated", hyp.description)
        self.assertIn("ev-1", hyp.supporting_evidence_ids)
        self.assertLessEqual(hyp.confidence, 0.70)  # Capped upper bound for Brain input

    def test_uncorroborated_brain_claim_becomes_speculation(self) -> None:
        """Test Brain claim with no evidence is downgraded to SPECULATION."""
        existing_evidence = [
            EvidenceItem(
                evidence_id="ev-1",
                evidence_type=EvidenceType.METRIC,
                description="CPU is at 95%",
                source="system_monitor",
                confidence=1.0,
                epistemic_type=EpistemicType.FACT,
                data={"metric": "cpu"},
            )
        ]
        brain_claim = {
            "description": "malware_miner.exe might be hiding in svchost",
            "affected_resource": "malware_miner.exe",
            "cause": "crypto mining",
            "confidence": 0.90,
        }
        hyp = self.engine.evaluate_brain_hypothesis(brain_claim, existing_evidence)

        self.assertEqual(hyp.epistemic_type, EpistemicType.SPECULATION)
        self.assertIn("Uncorroborated", hyp.description)
        self.assertEqual(len(hyp.supporting_evidence_ids), 0)
        self.assertLessEqual(hyp.confidence, 0.25)

    def test_evidence_sanitization_redacts_secrets_and_audio(self) -> None:
        """Test EvidenceItem sanitization strips credentials and audio buffers."""
        item = EvidenceItem(
            evidence_id="ev-sec",
            evidence_type=EvidenceType.OBSERVATION,
            description="Inspection of configuration",
            source="test",
            data={
                "api_key": "sk-secret123456789",
                "password": "SuperSecretPassword!",
                "audio_buffer": b"\x00\x01\x02" * 100,
                "safe_field": "public_data",
            },
        )
        self.assertEqual(item.data["api_key"], "[REDACTED]")
        self.assertEqual(item.data["password"], "[REDACTED]")
        self.assertEqual(item.data["audio_buffer"], "[REDACTED_AUDIO_BUFFER]")
        self.assertEqual(item.data["safe_field"], "public_data")


# =============================================================================
# 3. Recovery Planning & Safe-First Ordering Tests
# =============================================================================

class TestRecoveryPlanner(unittest.TestCase):
    """Test safe-first recovery option generation and canonical Plan creation."""

    def setUp(self) -> None:
        self.bus = EVEventBus()
        self.risk_engine = EVRiskEngine()
        self.validator = PlanValidator(self.risk_engine)
        self.planner = EVRecoveryPlanner(
            risk_engine=self.risk_engine,
            plan_validator=self.validator,
            event_bus=self.bus,
        )

    def test_safe_first_ordering_for_cpu_pressure(self) -> None:
        """
        Verify safe-first ordering for CPU pressure:
        OBSERVE (1) -> COLLECT_EVIDENCE (2) -> EXPLAIN (3) -> IRREVERSIBLE_MUTATION (6)
        """
        diag = Diagnosis(
            diagnosis_id="diag-cpu",
            condition_id="cond-cpu",
            category=DiagnosisCategory.RESOURCE_PRESSURE,
            severity=EVEventSeverity.WARNING,
            confidence=0.90,
            affected_resources=["heavy_app.exe"],
        )
        options = self.planner.generate_recovery_options(diag)

        ranks = [o.safe_order_rank for o in options]
        self.assertEqual(ranks, sorted(ranks))

        # First option should be OBSERVE (rank 1)
        self.assertEqual(options[0].stage, RecoveryStage.OBSERVE)
        self.assertFalse(options[0].requires_approval)

        # Mutating option (STOP_PROCESS, rank 6) must require approval
        mutating_opt = next(o for o in options if o.stage == RecoveryStage.IRREVERSIBLE_MUTATION)
        self.assertEqual(mutating_opt.action, AgentAction.STOP_PROCESS)
        self.assertTrue(mutating_opt.requires_approval)
        self.assertFalse(mutating_opt.reversible)

    def test_timeout_and_unknown_prevent_blind_retries(self) -> None:
        """
        CANONICAL INVARIANT:
        If diagnosis follows UNKNOWN or TIMEOUT outcome:
        Planner must NOT propose blindly repeating the mutation.
        Must only propose OBSERVE and EXPLAIN.
        """
        diag = Diagnosis(
            diagnosis_id="diag-timeout",
            condition_id="cond-timeout",
            category=DiagnosisCategory.TIMEOUT,
            severity=EVEventSeverity.ERROR,
            confidence=0.90,
            affected_resources=["worker.exe"],
            metadata={"failure_classification": FailureClassification.TIMEOUT.value},
        )
        options = self.planner.generate_recovery_options(diag)

        # None of the options may be mutating
        for opt in options:
            self.assertIn(opt.stage, (RecoveryStage.OBSERVE, RecoveryStage.EXPLAIN))
            if opt.action:
                self.assertEqual(opt.action, AgentAction.FIND_PROCESS)
            self.assertFalse(opt.requires_approval)

    def test_verification_failure_proposes_observation_not_blind_retry(self) -> None:
        """Verification failure must propose observation & explanation, not blind mutation."""
        diag = Diagnosis(
            diagnosis_id="diag-vf",
            condition_id="cond-vf",
            category=DiagnosisCategory.VERIFICATION_FAILURE,
            severity=EVEventSeverity.ERROR,
            confidence=0.95,
            affected_resources=["D:\\EV\\test.txt"],
            metadata={"failure_classification": FailureClassification.VERIFICATION_FAILED.value},
        )
        options = self.planner.generate_recovery_options(diag)

        for opt in options:
            self.assertIn(opt.stage, (RecoveryStage.OBSERVE, RecoveryStage.EXPLAIN))
            self.assertFalse(opt.requires_approval)

    def test_cancelled_plan_proposes_explain_only(self) -> None:
        """Cancelled plan produces explain proposal, zero mutation retry."""
        diag = Diagnosis(
            diagnosis_id="diag-canc",
            condition_id="cond-canc",
            category=DiagnosisCategory.UNKNOWN_FAILURE,
            severity=EVEventSeverity.INFO,
            confidence=1.0,
            metadata={"failure_classification": FailureClassification.CANCELLED.value},
        )
        options = self.planner.generate_recovery_options(diag)

        self.assertEqual(len(options), 1)
        self.assertEqual(options[0].stage, RecoveryStage.EXPLAIN)
        self.assertIsNone(options[0].action)

    def test_canonical_plan_generation_from_recovery_option(self) -> None:
        """Test converting a RecoveryOption into a validated canonical Plan."""
        opt = RecoveryOption(
            option_id="opt-file-obs",
            diagnosis_id="diag-file",
            description="Inspect file attributes at target path",
            stage=RecoveryStage.OBSERVE,
            safe_order_rank=1,
            action=AgentAction.GET_FILE_INFO,
            parameters={"path": "D:\\EV\\sample.txt"},
            expected_effect="Verify file existence",
            risk_level=RiskLevel.NONE,
            requires_approval=False,
        )
        plan = self.planner.create_recovery_plan(opt)

        self.assertIsInstance(plan, Plan)
        self.assertEqual(len(plan.steps), 1)
        self.assertEqual(plan.steps[0].action, AgentAction.GET_FILE_INFO)
        self.assertEqual(plan.status, PlanStatus.READY)
        self.assertFalse(plan.approval_required)
        self.assertFalse(plan.transaction_required)

    def test_mutating_recovery_plan_enforces_approval_and_transaction(self) -> None:
        """
        Mutating recovery plan MUST have transaction_required=True and approval_required=True.
        Status must transition to AWAITING_APPROVAL.
        """
        opt = RecoveryOption(
            option_id="opt-stop-proc",
            diagnosis_id="diag-proc",
            description="Terminate runaway process heavy_app.exe",
            stage=RecoveryStage.IRREVERSIBLE_MUTATION,
            safe_order_rank=6,
            action=AgentAction.STOP_PROCESS,
            parameters={"process_name": "heavy_app.exe"},
            expected_effect="Stop runaway process",
            risk_level=RiskLevel.HIGH,
            reversible=False,
            reversibility=ActionReversibility.NON_REVERSIBLE,
            requires_approval=True,
        )
        plan = self.planner.create_recovery_plan(opt)

        self.assertTrue(plan.approval_required)
        self.assertTrue(plan.transaction_required)
        self.assertEqual(plan.status, PlanStatus.AWAITING_APPROVAL)
        self.assertIn(plan.risk_level, (RiskLevel.HIGH, RiskLevel.MEDIUM))

    def test_recovery_plan_cannot_downgrade_risk(self) -> None:
        """Ensure PlanValidator and EVRiskEngine prevent recovery plans from downgrading risk."""
        opt = RecoveryOption(
            option_id="opt-delete",
            diagnosis_id="diag-del",
            description="Delete file from sandbox",
            stage=RecoveryStage.REVERSIBLE_MUTATION,
            safe_order_rank=5,
            action=AgentAction.DELETE_FILE,
            parameters={"path": "D:\\EV\\test.tmp"},
            risk_level=RiskLevel.NONE,  # Attempted downgrade!
            requires_approval=False,    # Attempted bypass!
        )
        plan = self.planner.create_recovery_plan(opt)

        # Risk engine must enforce authoritative risk (DELETE_FILE is at least MEDIUM/HIGH)
        self.assertNotEqual(plan.risk_level, RiskLevel.NONE)
        self.assertTrue(plan.approval_required)
        self.assertTrue(plan.transaction_required)


# =============================================================================
# 4. Security & Boundary Tests
# =============================================================================

class TestSafetyAndAuthorityBoundaries(unittest.TestCase):
    """Test non-negotiable safety rules: zero execution authority in recovery layer."""

    def test_diagnostic_engine_has_no_execution_methods(self) -> None:
        """EVDiagnosticEngine must possess ZERO execution methods."""
        engine = EVDiagnosticEngine()
        forbidden = ["execute", "run", "call", "kill", "terminate", "write", "delete", "dispatch"]
        for f in forbidden:
            self.assertFalse(hasattr(engine, f), f"EVDiagnosticEngine has forbidden method: {f}")

    def test_recovery_planner_has_no_execution_methods(self) -> None:
        """EVRecoveryPlanner must possess ZERO execution methods."""
        planner = EVRecoveryPlanner()
        forbidden = ["execute", "run", "call", "kill", "terminate", "write", "delete", "dispatch"]
        for f in forbidden:
            self.assertFalse(hasattr(planner, f), f"EVRecoveryPlanner has forbidden method: {f}")

    def test_eventbus_emits_diagnosis_and_recovery_events(self) -> None:
        """Verify structured events published on EVEventBus."""
        bus = EVEventBus()
        events_received: List[EVEvent] = []
        bus.subscribe(lambda e: events_received.append(e))

        engine = EVDiagnosticEngine(event_bus=bus)
        planner = EVRecoveryPlanner(event_bus=bus)

        alert = SystemAlert(
            alert_id="alert-test",
            domain=SystemMetricDomain.CPU,
            metric="cpu_percent",
            severity=SystemObservationSeverity.WARNING,
            message="CPU spike",
            value=88.0,
            threshold=80.0,
            triggered_at=datetime.now(timezone.utc),
            sustained_seconds=5.0,
            metadata={"highest_process": "worker.exe"},
        )
        diag = engine.diagnose_system_alert(alert)
        planner.generate_recovery_options(diag)

        event_types = [e.event_type for e in events_received]
        self.assertIn(EVEventType.DIAGNOSIS_CREATED, event_types)
        self.assertIn(EVEventType.RECOVERY_PROPOSED, event_types)
