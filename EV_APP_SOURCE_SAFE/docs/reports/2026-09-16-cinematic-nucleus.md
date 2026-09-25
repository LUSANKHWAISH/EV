```text
E.V. CINEMATIC NUCLEUS AND INTERFACE — 16 SEPTEMBER 2026

STATUS
Working opt-in candidate, ready for visual review. The plan was saved before
implementation. The renderer and interface are functional; matching the film's
organic detail and light distribution remains an artistic review, not a verified
percentage. This is not a claim of an identical movie effect.

IMPLEMENTATION
- Procedural 3D circuit patches, clustered routes, fragmented peripheral boards,
  four independently moving bands, curling central filaments and GPU particles.
- Full dark cinematic interface: command composer, response and selectable full
  response, task/lifecycle rail, telemetry, activity, settings and expanded view.
- Free yaw, pitch limited to ±18 degrees, bounded zoom, reset and module requests.
- Standard 60 FPS target and a documented lighter 30 FPS Quality profile.
- The new connected interface consumes GuiBridge state and uses its existing
  command, result and telemetry paths. The original approval and provider dialogs
  remain above it and disable underlying input while visible.
- Music is reserved and disabled. PCM/TTS, ASR, execution authority and provider
  behavior were not changed. Speaking amplitude remains the existing synthetic
  signal. The bridge has no public microphone-start method, so the new microphone
  control explains that limitation instead of claiming to start listening.

OPEN THE BUILD
Preview, with commands disconnected:
  D:\EV\Launch Cinematic Preview.cmd
Connected to the existing application:
  D:\EV\Launch Cinematic EV.cmd
Console equivalent for the connected version:
  D:\EV\.venv\Scripts\python.exe -B -m gui.app --cinematic
Run the command from D:\EV. The original launch path remains available.

TEST RESULTS
- 132 existing targeted tests passed in 15.94 seconds: application bootstrap,
  bridge, results, lifecycle, approvals and visual state. Not a full-repo test run.
- 39 rendered preview checks passed: real Qt input, focus isolation, module picks,
  profile reductions, measured pacing, pause, alpha borders, smaller layout,
  selectable read-only responses and four yaw orientations.
- 22 isolated bridge/overlay checks passed with no executor or external calls.
- Actual gui.app --cinematic startup passed with native Windows chrome, system
  telemetry, one visible window and no QML runtime errors. No task was submitted.

BENCHMARKS
GTX 970, D3D11, BenQ 1920x1080, 60 Hz, DPR 1.0.
Four sequential 25-second runs, first two seconds excluded, no recording:

Profile             Mean FPS    p95 frame ms    Process CPU*    Working set*
Standard / 60         59.65         17.44            1.99%        233 MiB
Expanded / 60         59.95         17.50            1.96%        233 MiB
Standard / 30         29.63         35.45            0.90%        236 MiB
Expanded / 30         29.63         44.57            0.73%        236 MiB

* Medians; CPU normalized across logical CPUs; interpreter process tree included.
These are measured averages, not a guarantee of a locked rate under every load.
The 30 FPS profile reduces particles 3072 -> 1024, route geometry, render dimensions
100% -> 78%, glow dimensions 50% -> 28%, and glow samples 13 -> 5. Measured image
data is 13.625 -> 6.125 MiB. NVIDIA measurements in the JSON cover the whole adapter;
they are not a per-process VRAM allocation. Live voice contention was not tested.

EVIDENCE
Folder: D:\EV\prototypes\cinematic_v4\evidence
- review_standard.png, review_expanded.png, review_quality.png, review_settings.png
- reference_comparison.png: film frame and actual window crop, labelled
- cinematic_motion.mp4: actual 15-second 1080p recording with simulated states
- cinematic_motion.json: capture/duplicate counts; recording affects frame timing
- validation.json, integration_validation.json, connected_startup.json
- benchmark_metrics.json and per-profile frame-time CSV files
- source_audit.json, source_manifest.json, gui_app_overnight.patch
Older art drafts and raw alpha diagnostics are retained as development evidence.

HASHES AND GIT COMMIT
352 existing files were baselined. 351 remain byte-identical. The only intentional
existing-file edit is gui/app.py: the --cinematic CLI branch and renderer attachment.
Its complete pre-edit copy and the exact overnight diff are retained. The source
manifest records SHA-256 hashes for the new code/assets and edited entry point.
No Git commit was created. Baseline HEAD:
  8237dbbf7055826806ee82b62520e1e88841d248
Pre-existing tracked and untracked work was preserved.

NEXT STEPS
Review the actual moving candidate and comparison before further art changes.
The film still has more organic, locally intense flowing detail; final visual
acceptance belongs to the user. The broader roadmap and music implementation
remain the next phase. Settings are session-local; no installer was produced.

PLAN AND USAGE
D:\EV\docs\plans\2026-09-16-cinematic-nucleus.md
D:\EV\prototypes\cinematic_v4\README.md
```
