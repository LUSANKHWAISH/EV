"""
Acoustic Smoke Test for Task 014F-11: 3-Way Model Verification on Raw Acoustic Datasets.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = r"D:\EV"
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from openwakeword.model import Model

MODELS = {
    "Baseline": r"D:\EV\models\wakeword\hey_ev.onnx",
    "Candidate_V1": r"D:\EV\models\wakeword\candidates\hey_ev_human_v2.onnx",
    "Candidate_V2": r"D:\EV\models\wakeword\candidates\hey_ev_human_v3.onnx",
}

def main():
    print("==========================================================================================", flush=True)
    print("                 LIVE ACOUSTIC SMOKE TEST: 3-WAY MODEL COMPARISON", flush=True)
    print("==========================================================================================", flush=True)
    print(f"{'Category':<16} | {'Phrase':<24} | {'Baseline':<10} | {'Candidate V1':<12} | {'Candidate V2':<12}", flush=True)
    print("-" * 85, flush=True)

    engines = {
        name: Model(wakeword_models=[path], inference_framework="onnx")
        for name, path in MODELS.items()
    }

    raw_dir = Path(r"D:\EV\models\wakeword\dataset\raw")

    # Pick representative raw files
    test_files = [
        # Positives
        ("POSITIVE", "Hey EV (take 0)", raw_dir / "pos_base_h_0.wav"),
        ("POSITIVE", "Hey E.V. (take 1)", raw_dir / "pos_base_h_1.wav"),
        ("POSITIVE", "Hey E V (take 2)", raw_dir / "pos_base_h_2.wav"),
        # Hard negatives
        ("HARD_NEGATIVE", "Hey Everyone", raw_dir / "neg_hn_0.wav"),
        ("HARD_NEGATIVE", "Hey Evan", raw_dir / "neg_hn_1.wav"),
        ("HARD_NEGATIVE", "Hey Evie", raw_dir / "neg_hn_2.wav"),
        ("HARD_NEGATIVE", "Hey Evidence", raw_dir / "neg_hn_7.wav"),
        ("HARD_NEGATIVE", "Every", raw_dir / "neg_hn_19.wav"),
        # General negatives
        ("GENERAL_NEGATIVE", "Open browser", raw_dir / "neg_cmd_0.wav"),
        ("GENERAL_NEGATIVE", "Turn lights", raw_dir / "neg_cmd_1.wav"),
        ("GENERAL_NEGATIVE", "What time", raw_dir / "neg_cmd_2.wav"),
        ("GENERAL_NEGATIVE", "Cancel command", raw_dir / "neg_cmd_3.wav"),
    ]

    for cat, phrase, wav_p in test_files:
        if not wav_p.exists():
            continue
        scores = {}
        for name, oww in engines.items():
            oww.reset()
            preds = oww.predict_clip(str(wav_p), padding=0)
            m = float(max([x[list(x.keys())[0]] for x in preds])) if preds else 0.0
            scores[name] = m
        print(f"{cat:<16} | {phrase:<24} | {scores['Baseline']:<10.4f} | {scores['Candidate_V1']:<12.4f} | {scores['Candidate_V2']:<12.4f}", flush=True)

if __name__ == "__main__":
    main()
