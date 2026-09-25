import os
import sys
from pathlib import Path

ROOT = Path("d:/EV/prototypes/cinematic_v4")
sys.path.insert(0, str(ROOT))

import cv2
import numpy as np
from PySide6.QtCore import QUrl, QTimer, Qt
from PySide6.QtGui import QGuiApplication, QImage
from PySide6.QtQml import QQmlApplicationEngine, qmlRegisterType
from PySide6.QtQuick import QQuickItem

from geometry import (
    LabGeometry,
    ParticleInstances,
    OrbitalParticleInstances,
    CosmicDepthInstances,
)
from presentation import PresentationModel

def run_capture():
    app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])
    
    qmlRegisterType(LabGeometry, 'EVLab', 1, 0, 'LabGeometry')
    qmlRegisterType(ParticleInstances, 'EVLab', 1, 0, 'ParticleInstances')
    qmlRegisterType(OrbitalParticleInstances, 'EVLab', 1, 0, 'OrbitalParticleInstances')
    qmlRegisterType(CosmicDepthInstances, 'EVLab', 1, 0, 'CosmicDepthInstances')
    
    lab = PresentationModel()
    lab.setState('IDLE')
    lab.finishLaunch()
    
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty('lab', lab)
    engine.rootContext().setContextProperty('startExpanded', False)
    engine.load(QUrl.fromLocalFile(str(ROOT / 'qml/LabWindow.qml')))
    
    if not engine.rootObjects():
        print("Engine failed to load")
        return
        
    window = engine.rootObjects()[0]
    window.resize(1920, 1080)
    
    stage = window.findChild(QQuickItem, 'cinematicStage')
    if stage:
        stage.setProperty('cosmicTheme', 0) # Cyan blue
        stage.setProperty('cosmicDepthEnabled', True)
        
    out_dir = Path("d:/EV/scratch/motion_test")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    frames = []
    
    def capture_frame(idx):
        img = window.grabWindow()
        path = str(out_dir / f"frame_{idx:02d}.png")
        img.save(path)
        frames.append(path)
        print(f"Captured {path}")
        if idx == 3:
            app.quit()
        else:
            QTimer.singleShot(400, lambda: capture_frame(idx + 1))
            
    # Start capturing after 2000ms
    QTimer.singleShot(2000, lambda: capture_frame(1))
    app.exec()
    
    # Now analyze motion between frame 1 and frame 2
    if len(frames) >= 2:
        img1 = cv2.imread(frames[0])
        img2 = cv2.imread(frames[1])
        
        # Center region around nucleus (1920x1080 -> center ~ 960, 440)
        h, w = img1.shape[:2]
        cx, cy = 960, 440
        rw, rh = 350, 350
        
        crop1 = img1[cy-rh:cy+rh, cx-rw:cx+rw]
        crop2 = img2[cy-rh:cy+rh, cx-rw:cx+rw]
        
        g1 = cv2.cvtColor(crop1, cv2.COLOR_BGR2GRAY)
        g2 = cv2.cvtColor(crop2, cv2.COLOR_BGR2GRAY)
        
        flow = cv2.calcOpticalFlowFarneback(g1, g2, None, 0.5, 3, 15, 3, 5, 1.2, 0)
        
        # Foreground particles (bright cyan dots: high blue/green relative to red)
        cyan_mask = (crop1[..., 0] > 100) & (crop1[..., 1] > 120) & (crop1[..., 2] < 200)
        
        if np.any(cyan_mask):
            mean_dx = np.mean(flow[cyan_mask, 0])
            mean_dy = np.mean(flow[cyan_mask, 1])
            print(f"Cyan Particle Motion: mean_dx = {mean_dx:.3f} px (positive = LEFT TO RIGHT)")
            if mean_dx > 0:
                print("SUCCESS: Particles are rotating from LEFT to RIGHT!")
            else:
                print("WARNING: Particles are moving right to left")
        else:
            print("No cyan mask detected, calculating general flow...")
            bright = g1 > 60
            mean_dx = np.mean(flow[bright, 0])
            print(f"General flow dx: {mean_dx:.3f} px")

if __name__ == '__main__':
    run_capture()
