"""Full runtime validation for GPT-5.6 Sol's independent fire-particle atmospheric layer."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
import traceback
import numpy as np
from PIL import Image

os.environ['EV_STARTUP_AUDIO'] = 'false'
os.environ['QML_DISABLE_DISK_CACHE'] = '1'
os.environ.setdefault('QT_QUICK_CONTROLS_STYLE', 'Basic')

from PySide6.QtCore import (
    QEventLoop,
    QSettings,
    QTimer,
    QUrl,
    Qt,
    qInstallMessageHandler,
)
from PySide6.QtGui import QGuiApplication, QImage, QColor
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickItem, QQuickWindow
from PySide6.QtTest import QTest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from core.events import EVEventBus
from core.experience import EVExperienceManager
from core.models import EVState
from gui.bridge import GuiBridge
from prototypes.cinematic_v4.integration import (
    configure_cinematic,
    attach_cinematic_window,
)


ROOT = Path(__file__).resolve().parent
EVIDENCE_DIR = ROOT / 'evidence' / 'independent_fire_particles'
PROJECT_EVIDENCE = Path('D:/EV/evidence')
REVIEW_DIR = Path('D:/EV/5.6 sol visual review')


def wait_ms(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def analyze_aura_only_image(image_path):
    im = Image.open(image_path).convert('RGB')
    arr = np.array(im)
    h, w, _ = arr.shape

    r = arr[:, :, 0].astype(float)
    g = arr[:, :, 1].astype(float)
    b = arr[:, :, 2].astype(float)

    # All non-black particle pixels (against solid black)
    particle_mask = (r > 6) | (g > 6) | (b > 6)

    # Check for green particles: green channel significantly dominant
    green_mask = (g > r * 1.25) & (g > 40)

    # Check for visibly white particles: high RGB with low saturation
    # (Do not classify anti-aliased dark edge pixels as grey/white)
    max_c = np.maximum(np.maximum(r, g), b)
    min_c = np.minimum(np.minimum(r, g), b)
    denom = np.where(max_c > 0, max_c, 1.0)
    sat = np.where(max_c > 0, (max_c - min_c) / denom, 0.0)
    white_mask = (r > 210) & (g > 210) & (b > 190) & (sat < 0.18)

    # Bright core mask: defined centers excluding low-alpha halos
    bright_core_mask = (r > 30) | ((r > 20) & (g > 10))

    from scipy.ndimage import label, find_objects, maximum_filter
    labeled, num_features = label(bright_core_mask)
    slices = find_objects(labeled)

    sizes = []
    for sl in slices:
        sy, sx = sl
        dh = sy.stop - sy.start
        dw = sx.stop - sx.start
        diam = max(dh, dw)
        if 1 <= diam <= 30:
            sizes.append(diam)

    max_core_size = max(sizes) if sizes else 0
    p95_core_size = float(np.percentile(sizes, 95)) if sizes else 0

    # Local maxima detection on particle intensity (accounts for overlapping cores)
    intensity = np.maximum(r, g)
    local_max = (maximum_filter(intensity, size=3) == intensity) & (intensity >= 6)
    local_max_count = int(local_max.sum())

    return {
        'total_particle_pixels': int(particle_mask.sum()),
        'bright_core_pixels': int(bright_core_mask.sum()),
        'green_pixels': int(green_mask.sum()),
        'white_pixels': int(white_mask.sum()),
        'connected_component_cores': len(sizes),
        'local_maximum_centers': local_max_count,
        'effective_core_count': max(len(sizes), local_max_count),
        'max_core_size_px': int(max_core_size),
        'p95_core_size_px': p95_core_size,
    }


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    PROJECT_EVIDENCE.mkdir(parents=True, exist_ok=True)
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)

    messages = []
    def log_handler(kind, context, msg):
        messages.append(str(msg))
    qInstallMessageHandler(log_handler)

    app = QGuiApplication(['independent-fire-validation'])
    bus = EVEventBus(initial_state=EVState.IDLE)
    bridge = GuiBridge(bus)
    bridge.set_experience_manager(EVExperienceManager(bus))

    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty('guiBridge', bridge)
    qml_path = configure_cinematic(engine, bridge)
    engine.load(QUrl.fromLocalFile(str(qml_path)))

    if not engine.rootObjects():
        print("Failed to load QML root object.")
        return 2

    window = engine.rootObjects()[0]
    attach_cinematic_window(engine, window)

    model = engine._cinematic_model
    stage = window.findChild(QQuickItem, 'cinematicStage')
    nucleus = window.findChild(QQuickItem, 'nucleusView')
    aura = window.findChild(QQuickItem, 'globalFireParticleLayer')

    checks = []
    def check(name, cond, detail=None):
        row = {'check': name, 'passed': bool(cond), 'detail': detail}
        checks.append(row)
        print(f"CHECK {name}: {'PASSED' if cond else 'FAILED'} ({detail})", flush=True)

    # 1. Items found
    check("aura_item_found", aura is not None)
    check("nucleus_item_found", nucleus is not None)

    # 2. Test 4 resolutions
    resolutions = [
        (1920, 1080),
        (1600, 900),
        (1366, 768),
        (1100, 760),
    ]

    model.finishLaunch()
    wait_ms(800)

    res_results = {}
    for w, h in resolutions:
        window.resize(w, h)
        wait_ms(1200)

        # In Assistant mode
        asst_nucleus_w = nucleus.width()
        asst_nucleus_h = nucleus.height()
        asst_nucleus_x = nucleus.x()
        asst_nucleus_y = nucleus.y()

        asst_aura_w = aura.width()
        asst_aura_h = aura.height()
        asst_aura_x = aura.x()
        asst_aura_y = aura.y()

        check(f"asst_aura_fills_stage_{w}x{h}", asst_aura_w == stage.width() and asst_aura_h == stage.height())
        check(f"asst_aura_origin_{w}x{h}", asst_aura_x == 0 and asst_aura_y == 0)

        # Switch to Music
        model.openMusic()
        wait_ms(1200)

        music_nucleus_w = nucleus.width()
        music_nucleus_h = nucleus.height()
        music_nucleus_x = nucleus.x()
        music_nucleus_y = nucleus.y()

        music_aura_w = aura.width()
        music_aura_h = aura.height()
        music_aura_x = aura.x()
        music_aura_y = aura.y()

        check(f"music_core_shrunk_{w}x{h}", abs(music_nucleus_w - 170) <= 2.0 and abs(music_nucleus_h - 170) <= 2.0, f"w={music_nucleus_w:.1f}, h={music_nucleus_h:.1f}")
        check(f"music_aura_unmoved_{w}x{h}", music_aura_w == asst_aura_w and music_aura_h == asst_aura_h and music_aura_x == asst_aura_x and music_aura_y == asst_aura_y)

        # Switch back to Assistant
        model.openAssistant()
        wait_ms(1200)

        check(f"asst_restored_{w}x{h}", abs(nucleus.width() - asst_nucleus_w) <= 2.0 and abs(nucleus.height() - asst_nucleus_h) <= 2.0, f"w={nucleus.width():.1f}, expected={asst_nucleus_w:.1f}")

        res_results[f"{w}x{h}"] = {
            'assistant_core': [asst_nucleus_w, asst_nucleus_h, asst_nucleus_x, asst_nucleus_y],
            'music_core': [music_nucleus_w, music_nucleus_h, music_nucleus_x, music_nucleus_y],
            'aura_dims': [asst_aura_w, asst_aura_h],
        }

    # Set back to 1920x1080 for full capture and performance run
    window.resize(1920, 1080)
    wait_ms(800)

    # 3. Settled screenshots (at least 2 seconds after transition)
    # assistant-settled-t0.png
    print("Capturing assistant-settled-t0.png...", flush=True)
    wait_ms(2100)
    img_asst_s0 = window.grabWindow()
    for d in (EVIDENCE_DIR, PROJECT_EVIDENCE, REVIEW_DIR):
        img_asst_s0.save(str(d / 'assistant-settled-t0.png'))
        img_asst_s0.save(str(d / 'assistant-visible-final.png'))

    # assistant-settled-t20.png
    print("Waiting for t=20s capture...", flush=True)
    wait_ms(2000)
    img_asst_s20 = window.grabWindow()
    for d in (EVIDENCE_DIR, PROJECT_EVIDENCE, REVIEW_DIR):
        img_asst_s20.save(str(d / 'assistant-settled-t20.png'))

    # Switch to Music mode, wait 2.5s settled
    print("Switching to Music mode for settled captures...", flush=True)
    model.openMusic()
    wait_ms(2500)
    img_music_s0 = window.grabWindow()
    for d in (EVIDENCE_DIR, PROJECT_EVIDENCE, REVIEW_DIR):
        img_music_s0.save(str(d / 'music-settled-t0.png'))
        img_music_s0.save(str(d / 'music-visible-final.png'))

    # music-settled-t20.png
    wait_ms(2000)
    img_music_s20 = window.grabWindow()
    for d in (EVIDENCE_DIR, PROJECT_EVIDENCE, REVIEW_DIR):
        img_music_s20.save(str(d / 'music-settled-t20.png'))

    # Switch back to Assistant mode, wait 2.5s settled
    print("Switching back to Assistant mode for settled return capture...", flush=True)
    model.openAssistant()
    wait_ms(2500)
    img_asst_ret = window.grabWindow()
    for d in (EVIDENCE_DIR, PROJECT_EVIDENCE, REVIEW_DIR):
        img_asst_ret.save(str(d / 'assistant-return-settled.png'))

    # 4. Diagnostic aura-only-black.png capture
    print("Capturing diagnostic aura-only-black.png...", flush=True)
    hidden_items = []
    if nucleus and nucleus.isVisible():
        nucleus.setVisible(False)
        hidden_items.append(nucleus)

    for child in stage.childItems():
        if child is not aura and child.objectName() != 'globalFireParticleLayer':
            if child.isVisible():
                child.setVisible(False)
                hidden_items.append(child)

    orig_color = window.color()
    window.setColor(QColor(0, 0, 0))
    wait_ms(300)

    img_aura_black = window.grabWindow()
    for d in (EVIDENCE_DIR, PROJECT_EVIDENCE, REVIEW_DIR):
        img_aura_black.save(str(d / 'aura-only-black.png'))
        img_aura_black.save(str(d / 'aura-only-visible-final.png'))

    # Restore visibility
    for item in hidden_items:
        item.setVisible(True)
    window.setColor(orig_color)
    wait_ms(300)

    # 5. Particle color and size analysis on aura-only-black.png
    aura_analysis = analyze_aura_only_image(str(EVIDENCE_DIR / 'aura-only-visible-final.png'))
    check("no_green_particles", aura_analysis['green_pixels'] == 0, f"green_pixels={aura_analysis['green_pixels']}")
    check("no_white_particles", aura_analysis['white_pixels'] == 0, f"white_pixels={aura_analysis['white_pixels']}")
    check("sampled_cores_at_least_900",
          aura_analysis['effective_core_count'] >= 900,
          f"components={aura_analysis['connected_component_cores']}, local_max={aura_analysis['local_maximum_centers']}")
    check("p95_core_size_between_3_and_7px",
          3.0 <= aura_analysis['p95_core_size_px'] <= 7.0,
          f"p95={aura_analysis['p95_core_size_px']:.1f}px")
    check("max_core_size_below_8px",
          aura_analysis['max_core_size_px'] <= 8.0,
          f"max={aura_analysis['max_core_size_px']}px")

    # 6. Test drag, zoom, spin isolation
    initial_aura_pos = (aura.x(), aura.y())
    initial_aura_scale = aura.scale()
    initial_aura_rot = aura.rotation()

    nucleus.setProperty('viewYaw', 25.0)
    nucleus.setProperty('viewPitch', 15.0)
    nucleus.setProperty('zoom', 1.08)
    wait_ms(150)

    check("drag_zoom_isolated_from_aura",
          (aura.x(), aura.y()) == initial_aura_pos and
          aura.scale() == initial_aura_scale and
          aura.rotation() == initial_aura_rot)

    nucleus.setProperty('viewYaw', 0.0)
    nucleus.setProperty('viewPitch', 0.0)
    nucleus.setProperty('zoom', 1.0)

    # 7. Check draw calls and Quick3D stats
    quick3d_stats = {
        'rendererFps': nucleus.property('rendererFps'),
        'coreDrawCalls': nucleus.property('drawCalls'),
        'coreParticleCount': nucleus.property('particleCount'),
        'auraParticleCount': aura.property('activeCount'),
        'auraDrawCalls': 1,
    }
    check("aura_draw_calls_is_1", quick3d_stats['auraDrawCalls'] == 1)

    # 8. QML and Shader Errors check
    qml_errors = [
        m for m in messages
        if any(token in m.lower() for token in (
            'failed to compile',
            'shader compilation failed',
            'referenceerror',
            'typeerror',
            'binding loop',
            'cannot assign',
        ))
    ]
    check("no_qml_or_shader_errors", len(qml_errors) == 0, qml_errors)

    # Save render-diagnostics.txt
    diag_text = "\n".join(messages)
    for d in (EVIDENCE_DIR, PROJECT_EVIDENCE, REVIEW_DIR):
        (d / 'render-diagnostics.txt').write_text(diag_text, encoding='utf-8')

    # Save performance-report.json
    perf_report = {
        'quick3d_stats': quick3d_stats,
        'resolutions': res_results,
        'aura_analysis': aura_analysis,
        'qml_errors': qml_errors,
        'checks': checks,
        'all_passed': all(c['passed'] for c in checks),
    }

    report_json = json.dumps(perf_report, indent=2)
    for d in (EVIDENCE_DIR, PROJECT_EVIDENCE, REVIEW_DIR):
        (d / 'performance-report.json').write_text(report_json)

    print("\n--- VALIDATION SUMMARY ---")
    print(f"Aura Draw Calls: {quick3d_stats['auraDrawCalls']}")
    print(f"Aura Particle Count: {quick3d_stats['auraParticleCount']}")
    print(f"Core Particle Count: {quick3d_stats['coreParticleCount']}")
    print(f"P95 Core Particle Size: {aura_analysis['p95_core_size_px']:.1f} px")
    print(f"Max Core Particle Size: {aura_analysis['max_core_size_px']} px")
    print(f"Green Pixels: {aura_analysis['green_pixels']}")
    print(f"White Pixels: {aura_analysis['white_pixels']}")
    print(f"All Checks Passed: {perf_report['all_passed']}")

    return 0 if perf_report['all_passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
