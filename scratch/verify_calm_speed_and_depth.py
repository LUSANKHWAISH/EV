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

def run_test():
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
        stage.setProperty('cosmicTheme', 0)
        stage.setProperty('cosmicDepthEnabled', True)
        
    out_dir = Path("d:/EV/scratch/calm_speed_test")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    frames = []
    
    def capture(idx):
        img = window.grabWindow()
        path = str(out_dir / f"frame_{idx:02d}.png")
        img.save(path)
        frames.append(path)
        print(f"Captured {path}")
        if idx == 2:
            app.quit()
        else:
            # Capture 1 second later (1000ms) to measure per-second speed directly
            QTimer.singleShot(1000, lambda: capture(idx + 1))
            
    QTimer.singleShot(2000, lambda: capture(1))
    app.exec()
    
    if len(frames) >= 2:
        img1 = cv2.imread(frames[0])
        img2 = cv2.imread(frames[1])
        
        # Center region around nucleus
        h, w = img1.shape[:2]
        crop1 = img1[200:800, 300:1600]
        crop2 = img2[200:800, 300:1600]
        
        g1 = cv2.cvtColor(crop1, cv2.COLOR_BGR2GRAY)
        g2 = cv2.cvtColor(crop2, cv2.COLOR_BGR2GRAY)
        
        flow = cv2.calcOpticalFlowFarneback(g1, g2, None, 0.5, 3, 15, 3, 5, 1.2, 0)
        mag, ang = cv2.cartToPolar(flow[..., 0], flow[..., 1])
        
        mask = g1 > 50
        avg_dx = np.mean(flow[mask, 0])
        avg_dy = np.mean(flow[mask, 1])
        avg_speed = np.mean(mag[mask])
        print(f"IDLE Mode Motion (1 second): avg_dx={avg_dx:.3f} px/s, avg_dy={avg_dy:.3f} px/s, speed={avg_speed:.3f} px/s")
        print("Target from WARNING mode was: avg_dx ~ 0.55 px/s, speed ~ 1.7 px/s")

if __name__ == '__main__':
    run_test()
