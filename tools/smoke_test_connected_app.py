"""
End-to-end smoke test for the connected Windows E.V. application.
Verifies:
1. Application launch with cinematic interface default.
2. Golden nucleus core and stage presence.
3. Settings overlay open and close.
4. Assistant to Music mode switching.
5. Three visualizers presence in Music workspace (CeilingRain, FlowTrace, SegmentStack).
6. Local audio playback session queue and transport control.
7. Music back to Assistant mode switching.
8. Clean shutdown of subsystems.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import time

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtCore import QEventLoop, QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickItem
from PySide6.QtQuickControls2 import QQuickStyle

# Set headless/offscreen flags for deterministic execution
os.environ["EV_STARTUP_AUDIO"] = "false"
os.environ["QSG_RENDER_LOOP"] = "basic"

from core.action_pipeline import ActionPipelineContext
from core.events import EVEventBus
from core.experience import EVExperienceManager
from core.models import EVState
from core.orchestrator import EVOrchestrator
from core.paths import get_resource_root
from core.proactive_awareness import EVProactiveAwarenessEngine
from core.provider_config import AIProviderConfigStore, DPAPICredentialStore
from core.system_monitor import EVSystemMonitor
from gui.bridge import GuiBridge
from prototypes.cinematic_v4.integration import attach_cinematic_window, configure_cinematic


def run_smoke_test() -> int:
    results: dict[str, bool] = {}
    print("=== STARTING CONNECTED EV APPLICATION SMOKE TEST ===")

    temp_dir = tempfile.TemporaryDirectory(prefix="ev-app-smoke-")
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

    orchestrator = EVOrchestrator(event_bus=event_bus)
    system_monitor = EVSystemMonitor(event_bus=event_bus)
    system_monitor.start()

    awareness_engine = EVProactiveAwarenessEngine(
        event_bus=event_bus,
        system_monitor=system_monitor,
        experience_manager=experience_manager,
    )
    awareness_engine.start()

    # 1. Launch Cinematic Default
    qml_file = configure_cinematic(engine, bridge)
    engine.load(QUrl.fromLocalFile(str(qml_file)))
    root_objects = engine.rootObjects()
    results["1_launch_cinematic"] = len(root_objects) > 0 and root_objects[0].objectName() == "cinematicWindow"
    print(f"[{'PASS' if results['1_launch_cinematic'] else 'FAIL'}] 1. Launch & root window loaded")

    if not results["1_launch_cinematic"]:
        return 1

    window = root_objects[0]
    attach_cinematic_window(engine, window)

    def wait(ms: int) -> None:
        loop = QEventLoop()
        QTimer.singleShot(ms, loop.quit)
        loop.exec()

    wait(200)

    # 2. Golden Core & Stage
    stage = window.findChild(QQuickItem, "cinematicStage")
    results["2_golden_core_stage"] = stage is not None and stage.objectName() == "cinematicStage"
    print(f"[{'PASS' if results['2_golden_core_stage'] else 'FAIL'}] 2. Golden nucleus stage present")

    # 3. Settings Overlay Open and Close
    bridge.openSettings()
    wait(100)
    settings_open = bridge.settingsVisible
    bridge.closeSettings()
    wait(100)
    settings_closed = not bridge.settingsVisible
    results["3_settings_open_close"] = settings_open and settings_closed
    print(f"[{'PASS' if results['3_settings_open_close'] else 'FAIL'}] 3. Settings overlay open/close")

    # 4. Mode Switching to Music
    bridge.setExperienceMode("MUSIC")
    wait(200)
    results["4_mode_switch_music"] = bridge.experienceMode == "MUSIC"
    print(f"[{'PASS' if results['4_mode_switch_music'] else 'FAIL'}] 4. Switched to Music mode")

    # 5. Three Visualizers (CeilingRain, FlowTrace, SegmentStack) in Music Workspace
    music_page = window.findChild(QQuickItem, "musicWorkspace")
    ceiling_rain = window.findChild(QQuickItem, "ceilingRain")
    flow_trace = window.findChild(QQuickItem, "flowTrace")
    segment_stack = window.findChild(QQuickItem, "segmentStack")

    results["5_three_visualizers"] = (
        music_page is not None
        and ceiling_rain is not None
        and flow_trace is not None
        and segment_stack is not None
    )
    print(f"[{'PASS' if results['5_three_visualizers'] else 'FAIL'}] 5. Three music visualizers rendered (CeilingRain, FlowTrace, SegmentStack)")

    # 6. Local Playback Session Queue & Transport
    cinematic_model = getattr(engine, "_cinematic_model", None)
    music_session = cinematic_model.music if cinematic_model else None
    results["6_playback_session"] = False
    if music_session is not None:
        test_audio_path = get_resource_root() / "prototypes" / "cinematic_v4" / "assets" / "startup" / "arrival.wav"
        if test_audio_path.exists():
            music_session.addFiles([QUrl.fromLocalFile(str(test_audio_path))])
            wait(100)
            has_track = len(music_session.queue) > 0
            music_session.togglePlayback()
            wait(50)
            music_session.stop()
            wait(50)
            results["6_playback_session"] = has_track
    print(f"[{'PASS' if results['6_playback_session'] else 'FAIL'}] 6. Local playback session queue and transport")

    # 7. Mode Switching Back to Assistant
    bridge.setExperienceMode("STANDARD")
    wait(200)
    results["7_mode_switch_assistant"] = bridge.experienceMode == "STANDARD"
    print(f"[{'PASS' if results['7_mode_switch_assistant'] else 'FAIL'}] 7. Switched back to Assistant mode")

    # 8. Clean Shutdown
    try:
        if music_session is not None:
            music_session.close()
        awareness_engine.stop()
        system_monitor.stop()
        bridge.shutdown()
        results["8_clean_shutdown"] = True
    except Exception as exc:
        print(f"Shutdown error: {exc}")
        results["8_clean_shutdown"] = False
    print(f"[{'PASS' if results['8_clean_shutdown'] else 'FAIL'}] 8. Clean subsystem shutdown")

    temp_dir.cleanup()
    all_passed = all(results.values())
    print("=== SMOKE TEST SUMMARY ===")
    for k, v in results.items():
        print(f"  {k}: {'PASS' if v else 'FAIL'}")
    print(f"OVERALL: {'SUCCESS (ALL PASSED)' if all_passed else 'FAILURE'}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(run_smoke_test())
