# ASTRA HANDOFF — current E.V. state

Snapshot date: 16 September 2026. Workspace: `D:\EV`. Git origin: `https://github.com/LUSANKHWAISH/EV.git` (private when inspected). Starting HEAD before this checkpoint: `8237dbbf7055826806ee82b62520e1e88841d248`, branch `master`. See [checkpoint record](docs/handoff/ASTRA_CHECKPOINT.md) and `git log -1` for the final commit.

## What the next agent must understand first

The user has accepted the cinematic golden nucleus and main interface, the Music foundation, beat reaction in both modes, startup sound and the restyled provider dialog. Continue from these files. Do not rebuild the accepted core from a generic sphere tutorial. The next requested product work is a real EQ, more instruments and multiple arranged visualizers. This handoff contains plans, not those new features.

The working tree also contained earlier provider, bridge, voice-telemetry and classic-interface changes before the Astra cinematic stages. A runnable checkpoint needs their dependencies. The Git checkpoint therefore preserves the current application with **inherited integration work explicitly acknowledged**, rather than asserting that every line was authored by Astra. Old scratch scripts, large previous backup trees, credentials, runtime databases, capture profiles and reference videos are not release content.

## Current environment and launch

- Windows 10 Pro build 19045; NVIDIA GTX 970; approximately 32 GB system RAM.
- Existing Python: `D:\EV\.venv\Scripts\python.exe`, Python 3.12; PySide6 6.11.2 observed.
- Qt Quick/QML/Qt Quick 3D presentation; Python backend; NumPy analysis; PyAudioWPatch 0.2.12.8 for WASAPI output capture.
- Normal GUI: `Launch EV.cmd` or `python -m gui.app` from the activated project environment. `--cinematic` is explicit but no longer required. `--classic` opens the previous interface.
- `Launch Cinematic Preview.cmd` is an isolated preview, not a substitute for testing the connected application.

```powershell
Set-Location D:\EV
.\.venv\Scripts\python.exe -B -m gui.app
# Previous interface, if needed:
.\.venv\Scripts\python.exe -B -m gui.app --classic
```

For a new checkout, first create Python 3.12's virtual environment and install `requirements.txt`. Audit optional imports before calling the environment reproducible: the present requirements are not a complete lockfile. The existing GUI imports `httpx` and `psutil`; tests need `pytest`. Voice has additional optional packages/model files (`sounddevice`, `faster-whisper`, ONNX/openWakeWord and their dependencies). Do not automatically install CUDA, PyTorch or giant voice models just to work on Music. Record a minimal verified install and separate optional voice requirements in a later packaging task. Do not copy `.venv` between machines.

## Source ownership map

| Files | Responsibility |
|---|---|
| `gui/app.py` | Main bootstrap, providers, pipeline wiring, cinematic/default selection. |
| `gui/bridge.py`, `gui/visual_state.py` | Canonical UI state, queued events, visual priority, provider and approval surfaces. |
| `core/action_pipeline.py`, `core/orchestrator.py` | Canonical planning/execution path; do not bypass for new actions. |
| `core/plan_validator.py`, `core/risk.py`, `core/plan_executor.py` | Validation, risk/permission boundary and execution sequencing. |
| `core/agent.py`, `core/verifier.py`, `core/backup.py` | Approved tool dispatch, result verification and recovery support. |
| `core/paths.py` | Resource and runtime-data locations; new persistence belongs here, not hardcoded drive paths. |
| `core/provider_config.py`, `providers/` | Provider configuration/protocol adapters and protected credentials. |
| `prototypes/cinematic_v4/integration.py` | Connected presentation adapter. Despite the folder name, it is used by the main app. |
| `prototypes/cinematic_v4/qml/CinematicStage.qml` | Main layout, settings drawer, Music switching, core position and reaction priority. |
| `.../qml/ConnectedWindow.qml` | Main window and existing provider/approval layers (z=80/100). |
| `.../qml/NucleusScene.qml`, `NucleusView.qml`, `CoreMotion.qml`, `shaders/` | Accepted core, motion and rendering. Preserve their appearance. |
| `.../geometry.py`, `assets/`, `generate_*` | Batched meshes, instances and reproducible procedural assets. |
| `music/session.py` | Current playback, loopback ownership, queue and measured analysis properties. |
| `music/analysis.py`, `music/onsets.py`, `music/loopback.py` | Bounded worker, measured FFT/onset envelopes and Windows capture. |
| `.../qml/MusicWorkspace.qml`, `MusicReactionSettings.qml` | Music transport/spectrum and saved reaction controls. |
| `.../startup_audio.py`, `assets/startup/` | Fixed “E.V. online” startup signature and original procedural sounds. |
| `gui/qml/components/EVSettingsOverlay.qml` | Restyled provider settings; local palette, original GuiBridge actions. |

### Already working

1. Cinematic main interface, core projection/launch, task context, telemetry, response, command field, panel navigation and classic fallback.
2. Sharp golden core with flows, discrete glints/discharges, bounded viewing pitch and free yaw. Standard/expanded sizing is controlled by the stage; current max width is 540/820 before viewport constraints, not a promise of exact visible diameter.
3. 60 FPS target plus lighter 30 FPS profile reducing scene work; actual FPS depends on display, device and capture overhead. No blanket GTX 970 60 FPS guarantee.
4. Startup “E.V. online” with fixed procedural rise/arrival; once per launch; settings for mute/volume; yields to tasks/voice/hide/close. It is not conversational TTS.
5. Local music playback and a session queue; play/pause/stop/prev/next/seek/volume/mute/output selection. Filenames are initial titles. No persistent library or full tags/artwork yet.
6. Real Qt PCM tap and Windows selected-output loopback; 64-band spectrum, waveform, RMS/peak and bass/mid/high energy. One primary visualizer view today.
7. Spectral onset detection over whole buffers: 1024-sample window, 512 hop, adaptive threshold, 145 ms retrigger guard; immediate pulse with 115 ms release. This is transient detection, not BPM/beat-grid tracking.
8. Music reactions: All modes (default), Music only, Off and saved intensity. Music max pulse expansion 2.5%; Assistant one-quarter intensity, max 0.625%. Voice/task/approval/animation-pause priority wins. All modes can preserve capture across navigation; manual Stop Capture stays stopped. Visible capture indicator in Assistant.
9. Provider settings redesigned in dark blue/gold; masked credentials, real provider actions, custom dropdowns and compact layout. Core Style presets are explicitly classic-interface controls. Four other categories are still placeholders.

### Not implemented / do not claim

Real playback EQ, parametric audio processing, several simultaneous visualizers, persistent library/playlists, full shuffle/repeat, artwork/catalogs, cloud-provider playback, phone pairing/control, inbox/WhatsApp connectors, unrestricted mobile automation, calibrated end-to-end audio/visual latency and production installer. Some historical reports include failed/replaced visual experiments; latest accepted stages win.

## Runtime behavior and boundaries

- `MusicSession._music_open` denotes the page; `_active` denotes analysis demand. Preserve this distinction. Hidden Music can still analyze for ambient reactions.
- Capture only the selected output. This Windows build cannot be assumed to support Microsoft's newer per-process loopback path. Do not label selected-output mixing “only YouTube”.
- Never feed captured output back to speakers. EQ for external audio requires an explicit different routing product and is not silently enabled here.
- `QAudioBufferOutput` observes QMediaPlayer PCM; modifying a copy does not make an audible EQ. Follow the new Music plan for owned decode/DSP/output.
- Analysis/onset queues are bounded. Seek, source change and stop must discard stale generations. Preserve silence/mute behavior and callback shutdown.
- Visual `WARNING` may reflect telemetry and can react while idle; actual lifecycle/approval/voice activity suppresses music. Errors/listening/executing do not become beat animations.
- Existing speaking amplitude is synthetic bridge telemetry. `core/tts.py` was not rewritten. Real TTS PCM and music/voice acoustic coexistence need their own task.
- Keep approval above provider settings and the stage. Do not add a QML direct-execution shortcut.
- Existing action pipeline explicitly treats voice/brain/memory/awareness as non-authorizing, uses validation/risk/approval and requires verification. Cancel must not auto-continue; uncertain non-idempotent actions must not blindly retry.

## Persistence and secrets

`core.paths` defaults runtime state to `%LOCALAPPDATA%\EV` and supports environment overrides. Startup settings use QSettings `EV/CinematicStartup`; Music uses `EV/MusicFoundation`. Music volume, reaction policy and intensity persist; the queue, selected capture device/source and capture-running state currently do not. Restore a future persisted queue paused.

Keep `.env`, API keys, DPAPI/credential files, account tokens, runtime databases, raw audio, browser profiles and user video captures out of Git and handoffs. The backup is a source/assets/docs recovery snapshot, not a portable credential or model-cache clone. Credential restoration is a separate local-user operation; DPAPI data is machine/user-bound.

## Verification and known limits

Recent completed runs (different checkpoints; do not add these as one fresh suite):

- Music all-modes: 65 unit + 32 rendered + 23 player regression + 9 beat checks = 129 passing checks at that stage.
- Settings redesign: 10 settings unit + 22 rendered = 32 passing checks at that stage.
- Earlier core regression passed 18 render checks; beat fixture produced ten distinct responses for ten kick hits.
- Earlier detector-only timing: median 2.22 ms, p95 4.22 ms per 4096-frame stereo block. Not full analysis/render/latency performance.

```powershell
Set-Location D:\EV
$env:EV_STARTUP_AUDIO='false'
.\.venv\Scripts\python.exe -B -m pytest tests/test_music_foundation.py tests/test_music_beats.py tests/test_music_reaction_modes.py tests/test_cinematic_startup_audio.py -q -p no:cacheprovider
.\.venv\Scripts\python.exe -B -m pytest tests/test_gui_settings.py -q -p no:cacheprovider
$env:QSG_RENDER_LOOP='basic'
.\.venv\Scripts\python.exe -B -m prototypes.cinematic_v4.validate_music_all_modes
.\.venv\Scripts\python.exe -B -m prototypes.cinematic_v4.validate_settings_redesign
```

Run rendered/audio helpers **sequentially**, not simultaneously. They use actual local output and generated fixtures; two capture tests can contaminate each other. Check the helper's fixture paths before running from a fresh checkout. Settings validation creates a temporary provider store and mocks HTTP. Set isolated runtime directories for any broader backend tests. The original `validate_integration` helper is useful but review its runtime config access before running it against a live user environment.

For threaded PCM tests use Qt event loops that release Python's GIL while waiting; a long synchronous `QTest.qWait` chain can starve the worker and falsely show no beats. Forced `grabWindow()` readbacks are evidence of rendering, not a fair FPS benchmark. Do not hide a failed check by changing expected values without investigating.

The original full repository suite may have historical failures; the checkpoint record distinguishes current narrow checks from unrun suites. Do not claim production readiness from these limited tests. A clean-environment dependency lock and wider regression audit are the next release-engineering tasks.

## Recovery / next action

Use `astrabackup/README.md` and its manifest; extract into a **new directory** first. Never overwrite the only working tree or run `git reset --hard` to undo a visual experiment. Keep a named screenshot/asset hash baseline before each milestone. Read [next-agent prompt](docs/handoff/ASTRA_NEXT_AGENT_PROMPT.md), then implement only M1 after the user authorizes that next task.
