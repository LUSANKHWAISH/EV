@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    echo E.V.'s existing Python environment was not found in .venv.
    pause
    exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" -B -m gui.app
