# 10 — COMPLETE HANDOFF FOR GPT ASTRA

**Project**: E.V. (Enhanced Virtual Intelligence) Desktop Application  
**Target Recipient**: **GPT Astra** (Lead AI Architect & Systems Engineer)  
**Date & Timestamp**: September 22, 2026 — 14:30 IST  
**Repository Path**: `d:\EV`  
**Base Commit**: `a97c09c` (*feat(cinematic): fix core spherical frustum clipping and finalize independent fire particles*)  
**Python Runtime**: Windows 10 (Build 19045), Python 3.11+ in `d:\EV\.venv`  

---

## 1. Executive Summary & Handover Context

### Why Astra is Taking Over
The project owner has explicitly requested that **GPT Astra** take over full architectural and implementation ownership of E.V. effective immediately:
> *"OK ENOUGH NOW ITS NOT GOOD AT ALL GIVE A COMPLETE DETAILD HANDOFF FOR GPT ASTRA FROM NOW ON HE WILL HANDLE THIS PROJECT"*

### Root Cause of User Frustration: The Stark Arc Reactor Prototype
In the most recent sessions (Sep 21–22, 2026), an attempt was made to replace the flagship celestial particle core with an Iron Man Mark 85 Tri-Core Arc Reactor based on a reference image (`ChatGPT Image Sep 20, 2026, 10_04_31 AM.png`).
- **What was built**: A pure QML/Canvas component [`prototypes/cinematic_v4/qml/StarkArcReactorCore.qml`](file:///d:/EV/prototypes/cinematic_v4/qml/StarkArcReactorCore.qml) attempting to simulate 3D depth via multi-plane parallax ($0.50\times$ outer shards, $0.18\times$ stator, $-0.12\times$ unibeam) and 2D canvas drawing.
- **Why it failed**: The user rejected it as *"kind of too generic"* and *"not good at all"*. 2D QML Canvas and Rectangle primitives cannot achieve true photorealistic physically based rendering (PBR), specular metalness/roughness, machined micro-chamfers, volumetric depth, and cinematic anamorphic bloom. Simulating 3D hardware via 2D vector layers looked like a flat UI widget rather than movie-grade industrial CGI.
- **Astra's mandate**: Take full control of the visual direction, decide whether to resurrect/refine the celestial particle core or engineer a true 3D mesh/shader-based Arc Reactor, and continue driving the core engineering roadmap (Multi-Visualizer Studio, Voice Duplex, and Safety Engine).

---

## 2. Git Status & Current Working Tree

### Base Commit
- **`a97c09c`**: `feat(cinematic): fix core spherical frustum clipping and finalize independent fire particles`
- Prior commit: `04342f3` `Astra work: checkpoint cinematic E.V., music and development handoff`

### Modified Files (Tracked)
1. [`prototypes/cinematic_v4/geometry.py`](file:///d:/EV/prototypes/cinematic_v4/geometry.py): Adjusted frustum math and particle distribution bounds.
2. [`prototypes/cinematic_v4/integration.py`](file:///d:/EV/prototypes/cinematic_v4/integration.py): Audio loopback and telemetry bridge hooks.
3. [`prototypes/cinematic_v4/qml/CinematicStage.qml`](file:///d:/EV/prototypes/cinematic_v4/qml/CinematicStage.qml): Swapped visual cores during prototyping.
4. [`prototypes/cinematic_v4/qml/NucleusScene.qml`](file:///d:/EV/prototypes/cinematic_v4/qml/NucleusScene.qml): 3D Quick 3D celestial particle scene.
5. [`prototypes/cinematic_v4/run_preview.py`](file:///d:/EV/prototypes/cinematic_v4/run_preview.py): Standalone prototype launcher.

### Untracked Files from Recent Experiments (Review / Decide to Keep or Discard)
- [`prototypes/cinematic_v4/qml/StarkArcReactorCore.qml`](file:///d:/EV/prototypes/cinematic_v4/qml/StarkArcReactorCore.qml): The rejected QML Canvas Stark Arc Reactor.
- `prototypes/cinematic_v4/assets/stark_mk85/`: Generated asset crops and reference materials.
- [`prototypes/cinematic_v4/qml/CosmicDepthField.qml`](file:///d:/EV/prototypes/cinematic_v4/qml/CosmicDepthField.qml): Starfield and depth particle background.
- [`prototypes/cinematic_v4/qml/QuantumSingularityField.qml`](file:///d:/EV/prototypes/cinematic_v4/qml/QuantumSingularityField.qml): Singularity shader prototype.
- [`scratch/verify_stark_reactor.py`](file:///d:/EV/scratch/verify_stark_reactor.py): Headless QML render test for the Stark reactor.
- `scratch/stark_reactor_renders/`: PNG test captures (`stark_idle.png`, `stark_speaking.png`, `stark_music.png`, `stark_core_crop.png`).

---

## 3. High-Level Architecture of E.V.

E.V. is structured into two decoupled, safety-enforced layers:

```
+-------------------------------------------------------------------------+
|                              FRONTEND                                   |
|  PySide6 + QML (Qt Quick 3D + Qt Quick 2D)                              |
|  - Production Stage: gui/qml/EVWindow.qml -> EVFlagshipStage.qml       |
|  - Flagship Celestial Core: gui/qml/components/presets/                 |
|                            EVCoreFlagshipVisual.qml                     |
|  - Cinematic V4 Prototype: prototypes/cinematic_v4/qml/                |
|                            CinematicStage.qml & NucleusView.qml         |
|  - Multi-Visualizer Studio: gui/qml/components/visualizers/            |
|                            (VisualizerBoard, CeilingRain, FlowTrace)    |
|  - Settings & Overlays: EVSettingsOverlay.qml, EVApprovalOverlay.qml    |
+-------------------------------------------------------------------------+
                                   ▲
                                   │ Qt Signals & Slots / Properties
                                   ▼
+-------------------------------------------------------------------------+
|                          BRIDGE LAYER                                   |
|  gui/bridge.py                                                          |
|  - Dispatches audio FFT spectrum (64 bands), RMS, peak, onsets          |
|  - Dispatches system telemetry (CPU, RAM, GPU, thermals)                |
|  - Manages experience modes (STANDARD, AI, WORK, MUSIC, SYSTEM, SLEEP)  |
+-------------------------------------------------------------------------+
                                   ▲
                                   │ Thread-safe queues / Callbacks
                                   ▼
+-------------------------------------------------------------------------+
|                              BACKEND                                    |
|                                                                         |
|  1. EXECUTION & SAFETY ENGINE (Zero Unauthorized Mutating Actions):     |
|     - core/action_pipeline.py: Validates and executes PowerShell tasks  |
|     - core/plan_validator.py: AST & semantic safety checks              |
|     - core/risk.py: Risk scoring (Low, Medium, High, Critical)          |
|     - core/backup.py & recovery.py: Pre-flight snapshot & rollback      |
|                                                                         |
|  2. AUDIO & MUSIC ANALYSIS ENGINE:                                      |
|     - music/session.py: Audio engine coordinator                        |
|     - music/analysis.py: WASAPI loopback capture (PyAudioWPatch)        |
|     - 64-band FFT, 3-band energy (bass/mid/treble), spectral onsets     |
|     - music/workspace.py: Visualizer panel layout & state persistence   |
|                                                                         |
|  3. AI PROVIDER MANAGEMENT (DPAPI Protected):                           |
|     - providers/: Anthropic, Gemini, OpenAI, OpenRouter, Ollama         |
|     - core/provider_config.py: Windows DPAPI encryption for API keys   |
|                                                                         |
|  4. VOICE & WAKE-WORD (In-Progress):                                    |
|     - core/voice_wakeword_openwakeword.py: Local openWakeWord engine    |
|     - core/asr_faster_whisper.py: Local faster-whisper transcription    |
+-------------------------------------------------------------------------+
```

---

## 4. Technical Post-Mortem & Guidance for GPT Astra

### Issue: Why Did the Stark Arc Reactor Feel "Not Good"?
1. **Tooling Mismatch**: The implementation relied on QML `Canvas` (HTML5 Canvas 2D style context) and nested `Rectangle` items with gradients. It attempted to draw metallic bezels, copper wire turns, and chamfers programmatically in JavaScript.
2. **Missing Shading Model**: Real hardware surfaces require physically based rendering: microfacet specular distribution (GGX), Fresnel reflections, normal maps for machine grooves, and metallic-roughness maps. 2D QML items cannot react realistically to dynamic lights.
3. **Pseudo-3D Parallax Limitations**: Shifting 2D layers horizontally and vertically based on mouse tilt ($X, Y$) does not reproduce true 3D perspective distortion, depth clipping, or occlusion.

### Astra's Recommended Options:
- **Option A (Restore Proven Celestial Core — Recommended)**:  
  Revert the experimental `CinematicStage.qml` changes and return to the **Celestial 3D Particle Core** (`EVCoreFlagshipVisual.qml` / `NucleusScene.qml`). This core features 1,400+ GPU-instanced 3D particles, bounded FOV 38° frustum, atmospheric fire ribbons, and flawless 60 FPS performance, which was thoroughly validated and praised in earlier commits.
- **Option B (True 3D Stark Arc Reactor via Qt Quick 3D)**:  
  If the user insists on the Stark Arc Reactor, do **NOT** use 2D Canvas or QML shapes. Instead:
  1. Generate or import a real 3D mesh (`.mesh` or `.gltf` with separate nodes for unibeam, stator rings, and nanotech shards).
  2. Use Qt Quick 3D `Model` nodes with `PrincipledMaterial` (assigning proper `roughnessMap`, `normalMap`, and `metalnessMap`).
  3. Use real `DirectionalLight` and `PointLight` nodes that move with the camera gimbal.
  4. Implement a custom post-processing bloom shader for the anamorphic unibeam flare.

---

## 5. Environment & Execution Cheatsheet

### Python Environment
Always use the virtual environment located at `d:\EV\.venv`:
- Interpreter: `.\.venv\Scripts\python.exe`
- Pip: `.\.venv\Scripts\pip.exe`

### Running the Application
```powershell
# Run canonical desktop app
.\.venv\Scripts\python.exe -m gui.app

# Run cinematic v4 prototype
.\.venv\Scripts\python.exe -B prototypes/cinematic_v4/run_preview.py
```

### Running Test Suites (CRITICAL WINDOWS RULE)
> **MANDATORY**: Always pass `--basetemp` to pytest on Windows. Without this flag, pytest attempts to create a symlink (`pytest-current`) in `%TEMP%` which fails with `WinError 5: Access is denied`.

```powershell
# 1. Music, Audio & Startup Sound Tests
$env:EV_STARTUP_AUDIO='false'
.\.venv\Scripts\python.exe -B -m pytest tests/test_music_foundation.py tests/test_music_beats.py tests/test_music_reaction_modes.py tests/test_cinematic_startup_audio.py -q -p no:cacheprovider --basetemp=C:\Users\$env:USERNAME\AppData\Local\Temp\ev_pytest

# 2. Music Workspace & Visualizer Layout Tests
.\.venv\Scripts\python.exe -B -m pytest tests/test_music_workspace.py tests/test_music_analysis_snapshots.py -q -p no:cacheprovider --basetemp=C:\Users\$env:USERNAME\AppData\Local\Temp\ev_pytest

# 3. GUI Settings, Modes & Performance Tests
.\.venv\Scripts\python.exe -B -m pytest tests/test_gui_settings.py tests/test_gui_performance.py tests/test_gui_modes.py -q -p no:cacheprovider --basetemp=C:\Users\$env:USERNAME\AppData\Local\Temp\ev_pytest

# 4. Core Pipeline & Security Tests
.\.venv\Scripts\python.exe -B -m pytest tests/test_action_pipeline.py tests/test_provider_config.py -q -p no:cacheprovider --basetemp=C:\Users\$env:USERNAME\AppData\Local\Temp\ev_pytest
```

---

## 6. Priority Roadmap for Astra

### Milestone 1: Visual Core Alignment
- [ ] Consult with the user or inspect their preference: Revert to the cinematic Celestial Particle Core (`EVCoreFlagshipVisual.qml` / `NucleusScene.qml`) or plan a true 3D Qt Quick 3D mesh pipeline for the Arc Reactor.
- [ ] Ensure `prototypes/cinematic_v4/qml/CinematicStage.qml` cleanly presents the chosen visual core without console errors.

### Milestone 2: Multi-Visualizer Studio Stabilization
- [ ] Connect `VisualizerBoard.qml` and its panels (`CeilingRain.qml`, `FlowTrace.qml`, `SegmentStack.qml`) to `music/workspace.py` and `music/session.py`.
- [ ] Implement responsive layout persistence (grid docking and resizing).
- [ ] Guarantee silence and non-finite (NaN/inf) protection across all visualizer canvas rendering.

### Milestone 3: Voice Duplex & Continuous Interaction
- [ ] Integrate `faster-whisper` and `openWakeWord` with live TTS PCM output.
- [ ] Implement audio ducking (lowering music volume during user speech or E.V. voice response).
- [ ] Prevent microphone feedback / self-triggering during TTS playback.

### Milestone 4: Windows Packaging & Release Prep
- [ ] Create a standalone PyInstaller / portable build script.
- [ ] Split `requirements.txt` into `requirements-core.txt` and `requirements-voice.txt`.

---

## 7. Non-Negotiable Invariants & Safety Boundaries

1. **Security & DPAPI**: Never store API keys in plaintext or commit them to Git. All keys must use Windows DPAPI via `core/provider_config.py`.
2. **Action Pipeline Approval**: No LLM, voice command, or autonomous agent may execute mutating PowerShell commands without passing through `PlanValidator` and displaying the `EVApprovalOverlay.qml` modal to the user.
3. **Audio Privacy**: Audio captured via WASAPI loopback is processed strictly in-memory for FFT analysis and discarded immediately. No raw microphone or loopback audio is persisted to disk.
4. **Sequential Testing**: Never run audio or Qt Quick tests concurrently.

---

*Handoff compiled and verified for GPT Astra.*
