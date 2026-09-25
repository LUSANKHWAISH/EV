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
        
    out_dir = Path("d:/EV/scratch/orbit_test")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    frames = []
    
    def capture(idx):
        img = window.grabWindow()
        path = str(out_dir / f"orbit_frame_{idx:02d}.png")
        img.save(path)
        frames.append(path)
        print(f"Captured {path}")
        if idx == 3:
            app.quit()
        else:
            QTimer.singleShot(1000, lambda: capture(idx + 1))
            
    QTimer.singleShot(1500, lambda: capture(1))
    app.exec()
    
    if len(frames) >= 2:
        img1 = cv2.imread(frames[0])
        img2 = cv2.imread(frames[1])
        diff = cv2.absdiff(img1, img2)
        print("Total frame diff:", np.mean(diff))

if __name__ == '__main__':
    run_test()
