# 02 — ARCHITECTURE: E.V. Desktop Application

## 1. High-Level Architecture Overview
E.V. is structured as a dual-layer desktop application:
1. **Frontend / Presentation Layer**: Built on Qt Quick 2 and Qt Quick 3D (via PySide6), rendering a GPU-instanced 3D particle nucleus ("Astra Core"), audio visualizers, and reactive HUD surfaces.
2. **Backend & Automation Core**: Python 3.12 subsystem orchestrating asynchronous AI providers, system monitoring, structured PowerShell execution with pre-execution safety verification and rollback, and a dedicated WASAPI audio analysis worker.

Communication between the UI and backend is managed via a centralized `GuiBridge` (`gui/bridge.py`), exposing strongly typed Qt properties, signals, and slots with thread safety.

```mermaid
graph TD
    subgraph Frontend [Presentation Layer (Qt Quick / QML / Qt Quick 3D)]
        UI[ConnectedWindow / CinematicStage]
        Core3D[EVCoreFlagshipVisual - 3D Celestial Nucleus]
        Viz[VisualizerBoard - Multi-Visualizer Studio]
        Settings[EVSettingsOverlay - Provider Config]
        Approval[ApprovalOverlay - Mutating Action Consent]
    end

    subgraph Bridge [Qt Bridge Layer]
        GB[GuiBridge (QObject)]
        VS[VisualState Coordinator]
        MS[MusicSession (QObject)]
    end

    subgraph AudioEngine [Audio & Music Engine]
        WASAPI[PyAudioWPatch Loopback]
        PCM[QAudioBufferOutput Tap]
        Worker[AnalysisWorker (NumPy FFT)]
        Beats[Beat & Onset Detector]
        Workspace[WorkspaceStore (Layouts)]
    end

    subgraph CoreEngine [Core Troubleshooting & Execution Engine]
        AP[ActionPipeline]
        PlanVal[PlanValidator]
        Risk[RiskAssessment]
        Exec[PlanExecutor (PowerShell)]
        Backup[Backup & Rollback Manager]
        Monitor[SystemMonitor]
    end

    subgraph AIProviders [AI Provider Subsystem]
        BPM[BrainProviderManager]
        DPAPI[DPAPICredentialStore (Windows DPAPI)]
        Gemini[GeminiProvider]
        Anthropic[AnthropicProvider]
        OpenAI[OpenAI / Azure / Groq / Ollama]
    end

    UI --> GB
    Core3D --> GB
    Viz --> MS
    Settings --> GB
    Approval --> GB

    GB --> VS
    GB --> AP
    GB --> BPM
    MS --> Worker
    WASAPI --> Worker
    PCM --> Worker
    Worker --> Beats
    Beats --> MS
    MS --> GB
    MS --> Workspace

    AP --> PlanVal
    PlanVal --> Risk
    Risk --> Exec
    Exec --> Backup
    Exec --> Monitor

    BPM --> DPAPI
    BPM --> Gemini
    BPM --> Anthropic
    BPM --> OpenAI
```

---

## 2. Main Processes & Modules

| Module | Responsibility | Key Files |
|---|---|---|
| **GUI Bootstrap** | Application launch, QML engine initialization, signal wiring | `gui/app.py`, `Launch EV.cmd` |
| **Bridge & State** | Thread-safe UI-backend communication, property synchronization | `gui/bridge.py`, `gui/visual_state.py` |
| **Cinematic Core** | 3D celestial particle orb, motion, glints, shader passes | `gui/qml/components/presets/EVCoreFlagshipVisual.qml`, `prototypes/cinematic_v4/qml/Nucleus*.qml` |
| **Action Pipeline** | Planning, validation, permission gating, PowerShell execution | `core/action_pipeline.py`, `core/plan_validator.py`, `core/plan_executor.py` |
| **Risk & Safety** | Risk classification, rollback transactions, security boundary | `core/risk.py`, `core/backup.py`, `core/recovery.py` |
| **Audio & Music** | Loopback capture, FFT analysis, onset detection, visualizers | `music/session.py`, `music/analysis.py`, `music/onsets.py`, `music/workspace.py` |
| **AI Providers** | Multi-provider dispatch, DPAPI credential security, connection test | `core/provider_config.py`, `core/brain_provider.py`, `providers/` |
| **Voice & Speech** | Wake-word detection, ASR transcription, speech synthesis | `core/voice_manager.py`, `core/voice_wakeword.py`, `core/asr_faster_whisper.py` |
| **Paths & Data** | Deterministic resource and runtime directory resolution | `core/paths.py` |

---

## 3. Entry Points
- **Canonical Application**:
  ```powershell
  .\.venv\Scripts\python.exe -B -m gui.app
  # or Launch EV.cmd
  ```
- **Classic UI Fallback**:
  ```powershell
  .\.venv\Scripts\python.exe -B -m gui.app --classic
  ```
- **Isolated 3D Core Preview**:
  ```powershell
  .\.venv\Scripts\python.exe -B -m prototypes.cinematic_v4.preview
  # or Launch Cinematic Preview.cmd
  ```
- **Diagnostic / Smoke Testing**:
  ```powershell
  .\.venv\Scripts\python.exe -B smoke_test.py
  ```

---

## 4. Data Flow
1. **User Request Flow**:
   - User types command in `EVCommandInput.qml` or speaks via microphone.
   - Text is passed through `GuiBridge.submit_prompt()`.
   - `ActionPipeline` consults active `EVBrainProvider` (Gemini/Anthropic/OpenAI) to generate an action plan.
   - `PlanValidator` and `RiskAssessment` inspect each step.
   - If risk is `MUTATING` or higher, the pipeline transitions `visual_state` to `WAITING_FOR_APPROVAL` and blocks until the user confirms via `ApprovalOverlay.qml`.
   - On approval, `BackupManager` creates a pre-execution snapshot.
   - `PlanExecutor` executes the command via PowerShell, verifying output against expected state.
   - If verification fails, automatic rollback is proposed or executed.
2. **Audio Analysis & Reaction Flow**:
   - Audio originates either from local playback (`QMediaPlayer` via `QAudioBufferOutput`) or system loopback (`PyAudioWPatch` WASAPI capture).
   - PCM chunks (1024–4096 frames) are pushed to `AnalysisWorker` thread.
   - Worker computes 64-band FFT spectrum, RMS, peak, and spectral flux.
   - `OnsetDetector` checks against adaptive thresholds with 145 ms retrigger guard.
   - Monotonic `AnalysisFrame` snapshots are emitted to `MusicSession`.
   - `MusicSession.beat` drives the pulse animation in `CinematicStage.qml` (expanding core by up to 2.5% in Music mode, 0.625% in Assistant mode).
   - `VisualizerBoard.qml` paints live spectrum, flow traces, and segment stacks via HTML5-style QML `Canvas` elements.

---

## 5. UI Structure & Layers
The visual presentation is organized in z-ordered declarative layers:
- **Z = 0–10**: Background, gradient scrim, and 3D Viewport (`EVCoreFlagshipVisual.qml` / `NucleusScene.qml`).
- **Z = 20**: Music Workspace & Visualizer Board (`MusicWorkspace.qml`, `VisualizerBoard.qml`).
- **Z = 30**: Telemetry Rails, System Monitor graphs, Command Input bar.
- **Z = 50**: Navigation and drawer panels.
- **Z = 80**: Settings Overlay (`EVSettingsOverlay.qml`) for AI providers, audio, and visual styles.
- **Z = 100**: Approval Overlay (`EVApprovalOverlay.qml`) — strictly dominates all other layers for security consent.

---

## 6. Backend / Native Communication
- **PySide6 / QML Bridge**:
  - `GuiBridge` is exposed to QML as a context property or singleton.
  - State changes use Qt signals (`@Signal`), properties (`@Property`), and slots (`@Slot`).
  - Thread safety: Heavy operations (AI network calls, PowerShell commands, FFT analysis) run in worker threads or `QThreadPool` and emit Qt signals to update the UI thread.
- **Windows Native APIs**:
  - `CryptProtectData` / `CryptUnprotectData` via `ctypes.windll.crypt32` for DPAPI encryption.
  - `DwmSetWindowAttribute` via `ctypes.windll.dwmapi` for dark titlebar and window chrome integration (`gui/windows_chrome.py`).
  - WASAPI loopback capture via `PyAudioWPatch`.

---

## 7. Database & Storage System
- **Paths**: Controlled deterministically by `core/paths.py`:
  - Resource root: Repository directory (source mode) or `sys._MEIPASS` (frozen mode).
  - User data root: `%LOCALAPPDATA%\EV\` (Windows default) or overridden via `EV_USER_DATA_DIR`.
- **Stores**:
  - SQLite databases: `ev_history.sqlite3` (task history), `ev_memory.sqlite3` (conversational memory).
  - Settings: `QSettings` (`EV/CinematicStartup`, `EV/MusicFoundation`, `EV/CoreStyle`).
  - Provider Config: `%LOCALAPPDATA%\EV\config\ai_providers.json`.
  - Credentials: `%LOCALAPPDATA%\EV\config\ai_credentials.bin` (DPAPI encrypted).
  - Workspace Layout: `%LOCALAPPDATA%\EV\config\music_workspace.json` (atomic write with `.previous` backup).

---

## 8. External APIs & Integrations
- **Google Gemini API**: `generativelanguage.googleapis.com` via `google-genai` / `httpx`.
- **Anthropic Claude API**: `api.anthropic.com/v1/messages` via `httpx`.
- **OpenAI / OpenAI-Compatible**: `api.openai.com/v1`, OpenRouter, Groq, local Ollama (`localhost:11434/v1`).
- **Loopback Audio**: Windows Audio Session API (WASAPI) default render endpoint.

---

## 9. Security & Anti-Bypass Invariants
1. **Zero Execution Authority for LLMs**: AI models propose action plans; they never directly execute shell commands.
2. **Mandatory Approval for Mutations**: Any command modifying files, registry, or services requires explicit user approval.
3. **No Key Storage in Plaintext**: Stored credentials are encrypted with DPAPI; config files contain only metadata and masked keys (`••••••••••••`).
4. **Isolated Runtime Tests**: Test suites use temporary credential stores and mocked HTTP clients to prevent live service hits or credential leakage.
