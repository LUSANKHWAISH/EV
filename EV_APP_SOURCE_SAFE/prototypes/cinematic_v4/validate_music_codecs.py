"""Decode real local codecs and check queue advancement without audible output."""
import json
from pathlib import Path
import wave

import numpy as np
from PySide6.QtCore import QCoreApplication,QSettings,QTimer,QUrl
from music.session import MusicSession

DEST=Path(__file__).resolve().parent/'evidence/music_foundation'


def main():
    app=QCoreApplication([])
    settings=QSettings(str(DEST/'codec-settings.ini'),QSettings.Format.IniFormat)
    session=MusicSession(settings=settings)
    session.set_active(True);session.setVolume(0)
    results=[];pending=['mp3','flac']
    def load():
        if not pending:
            queue_test();return
        suffix=pending.pop(0)
        before=session.worker.processed
        session.addFiles([QUrl.fromLocalFile(str(DEST/('fixture.'+suffix)))])
        def check():
            frame=session.worker.latest()
            results.append({'format':suffix,'passed':session.playing and session.position>500 and session.duration>11000 and session.worker.processed>before and frame is not None and frame['rms']>.01,
                            'duration_ms':session.duration,'decoded_rms':frame['rms'] if frame else None})
            load()
        QTimer.singleShot(2200,check)
    def queue_test():
        session.stop();session._queue=[];session._index=-1
        for name in ('short-a','short-b'):
            p=DEST/(name+'.wav');sr=48000;t=np.arange(int(.45*sr))/sr
            pcm=(np.sin(2*np.pi*750*t)*.05*32767).astype('<i2')
            with wave.open(str(p),'wb') as stream:
                stream.setnchannels(1);stream.setsampwidth(2);stream.setframerate(sr);stream.writeframes(pcm.tobytes())
        session.addFiles([QUrl.fromLocalFile(str(DEST/(n+'.wav'))) for n in ('short-a','short-b')])
        QTimer.singleShot(2400,finish)
    def finish():
        results.append({'format':'queue','passed':session.currentIndex==1 and not session.playing,'current_index':session.currentIndex})
        session.close()
        report={'passed':all(row['passed'] for row in results),'results':results}
        (DEST/'codecs.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
        app.exit(0 if report['passed'] else 1)
    load();QTimer.singleShot(15000,app.quit)
    result=app.exec();session.close();return result


if __name__=='__main__':raise SystemExit(main())
