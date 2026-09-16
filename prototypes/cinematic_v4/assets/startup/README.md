# E.V. startup signature

`rise.wav` is a 3.2-second original procedural energy rise. `arrival.wav` is a soft impact, the fixed phrase “E.V. online.” at +0.42 seconds, and a short stereo tail. Nominal total: 6.8 seconds. Both are stereo 48 kHz 16-bit PCM, decoded ahead of the first presentation; no generation or external request occurs during launch.

The male announcement was generated locally using the installed Microsoft David Desktop voice. `voice_source.wav` is the build source; the runtime plays only `rise.wav` and `arrival.wav`. No film recording, voice clone or microphone recording is used. Regenerate with `python -m prototypes.cinematic_v4.generate_startup_audio` on a Windows machine with that voice installed and NumPy available.

In the main app, open the gear icon → Interface settings → Startup sound. Default volume is 55%; mute and volume persist in QSettings under `EV/CinematicStartup`. This adjusts only startup audio. Windows output device and master volume still apply. `EV_STARTUP_AUDIO=false` suppresses startup audio for automated runs without changing saved preferences.

Playback starts once after the window presents. Arrival follows the existing core projection's completion. Pause, hide/minimize, window close, task submission, approval, listening request, bridge voice activity or speaking activity cancels the remaining sound. Unmuting and Replay core projection do not restart it. Missing/late audio fails silently; it never blocks launch. The standalone visual preview remains silent.

This is fixed presentation audio, not a replacement for `core/tts.py` and not measured microphone or speech telemetry. It consumes existing bridge activity to yield to voice; it does not add wake-word controls or enable conversational TTS.
