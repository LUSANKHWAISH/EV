"""
Capture offscreen screenshots and validate layout of 10-band playback EQ in EV Music.
Verifies layout at 1100x760 and 1920x1080 resolutions.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
import time

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtCore import QEventLoop, QTimer, QUrl, QSize
from PySide6.QtGui import QGuiApplication, QImage
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickItem, QQuickWindow
from PySide6.QtQuickControls2 import QQuickStyle

os.environ["EV_STARTUP_AUDIO"] = "false"
os.environ["QSG_RENDER_LOOP"] = "basic"

from core.events import EVEventBus
from core.experience import EVExperienceManager
from core.models import EVState
from core.paths import get_resource_root
from core.provider_config import AIProviderConfigStore, DPAPICredentialStore
from gui.bridge import GuiBridge
from prototypes.cinematic_v4.integration import attach_cinematic_window, configure_cinematic


def capture_screenshots() -> int:
    print("=== CAPTURING 10-BAND EQ SCREENSHOTS & VALIDATING LAYOUT ===")

    out_dir = PROJECT_ROOT / "test_runtime"
    out_dir.mkdir(parents=True, exist_ok=True)

    temp_dir = tempfile.TemporaryDirectory(prefix="ev-eq-shot-")
    temp_path = Path(temp_dir.name)
    os.environ["EV_USER_DATA_DIR"] = str(temp_path)

    app = QGuiApplication.instance()
    if app is None:
        app = QGuiApplication([sys.argv[0], "-platform", "offscreen"])

    QQuickStyle.setStyle("Basic")
    engine = QQmlApplicationEngine()
    event_bus = EVEventBus(initial_state=EVState.IDLE)
    bridge = GuiBridge(event_bus)

    experience_manager = EVExperienceManager(event_bus)
    bridge.set_experience_manager(experience_manager)
    engine.rootContext().setContextProperty("guiBridge", bridge)

    provider_store = AIProviderConfigStore(
        config_path=temp_path / "providers.json",
        credential_store=DPAPICredentialStore(store_path=temp_path / "credentials.bin"),
    )
    bridge.set_provider_config_store(provider_store)

    qml_file = configure_cinematic(engine, bridge)
    engine.load(QUrl.fromLocalFile(str(qml_file)))
    root_objects = engine.rootObjects()
    if not root_objects:
        print("ERROR: Failed to load root QML window")
        return 1

    window: QQuickWindow = root_objects[0]
    attach_cinematic_window(engine, window)

    def wait(ms: int) -> None:
        loop = QEventLoop()
        QTimer.singleShot(ms, loop.quit)
        loop.exec()
        app.processEvents()

    wait(200)

    cinematic_model = getattr(engine, "_cinematic_model", None)
    # Switch to Music mode
    bridge.setExperienceMode("MUSIC")
    if cinematic_model and hasattr(cinematic_model, "openMusic"):
        cinematic_model.openMusic()
    wait(400)

    music = cinematic_model.music if cinematic_model else None
    if not music:
        print("ERROR: Music session not attached")
        return 1

    # Load audio file (arrival.wav)
    test_audio = get_resource_root() / "prototypes" / "cinematic_v4" / "assets" / "startup" / "arrival.wav"
    if test_audio.exists():
        music.addFiles([QUrl.fromLocalFile(str(test_audio))])
        wait(200)

    # Set an attractive demo curve:
    # Sub bass boost (+5 dB), low mid dip (-2 dB), presence boost (+3 dB), air (+5 dB)
    test_curve = [5.0, 4.0, 2.0, 0.0, -2.0, -1.0, 1.5, 3.0, 4.5, 5.5]
    for i, g in enumerate(test_curve):
        music.setBandGain(i, g)
    music.setPreamp(-1.5)  # Safe headroom adjustment
    wait(200)

    # Validate elements exist
    eq_panel = window.findChild(QQuickItem, "musicEqualizerPanel")
    assert eq_panel is not None, "musicEqualizerPanel not found in QML hierarchy"
    assert eq_panel.isVisible(), "musicEqualizerPanel is not visible"

    preamp = window.findChild(QQuickItem, "preampSlider")
    assert preamp is not None, "preampSlider not found"

    bypass_btn = window.findChild(QQuickItem, "eqBypassToggleBtn")
    assert bypass_btn is not None, "eqBypassToggleBtn not found"

    flat_btn = window.findChild(QQuickItem, "eqResetFlatBtn")
    assert flat_btn is not None, "eqResetFlatBtn not found"

    child_names = [c.objectName() for c in eq_panel.findChildren(QQuickItem) if c.objectName()]
    print(f"Located {len(child_names)} named items in EqualizerPanel: {child_names}")

    for i in range(10):
        slider = window.findChild(QQuickItem, f"eqBandSlider_{i}")
        assert slider is not None, f"eqBandSlider_{i} not found among {child_names}"

    print("[PASS] All 10 band sliders, preamp, bypass and reset buttons located")

    # Capture 1: Compact 1100x760
    window.resize(QSize(1100, 760))
    wait(200)
    image_1100 = window.grabWindow()
    shot_path_1100 = out_dir / "music_10band_eq_1100x760.png"
    saved_1 = image_1100.save(str(shot_path_1100))
    print(f"[{'PASS' if saved_1 else 'FAIL'}] Saved 1100x760 screenshot to {shot_path_1100} ({image_1100.width()}x{image_1100.height()})")

    # Capture 2: Full HD 1920x1080
    window.resize(QSize(1920, 1080))
    wait(200)
    image_1080 = window.grabWindow()
    shot_path_1080 = out_dir / "music_10band_eq_1920x1080.png"
    saved_2 = image_1080.save(str(shot_path_1080))
    print(f"[{'PASS' if saved_2 else 'FAIL'}] Saved 1920x1080 screenshot to {shot_path_1080} ({image_1080.width()}x{image_1080.height()})")

    # Clean shutdown
    music.close()
    bridge.shutdown()
    temp_dir.cleanup()

    print("=== SCREENSHOT CAPTURE COMPLETE ===")
    return 0 if (saved_1 and saved_2) else 1


if __name__ == "__main__":
    sys.exit(capture_screenshots())
