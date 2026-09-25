# DEPENDENCY SUMMARY: E.V. Desktop Application

## 1. Runtime & Toolchain Versions
- **Python**: Python 3.12.10 (64-bit on Windows 10/11)
- **Host OS**: Windows 10 Pro (Build 19045) / Windows 11
- **Package Installer**: pip 25.0.1
- **Qt Runtime**: PySide6 6.11.2 (Qt 6.8+ required, Qt 6.11.2 installed)

---

## 2. Direct Dependencies (`requirements.txt`)

| Package | Specified Constraint | Installed Version | Purpose |
|---|---|---|---|
| `pydantic` | unpinned | 2.13.4 | Core data models, schema validation |
| `python-dotenv` | unpinned | 1.2.3 | Environment variable loading from `.env` |
| `PySide6` | `>=6.8.0,<7` | 6.11.2 | Qt Quick, Qt Quick 3D, GUI host |
| `numpy` | `>=1.26` | 2.5.2 | FFT analysis, spectral calculations, audio buffers |
| `PyAudioWPatch` | `==0.2.12.8` (win32) | 0.2.12.8 | WASAPI loopback audio capture |
| `openwakeword` | `>=0.6.0` | 0.6.0 | Local wake-word detection |

---

## 3. Key Secondary & Optional Dependencies (in `.venv`)

| Package | Installed Version | Purpose |
|---|---|---|
| `faster-whisper` | 1.2.1 | Automatic Speech Recognition (ASR) via CTranslate2 |
| `ctranslate2` | 4.8.2 | Fast inference engine for Whisper models |
| `onnxruntime` | 1.29.0 | ONNX model execution (openWakeWord backend) |
| `sounddevice` | 0.5.6 | Microphone input capture |
| `httpx` | 0.28.1 | Async HTTP client for AI provider APIs |
| `google-genai` | 2.21.0 | Official Google GenAI SDK |
| `psutil` | 7.2.2 | Hardware and process monitoring telemetry |
| `pytest` | 9.1.1 | Test execution framework |
| `anyio` | 4.14.2 | Asynchronous concurrency library |
| `cryptography` | 50.0.1 | Cryptographic primitives |

---

## 4. Potentially Obsolete or Incompatible Dependencies
- **NumPy 2.x Compatibility**: The installed version is NumPy 2.5.2. Some older C-extensions in voice libraries (e.g. older PyAudio or Whisper builds) require NumPy < 2.0. In the current virtual environment, PyAudioWPatch 0.2.12.8 and faster-whisper 1.2.1 work correctly with NumPy 2.5.2, but any new C-extensions should be validated against the NumPy 2.0 C-API.
- **PyAudioWPatch Win32 Constraint**: PyAudioWPatch is strictly Windows-only. It will fail installation on macOS or Linux unless marked with `sys_platform == "win32"`.
- **Unpinned `pydantic`**: `requirements.txt` has unpinned `pydantic`. The codebase is written against Pydantic v2 (`pydantic>=2.0`).

---

## 5. Lockfiles Found
- **Status**: No formal lockfile (`poetry.lock`, `Pipfile.lock`, `pnpm-lock.yaml`, etc.) is committed in the repository root.
- **Recommendation**: Create a pinned `requirements.lock` generated via `pip freeze` from the verified `.venv` environment to guarantee reproducible builds across developer machines.
