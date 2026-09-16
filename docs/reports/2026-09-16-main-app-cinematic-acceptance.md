# Accepted cinematic interface in the main E.V. app

## Status

Verified and launched the main app with the accepted core and inner-filament refinement. The production wiring was already present: `D:/EV/Launch EV.cmd` starts `pythonw -B -m gui.app`; the default argument selects the cinematic interface. No additional application source changes or duplicate asset copy were needed in this step.

## Implementation / production path

`Launch EV.cmd` → `gui/app.py` → `prototypes/cinematic_v4/integration.py` → `qml/ConnectedWindow.qml` → `CinematicStage` / `NucleusScene`.

This is the connected application. Its `BridgePresentationModel` consumes the existing `GuiBridge`. Command submission, task results, lifecycle stages, telemetry, mode, voice levels, approval overlay and provider settings use that bridge. The accepted visuals are the same shared QML, shaders and mesh assets used by the preview. All 68 files in the accepted source manifest match their recorded hashes.

The main application's approval surface retains its higher z-order and disables the underlying interface while pending. Provider settings use the existing overlay. Preview simulation controls cannot modify production state.

Existing limitation: clicking the core does not start the microphone, because the current bridge does not expose that action; it shows the existing voice-control notice. Existing voice-level signals are connected. No TTS/PCM, voice-control or music-mode work was added here.

## Test Results

- 39 tests passed in `tests/test_gui_app.py` in 59.72 seconds. These cover default cinematic selection, the existing classic option and canonical task/approval wiring, among other app checks.
- 22 rendered bridge-integration checks passed using the real `GuiBridge` and an isolated event bus. Commands and rejection events were test fixtures with no executor or external service attached. Result/history updates, telemetry, canonical state, overlay priority, input blocking and provider settings were verified.
- Actual `gui.app` startup passed: visible cinematic window, enabled stage, attached native chrome, completed launch, saved render, no QML errors and clean exit. The diagnostic startup used basic Qt rendering with forced readbacks and disabled TTS; it is not a frame-rate benchmark.
- After those checks, the normal application entry point was launched separately with the user's normal configuration and left open for review. Launch-process evidence is in `launch.json` and `running_app.json`.

## Benchmarks

No new performance benchmark was run during this integration verification. The prior visual-refinement timing probes were constrained by a 32 Hz virtual display; this step does not establish a new 60 FPS result.

## Hashes / source boundary

All 352 protected project source files and all 68 accepted-manifest files are unchanged in this step. Only verification artifacts and this report were written.

Accepted manifest SHA256: `52019d0118f9ff366543247084bb1821d59997d0b4a7c9413961c4aab719c4bd`

`gui/app.py` SHA256: `d3dde949ea4081bf8847c5d91dc0f7f7da333c82c499c5145628a2d0ccc78027`

The verified visual backup remains at `D:/EV/.ev-cinematic-nucleus-backups/20260916-142419-accepted-fire-gold-before-inner-filaments/`. The current accepted refinement is recorded by `D:/EV/prototypes/cinematic_v4/evidence/inner_filament_refine/source_manifest.json`.

## Git Commit

HEAD: `8237dbbf7055826806ee82b62520e1e88841d248`. No commit created; unrelated pre-existing changes were preserved.

## Next Steps

Use the opened main E.V. window. For future launches, double-click `D:/EV/Launch EV.cmd`. `Launch Cinematic Preview.cmd` is the isolated preview launcher.

Evidence: `D:/EV/prototypes/cinematic_v4/evidence/main_app_acceptance/`, including `accepted_asset_verification.json`, `pytest_result.json`, `integration_validation.json`, `connected_startup.json`, `connected_startup.png`, and launch details.
