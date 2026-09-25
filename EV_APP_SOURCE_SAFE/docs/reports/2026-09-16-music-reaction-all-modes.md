# Music reaction in Assistant and Music

Status: implemented. Restart E.V. once to load the update, then open Interface settings → Music reaction. All modes is the default; the intensity slider starts at 100%, with Assistant using one-quarter of that strength. Settings are saved between launches. The user's already-running E.V. instance was not restarted by this task.

## Behavior

- **All modes:** the selected source continues driving the core after leaving Music. Assistant uses subtle golden pulses, with at most 0.625% expansion. Music uses the existing stronger reaction, with at most 2.5% expansion.
- **Music only:** preserves the previous behavior. Leaving Music suspends analysis and releases Windows capture; returning resumes the requested source.
- **Off:** disables the core's music reaction everywhere. The Music workspace can still display its spectrum. Analysis/capture sleeps outside Music.
- The saved **0–100% intensity** changes visual strength without altering playback volume. The current gold palette, geometry and shader effects were not retuned.
- Listening, speaking, thinking, execution, verification, active task lifecycle and approval take priority. Pausing animation also suppresses music pulses. Ordinary idle awareness/telemetry-warning states may still react.
- Settings can select E.V. player or Windows audio, choose the output to capture, and stop/reconnect capture. A visible Windows audio status indicator appears above telemetry outside Music and opens settings. In All modes, switching between Assistant and Music preserves the same capture instance.
- Manually stopping capture stays stopped across navigation and device notifications. Playback can continue independently of visualization. No capture or analysis starts at ordinary launch without an active source; Windows-source selection is session-only.

## Implementation

`music/session.py` now separates Music-page visibility from analysis demand. It retains capture intent during a temporary Music-only suspension, distinguishes manual stop, and stores reaction preferences. `prototypes/cinematic_v4/integration.py` exposes a read-only priority check using the existing bridge's visual, voice, lifecycle and approval state.

`CinematicStage.qml` applies the appropriate reaction gain and status indicator. `MusicReactionSettings.qml` supplies the settings controls. `MusicWorkspace.qml` reports when core reaction is off or paused. The analyzer, onset detector, core meshes, shader and backend authority code are unchanged in this task.

## Validation

- 65 unit checks passed: 19 new preference/lifecycle/priority checks plus 46 existing onset, Music and startup-audio checks.
- 32 new real PCM and QML checks passed: Assistant receives both local-player and Windows-output beats; the actual core shader receives up to 0.25 in Assistant and 1.0 in Music; scale bounds hold; priority suppresses the pulse; real mode/slider/source/stop controls work; capture continuity, Off, manual stop and cleanup work. Settings were inspected at 1920×1080 and 1100×760.
- The existing 23-check Music regression explicitly runs with Music only selected, covering playback, seek, volume, mute, pause, silence, capture, navigation and approval.
- The existing 9-check beat/render validation explicitly runs with Music only selected and full intensity, checking known kick pulses and the unchanged Music response.

The new rendering helper uses generated audio and an isolated bridge without an executor. Its fixed envelope is used only for deterministic priority checks; source-to-core checks use actual PCM. Initial synchronous test waits prevented the worker from making progress; the helper now uses a Qt event loop that releases the Python GIL during waits. The final checks pass with real background analysis.

## Benchmarks and limits

No new FPS or speaker-to-screen latency benchmark was claimed. Validation uses forced frame readbacks, which affect displayed FPS. This update reuses the existing audio worker and detector; capture continues outside Music only when the selected policy and source call for it. Windows audio includes the selected output's mix, including other app sounds. Transient detection is not a predicted BPM grid.

## Backup, hashes and Git

Backup: `D:\EV\.ev-cinematic-nucleus-backups\20260916-195727-before-all-mode-beats` — 445 files copied and SHA256 verified before editing. Final verification, source manifest and validation results are under `D:\EV\prototypes\cinematic_v4\evidence\music_all_modes`. No Git commit was created. Pre-existing changes elsewhere in the workspace were preserved, including the backend and `core/tts.py`.

## Next steps

Restart E.V. once. For VLC/YouTube, open Interface settings, leave Music reaction on All modes, select Windows audio, and choose the output carrying the music. For E.V.'s local player, choose E.V. player. Adjust the intensity slider to taste; Assistant stays at one-quarter of the selected Music strength.
