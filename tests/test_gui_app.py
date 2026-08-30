# Regression tests for the GUI launcher (gui/app.py) production wiring.
import argparse
import sys
from unittest.mock import patch, MagicMock

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QGuiApplication

from core.events import EVEventBus
from core.models import EVState
from core.orchestrator import EVOrchestrator
from gui.app import _parse_args, main
from gui.bridge import GuiBridge

# --- Argument parsing ------------------------------------------------------

def test_parse_args_returns_namespace():
    """Verify the CLI parser works and handles basic arguments."""
    args = _parse_args([])
    assert isinstance(args, argparse.Namespace)

def test_parse_args_accepts_help():
    """Verify --help is handled by argparse."""
    with pytest.raises(SystemExit):
        _parse_args(["--help"])

# --- Production Architecture Wiring ----------------------------------------

@pytest.fixture
def mock_gui_env():
    """Mock out the blocking Qt/GUI components for testing main()."""
    with patch("gui.app.QGuiApplication") as mock_app, \
         patch("gui.app.QQmlApplicationEngine") as mock_engine, \
         patch("gui.app.install_windows_native_chrome"), \
         patch("sys.exit") as mock_exit, \
         patch("sys.argv", ["gui.app"]):

        # Make app.exec() return 0 instead of blocking
        mock_app_instance = MagicMock()
        mock_app_instance.exec.return_value = 0
        mock_app.instance.return_value = mock_app_instance
        mock_app.return_value = mock_app_instance

        # Make engine.rootObjects() return a dummy window
        mock_engine_instance = MagicMock()
        mock_engine_instance.rootObjects.return_value = [MagicMock()]
        mock_engine.return_value = mock_engine_instance

        yield mock_app_instance, mock_engine_instance, mock_exit

def test_main_creates_shared_event_bus(mock_gui_env):
    """Verify main() creates exactly one EVEventBus and passes it to components."""
    mock_app, mock_engine, mock_exit = mock_gui_env

    with patch("gui.app.EVEventBus") as mock_bus_cls, \
         patch("gui.app.GuiBridge") as mock_bridge_cls, \
         patch("gui.app.EVOrchestrator") as mock_orch_cls:

        mock_bus_instance = MagicMock()
        mock_bus_cls.return_value = mock_bus_instance

        main()

        # Bus should be created once
        mock_bus_cls.assert_called_once_with(initial_state=EVState.IDLE)

        # Bridge should receive the exact same bus
        mock_bridge_cls.assert_called_once_with(mock_bus_instance)

        # Orchestrator should receive the exact same bus
        mock_orch_cls.assert_called_once_with(event_bus=mock_bus_instance)

def test_main_registers_bridge_with_qml(mock_gui_env):
    """Verify the GuiBridge is exposed to QML."""
    mock_app, mock_engine, mock_exit = mock_gui_env

    with patch("gui.app.GuiBridge") as mock_bridge_cls:
        mock_bridge_instance = MagicMock()
        mock_bridge_cls.return_value = mock_bridge_instance

        main()

        root_context = mock_engine.rootContext.return_value
        root_context.setContextProperty.assert_called_once_with("guiBridge", mock_bridge_instance)

def test_main_retains_orchestrator(mock_gui_env):
    """Verify the EVOrchestrator is kept alive by attaching it to the app."""
    mock_app, mock_engine, mock_exit = mock_gui_env

    with patch("gui.app.EVOrchestrator") as mock_orch_cls:
        mock_orch_instance = MagicMock()
        mock_orch_cls.return_value = mock_orch_instance

        main()

        # The app instance must retain the orchestrator to prevent garbage collection
        assert getattr(mock_app, "_ev_orchestrator") is mock_orch_instance

def test_main_executes_and_exits(mock_gui_env):
    """Verify main() calls app.exec() and exits with its return code."""
    mock_app, mock_engine, mock_exit = mock_gui_env
    mock_app.exec.return_value = 42

    main()

    mock_app.exec.assert_called_once()
    mock_exit.assert_called_once_with(42)
