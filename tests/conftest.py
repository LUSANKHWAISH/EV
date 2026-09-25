"""Root test configuration and deterministic offscreen Qt application setup."""
import os
import pytest
from PySide6.QtGui import QGuiApplication

# Ensure headless/offscreen flags for deterministic execution across entire test suite
os.environ.setdefault("EV_STARTUP_AUDIO", "false")
os.environ.setdefault("QSG_RENDER_LOOP", "basic")
os.environ.setdefault("QML_DISABLE_DISK_CACHE", "1")
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")


@pytest.fixture(scope="session", autouse=True)
def qapp():
    """Ensure a single offscreen QGuiApplication exists for the entire test session."""
    app = QGuiApplication.instance()
    if app is None:
        app = QGuiApplication(["pytest", "-platform", "offscreen"])
    yield app
