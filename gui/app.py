# Main GUI entry point for E.V.
# Bootstrap application and load QML root.
import argparse
import sys
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

import logging

from core.events import EVEventBus
from core.models import EVState
from core.orchestrator import EVOrchestrator

logger = logging.getLogger(__name__)
from gui.bridge import GuiBridge
from gui.windows_chrome import install_windows_native_chrome


def _parse_args(argv: list) -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="gui.app",
        description="E.V. - Enhanced Virtual Intelligence GUI",
    )
    return parser.parse_args(argv)


def main() -> None:
    """Main entry point for the GUI application."""
    args = _parse_args(sys.argv[1:])

    app = QGuiApplication.instance()
    if app is None:
        # Pass only the program name; CLI flags are handled by argparse above.
        app = QGuiApplication(sys.argv[:1])

    # Set Qt Quick Controls style to Basic before loading QML
    QQuickStyle.setStyle('Basic')

    engine = QQmlApplicationEngine()

    # Create event bus
    event_bus = EVEventBus(initial_state=EVState.IDLE)

    # Create bridge and register context property for QML
    bridge = GuiBridge(event_bus)
    engine.rootContext().setContextProperty("guiBridge", bridge)

    # Instantiate production backend orchestrator
    orchestrator = EVOrchestrator(event_bus=event_bus)

    def handle_task_submission(command: str) -> None:
        if not command.strip():
            return
        orchestrator.submit_command(command.strip())

    bridge.taskSubmitted.connect(handle_task_submission)

    # Load root QML
    qml_file = Path(__file__).parent / "qml" / "Main.qml"
    engine.load(QUrl.fromLocalFile(str(qml_file)))

    if not engine.rootObjects():
        sys.exit(-1)

    # Windows-only native chrome integration.
    #
    # The QML window remains visually frameless, while Windows receives
    # the native frame capabilities required for Aero Snap and normal
    # desktop window management.
    root_window = engine.rootObjects()[0]
    native_chrome = install_windows_native_chrome(app, root_window)

    # Keep the native event filter alive for the complete application
    # lifetime. QAbstractNativeEventFilter must not be garbage-collected.
    setattr(app, "_ev_windows_native_chrome", native_chrome)

    # Store orchestrator on app to prevent garbage collection and allow future access
    setattr(app, "_ev_orchestrator", orchestrator)

    app.aboutToQuit.connect(bridge.shutdown)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
