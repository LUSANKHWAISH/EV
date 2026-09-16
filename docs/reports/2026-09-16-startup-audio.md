# Cinematic startup audio — complete

The main E.V. cinematic interface now plays an original energy rise during the approved core projection, followed by a soft arrival impact and a male “E.V. online.” announcement. The fixed local sequence lasts approximately 6.8 seconds. It works while conversational TTS remains disabled.

Open the gear icon → Interface settings → Startup sound to mute it or adjust its separate volume. Defaults: on, 55%. Preferences persist across launches. Replay core projection remains silent. No core mesh, shader, motion, palette, launcher or backend source was modified.

## Implementation

- `prototypes/cinematic_v4/startup_audio.py`: Qt output-only playback controller, synchronized to first presentation and actual launch completion. It plays once per app window and yields to tasks, approval, bridge voice/speaking activity, listening requests, pause, hide/minimize, close, mute and shutdown. Audio loading failure never blocks the interface.
- `prototypes/cinematic_v4/integration.py`: attaches the controller to the connected model/window.
- `prototypes/cinematic_v4/qml/CinematicStage.qml`: persistent startup mute and volume controls, styled to the existing interface. Standalone preview stays silent.
- `prototypes/cinematic_v4/assets/startup/`: two stereo PCM playback assets, build voice source, manifest and documentation. The installed Microsoft David Desktop voice generated only the fixed phrase at build time; runtime needs no synthesis process, microphone or network. Effects are original procedural synthesis.
- New asset generator, focused tests and bounded rendered/main-app validation helpers are included.

## Verification

- 25 focused tests passed in 0.99 seconds: sequencing, one-shot behavior, cancellation, settings persistence, unavailable/late audio, bounded volume, valid PCM and clean asset edges.
- 12 rendered checks passed: both assets reached Qt's playing state, arrival followed launch completion, completed playback, actual mute button and volume slider, saved settings, silent visual replay, no command emission and no QML errors. Settings inspected at 1920×1080 and 1100×760.
- 22 existing bridge/overlay integration checks passed, including approval input ownership and provider overlay behavior.
- Actual `gui.app` startup passed with its normal threaded renderer, native chrome and observational subsystems. Rise began at 5.833 seconds after process bootstrap, arrival at 9.047 seconds and playback finished at 12.649 seconds. Core launch progress was exactly 1 at arrival. Clean exit and no callback/QML errors in the final run.
- One shutdown signal conversion error and an asset-tail discontinuity were found during development and corrected before the final passing runs.

Playback was verified through Windows **Remote Audio**. This confirms device playback and timing, not a subjective listening judgment or physical speaker loudness. FPS was not benchmarked for this audio-only change. Source WAV peaks remain below clipping; nominal rise/arrival durations are 3.2 and 3.6 seconds.

## Backup and source audit

Before edits, 419 existing files were copied and SHA256-verified at:

`D:\EV\.ev-cinematic-nucleus-backups\20260916-155207-before-startup-audio`

Only two existing files changed: `integration.py` and `qml/CinematicStage.qml`. All 352 protected source files, including `core/tts.py`, `core/voice_manager.py`, `gui/app.py` and `gui/bridge.py`, remain unchanged. The accepted core geometry, shaders, motion and palette remain unchanged.

Source manifest: `prototypes/cinematic_v4/evidence/startup_audio/source_manifest.json`

SHA256: `fd640ebbc537921988bb2da67613ab5e067ee25c0580f0388b81116f44de783d`

Full evidence, sound preview, screenshots, timings and test records are in `prototypes/cinematic_v4/evidence/startup_audio/`.

Rollback: restore only the two changed existing files from this backup. The added audio/controller files then become unreferenced. Do not restore unrelated backend files over future work.

## Git and next step

No commit created; existing unrelated working-tree changes were preserved. Open `D:\EV\Launch EV.cmd` to hear the startup. Review voice character and sound intensity; both can be refined independently of the accepted core visuals.
