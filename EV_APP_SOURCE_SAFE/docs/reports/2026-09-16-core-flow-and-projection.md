```text
E.V. CORE FLOW AND STARTUP PROJECTION — 16 September 2026

Status: COMPLETE. Installed in the default cinematic E.V. interface.

Reference review:
The provided 08-32-41 recording is 151.226 seconds, 1920x1080, 60 FPS.
Reviewed its entire timeline using one-second samples, including the repeated
VLC seeks/replays. Examined the projection at 6 samples/second and gold/blue flow
close-ups at 4 samples/second. This is not a claim that every source frame was
individually inspected or that the procedural result is film-identical.
Detailed review sheets are retained in evidence/flow_launch.

Implementation:
- A 3.2-second projection begins after the first displayed frame: a compact spark
  travels upward along a curved trail, bright tilted arcs unfold, and layered
  circuits fill the volume before it settles. Backend bootstrap time is separate.
- The transition plays on app launch. Resize, state/quality changes and results
  do not replay it. Core interaction skips the remaining transition. Animation
  pause freezes it; Settings > Replay core projection explicitly restarts it.
- Three dominant, thinner tilted orbital bands and small bounded precession
  preserve a recognizable sphere. Whole-object movement remains restrained while
  local currents move faster. Pitch remains bounded and yaw remains free.
- Added 120 curved path strips with travelling bright heads, fading tails and
  synchronized branches. The lighter profile uses 48 strips and fewer segments.
- Particle populations now include curving inward currents, independent junction
  flashes that extinguish completely, and outward embers that fade away.
- Local circuit highlights ignite independently. Gold/fire colouring is retained;
  the blue reference informs energy behaviour. Sharper filaments and less diffuse
  glow preserve bright points and dark gaps.
- Procedural GPU geometry/shaders provide the visuals; film frames are review
  evidence only, not application textures.
- Existing GuiBridge, command/provider routing and approval overlays are retained.
  No backend, authority, TTS/PCM, voice, music or classic-interface changes.

Test Results:
- 5 presentation tests pass: first-frame start, duration in both profiles,
  pause/resume, explicit replay and state/request isolation.
- 12 rendered projection checks pass: visible seed, growth into the full volume,
  changing idle emission, pause pixel identity, resume, replay and interruption.
- 39 rendered interaction checks pass, including picking, rotation, typing,
  lighter mode, response layout, transparency and small-window behaviour.
- 22 rendered bridge/approval checks pass with an isolated real GuiBridge.
- Actual default gui.app startup passes: visible usable interface, native chrome,
  projection complete (1.0), 60 FPS reported and no reported QML runtime errors.
- No live task, approval, network model request or voice playback was submitted.

Benchmarks:
GTX 970, 1920x1080, expanded nucleus, sequential 20-second runs without recording.
Projection skipped for steady-state measurements; first two seconds excluded.
Standard: 59.50 average FPS; 16.67 ms median; 17.59 ms p95.
Lighter:  29.65 average FPS; 33.70 ms median; 45.45 ms p95.
Both use 27 steady-state draw calls. Drawn vertices: 298,656 / 230,688.
Particles: 3,072 / 1,024. Renderer image data: 13.625 / 6.125 MiB.
Lighter mode also reduces render resolution and glow samples. Its pacing is not
perfectly even, and no live voice contention or total process VRAM claim is made.

Artifacts:
D:\EV\prototypes\cinematic_v4\evidence\flow_launch\launch_and_flow.mp4
  Actual Qt window capture: 15 seconds, 1080p, 30 FPS, 450 encoded frames.
  Capture overhead caused 65 repeated frames; see launch_and_flow.json.
D:\EV\prototypes\cinematic_v4\evidence\flow_launch\launch_sequence.jpg
D:\EV\prototypes\cinematic_v4\evidence\flow_launch\launch_settled.png
D:\EV\prototypes\cinematic_v4\evidence\flow_launch\connected_startup.png
D:\EV\prototypes\cinematic_v4\evidence\flow_launch\projection_validation.json
D:\EV\docs\plans\2026-09-16-core-flow-and-projection.md

Hashes:
All 352 protected source files are unchanged from the start of this pass.
The existing renderer, runner, documentation and asset-manifest changes are
confined to the cinematic module; source backups are in flow_launch/previous_source.
Shader surface.frag SHA256:
88e46199564efbcde633d4d3a0575fd954f3c99b79effad6e2263780e6e9f9cf
gui/app.py SHA256 (unchanged in this pass):
d3dde949ea4081bf8847c5d91dc0f7f7da333c82c499c5145628a2d0ccc78027
Full hashes: evidence/flow_launch/source_manifest.json.
Current-pass boundary audit: evidence/flow_launch/change_scope.json.
The older overnight baseline still records its two previously authorized changes
(gui/app.py and tests/test_gui_app.py); those were not modified in this pass.

Git Commit: No new commit. Unrelated existing work preserved.
HEAD: 8237dbbf7055826806ee82b62520e1e88841d248

Next Steps:
Reopen E.V. by double-clicking D:\EV\Launch EV.cmd to see the automatic projection.
Use Settings > Replay core projection to watch it again without restarting.
The independent preview remains D:\EV\Launch Cinematic Preview.cmd.
The new flow and shape are ready for visual review; roadmap and music follow later.
```
