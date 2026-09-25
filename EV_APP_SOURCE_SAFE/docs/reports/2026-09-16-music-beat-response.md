# Music core beat response — 16 September 2026

Status: implemented and validated. Restart the running E.V. app once to load the changes. Its existing process and session queue were left running during this task.

The previous core followed smoothed audio energy, so individual hits had little visual impact. Its spectrum also examined only the last portion of a decoded buffer, which could miss a short attack near the beginning. The music analyzer now detects spectral onsets throughout each buffer and sends timed pulses to the actual core material. Both E.V. player audio and selected Windows-output loopback use this path.

## Implementation

- New `music/onsets.py` detects spectral changes in overlapping 1024-sample windows with a 512-sample hop, adaptive threshold, silence gate and 145 ms retrigger guard. It combines stereo energy without cancellation and handles nonfinite input.
- `music/analysis.py` maintains a bounded onset queue, preserves positions within decoded buffers and clears events when sources reset. `music/session.py` exposes an immediate-attack, 115 ms release envelope and clears it for silence, pause, mute or stale audio.
- The docked Music core brightens its golden hub and selected sharp discharge lanes on each hit, with at most 2.5% rigid expansion. The existing geometry, camera and palette remain in place. The pulse uniform defaults to zero outside Music; voice/task/approval state priority and animation pause remain effective.
- `music/README.md` documents the behavior. New unit and rendered validation helpers exercise real decoded PCM and Windows loopback.
- The existing Music validation helper now waits for actual playback position, within a bounded deadline, so slow codec/device initialization does not produce a false failure. Its playback assertions are retained.

## Test results

- 46 unit checks passed in 5.62 seconds: new onset/envelope tests, Music foundation and startup audio regression.
- 9 real playback/render checks passed: ten known kick hits produced ten distinct pulses; shader pulse reached 1.0; scale stayed at or below 1.025; silence and stop cleared the response; Windows loopback drove the same signal; Assistant had no music pulse; no render/callback errors.
- 23 existing Music playback, control, capture, navigation and approval checks passed. The tested loopback endpoint was BenQ VZ2250 (NVIDIA High Definition Audio).
- 18 default-core render checks passed, including transparent borders, camera bounds, assembly, lighter mode, motion, lighting and pause. Comparisons against the pre-change backup showed sparse, very small raster differences rather than exact byte identity; mean absolute differences were below 0.0007 on the 0–255 channel scale.

Total: 96 passing automated checks. Rendered fixtures use isolated application instances and generated audio; they do not run the live executor or use a microphone. The user's running app still requires a restart.

## Benchmarks and limits

The onset detector alone took a median 2.22 ms and a 95th percentile 4.22 ms per 4096-frame stereo block in the local timing run. This excludes the existing spectrum analysis, capture, GUI, speaker latency and rendering. It is not an FPS benchmark or a measured speaker-to-screen latency guarantee.

With procedural motion frozen for comparison, the core crop's summed red/green intensity rose by approximately 14.2% on the test hit. The beat shader uniform and bounded scale were checked on the rendered core itself.

The detector responds to attacks in the audio, not a predicted tempo grid. Dense tracks, sustained material and different mixes may need tuning. Windows audio captures the selected output mix, including other apps and notifications. Cloud playback integration and advanced BPM/beat tracking remain separate roadmap work.

## Backup, hashes and Git

Pre-change backup: `D:\EV\.ev-cinematic-nucleus-backups\20260916-193058-before-music-beats` (441 files). The final source audit and SHA256 manifest are saved under `D:\EV\prototypes\cinematic_v4\evidence\music_beats`. The protected-source audit compares against the start of this task, preserving the repository's earlier work. No backend authority or TTS changes were included. No Git commit was created.

## Next steps

Restart E.V., open Music, and play a track through E.V. player. For VLC/browser playback, select Windows audio and the device carrying that sound. The docked core should now produce quick golden pulses on audible attacks and settle between them.
