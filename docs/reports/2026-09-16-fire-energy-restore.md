# Fire-gold restoration and energy emission — 16 September 2026

Status: implementation complete and checked in the actual Qt renderer. Visual acceptance is for the user to judge from the saved comparison and motion clip.

## Implementation

- Restored stronger fire-orange and gold emission, larger core framing (camera 420 → 382), denser shell coverage, and substantial orbital bands. Restored the earlier band alignment while retaining independent controlled movement and a stable spherical volume.
- Added 48 branching golden discharge families (16 in the lighter mode), batched into one additional draw call. Each has a travelling ignition front, an illuminated trailing section, a brief flicker and complete extinction. Forks share their parent's phase. The new mesh is 1,728 triangles, or 576 in the lighter mode.
- Added larger local golden ignition points and outward spark streaks. Sped up the existing travelling energy packets and strengthened filament highlights.
- Tightened bloom to bright features, reduced its radius and suppressed bloom from dim circuitry. Main line centres remain crisp, with orange/gold falloff and pale-gold peaks.
- Kept startup projection, real state consumption, pause, input and overlays. Inset the peripheral schematic layer by 8% to retain the closer camera without clipping at maximum zoom and bounded pitch.
- These shared cinematic assets load in the existing default E.V. interface and in the preview launcher. Backend, authority, voice/TTS and music files were not changed in this task.

## Test Results

68 checks passed: 39 interface/input/layout checks, 17 independent motion/reaction/pause/bounds checks and 12 projection/launch checks. No skipped FPS check in this run. The actual `gui.app` default bootstrap also passed, with completed projection, enabled cinematic stage and attached native window chrome; no task was submitted and no TTS was started.

The isolated production discharge material produced 12 distinct frames at fixed sample times. 4,434 pixels ignited and extinguished over the sequence. This inspection used Qt's basic render loop to avoid a standalone Python/Qt threaded capture stall; its timing is not a performance measurement.

An initial maximum-zoom check caught clipping in three orientations. After insetting the peripheral geometry, all four tested maximum-zoom orientations passed with zero alpha on the viewport border.

The final fixed-clock before/after window captures show 14,841 → 35,981 bright warm pixels (red > 180 under the same colour mask), and mean red within warm lit pixels 122.0 → 146.4. These measurements describe these two renders, including their changed geometry/framing; they are not a percentage match to the film.

## Benchmarks

GTX 970, D3D11, BenQ VZ2250 1920×1080 at 60 Hz. Each mode ran for 20 seconds, excluding the initial two seconds from frame statistics. No recording or forced readback pump. Both windows were exposed and active in all 79 observations.

| Mode | Average presented FPS | Median frame | p95 frame | Particles | Drawn vertices | Image memory |
|---|---:|---:|---:|---:|---:|---:|
| Standard | 58.99 | 16.66 ms | 17.93 ms | 3,072 | 303,840 | 13.63 MiB |
| Lighter | 29.58 | 33.72 ms | 48.55 ms | 1,024 | 232,416 | 6.13 MiB |

Both profiles use 28 draw calls. Lighter mode also reduces discharge/line density, render resolution and glow sampling. Its p95 shows occasional longer frames despite the 29.6 FPS average. Results are specific to this run, not a guarantee under every system load.

The final 15-second, 1080p, 30 FPS clip contains 450 encoded frames, including 41 duplicates from capture overhead. It shows the projection launch and idle energy; benchmark values above come from separate uncaptured runs.

## Artifacts

Evidence directory: `D:/EV/prototypes/cinematic_v4/evidence/fire_energy_restore/`

- `before_after.png`: fixed-clock comparison against the saved immediately preceding source.
- `final_energy_motion.mp4`: final actual Qt window capture, including launch.
- `final_standard.png`, `final_expanded.png`: actual layouts.
- `discharge_inspection.jpg` / `.json`: isolated ignition and extinction review.
- `validation.json`, `reaction_validation/`, `launch_validation/`, `connected_startup.json`: functional evidence.
- `benchmark_standard.json`, `benchmark_lighter.json`: separate performance runs.
- `previous_source/` and `baseline.json`: pre-edit snapshot.
- `current_task_audit.json`, `source_audit.json`, `source_manifest.json`: source boundary and reproducibility.

## Hashes and Git Commit

All 352/352 protected project source files are unchanged against this task's baseline. Existing unrelated working-tree changes remain in place. The older overnight audit separately records the already-authorised app/default-launch and GUI test changes.

- Surface fragment shader SHA256: `ffdf9ec3f204abcff8d9a9473ca4ae49208f3681f979aec5db692a5b3fe60568`
- Existing gui/app.py SHA256: `d3dde949ea4081bf8847c5d91dc0f7f7da333c82c499c5145628a2d0ccc78027`
- HEAD: `8237dbbf7055826806ee82b62520e1e88841d248`
- No commit created.

## Next Steps

Close any old E.V. window and reopen `D:/EV/Launch EV.cmd` to load the updated shared core. `D:/EV/Launch Cinematic Preview.cmd` opens the isolated preview. Review the real motion before accepting the visual direction; music and roadmap work remain separate.
