"""
Evaluate all 5 experimental configurations against the locked holdout.
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
from tools.experiment_014f11_runner import (
    DEFAULT_ACTIVE_MODEL,
    DEFAULT_CANDIDATE_V1_MODEL,
    generate_targeted_dataset,
    train_and_eval_configuration,
    export_model_to_onnx,
    evaluate_onnx_model_on_locked_holdout,
)

pipeline = WakeWordDatasetPipeline(random_seed=42)
X_holdout, y_holdout, holdout_samples = pipeline.extract_locked_holdout_features()

# Generate dataset
from openwakeword.utils import AudioFeatures
F = AudioFeatures(inference_framework="onnx", device="cpu", ncpu=4)
meta_enh, clips_enh, labels_enh = generate_targeted_dataset(random_seed=42, hn_aug_level="enhanced")
clips_arr_enh = np.vstack(clips_enh).astype(np.int16)
features_enh = F.embed_clips(clips_arr_enh, batch_size=32)

train_idx_enh = [i for i, m in enumerate(meta_enh) if m.split == "train"]
val_idx_enh = [i for i, m in enumerate(meta_enh) if m.split == "val"]
labels_enh_arr = np.array(labels_enh, dtype=np.float32)

X_train_enh, y_train_enh = features_enh[train_idx_enh], labels_enh_arr[train_idx_enh]
X_val_enh, y_val_enh = features_enh[val_idx_enh], labels_enh_arr[val_idx_enh]
meta_train_enh = [meta_enh[i] for i in train_idx_enh]
meta_val_enh = [meta_enh[i] for i in val_idx_enh]

configurations = [
    {
        "name": "Config_1_BaselineReplication",
        "epochs": 45,
        "lr": 8e-4,
        "weight_decay": 1e-4,
        "loss_type": "weighted_bce",
        "neg_weight": 1.4,
        "hn_weight": 1.4,
        "seed": 42,
    },
    {
        "name": "Config_2_NegWeight_2.5",
        "epochs": 45,
        "lr": 8e-4,
        "weight_decay": 1e-4,
        "loss_type": "weighted_bce",
        "neg_weight": 2.5,
        "hn_weight": 2.5,
        "seed": 42,
    },
    {
        "name": "Config_3_TwoTier_HN3.5",
        "epochs": 45,
        "lr": 6e-4,
        "weight_decay": 1e-4,
        "loss_type": "two_tier_hn",
        "neg_weight": 1.5,
        "hn_weight": 3.5,
        "seed": 42,
    },
    {
        "name": "Config_4_TwoTier_HN5.0",
        "epochs": 45,
        "lr": 5e-4,
        "weight_decay": 1e-4,
        "loss_type": "two_tier_hn",
        "neg_weight": 1.8,
        "hn_weight": 5.0,
        "seed": 42,
    },
    {
        "name": "Config_5_FocalLoss_G1.5",
        "epochs": 45,
        "lr": 6e-4,
        "weight_decay": 1e-4,
        "loss_type": "focal_loss",
        "neg_weight": 1.8,
        "hn_weight": 4.0,
        "focal_gamma": 1.5,
        "seed": 42,
    },
]

print("=" * 115)
print("             ALL CONFIGURATIONS COMPARISON ON LOCKED HOLDOUT (Threshold = 0.50)")
print("=" * 115)
print(f"{'Config':<30} | {'Human Recall':<16} | {'HardNeg FP':<14} | {'GenNeg FP':<12} | {'Holdout Acc':<12} | {'Holdout F1':<10}")
print("-" * 115)

active_eval = evaluate_onnx_model_on_locked_holdout(
    DEFAULT_ACTIVE_MODEL, X_holdout, y_holdout, holdout_samples, human_dir=pipeline.human_dir
)
v1_eval = evaluate_onnx_model_on_locked_holdout(
    DEFAULT_CANDIDATE_V1_MODEL, X_holdout, y_holdout, holdout_samples, human_dir=pipeline.human_dir
)

a_05 = active_eval["thresholds"]["0.5"]
v1_05 = v1_eval["thresholds"]["0.5"]

print(f"{'Active Baseline':<30} | {a_05['positive_recall_count']}/17 ({a_05['recall']*100:5.1f}%)    | {a_05['hard_neg_fp_count']}/12 ({a_05['hard_neg_fp_count']/12*100:4.1f}%)  | {a_05['gen_neg_fp_count']}/4 ({a_05['gen_neg_fp_count']/4*100:4.1f}%)  | {a_05['accuracy']:<12.3f} | {a_05['f1']:<10.3f}")
print(f"{'Candidate V1 (Task 014F-10)':<30} | {v1_05['positive_recall_count']}/17 ({v1_05['recall']*100:5.1f}%)    | {v1_05['hard_neg_fp_count']}/12 ({v1_05['hard_neg_fp_count']/12*100:4.1f}%)  | {v1_05['gen_neg_fp_count']}/4 ({v1_05['gen_neg_fp_count']/4*100:4.1f}%)  | {v1_05['accuracy']:<12.3f} | {v1_05['f1']:<10.3f}")

for cfg in configurations:
    model, res = train_and_eval_configuration(
        config_name=cfg["name"],
        X_train=X_train_enh,
        y_train=y_train_enh,
        meta_train=meta_train_enh,
        X_val=X_val_enh,
        y_val=y_val_enh,
        meta_val=meta_val_enh,
        epochs=cfg["epochs"],
        lr=cfg["lr"],
        weight_decay=cfg["weight_decay"],
        loss_type=cfg["loss_type"],
        neg_weight=cfg["neg_weight"],
        hn_weight=cfg["hn_weight"],
        focal_gamma=cfg.get("focal_gamma", 1.5),
        seed=cfg["seed"],
    )
    temp_onnx = Path(REPO_ROOT) / "models" / "wakeword" / "candidates" / f"temp_{cfg['name']}.onnx"
    export_model_to_onnx(model, str(temp_onnx))
    cfg_eval = evaluate_onnx_model_on_locked_holdout(
        str(temp_onnx), X_holdout, y_holdout, holdout_samples, human_dir=pipeline.human_dir
    )
    c_05 = cfg_eval["thresholds"]["0.5"]
    print(f"{cfg['name']:<30} | {c_05['positive_recall_count']}/17 ({c_05['recall']*100:5.1f}%)    | {c_05['hard_neg_fp_count']}/12 ({c_05['hard_neg_fp_count']/12*100:4.1f}%)  | {c_05['gen_neg_fp_count']}/4 ({c_05['gen_neg_fp_count']/4*100:4.1f}%)  | {c_05['accuracy']:<12.3f} | {c_05['f1']:<10.3f}")
    if temp_onnx.exists():
        temp_onnx.unlink()
