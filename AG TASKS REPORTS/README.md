# E.V. VOICE PIPELINE — AG TASKS REPORTS

Welcome to the master archive of the Google Antigravity (AG) task reports for the **E.V. Voice Runtime Pipeline**.

---

## 📑 Archive Contents

1. [`01_TASK_014C_VAD_AND_WAKEWORD_FOUNDATION.md`](01_TASK_014C_VAD_AND_WAKEWORD_FOUNDATION.md)
   * VAD (`EnergyVADProvider`) & Wake-word (`EVWakeWordProvider`) foundation.
   * Canonical audio contract (16 kHz, mono, PCM16, 30 ms).
   * Commit: `577761ae65f8836a76256a14f1e1f1a0f8091ef4`.

2. [`02_TASK_014D_ASR_FOUNDATION_ARCHITECTURE_AND_IMPLEMENTATION.md`](02_TASK_014D_ASR_FOUNDATION_ARCHITECTURE_AND_IMPLEMENTATION.md)
   * ASR architecture audit & pure standard library foundation (`core/asr.py`).
   * Commit: `2c34977bc8c92ed2a3689c3671014a1ab0dad7cd`.

3. [`03_TASK_014D_B_FASTER_WHISPER_BENCHMARK_AND_MODEL_PROTECTION.md`](03_TASK_014D_B_FASTER_WHISPER_BENCHMARK_AND_MODEL_PROTECTION.md)
   * Production `faster-whisper` CTranslate2 INT8 provider (`core/asr_faster_whisper.py`).
   * Benchmark tool (`tools/benchmark_asr.py`) & model cache `.gitignore` protection.
   * Commit: `48334499422ac25459a2c17cc83fa725fd81572c`.

4. [`04_TASK_014E_1_VOICE_RUNTIME_INTEGRATION_IMPLEMENTATION.md`](04_TASK_014E_1_VOICE_RUNTIME_INTEGRATION_IMPLEMENTATION.md)
   * Complete voice runtime integration (`core/voice_manager.py`).
   * PortAudio microphone capture (`sounddevice 0.5.6`), utterance assembly, wake stripping.
   * Unit tests: 41 passed (`tests/test_voice_manager.py`).

5. [`05_TASK_014E_1_SOURCE_LEVEL_SAFETY_AUDIT.md`](05_TASK_014E_1_SOURCE_LEVEL_SAFETY_AUDIT.md)
   * Strict source-level safety and architecture audit.
   * Proved untrusted orchestrator boundary, memory-only privacy, thread safety.
   * Verdict: `PASS — SAFE TO COMMIT`.

6. [`06_TASK_014E_1_FINAL_COMMIT_AND_PUSH.md`](06_TASK_014E_1_FINAL_COMMIT_AND_PUSH.md)
   * Final commit & push report.
   * Commit: `66a3eb9a8ae53683d6b6b34a4fa3a6fd34fd5893`.

7. [`07_TASK_014E_2_PHYSICAL_RUNTIME_VALIDATION_AND_TUNING.md`](07_TASK_014E_2_PHYSICAL_RUNTIME_VALIDATION_AND_TUNING.md)
   * Real hardware execution on Intel Core i7-4770K CPU under INT8 quantization.
   * 10 technical commands benchmarked across `tiny.en` and `base.en`.
   * End-to-end pipeline test & STOP barge-in latency (196.09 ms).
   * Recommendation: `RECOMMEND base.en`.
   * Verdict: `PASS — PHYSICAL VOICE RUNTIME VALIDATED`.

8. [`FULL_CONVERSATION_LOG.md`](FULL_CONVERSATION_LOG.md)
   * Complete human-readable chronological transcript of every prompt and response.

9. [`raw_conversation_transcript.jsonl`](raw_conversation_transcript.jsonl)
   * Complete, bit-for-bit JSONL log of the full conversation trajectory (2.2 MB).

---

## 🏛️ Architecture Blueprint

```text
[Windows Microphone] ──(SoundDeviceAudioCaptureProvider)──> [AudioFrame: 16kHz, mono, PCM16, 30ms]
                                                                     │
                                                                     ├──> AudioRingBuffer (rolling ~3s)
                                                                     └──> EVBargeInStopDetector
                                                                                 │
                                                                           EVVoiceManager
                                                                                 │
                                        ┌────────────────────────────────────────┴────────────────────────────────────────┐
                                  [IDLE State]                                                                    [LISTENING State]
                                        │                                                                                 │
                                 EVWakeWordProvider                                                                 EVVADProvider
                                   ("Hey EV")                                                                   (Energy/RMS tracking)
                                        │                                                                                 │
                                        └───> _transition_to_listening()                                                 ├──> Silence Timeout: 1.1s
                                                     │                                                                    ├──> Initial Silence: 3.0s
                                                 Pre-Roll                                                                 ├──> Min Speech: 0.3s
                                                (750 ms)                                                                  └──> Max Utterance: 8.0s
                                                     │                                                                            │
                                                     └──────────────────────── Utterance Assembly ───────────────────────────────>│
                                                                                                                          [TRANSCRIBING State]
                                                                                                                                  │
                                                                                                                         EVASRProvider
                                                                                                                     (faster-whisper base.en)
                                                                                                                                  │
                                                                                                                           strip_wake_phrase()
                                                                                                                                  │
                                                                                                                         UNTRUSTED COMMAND
                                                                                                                                  │
                                                                                                                   EVOrchestrator.submit_command()
                                                                                                                                  │
                                                                                                                    E.V. Safety / Risk / Queue
```

---

## 📦 Commit History

| Task | Commit SHA | Summary |
| :--- | :--- | :--- |
| **014C** | `577761ae65f8836a76256a14f1e1f1a0f8091ef4` | `feat: add VAD and wake-word foundation` |
| **014D** | `2c34977bc8c92ed2a3689c3671014a1ab0dad7cd` | `feat: add ASR foundation interface and mock provider` |
| **014D-B**| `48334499422ac25459a2c17cc83fa725fd81572c` | `feat: add faster-whisper ASR provider and benchmark` |
| **014E-1**| `66a3eb9a8ae53683d6b6b34a4fa3a6fd34fd5893` | `feat: add voice runtime integration` |
| **014E-2**| *(Validation / Calibration)* | `NO SOURCE CHANGES REQUIRED` (Verified on CPU INT8) |

---
*Generated automatically for E.V. voice development session.*
