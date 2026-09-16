# E.V. continuous core deformation — 16 September 2026

Status: implemented in the renderer shared by the main E.V. interface and preview.
Functional verification passes. Fresh live performance verification remains open
because the active remote desktop suppresses normal window presentation.

The preceding pass added travelling emission and startup projection but mostly
retained fixed geometry. This pass adds actual non-rigid movement: directional
stretch, local inward folding and differential twist, followed by reformation.
The central opening, shell fragments and large bands visibly change their shape.

## Implementation

One smooth field in assembly coordinates deforms the shells, bands, circuit
routes, neural branches, filaments and particle centers. Applying the same field
keeps connected paths coherent. Surface normals are recomputed with finite
differences so front/rear brightness cues follow the changed surfaces. Meshes and
particle instance buffers stay uploaded; there is no Python per-vertex animation.

The field uses the existing presentation motion clock. Existing state-dependent
speed applies to deformation; pause freezes it. Its strength fades in over the
last part of deployment. The projection source and launch trail remain independent.
A radial constraint and adjusted camera distance leave room for the changing
outline. Maximum zoom and both pitch limits were sampled at six deformation/view
combinations. A stable center hit proxy supports picking because CPU picking does
not know about GPU-deformed triangles.

This is a bounded evolving core, not arbitrary topology changes, a destruction
simulation or an exact recreation of a film shot. Artistic matching remains a
visual review; no match percentage is claimed. No voice, PCM, music, approval,
backend or classic UI files were modified in this pass.

Canonical shader source is `prototypes/cinematic_v4/qml/shaders/shape_field.glsl`
plus `surface.vert.in` and `particles.vert.in`. `build_shape_shaders.py` inlines the
shared field into runtime vertex shaders; `--check` verifies the generated files.
The runtime rejected relative GLSL includes, which is why this generation step is
necessary. Vertex and particle shaders compiled on D3D11 / GTX 970 without errors.

## Test results

Evidence is in `D:\EV\prototypes\cinematic_v4\evidence\shape_shift`.

| Check | Result |
| --- | --- |
| Shape-only renders, bounds, both profiles and pause | 13 passed |
| Input, picking, settings, layout and four yaw views | 38 passed; 1 FPS assertion explicitly skipped |
| Startup projection, emission, replay, interruption and pause | 12 passed |
| Real GuiBridge contracts, result surfaces and approval/provider overlays | 22 passed |
| Actual default app startup with native chrome and completed projection | Passed |
| Generated shader freshness | Both shaders current |

Shape validation freezes the camera, rotation and emission clock while changing
only deformation phase. The disabled-field control allows insignificant MSAA/glow
edge differences; actual shape phases must change over 10% of visible alpha pixels.
The paused comparison is pixel-identical. These pixel measurements establish
deformation, not perceptual similarity to the reference. The lighter-profile
comparison changes only deformation phase within that same profile.

Initial captures exposed asynchronous readback delays on an unexposed window.
The shape validator now waits for each readback and explicitly renders until it
retires. This revealed clipping at two extreme views, fixed by giving the camera
more room. An initial ordinary interaction run could not update its render/picking
state in this remote session. Repeating with a documented diagnostic readback pump
passed functional checks. The diagnostic bypasses preview frame pacing and skips
the live FPS assertion; it does not change the production frame limiter. Geometry
savings were checked from the actual bound mesh index buffers rather than stale
RenderStats: 216,762 full-profile indices versus 148,794 lighter-profile indices.

Integration validation used an isolated event bus without an executor. The actual
startup smoke check submitted no task, started no TTS and made no model request.
Both used explicit diagnostic renders in this session. Diagnostic reports retain
their scope and the startup/preview reports identify the forced readback mode.

## Benchmarks and media

Two separate 12-second expanded steady-state runs, one per profile, used no
capture pump, recording or interactions. Both reported `window_exposed: false`,
one presented frame, and no measurable steady-state FPS. The active RDP display
was `DISPLAY97`, 1920×1080, reporting 32 Hz. These runs cannot establish either
60 FPS or 30 FPS performance. Earlier 60 Hz measurements belong to the previous
implementation and are not reused as proof for this one.

The renderer initialized at 27 draw calls in both profiles, with 298,656 versus
230,688 drawn vertices, 3,072 versus 1,024 particle instances and 13.625 versus
6.125 MiB of image data. These initialization statistics are not GPU timing or
process VRAM measurements. The extra deformation/normal shader work still needs
a live display benchmark on the user's normal 60 Hz screen.

`shape_motion.mp4` is an actual 15-second 1920×1080 Qt window recording, encoded
at 30 FPS. Its 450 encoded frames include 48 duplicates introduced by capture
timing; the JSON sidecar discloses this. It is not a performance benchmark.
`shape_comparison.png` compares three actual renders with only shape phase changed.
`motion_contact_sheet.jpg` samples the recording at two frames per second.

## Hashes and Git

The current-pass baseline contains all 352 protected project files, and all 352
remain byte-identical. `change_scope.json` records current-pass hashes and changes.
`source_manifest.json` includes the cinematic source, assets, launchers and plans;
`source_audit.json` holds its SHA256. The older overnight audit baseline correctly
shows earlier authorized changes to `gui/app.py` and `tests/test_gui_app.py`; those
two files are unchanged in this shape pass.

HEAD: `8237dbbf7055826806ee82b62520e1e88841d248`. No commit created. Existing unrelated
working-tree changes were preserved. Pre-pass sources are retained in
`evidence/shape_shift/previous_source`.

## Open and review

Restart `D:\EV\Launch EV.cmd` to use the updated connected interface, or open
`D:\EV\Launch Cinematic Preview.cmd` for visual review without execution services.
Expand the core to inspect the deformation more closely. Next: judge its motion
and intensity, then repeat the normal benchmark on an exposed 60 Hz display.

Reproduce the rendered checks:

```powershell
.\.venv\Scripts\python.exe -B prototypes/cinematic_v4/build_shape_shaders.py --check
.\.venv\Scripts\python.exe -B prototypes/cinematic_v4/run_preview.py --reference-dpi --validate-shape --report shape_shift/validation_run.json
.\.venv\Scripts\python.exe -B prototypes/cinematic_v4/run_preview.py --reference-dpi --force-render --validate --report shape_shift/interaction_forced_run.json
.\.venv\Scripts\python.exe -B prototypes/cinematic_v4/run_preview.py --reference-dpi --force-render --validate-launch --report shape_shift/projection_run.json
.\.venv\Scripts\python.exe -B -m prototypes.cinematic_v4.validate_integration --force-render
.\.venv\Scripts\python.exe -B -m prototypes.cinematic_v4.smoke_connected --force-render --report shape_shift/connected_startup.json
```

Omit `--force-render` on a normally presenting desktop. Benchmark there with
`--expanded --skip-launch --duration 25`, once normally and once with `--quality`,
using separate report names and no recording or other renderer in parallel.
