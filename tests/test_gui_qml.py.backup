"""Runtime tests for the E.V. Qt Quick/QML GUI foundation."""

import sys
from pathlib import Path

import pytest
from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine, QQmlComponent

from core.events import EVEventBus
from core.models import EVState
from gui.bridge import GuiBridge


PROJECT_ROOT = Path(__file__).resolve().parent.parent
QML_ROOT = PROJECT_ROOT / "gui" / "qml"
COMPONENT_ROOT = QML_ROOT / "components"


@pytest.fixture(scope="session")
def app():
    """Ensure one QGuiApplication exists for the test process."""
    instance = QGuiApplication.instance()
    if instance is None:
        instance = QGuiApplication(sys.argv[:1])
    return instance


@pytest.fixture
def qml_engine(app):
    """Create a real QML engine with E.V.'s real GUI bridge context."""
    engine = QQmlApplicationEngine()
    bus = EVEventBus(initial_state=EVState.IDLE)
    bridge = GuiBridge(bus)
    engine.rootContext().setContextProperty("guiBridge", bridge)

    try:
        yield engine
    finally:
        for root_object in engine.rootObjects():
            root_object.deleteLater()
        app.processEvents()

        engine.clearComponentCache()
        engine.deleteLater()
        app.processEvents()

        bridge.shutdown()


def _component_error_text(component):
    return "\n".join(error.toString() for error in component.errors())


def test_main_qml_creates_root_object(qml_engine):
    """Main.qml must load successfully using the real bridge context."""
    qml_file = QML_ROOT / "Main.qml"
    qml_engine.load(QUrl.fromLocalFile(str(qml_file)))

    roots = qml_engine.rootObjects()

    assert roots, "Main.qml failed to create a root object"


def test_qml_components_importable(qml_engine):
    """Load and instantiate every registered E.V. QML component.

    Failures are accumulated so one test run exposes the entire remaining
    QML defect set instead of stopping at the first broken component.
    """
    component_files = [
        "EVWindow.qml",
        "EVTopBar.qml",
        "EVStatusIndicator.qml",
        "EVCorePlaceholder.qml",
        "EVSurface.qml",
        "EVPanel.qml",
        "EVHairline.qml",
        "EVSectionLabel.qml",
        "EVStateBadge.qml",
        "EVButton.qml",
        "EVIconButton.qml",
        "EVSignalIndicator.qml",
    ]

    failures = []
    created_instances = []

    for filename in component_files:
        component_path = COMPONENT_ROOT / filename

        component = QQmlComponent(
            qml_engine,
            QUrl.fromLocalFile(str(component_path)),
        )

        if component.isError():
            errors = _component_error_text(component)
            failures.append(
                f"{filename} LOAD FAILURE:\n{errors}"
            )
            continue

        instance = component.create(qml_engine.rootContext())

        if instance is None:
            errors = _component_error_text(component)
            failures.append(
                f"{filename} CREATE FAILURE:\n"
                f"{errors or 'QQmlComponent.create() returned None'}"
            )
            continue

        created_instances.append(instance)

    # Some top-level QML Window objects may already have been destroyed
    # by Qt by the time cleanup runs. Their Python wrapper can therefore
    # remain while the underlying C++ object is gone.
    #
    # Cleanup must never turn successful component validation into a
    # false test failure.
    for instance in created_instances:
        try:
            instance.deleteLater()
        except RuntimeError:
            # Underlying Qt object was already destroyed.
            pass

    app = QGuiApplication.instance()
    if app is not None:
        app.processEvents()

    assert not failures, (
        "QML COMPONENT VALIDATION FAILED\n\n"
        + "\n\n".join(failures)
    )

def test_qmldir_registers_all_components():
    """The QML module manifest must expose every E.V. GUI component."""
    qmldir_path = COMPONENT_ROOT / "qmldir"

    expected = {
        "EVWindow 1.0 EVWindow.qml",
        "EVTopBar 1.0 EVTopBar.qml",
        "EVStatusIndicator 1.0 EVStatusIndicator.qml",
        "EVCorePlaceholder 1.0 EVCorePlaceholder.qml",
        "EVSurface 1.0 EVSurface.qml",
        "EVPanel 1.0 EVPanel.qml",
        "EVHairline 1.0 EVHairline.qml",
        "EVSectionLabel 1.0 EVSectionLabel.qml",
        "EVStateBadge 1.0 EVStateBadge.qml",
        "EVButton 1.0 EVButton.qml",
        "EVIconButton 1.0 EVIconButton.qml",
        "EVSignalIndicator 1.0 EVSignalIndicator.qml",
    }

    actual = {
        line.strip()
        for line in qmldir_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert actual == expected


def test_design_system_tokens_used():
    """Design-system components should consume Theme tokens."""
    component_files = [
        "EVSurface.qml",
        "EVPanel.qml",
        "EVHairline.qml",
        "EVSectionLabel.qml",
        "EVStateBadge.qml",
        "EVButton.qml",
        "EVIconButton.qml",
        "EVSignalIndicator.qml",
        "EVTopBar.qml",
        "EVWindow.qml",
        "EVStatusIndicator.qml",
        "EVCorePlaceholder.qml",
    ]

    for filename in component_files:
        content = (COMPONENT_ROOT / filename).read_text(encoding="utf-8")

        import_lines = {
            line.strip()
            for line in content.splitlines()
            if line.strip().startswith("import ")
        }

        assert 'import "../theme"' in import_lines, (
            f"{filename} must import the shared Theme module directly"
        )

        assert "Theme." in content, (
            f"{filename} must use at least one Theme token"
        )


def test_application_configures_basic_style():
    """The application must configure Basic controls style internally."""
    app_source = (PROJECT_ROOT / "gui" / "app.py").read_text(encoding="utf-8")

    assert "QQuickStyle.setStyle('Basic')" in app_source
