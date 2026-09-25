# 09 — AGENT CONTINUATION PROMPT

You are continuing development on **E.V. (Enhanced Virtual Intelligence)**, an autonomous Windows troubleshooting engine and desktop assistant featuring a GPU-instanced 3D celestial particle core (Qt Quick 3D), real-time WASAPI audio analysis and beat reactivity (PyAudioWPatch), and multi-provider AI execution (Anthropic, Gemini, OpenAI) with Windows DPAPI credential protection.

---

## 1. Context & Essential Reading
Before writing any code or modifying existing files, you MUST review the handoff documentation located in `AI_PROJECT_HANDOFF/`:
- **`00_START_HERE.md`**: Project overview, status, and recommended workflow.
- **`01_PROJECT_STATUS.md`**: Feature completion status, technical debt, and boundaries.
- **`02_ARCHITECTURE.md`**: Dual-layer architecture, QML-Python bridge, and data flow.
- **`03_SETUP_AND_COMMANDS.md`**: Exact environment and test execution commands.
- **`05_NEXT_DEVELOPMENT_PLAN.md`**: Prioritized roadmap and milestone tasks.
- **`07_GIT_STATUS.md`**: Active uncommitted work and modified files.
- **`10_GPT_ASTRA_COMPLETE_HANDOFF.md`**: **CRITICAL** — Full handover brief for GPT Astra detailing latest work, root causes of user feedback, and immediate decision points.

---

## 2. Your First Assigned Task: Milestone 1 (Multi-Visualizer Studio)
Your primary objective is to complete **Milestone 1: Multi-Visualizer Studio Stabilization**:
1. **Wire Visualizer Trio**: Connect `VisualizerBoard.qml` (and its children `CeilingRain.qml`, `FlowTrace.qml`, `SegmentStack.qml`) with `music/session.py` and `music/workspace.py`.
2. **Layout Persistence**: Ensure that layout configurations loaded via `WorkspaceStore` in `music/workspace.py` correctly render panels with appropriate widths, heights, and margins in QML.
3. **Canvas Bounds & Non-Finite Protection**: Verify that all three visualizers gracefully handle silence, non-finite audio values (NaN/inf), and window resizing without generating QML/Canvas errors or performance drops.

---

## 3. Strict Operating Rules & Constraints
- **Preserve Existing Behavior**: Do NOT refactor, rename, or redesign the accepted 3D nucleus (`EVCoreFlagshipVisual.qml` / `NucleusScene.qml`), the action pipeline, or the provider settings overlay.
- **Zero Secret Exposure**: NEVER hardcode, log, or commit API keys, tokens, or credentials. All provider keys MUST be handled via `DPAPICredentialStore` and masked as `••••••••••••` in the UI.
- **Windows Pytest Rule**: Always pass `--basetemp=C:\Users\$env:USERNAME\AppData\Local\Temp\ev_pytest` when running pytest on Windows to avoid `WinError 5: Access is denied` on default symlinks.
- **Sequential Audio Tests**: Never run audio or Qt Quick tests concurrently. Always run them sequentially.
- **No Unauthorized Deployment**: Do NOT push commits, reset Git history, publish packages, deploy to production, or delete database files.

---

## 4. Acceptance Criteria & Verification
To consider your task complete:
1. All existing 164 tests in the test suite must continue to PASS:
   ```powershell
   $env:EV_STARTUP_AUDIO='false'
   .\.venv\Scripts\python.exe -B -m pytest tests/test_music_foundation.py tests/test_music_beats.py tests/test_music_reaction_modes.py tests/test_cinematic_startup_audio.py -q -p no:cacheprovider --basetemp=C:\Users\$env:USERNAME\AppData\Local\Temp\ev_pytest
   .\.venv\Scripts\python.exe -B -m pytest tests/test_music_workspace.py tests/test_music_analysis_snapshots.py -q -p no:cacheprovider --basetemp=C:\Users\$env:USERNAME\AppData\Local\Temp\ev_pytest
   .\.venv\Scripts\python.exe -B -m pytest tests/test_gui_settings.py tests/test_gui_performance.py tests/test_gui_modes.py -q -p no:cacheprovider --basetemp=C:\Users\$env:USERNAME\AppData\Local\Temp\ev_pytest
   ```
2. The application boots cleanly via `python -m gui.app` and displays the multi-visualizer studio in the Music tab.
3. `python -m compileall -q core gui music providers config tests` reports zero syntax or compilation errors.
