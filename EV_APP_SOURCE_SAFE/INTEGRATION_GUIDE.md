# E.V. — HYBRID AI ASSISTANT CORE INTEGRATION GUIDE

## 1. Executive Technical Summary

**E.V. (Enhanced Virtual Intelligence)** is a Windows-native desktop AI assistant built with:
- **Frontend**: **PySide6 6.11.2 (Qt 6.11 Quick/QML)** with custom hardware-accelerated Canvas/Quick visualizers, dynamic DWM native Windows chrome, and fluid HUD components.
- **Backend Architecture**: **Python 3.12 (64-bit AMD64)** orchestrating a 10-stage fail-closed intelligent action pipeline, dual-path query resolution (Deterministic Regex Grammar vs Multi-Provider LLM Brain), persistent SQLite memory, risk assessment engine, and multi-turn context management.
- **Voice Subsystem**: OpenWakeWord ONNX engine (`hey_ev.onnx`), local faster-whisper speech-to-text, and presentation-layer TTS feedback.
- **Security Invariant**: Zero God Mode, Zero bypass. Read-only operations execute with verification; mutating system operations (file creation/deletion, process kills, system config) require explicit human approval via HUD/Voice gates with CompoundTransaction LIFO rollback guarantees.

---

## 2. Technology Stack & Environment

| Component | Technology | Version | Purpose |
| :--- | :--- | :--- | :--- |
| **Python** | CPython (AMD64) | `3.12.10` | Core runtime & backend execution |
| **GUI Framework** | PySide6 (Qt Quick / QML) | `6.11.2` | High-DPI hardware-accelerated UI |
| **Qt Engine** | Qt Quick / QML SceneGraph | `6.11.2` | Dynamic canvas rendering & HUD |
| **Style** | QQuickStyle `Basic` | `6.11.2` | Raw custom GPU rendering (no native widget overhead) |
| **Wake-Word** | openwakeword (ONNX Runtime) | `0.6.0` | Offline, zero-latency "Hey E.V." detection |
| **Speech-to-Text** | faster-whisper | `1.2.1` | Local quantized Whisper speech transcription |
| **Audio I/O** | sounddevice / SoundCard | `0.5.6` | Multi-channel microphone capture & FFT analysis |
| **Security/Crypto** | Windows DPAPI (`crypt32.dll`) | Win32 native | Encrypted credential storage at rest |
| **Window Host** | DWM API (`dwmapi.dll`) | Win32 native | Native Windows 11 snap layouts, glass & drop shadows |

---

## 3. Project Directory Structure

```
EV/
├── core/                                # Core intelligence, orchestration, and action pipeline
│   ├── action_pipeline.py               # Canonical 10-stage end-to-end execution coordinator
│   ├── agent.py                         # EVAgent: Ground-truth tool implementations (PowerShell, files, procs)
│   ├── brain_context.py                 # Assembles bounded context prompts for LLM providers
│   ├── brain_converter.py               # Converts LLM action proposals to validated AgentTasks
│   ├── brain_models.py                  # Pydantic data schemas: decisions, proposals, context
│   ├── brain_provider.py                # Abstract base class EVBrainProvider
│   ├── brain_provider_manager.py        # Failover and provider rotation manager
│   ├── brain_router.py                  # Dual-path router: FAST_PATH grammar vs BRAIN_PATH LLM
│   ├── brain_validator.py               # Proposal validation gate (whitelists allowed actions)
│   ├── cancellation.py                  # CancellationToken & cooperative cancellation mechanics
│   ├── conversation.py                  # EVConversationContextStore (multi-turn clarification buffer)
│   ├── events.py                        # Central thread-safe EVEventBus (state machine transitions)
│   ├── experience.py                    # Experience manager: volume, microphone sensitivity, sound effects
│   ├── history.py                       # EVTaskHistoryStore (persistent SQLite execution audit trail)
│   ├── memory.py                        # EVConversationMemoryStore (dialogue history, profile facts)
│   ├── models.py                        # Core system domain enums & dataclasses (EVState, RiskLevel)
│   ├── orchestrator.py                  # EVOrchestrator central system coordinator
│   ├── paths.py                         # Deterministic path resolution for bundled vs user appdata
│   ├── plan.py                          # Plan, PlanStep, StepStatus canonical structures
│   ├── plan_executor.py                 # CompoundTransaction execution with automatic LIFO rollback
│   ├── plan_validator.py                # Fail-closed plan security validator
│   ├── proactive_awareness.py           # Background system observer (alerts on high RAM, CPU, disk)
│   ├── provider_config.py               # DPAPI-encrypted multi-provider settings storage
│   ├── recovery.py                      # Diagnostic engine and automatic recovery planner
│   ├── resolver.py                      # Fast-path deterministic regex command resolver
│   ├── risk.py                          # EVRiskEngine: Authoritative risk classification & approval rules
│   ├── risk_intelligence.py             # Action category classifier
│   ├── system_monitor.py                # psutil-backed host health telemetry engine
│   ├── transaction.py                   # Atomic reversible file & state transaction rollback engine
│   ├── tts.py                           # Presentation-layer Text-To-Speech engine
│   ├── verifier.py                      # Post-execution ground-truth verifier (checks real disk/proc state)
│   ├── voice_capture.py                 # Microphone stream capture thread with silence detection
│   └── voice_manager.py                 # Complete 2-stage wake-word + ASR pipeline
├── gui/                                 # PySide6 / QML Presentation Layer
│   ├── app.py                           # Main application entry point (`python -m gui.app`)
│   ├── bridge.py                        # GuiBridge: Thread-safe QObject connecting Python to QML
│   ├── windows_chrome.py                # Native Win32/DWM frameless window styling and snap layout
│   └── qml/                             # Qt Quick QML Visual Hierarchy
│       ├── components/                  # Reusable UI component modules
│       │   ├── EVCommandInput.qml       # HUD bottom command entry & micro-action triggers
│       │   ├── EVIntelligenceCore.qml   # Central Core Stage Container & preset Loader
│       │   ├── EVResultSurface.qml      # HUD execution readout & conversational response display
│       │   ├── EVSettingsOverlay.qml    # Modal settings drawer (Providers, Audio, System, Model)
│       │   ├── EVSystemAlertBanner.qml  # Top notification & alert banner
│       │   ├── EVTelemetryRail.qml      # Left/Right real-time system metrics meters
│       │   ├── EVTopBar.qml             # Window title, state badge, window controls
│       │   ├── EVWindow.qml             # Root window with frameless drag & drop handling
│       │   └── presets/                 # Intelligence Core visual presets
│       │       ├── EVCoreNexusSphere.qml # Authoritative ORIGINAL Nexus Sphere (9 orbital rings, hex grid)
│       │       ├── EVCoreFlagshipVisual.qml # ASTRA Flagship visual (3D volumetric core)
│       │       └── EVCoreOriginalVisual.qml # Procedural backup visualizer
│       └── theme/
│           └── Theme.qml                # Unified design system tokens, colors, fonts, glow effects
├── models/
│   └── wakeword/                        # Bundled offline AI models
│       ├── hey_ev.onnx                  # Production custom-trained OpenWakeWord model (~850 KB)
│       └── hey_ev_v1_baseline.onnx      # Baseline model for verification
├── providers/                           # External AI Intelligence Connectors
│   ├── __init__.py
│   ├── gemini_provider.py               # Google Gemini API connector (REST / SSE)
│   ├── openai_compatible_provider.py    # OpenRouter & Azure OpenAI connectors
│   └── anthropic_provider.py            # Anthropic Claude connector
├── tests/                               # Comprehensive Automated Test Suites (100% offline)
│   ├── test_action_pipeline.py          # 10-stage execution pipeline test matrix
│   ├── test_brain_orchestrator.py       # Brain routing and fallback tests
│   ├── test_brain_router.py             # Grammar vs LLM routing tests
│   ├── test_gui_app.py                  # GUI launcher and result formatting tests
│   ├── test_gui_hud_result.py           # HUD result presentation tests
│   ├── test_gui_modes.py                # Experience modes and core presets tests
│   ├── test_gui_settings.py             # Settings overlay & provider config tests
│   └── test_gui_telemetry.py            # System metrics telemetry tests
├── tools/                               # Diagnostic & verification utilities
│   ├── create_integration_bundle.py     # Clean ZIP packager
│   └── smoke_test_full_voice_loop.py    # Voice capture, wakeword, and ASR diagnostics
├── CMakeLists.txt                       # Reference CMake build file for native Qt C++ integration
├── requirements.txt                     # Production Python dependencies
├── pytest.ini                           # Test runner configuration
├── .env.example                         # Environment template (NO SECRETS)
└── README.md                            # High-level overview
```

---

## 4. QML-to-Python Communication Contract

Communication between the PySide6 UI and the Python engine is strictly mediated through **`GuiBridge`** (`gui/bridge.py`), registered as a context property:
```python
engine.rootContext().setContextProperty("guiBridge", bridge)
```

### Key Properties (`@Property`)
| QML Property | Type | Direction | Description |
| :--- | :--- | :--- | :--- |
| `state` | `string` | Python -> QML | Authoritative EVState (`IDLE`, `LISTENING`, `PROCESSING`, `EXECUTING`, `AWAITING_APPROVAL`, `FAILED`) |
| `taskResult` | `string` | Python -> QML | Human-readable outcome text or AI conversational response |
| `taskResultStatus` | `string` | Python -> QML | Authoritative result status (`SUCCESS`, `FAILED`, `CANCELLED`, `ROLLED_BACK`) |
| `taskResultSuccess` | `bool` | Python -> QML | Boolean success flag driving HUD glow & color tokens |
| `coreMode` | `string` | QML <-> Python | Active visual preset (`ORIGINAL` for Nexus Sphere, `ASTRA` for Flagship) |
| `activeProviderName`| `string` | Python -> QML | Name of active AI provider (e.g. `OpenRouter`, `Gemini`) |
| `speechAmplitude` | `real` | Python -> QML | Live microphone/speech energy (0.0 - 1.0) driving Core audio reactivity |
| `cpuUsage` / `ramUsage` | `real` | Python -> QML | Real-time system telemetry percentages |

### Key Slots (`@Slot`)
| QML Slot Call | Arguments | Description |
| :--- | :--- | :--- |
| `guiBridge.submitTask(cmd)` | `QString command` | Asynchronously dispatches command to `EVActionPipeline` worker thread |
| `guiBridge.resolveApproval(planId, ok)` | `QString, bool` | Resolves human authorization for mutating system actions |
| `guiBridge.setCoreMode(mode)` | `QString mode` | Switches the visual preset between `ORIGINAL` and `ASTRA` |
| `guiBridge.cancelActiveTask()` | None | Signals cooperative `CancellationToken` to halt execution |
| `guiBridge.clearTaskResult()` | None | Resets HUD result surface back to clean idle state |

---

## 5. How to Add a New AI Core (Extension Points)

### Adding a New Intelligence Provider (Backend)
1. Subclass `EVBrainProvider` from `core/brain_provider.py`:
   ```python
   from core.brain_provider import EVBrainProvider
   from core.brain_models import BrainDecision, BrainDecisionType, BrainActionProposal

   class LocalSLMProvider(EVBrainProvider):
       def __init__(self, endpoint: str = "http://localhost:11434"):
           super().__init__(provider_name="local_slm", model_name="llama3.2")
           self.endpoint = endpoint

       def generate_decision(self, prompt: str, context: BrainContext, timeout_seconds: float = 15.0) -> BrainDecision:
           # Query local model via REST / ONNX GenAI
           ...
           return BrainDecision(
               decision_type=BrainDecisionType.EXPLANATION_ONLY, # or EXECUTE_ACTION
               user_message="Response text",
               proposed_actions=[...] # if executing system tools
           )
   ```
2. Register it with `EVBrainProviderManager` in `gui/app.py` or `core/provider_config.py`.

### Adding a New Visual Core Preset (Frontend)
1. Create your visual component in `gui/qml/components/presets/EVCoreMyVisual.qml`.
2. Ensure it binds to `guiBridge.speechAmplitude` and `guiBridge.state` for reactive motion.
3. In `gui/qml/components/EVIntelligenceCore.qml`, add your preset to the `Loader` `sourceComponent` mapping:
   ```qml
   source: {
       if (guiBridge.coreMode === "ORIGINAL") return "presets/EVCoreNexusSphere.qml";
       if (guiBridge.coreMode === "ASTRA") return "presets/EVCoreFlagshipVisual.qml";
       if (guiBridge.coreMode === "CUSTOM") return "presets/EVCoreMyVisual.qml";
       return "presets/EVCoreNexusSphere.qml";
   }
   ```

---

## 6. Build and Run Instructions

### Prerequisites
- Windows 10/11 (64-bit AMD64)
- Python 3.12.x installed with PATH configured

### Installation
```powershell
# 1. Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt
```

### Launching the Application
```powershell
# Run the PySide6 QML GUI application
python -m gui.app
```

### Running the Test Suite (Offline & Deterministic)
```powershell
pytest tests/ -q
```
