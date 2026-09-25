# 01 — PROJECT STATUS: E.V. Desktop Application

## 1. Completed Features
- **Cinematic Presentation & 3D Nucleus (Astra Core)**:
  - GPU-instanced Qt Quick 3D celestial sphere (`gui/qml/components/presets/EVCoreFlagshipVisual.qml`).
  - 4 concentric particle shells (Hero Stars along helical ribbons, Mantle/Shell, Nucleus Cluster, Atmospheric Dust Crust).
  - Smooth mouse orbit interaction with spring-back to center.
  - Attentive voice behavior: rotation halts monotonically during listening/speaking, luminosity blooms with audio energy.
  - Multi-profile rendering target (60 FPS default, lighter 30 FPS mode).
- **Core Action Execution & Safety Engine**:
  - Structured PowerShell execution pipeline (`core/action_pipeline.py`, `core/plan_executor.py`).
  - Validation, risk analysis, and explicit approval boundaries (`core/risk.py`, `core/plan_validator.py`).
  - Pre-execution backup and deterministic rollback mechanics (`core/backup.py`, `core/recovery.py`).
  - Strict anti-bypass security: voice/brain/memory layers have zero execution authority.
- **AI Provider Management & DPAPI Key Security**:
  - Multi-provider support (`providers/`): Anthropic, Google Gemini, OpenAI, Azure OpenAI, OpenRouter, Groq, Ollama.
  - DPAPI credential encryption (`CryptProtectData`/`CryptUnprotectData`) via `core/provider_config.py`.
  - Invariant: Exactly one active provider at any given time.
  - Key masking in UI (`••••••••••••`).
  - Side-effect-free connection probe classifying HTTP status codes.
- **Music Playback & Audio Loopback Foundation**:
  - Qt PCM tap (`QAudioBufferOutput`) and Windows WASAPI loopback capture (`PyAudioWPatch`).
  - Real-time 64-band FFT spectrum, waveform, RMS/peak, and 3-band energy (bass, mid, treble).
  - Spectral onset detection (1024-sample window, 512 hop, adaptive threshold, 145 ms retrigger guard).
  - Multi-mode beat reactivity: All Modes, Music Only, Off, with saved intensity.
- **Startup Sound Signature**:
  - Procedural "E.V. online" sound signature (`prototypes/cinematic_v4/startup_audio.py`), once per launch, yielding cleanly to voice/task/close events.
- **Settings & HUD Overlays**:
  - Dark blue & gold settings overlay (`gui/qml/components/EVSettingsOverlay.qml`).
  - Experience mode switcher (STANDARD, AI, WORK, MUSIC, SYSTEM, APPROVAL, SLEEP).

---

## 2. Partially Completed Features
- **Multi-Visualizer Studio (Active In-Progress Work)**:
  - Implemented in working tree: `music/workspace.py` (atomic layout persistence, grid validation), `VisualizerBoard.qml`, `CeilingRain.qml`, `FlowTrace.qml`, `SegmentStack.qml`.
  - Remaining: Interactive drag-and-drop / resizing handles in QML, per-panel color scheme customization, panel preset selector in settings drawer.
- **Voice Interaction Pipeline**:
  - Implemented: Wake-word engine (`openWakeWord`), ASR module (`faster-whisper`), voice activity detector (`voice_vad.py`), synthetic bridge telemetry.
  - Remaining: Full continuous conversational loop with live TTS PCM mixing and echo-cancellation against background music.
- **Conversation & Task Memory**:
  - Implemented: SQLite stores (`core/history.py`, `core/memory.py`), transaction logging.
  - Remaining: Semantic search over past troubleshooting sessions, auto-cleanup policy for large history databases.

---

## 3. Planned / Missing Features
- **Audible Playback Equalizer (EQ) & Parametric DSP**:
  - Current `QAudioBufferOutput` is a read-only PCM tap. Modifying the buffer does not affect heard audio. An owned decode/DSP/output pipeline is required for an audible equalizer.
- **Persistent Music Library & Playlists**:
  - Current music session supports queue playback and file selection, but lacks persistent ID3 tag extraction, album artwork rendering, and playlist saving.
- **Mobile Companion / WhatsApp / Remote Pair**:
  - Documented as future roadmap items; zero code implemented.
- **Production Installer & Auto-Update**:
  - No installer or auto-updater configured. Application currently runs via Python virtual environment or `.cmd` batch scripts.

---

## 4. Broken / Failing Areas & Known Bugs
- **Pytest Tempdir Access Denied on Windows**:
  - Running pytest without specifying `--basetemp` fails on `pathlib.Path.stat()` when checking pytest's default symlink (`pytest-current`) in `%TEMP%`.
  - **Status**: Mitigated via documented `--basetemp` flag.
- **Selected-Output Mixing Scope**:
  - On Windows 10 build 19045, WASAPI captures the entire default output mix. Per-process audio loopback requires newer Windows 10/11 APIs.

---

## 5. TODO / FIXME Summary
- Search of codebase shows zero unresolved `FIXME` items.
- A single historical `TODO: bind to actual state` exists in an archived handoff file (`handoff/012C2/EVFlagshipStage_012C2.qml`), which was superseded by `prototypes/cinematic_v4/qml/CinematicStage.qml`.

---

## 6. Technical Debt
- **Dependency Specification**: `requirements.txt` contains only 6 unpinned packages. The `.venv` environment has 77 packages installed, including heavy ML packages (`ctranslate2`, `faster-whisper`, `onnxruntime`, `torch`/`torchaudio` dependencies). Needs separate `requirements-core.txt` and `requirements-voice.txt`.
- **Legacy Backup Trees**: The repository contains numerous historical backup directories (`backup_018K3_*`, `handoff/*`, `gui_backup_*`) totaling over 500 MB. These should be archived externally.
- **QML Code Organization**: Several production QML files reside in `prototypes/cinematic_v4/qml/` while being directly imported by the canonical app. They should eventually be migrated to `gui/qml/`.

---

## 7. Security & Privacy Assessment
- **Zero Plaintext Secrets in Code**: Scanned codebase for API keys, tokens, passwords; all detected key-like strings are mock fixtures in test suites (`tests/test_gemini_provider.py`, `tests/test_provider_config.py`).
- **DPAPI Credential Isolation**: Real provider API keys are encrypted with Windows DPAPI and stored in `%LOCALAPPDATA%\EV\config\ai_credentials.bin`, accessible only by the logged-in Windows user.
- **Execution Boundary**: All PowerShell commands must pass through `PlanValidator` and `RiskAssessment`. Mutating actions require explicit user approval via modal overlay.
- **Loopback Privacy**: WASAPI audio capture is processed in-memory for FFT/transient extraction and discarded immediately. No raw audio is recorded to disk.

---

## 8. Release Readiness Assessment
- **Status**: **ALPHA / DEVELOPMENT**
- **Production Deployment Ready**: **NO**
- **Internal Developer Ready**: **YES**
- **Test Suite Pass Rate**: **100%** on active suites (164/164 tests passed across music, workspace, GUI settings, GUI modes, and core pipeline).

---

## 9. Completion Estimate
- **Estimated Completion**: **~72%** (Clearly marked as an estimate)
- **Evidence Used for Estimate**:
  - **Core Troubleshooting Engine**: 95% complete (pipeline, risks, verification, rollbacks, providers fully tested).
  - **3D Cinematic UI / Presentation**: 90% complete (GPU particle core, responsive stages, HUD, theme).
  - **Audio Analysis & Beat Reactivity**: 85% complete (FFT, onsets, multi-mode reactivity, startup sound).
  - **Multi-Visualizer Studio**: 50% complete (layout store and QML panels created; docking/drag handles missing).
  - **Playback Equalizer & DSP**: 15% complete (architecture planned, DSP pipeline not yet built).
  - **Voice Pipeline**: 60% complete (wake-word and ASR functional, continuous duplex loop incomplete).
  - **Packaging & Deployment**: 10% complete (runs via `.cmd` scripts; no installer, CI/CD, or auto-updater).
