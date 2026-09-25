"""Bounded VLC/Chrome output-capture proof; only generated test audio is played."""
import json
from pathlib import Path
import subprocess
import time

import psutil

from music.analysis import AnalysisWorker
from music.loopback import LoopbackCapture

DEST=Path(__file__).resolve().parent/'evidence/music_foundation'


def main():
    fixture=DEST/'fixture.wav'
    page=DEST/'browser_audio.html'
    page.write_text('<!doctype html><title>E.V. local audio capture test</title><audio autoplay loop controls src="fixture.wav"></audio>')
    programs={
        'vlc':['C:/Program Files/VideoLAN/VLC/vlc.exe','--intf','dummy','--no-one-instance','--no-video','--play-and-exit','--no-loop','--no-repeat','--no-metadata-network-access',str(fixture)],
        'chrome':['C:/Program Files/Google/Chrome/Application/chrome.exe','--headless=new','--autoplay-policy=no-user-gesture-required','--no-first-run','--no-default-browser-check','--disable-extensions','--user-data-dir='+str(DEST/'chrome_test_profile'),page.as_uri()]
    }
    results={}
    for name,command in programs.items():
        worker=AnalysisWorker();events=[];samples=[];process=None
        capture=LoopbackCapture(worker.push,lambda state,detail:events.append({'state':state,'detail':detail}))
        try:
            capture.start()
            time.sleep(.6)
            process=subprocess.Popen(command,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
            started=time.monotonic()
            while time.monotonic()-started<4.5:
                frame=worker.latest()
                if frame:samples.append({'rms':frame['rms'],'peakHz':frame['peakHz'],'age':time.monotonic()-frame['timestamp']})
                time.sleep(.1)
            matches=[s for s in samples if s['rms']>.005 and abs(s['peakHz']-440)<30 and s['age']<.3]
            results[name]={'passed':len(matches)>5,'capture_events':events,'matching_samples':len(matches),'samples':len(samples),
                           'max_rms':max((s['rms'] for s in samples),default=0),'observed_frequency_hz':matches[-1]['peakHz'] if matches else None}
        except Exception as exc:results[name]={'passed':False,'error':str(exc)}
        finally:
            if process:
                try:
                    owned=psutil.Process(process.pid)
                    children=owned.children(recursive=True)
                    owned.terminate()
                    for child in children:
                        try:child.terminate()
                        except psutil.Error:pass
                    psutil.wait_procs([owned]+children,timeout=3)
                except psutil.Error:pass
            capture.stop();worker.close()
    report={'scope':'Separate VLC process and separate headless Chrome profile playing generated local WAV. Selected Windows output loopback, no microphone and no captured audio saved. This verifies browser audio, not the YouTube website or a cloud-provider integration.',
            'passed':all(r['passed'] for r in results.values()),'results':results}
    (DEST/'external_capture.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report),flush=True)
    return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
