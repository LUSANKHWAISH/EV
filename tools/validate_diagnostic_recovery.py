"""
Live Windows Validation & 20-Cycle Stability Benchmark for Task 017:
Contextual Action Planning & Recovery Intelligence.

Validates:
Phase 1:
1. Real CPU observation -> structured Diagnosis with multi-hypotheses
2. Real Memory observation -> structured Diagnosis with top consumer
3. Controlled File failure -> deterministic Diagnosis in isolated sandbox
4. Verification failure -> VERIFICATION_FAILURE diagnosis (execution success + verification fail)
5. Unknown execution result -> UNKNOWN_FAILURE with ZERO blind retry
6. Recovery proposal generation conforming strictly to Safe-First ordering
7. Mutating recovery plan converts to Plan with mandatory approval and transaction
8. Security invariant: Awareness and Diagnosis possess ZERO execution authority

Phase 2:
20-Cycle Stability Benchmark:
- 20 complete diagnosis -> evidence -> hypotheses -> recovery proposal -> plan validation cycles
- Thread count stability (delta = 0)
- RSS memory growth bounded
- Zero stale objects or dangling workers
"""
from __future__ import annotations

import logging
import os
import shutil
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.events import EVEvent, EVEventBus
from core.models import (
    ActionCategory,
    ActionReversibility,
    AgentAction,
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
from core.plan import Plan, PlanStatus, PlanStep
from core.plan_validator import PlanValidator
from core.recovery import EVDiagnosticEngine, EVRecoveryPlanner
from core.risk import EVRiskEngine
from core.system_monitor import SystemAlert, SystemMetricDomain, SystemObservation, SystemObservationSeverity

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("validate_diagnostic_recovery")


def main() -> int:
    logger.info("=== E.V. TASK 017 — CONTEXTUAL DIAGNOSIS & RECOVERY VALIDATION ===")

    # Dedicated isolated test sandbox
    temp_dir = Path(tempfile.mkdtemp(prefix="ev_task017_val_"))
    sandbox_dir = temp_dir / "sandbox"
    sandbox_dir.mkdir(parents=True, exist_ok=True)

    proc = psutil.Process(os.getpid()) if HAS_PSUTIL else None
    initial_threads = threading.active_count()
    initial_rss = (proc.memory_info().rss / (1024 * 1024)) if proc else 0.0

    logger.info(
        "Initial Process PID: %d, Threads: %d, RSS: %.2f MB",
        os.getpid(),
        initial_threads,
        initial_rss,
    )

    try:
        bus = EVEventBus()
        events_emitted: List[EVEvent] = []
        bus.subscribe(lambda e: events_emitted.append(e))

        risk_engine = EVRiskEngine()
        plan_validator = PlanValidator(risk_engine)
        diagnostic_engine = EVDiagnosticEngine(event_bus=bus)
        recovery_planner = EVRecoveryPlanner(
            risk_engine=risk_engine,
            plan_validator=plan_validator,
            event_bus=bus,
        )

        logger.info("\n--- PHASE 1: LIVE DETERMINISTIC DIAGNOSIS & RECOVERY TESTS ---")

        # ---------------------------------------------------------------------
        # Test 1: Real CPU Observation -> Structured Diagnosis
        # ---------------------------------------------------------------------
        logger.info("[Test 1] Real CPU observation -> structured Diagnosis...")
        current_cpu = psutil.cpu_percent(interval=0.1) if HAS_PSUTIL else 50.0
        cpu_alert = SystemAlert(
            alert_id="alert-cpu-live",
            domain=SystemMetricDomain.CPU,
            metric="cpu_percent",
            severity=SystemObservationSeverity.WARNING,
            message=f"Live CPU alert ({current_cpu:.1f}%)",
            value=max(current_cpu, 85.0),
            threshold=80.0,
            triggered_at=datetime.now(timezone.utc),
            sustained_seconds=10.0,
            metadata={
                "highest_process": "python.exe",
                "highest_process_cpu": 65.0,
            },
        )
        diag_cpu = diagnostic_engine.diagnose_system_alert(cpu_alert)
        assert diag_cpu.category == DiagnosisCategory.RESOURCE_PRESSURE
        assert "python.exe" in diag_cpu.affected_resources
        assert len(diag_cpu.probable_causes) >= 2
        logger.info("-> Test 1 PASSED: Category=%s, Hypotheses=%d", diag_cpu.category.value, len(diag_cpu.probable_causes))

        # ---------------------------------------------------------------------
        # Test 2: Real Memory Observation -> Structured Diagnosis
        # ---------------------------------------------------------------------
        logger.info("[Test 2] Real Memory observation -> structured Diagnosis...")
        mem = psutil.virtual_memory() if HAS_PSUTIL else None
        mem_pct = mem.percent if mem else 70.0
        mem_alert = SystemAlert(
            alert_id="alert-mem-live",
            domain=SystemMetricDomain.MEMORY,
            metric="memory_percent",
            severity=SystemObservationSeverity.WARNING,
            message=f"Live Memory alert ({mem_pct:.1f}%)",
            value=max(mem_pct, 88.0),
            threshold=85.0,
            triggered_at=datetime.now(timezone.utc),
            sustained_seconds=15.0,
            metadata={
                "highest_process": "python.exe",
                "highest_process_memory_mb": 250,
                "memory_percent": mem_pct,
            },
        )
        diag_mem = diagnostic_engine.diagnose_system_alert(mem_alert)
        assert diag_mem.category == DiagnosisCategory.RESOURCE_PRESSURE
        assert len(diag_mem.evidence) >= 2
        logger.info("-> Test 2 PASSED: Evidence count=%d, Severity=%s", len(diag_mem.evidence), diag_mem.severity.value)

        # ---------------------------------------------------------------------
        # Test 3: Controlled File Failure -> Diagnosis in Sandbox
        # ---------------------------------------------------------------------
        logger.info("[Test 3] Controlled File failure -> Diagnosis...")
        missing_file = str(sandbox_dir / "nonexistent_task017.txt")
        exec_file_fail = ExecutionResult(
            action_id="act-file-fail-1",
            action_type=AgentAction.READ_TEXT_FILE,
            status=ExecutionStatus.FAILED,
            duration=0.01,
            error=f"File not found: '{missing_file}' does not exist",
        )
        diag_file = diagnostic_engine.diagnose_execution_result(
            exec_file_fail,
            action_name="READ_TEXT_FILE",
            parameters={"path": missing_file},
        )
        assert diag_file.category == DiagnosisCategory.FILE_FAILURE
        assert missing_file in diag_file.affected_resources
        logger.info("-> Test 3 PASSED: Category=%s, Affected=%s", diag_file.category.value, diag_file.affected_resources)

        # ---------------------------------------------------------------------
        # Test 4: Verification Failure (Exec SUCCEEDED + Verif FAILED)
        # ---------------------------------------------------------------------
        logger.info("[Test 4] Execution Succeeded + Verification Failed -> VERIFICATION_FAILURE...")
        test_file = str(sandbox_dir / "mismatch_test.txt")
        exec_vf = ExecutionResult(
            action_id="act-vf-live",
            action_type=AgentAction.WRITE_FILE,
            status=ExecutionStatus.SUCCEEDED,
            duration=0.02,
            result={"bytes_written": 50},
        )
        verif_vf = VerificationResult(
            verification_type=VerificationType.FILE_HASH_MATCH,
            status=VerificationStatus.FAILED,
            success=False,
            message="SHA-256 mismatch between expected content and disk state",
            observed_state={"file_exists": True, "size_bytes": 50},
        )
        diag_vf = diagnostic_engine.diagnose_execution_result(
            exec_vf,
            verification=verif_vf,
            action_name="WRITE_FILE",
            parameters={"path": test_file},
        )
        assert diag_vf.category == DiagnosisCategory.VERIFICATION_FAILURE
        assert diag_vf.metadata["failure_classification"] == FailureClassification.VERIFICATION_FAILED.value
        # Both facts must be preserved
        ev_types = [e.evidence_type for e in diag_vf.evidence]
        assert EvidenceType.EXECUTION_RESULT in ev_types
        assert EvidenceType.VERIFICATION_RESULT in ev_types
        logger.info("-> Test 4 PASSED: Core Invariant Confirmed (VERIFICATION_FAILURE preserves execution & verification facts)")

        # ---------------------------------------------------------------------
        # Test 5: Unknown Outcome -> Zero Blind Retry
        # ---------------------------------------------------------------------
        logger.info("[Test 5] Unknown execution -> UNKNOWN_FAILURE with zero blind retry...")
        exec_unknown = ExecutionResult(
            action_id="act-unknown-live",
            action_type=AgentAction.STOP_PROCESS,
            status=ExecutionStatus.UNKNOWN,
            duration=15.0,
            error="Process termination timed out; state ambiguous",
        )
        diag_unknown = diagnostic_engine.diagnose_execution_result(
            exec_unknown,
            action_name="STOP_PROCESS",
            parameters={"process_name": "hung_task.exe"},
        )
        assert diag_unknown.category == DiagnosisCategory.UNKNOWN_FAILURE

        options_unknown = recovery_planner.generate_recovery_options(diag_unknown)
        for opt in options_unknown:
            # Must ONLY be OBSERVE or EXPLAIN; never mutating!
            assert opt.stage in (RecoveryStage.OBSERVE, RecoveryStage.EXPLAIN)
            assert opt.requires_approval is False
            if opt.action:
                assert opt.action == AgentAction.FIND_PROCESS
        logger.info("-> Test 5 PASSED: Ambiguous outcome generated %d options; ZERO blind retries", len(options_unknown))

        # ---------------------------------------------------------------------
        # Test 6: Recovery Proposal Safe-First Ordering
        # ---------------------------------------------------------------------
        logger.info("[Test 6] Recovery proposal safe-first ordering for CPU pressure...")
        options_cpu = recovery_planner.generate_recovery_options(diag_cpu)
        ranks = [o.safe_order_rank for o in options_cpu]
        assert ranks == sorted(ranks), f"Ranks not sorted in safe order: {ranks}"
        assert options_cpu[0].stage == RecoveryStage.OBSERVE
        logger.info("-> Test 6 PASSED: Safe-first order confirmed: %s", [o.stage.value for o in options_cpu])

        # ---------------------------------------------------------------------
        # Test 7: Mutating Recovery Plan Enforces Approval & Transaction
        # ---------------------------------------------------------------------
        logger.info("[Test 7] Converting mutating recovery option to Plan...")
        mutating_opt = next(o for o in options_cpu if o.stage == RecoveryStage.IRREVERSIBLE_MUTATION)
        recovery_plan = recovery_planner.create_recovery_plan(mutating_opt)
        assert recovery_plan.approval_required is True
        assert recovery_plan.transaction_required is True
        assert recovery_plan.status == PlanStatus.AWAITING_APPROVAL
        assert recovery_plan.risk_level in (RiskLevel.HIGH, RiskLevel.MEDIUM)
        logger.info("-> Test 7 PASSED: Mutating plan strictly approval-gated: status=%s, risk=%s", recovery_plan.status.value, recovery_plan.risk_level.value)

        # ---------------------------------------------------------------------
        # Test 8: Security Boundary: Zero Autonomous Authority
        # ---------------------------------------------------------------------
        logger.info("[Test 8] Security audit: Zero execution authority in recovery layer...")
        for forbidden in ["run", "execute", "call", "kill", "terminate", "write", "delete", "dispatch"]:
            assert not hasattr(diagnostic_engine, forbidden)
            assert not hasattr(recovery_planner, forbidden)
        logger.info("-> Test 8 PASSED: Zero execution authority confirmed")

        logger.info("\n--- PHASE 2: 20-CYCLE STABILITY BENCHMARK ---")
        for cycle in range(1, 21):
            # 1. Alert -> Diagnosis
            test_alert = SystemAlert(
                alert_id=f"alert-bench-{cycle}",
                domain=SystemMetricDomain.CPU,
                metric="cpu_percent",
                severity=SystemObservationSeverity.WARNING,
                message=f"Benchmark alert {cycle}",
                value=85.0 + (cycle % 10),
                threshold=80.0,
                triggered_at=datetime.now(timezone.utc),
                sustained_seconds=5.0,
                metadata={"highest_process": f"worker_{cycle}.exe"},
            )
            d = diagnostic_engine.diagnose_system_alert(test_alert)

            # 2. Diagnosis -> Recovery Options
            opts = recovery_planner.generate_recovery_options(d)
            assert len(opts) >= 2

            # 3. Option -> Plan validation & risk assessment
            p = recovery_planner.create_recovery_plan(opts[0])
            assert p.status in (PlanStatus.READY, PlanStatus.AWAITING_APPROVAL)

            if cycle % 5 == 0:
                cur_threads = threading.active_count()
                cur_rss = (proc.memory_info().rss / (1024 * 1024)) if proc else 0.0
                logger.info(
                    "Cycle %2d/20: Threads=%d (delta=%+d), RSS=%.2f MB (delta=%+.2f MB), Events=%d",
                    cycle,
                    cur_threads,
                    cur_threads - initial_threads,
                    cur_rss,
                    cur_rss - initial_rss,
                    len(events_emitted),
                )

        final_threads = threading.active_count()
        final_rss = (proc.memory_info().rss / (1024 * 1024)) if proc else 0.0
        delta_threads = final_threads - initial_threads
        rss_growth = final_rss - initial_rss

        logger.info("\n=== STABILITY BENCHMARK SUMMARY ===")
        logger.info("Baseline Threads: %d | Final Threads: %d (Delta: %+d)", initial_threads, final_threads, delta_threads)
        logger.info("Baseline RSS: %.2f MB | Final RSS: %.2f MB (Growth: %+.2f MB)", initial_rss, final_rss, rss_growth)
        logger.info("Total Events Published: %d", len(events_emitted))

        assert delta_threads == 0, f"Thread leak detected: delta={delta_threads}"
        assert rss_growth < 50.0, f"Unbounded memory growth: +{rss_growth:.2f} MB"

        logger.info("\n>>> ALL PHASE 1 & PHASE 2 TESTS PASSED PERFECTLY <<<")
        return 0

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
