# Music foundation — first working milestone

Status: implemented and validated. This delivers the local-player/output-capture foundation and a usable Music workspace. The complete player, cloud adapters and visualizer gallery in the roadmap remain later milestones.

## Open and use

Launch `D:\EV\Launch EV.cmd`, or run `D:\EV\.venv\Scripts\python.exe -m gui.app` from the project directory. Select **Music** in the top navigation. At narrow widths, use the music-note button in the left rail.

- **Open tracks**, or drop local audio files onto the workspace. The first newly added track starts playing, and the remaining tracks form a session queue.
- Play/pause, previous/next, stop, seek, mute and volume controls work. Keyboard arrows on the seek slider move one second. Volume is saved between launches; the queue is session-only for this milestone.
- **E.V. player** analyzes that player's real decoded audio. **Windows audio** visualizes sound on the selected rendering endpoint, including other applications routed there. Capture has visible connect/stop controls and a device selector.
- The golden core moves into a corner and receives bounded music-level reaction while the assistant is idle. Assistant task/voice states retain normal visual priority. Returning to Assistant releases loopback capture and suspends analysis; local playback may continue.
- No microphone input, cloud account or TTS change is needed. No captured system audio is recorded or uploaded.

## Implementation

New `music/` modules provide a local Qt/FFmpeg playback session, a bounded analysis worker and a replaceable WASAPI loopback adapter. The analysis uses a 2048-sample Hann FFT, 64 logarithmic bands, waveform points, stereo levels, RMS, sample peak and bass/mid/treble energy. Each visualization reads the same analysis stream; capture is never fed back into an audio output.

`MusicWorkspace.qml` adds the player/queue, output and input controls, live spectrum/waveform, meters and transport. Existing mode changes continue through `GuiBridge`/`EVExperienceManager`; the music module adds no execution authority. The existing approval surface still disables the underlying stage. An open music file picker closes when the workspace becomes disabled.

Only three existing files were changed: `prototypes/cinematic_v4/integration.py`, `prototypes/cinematic_v4/qml/CinematicStage.qml` and `requirements.txt`. New modules, tests, validation helpers and documentation were added.

Requirements now declare PySide6 6.8+ (below 7), NumPy and Windows-only PyAudioWPatch 0.2.12.8. The latter was installed into E.V.'s existing virtual environment from its matching Python 3.12 Windows wheel. Qt/PySide6 itself was already 6.11.2 and was not upgraded.

The approved core meshes, shaders, palette and motion source are unchanged. Music controls the existing reaction input and its stage position/size. Startup sound assets and `core/tts.py` are unchanged; navigating to Music does not replay startup audio.

## Verification

- **33 unit checks passed in 1.64 seconds:** eight new music signal/lifecycle checks plus the 25 existing startup-audio checks. Known tones, anti-phase stereo, left-only audio, silence, nonfinite inputs, source reset, bounded queues and worker shutdown were covered.
- **23 rendered music checks passed:** real local PCM, playback, keyboard volume/seek controls, pause/mute release to silence, seek, loopback start/stop/reconnect, default-device reconnect, source switching, the generated silent passage, compact navigation, approval input ownership, Assistant restoration and clean shutdown. No QML/Python callback errors remained in the final run.
- **22 existing bridge/overlay integration checks passed.** Main command/response wiring, provider overlay and approval controls retained their behavior.
- **WAV, MP3 and FLAC decoded successfully.** MP3 and FLAC passed separate real-player checks, and two short files advanced automatically through the queue and stopped at its end. Other picker extensions remain backend-dependent and were not all tested.
- **Separate VLC and Chrome output tests passed.** A generated local signal was played by an isolated VLC process and an isolated headless Chrome profile. Both were detected through Windows loopback, with the 440 Hz test component measured at the expected nearest FFT bin, 430.664 Hz at 44.1 kHz. This verifies browser audio capture; it is not a test of the YouTube website, Spotify or cloud-provider playback.
- **Actual `gui.app` startup passed** with the normal threaded renderer, native chrome and the original startup signature. It reached launch completion, finished the announcement and shut down cleanly with no callback/QML errors.

The rendered captures cover 1920×1080 and 1100×760. Test audio was generated for this task; user music was not required. External test processes were closed afterward.

## Measurements and limits

CPU-only analysis timing over 200 measured stereo 2048-sample windows: **1.78 ms median, 3.31 ms p95**. This excludes capture, output, GUI and display latency. It is not an FPS benchmark or a measured end-to-end latency claim.

The local Qt WAV path delivered 4096-frame buffers at 48 kHz, approximately **85.3 ms of audio per buffer**. Presentation runs on a separate 33 ms timer with smoothing. Precise synchronization to physical speaker output and more detailed transient/beat analysis remain later tuning work. Local meters account for E.V.'s volume/mute, not the Windows master volume; loopback meters reflect the selected Windows mix.

The current device was **Remote Audio**, with 44.1 kHz stereo loopback. Reconnecting that endpoint/default selection was tested. Switching among different physical interfaces, Bluetooth, exclusive/protected paths and long-duration reliability still need hardware-specific testing. No 60 FPS claim or long-session stability claim is made for this milestone.

On Windows 10 build 19045, this captures an endpoint's mix rather than isolating one process. Other sounds on that endpoint will also appear. Cloud clients, persistent library/playlists, album metadata/artwork, EQ, gapless/crossfade, repeat/shuffle, accurate beat tracking, external media-session controls and additional visualizer presets have not been presented as completed features.

## Backup, hashes and Git

Before edits, **431 files** were backed up and SHA256-verified at:

`D:\EV\.ev-cinematic-nucleus-backups\20260916-175400-before-music-foundation`

All 431 backup copies were reverified afterward. Within the 352-file protected baseline, **351 files are unchanged**; `requirements.txt` is the single intentional dependency declaration update. No existing core/backend, GUI bridge or application-bootstrap source changed.

Full source hashes are recorded in `prototypes/cinematic_v4/evidence/music_foundation/source_manifest.json`. The source audit records the exact changed/new files and backup location. Evidence, generated fixtures, screenshots, codec/capture checks and timing measurements are in that same evidence directory.

No commit created. Existing unrelated working-tree changes were preserved.

Rollback this milestone by restoring the three changed existing files from this backup. The new Music modules and QML component then become unreferenced. PyAudioWPatch can remain installed without enabling capture. Do not restore unrelated backend files over future work.

## Next milestone

Review the player and real audio response with your music. Then build the persistent library/queue features and expand the visualizer controls/presets, using this proven local/decode/loopback foundation. Cloud-provider work follows the separate capabilities and restrictions described in the saved roadmap.
