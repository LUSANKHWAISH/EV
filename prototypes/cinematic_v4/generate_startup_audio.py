"""Build the fixed startup signature locally; no generation work at app startup."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import wave

import numpy as np

ROOT = Path(__file__).resolve().parent
DEST = ROOT / 'assets' / 'startup'
RATE = 48000
RNG = np.random.default_rng(160926)


def write_wave(path, data):
    data = np.asarray(data)
    if data.ndim == 1:
        data = np.column_stack((data, data))
    assert np.max(np.abs(data)) < 0.99
    with wave.open(str(path), 'wb') as stream:
        stream.setnchannels(data.shape[1])
        stream.setsampwidth(2)
        stream.setframerate(RATE)
        stream.writeframes((data * 32767).astype('<i2').tobytes())


def fades(signal, attack=.012, release=.12):
    signal = signal.copy()
    a, r = int(attack * RATE), int(release * RATE)
    attack_gain = np.linspace(0, 1, a) ** 2
    release_gain = np.linspace(1, 0, r) ** 2
    signal[:a] *= attack_gain[:, None] if signal.ndim == 2 else attack_gain
    signal[-r:] *= release_gain[:, None] if signal.ndim == 2 else release_gain
    return signal


def air(count, low=180, high=4800):
    frequency = np.fft.rfftfreq(count, 1 / RATE)
    spectrum = np.fft.rfft(RNG.normal(size=count))
    spectrum *= (1 - np.exp(-(frequency / low) ** 4)) * np.exp(-(frequency / high) ** 2)
    result = np.fft.irfft(spectrum, n=count)
    return result / max(1e-9, np.std(result))


def stereo(signal, wet=.12):
    result = np.column_stack((signal, signal))
    for delay, gain, channel in ((.047, wet, 0), (.071, wet, 1), (.137, wet*.55, 0), (.193, wet*.4, 1)):
        n = int(delay * RATE)
        result[n:, channel] += signal[:-n] * gain
    return result


def read_voice():
    path = DEST / 'voice_source.wav'
    # Build-time System.Speech output only. No microphone or core/tts.py involved.
    script = '''
Add-Type -AssemblyName System.Speech
$evStartupSynth = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $evStartupSynth.SelectVoice('Microsoft David Desktop')
    $evStartupSynth.SetOutputToWaveFile($env:EV_STARTUP_VOICE_DEST)
    $evStartupSynth.SpeakSsml('<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US"><prosody rate="-8%" pitch="-5%"><say-as interpret-as="characters">EV</say-as><break time="160ms"/>online.</prosody></speak>')
} finally { $evStartupSynth.Dispose() }
'''
    environment = os.environ.copy()
    environment['EV_STARTUP_VOICE_DEST'] = str(path)
    subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
                   env=environment, check=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
    with wave.open(str(path), 'rb') as stream:
        assert stream.getsampwidth() == 2
        original_rate = stream.getframerate()
        data = np.frombuffer(stream.readframes(stream.getnframes()), dtype='<i2').astype(float) / 32768
        data = data.reshape(-1, stream.getnchannels()).mean(axis=1)
    active = np.flatnonzero(np.abs(data) > .004)
    assert active.size > 0
    data = data[max(0, active[0]-int(original_rate*.025)):min(len(data), active[-1]+int(original_rate*.08))]
    output = np.interp(np.arange(round(len(data)*RATE/original_rate))*original_rate/RATE, np.arange(len(data)), data)
    # Gentle saturation keeps the fixed phrase present above the fading impact.
    output = np.tanh(output / max(np.max(np.abs(output)), 1e-9) * 1.4)
    return fades(output / np.max(np.abs(output)) * .68, .012, .08)


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    voice = read_voice()
    t = np.arange(round(3.2 * RATE)) / RATE
    u = t / 3.2
    sweep = np.sin(2*np.pi*(85*t + 34*t*t + 5*t*t*t))
    body = sum(np.sin(2*np.pi*f*t + .3*np.sin(t*(i+1))) / (i+1)
               for i, f in enumerate((65.406, 98., 130.813, 196.)))
    breath = air(len(t)) * (.017 + .055*u*u)
    propulsion = .065*air(len(t), 350, 6500)*np.exp(-((t-.27)/.18)**2)
    pulse = .8 + .2*np.sin(2*np.pi*(2*t + t*t))
    rise = fades((.085*body + .10*sweep*u)*np.sin(np.pi*u/2)**1.6*pulse + breath*u + propulsion, .04, .1)
    rise = fades(stereo(rise, .22), .01, .1)
    write_wave(DEST / 'rise.wav', rise)

    t = np.arange(round(max(3.6, .42 + len(voice)/RATE + .9) * RATE)) / RATE
    impact = .32*np.sin(2*np.pi*(46*t+9*(1-np.exp(-7*t))))*np.exp(-3.8*t)
    impact += .13*np.sin(2*np.pi*98*t)*np.exp(-3.1*t)
    impact += .055*air(len(t), 180, 5500)*np.exp(-7*t)
    shimmer = sum(np.sin(2*np.pi*f*t)/(i+1) for i,f in enumerate((523.25, 784., 1046.5)))
    impact += .03*shimmer*np.exp(-1.9*t)
    arrival = stereo(fades(impact, .008, .3), .2)
    offset = int(.42*RATE)
    spoken = stereo(np.pad(voice, (0, int(.7*RATE))), .085)
    arrival[offset:offset+len(spoken)] += spoken
    arrival = fades(arrival, .008, .2)
    peak = np.max(np.abs(arrival))
    if peak > .85:
        arrival *= .85 / peak
    write_wave(DEST / 'arrival.wav', arrival)
    evidence = ROOT / 'evidence' / 'startup_audio'
    evidence.mkdir(parents=True, exist_ok=True)
    write_wave(evidence / 'startup-preview.wav', np.concatenate((rise, arrival)))
    manifest = {'voice':'Microsoft David Desktop', 'spoken_text':'E.V. online.',
                'generation':'Local System.Speech fixed phrase + original NumPy synthesis; no film audio.',
                'sample_rate':RATE, 'channels':2, 'sample_width_bytes':2,
                'arrival_voice_offset_seconds':.42, 'files':{}}
    for name, data in (('rise.wav', rise), ('arrival.wav', arrival)):
        manifest['files'][name] = {'seconds':len(data)/RATE, 'peak_dbfs':float(20*np.log10(np.max(np.abs(data)))),
                                 'rms_dbfs':float(20*np.log10(np.sqrt(np.mean(data**2)))),
                                 'sha256':hashlib.sha256((DEST/name).read_bytes()).hexdigest()}
    (DEST/'manifest.json').write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
