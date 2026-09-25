"""One-shot presentation audio. Does not modify the voice or authority systems."""
import logging
import math
import os
from pathlib import Path

from PySide6.QtCore import QObject, Property, QCoreApplication, QSettings, QTimer, QUrl, Signal, Slot
from PySide6.QtMultimedia import QSoundEffect
from PySide6.QtGui import QWindow

ASSETS = Path(__file__).resolve().parent / 'assets' / 'startup'
logger = logging.getLogger(__name__)


class StartupAudio(QObject):
    settingsChanged = Signal()
    phaseChanged = Signal(str)

    def __init__(self, model, bridge, *, settings=None, effect_factory=QSoundEffect):
        super().__init__(model)
        self.model = model
        self.bridge = bridge
        self.settings = settings if settings is not None else QSettings('EV', 'CinematicStartup')
        self._muted = str(self.settings.value('muted', False)).lower() in ('true', '1')
        self._volume = self._bounded_volume(self.settings.value('volume', 0.55))
        self._disabled = os.getenv('EV_STARTUP_AUDIO', 'true').strip().lower() in ('false', '0', 'off')
        self._phase = 'pending'
        self._armed = False
        self._window = None
        self._effects = {}
        for name in ('rise', 'arrival'):
            effect = effect_factory(self)
            effect.setLoopCount(1)
            effect.setVolume(self._volume)
            effect.statusChanged.connect(self._advance)
            self._effects[name] = effect
            effect.setSource(QUrl.fromLocalFile(str(ASSETS / (name + '.wav'))))
        self._effects['arrival'].playingChanged.connect(self._arrival_finished)
        self._deadline = QTimer(self)
        self._deadline.setSingleShot(True)
        self._deadline.setInterval(12000)
        self._deadline.timeout.connect(self.cancel)
        model.frameChanged.connect(self._advance)
        model.settingsChanged.connect(self._check_animation)
        model.listeningRequested.connect(self.cancel)
        bridge.taskSubmitted.connect(self.cancel)
        for signal in (bridge.visualStateChanged, bridge.approvalPendingChanged,
                       bridge.lifecycleActiveChanged, bridge.voiceActivityChanged,
                       bridge.speakingActivityChanged):
            signal.connect(self._check_busy)
        app = QCoreApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.cancel)

    @staticmethod
    def _bounded_volume(value):
        try:
            value = float(value)
            return max(0., min(1., value)) if math.isfinite(value) else 0.55
        except (ValueError, TypeError):
            return 0.55

    @Property(bool, notify=settingsChanged)
    def muted(self):
        return self._muted

    @Property(float, notify=settingsChanged)
    def volume(self):
        return self._volume

    @Slot(bool)
    def setMuted(self, value):
        self._muted = bool(value)
        self.settings.setValue('muted', self._muted)
        self.settings.sync()
        if self._muted:
            self.cancel()
        self.settingsChanged.emit()

    @Slot(float)
    def setVolume(self, value):
        self._volume = self._bounded_volume(value)
        for effect in self._effects.values():
            effect.setVolume(self._volume)
        self.settings.setValue('volume', self._volume)
        self.settings.sync()
        if self._volume == 0:
            self.cancel()
        self.settingsChanged.emit()

    def attach_window(self, window):
        self._window = window
        window.frameSwapped.connect(self._first_frame)
        window.visibleChanged.connect(self._check_window)
        window.visibilityChanged.connect(self._check_window)
        window.closing.connect(self.cancel)

    @Slot()
    def _first_frame(self):
        if self._armed:
            return
        self._armed = True
        self._deadline.start()
        self._advance()

    def _set_phase(self, phase):
        self._phase = phase
        self.phaseChanged.emit(phase)

    def _busy(self):
        return (self.bridge.approvalPending or self.bridge.lifecycleActive
                or self.bridge.voiceActivity or self.bridge.speakingActivity
                or self.bridge.visualState in ('LISTENING', 'SPEAKING', 'THINKING',
                    'PROCESSING', 'EXECUTING', 'VERIFYING', 'WAITING_FOR_APPROVAL'))

    @Slot()
    def _check_busy(self, *args):
        if self._busy():
            self.cancel()

    @Slot()
    def _check_animation(self):
        if not self.model.animationEnabled:
            self.cancel()

    @Slot()
    def _check_window(self, *args):
        if self._window is not None and (not self._window.isVisible() or self._window.visibility() == QWindow.Visibility.Minimized):
            self.cancel()

    @Slot()
    def _advance(self):
        if not self._armed or self._phase in ('complete', 'cancelled'):
            return
        if self._disabled or self._muted or self._volume == 0 or self._busy() or not self.model.animationEnabled:
            self.cancel()
            return
        progress = self.model.launchProgress
        if self._phase == 'pending':
            # A slow/missing audio device must never delay the core or announce late.
            if progress > 0.12:
                self.cancel()
                return
            statuses = [effect.status() for effect in self._effects.values()]
            if QSoundEffect.Status.Error in statuses:
                logger.info('Startup audio unavailable; continuing silently')
                self.cancel()
                return
            if not all(status == QSoundEffect.Status.Ready for status in statuses):
                return
            self._set_phase('rise')
            self._effects['rise'].play()
        if self._phase == 'rise' and progress >= 1.0:
            self._effects['rise'].stop()
            self._set_phase('arrival')
            self._effects['arrival'].play()

    @Slot()
    def _arrival_finished(self):
        if self._phase == 'arrival' and not self._effects['arrival'].isPlaying():
            self._deadline.stop()
            self._set_phase('complete')

    @Slot()
    def cancel(self):
        if self._phase in ('complete', 'cancelled'):
            return
        self._set_phase('cancelled')
        self._deadline.stop()
        for effect in self._effects.values():
            effect.stop()
