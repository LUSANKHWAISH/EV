# Main GUI entry point for E.V.
# Bootstrap application and load QML root.
import argparse
import sys
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from core.events import EVEventBus
from core.models import EVState
from gui.bridge import GuiBridge
from gui.windows_chrome import install_windows_native_chrome


# Representative states cycled by the development-only visual demo.
# Observation only: no commands, no filesystem access, no system actions.
DEMO_STATE_SEQUENCE = (
    EVState.IDLE,
    EVState.LISTENING,
    EVState.PLANNING,
    EVState.AWAITING_APPROVAL,
    EVState.EXECUTING,
    EVState.VERIFYING,
    EVState.SUCCESS,
    EVState.SPEAKING,
    EVState.FAILED,
    EVState.RECOVERING,
)

# Slow, human-observable cadence for the development demo.
DEMO_INTERVAL_MS = 2000


def _parse_args(argv: list) -> argparse.Namespace:
    """Parse command line arguments.

    The representative state progression is enabled by default so the HUD
    visibly advances through the E.V. lifecycle on a normal launch. Pass
    --no-demo-states for a static window pinned to the initial state.
    """
    parser = argparse.ArgumentParser(
        prog="gui.app",
        description="E.V. - Enhanced Virtual Intelligence GUI",
    )
    parser.add_argument(
        "--demo-states",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Slowly cycle representative EVState values through the event "
            "bus so the GUI visibly progresses through the E.V. lifecycle "
            "(OBSERVE -> LISTEN -> PLAN -> APPROVAL -> EXECUTE -> VERIFY -> "
            "COMPLETE -> RESPOND). Enabled by default; use --no-demo-states "
            "for a static window pinned to the initial state. Performs no "
            "commands, filesystem, or system actions."
        ),
    )
    return parser.parse_args(argv)


def _start_state_demo(app: QGuiApplication, event_bus: EVEventBus) -> QTimer:
    """
    Development-only state demo.

    Publishes representative state changes via EVEventBus.set_state() only.
    Performs no command execution, no filesystem mutation, and no system actions.
    The timer is parented to `app` so it stays alive for the process lifetime.
    """
    index = {"value": 0}

    def advance() -> None:
        event_bus.set_state(DEMO_STATE_SEQUENCE[index["value"]])
        index["value"] = (index["value"] + 1) % len(DEMO_STATE_SEQUENCE)

    timer = QTimer(app)
    timer.setInterval(DEMO_INTERVAL_MS)
    timer.timeout.connect(advance)
    timer.start()
    return timer


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

    # Representative lifecycle state progression (enabled by default).
    # Drives the HUD through the E.V. lifecycle via EVEventBus.set_state()
    # only; --no-demo-states pins the window to the initial state.
    if args.demo_states:
        _start_state_demo(app, event_bus)

    app.aboutToQuit.connect(bridge.shutdown)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
