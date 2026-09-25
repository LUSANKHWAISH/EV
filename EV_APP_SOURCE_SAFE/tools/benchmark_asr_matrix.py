"""
tools/benchmark_asr_matrix.py - Comprehensive ASR Performance & Accuracy Matrix Benchmark

Task 014F-15:
Measures cold/warm latency, RTF, memory (RSS), and semantic accuracy across:
  - Models: tiny.en vs base.en
  - Beam sizes: 1, 2, 5
  - Decoder flags: without_timestamps (True/False), condition_on_previous_text (True/False), initial_prompt
  - CPU Threads: 1, 2, 4, 8
  - Command corpus: 8 canonical system commands
"""
from __future__ import annotations

import gc
import logging
import os
import platform
import sys
import tempfile
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import psutil

REPO_ROOT = Path(r"D:\EV")
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.asr import ASRResult, calculate_utterance_duration
from core.asr_faster_whisper import DEFAULT_MODEL_DIR, FasterWhisperASRProvider
from core.voice_capture import AudioFrame, DEFAULT_BYTES_PER_FRAME, DEFAULT_SAMPLE_RATE
from tools.wakeword_dataset import synthesize_sapi_speech

logging.basicConfig(level=logging.WARNING)

COMMAND_CORPUS: List[str] = [
    "check my CPU usage",
    "check my memory usage",
    "find process python",
    "tell me how much free space is on my C drive",
    "what is my IP address",
    "show active tasks",
    "system status",
    "open PowerShell",
]


def get_process_memory_mb() -> float:
    proc = psutil.Process()
    return proc.memory_info().rss / (1024.0 * 1024.0)


def load_wav_as_frames(wav_path: str) -> Tuple[List[AudioFrame], float]:
    with wave.open(wav_path, "rb") as wf:
        raw_bytes = wf.readframes(wf.getnframes())
    chunk_size = DEFAULT_BYTES_PER_FRAME
    frames: List[AudioFrame] = []
    ts = time.monotonic()
    for offset in range(0, len(raw_bytes), chunk_size):
        chunk = raw_bytes[offset : offset + chunk_size]
        if len(chunk) < chunk_size:
            chunk = chunk + b"\x00" * (chunk_size - len(chunk))
        frames.append(AudioFrame(data=chunk, timestamp=ts + len(frames) * 0.030))
    duration = len(frames) * 0.030
    return frames, duration


def generate_corpus_audio(tmp_dir: Path) -> Dict[str, Tuple[List[AudioFrame], float]]:
    corpus_audio: Dict[str, Tuple[List[AudioFrame], float]] = {}
    print(f"[*] Generating synthetic SAPI audio for {len(COMMAND_CORPUS)} commands in {tmp_dir}...")
    for idx, phrase in enumerate(COMMAND_CORPUS):
        wav_path = str(tmp_dir / f"cmd_{idx}.wav")
        ok = synthesize_sapi_speech(phrase, wav_path)
        if not ok or not os.path.exists(wav_path):
            raise RuntimeError(f"Failed to synthesize SAPI speech for: {phrase}")
        frames, dur = load_wav_as_frames(wav_path)
        corpus_audio[phrase] = (frames, dur)
        try:
            os.remove(wav_path)
        except Exception:
            pass
    print(f"[+] Successfully generated in-memory AudioFrames for all {len(COMMAND_CORPUS)} commands.")
    return corpus_audio


@dataclass
class BenchmarkRunResult:
    config_name: str
    model_name: str
    cpu_threads: int
    beam_size: int
    without_timestamps: bool
    condition_on_previous_text: bool
    initial_prompt: Optional[str]
    cold_load_sec: float
    cold_latency_ms: float
    warm_latency_ms: float
    audio_duration_sec: float
    rtf: float
    baseline_ram_mb: float
    peak_ram_mb: float
    transcripts: Dict[str, str]
    exact_matches: int
    semantic_matches: int
    total_commands: int


def run_single_config(
    config_name: str,
    model_name: str,
    cpu_threads: int,
    beam_size: int,
    without_timestamps: bool,
    condition_on_previous_text: bool,
    initial_prompt: Optional[str],
    corpus_audio: Dict[str, Tuple[List[AudioFrame], float]],
    warm_iterations: int = 3,
) -> BenchmarkRunResult:
    gc.collect()
    time.sleep(0.1)
    base_ram = get_process_memory_mb()

    provider = FasterWhisperASRProvider(
        model_size_or_path=model_name,
        device="cpu",
        compute_type="int8",
        cpu_threads=cpu_threads,
        download_root=DEFAULT_MODEL_DIR,
        beam_size=beam_size,
    )

    t0 = time.perf_counter()
    model = provider.load_model()
    cold_load_sec = time.perf_counter() - t0

    # Cold inference on first command
    first_cmd = COMMAND_CORPUS[0]
    first_frames, first_dur = corpus_audio[first_cmd]

    # Convert frames to audio_array
    import numpy as np
    from core.asr import frames_to_pcm

    def transcribe_with_params(frames: List[AudioFrame]) -> Tuple[str, float]:
        pcm_bytes = frames_to_pcm(frames)
        arr = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        kw: Dict[str, Any] = {
            "language": "en",
            "beam_size": beam_size,
            "temperature": 0.0,
            "without_timestamps": without_timestamps,
            "condition_on_previous_text": condition_on_previous_text,
        }
        if initial_prompt:
            kw["initial_prompt"] = initial_prompt
        segs, info = model.transcribe(arr, **kw)
        text = " ".join(s.text.strip() for s in segs if s.text).strip()
        return text, calculate_utterance_duration(frames)

    # First / cold inference
    t0 = time.perf_counter()
    first_transcript, _ = transcribe_with_params(first_frames)
    cold_latency_ms = (time.perf_counter() - t0) * 1000.0

    # Warm inferences across corpus
    latencies: List[float] = []
    durations: List[float] = []
    transcripts: Dict[str, str] = {}
    peak_ram = get_process_memory_mb()

    for cmd in COMMAND_CORPUS:
        frames, dur = corpus_audio[cmd]
        cmd_latencies = []
        last_text = ""
        for _ in range(warm_iterations):
            t0 = time.perf_counter()
            text, _ = transcribe_with_params(frames)
            t1 = time.perf_counter()
            cmd_latencies.append((t1 - t0) * 1000.0)
            last_text = text
            curr_ram = get_process_memory_mb()
            if curr_ram > peak_ram:
                peak_ram = curr_ram

        avg_cmd_lat = float(np.median(cmd_latencies))
        latencies.append(avg_cmd_lat)
        durations.append(dur)
        transcripts[cmd] = last_text

    avg_warm_lat = float(np.mean(latencies))
    total_audio_sec = float(sum(durations))
    total_time_sec = float(sum(latencies)) / 1000.0
    rtf = total_time_sec / total_audio_sec if total_audio_sec > 0 else 0.0

    # Semantic and exact matches
    exact = 0
    semantic = 0
    for expected, got in transcripts.items():
        exp_clean = expected.lower().strip()
        got_clean = got.lower().replace(".", "").replace(",", "").replace("'", "").strip()
        if exp_clean == got_clean:
            exact += 1
            semantic += 1
        else:
            # Semantic check: keywords check
            exp_words = set(exp_clean.split())
            got_words = set(got_clean.split())
            # Accept minor variations like "power shell" vs "powershell", "c drive" vs "see drive"
            got_normalized = got_clean.replace("power shell", "powershell").replace("sea drive", "c drive")
            if exp_clean == got_normalized:
                semantic += 1
            elif exp_words.issubset(set(got_normalized.split())):
                semantic += 1

    return BenchmarkRunResult(
        config_name=config_name,
        model_name=model_name,
        cpu_threads=cpu_threads,
        beam_size=beam_size,
        without_timestamps=without_timestamps,
        condition_on_previous_text=condition_on_previous_text,
        initial_prompt=initial_prompt,
        cold_load_sec=cold_load_sec,
        cold_latency_ms=cold_latency_ms,
        warm_latency_ms=avg_warm_lat,
        audio_duration_sec=float(np.mean(durations)),
        rtf=rtf,
        baseline_ram_mb=base_ram,
        peak_ram_mb=peak_ram,
        transcripts=transcripts,
        exact_matches=exact,
        semantic_matches=semantic,
        total_commands=len(COMMAND_CORPUS),
    )


def main() -> None:
    print("=" * 80)
    print("      E.V. TASK 014F-15: VOICE ASR PERFORMANCE & ACCURACY MATRIX")
    print("=" * 80)
    cpu_phys = psutil.cpu_count(logical=False)
    cpu_log = psutil.cpu_count(logical=True)
    print(f"Platform: {platform.system()} {platform.release()}")
    print(f"CPU:      Intel Core i7-4770K ({cpu_phys} physical cores / {cpu_log} logical threads)")
    print(f"Memory:   {psutil.virtual_memory().total / (1024**3):.1f} GB Total")
    print()

    with tempfile.TemporaryDirectory() as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        corpus_audio = generate_corpus_audio(tmp_dir)

        test_configs = [
            # 1. CURRENT BASELINE (as currently configured in core/asr_faster_whisper.py)
            {
                "config_name": "CFG-0: Baseline (base.en, beam=5, ts=True, cond=True, threads=4)",
                "model_name": "base.en",
                "cpu_threads": 4,
                "beam_size": 5,
                "without_timestamps": False,
                "condition_on_previous_text": True,
                "initial_prompt": None,
            },
            # 2. Decoder optimizations on base.en (beam=1 greedy, without_timestamps=True, cond=False)
            {
                "config_name": "CFG-1: base.en, beam=1 (greedy), ts=False, cond=False, threads=4",
                "model_name": "base.en",
                "cpu_threads": 4,
                "beam_size": 1,
                "without_timestamps": True,
                "condition_on_previous_text": False,
                "initial_prompt": None,
            },
            {
                "config_name": "CFG-2: base.en, beam=1, ts=False, cond=False, initial_prompt='E.V. PowerShell CPU RAM', threads=4",
                "model_name": "base.en",
                "cpu_threads": 4,
                "beam_size": 1,
                "without_timestamps": True,
                "condition_on_previous_text": False,
                "initial_prompt": "E.V. PowerShell CPU RAM",
            },
            {
                "config_name": "CFG-3: base.en, beam=2, ts=False, cond=False, threads=4",
                "model_name": "base.en",
                "cpu_threads": 4,
                "beam_size": 2,
                "without_timestamps": True,
                "condition_on_previous_text": False,
                "initial_prompt": None,
            },
            # 3. CPU Thread scaling on base.en (threads: 1, 2, 4, 8) with beam=1
            {
                "config_name": "CFG-4: base.en, beam=1, ts=False, cond=False, threads=1",
                "model_name": "base.en",
                "cpu_threads": 1,
                "beam_size": 1,
                "without_timestamps": True,
                "condition_on_previous_text": False,
                "initial_prompt": None,
            },
            {
                "config_name": "CFG-5: base.en, beam=1, ts=False, cond=False, threads=2",
                "model_name": "base.en",
                "cpu_threads": 2,
                "beam_size": 1,
                "without_timestamps": True,
                "condition_on_previous_text": False,
                "initial_prompt": None,
            },
            {
                "config_name": "CFG-6: base.en, beam=1, ts=False, cond=False, threads=8",
                "model_name": "base.en",
                "cpu_threads": 8,
                "beam_size": 1,
                "without_timestamps": True,
                "condition_on_previous_text": False,
                "initial_prompt": None,
            },
            # 4. Model comparison: tiny.en baseline vs optimized
            {
                "config_name": "CFG-7: tiny.en, beam=5, ts=True, cond=True, threads=4",
                "model_name": "tiny.en",
                "cpu_threads": 4,
                "beam_size": 5,
                "without_timestamps": False,
                "condition_on_previous_text": True,
                "initial_prompt": None,
            },
            {
                "config_name": "CFG-8: tiny.en, beam=1 (greedy), ts=False, cond=False, threads=4",
                "model_name": "tiny.en",
                "cpu_threads": 4,
                "beam_size": 1,
                "without_timestamps": True,
                "condition_on_previous_text": False,
                "initial_prompt": None,
            },
            {
                "config_name": "CFG-9: tiny.en, beam=1, ts=False, cond=False, initial_prompt='E.V. PowerShell CPU RAM', threads=4",
                "model_name": "tiny.en",
                "cpu_threads": 4,
                "beam_size": 1,
                "without_timestamps": True,
                "condition_on_previous_text": False,
                "initial_prompt": "E.V. PowerShell CPU RAM",
            },
        ]

        results: List[BenchmarkRunResult] = []

        print("\n--- RUNNING BENCHMARK MATRIX ---\n")
        for cfg in test_configs:
            print(f"[*] Testing {cfg['config_name']}...")
            res = run_single_config(
                config_name=cfg["config_name"],
                model_name=cfg["model_name"],
                cpu_threads=cfg["cpu_threads"],
                beam_size=cfg["beam_size"],
                without_timestamps=cfg["without_timestamps"],
                condition_on_previous_text=cfg["condition_on_previous_text"],
                initial_prompt=cfg["initial_prompt"],
                corpus_audio=corpus_audio,
                warm_iterations=2,
            )
            results.append(res)
            print(f"    -> Warm Latency: {res.warm_latency_ms:.1f} ms | RTF: {res.rtf:.3f} | Accuracy: {res.semantic_matches}/{res.total_commands} semantic")

        print("\n" + "=" * 80)
        print("                 BENCHMARK MATRIX RESULTS SUMMARY")
        print("=" * 80)
        print(f"{'Config':<55} | {'Cold(ms)':<8} | {'Warm(ms)':<8} | {'RTF':<6} | {'Exact':<5} | {'Semantic':<8} | {'Peak RAM'}")
        print("-" * 110)
        for r in results:
            print(f"{r.config_name[:55]:<55} | {r.cold_latency_ms:8.1f} | {r.warm_latency_ms:8.1f} | {r.rtf:6.3f} | {r.exact_matches:2d}/{r.total_commands} | {r.semantic_matches:2d}/{r.total_commands:2d}   | {r.peak_ram_mb:6.1f} MB")

        print("\n" + "=" * 80)
        print("                 COMMAND TRANSCRIPT DETAIL BY CONFIG")
        print("=" * 80)
        for r in results:
            print(f"\n--- {r.config_name} ---")
            for expected, got in r.transcripts.items():
                match_mark = "OK" if expected.lower().replace(" ", "") in got.lower().replace(" ", "") or got.lower().replace(" ", "") in expected.lower().replace(" ", "") else "DIFF"
                print(f"  [{match_mark:4s}] Expected: '{expected}'")
                print(f"         Got:      '{got}'")


if __name__ == "__main__":
    main()
