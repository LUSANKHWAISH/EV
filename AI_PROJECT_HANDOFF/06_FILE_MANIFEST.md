# 06 — FILE MANIFEST: E.V. Desktop Application

## 1. Repository Structure & Key Directory Roles

```text
d:\EV\
├── core\                     # Core troubleshooting engine, execution pipeline, safety & providers
│   ├── action_pipeline.py    # Canonical planning and execution pipeline
│   ├── agent.py              # Tool dispatch and agent execution logic
│   ├── backup.py             # Pre-mutation snapshots and file rollback
│   ├── brain_provider.py     # Base interface for LLM providers
│   ├── paths.py              # Deterministic path resolution (source & frozen)
│   ├── plan_executor.py      # PowerShell command execution
│   ├── plan_validator.py     # Plan validation & invariant checks
│   ├── provider_config.py    # DPAPI key security & provider configurations
│   ├── recovery.py           # Rollback mechanics & failure recovery
│   ├── risk.py               # Risk classification (READ_ONLY, MUTATING, DESTRUCTIVE)
│   ├── system_monitor.py     # Hardware telemetry (CPU, RAM, GPU, network)
│   └── voice_manager.py      # Wake-word & speech recognition coordinator
├── gui\                      # Presentation host & PySide6/QML bridge
│   ├── app.py                # Main application bootstrap and CLI argument parsing
│   ├── bridge.py             # GuiBridge QObject exposing signals, slots, and properties
│   ├── visual_state.py       # Visual state machine (IDLE, LISTENING, THINKING, etc.)
│   ├── windows_chrome.py     # DWM dark titlebar & native window integration
│   └── qml\                  # Qt Quick components and theme
│       ├── components\       # Reusable UI controls (TopBar, CommandInput, Overlays)
│       └── theme\            # Theme tokens, palettes, and typography
├── music\                    # Music playback & audio loopback analysis
│   ├── analysis.py           # FFT spectral analysis & AnalysisWorker thread
│   ├── loopback.py           # WASAPI loopback audio capture (PyAudioWPatch)
│   ├── onsets.py             # Spectral onset and transient beat detector
│   ├── session.py            # MusicSession QObject managing playback & analysis
│   └── workspace.py          # Multi-visualizer layout store & validation
├── providers\                # Concrete AI provider implementations
│   ├── anthropic_provider.py # Claude API integration
│   ├── gemini_provider.py    # Google Gemini API integration
│   └── openai_compatible...  # OpenAI, Azure, OpenRouter, Groq, Ollama
├── prototypes\cinematic_v4\  # Production cinematic stage, 3D nucleus & visualizers
│   ├── integration.py        # Connected cinematic presentation adapter
│   ├── startup_audio.py      # Procedural startup sound generator
│   └── qml\                  # Cinematic stage QML files
│       ├── CinematicStage.qml
│       ├── ConnectedWindow.qml
│       ├── NucleusScene.qml
│       ├── VisualizerBoard.qml
│       ├── CeilingRain.qml
│       ├── FlowTrace.qml
│       └── SegmentStack.qml
├── tests\                    # Pytest automated test suites
├── tools\                    # Diagnostic and evaluation utilities
├── config\                   # Configuration management (`settings.py`)
├── AI_PROJECT_HANDOFF\       # Complete handoff documentation suite & logs
├── .env.example              # Safe configuration template (placeholders only)
├── requirements.txt          # Python dependencies
├── pytest.ini                # Pytest configuration
├── CMakeLists.txt            # CMake specification for QML modules / C++ host
└── Launch EV.cmd             # Windows launcher script
```

---

## 2. Files Included in the Source Package (`EV_APP_SOURCE_SAFE.zip`)
- **All application source code**: `core/`, `gui/`, `music/`, `providers/`, `config/`.
- **Active prototypes & components**: `prototypes/cinematic_v4/` (including all QML, shaders, and visualizer components).
- **All test suites**: `tests/` (86 test files covering all subsystems).
- **Configuration templates & build manifests**: `.env.example`, `requirements.txt`, `pytest.ini`, `CMakeLists.txt`.
- **Launcher scripts & documentation**: `Launch EV.cmd`, `Launch Cinematic Preview.cmd`, `Launch Classic EV.cmd`, `README.md`, `INTEGRATION_GUIDE.md`, `ASTRA_PLAN.md`, `ASTRA_HANDOFF.md`.
- **Active uncommitted work**:
  - Modified: `gui/qml/components/presets/EVCoreFlagshipVisual.qml`, `music/analysis.py`, `music/session.py`, `prototypes/cinematic_v4/qml/CinematicStage.qml`, `prototypes/cinematic_v4/qml/MusicWorkspace.qml`.
  - Untracked: `music/workspace.py`, `prototypes/cinematic_v4/qml/VisualizerBoard.qml`, `CeilingRain.qml`, `FlowTrace.qml`, `SegmentStack.qml`, `tests/test_music_workspace.py`, `tests/test_music_analysis_snapshots.py`.
- **Complete Handoff Documentation**: `AI_PROJECT_HANDOFF/` and its `logs/`.

---

## 3. Files & Directories Intentionally Excluded
The following categories are strictly excluded from all handoff packages:

### A. Sensitive Files & Real Data
- Real runtime SQLite databases: `data/ev_history.sqlite3` (~3.3 MB), `data/ev_memory.sqlite3` (~172 KB).
- DPAPI credential files: `ai_credentials.bin`, `creds.bin` (in test outputs and evidence folders).
- Local user app data in `%LOCALAPPDATA%\EV\`.

### B. Virtual Environments & Git Metadata
- Python virtual environments: `d:\EV\.venv\`, `d:\EV\venv\`.
- Git repository metadata: `d:\EV\.git\`.

### C. Large AI Model Weights & Binaries
- `models/asr/` (~150MB+ faster-whisper model weights).
- Pre-existing archive: `EV_Core_Integration_Bundle.zip` (24.7 MB).
- Large media files: `temp_video.mp4` (6.9 MB).

### D. Historical Backup Trees & Scratch Dumps
- `backup_018K3_20260909_095713/`
- `backup_018K3_20260909_111000/`
- `backup_018K3_SETTINGS_20260909_114530/`
- `backup_nexus_task_20260909/`
- `backups/`
- `astrabackup/`
- `gui_backup_018K3_ASTRA_20260909_0043/`
- `prototypes/ev_core_webgl_BACKUP_*/`
- `handoff/` (historical scratch folders)
- Scratch diagnostic scripts: `diag*.py`, `check_*.py`, `smoke_test*.py`, `ui_test*.py`, `*.png` screenshots.

### E. Caches & Build Outputs
- `__pycache__/` and all nested `__pycache__/` directories.
- `.pytest_cache/`.
- `.astra-local/` test artifacts and evidence dumps.

---

## 4. Files That Must Be Provided or Recreated on Destination
When deploying onto a new machine:
1. **Virtual Environment**: Recreate via `py -3.12 -m venv .venv` and install `requirements.txt`.
2. **Configuration**: Copy `.env.example` to `.env`.
3. **AI Credentials**: Enter provider API keys in the Settings Overlay (encrypted automatically into Windows DPAPI).
4. **Voice Models (Optional)**: If using voice wake-word or ASR, models will automatically be cached to `models/` on first use by `faster-whisper` and `openwakeword`.
