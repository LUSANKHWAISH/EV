# Baseline Stabilization Checkpoint — 25 September 2026

## 1. Scope & Execution Context
- **Workspace:** `D:\EV`
- **Starting Committed HEAD:** `a97c09c897755dbb9e1c238c53aaa3a8ce452363` (`feat(cinematic): fix core spherical frustum clipping and finalize independent fire particles`)
- **Active Branch:** `chore/stabilize-baseline`
- **Objective:** Stabilize the baseline, resolve reported regressions, make installation reproducible, and verify all core subsystems without discarding in-flight theme/test work.

## 2. Dependency Architecture & Installation Reproducibility
- **Base Application (`requirements.txt`):**
  - Added direct runtime dependencies: `httpx>=0.27` (required by AI providers and provider config store), `psutil>=5.9` (required by system monitoring and HUD telemetry).
  - Cleaned out `openwakeword` from the base install so that core application and music start reliably in headless/standard environments without C++ model toolchains.
- **Dedicated Test Requirements (`requirements-test.txt`):**
  - References `requirements.txt` + `pytest>=8.0`.
- **Optional Voice Requirements (`requirements-voice.txt`):**
  - References `requirements.txt` + `sounddevice>=0.5.0`, `faster-whisper>=1.0.0`, `onnxruntime>=1.16.0`, `openwakeword>=0.6.0`.
- **Validation in Fresh Python 3.12 Environment (`test_runtime/fresh_venv`):**
  - Python version: 3.12.10
  - `pip check` result: **No broken requirements found.**
  - All core, GUI, and music modules import cleanly with zero errors.
  - Installed package versions:
    - `PySide6`: 6.11.2 (with Addons & Essentials)
    - `numpy`: 2.5.3
    - `PyAudioWPatch`: 0.2.12.8
    - `pydantic`: 2.13.5
    - `httpx`: 0.28.1
    - `psutil`: 7.2.2
    - `python-dotenv`: 1.2.3

## 3. Investigation & Resolution of Reported Failures

### A. Geometry Hash Regression (`tests/test_cinematic_orbital_aura.py`)
- **Diagnosis:** Uncommitted additions for cosmic depth particles (`make_cosmic_depth_instance_data` and `CosmicDepthInstances`) were directly appended to `prototypes/cinematic_v4/geometry.py`. This changed the file's SHA-256 hash, causing `test_focused_round_core_contract` to fail. Additionally, git checkout on Windows without line-ending enforcement converted LF to CRLF.
- **Resolution:**
  1. Extracted `CosmicDepthInstances` and its generator into a dedicated module: `prototypes/cinematic_v4/cosmic_geometry.py`.
  2. Restored `prototypes/cinematic_v4/geometry.py` to its exact committed state at `a97c09c`.
  3. Created `.gitattributes` to explicitly preserve LF line endings on `geometry.py`.
  4. Updated imports in `integration.py` and `run_preview.py` to reference `cosmic_geometry.py`.
- **Verification:** `tests/test_cinematic_orbital_aura.py` passes 12/12 checks, preserving the exact expected golden core hash (`a26fb15a1d66b74105faafc4738dbbb463594e6ce37d621402eff9e18d511106`).

### B. Voice Privacy Invariant Test (`tests/test_voice_manager.py`)
- **Diagnosis:** `test_privacy_no_audio_files_created_on_disk` scanned `D:\EV` for `.wav` files without checking if they were pre-existing repository assets. It tripped over `prototypes/cinematic_v4/assets/startup/arrival.wav`, a static procedural startup asset committed on 16 September 2026.
- **Resolution:**
  1. Isolated runtime data paths by setting `EV_USER_DATA_DIR` to `tmp_path / "runtime"`.
  2. Dynamically resolved the workspace root without hardcoded drive letters.
  3. Captured a snapshot of pre-existing audio assets before voice processing.
  4. Verified that no *new* audio files (`.wav` or `.pcm`) were created anywhere during voice processing.
- **Verification:** `tests/test_voice_manager.py` passes 41/41 checks, strictly catching real disk leaks while allowing static assets.

## 4. Test Verification Summary (Dedicated Writable Temp Dir)
Pytest temporary directory cleanup lock on Windows was resolved by adding `addopts = --basetemp=test_runtime/pytest_temp` to `pytest.ini`.

1. **Group 1: Music Foundation, Beats, Reaction Modes, Startup Audio, Workspace & Snapshots**
   - Command: `pytest tests/test_music_foundation.py tests/test_music_beats.py tests/test_music_reaction_modes.py tests/test_cinematic_startup_audio.py tests/test_music_workspace.py tests/test_music_analysis_snapshots.py -q -p no:cacheprovider`
   - **Result:** **75 passed** in 23.36s.
2. **Group 2: Action Pipeline, Planning, Execution & Verifier**
   - Command: `pytest tests/test_action_pipeline.py tests/test_planning.py tests/test_verifier.py tests/test_execution_verification.py -q -p no:cacheprovider`
   - **Result:** **112 passed, 6 subtests passed** in 11.57s.
3. **Group 3: Provider Configuration & Bridge Contracts**
   - Command: `pytest tests/test_provider_config.py tests/test_gui_bridge.py -q -p no:cacheprovider`
   - **Result:** **46 passed** in 28.90s.
4. **Group 4: Cinematic Orbital Aura & GUI Settings**
   - Command: `pytest tests/test_cinematic_orbital_aura.py tests/test_gui_settings.py -q -p no:cacheprovider`
   - **Result:** **22 passed** in 49.45s.
5. **Group 5: Voice Manager & VAD**
   - Command: `pytest tests/test_voice_manager.py tests/test_voice_vad.py -q -p no:cacheprovider`
   - **Result:** **61 passed** in 12.45s.
- **Total Automated Unit & Contract Tests:** **316 passed, 0 failed.**

## 5. End-to-End Application Smoke Test
Executed via `tools/smoke_test_connected_app.py`:
- `1_launch_cinematic`: **PASS** (Cinematic default window initialized)
- `2_golden_core_stage`: **PASS** (Golden nucleus stage and scene rendered)
- `3_settings_open_close`: **PASS** (Settings overlay toggles and controls state)
- `4_mode_switch_music`: **PASS** (Smooth transition to Music workspace)
- `5_three_visualizers`: **PASS** (CeilingRain, FlowTrace, SegmentStack all loaded)
- `6_playback_session`: **PASS** (Local track queued and transport controls functional)
- `7_mode_switch_assistant`: **PASS** (Transition back to Assistant workspace)
- `8_clean_shutdown`: **PASS** (All engines and bridge terminate cleanly)
- **Overall:** **SUCCESS (ALL PASSED)**
