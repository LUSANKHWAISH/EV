"""Explicit render-thread pacing; D3D11 QRhi treats swap interval as on/off.

The lighter scene profile is independent of this limiter. The GUI thread does
not sleep and no application/controller state is changed by the render thread.
"""
import time
from PySide6.QtCore import QObject,Slot

class FramePacer(QObject):
    def __init__(self,refresh_rate=60.0,parent=None):
        super().__init__(parent)
        self.quality=False
        self.last_begin=0.0
        self.cap_standard=refresh_rate>60.5
    @Slot()
    def before_frame(self):
        if not self.quality and not self.cap_standard:
            self.last_begin=0.0
            return
        now=time.perf_counter()
        if self.last_begin:
            remaining=self.last_begin+1/(30 if self.quality else 60)-now
            if remaining>0:time.sleep(remaining)
        self.last_begin=time.perf_counter()
