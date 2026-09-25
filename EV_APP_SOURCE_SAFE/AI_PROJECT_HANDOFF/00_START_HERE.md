# 00 — START HERE: E.V. Desktop Application Handoff

## Project Name & Purpose
- **Project Name**: E.V. (Enhanced Virtual Intelligence)
- **Primary Purpose**: A local, autonomous Windows troubleshooting engine and desktop assistant. E.V. provides conversational assistance, automated diagnostic tools, PowerShell execution with safety boundaries, verification and rollback mechanics, combined with a 3D celestial nucleus presentation (Qt Quick 3D) and real-time WASAPI audio analysis/beat reactivity.
- **Current Development Status**: Active Development / Multi-Visualizer Foundation. The cinematic golden nucleus, Music playback/capture foundation, multi-provider AI configuration, and startup signature are accepted and fully operational. Current uncommitted work implements the multi-visualizer studio (VisualizerBoard, CeilingRain, FlowTrace, SegmentStack) and analysis snapshot stream.

---

## Desktop / Framework Stack
- **Desktop Host**: PySide6 (Qt 6.11.2) running on Python 3.12.10 on Windows 10/11 (64-bit).
- **Presentation / Frontend**: Qt Quick 2 + Qt Quick 3D + QML (GPU-instanced particle rendering, custom shaders, Canvas visualizers).
- **Backend Runtime**: Python 3.12 (`.venv`), asynchronous worker threads, NumPy 2.5.2 FFT analysis, PyAudioWPatch 0.2.12.8 (WASAPI loopback capture).
- **AI Providers**: Anthropic Claude, Google Gemini, OpenAI, Azure OpenAI, OpenRouter, Groq, Ollama (local), with Windows DPAPI encryption (`CryptProtectData`) for local key storage.
- **Voice Subsystems**: openWakeWord (ONNX runtime), faster-whisper (CTranslate2 ASR), edge-tts / pyttsx3.

---

## Exact Recommended Next Step
1. **Unpack `EV_APP_SOURCE_SAFE.zip`** into a clean directory on Windows.
2. Read [`09_AGENT_CONTINUATION_PROMPT.md`](09_AGENT_CONTINUATION_PROMPT.md) and [`05_NEXT_DEVELOPMENT_PLAN.md`](05_NEXT_DEVELOPMENT_PLAN.md).
3. Review and integrate the active uncommitted multi-visualizer studio work (`music/workspace.py`, `prototypes/cinematic_v4/qml/VisualizerBoard.qml`, and visualizer panels) into the canonical build, verifying with `pytest tests/test_music_workspace.py tests/test_music_analysis_snapshots.py`.

---

## Top Five Priorities
1. **Stabilize Multi-Visualizer Studio**: Finalize panel coordinate persistence, docking, and rendering performance for the trio visualizers (`CeilingRain`, `FlowTrace`, `SegmentStack`).
2. **Audio Pipeline Hardening**: Enforce strict bounded queue discards on seek/source changes to prevent audio-visual desync during high CPU load.
3. **Playback Equalizer & DSP**: Implement user-configurable parametric EQ / biquad filters on the owned playback stream (differentiating player DSP from external loopback analysis).
4. **Clean Dependency Locking**: Create a pinned, reproducible `requirements.lock` or `pyproject.toml` (separating core desktop dependencies from heavy voice/CUDA models).
5. **Standalone Packaging & Distribution**: Configure PyInstaller / cx_Freeze bundling specification with resource path abstraction (`core/paths.py`) for one-click deployment.

---

## Known Blockers
- **Windows Symlink Privileges in Default Pytest Tempdir**: Pytest's default `tmpdir` fixture attempts to create symlinks in `%TEMP%\pytest-of-<user>\pytest-current`, which fails with `WinError 5: Access is denied` if Developer Mode or Administrator privileges are disabled. **Resolution**: Always supply `--basetemp=C:\Users\<user>\AppData\Local\Temp\ev_pytest` or use a local directory.
- **Audio Capture Dependency on Windows WASAPI**: PyAudioWPatch is strictly Windows-only (`sys_platform == "win32"`). Loopback capture requires an active audio output endpoint.
- **Heavy Voice Model Weights Excluded**: `faster-whisper` and `openwakeword` ONNX models are excluded from safe source archives due to file size (>150 MB). They must be downloaded or cached via their respective loaders.

---

## Archive Upload Order
When handing off or resuming this project, upload and inspect in this exact sequence:

1. **`EV_APP_HANDOFF_DOCS.zip`** (Immediate review): Contains the complete `AI_PROJECT_HANDOFF/` documentation suite, test logs, manifests, and continuation prompt.
2. **`EV_APP_SOURCE_SAFE.zip`** (Codebase): Sanitized complete project source code, tests, configuration templates, and active uncommitted work (zero secrets, zero databases, zero venvs).
3. **Screenshots / Logs / Manual Assets** (Optional supplementary artifacts): Diagnostic screenshots or reference captures if needed.
