# Inner filament refinement — 16 September 2026

## Status

Implemented for visual review. The current accepted fire-gold version was backed up before editing. Actual Qt renders show narrower inner strands and less folded ribbon area; the user decides final visual acceptance.

## Backup

`D:/EV/.ev-cinematic-nucleus-backups/20260916-142419-accepted-fire-gold-before-inner-filaments`

420 source, asset and launcher files were copied and SHA256 verified before editing, then verified again on completion. This includes the 352 protected project source files. `backup_manifest.json` identifies every saved file. `rollback_paths.json` identifies the five files needed to roll back just this refinement.

## Implementation

- Replaced the three broad striped inner surfaces with 21 tapered strands and three short branches. The lighter profile uses nine strands and three branches.
- Reduced curling and the bundle width; varied lateral spacing and depth so the strands no longer form a wide flat sheet.
- Replaced the inner material's regular stripe/dot pattern with continuous bright spines and independently phased travelling light. Each packet has a bright front, trailing light and fade-out. Branches share their parent's packet coordinate.
- Kept the current fire-gold palette and emission settings. All shader logic outside the inner-filament branch matches the accepted baseline. Outer shells, orbital bands, central core, lightning, particles, glow, camera framing and motion controller are unchanged.
- Added a smaller inner mesh for the lighter mode, using the existing quality switch. No additional draw call.

Changed existing files: `generate_assets.py`, `assets/energy_ribbons.npz`, `assets/manifest.json`, `qml/NucleusView.qml`, `qml/shaders/surface.frag`, all under `D:/EV/prototypes/cinematic_v4/`. Added `assets/energy_ribbons_low.npz`. Plans, evidence and this report are separate artifacts.

## Test Results

18 focused checks passed using direct `QQuickWindow.grabWindow` renders of the production `NucleusScene` and shaders: visible gold geometry, independent orbital motion, transparent border, reaction at fixed clock, unchanged assembly scale, lighter mesh selection and visibility, four yaw orientations at maximum zoom and bounded pitch, projection seed/growth/completion, no command requests, isolated strand visibility, moving illumination at fixed layer orientation and identical paused frames.

The actual `gui.app` cinematic startup check passed: native window chrome, enabled stage, completed projection, saved render and no QML errors. It used the basic Qt render loop and forced readbacks for this virtual desktop. No task was submitted and TTS was disabled for the smoke check.

The older nested-item capture harness returned blank/stale frames on this virtual display, causing its two image-change checks to fail; those results are preserved in `legacy_capture_failure.json`. They are not counted as passes. Direct window captures resolved the inspection problem and produced the 18 checks above without changing production rendering code or weakening the pixel checks. All compared frames must contain visible geometry.

## Benchmarks

GTX 970, D3D11, 1920×1080. The active virtual display reports 32 Hz. Separate 12-second timing probes used the normal threaded renderer, no forced readbacks and no recording; the first two seconds were excluded. Both windows were exposed and active in all 45 observations.

| Profile | Average FPS | Median frame | p95 frame | Drawn vertices | Particles |
|---|---:|---:|---:|---:|---:|
| Standard | 31.30 | 31.22 ms | 33.30 ms | 297,216 | 3,072 |
| Lighter | 29.41 | 33.83 ms | 53.07 ms | 216,432 | 1,024 |

The 60 FPS target cannot be verified on this 32 Hz display. The default target remains unchanged. Lighter mode's p95 indicates occasional longer frames in this session. Draw calls remain 28; image memory remains 13.63 MiB standard / 6.13 MiB lighter.

Inner geometry decreased from 6,480 triangles to 4,272 standard (34% fewer) and 1,152 lighter (82% fewer than the old ribbon mesh). Those are geometry reductions, not measured GPU speedups.

## Evidence

`D:/EV/prototypes/cinematic_v4/evidence/inner_filament_refine/`

- `before_after.png`: accepted baseline and refined full core at a fixed clock.
- `ribbon_detail_comparison.png`: isolated old/new inner layers, rendered from their respective sources at the same sample time.
- `after_inspection/checks.json`: 18 direct-render checks and associated images.
- `connected_startup.json` / `.png`: actual app bootstrap.
- `motion.mp4`: 15-second actual-window recording. The 30 FPS encoded stream contains 450 frames, including 262 duplicates from virtual-display/capture overhead; this clip is not a smoothness or FPS benchmark. The separate timing probes above measure presentation without capture overhead.
- `source_manifest.json`, `source_audit.json`, `rollback_paths.json`: hashes and scope.

## Hashes / Git Commit

All 352 protected project source files are unchanged against this task's baseline. Only the five listed existing cinematic files changed; the backup's 420 saved files still match their original hashes. Unrelated pre-existing working-tree changes were preserved.

- Surface shader SHA256: `f704ec3a7856d7b147ebbd74bcfb9ba0ba11d9bc0fd07e18911ba754dde665be`
- Existing gui/app.py SHA256: `d3dde949ea4081bf8847c5d91dc0f7f7da333c82c499c5145628a2d0ccc78027`
- Git HEAD: `8237dbbf7055826806ee82b62520e1e88841d248`
- No commit created.

## Next Steps

Close the currently running E.V. window and reopen `D:/EV/Launch EV.cmd` to load the refined shared core. Use `D:/EV/Launch Cinematic Preview.cmd` for the isolated preview. Review the marked inner regions in the live app. If a rollback is requested, restore only the five paths in `rollback_paths.json` from the verified backup; leave unrelated project files alone.
