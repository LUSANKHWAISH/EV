```text
E.V. FIRE-GOLD REFRESH — 16 September 2026

Status: COMPLETE. Ready to open and review in motion.

Implementation:
- Brighter ember-orange, golden and ivory highlights; stronger glow in both modes.
- About 1.7 times the previous idle animation speed (0.55 to 0.95), scrolling band
  circuitry, faster internal light currents and particles. Geometry is preserved.
- Cinematic is now the default project GUI through python -m gui.app.
  --cinematic remains supported; --classic opens the previous interface.
- Added D:\EV\Launch EV.cmd and D:\EV\Launch Classic EV.cmd.
- Existing GuiBridge, command routing, provider and approval overlays remain in use.
  No backend, authority, TTS/PCM, voice or music implementation changes.
- Updated launch documentation, startup checks and tests for both GUI choices.

Test Results:
- tests/test_gui_app.py: 39 passed in 31.79 seconds.
- Actual rendered preview: 39/39 checks passed, including interaction, small layout,
  full responses, bounded pitch/zoom, module picking, reduced-cost mode and pause.
- Rendered integration: 22/22 checks passed with a real isolated GuiBridge,
  including canonical commands/results and approval/provider overlay input ownership.
- Real default GUI startup and --classic startup: both passed, native window chrome
  attached, no reported QML runtime errors. No real task or voice playback invoked.

Benchmarks:
- GTX 970, 1920x1080, expanded nucleus, two sequential 20-second runs without capture.
- Standard 60: average 59.94 FPS; median frame 16.67 ms; p95 frame 17.44 ms.
- Lighter 30: average 29.62 FPS; median frame 33.72 ms; p95 frame 36.64 ms.
- Lighter mode uses 1,024 vs 3,072 particles, 218,556 vs 251,964 drawn vertices,
  6.125 vs 13.625 MiB of renderer image data, smaller render targets and 5 vs 13 glow
  samples. These are scene metrics, not total process VRAM measurements.
- The 30 FPS profile is an approximate target, not a claim of perfectly even frames.

Review artifacts:
- D:\EV\prototypes\cinematic_v4\evidence\fire_refresh\after.png
- D:\EV\prototypes\cinematic_v4\evidence\fire_refresh\comparison.png
- D:\EV\prototypes\cinematic_v4\evidence\fire_refresh\default_startup.png
- D:\EV\prototypes\cinematic_v4\evidence\fire_refresh\motion.mp4
  Actual idle animation, 1920x1080, 15 seconds, 30 FPS, 450 encoded frames.
  Capture overhead caused 50 duplicated frames, disclosed in motion.json.
- Earlier visual-review images remain the earlier art version. Previous validation
  outputs were archived in fire_refresh/previous_validation before the latest run.

Hashes:
- Against the saved 352-file pre-cinematic source baseline, 350 remain unchanged.
  The two intentional existing-file changes are gui/app.py and tests/test_gui_app.py.
- gui/app.py SHA256:
  d3dde949ea4081bf8847c5d91dc0f7f7da333c82c499c5145628a2d0ccc78027
- tests/test_gui_app.py SHA256:
  f8f82bd4ad4a7392d25a631fc3f367e1d10808daccfefbade6d14d11dd1e8ea1
- Full cinematic source hashes and boundary audit:
  D:\EV\prototypes\cinematic_v4\evidence\fire_refresh\source_manifest.json
  D:\EV\prototypes\cinematic_v4\evidence\fire_refresh\source_audit.json

Git Commit: No new commit. Existing unrelated work was preserved.
Baseline HEAD: 8237dbbf7055826806ee82b62520e1e88841d248

Next Steps:
- Double-click D:\EV\Launch EV.cmd to open the refreshed connected application.
- D:\EV\Launch Cinematic Preview.cmd opens the independent visual preview.
- D:\EV\Launch Classic EV.cmd opens the previous interface if needed.
- This updates the project GUI; a separate packaged installer was not rebuilt.
- Visual acceptance remains with the user; the project roadmap and music mode
  follow separately. Film-reference pixel identity is not claimed.
```
