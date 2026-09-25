import sys
sys.path.insert(0, r"D:\EV")

import sounddevice as sd
import numpy as np
import threading
import time

from core.tts import WindowsSAPIProvider

INPUT_DEVICE = 1

print("Input:", sd.query_devices(INPUT_DEVICE)["name"])
print("Starting microphone capture...")
print("DO NOT SPEAK.")

result_audio = []

def record():
    x = sd.rec(
        int(7 * 16000),
        samplerate=16000,
        channels=1,
        dtype="int16",
        device=INPUT_DEVICE
    )
    sd.wait()
    result_audio.append(x)

thread = threading.Thread(target=record)
thread.start()

time.sleep(1)

print("E.V. SPEAKING NOW...")
tts = WindowsSAPIProvider()

result = tts.speak(
    "This is E V. If you can hear me, the microphone may also hear me.",
    "feedback-test-002"
)

print("TTS RESULT:", result)
print("Waiting for microphone capture...")
thread.join()

audio = result_audio[0].astype(np.float32).reshape(-1)

# Analyze the period where TTS was expected
rms = float(np.sqrt(np.mean(audio * audio)))
peak = int(np.max(np.abs(audio)))

print()
print("CAPTURE COMPLETE")
print("RMS:", round(rms, 2))
print("Peak:", peak)
print("Non-zero:", int(np.count_nonzero(audio)))
