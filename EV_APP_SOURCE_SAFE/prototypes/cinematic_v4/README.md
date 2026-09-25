# E.V. cinematic interface candidate

This is E.V.'s default Qt Quick 3D interface, built from procedural geometry.
The film references guide the structure and motion; no movie frames are used as
textures. Visual acceptance is still a human review, not a similarity percentage.

## Open it

From `D:\EV`, double-click:

- **Launch Cinematic Preview.cmd** — visual review with local system telemetry.
  Commands stay in memory in the preview session. Listening/speaking amplitude
  is simulated. No microphone, TTS, model request or execution service is started.
- **Launch EV.cmd** (or **Launch Cinematic EV.cmd**) — the same interface connected to the existing E.V.
  application. Commands, results, lifecycle, experience mode and system telemetry
  use `GuiBridge`. This path has the normal application's execution capabilities
  and the existing approval and AI provider dialogs.

The default `.venv\Scripts\python.exe -B -m gui.app` now opens the cinematic
interface. `--cinematic` remains an explicit alias. The previous interface is
available through **Launch Classic EV.cmd** or `--classic`.
This changes the project GUI entry point; it does not rebuild a packaged installer.

The fire-gold refresh adds a brighter ember/gold/ivory palette, stronger glow,
scrolling band circuitry and about 1.7 times the previous idle animation speed.
Approval, error and sleep states retain restrained motion. Current comparison
and motion captures are in `evidence/fire_refresh/`; the earlier `review_*`
images and `cinematic_motion.mp4` show the preceding art version.

The subsequent **flow and projection** pass is in `evidence/flow_launch/`.
It adds branching paths with moving bright heads and fading tails, independently
flashing junctions, sharper gold emission, three dominant tilted orbits and a
3.2-second startup projection. The small source travels upward, the orbits open,
and the circuitry assembles into the full volume. It starts after the first frame
has appeared and does not delay command entry or replay on resize/state changes.
Clicking or dragging the core skips the remaining projection. Settings offers
**Replay core projection**; pausing animation also pauses a projection in progress.
The blue reference informs the local energy behaviour; E.V. retains the gold palette.

The **reaction-motion correction** replaces the rejected whole-core stretch/fold
animation. The volume keeps its size while the dominant arcs change orientation
independently and the central loops counterrotate. Local circuit highlights,
branch packets and junction flashes intensify with the existing smoothed activity
and audio signals. Motion follows the existing presentation clock; pause freezes it.
The earlier shape-shift evidence is historical and was rejected by the user.
Review `evidence/reaction_motion/idle_motion.mp4` and `state_reactions.mp4` for the
current implementation. The latter uses labelled preview fixtures, not live voice.

For console diagnostics, run:

```powershell
Set-Location D:\EV
.\.venv\Scripts\python.exe -B prototypes/cinematic_v4/run_preview.py
```

The preview's last render report and diagnostics are in `evidence/last_run.json`
and `evidence/render_diagnostics.txt`. These may be overwritten by another preview
run; named benchmark and validation artifacts are retained separately.

## Interaction

- Drag the nucleus to rotate; yaw is free and pitch is clamped to ±18°.
- Scroll over the nucleus for bounded zoom. Double-click to reset the view.
- Use **+ / −**, or **Space while the nucleus has keyboard focus**, to expand or
  reduce the nucleus. Typing spaces in the command input does not expand it.
- Hover the five small module nodes to reveal their destination; click to open
  telemetry, lifecycle/activity, command input, results or mode/settings.
- Click the center or microphone control for a listening request. The current
  bridge has no public microphone-start method, so the connected interface
  explains this and leaves microphone state unchanged.
- Enter sends a typed command. Longer responses have a scrollable full view.
- Use the left rail or top navigation for activity, system information and settings.
  Escape closes a presentation drawer. F11 toggles fullscreen.
- The existing approval surface owns input while visible; the nucleus and
  composer cannot approve a task. Existing approval buttons retain their behavior.
- Music is visibly reserved for a later release and is disabled.

## Rendering profiles

| Setting | Standard | Quality / lighter |
| --- | --- | --- |
| Frame target | 60 FPS | 30 FPS |
| GPU particle instances | 3,072 | 1,024 |
| Circuit route geometry | Full | About one third of route segments |
| Circuit texture | 2048×1024 | 1024×512 |
| 3D render dimensions | 100% | 78% per dimension |
| Glow source dimensions | 50% | 28% per dimension |
| Glow samples | 13 | 5 |

The Quality name follows the requested naming; it is the less expensive profile.
The toggle changes scene cost as well as pacing. Settings are session-local.
Animation pause freezes shader time, geometry motion and audio animation, while
the clock, input and system telemetry remain usable.

At 1080p the standard viewport is 540 logical pixels; the visible fragmented
nucleus occupies less than that. Expanded viewport is 820 pixels. The window
supports a 1100×760 minimum and reduces the scene for smaller layouts. The scene
has alpha inside E.V.'s window; it is not a transparent Windows desktop overlay.

## Architecture and boundaries

`gui/app.py` selects the cinematic renderer by default, with a `--classic` fallback.
`integration.py` adapts the existing bridge without constructing a second
production state controller or system monitor. The independent preview reuses
the existing `VisualStateController` with labelled fixtures.

`CinematicStage.qml` is shared by preview and connected windows. The connected
window hosts the original provider dialog at z=80 and original approval dialog
at z=100, disabling the presentation beneath either dialog. The renderer uses
batched meshes, a GPU instance buffer and alpha-preserving compositing.

TTS PCM playback, `core/tts.py`, voice recognition, authority, provider behavior,
music playback and installer packaging were outside this implementation.
Connected speech animation uses the bridge's existing synthetic speaking level;
it is not a measured playback RMS signal. Actual ASR/TTS contention needs a
separate live voice test.

## Reproduce the checks

```powershell
Set-Location D:\EV
.\.venv\Scripts\python.exe -B prototypes/cinematic_v4/run_preview.py --reference-dpi --validate --report validation_run.json
.\.venv\Scripts\python.exe -B -m prototypes.cinematic_v4.validate_integration
.\.venv\Scripts\python.exe -B prototypes/cinematic_v4/run_preview.py --reference-dpi --validate-launch --report flow_launch/projection_run.json
.\.venv\Scripts\python.exe -B -m pytest prototypes/cinematic_v4/test_projection.py -q
.\.venv\Scripts\python.exe -B prototypes/cinematic_v4/benchmark.py
.\.venv\Scripts\python.exe -B prototypes/cinematic_v4/run_preview.py --reference-dpi --force-render --validate-reaction --report reaction_motion/validation_run.json
```

Validation posts input into the actual Qt window. It does not inject OS input.
The integration validation uses a real `GuiBridge` and isolated `EVEventBus`,
with no orchestrator or external service. Test approval fixtures cannot execute
anything. The benchmark runs profiles sequentially without recording. NVIDIA
utilization and VRAM measurements cover the entire adapter, not just E.V.

To regenerate meshes/textures, run `generate_assets.py` with the same Python
environment. NumPy and PySide6 are already installed. The geometry seed is 9416.
Then run `python -B -m prototypes.cinematic_v4.generate_flow_assets` for the new
branching paths and projection meshes (seed 160926). Both profiles include branching
paths; the lighter profile uses 48 instead of 120 strips and fewer curve segments.
To rebuild the Qt Quick glow shader after editing it:

```powershell
& .\.venv\Lib\site-packages\PySide6\qsb.exe --glsl '100 es,120,150' --hlsl 50 --msl 12 -o prototypes/cinematic_v4/qml/shaders/glow.frag.qsb prototypes/cinematic_v4/qml/shaders/glow.frag
```

The other shaders are Qt Quick 3D CustomMaterial source shaders and do not use
this qsb command. Media capture requires the already installed FFmpeg.

The surface and particle vertex shaders now use ordinary model transforms. The
rejected deformation field, generated templates and builder have been removed;
edit `surface.vert` and `particles.vert` directly. Layer orientation lives in
`qml/CoreMotion.qml`. No per-frame vertex or particle-buffer uploads are needed.

Diagnostic `--orbit-time SECONDS --freeze` isolates internal orientation from
camera and emission motion. `--force-render` pumps explicit readbacks for an
occluded/remote desktop; it disables preview frame pacing and skips the FPS
assertion. It is not a performance measurement or production setting. Integration
and startup smoke tools also accept this diagnostic flag. Use normally exposed
windows without recording/readbacks for live 60/30 FPS verification.

See `D:\EV\docs\plans\2026-09-16-cinematic-nucleus.md` for the saved plan and work
log, and `evidence/` for actual captures, validations and measured timings.

## Review files

- `evidence/review_standard.png` — standard 1080p interface.
- `evidence/review_expanded.png` — expanded cinematic nucleus.
- `evidence/review_quality.png` — lighter profile at the same expanded size.
- `evidence/review_settings.png` — settings in the 1280×800 layout.
- `evidence/reference_comparison.png` — film reference and actual window crop.
- `evidence/cinematic_motion.mp4` — actual 15-second 1080p window recording with
  labelled preview states. Its accompanying JSON discloses capture duplicates.
- `evidence/integration_connected.png` and `integration_approval.png` — isolated
  bridge validation. The approval shown is a test fixture with no executor.
- `evidence/connected_startup.png` — real application startup and system telemetry.
- `evidence/validation.json`, `integration_validation.json`,
  `connected_startup.json`, `benchmark_metrics.json` and `source_audit.json` —
  machine-readable verification. Frame-time CSV files accompany benchmark runs.

Older `art*`, `interface_*`, `core_*` and draft motion files record earlier
iterations. Use the named `review_*` images and final motion for the current
candidate. Raw transparent item grabs are alpha diagnostics; window captures
show the actual composition.

Current flow/projection review:
- `evidence/flow_launch/launch_and_flow.mp4` — actual startup plus ongoing idle flow.
- `evidence/flow_launch/launch_seed.png`, `launch_arcs.png`, `launch_weave.png`,
  `launch_settled.png` — staged launch captures, named relative to this folder.
- `evidence/flow_launch/projection_validation.json` — actual launch/pause/replay checks.
- `docs/reports/2026-09-16-core-flow-and-projection.md` in the project root — preceding report.
- `docs/reports/2026-09-16-shape-shift.md` — rejected historical deformation pass.
- `docs/reports/2026-09-16-core-reaction-motion.md` — current motion correction report.

For a steady-state benchmark use `--skip-launch`. For a recording that includes the
full transition use `--record FILE.mp4 --record-launch --duration 19`.
