# Continuous core deformation

Status: implemented and functionally verified. Fresh live FPS validation remains
unavailable while the remote desktop suppresses window presentation.

The earlier implementation changes light, rotation and startup assembly, but
mostly retains static geometry. This pass adds continuous non-rigid deformation.

- Apply one coherent deformation field in assembly coordinates to the shells,
  orbital bands, circuitry, filaments, branching paths and particle positions.
- Blend directional stretch, a local inward fold and differential twist smoothly;
  retain a bounded spherical envelope and recognizable central aperture.
- Use the existing presentation clock, so pause freezes shape and task activity
  controls its pace without adding another application-state controller.
- Keep the launch trail outside this field. Use a conservative center hit proxy,
  since GPU-deformed visual triangles do not update CPU picking geometry.
- Prove deformation using renders with rotation, camera, light/flow time and
  launch frozen: only the shape phase changes. Check multiple views and maximum
  zoom, both profiles, pause, projection, interaction and bridge integration.
- Record actual continuous motion, benchmark without capture, save source hashes.

No backend, approval, voice, music or classic-interface changes are in scope.

Completed: shared GPU field and deformed normals, particle integration, bounded
framing, stable picking, 13 deformation checks, 38 interaction checks, 12 projection
checks, 22 bridge checks, real application startup and an actual 15-second video.
The interaction suite explicitly skips its FPS assertion in forced-render mode.
Both separate 12-second benchmark attempts presented only one frame and reported
the window unexposed; they establish no live frame-rate result. See the report at
`docs/reports/2026-09-16-shape-shift.md` and evidence under `evidence/shape_shift/`.
