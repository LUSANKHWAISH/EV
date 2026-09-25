# Core flow and projection pass

Status: COMPLETE. Implemented and verified against the user's 08:32:41 reference clip.

Reference review: the complete 151.226-second recording was sampled across its
timeline, including its repeated seeks/replays. Detailed contact sequences cover
the gold projection (8.4–12.4 s), gold surface flow (15–18 s) and blue network
(41–44 s). Evidence: `prototypes/cinematic_v4/evidence/flow_launch/`.

Observed behaviours to adapt:
- Gold: a stable, open spherical volume; a few dominant tilted loops; layered
  angular circuitry; intense small highlights, dark gaps and independent currents.
- Blue: branching filaments, moving short packets, local junction ignition and
  gradual extinction; much faster local activity than whole-object rotation.
- Projection: a compact source travels outward, arcs open first, then internal
  circuits fill the volume and settle. A simple scale/fade is insufficient.

Implementation:
1. Preserve the current source and protected-file hashes before edits.
2. Add batched branched paths with travelling head/tail pulses and reduced geometry
   in lighter mode. Replace uniform particle drift with packets, junction flashes
   and fading embers. Keep the gold/fire palette from the accepted pass.
3. Refine the dominant orbital shape and reduce diffuse glow in favour of sharper
   local emission. Keep bounded pitch, free yaw, transparent internal composition.
4. Add a roughly three-second one-shot projection starting after the first rendered
   frame. Keep it presentation-only, pausable/skippable, without delaying input.
   Reopening the app plays it; resize, mode changes and results do not replay it.
5. Capture the real launch and continuous idle activity; inspect rendered frames.
6. Validate launch timing/pause/skip/replay, state wiring, existing interactions,
   modal approval priority and both rendering profiles. Record performance without
   capture overhead, then publish the report and source audit.

Boundaries: no voice/PCM, authority, backend, music or classic-interface changes.
The clip is a reference for procedural rendering; film imagery is not shipped as
an interface asset. Full timeline review does not imply inspection of every frame
or a claim of pixel-identical film reproduction.

Completion evidence:
- 120 batched path strips (48 in lighter mode), moving packets with shared branch
  timing, flashing junctions and outward embers. Three refined dominant orbits.
- 3.2-second projection after first presentation; pause/resume, skip on core input,
  explicit replay and automatic one-shot behaviour verified in rendered Qt.
- 5 presentation tests, 12 projection checks, 39 interaction checks and 22 isolated
  bridge/approval checks pass. Actual connected startup finishes projection at 1.0,
  reports 60 FPS, and has no reported QML errors.
- Expanded unrecorded averages: 59.50 FPS standard, 29.65 FPS lighter. The latter
  has 45.45 ms p95 frames; it is not a claim of perfectly even 30 FPS pacing.
- Actual 15-second launch/idle capture saved as `flow_launch/launch_and_flow.mp4`.
  Its 65 repeated capture frames are disclosed in the accompanying metadata.
- All 352 pre-existing protected source files match the start of this pass.
  Current report: `docs/reports/2026-09-16-core-flow-and-projection.md`.
