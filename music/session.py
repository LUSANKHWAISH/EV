"""Music-domain controller: local player, selected output capture and real meters."""
import math
from pathlib import Path
import time

import numpy as np
from PySide6.QtCore import QObject, Property, QCoreApplication, QSettings, QTimer, QUrl, Signal, Slot
from PySide6.QtMultimedia import QAudioBufferOutput, QAudioFormat, QAudioOutput, QMediaDevices, QMediaPlayer

from .analysis import AnalysisWorker
from .loopback import LoopbackCapture
from .onsets import BeatEnvelope


class MusicSession(QObject):
    changed = Signal()
    analysisChanged = Signal()
    devicesChanged = Signal()
    userAction = Signal()
    _captureMessage = Signal(int, str, str)

    def __init__(self, parent=None, settings=None):
        super().__init__(parent)
        self._settings = settings if settings is not None else QSettings('EV', 'MusicFoundation')
        self._active = False
        self._music_open = False
        self._closed = False
        mode = self._settings.value('reactionMode', 'all')
        self._reaction_mode = mode if mode in ('music','all','off') else 'all'
        try:
            intensity = float(self._settings.value('reactionIntensity', 1.))
        except (ValueError, TypeError):
            intensity = 1.
        self._reaction_intensity = max(0.,min(1.,intensity)) if math.isfinite(intensity) else 1.
        self._capture_requested = False
        self._input = 'player'
        self._status = 'Open a local track to begin.'
        self._capture_state = 'off'
        self._capture_generation = 0
        self._device_id = -1
        self._devices = []
        self._queue = []
        self._index = -1
        self._frame = None
        self._beat = BeatEnvelope()
        self._bands = [0.]*64
        self._wave = [0.]*160
        self._values = dict(rms=0.,peak=0.,bass=0.,mid=0.,treble=0.)
        self._last_tick = time.monotonic()
        self.worker = AnalysisWorker()
        self.capture = None
        self.output = QAudioOutput(self)
        try:
            volume = float(self._settings.value('volume', .55))
            if not math.isfinite(volume):
                volume = .55
        except (ValueError, TypeError):
            volume = .55
        self.output.setVolume(max(0.,min(1.,volume)))
        self.player = QMediaPlayer(self)
        self.player.setAudioOutput(self.output)
        self.tap = QAudioBufferOutput(self)
        self.player.setAudioBufferOutput(self.tap)
        self.tap.audioBufferReceived.connect(self._pcm)
        self.player.positionChanged.connect(self.changed)
        self.player.durationChanged.connect(self.changed)
        self.player.seekableChanged.connect(self.changed)
        self.player.playbackStateChanged.connect(self._playback_changed)
        self.player.mediaStatusChanged.connect(self._media_status)
        self.player.errorOccurred.connect(self._error)
        self._captureMessage.connect(self._capture_message)
        self.media_devices = QMediaDevices(self)
        self.media_devices.audioOutputsChanged.connect(self._devices_changed)
        self.timer = QTimer(self)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self._tick)
        app = QCoreApplication.instance()
        if app:
            app.aboutToQuit.connect(self.close)

    @Property(str, notify=changed)
    def inputSource(self): return self._input
    @Property(str, notify=changed)
    def reactionMode(self): return self._reaction_mode
    @Property(float, notify=changed)
    def reactionIntensity(self): return self._reaction_intensity
    @Property(bool, notify=changed)
    def analysisActive(self): return self._active
    @Property(float, notify=changed)
    def reactionGain(self):
        if self._reaction_mode == 'off' or (not self._music_open and self._reaction_mode != 'all'):
            return 0.
        return self._reaction_intensity * (1. if self._music_open else .25)
    @Property(str, notify=changed)
    def status(self): return self._status
    @Property(str, notify=changed)
    def captureState(self): return self._capture_state
    @Property(str, notify=changed)
    def title(self): return self._queue[self._index]['title'] if 0 <= self._index < len(self._queue) else 'Your music, in motion.'
    @Property('QVariantList', notify=changed)
    def queue(self): return [{'title':row['title'],'index':i} for i,row in enumerate(self._queue)]
    @Property(int, notify=changed)
    def currentIndex(self): return self._index
    @Property(bool, notify=changed)
    def playing(self): return self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
    @Property(bool, notify=changed)
    def hasTrack(self): return self._index >= 0
    @Property(bool, notify=changed)
    def seekable(self): return self.player.isSeekable()
    @Property(float, notify=changed)
    def position(self): return float(self.player.position())
    @Property(float, notify=changed)
    def duration(self): return float(self.player.duration())
    @Property(float, notify=changed)
    def volume(self): return self.output.volume()
    @Property(bool, notify=changed)
    def muted(self): return self.output.isMuted()
    @Property('QVariantList', notify=devicesChanged)
    def captureDevices(self): return [{'id':-1,'label':'Follow default Windows output'}]+self._devices
    @Property(int, notify=devicesChanged)
    def captureDeviceId(self): return self._device_id
    @Property('QStringList', notify=devicesChanged)
    def outputDevices(self): return ['Default output']+[d.description() for d in QMediaDevices.audioOutputs()]
    @Property('QVariantList', notify=analysisChanged)
    def bands(self): return self._bands
    @Property('QVariantList', notify=analysisChanged)
    def waveform(self): return self._wave
    @Property(float, notify=analysisChanged)
    def level(self): return min(1., self._values['rms']*5)
    @Property(float, notify=analysisChanged)
    def beat(self): return self._beat.value
    @Property(float, notify=analysisChanged)
    def bass(self): return min(1., self._values['bass']*5)
    @Property(float, notify=analysisChanged)
    def mid(self): return min(1., self._values['mid']*5)
    @Property(float, notify=analysisChanged)
    def treble(self): return min(1., self._values['treble']*5)
    @Property(str, notify=analysisChanged)
    def rmsText(self): return f'{20*math.log10(max(1e-6,self._values["rms"])):.1f} dBFS'
    @Property(str, notify=analysisChanged)
    def peakText(self): return f'{20*math.log10(max(1e-6,self._values["peak"])):.1f} dBFS'

    def set_active(self, active):
        """Set Music-page visibility; analysis may continue for ambient reactions."""
        if self._closed: return
        was_open = self._music_open
        self._music_open = bool(active)
        if self._music_open and not was_open: self.refreshDevices()
        self._sync_active()
        self.changed.emit()

    @Slot(str)
    def setReactionMode(self, mode):
        if mode not in ('music','all','off') or mode == self._reaction_mode: return
        self._reaction_mode = mode
        self._settings.setValue('reactionMode',mode)
        self._sync_active()
        self.changed.emit()

    @Slot(float)
    def setReactionIntensity(self, value):
        if not math.isfinite(value): return
        self._reaction_intensity = max(0.,min(1.,value))
        self._settings.setValue('reactionIntensity',self._reaction_intensity)
        self.changed.emit()

    def _sync_active(self):
        background = self._reaction_mode == 'all' and (
            self._capture_requested if self._input == 'system' else self.playing)
        active = not self._closed and (self._music_open or background)
        if active == self._active: return
        self._active = active
        self.worker.reset()
        if active:
            self._last_tick = time.monotonic()
            self.timer.start()
            if self._input == 'system' and self._capture_requested: self._start_capture()
        else:
            self._stop_capture()
            self.timer.stop()
            self._clear_analysis()
        self.changed.emit()

    @Slot()
    def refreshDevices(self):
        try:
            self._devices = LoopbackCapture.devices()
        except Exception as exc:
            self._devices = []
            self._status = f'Windows output capture unavailable: {type(exc).__name__}'
        self.devicesChanged.emit()
        self.changed.emit()

    @Slot()
    def _devices_changed(self):
        if self._active:
            self.refreshDevices()
            if self._input == 'system' and self._capture_state in ('active','starting'):
                self._start_capture()
        else: self.devicesChanged.emit()

    @Slot(str)
    def setInput(self, source):
        if source not in ('player','system') or source == self._input: return
        self.userAction.emit()
        if not self._stop_capture(): return
        self._input = source
        self._capture_requested = source == 'system'
        if source == 'system': self.refreshDevices()
        self.worker.reset()
        self._clear_analysis()
        self._status = 'Analyzing E.V. playback.' if source == 'player' else 'Windows output selected.'
        self._sync_active()
        if source == 'system' and self._active and self.capture is None: self._start_capture()
        self.changed.emit()

    @Slot()
    def startCapture(self):
        if self._input != 'system' or self._closed: return
        self.userAction.emit()
        self._capture_requested = True
        was_active = self._active
        self._sync_active()
        if was_active and self._active: self._start_capture()

    def _start_capture(self):
        if not self._active or not self._capture_requested or self._closed: return
        if not self._stop_capture(): return
        self._capture_generation += 1
        generation = self._capture_generation
        def consume(pcm, rate):
            if generation == self._capture_generation and self._active and self._input == 'system':
                self.worker.push(pcm,rate)
        self.capture = LoopbackCapture(consume, lambda state,detail:self._captureMessage.emit(generation,state,detail))
        self._capture_state = 'starting'
        self._status = 'Connecting to Windows output…'
        self.capture.start(self._device_id)
        self.changed.emit()

    @Slot(result=bool)
    def stopCapture(self):
        self._capture_requested = False
        stopped = self._stop_capture()
        self._sync_active()
        return stopped

    def _stop_capture(self):
        self._capture_generation += 1
        if self.capture:
            try:
                self.capture.stop()
            except RuntimeError:
                self._capture_state = 'error'
                self._status = 'Audio device is still closing. Reconnect when it becomes available.'
                self.worker.reset()
                self._clear_analysis()
                self.changed.emit()
                return False
            self.capture = None
        self._capture_state = 'off'
        if self._input == 'system':
            self.worker.reset()
            self._clear_analysis()
            self._status = 'Output capture stopped.'
        self.changed.emit()
        return True

    @Slot(int,str,str)
    def _capture_message(self, generation, state, detail):
        if generation != self._capture_generation: return
        self._capture_state = state
        self._status = ('Listening to output · ' if state == 'active' else 'Capture unavailable · ')+detail
        self.changed.emit()

    @Slot(int)
    def setCaptureDevice(self, device_id):
        if device_id != -1 and device_id not in [d['id'] for d in self._devices]: return
        self._device_id = device_id
        self.devicesChanged.emit()
        if self._active and self._input == 'system' and self._capture_requested: self._start_capture()

    @Slot(int)
    def setOutputDevice(self, index):
        devices = QMediaDevices.audioOutputs()
        if not 0 <= index <= len(devices): return
        self.output.setDevice(QMediaDevices.defaultAudioOutput() if index == 0 else devices[index-1])
        self.worker.reset()
        self.changed.emit()

    @Slot('QVariantList')
    def addFiles(self, urls):
        accepted = []
        for raw in urls:
            url = raw if isinstance(raw,QUrl) else QUrl(str(raw))
            if not url.isLocalFile(): continue
            path = Path(url.toLocalFile())
            if path.is_file() and path.suffix.lower() in ('.mp3','.wav','.flac','.aac','.m4a','.ogg','.opus','.aif','.aiff','.wma'):
                accepted.append({'path':str(path),'title':path.stem})
        if not accepted:
            self._status = 'Choose a readable local audio file.'
            self.changed.emit(); return
        self.userAction.emit()
        first = len(self._queue)
        self._queue.extend(accepted)
        self.changed.emit()
        self.playIndex(first)

    @Slot(int)
    def playIndex(self, index):
        if not 0 <= index < len(self._queue): return
        self.userAction.emit()
        self.player.stop()
        self._index = index
        self.worker.reset()
        self.player.setSource(QUrl.fromLocalFile(self._queue[index]['path']))
        self.player.play()
        self.changed.emit()

    @Slot()
    def togglePlayback(self):
        self.userAction.emit()
        if self.playing: self.player.pause()
        elif self.hasTrack: self.player.play()

    @Slot()
    def stop(self):
        self.player.stop()
        if self._input == 'player':
            self.worker.reset()
            self._clear_analysis()

    @Slot()
    def next(self): self.playIndex(self._index+1)
    @Slot()
    def previous(self):
        if self.position > 3000: self.seek(0)
        else: self.playIndex(max(0,self._index-1))
    @Slot(float)
    def seek(self, milliseconds):
        if self.seekable and math.isfinite(milliseconds):
            self.worker.reset()
            self.player.setPosition(int(max(0,min(self.duration,milliseconds))))
    @Slot(float)
    def setVolume(self, value):
        if not math.isfinite(value): return
        self.output.setVolume(max(0,min(1,value)))
        self._settings.setValue('volume',self.volume)
        self.changed.emit()
    @Slot(bool)
    def setMuted(self, value):
        self.output.setMuted(value)
        self.changed.emit()

    @Slot()
    def _playback_changed(self):
        if self._input == 'player' and not self.playing:
            self.worker.reset()
        self._sync_active()
        self.changed.emit()

    def _media_status(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            if self._index+1 < len(self._queue):
                self.next()
                return
        if self._input == 'player':
            self._status = {QMediaPlayer.MediaStatus.LoadingMedia:'Loading audio…',
                QMediaPlayer.MediaStatus.BufferingMedia:'Buffering…',
                QMediaPlayer.MediaStatus.BufferedMedia:'Local playback · measured audio',
                QMediaPlayer.MediaStatus.LoadedMedia:'Ready to play.',
                QMediaPlayer.MediaStatus.EndOfMedia:'End of queue.'}.get(status,self._status)
        self.changed.emit()

    def _error(self, error, message):
        self._status = 'Playback error · '+message
        if self._input == 'player': self.worker.reset()
        self.changed.emit()

    def _pcm(self, buffer):
        if not self._active or self._input != 'player' or not self.playing or not buffer.isValid(): return
        fmt = buffer.format()
        types = {QAudioFormat.SampleFormat.Float:np.float32,QAudioFormat.SampleFormat.Int16:np.int16,
                 QAudioFormat.SampleFormat.Int32:np.int32,QAudioFormat.SampleFormat.UInt8:np.uint8}
        dtype = types.get(fmt.sampleFormat())
        if dtype is None or fmt.channelCount() <= 0: return
        pcm = np.frombuffer(buffer.constData(),dtype=dtype,count=buffer.sampleCount()).astype(np.float32)
        if dtype == np.uint8: pcm = (pcm-128)/128
        elif dtype == np.int16: pcm /= 32768
        elif dtype == np.int32: pcm /= 2147483648
        self.worker.push(pcm.reshape(-1,fmt.channelCount()),fmt.sampleRate(),start_time=time.monotonic())

    def _clear_analysis(self):
        self._beat.value=0.
        self._bands = [0.]*64
        self._wave = [0.]*160
        self._values = dict(rms=0.,peak=0.,bass=0.,mid=0.,treble=0.)
        self.analysisChanged.emit()

    @Slot()
    def _tick(self):
        now = time.monotonic()
        dt = min(.15,now-self._last_tick)
        self._last_tick = now
        frame = self.worker.latest()
        valid = frame and now-frame['timestamp'] < .25
        gain = (0 if self.muted else self.volume) if self._input == 'player' else 1.
        if self._input == 'player' and not self.playing: valid = False
        self._beat.update(dt,self.worker.take_onsets(now),gain,bool(valid))
        # Local decode measurements are adjusted by E.V.'s volume, not the Windows master gain.
        targets = np.asarray(frame['bands']) if valid and gain > 0 else np.zeros(64)
        if valid and gain > 0:
            targets = np.clip(targets+20*math.log10(gain)/80,0,1)
        old = np.asarray(self._bands)
        tau = np.where(targets>old,.025,.16)
        self._bands = (old+(targets-old)*(1-np.exp(-dt/tau))).tolist()
        self._wave = (np.asarray(frame['waveform'])*gain).tolist() if valid else [0.]*160
        for name in self._values:
            target = frame[name]*gain if valid else 0.
            tau = .025 if target>self._values[name] else .16
            self._values[name] += (target-self._values[name])*(1-math.exp(-dt/tau))
        self.analysisChanged.emit()

    @Slot()
    def close(self):
        if self._closed: return
        self._closed = True
        self.timer.stop()
        self.stopCapture()
        self.player.stop()
        self.worker.close()
        self._settings.sync()
