# 08 — QUESTIONS FOR OWNER: E.V. Desktop Application

The following questions cannot be answered solely from the repository code and will guide architectural and product decisions for subsequent development.

---

## 1. Multi-Visualizer Studio & Equalizer
1. **Interactive Panel Resizing**: Should the multi-visualizer studio allow user-driven drag-and-drop / panel resizing directly within the QML interface, or should layouts remain fixed presets (e.g., "Reference Trio", "Full Spectrum", "Dual Waveform") selectable via a dropdown?
2. **Playback Equalizer Architecture**: Is an internal software equalizer desired (which requires writing an owned decode/DSP/playback pipeline using `QAudioSink`), or would an external system-level EQ (e.g., EqualizerAPO integration) be preferred?

---

## 2. Voice & Conversational Interaction
3. **Voice Duplex Policy**: When E.V. speaks (TTS), should background music playback pause completely, mute temporarily, or duck volume (e.g., to 20%)?
4. **Offline vs. Cloud Speech Recognition**: Should `faster-whisper` remain the primary ASR engine running locally on CPU/CUDA, or should cloud-based STT (e.g., Google Speech-to-Text or OpenAI Whisper API) be offered as a lighter alternative for low-power laptops?

---

## 3. Deployment & Packaging
5. **Distribution Format**: What is the target packaging format for end-users?
   - Standalone portable `.exe` (PyInstaller single-file or directory bundle)?
   - Windows Installer (`.msi` / Inno Setup / WiX)?
   - Store package (`MSIX`)?
6. **Code Signing**: Will an EV code-signing certificate be provided for signing the Windows executable and SmartScreen validation?

---

## 4. Platform Support
7. **Target OS Scope**: Is E.V. intended exclusively for Windows 10/11 (utilizing WASAPI, PowerShell, and DPAPI), or is cross-platform support (macOS / Linux) planned for the future? (Note: PyAudioWPatch, DPAPI, and PowerShell execution are currently Windows-specific).
