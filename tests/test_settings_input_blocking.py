"""Regression test: settings overlay blocks underlying stage input.

Verifies that while the EVSettingsOverlay is open the CinematicStage is
disabled, preventing underlying controls (e.g. musicButton) from receiving
clicks.  Once settings close, the stage must re-enable and controls must
work normally.

Adapted from scratch/diagnose_settings_input.py with bounded waits and
deterministic cleanup suitable for CI / pytest.
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path

import pytest

os.environ.setdefault("EV_STARTUP_AUDIO", "false")
os.environ.setdefault("QSG_RENDER_LOOP", "basic")
os.environ.setdefault("QML_DISABLE_DISK_CACHE", "1")
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

from PySide6.QtCore import QEventLoop, QTimer, QUrl, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest

from core.events import EVEventBus
from core.experience import EVExperienceManager
from core.models import EVState
from core.provider_config import AIProviderConfigStore, DPAPICredentialStore
from gui.bridge import GuiBridge
from prototypes.cinematic_v4.integration import (
    attach_cinematic_window,
    configure_cinematic,
)


@pytest.fixture(scope="module")
def cinematic_app(tmp_path_factory):
    """Stand up the connected cinematic app once for the entire module."""
    scratch = tmp_path_factory.mktemp("settings_input")
    os.environ["EV_USER_DATA_DIR"] = str(scratch)

    app = QGuiApplication.instance()
    if app is None:
        app = QGuiApplication(["test", "-platform", "offscreen"])

    engine = QQmlApplicationEngine()
    bus = EVEventBus(initial_state=EVState.IDLE)
    bridge = GuiBridge(bus)
    bridge.set_experience_manager(EVExperienceManager(bus))
    store = AIProviderConfigStore(
        config_path=scratch / "providers.json",
        credential_store=DPAPICredentialStore(store_path=scratch / "credentials.bin"),
    )
    bridge.set_provider_config_store(store)

    engine.rootContext().setContextProperty("guiBridge", bridge)
    qml_file = configure_cinematic(engine, bridge)
    engine.load(QUrl.fromLocalFile(str(qml_file)))

    roots = engine.rootObjects()
    assert roots, "QML root objects failed to load"
    window = roots[0]
    attach_cinematic_window(engine, window)
    model = engine._cinematic_model

    yield {
        "app": app,
        "engine": engine,
        "window": window,
        "bridge": bridge,
        "model": model,
    }

    # Cleanup
    try:
        model.music.close()
    except Exception:
        pass
    try:
        bridge.shutdown()
    except Exception:
        pass


def _wait(ms: int) -> None:
    """Process events for *ms* milliseconds without blocking indefinitely."""
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def _wait_until(predicate, timeout_s: float = 3.0, poll_ms: int = 50) -> bool:
    """Poll *predicate* with bounded timeout. Returns True if met."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return True
        _wait(poll_ms)
    return False


def _find_item(window, name: str) -> QQuickItem:
    """Find a QQuickItem by objectName, walking the tree if needed."""
    item = window.findChild(QQuickItem, name)
    if item is not None:
        return item
    # Breadth-first fallback through contentItem tree
    pending = [window.contentItem()]
    while pending:
        candidate = pending.pop(0)
        if candidate.objectName() == name:
            return candidate
        pending.extend(candidate.childItems())
    pytest.fail(f"QQuickItem '{name}' not found in scene tree")


class TestSettingsInputBlocking:
    """Settings overlay must block underlying stage input."""

    def test_stage_disabled_while_settings_open(self, cinematic_app):
        bridge = cinematic_app["bridge"]
        window = cinematic_app["window"]

        stage = _find_item(window, "cinematicStage")

        # Precondition: stage is enabled, settings closed
        assert stage.isEnabled(), "Stage should be enabled before opening settings"
        assert not bridge.settingsVisible, "Settings should be closed initially"

        # Open settings
        bridge.openSettings()
        met = _wait_until(
            lambda: bridge.settingsVisible and not stage.isEnabled(),
            timeout_s=3.0,
        )
        assert bridge.settingsVisible, "Settings did not open"
        assert not stage.isEnabled(), "Stage should be disabled while settings are open"

    def test_underlying_click_blocked_while_settings_open(self, cinematic_app):
        bridge = cinematic_app["bridge"]
        window = cinematic_app["window"]
        model = cinematic_app["model"]

        stage = _find_item(window, "cinematicStage")

        # Ensure settings are open
        if not bridge.settingsVisible:
            bridge.openSettings()
            _wait_until(lambda: bridge.settingsVisible, timeout_s=3.0)

        assert not stage.isEnabled(), "Stage should be disabled"

        # Record current mode and attempt a click on the underlying musicButton
        mode_before = model.experienceMode
        music_btn = _find_item(window, "musicButton")
        pt = music_btn.mapToScene(music_btn.boundingRect().center()).toPoint()
        QTest.mouseClick(
            window,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            pt,
        )
        _wait(100)

        assert model.experienceMode == mode_before, (
            "Underlying musicButton click must be blocked while settings are open"
        )

    def test_stage_re_enabled_after_settings_close(self, cinematic_app):
        bridge = cinematic_app["bridge"]
        window = cinematic_app["window"]

        stage = _find_item(window, "cinematicStage")

        # Ensure settings are open first
        if not bridge.settingsVisible:
            bridge.openSettings()
            _wait_until(lambda: bridge.settingsVisible, timeout_s=3.0)

        # Close settings
        bridge.closeSettings()
        met = _wait_until(
            lambda: not bridge.settingsVisible and stage.isEnabled(),
            timeout_s=3.0,
        )
        assert not bridge.settingsVisible, "Settings did not close"
        assert stage.isEnabled(), "Stage should be re-enabled after settings close"

    def test_underlying_click_works_after_settings_close(self, cinematic_app):
        bridge = cinematic_app["bridge"]
        window = cinematic_app["window"]
        model = cinematic_app["model"]

        # Ensure settings are closed and stage is enabled
        if bridge.settingsVisible:
            bridge.closeSettings()
            _wait_until(lambda: not bridge.settingsVisible, timeout_s=3.0)

        # Ensure we start in STANDARD mode for a clean test
        if model.experienceMode == "MUSIC":
            bridge.setExperienceMode("STANDARD")
            _wait(100)

        music_btn = _find_item(window, "musicButton")
        pt = music_btn.mapToScene(music_btn.boundingRect().center()).toPoint()
        QTest.mouseClick(
            window,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            pt,
        )
        _wait(200)

        assert model.experienceMode == "MUSIC", (
            "musicButton click should switch to MUSIC mode after settings close"
        )

        # Restore to STANDARD for other tests
        bridge.setExperienceMode("STANDARD")
        _wait(100)
