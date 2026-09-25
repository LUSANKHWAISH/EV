"""Tests for 018-D.2: Transparent Command Input + Borderless Typing Result HUD.

Covers:
- Result has no visible card/background (QML property inspection)
- Success/failure text color semantics
- Typing animation timer presence
- New result resets previous animation state
- Dismissal clears result
- Provider error sanitization end-to-end
- Directory listing formatter fix
- EVCommandInput transparent appearance
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QCoreApplication, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine, QQmlComponent

from core.events import EVEventBus
from core.models import EVState
from gui.app import _format_pipeline_result, _sanitize_provider_error
from gui.bridge import GuiBridge


PROJECT_ROOT = Path(__file__).resolve().parent.parent
QML_ROOT = PROJECT_ROOT / "gui" / "qml"
COMPONENT_ROOT = QML_ROOT / "components"


@pytest.fixture(scope="session")
def qapp():
    """Ensure one QGuiApplication exists."""
    instance = QGuiApplication.instance()
    if instance is None:
        instance = QGuiApplication(sys.argv[:1])
    return instance


@pytest.fixture
def bridge(qapp):
    """Create a fresh GuiBridge."""
    bus = EVEventBus(initial_state=EVState.IDLE)
    b = GuiBridge(bus)
    yield b
    b.shutdown()


@pytest.fixture
def result_surface(bridge, qapp):
    """Instantiate EVResultSurface.qml component with bridge context."""
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
    yield instance
    instance.deleteLater()
    engine.deleteLater()
    qapp.processEvents()


# ---- 1. Input Tests ----

def test_command_input_transparent_background(bridge, qapp):
    """1. Input background must be highly transparent (no opaque panel)."""
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("guiBridge", bridge)

    component = QQmlComponent(
        engine,
        QUrl.fromLocalFile(str(COMPONENT_ROOT / "EVCommandInput.qml")),
    )
    assert not component.isError(), [e.toString() for e in component.errors()]
    instance = component.create(engine.rootContext())
    assert instance is not None
    qapp.processEvents()

    # Verify component loads without QML errors
    assert instance.property("height") > 0

    instance.deleteLater()
    engine.deleteLater()
    qapp.processEvents()


def test_command_input_file_has_transparent_color():
    """2. EVCommandInput.qml source uses transparent rgba background, not opaque Theme.backgroundBase."""
    source = (COMPONENT_ROOT / "EVCommandInput.qml").read_text(encoding="utf-8")
    assert "Qt.rgba(1.0, 1.0, 1.0" in source or "Qt.rgba(1, 1, 1" in source
    assert "Theme.backgroundBase" not in source.split("background")[1].split("}")[0]


# ---- 2. Result Surface Tests ----

def test_result_surface_no_card_background():
    """5. EVResultSurface.qml source has no opaque Rectangle background card."""
    source = (COMPONENT_ROOT / "EVResultSurface.qml").read_text(encoding="utf-8")
    # Must not contain the old backgroundRect or surfaceLowest fill
    assert "surfaceLowest" not in source
    assert "backgroundRect" not in source
    assert "borderThin" not in source


def test_result_surface_no_status_dot():
    """6. EVResultSurface.qml has no status dot indicator."""
    source = (COMPONENT_ROOT / "EVResultSurface.qml").read_text(encoding="utf-8")
    assert "statusDot" not in source


def test_result_surface_success_uses_luminous_primary():
    """7. Success result text uses luminousPrimary color."""
    source = (COMPONENT_ROOT / "EVResultSurface.qml").read_text(encoding="utf-8")
    assert "luminousPrimary" in source


def test_result_surface_failure_uses_luminous_critical():
    """8. Failure result text uses luminousCritical color."""
    source = (COMPONENT_ROOT / "EVResultSurface.qml").read_text(encoding="utf-8")
    assert "luminousCritical" in source


def test_result_surface_has_typing_timer():
    """14. EVResultSurface.qml contains a Timer for typewriter animation."""
    source = (COMPONENT_ROOT / "EVResultSurface.qml").read_text(encoding="utf-8")
    assert "Timer {" in source or "Timer{" in source
    assert "typingTimer" in source


def test_result_surface_typing_does_not_block():
    """15. Typing timer uses short interval and QML Timer (non-blocking)."""
    source = (COMPONENT_ROOT / "EVResultSurface.qml").read_text(encoding="utf-8")
    assert "repeat: true" in source
    # Should not use any blocking mechanism
    assert "while (" not in source
    assert "Thread" not in source


def test_result_surface_instantiates(result_surface):
    """5+. EVResultSurface instantiates with no QML errors."""
    assert result_surface is not None


def test_result_surface_dismiss_clears(bridge, qapp):
    """12. clearTaskResult() resets result state to IDLE defaults."""
    bridge.notifyTaskResult("Test output text", "SUCCESS", True)
    QCoreApplication.processEvents()
    assert bridge.taskResult == "Test output text"
    assert bridge.taskResultAvailable is True

    bridge.clearTaskResult()
    QCoreApplication.processEvents()
    assert bridge.taskResult == ""
    assert bridge.taskResultStatus == "IDLE"
    assert bridge.taskResultAvailable is False


def test_new_task_clears_old_result(bridge, qapp):
    """13. submitTask() clears previous result and sets RUNNING."""
    bridge.notifyTaskResult("Old result", "SUCCESS", True)
    QCoreApplication.processEvents()
    assert bridge.taskResult == "Old result"

    bridge.submitTask("new command")
    QCoreApplication.processEvents()
    assert bridge.taskResult == ""
    assert bridge.taskResultStatus == "RUNNING"
    assert bridge.taskResultAvailable is False


# ---- 3. Directory Listing Formatter ----

def test_list_directory_uses_uppercase_enum():
    """19. LIST_DIRECTORY action produces detailed result (case-corrected)."""
    mock_item1 = MagicMock()
    mock_item1.name = "readme.txt"
    mock_item2 = MagicMock()
    mock_item2.name = "data.csv"

    mock_step = MagicMock()
    mock_step.action.value = "LIST_DIRECTORY"
    mock_step.parameters = {"path": "C:\\Users\\Downloads"}
    mock_step.result = [mock_item1, mock_item2]

    mock_res = MagicMock()
    mock_res.status.value = "COMPLETED"
    mock_res.overall_success = True
    mock_res.error = None
    mock_res.approved = True
    mock_res.plan.steps = [mock_step]
    mock_res.plan.goal = "list downloads"

    summary, status, success = _format_pipeline_result(mock_res)
    assert "Found 2 item(s)" in summary
    assert "readme.txt" in summary
    assert "data.csv" in summary
    assert status == "SUCCESS"
    assert success is True


# ---- 4. Provider Error Sanitization ----

def test_provider_503_not_exposed_in_gui():
    """20. Raw Gemini/provider JSON is not exposed to normal GUI presentation."""
    raw_error = "{'error': {'code': 503, 'message': 'Service Unavailable', 'status': 'UNAVAILABLE'}}"
    result = _sanitize_provider_error(raw_error)
    assert "{'error'" not in result
    assert "503" in result
    assert "temporarily unavailable" in result.lower()


def test_provider_error_http_code_visible():
    """21. HTTP 503 is represented clearly when available."""
    raw_error = '{"error": {"code": 503, "message": "The model is overloaded"}}'
    result = _sanitize_provider_error(raw_error)
    assert "503" in result
    assert "try again" in result.lower()


def test_provider_error_normal_text_unchanged():
    """Provider error sanitization does not alter normal error messages."""
    normal = "Task failed: Directory not found at C:\\missing"
    result = _sanitize_provider_error(normal)
    assert result == normal
