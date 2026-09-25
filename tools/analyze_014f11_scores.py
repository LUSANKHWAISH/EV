"""
Analyze score distributions and error forensics for Task 014F-11.
"""
import os
import sys
import json
import numpy as np
from pathlib import Path

REPO_ROOT = r"D:\EV"
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tools.wakeword_dataset import WakeWordDatasetPipeline, compute_file_sha256
from tools.experiment_014f11_runner import evaluate_onnx_model_on_locked_holdout

pipeline = WakeWordDatasetPipeline(random_seed=42)
X_holdout, y_holdout, holdout_samples = pipeline.extract_locked_holdout_features()

models = {
    "Baseline": r"D:\EV\models\wakeword\hey_ev.onnx",
    "Candidate_V1": r"D:\EV\models\wakeword\candidates\hey_ev_human_v2.onnx",
    "Candidate_V2": r"D:\EV\models\wakeword\candidates\hey_ev_human_v3.onnx",
}

print("==========================================================================================")
print("                       LOCKED HOLDOUT PER-SAMPLE SCORE ANALYSIS")
print("==========================================================================================")
print(f"{'Category':<16} | {'Phrase':<20} | {'Base Score':<10} | {'V1 Score':<10} | {'V2 Score':<10} | {'Filename'}")
print("-" * 110)

evals = {}
for name, path in models.items():
    evals[name] = evaluate_onnx_model_on_locked_holdout(path, X_holdout, y_holdout, holdout_samples, human_dir=pipeline.human_dir)

for i, s in enumerate(holdout_samples):
    cat = s.get("category", "")
    phrase = s.get("phrase", "")
    fn = s.get("filename", "")
    b_s = evals["Baseline"]["sample_details"][i]["score"]
    v1_s = evals["Candidate_V1"]["sample_details"][i]["score"]
    v2_s = evals["Candidate_V2"]["sample_details"][i]["score"]
    print(f"{cat:<16} | {phrase:<20} | {b_s:<10.4f} | {v1_s:<10.4f} | {v2_s:<10.4f} | {fn}")
