"""
Canonical Streaming Two-Stage Wake-Word Verification Benchmark (Task 014F-12A).

Evaluates:
  1. Baseline Stage 1 alone (hey_ev.onnx)
  2. Candidate V1 Stage 1 alone (hey_ev_human_v2.onnx)
  3. Candidate V2 Stage 1 alone (hey_ev_human_v3.onnx)
  4. Combined Stage 1 (Candidate V1) + Stage 2 Verifier (FasterWhisperWakeVerifier)
  5. Combined Stage 1 (Baseline) + Stage 2 Verifier (FasterWhisperWakeVerifier)

Protocol:
  - 16 kHz mono signed PCM16
  - 80 ms / 1280 sample sequential frames
  - Deterministic reset between utterances
  - Full 2-second utterance streaming aggregation with peak scoring
  - Stage 2 invocation strictly on Stage 1 candidate trigger
  - Strict leakage isolation: Dev benchmark on non-holdout; Single final evaluation on locked holdout
"""
from __future__ import annotations

import ctypes
import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

REPO_ROOT = Path(r"D:\EV")
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
from openwakeword.model import Model

from core.voice_capture import AudioFrame
from core.wake_verifier import FasterWhisperWakeVerifier, WakeVerificationResult
from tools.wakeword_dataset import compute_file_sha256, load_pcm16_wav

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

# Paths
ACTIVE_MODEL_PATH = REPO_ROOT / "models" / "wakeword" / "hey_ev.onnx"
CANDIDATE_V1_PATH = REPO_ROOT / "models" / "wakeword" / "candidates" / "hey_ev_human_v2.onnx"
CANDIDATE_V2_PATH = REPO_ROOT / "models" / "wakeword" / "candidates" / "hey_ev_human_v3.onnx"
HUMAN_DIR = REPO_ROOT / "models" / "wakeword" / "dataset" / "human"
HOLDOUT_MANIFEST_PATH = HUMAN_DIR / "locked_human_holdout_manifest.json"
MANIFEST_PATH = HUMAN_DIR / "human_collection_manifest.json"

FRAME_DURATION_MS = 80
FRAME_SAMPLES = int(16000 * FRAME_DURATION_MS / 1000)  # 1280 samples


@dataclass
class EvaluationSample:
    path: Path
    filename: str
    sha256: str
    label: int  # 1 = positive, 0 = negative
    category: str  # 'positive', 'hard_negative', 'general_negative'
    phrase: str
    is_holdout: bool


@dataclass
class SampleEvaluationResult:
    sample: EvaluationSample
    stage1_peak_score: float
    stage1_triggered: bool
    stage2_result: Optional[WakeVerificationResult]
    combined_verified: bool
    frame_count: int
    stage1_latencies_ms: List[float] = field(default_factory=list)
    stage2_latency_ms: float = 0.0


@dataclass
class BenchmarkSummary:
    total_samples: int
    positives: int
    hard_negatives: int
    general_negatives: int
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int
    positive_recall: float
    hard_negative_fpr: float
    hard_negative_rejection: float
    general_negative_fpr: float
    general_negative_rejection: float
    total_fpr: float
    accuracy: float
    avg_stage1_latency_ms: float
    avg_stage2_latency_ms: float
    avg_total_latency_ms: float


def load_dataset_inventory() -> Tuple[List[EvaluationSample], List[EvaluationSample]]:
    """Load and categorize all non-quarantine human recordings into dev and locked-holdout sets."""
    with open(HOLDOUT_MANIFEST_PATH, "r", encoding="utf-8") as f:
        holdout_data = json.load(f)
    holdout_map = {s["sha256"].lower(): s for s in holdout_data.get("samples", [])}

    manifest_map = {}
    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH, "r", encoding="utf-8") as mf:
            m_items = json.load(mf)
            manifest_map = {item.get("filename", ""): item for item in m_items}

    dev_samples: List[EvaluationSample] = []
    holdout_samples: List[EvaluationSample] = []

    # Positives
    pos_files = sorted((HUMAN_DIR / "positive").glob("*.wav"))
    for pf in pos_files:
        sha = compute_file_sha256(pf).lower()
        meta = manifest_map.get(pf.name, {})
        phrase = meta.get("phrase", "Hey EV")
        is_holdout = sha in holdout_map
        s = EvaluationSample(
            path=pf,
            filename=pf.name,
            sha256=sha,
            label=1,
            category="positive",
            phrase=phrase,
            is_holdout=is_holdout,
        )
        if is_holdout:
            holdout_samples.append(s)
        else:
            dev_samples.append(s)

    # Negatives
    neg_files = sorted((HUMAN_DIR / "negative").glob("*.wav"))
    hard_neg_prefixes = (
        "hey evan", "hey evelyn", "hey everyone", "hey everybody", "hey evidence",
        "hey event", "hey events", "hey everest", "hey everett", "hey everywhere",
        "hey eventually", "hey everyday", "hey stevie", "hey steve", "every", "hey",
        "heavy", "heavy duty", "heavy rain", "every day", "hey avi"
    )

    for nf in neg_files:
        sha = compute_file_sha256(nf).lower()
        meta = manifest_map.get(nf.name, {})
        phrase = meta.get("phrase", nf.stem).lower()
        is_holdout = sha in holdout_map

        is_hard = any(phrase.startswith(p) or p in phrase for p in hard_neg_prefixes)
        category = "hard_negative" if is_hard else "general_negative"

        s = EvaluationSample(
            path=nf,
            filename=nf.name,
            sha256=sha,
            label=0,
            category=category,
            phrase=meta.get("phrase", nf.stem),
            is_holdout=is_holdout,
        )
        if is_holdout:
            holdout_samples.append(s)
        else:
            dev_samples.append(s)

    return dev_samples, holdout_samples


def stream_evaluate_sample(
    sample: EvaluationSample,
    stage1_model: Model,
    stage2_verifier: Optional[FasterWhisperWakeVerifier] = None,
    threshold: float = 0.50,
) -> SampleEvaluationResult:
    """
    Simulate real-time streaming inference using canonical 80ms sequential frames.
    """
    # Load 16kHz mono PCM16 audio
    audio_data = load_pcm16_wav(str(sample.path))
    total_samples = len(audio_data)
    frames_int16: List[np.ndarray] = []
    for i in range(0, total_samples, FRAME_SAMPLES):
        chunk = audio_data[i : i + FRAME_SAMPLES]
        if len(chunk) < FRAME_SAMPLES:
            chunk = np.pad(chunk, (0, FRAME_SAMPLES - len(chunk)), mode="constant")
        frames_int16.append(chunk)

    # Deterministic reset
    stage1_model.reset()
    if stage2_verifier is not None:
        stage2_verifier.reset()

    model_key = list(stage1_model.models.keys())[0]

    peak_score = 0.0
    stage1_latencies = []
    triggered = False
    captured_audio_chunks: List[np.ndarray] = []
    stage2_res: Optional[WakeVerificationResult] = None

    t_frame_dur = FRAME_DURATION_MS / 1000.0
    for idx, chunk_1280 in enumerate(frames_int16):
        captured_audio_chunks.append(chunk_1280)

        # Stage 1 inference
        t0 = time.monotonic()
        preds = stage1_model.predict(chunk_1280)
        t_lat = (time.monotonic() - t0) * 1000.0
        stage1_latencies.append(t_lat)

        score_val = float(preds.get(model_key, 0.0)) if isinstance(preds, dict) else 0.0
        if score_val > peak_score:
            peak_score = score_val

        if score_val >= threshold and not triggered:
            triggered = True
            # Invoke Stage 2 immediately upon first candidate trigger
            if stage2_verifier is not None:
                # Concatenate accumulated audio up to this trigger point
                accumulated_pcm16 = np.concatenate(captured_audio_chunks)
                stage2_res = stage2_verifier.verify_phrase(accumulated_pcm16)

    # If Stage 2 verifier not attached:
    if stage2_verifier is None:
        combined_verified = triggered
    else:
        combined_verified = triggered and (stage2_res is not None and stage2_res.verified)

    stage2_lat = stage2_res.latency_ms if stage2_res else 0.0

    return SampleEvaluationResult(
        sample=sample,
        stage1_peak_score=peak_score,
        stage1_triggered=triggered,
        stage2_result=stage2_res,
        combined_verified=combined_verified,
        frame_count=len(frames_int16),
        stage1_latencies_ms=stage1_latencies,
        stage2_latency_ms=stage2_lat,
    )


def compute_metrics(results: List[SampleEvaluationResult]) -> BenchmarkSummary:
    total = len(results)
    positives = [r for r in results if r.sample.label == 1]
    negatives = [r for r in results if r.sample.label == 0]
    hard_negs = [r for r in negatives if r.sample.category == "hard_negative"]
    gen_negs = [r for r in negatives if r.sample.category == "general_negative"]

    tp = sum(1 for r in positives if r.combined_verified)
    fn = len(positives) - tp
    fp = sum(1 for r in negatives if r.combined_verified)
    tn = len(negatives) - fp

    fp_hard = sum(1 for r in hard_negs if r.combined_verified)
    tn_hard = len(hard_negs) - fp_hard
    fp_gen = sum(1 for r in gen_negs if r.combined_verified)
    tn_gen = len(gen_negs) - fp_gen

    pos_recall = (tp / len(positives) * 100) if positives else 0.0
    hard_fpr = (fp_hard / len(hard_negs) * 100) if hard_negs else 0.0
    hard_rej = (tn_hard / len(hard_negs) * 100) if hard_negs else 0.0
    gen_fpr = (fp_gen / len(gen_negs) * 100) if gen_negs else 0.0
    gen_rej = (tn_gen / len(gen_negs) * 100) if gen_negs else 0.0
    total_fpr = (fp / len(negatives) * 100) if negatives else 0.0
    acc = ((tp + tn) / total * 100) if total else 0.0

    all_s1_lats = [lat for r in results for lat in r.stage1_latencies_ms]
    avg_s1_lat = float(np.mean(all_s1_lats)) if all_s1_lats else 0.0
    s2_lats = [r.stage2_latency_ms for r in results if r.stage2_latency_ms > 0]
    avg_s2_lat = float(np.mean(s2_lats)) if s2_lats else 0.0
    avg_tot_lat = avg_s1_lat + avg_s2_lat

    return BenchmarkSummary(
        total_samples=total,
        positives=len(positives),
        hard_negatives=len(hard_negs),
        general_negatives=len(gen_negs),
        true_positives=tp,
        false_positives=fp,
        true_negatives=tn,
        false_negatives=fn,
        positive_recall=pos_recall,
        hard_negative_fpr=hard_fpr,
        hard_negative_rejection=hard_rej,
        general_negative_fpr=gen_fpr,
        general_negative_rejection=gen_rej,
        total_fpr=total_fpr,
        accuracy=acc,
        avg_stage1_latency_ms=avg_s1_lat,
        avg_stage2_latency_ms=avg_s2_lat,
        avg_total_latency_ms=avg_tot_lat,
    )


def run_full_suite():
    dev_samples, holdout_samples = load_dataset_inventory()
    print("=" * 70)
    print("E.V. TASK 014F-12A TWO-STAGE WAKE-WORD VERIFICATION BENCHMARK")
    print("=" * 70)
    print(f"Development Set Samples: {len(dev_samples)}")
    print(f"  Positives:         {sum(1 for s in dev_samples if s.category == 'positive')}")
    print(f"  Hard Negatives:    {sum(1 for s in dev_samples if s.category == 'hard_negative')}")
    print(f"  General Negatives: {sum(1 for s in dev_samples if s.category == 'general_negative')}")
    print(f"Locked Holdout Samples:  {len(holdout_samples)}")
    print(f"  Positives:         {sum(1 for s in holdout_samples if s.category == 'positive')}")
    print(f"  Hard Negatives:    {sum(1 for s in holdout_samples if s.category == 'hard_negative')}")
    print(f"  General Negatives: {sum(1 for s in holdout_samples if s.category == 'general_negative')}")
    print("-" * 70)

    # Initialize Stage 1 Models
    print("Initializing Stage 1 OpenWakeWord Models...")
    m_base = Model(wakeword_models=[str(ACTIVE_MODEL_PATH)], inference_framework="onnx")
    m_cand_v1 = Model(wakeword_models=[str(CANDIDATE_V1_PATH)], inference_framework="onnx")
    m_cand_v2 = Model(wakeword_models=[str(CANDIDATE_V2_PATH)], inference_framework="onnx")

    # Initialize Stage 2 Verifier
    print("Initializing Stage 2 FasterWhisperWakeVerifier (tiny.en INT8 CPU)...")
    t0_init = time.monotonic()
    verifier = FasterWhisperWakeVerifier(
        model_size_or_path="tiny.en",
        device="cpu",
        compute_type="int8",
        cpu_threads=4,
        download_root=r"D:\EV\models\asr",
    )
    verifier.load_model()
    init_dur = (time.monotonic() - t0_init) * 1000.0
    print(f"Stage 2 Initialized in {init_dur:.1f}ms")

    # Benchmarking configurations
    configs = [
        ("Baseline (hey_ev.onnx) Alone", m_base, None, 0.50),
        ("Candidate V1 (hey_ev_human_v2.onnx) Alone", m_cand_v1, None, 0.50),
        ("Candidate V2 (hey_ev_human_v3.onnx) Alone", m_cand_v2, None, 0.50),
        ("Two-Stage: Baseline + Stage 2 Verifier", m_base, verifier, 0.50),
        ("Two-Stage: Candidate V1 + Stage 2 Verifier", m_cand_v1, verifier, 0.50),
    ]

    print("\n" + "=" * 70)
    print("PHASE 1: DEVELOPMENT BENCHMARK (NON-HOLDOUT DATA)")
    print("=" * 70)

    dev_metrics_summary = {}
    for name, s1_mod, s2_ver, thresh in configs:
        res_list = [stream_evaluate_sample(s, s1_mod, s2_ver, threshold=thresh) for s in dev_samples]
        summary = compute_metrics(res_list)
        dev_metrics_summary[name] = (summary, res_list)
        print(f"\nConfiguration: {name}")
        print(f"  Positive Recall:       {summary.positive_recall:.2f}% ({summary.true_positives}/{summary.positives})")
        print(f"  Hard-Neg Rejection:    {summary.hard_negative_rejection:.2f}% ({summary.hard_negatives - int(round(summary.hard_negative_fpr*summary.hard_negatives/100))}/{summary.hard_negatives}) [FPR: {summary.hard_negative_fpr:.2f}%]")
        print(f"  General-Neg Rejection: {summary.general_negative_rejection:.2f}% ({summary.general_negatives - int(round(summary.general_negative_fpr*summary.general_negatives/100))}/{summary.general_negatives}) [FPR: {summary.general_negative_fpr:.2f}%]")
        print(f"  Total FPR:             {summary.total_fpr:.2f}% ({summary.false_positives}/{summary.hard_negatives + summary.general_negatives})")
        print(f"  Overall Accuracy:      {summary.accuracy:.2f}%")
        print(f"  Stage 1 Latency/frame: {summary.avg_stage1_latency_ms:.2f}ms")
        if s2_ver:
            print(f"  Stage 2 Latency/trig:  {summary.avg_stage2_latency_ms:.2f}ms")

    print("\n" + "=" * 70)
    print("PHASE 2: FROZEN LOCKED HOLDOUT EVALUATION (33 SAMPLES)")
    print("=" * 70)

    holdout_metrics_summary = {}
    for name, s1_mod, s2_ver, thresh in configs:
        res_list = [stream_evaluate_sample(s, s1_mod, s2_ver, threshold=thresh) for s in holdout_samples]
        summary = compute_metrics(res_list)
        holdout_metrics_summary[name] = (summary, res_list)
        print(f"\nConfiguration: {name}")
        print(f"  Positive Recall:       {summary.positive_recall:.2f}% ({summary.true_positives}/{summary.positives})")
        print(f"  Hard-Neg Rejection:    {summary.hard_negative_rejection:.2f}% [FPR: {summary.hard_negative_fpr:.2f}%]")
        print(f"  General-Neg Rejection: {summary.general_negative_rejection:.2f}% [FPR: {summary.general_negative_fpr:.2f}%]")
        print(f"  Total FPR:             {summary.total_fpr:.2f}% ({summary.false_positives}/{summary.hard_negatives + summary.general_negatives})")
        print(f"  Overall Accuracy:      {summary.accuracy:.2f}%")

    print("\n" + "=" * 70)
    print("HOLDOUT FORENSIC PER-SAMPLE DECISION MATRIX (Candidate V1 + Stage 2 Verifier)")
    print("=" * 70)
    cand_v1_s2_results = holdout_metrics_summary["Two-Stage: Candidate V1 + Stage 2 Verifier"][1]
    print(f"{'Filename':<32} | {'Category':<16} | {'Phrase':<20} | {'S1 Peak':<8} | {'S1 Trig':<7} | {'S2 Reason':<25} | {'S2 Text':<20} | {'Verified'}")
    print("-" * 140)
    for r in cand_v1_s2_results:
        s = r.sample
        s2_reason = r.stage2_result.reason if r.stage2_result else "S1_NOT_TRIGGERED"
        s2_text = r.stage2_result.raw_transcript if r.stage2_result else "-"
        s1_trig_str = "YES" if r.stage1_triggered else "NO"
        ver_str = "ACCEPTED" if r.combined_verified else "REJECTED"
        print(f"{s.filename:<32} | {s.category:<16} | {s.phrase[:18]:<20} | {r.stage1_peak_score:<8.3f} | {s1_trig_str:<7} | {s2_reason[:24]:<25} | {s2_text[:18]:<20} | {ver_str}")

    # Resource utilization
    rss_mb = 0.0
    try:
        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ('cb', ctypes.c_ulong),
                ('PageFaultCount', ctypes.c_ulong),
                ('PeakWorkingSetSize', ctypes.c_size_t),
                ('WorkingSetSize', ctypes.c_size_t),
                ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                ('QuotaPagedPoolUsage', ctypes.c_size_t),
                ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                ('PagefileUsage', ctypes.c_size_t),
                ('PeakPagefileUsage', ctypes.c_size_t),
            ]
        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        if ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            rss_mb = counters.WorkingSetSize / (1024 * 1024)
    except Exception:
        pass
    print("\n" + "=" * 70)
    print("RESOURCE & LATENCY PROFILING")
    print("=" * 70)
    print(f"Process Memory (Working Set): {rss_mb:.1f} MB")
    print(f"CPU Threads Configured: 4")

    # Save detailed JSON report
    report_dict = {
        "timestamp": time.time(),
        "dev_benchmark": {
            name: {
                "positive_recall": s.positive_recall,
                "hard_negative_fpr": s.hard_negative_fpr,
                "hard_negative_rejection": s.hard_negative_rejection,
                "general_negative_fpr": s.general_negative_fpr,
                "general_negative_rejection": s.general_negative_rejection,
                "total_fpr": s.total_fpr,
                "accuracy": s.accuracy,
                "true_positives": s.true_positives,
                "false_positives": s.false_positives,
                "true_negatives": s.true_negatives,
                "false_negatives": s.false_negatives,
                "avg_stage1_latency_ms": s.avg_stage1_latency_ms,
                "avg_stage2_latency_ms": s.avg_stage2_latency_ms,
            }
            for name, (s, _) in dev_metrics_summary.items()
        },
        "holdout_benchmark": {
            name: {
                "positive_recall": s.positive_recall,
                "hard_negative_fpr": s.hard_negative_fpr,
                "hard_negative_rejection": s.hard_negative_rejection,
                "general_negative_fpr": s.general_negative_fpr,
                "general_negative_rejection": s.general_negative_rejection,
                "total_fpr": s.total_fpr,
                "accuracy": s.accuracy,
                "true_positives": s.true_positives,
                "false_positives": s.false_positives,
                "true_negatives": s.true_negatives,
                "false_negatives": s.false_negatives,
            }
            for name, (s, _) in holdout_metrics_summary.items()
        },
    }

    out_path = REPO_ROOT / "models" / "wakeword" / "analysis" / "two_stage_benchmark_report.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report_dict, f, indent=2)
    print(f"\nFull benchmark report saved to {out_path}")


if __name__ == "__main__":
    run_full_suite()
