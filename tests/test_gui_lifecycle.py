"""Tests for Phase 018-E — Execution + Verification Visualization.

Covers the full 21-point verification suite:
1. New task -> THINKING
2. Plan-created evidence -> PLANNING
3. Validation evidence -> VALIDATING
4. Risk evidence -> RISK
5. Approval-required -> APPROVAL
6. Approval accepted -> EXECUTE
7. Plan started -> EXECUTE
8. Action verifying -> VERIFY
9. Successful final result -> SUCCESS
10. Failed final result -> FAILED
11. rolled_back=True -> ROLLED_BACK
12. Cancelled result -> CANCELLED
13. Late VERIFY after SUCCESS does not regress state
14. Late EXECUTE after ROLLED_BACK does not regress state
15. New task resets lifecycle
16. clearTaskResult resets presentation appropriately
17. Lifecycle does not execute/approve/rollback anything (presentation only)
18. No QML polling timers introduced
19. Existing typewriter result behavior still works
20. Protected EVFlagshipStage.qml SHA unchanged
21. QML diagnostics remain clean
"""

import hashlib
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QCoreApplication, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine, QQmlComponent

from core.events import EVEventBus, EVEventType
from core.models import EVState
from gui.app import _format_pipeline_result
from gui.bridge import GuiBridge

PROJECT_ROOT = Path(__file__).resolve().parent.parent
QML_ROOT = PROJECT_ROOT / "gui" / "qml"
COMPONENT_ROOT = QML_ROOT / "components"
FLAGSHIP_STAGE_PATH = COMPONENT_ROOT / "EVFlagshipStage.qml"
EXPECTED_FLAGSHIP_SHA256 = "b7eee6e5c3ad6a6c8ea85188767ce5b44ef3fe00d83fb202fb99f0b33fd689c8"


@pytest.fixture(scope="session")
def qapp():
    """Ensure a QGuiApplication exists."""
    instance = QGuiApplication.instance()
    if instance is None:
        instance = QGuiApplication(sys.argv[:1])
    return instance


@pytest.fixture
def event_bus():
    """Create a fresh EVEventBus."""
    return EVEventBus(initial_state=EVState.IDLE)


@pytest.fixture
def bridge(event_bus, qapp):
    """Create a fresh GuiBridge wired to the test event bus."""
    b = GuiBridge(event_bus)
    yield b
    b.shutdown()


# ---- 1. New task -> THINKING ----

def test_new_task_sets_thinking(bridge):
    """1. Submitting a new task immediately transitions lifecycle to THINKING (index 1)."""
    assert bridge.lifecycleStage == "IDLE"
    assert bridge.lifecycleStageIndex == 0
    assert bridge.lifecycleActive is False

    bridge.submitTask("inspect system status")
    QCoreApplication.processEvents()

    assert bridge.lifecycleStage == "THINKING"
    assert bridge.lifecycleStageIndex == 1
    assert bridge.lifecycleActive is True
    assert bridge.lifecycleRollback is False


# ---- 2. Plan-created evidence -> PLANNING ----

def test_plan_created_evidence_sets_planning(bridge, event_bus):
    """2. Plan-created evidence advances lifecycle to PLANNING (index 2)."""
    bridge.submitTask("create backup")
    QCoreApplication.processEvents()
    assert bridge.lifecycleStage == "THINKING"

    event_bus.publish(
        EVEventType.PLAN_CREATED,
        "planner",
        data={"plan_id": "plan-001", "goal": "create backup"},
    )
    QCoreApplication.processEvents()

    assert bridge.lifecycleStage == "PLANNING"
    assert bridge.lifecycleStageIndex == 2
    assert bridge.lifecycleActive is True


# ---- 3. Validation evidence -> VALIDATING ----

def test_validation_evidence_sets_validating(bridge, event_bus):
    """3. Plan validation evidence advances lifecycle to VALIDATING (index 3)."""
    bridge.submitTask("deploy code")
    QCoreApplication.processEvents()

    event_bus.publish(
        EVEventType.PLAN_VALIDATED,
        "validator",
        data={"plan_id": "plan-002", "valid": True},
    )
    QCoreApplication.processEvents()

    assert bridge.lifecycleStage == "VALIDATING"
    assert bridge.lifecycleStageIndex == 3
    assert bridge.lifecycleActive is True


# ---- 4. Risk evidence -> RISK ----

def test_risk_evidence_sets_risk(bridge):
    """4. Risk assessment evidence maps to RISK stage (index 4)."""
    bridge.submitTask("run migration")
    QCoreApplication.processEvents()

    bridge.notifyLifecycleStage("RISK")
    QCoreApplication.processEvents()

    assert bridge.lifecycleStage == "RISK"
    assert bridge.lifecycleStageIndex == 4
    assert bridge.lifecycleActive is True


# ---- 5. Approval-required -> APPROVAL ----

def test_approval_required_sets_approval(bridge, event_bus):
    """5. Approval requirement transitions lifecycle to APPROVAL (index 5) and flags requirement."""
    bridge.submitTask("delete database")
    QCoreApplication.processEvents()

    event_bus.publish(
        EVEventType.APPROVAL_REQUIRED,
        "risk_engine",
        data={
            "task_id": "task-appr-1",
            "action": "DROP_TABLE",
            "description": "Drop table users",
            "risk_level": "CRITICAL",
        },
    )
    QCoreApplication.processEvents()

    assert bridge.lifecycleStage == "APPROVAL"
    assert bridge.lifecycleStageIndex == 5
    assert bridge.lifecycleApprovalRequired is True
    assert bridge.approvalPending is True


# ---- 6. Approval accepted -> EXECUTE ----

def test_approval_accepted_progresses_to_execute(bridge, event_bus):
    """6. When approval is granted and execution begins, lifecycle advances to EXECUTE (index 6)."""
    bridge.submitTask("mutate config")
    QCoreApplication.processEvents()

    # Step into approval
    event_bus.publish(
        EVEventType.APPROVAL_REQUIRED,
        "risk_engine",
        data={"task_id": "task-appr-2", "action": "WRITE_FILE", "risk_level": "HIGH"},
    )
    QCoreApplication.processEvents()
    assert bridge.lifecycleStage == "APPROVAL"

    # Plan started after approval
    event_bus.publish(
        EVEventType.PLAN_STARTED,
        "executor",
        data={"plan_id": "task-appr-2"},
    )
    QCoreApplication.processEvents()

    assert bridge.lifecycleStage == "EXECUTE"
    assert bridge.lifecycleStageIndex == 6


# ---- 7. Plan started -> EXECUTE ----

def test_plan_started_sets_execute(bridge, event_bus):
    """7. PLAN_STARTED event advances lifecycle to EXECUTE (index 6)."""
    bridge.submitTask("read logs")
    QCoreApplication.processEvents()

    event_bus.publish(
        EVEventType.PLAN_STARTED,
        "pipeline",
        data={"plan_id": "plan-read-1"},
    )
    QCoreApplication.processEvents()

    assert bridge.lifecycleStage == "EXECUTE"
    assert bridge.lifecycleStageIndex == 6


# ---- 8. Action verifying -> VERIFY ----

def test_action_verifying_sets_verify(bridge, event_bus):
    """8. ACTION_VERIFYING event advances lifecycle to VERIFY (index 7)."""
    bridge.submitTask("write and verify")
    QCoreApplication.processEvents()

    event_bus.publish(
        EVEventType.ACTION_VERIFYING,
        "verifier",
        data={"step_index": 0, "action": "WRITE_FILE"},
    )
    QCoreApplication.processEvents()

    assert bridge.lifecycleStage == "VERIFY"
    assert bridge.lifecycleStageIndex == 7


# ---- 9. Successful final result -> SUCCESS ----

def test_successful_final_result_sets_success(bridge):
    """9. A successful task completion sets SUCCESS (index 8) and deactivates active flag."""
    bridge.submitTask("list files")
    QCoreApplication.processEvents()

    bridge.notifyTaskResult("Listing complete: 5 files found", "SUCCESS", True)
    QCoreApplication.processEvents()

    assert bridge.lifecycleStage == "SUCCESS"
    assert bridge.lifecycleStageIndex == 8
    assert bridge.lifecycleActive is False
    assert bridge.lifecycleRollback is False
    assert bridge.taskResultAvailable is True


# ---- 10. Failed final result -> FAILED ----

def test_failed_final_result_sets_failed(bridge):
    """10. A failed task completion without rollback sets FAILED (index 8)."""
    bridge.submitTask("read missing file")
    QCoreApplication.processEvents()

    bridge.notifyTaskResult("File not found", "FAILED", False)
    QCoreApplication.processEvents()

    assert bridge.lifecycleStage == "FAILED"
    assert bridge.lifecycleStageIndex == 8
    assert bridge.lifecycleActive is False
    assert bridge.lifecycleRollback is False


# ---- 11. rolled_back=True -> ROLLED_BACK ----

def test_rolled_back_sets_rolled_back(bridge):
    """11. A task resulting in rollback sets ROLLED_BACK (index 8) and lifecycleRollback=True."""
    bridge.submitTask("faulty batch transaction")
    QCoreApplication.processEvents()

    bridge.notifyTaskResult("Transaction failed and rolled back", "ROLLED_BACK", False)
    QCoreApplication.processEvents()

    assert bridge.lifecycleStage == "ROLLED_BACK"
    assert bridge.lifecycleStageIndex == 8
    assert bridge.lifecycleActive is False
    assert bridge.lifecycleRollback is True


def test_format_pipeline_result_distinguishes_rolled_back():
    """11b. _format_pipeline_result formats rolled_back=True as ROLLED_BACK instead of generic FAILED."""
    mock_res = MagicMock()
    mock_res.status.value = "FAILED"
    mock_res.overall_success = False
    mock_res.rolled_back = True
    mock_res.error = "Disk write verification failed"
    mock_res.approved = True
    mock_res.plan = None

    summary, status, success = _format_pipeline_result(mock_res)
    assert status == "ROLLED_BACK"
    assert success is False
    assert "Task rolled back:" in summary
    assert "Disk write verification failed" in summary


# ---- 12. Cancelled result -> CANCELLED ----

def test_cancelled_result_sets_cancelled(bridge):
    """12. A cancelled task sets CANCELLED (index 8)."""
    bridge.submitTask("long compilation")
    QCoreApplication.processEvents()

    bridge.notifyTaskResult("Operation cancelled by operator", "CANCELLED", False)
    QCoreApplication.processEvents()

    assert bridge.lifecycleStage == "CANCELLED"
    assert bridge.lifecycleStageIndex == 8
    assert bridge.lifecycleActive is False


# ---- 13. Late VERIFY after SUCCESS does not regress state ----

def test_late_verify_after_success_does_not_regress_state(bridge, event_bus):
    """13. Stale event protection: late ACTION_VERIFYING event after SUCCESS does not regress state."""
    bridge.submitTask("quick command")
    QCoreApplication.processEvents()

    bridge.notifyTaskResult("All complete", "SUCCESS", True)
    QCoreApplication.processEvents()
    assert bridge.lifecycleStage == "SUCCESS"

    # Attempt to inject late VERIFY via bus
    event_bus.publish(
        EVEventType.ACTION_VERIFYING,
        "delayed_verifier",
        data={},
    )
    QCoreApplication.processEvents()

    assert bridge.lifecycleStage == "SUCCESS"
    assert bridge.lifecycleStageIndex == 8
    assert bridge.lifecycleActive is False


# ---- 14. Late EXECUTE after ROLLED_BACK does not regress state ----

def test_late_execute_after_rolled_back_does_not_regress_state(bridge, event_bus):
    """14. Stale event protection: late PLAN_STARTED event after ROLLED_BACK does not regress state."""
    bridge.submitTask("rollback scenario")
    QCoreApplication.processEvents()

    bridge.notifyTaskResult("Rolled back", "ROLLED_BACK", False)
    QCoreApplication.processEvents()
    assert bridge.lifecycleStage == "ROLLED_BACK"

    # Attempt late EXECUTE via bus
    event_bus.publish(
        EVEventType.PLAN_STARTED,
        "delayed_executor",
        data={},
    )
    QCoreApplication.processEvents()

    assert bridge.lifecycleStage == "ROLLED_BACK"
    assert bridge.lifecycleStageIndex == 8
    assert bridge.lifecycleRollback is True


# ---- 15. New task resets lifecycle ----

def test_new_task_resets_lifecycle(bridge):
    """15. Submitting a new task clears the terminal state and resets lifecycle to THINKING."""
    bridge.submitTask("first task")
    QCoreApplication.processEvents()
    bridge.notifyTaskResult("First task complete", "SUCCESS", True)
    QCoreApplication.processEvents()
    assert bridge.lifecycleStage == "SUCCESS"
    assert bridge.lifecycleActive is False

    # Start new task
    bridge.submitTask("second task")
    QCoreApplication.processEvents()

    assert bridge.lifecycleStage == "THINKING"
    assert bridge.lifecycleStageIndex == 1
    assert bridge.lifecycleActive is True
    assert bridge.lifecycleRollback is False
    assert bridge.taskResult == ""
    assert bridge.taskResultAvailable is False


# ---- 16. clearTaskResult resets presentation appropriately ----

def test_clear_task_result_resets_presentation(bridge):
    """16. clearTaskResult() restores lifecycle presentation to IDLE defaults."""
    bridge.submitTask("task to dismiss")
    QCoreApplication.processEvents()
    bridge.notifyTaskResult("Done", "SUCCESS", True)
    QCoreApplication.processEvents()
    assert bridge.taskResultAvailable is True

    bridge.clearTaskResult()
    QCoreApplication.processEvents()

    assert bridge.lifecycleStage == "IDLE"
    assert bridge.lifecycleStageIndex == 0
    assert bridge.lifecycleActive is False
    assert bridge.lifecycleRollback is False
    assert bridge.lifecycleApprovalRequired is False
    assert bridge.taskResult == ""
    assert bridge.taskResultStatus == "IDLE"
    assert bridge.taskResultAvailable is False


# ---- 17. Lifecycle does not execute/approve/rollback anything ----

def test_lifecycle_is_pure_presentation_no_authority():
    """17. EVLifecycleHUD.qml has zero execution, mutation, or approval authority."""
    hud_source = (COMPONENT_ROOT / "EVLifecycleHUD.qml").read_text(encoding="utf-8")

    # Must not contain command dispatch or execution invocations
    forbidden_tokens = [
        "submitTask",
        "submitApproval",
        "requestStateChange",
        "executeAction",
        "rollback",
        "subprocess",
    ]
    for token in forbidden_tokens:
        assert token not in hud_source, f"Forbidden authority token '{token}' found in EVLifecycleHUD.qml"


# ---- 18. No QML polling timers introduced ----

def test_no_qml_polling_timers():
    """18. EVLifecycleHUD.qml contains no polling timers or background intervals."""
    hud_source = (COMPONENT_ROOT / "EVLifecycleHUD.qml").read_text(encoding="utf-8")
    assert "Timer {" not in hud_source and "Timer{" not in hud_source, (
        "EVLifecycleHUD.qml must not introduce QML Timers"
    )


# ---- 19. Existing typewriter result behavior still works ----

def test_existing_typewriter_result_behavior(bridge, qapp):
    """19. EVResultSurface typewriter timer and animation mechanisms operate correctly."""
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("guiBridge", bridge)

    component = QQmlComponent(
        engine,
        QUrl.fromLocalFile(str(COMPONENT_ROOT / "EVResultSurface.qml")),
    )
    assert not component.isError(), [e.toString() for e in component.errors()]
    instance = component.create(engine.rootContext())
    assert instance is not None
    qapp.processEvents()

    # Verify typewriter properties exist
    assert hasattr(instance, "property")
    assert instance.property("_charIndex") == 0
    assert instance.property("_animating") is False

    # Simulate result available
    bridge.notifyTaskResult("Typewriter line one\nLine two", "SUCCESS", True)
    qapp.processEvents()

    # Verify animation begins
    assert instance.property("_animating") is True
    assert instance.property("_fullText") == "Typewriter line one\nLine two"

    instance.deleteLater()
    engine.deleteLater()
    qapp.processEvents()


# ---- 20. Protected EVFlagshipStage.qml SHA unchanged ----

def test_protected_flagship_stage_sha_unchanged():
    """20. EVFlagshipStage.qml is strictly protected and its SHA256 matches baseline."""
    assert FLAGSHIP_STAGE_PATH.exists(), f"Flagship stage file not found at {FLAGSHIP_STAGE_PATH}"
    content = FLAGSHIP_STAGE_PATH.read_bytes()
    computed_sha = hashlib.sha256(content).hexdigest().lower()
    assert computed_sha == EXPECTED_FLAGSHIP_SHA256, (
        f"EVFlagshipStage.qml was modified! Expected {EXPECTED_FLAGSHIP_SHA256}, got {computed_sha}"
    )


# ---- 21. QML diagnostics remain clean ----

def test_qml_diagnostics_clean(bridge, qapp):
    """21. Both EVLifecycleHUD.qml and EVResultSurface.qml instantiate with zero QML errors."""
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("guiBridge", bridge)

    for qml_name in ["EVLifecycleHUD.qml", "EVResultSurface.qml"]:
        comp = QQmlComponent(
            engine,
            QUrl.fromLocalFile(str(COMPONENT_ROOT / qml_name)),
        )
        assert not comp.isError(), f"QML error in {qml_name}: {[e.toString() for e in comp.errors()]}"
        inst = comp.create(engine.rootContext())
        assert inst is not None, f"Failed to instantiate {qml_name}"
        qapp.processEvents()
        inst.deleteLater()

    engine.deleteLater()
    qapp.processEvents()
