"""WASAPI render-endpoint capture. Never sends captured audio to an output."""
import threading

import numpy as np


class LoopbackCapture:
    def __init__(self, consume, status):
        self.consume = consume
        self.status = status
        self._stop = threading.Event()
        self._thread = None

    @staticmethod
    def devices():
        import pyaudiowpatch as pa
        with pa.PyAudio() as audio:
            return [{'id':int(d['index']), 'label':d['name'], 'rate':int(d['defaultSampleRate']),
                     'channels':int(d['maxInputChannels'])} for d in audio.get_loopback_device_info_generator()]

    def start(self, device_id=-1):
        self.stop()
        self._stop.clear()
        self._thread = threading.Thread(target=self._capture, args=(device_id,), name='EV-MusicLoopback', daemon=True)
        self._thread.start()

    def _capture(self, device_id):
        try:
            import pyaudiowpatch as pa
            with pa.PyAudio() as audio:
                device = audio.get_default_wasapi_loopback() if device_id < 0 else audio.get_device_info_by_index(device_id)
                if not device.get('isLoopbackDevice'):
                    raise ValueError('The selected device is not a Windows output loopback')
                channels, rate = int(device['maxInputChannels']), int(device['defaultSampleRate'])
                def callback(data, frame_count, time_info, flags):
                    if self._stop.is_set():
                        return (None, pa.paComplete)
                    self.consume(np.frombuffer(data, dtype='<f4').reshape(-1, channels), rate)
                    return (None, pa.paContinue)
                with audio.open(format=pa.paFloat32, channels=channels, rate=rate, input=True,
                                input_device_index=device['index'], frames_per_buffer=1024,
                                stream_callback=callback) as stream:
                    self.status('active', device['name'])
                    while not self._stop.wait(.1):
                        if not stream.is_active():
                            raise RuntimeError('Output capture stopped; reconnect the device')
        except Exception as exc:
            if not self._stop.is_set():
                self.status('error', f'{type(exc).__name__}: {exc}')

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)
            if self._thread.is_alive():
                raise RuntimeError('Audio device is still closing; retry shortly')
        self._thread = None
