# 03 — SETUP AND COMMANDS: E.V. Desktop Application

All commands below assume execution in **PowerShell** on **Windows 10/11 (64-bit)** with the working directory set to the project root (`d:\EV`).

---

## 1. Required Runtimes & Toolchains
- **Operating System**: Windows 10 (Build 19045 or later) or Windows 11.
- **Python**: Python 3.12.x (64-bit). (Tested with Python 3.12.10).
- **GPU / Drivers**: DirectX 11/12 or Vulkan-capable GPU with up-to-date drivers for Qt Quick 3D.
- **Audio Output**: A connected audio output device (speakers or headphones) for WASAPI loopback capture.

---

## 2. Setting Up the Environment

### A. Create Virtual Environment
```powershell
Set-Location D:\EV
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
```

### B. Install Dependencies
```powershell
Set-Location D:\EV
# Install primary application dependencies
.\.venv\Scripts\pip.exe install -r requirements.txt

# For testing and development
.\.venv\Scripts\pip.exe install pytest anyio psutil httpx
```

> [!NOTE]
> Voice models (`faster-whisper`, `openwakeword`, `sounddevice`) are optional for core UI/Music development. To install optional voice dependencies:
> ```powershell
> .\.venv\Scripts\pip.exe install sounddevice faster-whisper openwakeword
> ```

---

## 3. Configuration Setup

Copy the template configuration to create your local environment:
```powershell
Set-Location D:\EV
Copy-Item .env.example .env
```

Contents of `.env`:
```ini
EV_LOG_LEVEL=INFO
EV_DRY_RUN=false
EV_MAX_COMMAND_TIMEOUT=120
```

> [!IMPORTANT]
> Do NOT store API keys in `.env`. Provider API keys are configured directly inside the application via the Settings Overlay and encrypted into Windows DPAPI.

---

## 4. Running the Application

### A. Canonical Cinematic Application (Default)
```powershell
Set-Location D:\EV
.\.venv\Scripts\python.exe -B -m gui.app
# Alternatively, double-click or run:
# .\Launch EV.cmd
```

### B. Classic Interface Fallback
```powershell
Set-Location D:\EV
.\.venv\Scripts\python.exe -B -m gui.app --classic
# Alternatively:
# .\Launch Classic EV.cmd
```

### C. Isolated 3D Nucleus Preview
```powershell
Set-Location D:\EV
.\.venv\Scripts\python.exe -B -m prototypes.cinematic_v4.preview
# Alternatively:
# .\Launch Cinematic Preview.cmd
```

---

## 5. Running Verification & Tests

> [!WARNING]
> On Windows without Developer Mode, always specify `--basetemp=C:\Users\<user>\AppData\Local\Temp\ev_pytest` to avoid `WinError 5: Access is denied` on pytest's default temp symlink.

### A. Music & Audio Analysis Suite (65 tests)
```powershell
Set-Location D:\EV
$env:EV_STARTUP_AUDIO='false'
.\.venv\Scripts\python.exe -B -m pytest tests/test_music_foundation.py tests/test_music_beats.py tests/test_music_reaction_modes.py tests/test_cinematic_startup_audio.py -v -p no:cacheprovider --basetemp=C:\Users\$env:USERNAME\AppData\Local\Temp\ev_pytest
```

### B. Multi-Visualizer Studio & Analysis Snapshot Suite (10 tests)
```powershell
Set-Location D:\EV
.\.venv\Scripts\python.exe -B -m pytest tests/test_music_workspace.py tests/test_music_analysis_snapshots.py -v -p no:cacheprovider --basetemp=C:\Users\$env:USERNAME\AppData\Local\Temp\ev_pytest
```

### C. GUI Settings & Provider Overlay Suite (10 tests)
```powershell
Set-Location D:\EV
.\.venv\Scripts\python.exe -B -m pytest tests/test_gui_settings.py -v -p no:cacheprovider --basetemp=C:\Users\$env:USERNAME\AppData\Local\Temp\ev_pytest
```

### D. Core Pipeline & Provider Config Suite (40 tests)
```powershell
Set-Location D:\EV
.\.venv\Scripts\python.exe -B -m pytest tests/test_paths.py tests/test_provider_config.py tests/test_action_pipeline.py -v -p no:cacheprovider --basetemp=C:\Users\$env:USERNAME\AppData\Local\Temp\ev_pytest
```

### E. GUI Modes & 3D Core Performance Suite (39 tests)
```powershell
Set-Location D:\EV
.\.venv\Scripts\python.exe -B -m pytest tests/test_gui_performance.py tests/test_gui_modes.py -v -p no:cacheprovider --basetemp=C:\Users\$env:USERNAME\AppData\Local\Temp\ev_pytest
```

---

## 6. Syntax & Compilation Checking

### Python Compile Check
```powershell
Set-Location D:\EV
.\.venv\Scripts\python.exe -m compileall -q core gui music providers config tests tools
```

---

## 7. Troubleshooting Known Setup Issues

| Issue | Cause | Solution |
|---|---|---|
| `WinError 5: Access is denied` in pytest | Pytest default `tmpdir` creates symlinks in `%TEMP%` requiring admin rights | Pass `--basetemp=C:\Users\<user>\AppData\Local\Temp\ev_pytest` to pytest |
| `No module named PyAudioWPatch` | PyAudioWPatch is not installed or platform is non-Windows | Run `pip install PyAudioWPatch==0.2.12.8` on Windows |
| Black screen / No 3D Core rendered | Graphics driver lacks Qt Quick 3D hardware acceleration | Ensure GPU drivers are updated; test with `$env:QSG_RHI_BACKEND='d3d11'` |
| `No default audio output device` | No audio playback endpoint is active | Plug in headphones or enable a default audio device in Windows Sound settings |
| Audio tests fail / clash | Multiple audio tests running concurrently | Run audio tests sequentially, never in parallel |
| Settings dialog keys reset | User session changed or DPAPI store moved | DPAPI keys are tied to the local Windows user account; re-enter keys in Settings |
