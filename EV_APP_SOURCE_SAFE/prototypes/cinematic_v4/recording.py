"""Records real QQuickWindow renders; bounded queue, real wall-clock playback."""
import json
import shutil
import subprocess
import threading
import time
from pathlib import Path
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QImage

class RenderRecorder:
    def __init__(self,window,path,seconds=15,fps=30):
        self.window=window;self.path=Path(path);self.seconds=seconds;self.fps=fps
        self.latest=None;self.lock=threading.Lock();self.error=None
        self.captured=0;self.written=0;self.duplicates=0;self.finished=False
        self.timer=QTimer(window);self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.setInterval(round(1000/fps));self.timer.timeout.connect(self.capture)
    def start(self):
        self.capture()
        self.thread=threading.Thread(target=self.encode,name='Qt-render-recorder',daemon=True)
        self.thread.start();self.timer.start()
    def capture(self):
        if self.finished:self.timer.stop();return
        image=self.window.grabWindow().convertToFormat(QImage.Format.Format_RGBA8888)
        if image.isNull():return
        data=bytes(image.constBits())
        with self.lock:
            self.latest=(self.captured,data,image.width(),image.height())
            self.captured+=1
    def encode(self):
        try:
            ffmpeg=shutil.which('ffmpeg')
            if not ffmpeg:raise RuntimeError('ffmpeg not found')
            with self.lock:frame=self.latest
            w,h=frame[2:]
            command=[ffmpeg,'-hide_banner','-loglevel','error','-y','-f','rawvideo','-pixel_format','rgba','-video_size',f'{w}x{h}','-framerate',str(self.fps),'-i','pipe:0','-an','-c:v','libx264','-preset','ultrafast','-crf','19','-pix_fmt','yuv420p',str(self.path)]
            proc=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW)
            start=time.perf_counter();last_id=-1
            for i in range(round(self.seconds*self.fps)):
                remaining=start+i/self.fps-time.perf_counter()
                if remaining>0:time.sleep(remaining)
                with self.lock:frame=self.latest
                if frame[0]==last_id:self.duplicates+=1
                last_id=frame[0];proc.stdin.write(frame[1]);self.written+=1
            proc.stdin.close();stderr=proc.stderr.read().decode();code=proc.wait()
            if code:raise RuntimeError(stderr)
            result={'source':'QQuickWindow.grabWindow: actual Qt rendered frames','width':w,'height':h,'fps':self.fps,'duration':self.seconds,'captured_frames':self.captured,'encoded_frames':self.written,'duplicate_frames':self.duplicates,'note':'Capture overhead is excluded from normal performance measurements.'}
            self.path.with_suffix('.json').write_text(json.dumps(result,indent=2))
        except Exception as exc:self.error=str(exc)
        finally:self.finished=True
