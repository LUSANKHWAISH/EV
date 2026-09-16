"""Create named review captures from actual Qt windows, sequentially."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent
E=ROOT/'evidence'

def run(name,extra):
    command=[sys.executable,'-B',str(ROOT/'run_preview.py'),'--reference-dpi','--capture',name+'.png','--capture-after','4','--duration','6','--report',name+'.json',*extra]
    with (E/(name+'_console.txt')).open('w') as log:
        result=subprocess.run(command,cwd=ROOT.parents[1],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:raise RuntimeError(name+' failed; inspect its console log')
    print(name,flush=True)

def comparison():
    from PySide6.QtGui import QGuiApplication,QImage,QPainter,QColor,QFont
    from PySide6.QtCore import Qt,QRect
    app=QGuiApplication.instance() or QGuiApplication(['ev-review-composition'])
    canvas=QImage(1480,838,QImage.Format.Format_RGB32);canvas.fill(QColor('#070d13'))
    painter=QPainter(canvas);painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QColor('#d5b878'));painter.setFont(QFont('Segoe UI',15))
    painter.drawText(20,35,'FILM REFERENCE · 34.5 SECONDS')
    painter.drawText(760,35,'E.V. · ACTUAL QT 3D RENDER')
    reference=QImage(str(E/'reference_34_5.png'))
    rendered=QImage(str(E/'review_expanded.png')).copy(588,38,820,820)
    for x,img in [(20,reference),(760,rendered)]:
        painter.drawImage(QRect(x,54,700,700),img.scaled(700,700,Qt.AspectRatioMode.IgnoreAspectRatio,Qt.TransformationMode.SmoothTransformation))
    painter.setPen(QColor('#8e9fa9'));painter.setFont(QFont('Segoe UI',10))
    painter.drawText(20,789,'Both views are cropped and resized for visual review. The right image is a real application capture, not a mockup.')
    painter.drawText(20,814,'The geometry and textures are procedural. No film frame is used by the renderer; no objective match percentage is claimed.')
    painter.end();canvas.save(str(E/'reference_comparison.png'))

def main():
    for name,args in [('review_standard',[]),('review_expanded',['--expanded']),('review_quality',['--quality','--expanded']),
                      ('review_settings',['--size','1280x800','--drawer','settings']),('review_yaw90',['--expanded','--view-yaw','90'])]:
        run(name,args)
    comparison()
    return 0

if __name__=='__main__':raise SystemExit(main())
