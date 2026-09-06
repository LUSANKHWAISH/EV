"""
Tests for Human-in-the-Loop Approval GUI Surface (Task 018-C).

Verifies the presentation-only approval surface:
- Hidden by default
- Appears when approvalPending becomes true
- Correctly reflects action, description, resource, risk, reason, reversible, rollback
- Approve and Reject invoke canonical bridge submitApproval
- Duplicate clicks prevented while resolving
- Remains visible while resolution is pending
- Failed resolution does not silently disappear
- Stale approvals rejected
- STOP and Voice authority remain strictly decoupled
- Zero mutable backend authority objects exposed to QML
"""

import sys
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine, QQmlComponent
from PySide6.QtTest import QSignalSpy

from core.events import EVEventBus
from core.models import EVEventType, EVState
from gui.bridge import GuiBridge

PROJECT_ROOT = Path(__file__).resolve().parent.parent
QML_ROOT = PROJECT_ROOT / "gui" / "qml"
COMPONENT_ROOT = QML_ROOT / "components"


@pytest.fixture(scope="session")
def app():
    """Ensure one QGuiApplication exists for the test session."""
    instance = QGuiApplication.instance()
    if instance is None:
        instance = QGuiApplication(sys.argv[:1])
    return instance


@pytest.fixture
def approval_env(app):
    """Setup a real QML engine with bridge, event bus, and EVApprovalOverlay."""
    from PySide6.QtQuick import QQuickWindow
    event_bus = EVEventBus(initial_state=EVState.IDLE)
    bridge = GuiBridge(event_bus)
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("guiBridge", bridge)

    window = QQuickWindow()

    qml_file = COMPONENT_ROOT / "EVApprovalOverlay.qml"
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(qml_file)))
    if component.isError():
        errors = "\n".join(e.toString() for e in component.errors())
        pytest.fail(f"Failed to load EVApprovalOverlay.qml: {errors}")

    overlay = component.create()
    assert overlay is not None, "Failed to instantiate EVApprovalOverlay"
    overlay.setParentItem(window.contentItem())
    app.processEvents()

    try:
        yield event_bus, bridge, overlay, app
    finally:
        overlay.deleteLater()
        window.deleteLater()
        app.processEvents()
        engine.clearComponentCache()
        engine.deleteLater()
        app.processEvents()
        bridge.shutdown()


def test_approval_ui_hidden_by_default(approval_env):
    """Test 1: Approval UI is hidden by default when no approval is pending."""
    _, bridge, overlay, _ = approval_env
    assert bridge.approvalPending is False
    assert overlay.property("visible") is False
    assert overlay.property("isResolving") is False


def test_approval_ui_appears_when_pending(approval_env):
    """Test 2: Approval UI appears when approvalPending becomes True."""
    event_bus, bridge, overlay, app = approval_env

    event_bus.set_state(EVState.AWAITING_APPROVAL)
    event_bus.publish(
        event_type=EVEventType.APPROVAL_REQUIRED,
        source="action_pipeline",
        correlation_id="plan-001",
        data={
            "task_id": "plan-001",
            "action": "WRITE_FILE",
            "goal": "Update config file",
            "description": "Writes production settings",
            "resource": "C:\\config\\app.json",
            "risk_level": "HIGH",
            "reason": "Direct file modification",
            "reversible": True,
            "rollback_available": True,
        },
    )
    app.processEvents()

    assert bridge.approvalPending is True
    assert overlay.property("visible") is True


def test_approval_ui_displays_all_fields(approval_env):
    """Tests 3-9: Action, description, resource, risk, reason, reversible, and rollback displayed."""
    event_bus, bridge, overlay, app = approval_env

    event_bus.set_state(EVState.AWAITING_APPROVAL)
    event_bus.publish(
        event_type=EVEventType.APPROVAL_REQUIRED,
        source="action_pipeline",
        correlation_id="plan-002",
        data={
            "task_id": "plan-002",
            "action": "DELETE_DATABASE",
            "goal": "Drop table data",
            "description": "Irreversible table wipe",
            "resource": "postgres://localhost:5432/main",
            "risk_level": "CRITICAL",
            "reason": "Destructive drop database operation",
            "reversible": False,
            "rollback_available": False,
        },
    )
    app.processEvents()

    # Test 3: Action displayed
    assert overlay.property("actionName") == "DELETE_DATABASE"

    # Test 4: Description displayed
    assert overlay.property("descriptionText") == "Irreversible table wipe"

    # Test 5: Resource displayed
    assert overlay.property("resourcePath") == "postgres://localhost:5432/main"

    # Test 6: Risk displayed
    assert overlay.property("riskLevel") == "CRITICAL"

    # Test 7: Reason displayed
    assert overlay.property("reasonText") == "Destructive drop database operation"

    # Test 8: Reversible displayed
    assert overlay.property("reversible") is False

    # Test 9: Rollback availability displayed
    assert overlay.property("rollbackAvailable") is False


def test_approve_invokes_bridge_approval_path(approval_env):
    """Test 10: Approve button invokes canonical bridge.submitApproval with True."""
    event_bus, bridge, overlay, app = approval_env

    spy_submitted = QSignalSpy(bridge.approvalSubmitted)
    spy_resolving = QSignalSpy(bridge.approvalResolvingChanged)

    event_bus.set_state(EVState.AWAITING_APPROVAL)
    event_bus.publish(
        event_type=EVEventType.APPROVAL_REQUIRED,
        source="action_pipeline",
        correlation_id="plan-003",
        data={"task_id": "plan-003", "action": "MODIFY_FILE", "risk_level": "MEDIUM"},
    )
    app.processEvents()

    overlay.handleDecision(True)
    app.processEvents()

    assert spy_submitted.count() == 1
    assert spy_submitted.at(0) == ["plan-003", True]
    assert spy_resolving.count() >= 1


def test_reject_invokes_bridge_approval_path(approval_env):
    """Test 11: Reject button invokes canonical bridge.submitApproval with False."""
    event_bus, bridge, overlay, app = approval_env

    spy_submitted = QSignalSpy(bridge.approvalSubmitted)

    event_bus.set_state(EVState.AWAITING_APPROVAL)
    event_bus.publish(
        event_type=EVEventType.APPROVAL_REQUIRED,
        source="action_pipeline",
        correlation_id="plan-004",
        data={"task_id": "plan-004", "action": "EXECUTE_SCRIPT", "risk_level": "HIGH"},
    )
    app.processEvents()

    overlay.handleDecision(False)
    app.processEvents()

    assert spy_submitted.count() == 1
    assert spy_submitted.at(0) == ["plan-004", False]


def test_duplicate_clicks_prevented_while_resolving(approval_env):
    """Test 12: Duplicate clicks while resolving are ignored and do not emit duplicate signals."""
    event_bus, bridge, overlay, app = approval_env

    spy_submitted = QSignalSpy(bridge.approvalSubmitted)

    event_bus.set_state(EVState.AWAITING_APPROVAL)
    event_bus.publish(
        event_type=EVEventType.APPROVAL_REQUIRED,
        source="action_pipeline",
        correlation_id="plan-005",
        data={"task_id": "plan-005", "action": "START_SERVICE"},
    )
    app.processEvents()

    # First click
    overlay.handleDecision(True)
    app.processEvents()
    assert overlay.property("isResolving") is True
    assert spy_submitted.count() == 1

    # Second and third clicks should be guarded
    overlay.handleDecision(True)
    overlay.handleDecision(False)
    app.processEvents()

    assert spy_submitted.count() == 1, "Duplicate clicks must be ignored while resolving"


def test_approval_remains_visible_while_resolution_pending(approval_env):
    """Test 13: UI remains visible in resolving state until backend confirms resolution."""
    event_bus, bridge, overlay, app = approval_env

    event_bus.set_state(EVState.AWAITING_APPROVAL)
    event_bus.publish(
        event_type=EVEventType.APPROVAL_REQUIRED,
        source="action_pipeline",
        correlation_id="plan-006",
        data={"task_id": "plan-006", "action": "WRITE_FILE"},
    )
    app.processEvents()

    overlay.handleDecision(True)
    app.processEvents()

    # Even though submitApproval was called, because state is still AWAITING_APPROVAL
    # and isResolving is True, the overlay must remain visible!
    assert overlay.property("isResolving") is True
    assert overlay.property("visible") is True

    # Now backend confirms resolution by transitioning to EXECUTING
    event_bus.set_state(EVState.EXECUTING)
    app.processEvents()

    # After backend state transition, overlay clears
    assert overlay.property("visible") is False
    assert overlay.property("isResolving") is False


def test_failed_resolution_does_not_silently_clear_approval(approval_env):
    """Test 14: Failed resolution keeps dialog visible with error message."""
    event_bus, bridge, overlay, app = approval_env

    event_bus.set_state(EVState.AWAITING_APPROVAL)
    event_bus.publish(
        event_type=EVEventType.APPROVAL_REQUIRED,
        source="action_pipeline",
        correlation_id="plan-007",
        data={"task_id": "plan-007", "action": "DELETE_FILE"},
    )
    app.processEvents()

    overlay.handleDecision(True)
    app.processEvents()
    assert overlay.property("isResolving") is True

    # Backend reports resolution failure (e.g. secondary risk rejection)
    bridge.notifyApprovalFailed("plan-007", "Secondary risk evaluation failed.")
    app.processEvents()

    # UI must NOT silently disappear!
    assert overlay.property("visible") is True
    assert overlay.property("isResolving") is False
    assert "Secondary risk" in overlay.property("resolutionError")


def test_stale_approval_rejected(approval_env):
    """Test 15: Submitting approval for a stale/mismatched task ID is rejected."""
    event_bus, bridge, overlay, app = approval_env

    event_bus.set_state(EVState.AWAITING_APPROVAL)
    event_bus.publish(
        event_type=EVEventType.APPROVAL_REQUIRED,
        source="action_pipeline",
        correlation_id="plan-valid",
        data={"task_id": "plan-valid", "action": "WRITE_FILE"},
    )
    app.processEvents()

    spy_submitted = QSignalSpy(bridge.approvalSubmitted)

    # Directly attempt to submit mismatched ID
    bridge.submitApproval("plan-stale-bogus", True)
    app.processEvents()

    assert spy_submitted.count() == 0, "Mismatched approval must be rejected"


def test_stop_state_clears_approval_independently(approval_env):
    """Test 16: STOP command transition immediately clears approval presentation."""
    event_bus, bridge, overlay, app = approval_env

    event_bus.set_state(EVState.AWAITING_APPROVAL)
    event_bus.publish(
        event_type=EVEventType.APPROVAL_REQUIRED,
        source="action_pipeline",
        correlation_id="plan-008",
        data={"task_id": "plan-008", "action": "MUTATION"},
    )
    app.processEvents()
    assert overlay.property("visible") is True

    # System STOP triggered
    event_bus.set_state(EVState.STOPPED)
    app.processEvents()

    assert bridge.approvalPending is False
    assert overlay.property("visible") is False


def test_voice_activity_does_not_affect_approval_authority(approval_env):
    """Test 17: Voice state changes (e.g. LISTENING, SPEAKING) do not alter approval state."""
    event_bus, bridge, overlay, app = approval_env

    event_bus.set_state(EVState.AWAITING_APPROVAL)
    event_bus.publish(
        event_type=EVEventType.APPROVAL_REQUIRED,
        source="action_pipeline",
        correlation_id="plan-009",
        data={"task_id": "plan-009", "action": "SECURE_ACTION"},
    )
    app.processEvents()
    assert overlay.property("visible") is True
    assert bridge.approvalPending is True

    # Voice transitions
    event_bus.publish(
        event_type=EVEventType.VOICE_STATE_CHANGED,
        source="voice",
        data={"voice_state": "LISTENING"},
    )
    app.processEvents()
    assert bridge.approvalPending is True
    assert overlay.property("visible") is True

    event_bus.publish(
        event_type=EVEventType.VOICE_STATE_CHANGED,
        source="voice",
        data={"voice_state": "SPEAKING"},
    )
    app.processEvents()
    assert bridge.approvalPending is True
    assert overlay.property("visible") is True


def test_no_mutable_backend_objects_exposed_to_qml(approval_env):
    """Test 18: Verify zero mutable authority objects (Plan, RiskEngine, Agent) exposed."""
    _, bridge, overlay, _ = approval_env

    forbidden_attributes = [
        "plan", "plan_executor", "active_plan", "risk_engine",
        "agent", "compound_transaction", "subprocess", "powershell",
        "execute_plan", "bypass_risk"
    ]
    for attr in forbidden_attributes:
        assert overlay.property(attr) is None, f"Overlay must not expose {attr}"
        assert not hasattr(bridge, attr), f"Bridge must not expose {attr}"
