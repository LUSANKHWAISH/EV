# E.V. core reaction motion correction — 16 September 2026

Status: corrected candidate implemented in the shared main-app/preview renderer.
Functional checks pass; the user should judge the motion in the new recordings.
This supersedes the rejected whole-volume deformation from the shape-shift pass.

## Implementation

Removed the global stretch/fold/twist field, its matrix uniforms, finite-difference
normal reconstruction, generated shader templates and builder. The surface shader
now applies ordinary model transforms to unchanged mesh vertices. Particle centers
also retain their original positions and currents without whole-volume warping.

Three dominant arcs change orientation independently through rigid rotation. Their
local radii and scales stay fixed. The central loops counterrotate with different
tilts; the surrounding circuit layers move more slowly. The assembly's idle yaw
is slower, and audio no longer scales the whole assembly. Startup growth remains
part of the existing projection transition. Outer circuit coverage was reduced
slightly to give the internal motion more room to read.

Existing smoothed presentation glow/audio values drive a bounded reaction amount.
It adjusts internal alignment and local travelling highlights, boosts packet heads
on the arcs and adds a following packet on selected neural paths. Parent/branch
phase remains shared. Junctions flare locally. No new production state controller,
voice implementation, backend request or command/approval route was introduced.
The existing motion clock changes pace with activity without resetting phase.

This follows the reviewed references' independent internal motion and localized
energy activity within a recognizable volume. It does not reproduce the attack
sequence's destruction. No exact shot match or similarity percentage is claimed.

Main files: `qml/CoreMotion.qml`, `qml/NucleusView.qml`, `qml/HoloMaterial.qml`,
`qml/NucleusScene.qml`, and `qml/shaders/{surface.vert,surface.frag,particles.vert}`
under `prototypes/cinematic_v4`. Edit the vertex shaders directly; there is no
deformation shader generation step now. Obsolete shape diagnostics were replaced
by `validate_reaction.py` and `--validate-reaction` / `--orbit-time` preview options.
The prior version is retained under `evidence/reaction_motion/previous_source`.

## Test results

| Check | Result |
| --- | --- |
| Internal motion, fixed scales/radii, reaction, pause and bounds | 17 passed |
| Interaction, core/module picking, settings, small layout and yaw views | 38 passed; 1 FPS assertion skipped in diagnostic mode |
| Projection, local emission, replay, skip and pause | 12 passed |
| Actual default E.V. startup, native chrome and finished projection | Passed |
| Changed Python files | Syntax parsed successfully |

The motion validation freezes camera, assembly motion and shader time while only
internal orientation changes. It checks the actual 3D node transforms, unchanged
mesh buffers and changed rendered pixels. Separate reaction checks keep time fixed
and verify visible changes while layer/assembly sizes remain fixed. Pause renders
are pixel-identical. Four maximum-zoom/pitch/yaw samples have transparent borders.

The renderer and default app produced no reported QML/shader errors. Startup used
the real application bootstrap without submitting a task, starting TTS, approving
an action or making a model request. Test fixtures and render readbacks do not
establish artistic similarity; that remains a visual review.

## Benchmarks

Fresh sequential 20-second expanded runs at 1920×1080, GTX 970, Windows display
`WinDisc` reporting 60 Hz. Startup was skipped and the first two seconds excluded.
No recording, capture pump or other E.V. renderer ran concurrently. Window exposure
and activation were sampled during the run: both were true in 79/79 samples for
each profile. Values read only after application exit are not used as evidence of
presentation availability.

| Metric | Standard | Quality / lighter |
| --- | --- | --- |
| Mean presented FPS | 60.00 | 29.60 |
| Median frame interval | 16.59 ms | 33.72 ms |
| p95 frame interval | 18.16 ms | 34.87 ms |
| Draw calls | 27 | 27 |
| Drawn vertices | 298,656 | 230,688 |
| Particle instances | 3,072 | 1,024 |
| Renderer image data | 13.625 MiB | 6.125 MiB |

These are presentation timings for this scene and session, not an ASR/TTS
contention benchmark or process VRAM measurement. Functional capture checks used
the explicit readback diagnostic, so their FPS assertion was skipped; the separate
normal runs above provide the fresh frame-rate measurements.

## Review artifacts

All current evidence is under `D:\EV\prototypes\cinematic_v4\evidence\reaction_motion`.

- `idle_motion.mp4`: actual 15-second 1080p window recording of steady activity.
- `state_reactions.mp4`: actual 15-second recording with labelled preview fixtures:
  IDLE → LISTENING → THINKING → SPEAKING → IDLE, in three-second intervals.
- Corresponding `_contact.jpg` files sample each recording at one frame/second.
- Both recordings encode 450 frames at 30 FPS. Capture timing introduced 50
  repeated frames in the idle clip and 71 in the state clip; JSON sidecars disclose
  this. Their audio levels are preview simulation, not measured PCM playback.
- `reaction_validation.json`, `interaction_validation.json`,
  `projection_validation.json`, `connected_startup.json`, and the two
  `*_benchmark.json` reports preserve the verification results and timing data.

## Hashes and Git

All 352 protected project files match the baseline at the start of this pass.
`change_scope.json` records the current-pass changes and hashes;
`source_manifest.json` covers current cinematic source/assets and related documents.
Its SHA256 is recorded by `source_audit.json`. The older overnight audit still
records the two earlier authorized changes to `gui/app.py` and its launch tests;
neither file changed in this correction.

No commit created. HEAD remains `8237dbbf7055826806ee82b62520e1e88841d248`.
Unrelated work, backend/authority files, voice and music implementation are untouched.

## Next steps

Review the two new clips for the feel of the internal motion. Restart
`D:\EV\Launch EV.cmd` for the connected interface or
`D:\EV\Launch Cinematic Preview.cmd` for visual review without execution services.
The correction is functionally verified; visual acceptance is still pending.

To repeat the motion checks:

```powershell
.\.venv\Scripts\python.exe -B prototypes/cinematic_v4/run_preview.py --reference-dpi --force-render --validate-reaction --report reaction_motion/validation_run.json
```

For performance, omit `--force-render`, use `--expanded --skip-launch --duration 20`,
then repeat with `--quality`, saving separate reports and running no recorder.
