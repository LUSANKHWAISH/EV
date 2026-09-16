# ASTRA — Music studio implementation plan

Status: **future work; no EQ or new preset is implemented by this document**. Read `ASTRA_HANDOFF.md` before editing. Deliver small verified milestones and keep the existing player usable throughout.

## 1. Reference observations and exact next target

User video: `F:\OneDrive\Videos\NVIDIA\Desktop\Desktop 2026.09.16 - 20.32.34.02.mp4`. Inspected metadata: 48.334 seconds, 1920×1080, H.264 at 120 frames/second, two AAC streams. Visual review used 48 one-second timeline samples across the recording and a full-resolution frame at 8 seconds. This establishes the visible arrangements and changing shapes; it is not a frame-by-frame reconstruction or a calibrated audio-to-screen latency measurement. Local review images are in `.astra-local/reference_review/` and are excluded from Git.

| Visible reference | Observation | E.V. preset specification |
|---|---|---|
| Top, roughly x=660–960 and y=196–350 | Many thin white bars extend downward from a fixed top baseline. The depth and frequency contour change rapidly; neighboring bins remain distinct. | **Ceiling Rain**: 96/128 log-frequency bars, top origin, 1–2 px gutters, fast attack and slower release, configurable gold/ivory/cyan palette. No moving baseline. |
| Lower left, roughly x=116–327 and y=790–845 | About ten broad bars rise from a bottom baseline; fine horizontal gaps give LED segmentation. | **Segment Stack**: default 10 bands, optional 16/32; rectangular cells; bottom origin; peak marker and optional stereo split. |
| Along lower edge, roughly x=180–760 and y=1005–1080 | A thin connected trace forms pronounced peaks and settles toward a baseline. Some portions are white/cyan. | **Flow Trace**: smooth spectrum-style curve with bounded interpolation, no invented negative magnitudes, optional stereo overlay or energy color. The video has no axis labels proving it is an oscilloscope; implement frequency mode first and offer a separately labelled time-waveform mode. |

All three are visible together for most of approximately 1–41 seconds. Near 0 and 42–48 seconds, the recording shows NVIDIA app UI. The wallpaper, launcher icons, CPU graph, desktop clock and news are not requests for E.V. features. Do not copy the wallpaper or recreate the Windows desktop.

**Immediate delivery: Reference Trio** — these three original visualizers arranged in Music, driven by one selected audio source, with the existing core dock and transport. Keep a familiar three-widget layout available even after adding studio instruments.

## 2. Workspace layout and interaction

Keep the canonical Music mode. Add `Player`, `Visualizer` and `Studio` layout choices inside Music, not separate audio sessions. Use a deterministic grid initially; add free resize/reordering only after the layouts work.

```text
┌ Music / current source / output device    Layout: Reference Trio    Presets ┐
│                      Ceiling Rain — full width                          │
├──────────────────────────────────────────────┬───────────────────────────┤
│                                              │                           │
│               Flow Trace                     │       Segment Stack       │
│                                              │                           │
├──────────────────────────────────────────────┴───────────────────────────┤
│ persistent transport: title / previous / play / next / seek / volume      │
└──────────────────────────────────────────────────────────────────────────┘
Separate collapsible rail: queue / library and the existing small golden core.
```

At 1920×1080 use roughly 24 px gaps, a 220–260 px queue/core rail, 88–112 px transport and a 140–180 px top strip. The central grid consumes remaining space, not hardcoded screen coordinates. At 1100×760 collapse library/queue to drawers, use a 120–140 px core dock and minimum 44 px primary touch/click targets where practical. Reserve the transport and core rectangles before solving panel layout; do not overlap them. Fullscreen hides chrome until interaction, Esc exits, and approval always remains above it.

Each instrument has a header with name, source/tap, settings, freeze and close. Freeze affects that display only. “Add visualizer” adds a bounded instance; duplicate presets are allowed with different settings. “Solo” temporarily enlarges one instrument and restores its prior geometry. Add reset layout, lock layout, snap/resizing, and keyboard-accessible equivalent controls. Clamp saved geometry on resize; never restore a panel off-screen.

Initial limit: **four analysis panels plus the core** on the GTX 970; the three reference panels are the default. This is a starting budget, not an assumed device limit. A later measured high-performance tier can allow six. Draw only visible panels; collapsing a panel releases its renderer/subscription. Preset files are validated data, never executable Python/JS/QML supplied by a user.

Proposed versioned layout data:

```json
{
  "schema": 1,
  "layout": "reference-trio",
  "columns": 12,
  "panels": [
    {"id":"rain-1","preset":"ceiling-rain","x":0,"y":0,"w":12,"h":2,"options":{"bands":128}},
    {"id":"trace-1","preset":"flow-trace","x":0,"y":2,"w":8,"h":4,"options":{"mode":"spectrum"}},
    {"id":"led-1","preset":"segment-stack","x":8,"y":2,"w":4,"h":4,"options":{"bands":10}}
  ]
}
```

Persist under a `core.paths` runtime config directory with atomic replacement and a previous-good backup. Validate schema, finite values, preset allowlist, size/count bounds and collision-free placement. Migrate schema explicitly; invalid data restores the default layout without losing the music library.

## 3. Preset catalogue and acceptance

| ID | Instrument | Required controls and behavior |
|---|---|---|
| `ceiling-rain` | Reference top bars | Bands, spacing, height/gain, attack/release, palette, origin. |
| `segment-stack` | Reference LED bars | Bands, segment/gap size, peak hold/fall, stereo split. |
| `flow-trace` | Reference flowing trace | Spectrum/time choice, stroke/fill, smoothing, channel overlay. |
| `precision-spectrum` | SPAN-inspired analysis | Log 20 Hz–20 kHz axis, calibrated dBFS, FFT 2048/4096/8192, average, peak hold, cursor Hz/dB, L/R/M/S selection and freeze. |
| `parametric-eq` | Fruity Parametric EQ-inspired editor | Seven draggable nodes, frequency/gain/Q, filter type/bypass, summed response and input/output spectrum. Editing requires a real DSP-capable source. |
| `wave-scope` | Wave Candy-inspired oscilloscope | Triggered L/R or mono waveform, timebase, level, trigger source/threshold, freeze. Use actual time-domain PCM, not FFT bins. |
| `spectrogram` | Wave Candy-style frequency history | Time horizontal, log frequency vertical, fixed dB color map; bounded history texture/ring. Label time/frequency axes. |
| `stereo-scope` | Wave Candy-style vectorscope | L/R or M/S plot, bounded point persistence, correlation meter; guard silence division. |
| `level-meter` | Peak/RMS meter | Separate stereo levels, dBFS scale, hold/reset, over indicator. Do not label sample peak “true peak” without oversampling validation. |
| `mirror-bars` | Monstercat-inspired decorative bars | Mirrored rhythm bars, track/art region and restrained bloom; original styling. |
| `orbit-spectrum` | Circular decorative spectrum | Arc bins, bounded radial growth, optional sparse sparks; avoid competing with the core. |
| `minimal-line` | Cantarell/illustro/NR_Kantas-inspired option | Thin bars or line, large negative space, configurable accent, very low renderer cost. |

SPAN is a Voxengo product; Fruity Parametric EQ and Wave Candy are FL Studio instruments. They are references for functionality, not one combined plugin called “FL SPAN.” Do not ship their binaries, screenshots, logos or exact skins. VST hosting, Rainmeter skin loading and external plugin licensing are optional separate projects, unnecessary for these built-in E.V. instruments.

## 4. Share analysis, not capture threads

Current data path:

```text
QMediaPlayer -> QAudioBufferOutput ┐
                                 ├-> AnalysisWorker -> MusicSession -> QML/core
WASAPI selected-output loopback ──┘
```

Extend this with one analysis bus per selected source. Multiple widgets subscribe to immutable snapshots; they must not instantiate additional loopback clients, player instances or independent FFT workers. Cache each distinct `(source, generation, window_size, hop, channel_mode)` analysis request. Compute 4096 bins once and aggregate to 10/64/128 display bands; do not calculate three FFTs for the three decorative views. Keep the existing onset detector independent of decorative display smoothing.

Suggested new files, introduced incrementally:

```text
music/contracts.py                  # block/frame identifiers and source capabilities
music/analysis_bus.py               # shared FFT/scope/history snapshots
music/preset_registry.py            # allowlisted built-in preset metadata
music/workspace.py                  # layouts, subscription ownership, persistence
music/dsp/biquad.py                 # filter coefficients, tests first
music/dsp/chain.py                  # preamp, filters, transitions, bypass
music/playback/base.py              # player capabilities and events
music/playback/qt_media.py          # preserve the current working backend
music/playback/pcm_player.py        # future owned decoder/DSP/output proof
music/library.py                   # later SQLite metadata/library
prototypes/cinematic_v4/qml/music/VisualizerBoard.qml
prototypes/cinematic_v4/qml/music/VisualizerPanel.qml
prototypes/cinematic_v4/qml/music/presets/*.qml
tests/test_music_analysis_bus.py
tests/test_music_layouts.py
tests/test_music_dsp.py
```

Do not rename/move the working cinematic tree as part of this feature. A later packaging refactor can remove the `prototypes` name after imports, resource paths and tests are migrated together.

Proposed contracts (design sketch; implement and test in M1/M2):

```python
from dataclasses import dataclass
from typing import Literal
import numpy as np

@dataclass(frozen=True)
class AudioBlock:
    source_id: str
    generation: int           # increments on seek, source/device/format discontinuity
    first_frame: int
    rate: int
    pcm: np.ndarray           # float32 [frames, channels], read-only owned snapshot
    presentation_time: float  # monotonic audio presentation estimate, not render time

@dataclass(frozen=True)
class AnalysisFrame:
    source_id: str
    generation: int
    sequence: int
    presentation_time: float
    frequencies: np.ndarray
    spectrum_dbfs: np.ndarray
    waveform: np.ndarray
    rms_lr: tuple[float, float]
    sample_peak_lr: tuple[float, float]
    correlation: float | None
    beat: float
    tap: Literal['pre_eq', 'post_eq', 'system_mix']
```

`frozen=True` does not make NumPy arrays immutable: explicitly copy at ownership transfer and set `array.flags.writeable=False`. Keep worker-owned arrays separate. Bound PCM history in frames and seconds, FFT request count, panel instances and texture history. Publish the latest frame at a controlled cadence, never one Qt signal per FFT bin. GUI models and QML properties update on the Qt thread using queued signals; capture callbacks do only bounded copying/enqueueing. Do not evaluate provider/assistant code inside audio callbacks.

For 48 kHz, 4096 samples span 85.33 ms; 8192 span 170.67 ms. High frequency resolution trades against responsiveness. Share a smaller hop (e.g. 512/1024) but do not claim the long window has zero latency. Track presentation timestamps, source generation, dropped blocks and freshness; reject stale generations after seek/source changes. UI intensity must not change the reported dBFS value.

## 5. Analysis correctness

- Apply a Hann window; use its coherent gain for amplitude calibration. Treat DC/Nyquist separately when doubling a one-sided spectrum.
- Display RMS and sample peak as separate quantities: a full-scale sine is 0 dBFS peak and about −3.01 dBFS RMS. Averaging and peak hold happen on a documented amplitude/power domain, not arbitrary pixel heights.
- Aggregate logarithmic bins with a defined max/energy policy. Label whether a curve is channel magnitude, energy sum, or mid/side. Combine channel energy before summing when avoiding anti-phase cancellation.
- Decorative smooth curves can differ from the precision analyzer, but both must come from the same measured samples. Silence settles to a floor, not fabricated movement.
- A true oscilloscope needs a time window and trigger. A spectrogram stores bounded FFT history. Correlation uses normalized covariance/energy, returns unknown near silence and remains in [−1,1].
- Add FFT size and smoothing controls to the precision instrument, not dozens of global settings affecting unrelated panels.
- Use QSG geometry/Qt Quick scene graph for dense bars, paths and dots; a small QML Canvas proof is acceptable for M1, but profile three/four simultaneous canvases. Never use one QML object per 8192 bin or create a new 3D renderer per simple meter. Use a bounded texture for the spectrogram rather than redrawing minutes of history in JavaScript every frame.

Minimal data-to-view outline (the registry supplies known components; no arbitrary URLs):

```qml
// Sketch for VisualizerBoard.qml; model/controller still to be implemented.
Item {
    required property var workspace
    required property var analysis
    Repeater {
        model: workspace.panels
        delegate: VisualizerPanel {
            required property var modelData
            panelId: modelData.id
            presetId: modelData.preset
            options: modelData.options
            analysisFrame: analysis.frame
            // Resolve placement through the tested grid model, not screen constants.
            x: workspace.rectFor(panelId).x
            y: workspace.rectFor(panelId).y
            width: workspace.rectFor(panelId).width
            height: workspace.rectFor(panelId).height
        }
    }
}
```

## 6. Real equalizer: mandatory audio boundary

**Do not add working-looking EQ sliders to QAudioBufferOutput and call the result an equalizer.** The current tap is observational. M3 must own audio between decoding and output, or use a proven backend that applies real filters. Keep a `PlaybackBackend` adapter and the old Qt player until the replacement passes.

Recommended proof to evaluate: PyAV/FFmpeg decoding in a worker → bounded float PCM ring → DSP worker → QAudioSink output. PyAV and SciPy are proposed new dependencies, **not installed by this plan**. Confirm wheels, licensing, shipped codec behavior and Qt sink format support. If the Python callback/queue cannot meet measured deadlines, move only the real-time bridge/DSP to a small compiled extension rather than rewriting the application.

```text
selected owned stream/file
  -> decoder + explicit channel/sample-rate conversion
  -> pre-EQ analysis tap
  -> preamp -> EQ sections -> transition/bypass -> output headroom stage
  -> post-EQ analysis tap -> bounded output ring -> QAudioSink
                                          -> authoritative playback clock

Windows loopback -> analysis bus only (no E.V. playback EQ effect)
```

Implementation rules:

1. Define backend methods `load`, `play`, `pause`, `stop`, `seek`, `set_output`, `set_volume`, `set_eq`, `close`, plus capability/status signals. Do not expose backend internals to every QML component.
2. The decoder must honor bounded queue capacity. Do not decode a two-hour file into memory. Keep FFmpeg container access on its owner thread; process seek commands there. Seek increments generation, flushes decoder/resampler/output rings and filters, resets analysis and ignores old packets. Account for codec priming and seek granularity.
3. Negotiate rate/channels/float format with the output device. Handle mono/stereo explicitly; downmix multi-channel using a documented matrix. Reject/convert unsupported formats. Never assume a 48 kHz device when the music is 44.1 kHz.
4. Feed the sink without FFT, network I/O or blocking disk access in the callback. An underrun supplies silence and increments a diagnostic counter; it must not block the GUI. Handle output-device loss, sample-rate change and restart with a new generation.
5. Base position on consumed/presented audio plus stream offsets, not decoder progress. Pause stops consuming; stop clears queues. Separate decoding-ahead from audible time for visuals.
6. Start with unity/bypass PCM playback. Prove volume, mute, seek, EOF, next track, cancellation and shutdown before inserting filters.
7. Apply EQ only to E.V.-owned unprotected PCM. For Windows input show “Analyze only — EQ applies to E.V. playback.” Pre/post tap choice is unavailable for system mix. A virtual audio-driver/system-wide equalizer is a separate explicitly requested product, not a dependency of this milestone.

### Graphic EQ first

Ten centers: 31, 62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000 Hz. Gains ±12 dB, preamp −18 to +6 dB, flat reset, bypass and saved presets. Clamp high bands below the actual Nyquist limit. Start with consistent broad Q and document that it is a graphic approximation, not independent brick-wall bands.

### Seven-band parametric editor

Low shelf, five peaking bands, high shelf initially; add high/low pass with defined slopes as separate supported types. Frequency 20 Hz to `min(20000, 0.45*rate)`, gain ±18 dB, Q 0.1–18. Drag horizontally in log frequency and vertically in gain; wheel/keyboard adjust Q, double-click resets that band. Numeric fields are always available. Show the summed electrical filter response distinctly from the incoming audio spectrum.

Reference peaking-filter coefficients (RBJ-style normalized biquad; standalone algorithm sketch):

```python
import math
import numpy as np

def peaking_sos(rate: float, hz: float, gain_db: float, q: float) -> np.ndarray:
    if not all(math.isfinite(v) for v in (rate, hz, gain_db, q)) or rate <= 0:
        raise ValueError('Finite parameters and positive sample rate required')
    hz = min(max(20.0, hz), rate * 0.45)
    q = min(max(0.1, q), 18.0)
    gain_db = min(max(-18.0, gain_db), 18.0)
    a = 10.0 ** (gain_db / 40.0)
    w = 2.0 * math.pi * hz / rate
    alpha = math.sin(w) / (2.0 * q)
    c = math.cos(w)
    numerator = np.array([1+alpha*a, -2*c, 1-alpha*a], dtype=np.float64)
    denominator = np.array([1+alpha/a, -2*c, 1-alpha/a], dtype=np.float64)
    return np.r_[numerator/denominator[0], 1.0, denominator[1:]/denominator[0]]

# Proposed DSP worker usage after installing/testing SciPy:
# sos = np.stack([peaking_sos(rate, b.hz, b.gain_db, b.q) for b in enabled_bands])
# zi = np.zeros((len(sos), 2, channel_count), dtype=np.float64)
# block_out, zi = scipy.signal.sosfilt(sos, block_in, axis=0, zi=zi)
# Retain zi across contiguous blocks. Reset only at an explicit discontinuity.
```

This snippet is not a complete EQ backend, shelf/pass filter design or a tested real-time output implementation. The next agent must add unit tests and audible output proof. Parameter changes require smoothing: prefer a 20–50 ms crossfade between stable old/new filter chains with separate state, or another stability-verified transition. Uncontrolled coefficient interpolation can become unstable; abrupt resets click. Bound parameter-update frequency and coalesce drag updates.

Headroom: estimate the maximum of the **combined** response, not just the largest band gain; overlapping boosts add. Offer automatic preamp compensation with a margin and show peak/overload. A tested limiter can be a later separate stage. Do not hide clipping behind `np.clip()` and advertise transparent mastering. Bypass should crossfade click-free, retain settings and have explicit unity/volume semantics.

## 7. Player/library/cloud continuation

After M3/M4: SQLite library with stable IDs, read-only tag/art extraction (e.g. Mutagen after dependency review), bounded artwork cache, import selected folders, path deduplication, unavailable/OneDrive-placeholder handling, persistent playlists and queue, shuffle history, repeat modes and media-session controls. Default restart restores paused, not autoplay. Implement gapless/crossfade only when the backend can coordinate sample-accurate transitions and gain.

First cloud paths: locally available synchronized files, progressive HTTP(S)/radio, then one personal library such as Jellyfin or a Subsonic-compatible server. Use source capability flags (`seek`, `eq`, `crossfade`, `pcm`, `download`, `metadata`, `external_transport`). Network workers handle retries, cancellation and expiring URLs; secrets belong in protected storage. YouTube pages are not direct audio URLs. Commercial provider SDKs, authentication, DRM, subscriptions and current policies must be checked independently; do not promise universal PCM/EQ/visualizer access or implement hidden stream extraction. External Windows visualization and official provider integration remain distinct features.

## 8. Performance and validation gates

Targets for testing on this PC: standard 60 FPS render target; lighter 30 FPS profile with reduced detail/work, not only a sleep. Start analysis publication at 30 Hz; interpolate simple display envelopes if rendering at 60. Precision spectrum may use 15–30 Hz; spectrogram history 20–30 columns/s. Reduce resolution/history length in lighter mode. Target no audible underruns during a 30-minute playback test; report actual counters and CPU/GPU/memory, not just “smooth.”

M1 tests: three panels visibly react to the same generated bass/mid/high sequence; silence stops them; no extra capture instance per panel; switching layouts/presets/source or minimizing doesn't leak workers; layout restored within bounds at 1100×760/1920×1080; all-modes core/approval priority still passes.

M2 tests: 100 Hz/1 kHz/10 kHz tones peak at expected frequency tolerance, full-scale sine peak/RMS calibration, stereo left-only/anti-phase/noise, DC and silence, trigger stability, finite correlation, bounded spectrogram memory. Compare a held frame and axes to numeric analysis data.

M3/M4 tests: unity/bypass null or documented tolerance, ±6 dB at a band's center, multi-band frequency response, stable impulse decay, finite output at parameter extremes, stereo independence, sample-rate switching, silent input, discontinuities, rapid dragging, preamp/headroom, no clicks and real audible/output-recorded spectral change. Use a low-volume generated signal and isolate test routing; do not capture private user music or microphone input.

Document audio-to-display offset with loopback timestamps and a transient fixture; 120 FPS video metadata is not proof of visualizer latency or performance. Test with E.V. voice enabled later as an explicit controlled coexistence task; music through speakers can retrigger ASR/wake-word and should not be treated as solved.

## 9. Small commit sequence for the next agent

1. **M1a** analysis snapshot adapter + one panel host; retain current visualizer as fallback.
2. **M1b** Ceiling Rain, Segment Stack, Flow Trace + Reference Trio layout + keyboard/settings controls.
3. **M1c** saved layouts, bounds/resize and measured four-panel performance; user visual review.
4. **M2a/b** precision spectrum/scopes, then spectrogram/stereo meters; calibrated fixtures.
5. **M3a** playback-backend interface and owned-PCM unity proof; do not remove Qt fallback yet.
6. **M3b** ten-band EQ/preamp/bypass, recorded output proof and device/seek regression.
7. **M4** parametric editor + stable coefficient transitions + presets.
8. **M5/M6** library, full transport, cloud adapters after the audio foundation is stable.

Each commit must say what is implemented, what was actually tested, remaining limitations and how to revert. Do not mark a gallery tile “available” until its renderer works. Do not convert a missing backend into a fake animation. Keep build instructions and this milestone table current.

## Technical references to verify at implementation

- Qt buffer observation: <https://doc.qt.io/qt-6/qaudiobufferoutput.html>
- Qt output ownership: <https://doc.qt.io/qt-6/qaudiosink.html>
- PyAV docs: <https://pyav.org/docs/stable/>
- SciPy SOS processing: <https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.sosfilt.html>
- RBJ audio EQ cookbook: <https://www.w3.org/TR/audio-eq-cookbook/>
- Windows loopback: <https://learn.microsoft.com/en-us/windows/win32/coreaudio/loopback-recording>

These are implementation reference links, not claims that every external API/provider policy was freshly revalidated during this planning-only checkpoint.
