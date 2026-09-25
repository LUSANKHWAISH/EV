"""
Reproducible Hardened PyTorch Training Pipeline for "Hey EV" (Task 014F-10).

Controlled Human-Augmented Wake-Word Model Retraining + Locked Human Holdout Evaluation.
Performs:
  1. Active baseline model immutability verification (SHA256).
  2. Ingestion of verified non-holdout human recordings (52 pos, 48 neg) + synthetic data.
  3. Programmatic holdout leakage audit (overlap == 0).
  4. Speaker-adapted OpenWakeWordNet training with weighted BCE loss.
  5. Candidate model export to D:\\EV\\models\\wakeword\\candidates\\hey_ev_human_v2.onnx.
  6. Final locked human holdout benchmark comparing active baseline vs candidate across 7 thresholds.
  7. OpenWakeWordProvider runtime compatibility verification.
  8. Post-experiment immutability re-verification.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import onnx
import onnxruntime as ort
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset

# Ensure repo root is on sys.path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from core.voice_wakeword_openwakeword import OpenWakeWordProvider
from tools.wakeword_dataset import (
    SampleMetadata,
    WakeWordDatasetPipeline,
    audit_dataset_leakage,
    compute_file_sha256,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ev.wakeword.training")

DEFAULT_ACTIVE_MODEL = r"D:\EV\models\wakeword\hey_ev.onnx"
DEFAULT_BASELINE_MODEL = r"D:\EV\models\wakeword\hey_ev_v1_baseline.onnx"
DEFAULT_CANDIDATE_OUTPUT_DIR = r"D:\EV\models\wakeword\candidates"
DEFAULT_CANDIDATE_FILENAME = "hey_ev_human_v2.onnx"
EXPECTED_ACTIVE_SHA = "9b11e3db5ca4118a19a35618f91db66aabc66c1ffe762cd69b215c9a1204f377"
EXPECTED_HOLDOUT_SHA = "03a59c13fa35fa932065e364e0b4bde2c3d174efc8f774f9f03ba96dfefe18ba"


def verify_active_model_hash() -> str:
    """Verify that active model hey_ev.onnx has not been modified."""
    active_p = Path(DEFAULT_ACTIVE_MODEL)
    if not active_p.exists():
        raise FileNotFoundError(f"Active model hey_ev.onnx missing at {DEFAULT_ACTIVE_MODEL}")

    actual_sha = compute_file_sha256(active_p)
    if actual_sha != EXPECTED_ACTIVE_SHA.lower():
        raise RuntimeError(
            f"CRITICAL IMMUTABILITY VIOLATION: Active model SHA256 mismatch!\n"
            f"Expected: {EXPECTED_ACTIVE_SHA}\n"
            f"Actual:   {actual_sha}"
        )
    return actual_sha


# ============================================================================
# Neural Network Architecture (Strict openWakeWord DNN specification)
# ============================================================================
class FCNBlock(nn.Module):
    """Fully Connected Layer with LayerNorm and ReLU (openWakeWord FCNBlock)."""

    def __init__(self, layer_dim: int) -> None:
        super().__init__()
        self.fcn_layer = nn.Linear(layer_dim, layer_dim)
        self.relu = nn.ReLU()
        self.layer_norm = nn.LayerNorm(layer_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.relu(self.layer_norm(self.fcn_layer(x)))


class OpenWakeWordNet(nn.Module):
    """
    Standard openWakeWord Feedforward Classifier.
    Maps input embedding feature tensor of shape (batch, 16, 96) to activation score [0.0, 1.0].
    """

    def __init__(
        self,
        input_shape: Tuple[int, int] = (16, 96),
        layer_dim: int = 128,
        n_blocks: int = 1,
        n_classes: int = 1,
    ) -> None:
        super().__init__()
        self.input_shape = input_shape
        self.flatten = nn.Flatten()
        self.layer1 = nn.Linear(input_shape[0] * input_shape[1], layer_dim)
        self.relu1 = nn.ReLU()
        self.layernorm1 = nn.LayerNorm(layer_dim)
        self.blocks = nn.ModuleList([FCNBlock(layer_dim) for _ in range(n_blocks)])
        self.last_layer = nn.Linear(layer_dim, n_classes)
        self.last_act = nn.Sigmoid() if n_classes == 1 else nn.ReLU()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.relu1(self.layernorm1(self.layer1(self.flatten(x))))
        for block in self.blocks:
            x = block(x)
        return self.last_act(self.last_layer(x))


# ============================================================================
# Model Training Engine with Weighted Negative Penalty
# ============================================================================
def train_hey_ev_model(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    epochs: int = 45,
    batch_size: int = 32,
    learning_rate: float = 8e-4,
    weight_decay: float = 1e-4,
    neg_penalty_weight: float = 1.4,
    random_seed: int = 42,
    device: str = "cpu",
) -> Tuple[OpenWakeWordNet, Dict[str, float]]:
    """
    Train OpenWakeWordNet with weighted loss to balance positive recall and hard negative rejection.
    """
    torch.manual_seed(random_seed)
    np.random.seed(random_seed)

    # Ground zero/unbuffered feature inputs explicitly to negative label 0
    zero_train = np.zeros((48, 16, 96), dtype=np.float32)
    zero_train_y = np.zeros(48, dtype=np.float32)
    X_train_ext = np.vstack([X_train, zero_train])
    y_train_ext = np.concatenate([y_train, zero_train_y])

    zero_val = np.zeros((16, 16, 96), dtype=np.float32)
    zero_val_y = np.zeros(16, dtype=np.float32)
    X_val_ext = np.vstack([X_val, zero_val])
    y_val_ext = np.concatenate([y_val, zero_val_y])

    # Convert to PyTorch tensors
    train_dataset = TensorDataset(
        torch.from_numpy(X_train_ext).float(),
        torch.from_numpy(y_train_ext).float().unsqueeze(1),
    )
    val_dataset = TensorDataset(
        torch.from_numpy(X_val_ext).float(),
        torch.from_numpy(y_val_ext).float().unsqueeze(1),
    )

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)

    model = OpenWakeWordNet(input_shape=(16, 96), layer_dim=128, n_blocks=1)
    model.to(device)

    # Custom weighted loss: higher weight on negative false alarms
    def custom_loss(preds: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        eps = 1e-7
        preds = torch.clamp(preds, eps, 1.0 - eps)
        loss = -(targets * torch.log(preds) + neg_penalty_weight * (1.0 - targets) * torch.log(1.0 - preds))
        return torch.mean(loss)

    optimizer = optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=weight_decay)

    best_val_loss = float("inf")
    best_val_f1 = 0.0
    best_weights = copy.deepcopy(model.state_dict())
    best_metrics: Dict[str, float] = {}

    logger.info("Starting speaker-adapted training loop for %d epochs (neg_weight=%.2f)...", epochs, neg_penalty_weight)

    for epoch in range(1, epochs + 1):
        model.train()
        train_loss = 0.0

        for batch_x, batch_y in train_loader:
            batch_x, batch_y = batch_x.to(device), batch_y.to(device)
            optimizer.zero_grad()
            preds = model(batch_x)
            loss = custom_loss(preds, batch_y)
            loss.backward()
            optimizer.step()
            train_loss += loss.item() * len(batch_x)

        train_loss /= len(train_dataset)

        # Validation on disjoint non-holdout dev set
        model.eval()
        val_loss = 0.0
        all_preds = []
        all_targets = []

        with torch.no_grad():
            for batch_x, batch_y in val_loader:
                batch_x, batch_y = batch_x.to(device), batch_y.to(device)
                preds = model(batch_x)
                loss = custom_loss(preds, batch_y)
                val_loss += loss.item() * len(batch_x)
                all_preds.extend(preds.cpu().numpy().flatten())
                all_targets.extend(batch_y.cpu().numpy().flatten())

        val_loss /= len(val_dataset)
        preds_bin = (np.array(all_preds) >= 0.5).astype(int)
        targets_bin = np.array(all_targets).astype(int)

        tp = np.sum((preds_bin == 1) & (targets_bin == 1))
        fp = np.sum((preds_bin == 1) & (targets_bin == 0))
        tn = np.sum((preds_bin == 0) & (targets_bin == 0))
        fn = np.sum((preds_bin == 0) & (targets_bin == 1))

        acc = (tp + tn) / max(1, len(targets_bin))
        precision = tp / max(1, tp + fp)
        recall = tp / max(1, tp + fn)
        f1 = (2 * precision * recall) / max(1e-6, precision + recall)

        if epoch % 5 == 0 or epoch == epochs or f1 > best_val_f1:
            logger.info(
                "Epoch %2d/%2d: TrainLoss=%.4f, ValLoss=%.4f, Acc=%.3f, Prec=%.3f, Rec=%.3f, F1=%.3f (TP=%d, FP=%d, FN=%d)",
                epoch, epochs, train_loss, val_loss, acc, precision, recall, f1, tp, fp, fn
            )

        if f1 > best_val_f1 or (f1 == best_val_f1 and val_loss < best_val_loss):
            best_val_f1 = f1
            best_val_loss = val_loss
            best_weights = copy.deepcopy(model.state_dict())
            best_metrics = {
                "val_loss": float(val_loss),
                "val_accuracy": float(acc),
                "val_precision": float(precision),
                "val_recall": float(recall),
                "val_f1": float(f1),
                "val_tp": int(tp),
                "val_fp": int(fp),
                "val_tn": int(tn),
                "val_fn": int(fn),
                "epoch": epoch,
            }

    model.load_state_dict(best_weights)
    model.eval()
    logger.info("Training complete. Best checkpoint at epoch %d: F1=%.3f, ValLoss=%.4f", best_metrics["epoch"], best_metrics["val_f1"], best_metrics["val_loss"])
    return model, best_metrics


# ============================================================================
# Benchmark & Hard-Negative Evaluation (Backward-Compatible Helpers)
# ============================================================================
def evaluate_model_on_holdout(
    model: OpenWakeWordNet,
    X_holdout: np.ndarray,
    y_holdout: np.ndarray,
    metadata_holdout: List[SampleMetadata],
    threshold: float = 0.50,
) -> Dict[str, Any]:
    """
    Evaluate model across holdout samples and calculate per-phrase breakdown.
    """
    model.eval()
    with torch.no_grad():
        inputs = torch.from_numpy(X_holdout).float()
        scores = model(inputs).numpy().flatten()

    preds_bin = (scores >= threshold).astype(int)
    targets_bin = y_holdout.astype(int)

    tp = int(np.sum((preds_bin == 1) & (targets_bin == 1)))
    fp = int(np.sum((preds_bin == 1) & (targets_bin == 0)))
    tn = int(np.sum((preds_bin == 0) & (targets_bin == 0)))
    fn = int(np.sum((preds_bin == 0) & (targets_bin == 1)))

    acc = (tp + tn) / max(1, len(targets_bin))
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    f1 = (2 * precision * recall) / max(1e-6, precision + recall)

    phrases_to_track = [
        "Hey EV",
        "Hey Everyone",
        "Hey Evan",
        "Hey Evie",
        "Hey Evening",
        "Hey Evidence",
        "Hey Stevie",
        "Heavy",
        "Every",
    ]

    phrase_breakdown: Dict[str, Dict[str, Any]] = {}
    for target_phrase in phrases_to_track:
        matching_idx = [i for i, m in enumerate(metadata_holdout) if target_phrase.lower() in m.phrase.lower()]
        if matching_idx:
            phrase_scores = scores[matching_idx]
            phrase_preds = preds_bin[matching_idx]
            max_s = float(np.max(phrase_scores))
            mean_s = float(np.mean(phrase_scores))
            if target_phrase == "Hey EV":
                rec = float(np.mean(phrase_preds == 1))
                phrase_breakdown[target_phrase] = {
                    "count": len(matching_idx),
                    "recall": round(rec, 3),
                    "max_score": round(max_s, 3),
                    "mean_score": round(mean_s, 3),
                }
            else:
                rej = float(np.mean(phrase_preds == 0))
                phrase_breakdown[target_phrase] = {
                    "count": len(matching_idx),
                    "rejection_rate": round(rej, 3),
                    "false_triggers": int(np.sum(phrase_preds == 1)),
                    "max_score": round(max_s, 3),
                    "mean_score": round(mean_s, 3),
                }

    return {
        "accuracy": round(acc, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "phrase_breakdown": phrase_breakdown,
    }


def compare_with_baseline_model(
    baseline_onnx_path: str,
    hardened_model: OpenWakeWordNet,
    X_holdout: np.ndarray,
    y_holdout: np.ndarray,
    metadata_holdout: List[SampleMetadata],
) -> Dict[str, Any]:
    """Side-by-side holdout comparison between baseline model and hardened model."""
    if not os.path.exists(baseline_onnx_path) or len(X_holdout) == 0:
        return {}

    session = ort.InferenceSession(baseline_onnx_path, providers=["CPUExecutionProvider"])
    in_name = session.get_inputs()[0].name
    out_name = session.get_outputs()[0].name

    baseline_scores = session.run([out_name], {in_name: X_holdout.astype(np.float32)})[0].flatten()
    baseline_preds = (baseline_scores >= 0.5).astype(int)
    targets_bin = y_holdout.astype(int)

    base_tp = int(np.sum((baseline_preds == 1) & (targets_bin == 1)))
    base_fp = int(np.sum((baseline_preds == 1) & (targets_bin == 0)))
    base_tn = int(np.sum((baseline_preds == 0) & (targets_bin == 0)))
    base_fn = int(np.sum((baseline_preds == 0) & (targets_bin == 1)))

    base_acc = (base_tp + base_tn) / max(1, len(targets_bin))
    base_f1 = (2 * base_tp) / max(1e-6, 2 * base_tp + base_fp + base_fn)

    hardened_eval = evaluate_model_on_holdout(hardened_model, X_holdout, y_holdout, metadata_holdout)

    return {
        "baseline": {
            "accuracy": round(base_acc, 4),
            "f1": round(base_f1, 4),
            "tp": base_tp,
            "fp": base_fp,
            "tn": base_tn,
            "fn": base_fn,
        },
        "hardened": hardened_eval,
    }


# ============================================================================
# Phase 8: Comprehensive Locked Holdout Evaluation
# ============================================================================
def evaluate_onnx_model_on_locked_holdout(
    onnx_path: str,
    X_holdout: np.ndarray,
    y_holdout: np.ndarray,
    holdout_samples: List[Dict[str, Any]],
    thresholds: Sequence[float] = (0.30, 0.40, 0.50, 0.55, 0.60, 0.65, 0.70),
    human_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Evaluate an ONNX model against the locked human holdout across all specified thresholds.
    Uses openWakeWord streaming evaluation (predict_clip) if audio files are accessible.
    Calculates TP, TN, FP, FN, accuracy, precision, recall, F1, FPR, FNR,
    hard-negative FP count, general-negative FP count, and positive recall.
    """
    scores: np.ndarray
    used_streaming = False

    if human_dir is not None and Path(human_dir).exists():
        try:
            from openwakeword.model import Model
            oww = Model(wakeword_models=[onnx_path], inference_framework="onnx")
            computed_scores = []
            for s in holdout_samples:
                wav_p = str(Path(human_dir) / s["relative_path"])
                if os.path.exists(wav_p):
                    oww.reset()
                    preds = oww.predict_clip(wav_p, padding=0)
                    m = float(max([x[list(x.keys())[0]] for x in preds])) if preds else 0.0
                    computed_scores.append(m)
                else:
                    raise FileNotFoundError(f"Missing holdout wav: {wav_p}")
            scores = np.array(computed_scores)
            used_streaming = True
            logger.info("Executed streaming locked holdout evaluation for %s (%d clips)", onnx_path, len(scores))
        except Exception as exc:
            logger.warning("Streaming holdout evaluation unavailable (%s); using static embedding features.", exc)
            session = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
            in_name = session.get_inputs()[0].name
            out_name = session.get_outputs()[0].name
            scores = session.run([out_name], {in_name: X_holdout.astype(np.float32)})[0].flatten()
    else:
        session = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
        in_name = session.get_inputs()[0].name
        out_name = session.get_outputs()[0].name
        scores = session.run([out_name], {in_name: X_holdout.astype(np.float32)})[0].flatten()

    targets_bin = y_holdout.astype(int)

    results_by_thresh: Dict[float, Dict[str, Any]] = {}

    hard_neg_indices = [i for i, s in enumerate(holdout_samples) if s.get("category") == "HARD_NEGATIVE"]
    gen_neg_indices = [i for i, s in enumerate(holdout_samples) if s.get("category") == "GENERAL_NEGATIVE"]
    pos_indices = [i for i, s in enumerate(holdout_samples) if s.get("category") == "POSITIVE"]

    for thresh in thresholds:
        preds_bin = (scores >= thresh).astype(int)

        tp = int(np.sum((preds_bin == 1) & (targets_bin == 1)))
        fp = int(np.sum((preds_bin == 1) & (targets_bin == 0)))
        tn = int(np.sum((preds_bin == 0) & (targets_bin == 0)))
        fn = int(np.sum((preds_bin == 0) & (targets_bin == 1)))

        total = max(1, len(targets_bin))
        acc = (tp + tn) / total
        precision = tp / max(1, tp + fp)
        recall = tp / max(1, tp + fn)
        f1 = (2 * precision * recall) / max(1e-6, precision + recall)
        fpr = fp / max(1, fp + tn)
        fnr = fn / max(1, fn + tp)

        hn_fps = int(np.sum(preds_bin[hard_neg_indices] == 1))
        gn_fps = int(np.sum(preds_bin[gen_neg_indices] == 1))
        pos_detected = int(np.sum(preds_bin[pos_indices] == 1))

        results_by_thresh[thresh] = {
            "threshold": thresh,
            "tp": tp,
            "tn": tn,
            "fp": fp,
            "fn": fn,
            "accuracy": round(float(acc), 4),
            "precision": round(float(precision), 4),
            "recall": round(float(recall), 4),
            "f1": round(float(f1), 4),
            "fpr": round(float(fpr), 4),
            "fnr": round(float(fnr), 4),
            "positive_recall_count": pos_detected,
            "positive_total": len(pos_indices),
            "hard_neg_fp_count": hn_fps,
            "hard_neg_total": len(hard_neg_indices),
            "gen_neg_fp_count": gn_fps,
            "gen_neg_total": len(gen_neg_indices),
        }

    sample_details = []
    for i, s in enumerate(holdout_samples):
        sample_details.append({
            "filename": s.get("filename"),
            "phrase": s.get("phrase"),
            "category": s.get("category"),
            "condition": s.get("condition"),
            "target_label": int(s.get("target_label", 0)),
            "score": round(float(scores[i]), 4),
        })

    return {
        "model_path": onnx_path,
        "model_sha256": compute_file_sha256(onnx_path),
        "evaluation_mode": "streaming" if used_streaming else "static_embeddings",
        "thresholds": results_by_thresh,
        "sample_details": sample_details,
    }


def compare_models_on_locked_holdout(
    active_onnx_path: str,
    candidate_onnx_path: str,
    X_holdout: np.ndarray,
    y_holdout: np.ndarray,
    holdout_samples: List[Dict[str, Any]],
    thresholds: Sequence[float] = (0.30, 0.40, 0.50, 0.55, 0.60, 0.65, 0.70),
    human_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Side-by-side locked holdout evaluation comparing active model vs candidate model."""
    active_eval = evaluate_onnx_model_on_locked_holdout(
        active_onnx_path, X_holdout, y_holdout, holdout_samples, thresholds, human_dir=human_dir
    )
    candidate_eval = evaluate_onnx_model_on_locked_holdout(
        candidate_onnx_path, X_holdout, y_holdout, holdout_samples, thresholds, human_dir=human_dir
    )

    logger.info("==========================================================================================")
    logger.info("                   LOCKED HUMAN HOLDOUT EVALUATION COMPARISON")
    logger.info("==========================================================================================")
    logger.info(
        "%-6s | %-10s | %-16s | %-16s | %-10s | %-6s | %-6s",
        "Thresh", "Model", "Recall (TP/17)", "HardNeg FP(/12)", "GenNeg FP", "Acc", "F1"
    )
    logger.info("-" * 90)

    for t in thresholds:
        a_m = active_eval["thresholds"][t]
        c_m = candidate_eval["thresholds"][t]
        logger.info(
            "%-6.2f | %-10s | %2d/%-2d (%5.1f%%)   | %2d/%-2d (%5.1f%%)    | %2d/%-2d     | %5.3f  | %5.3f",
            t, "Active",
            a_m["positive_recall_count"], a_m["positive_total"], a_m["recall"] * 100,
            a_m["hard_neg_fp_count"], a_m["hard_neg_total"], (a_m["hard_neg_fp_count"] / a_m["hard_neg_total"]) * 100,
            a_m["gen_neg_fp_count"], a_m["gen_neg_total"],
            a_m["accuracy"], a_m["f1"]
        )
        logger.info(
            "%-6.2f | %-10s | %2d/%-2d (%5.1f%%)   | %2d/%-2d (%5.1f%%)    | %2d/%-2d     | %5.3f  | %5.3f",
            t, "Candidate",
            c_m["positive_recall_count"], c_m["positive_total"], c_m["recall"] * 100,
            c_m["hard_neg_fp_count"], c_m["hard_neg_total"], (c_m["hard_neg_fp_count"] / c_m["hard_neg_total"]) * 100,
            c_m["gen_neg_fp_count"], c_m["gen_neg_total"],
            c_m["accuracy"], c_m["f1"]
        )
        logger.info("-" * 90)

    return {
        "active": active_eval,
        "candidate": candidate_eval,
    }


# ============================================================================
# Model Export & Validation
# ============================================================================
def export_model_to_onnx(
    model: OpenWakeWordNet,
    output_onnx_path: str,
) -> Path:
    """Export PyTorch model to ONNX format compatible with openWakeWord."""
    output_path = Path(output_onnx_path)

    # Critical Safety Guard: NEVER overwrite active model
    if output_path.resolve() == Path(DEFAULT_ACTIVE_MODEL).resolve():
        raise PermissionError(
            f"CRITICAL SAFETY VIOLATION: Attempted to overwrite active production model at {DEFAULT_ACTIVE_MODEL}!"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    model.eval()
    model.to("cpu")
    dummy_input = torch.randn(1, 16, 96, dtype=torch.float32)

    logger.info("Exporting candidate model to ONNX at %s...", output_path)
    torch.onnx.export(
        model,
        dummy_input,
        str(output_path),
        opset_version=13,
        input_names=["input"],
        output_names=["output"],
        dynamo=False,
        dynamic_axes={"input": {0: "batch"}, "output": {0: "batch"}},
    )

    onnx_model = onnx.load(str(output_path))
    onnx.checker.check_model(onnx_model)
    logger.info("ONNX checker passed successfully!")

    session = ort.InferenceSession(str(output_path), providers=["CPUExecutionProvider"])
    in_name = session.get_inputs()[0].name
    out_name = session.get_outputs()[0].name
    test_out = session.run([out_name], {in_name: np.zeros((1, 16, 96), dtype=np.float32)})[0]
    logger.info("ONNX test inference output on silence: %s", test_out)

    return output_path


def verify_with_openwakeword_provider(onnx_path: Path) -> bool:
    """Verify that OpenWakeWordProvider loads and processes frames correctly."""
    logger.info("Verifying OpenWakeWordProvider integration for %s...", onnx_path)
    provider = OpenWakeWordProvider(
        wakeword_models=[str(onnx_path)],
        model_dir=str(onnx_path.parent),
        target_phrase="Hey EV",
        threshold=0.5,
    )

    assert provider.is_available is True
    from core.voice_capture import create_silence_frame
    for _ in range(3):
        res = provider.process_frame(create_silence_frame())
    assert res is None
    provider.close()
    logger.info("OpenWakeWordProvider verification PASSED!")
    return True


# ============================================================================
# Main Orchestration CLI
# ============================================================================
def main() -> None:
    parser = argparse.ArgumentParser(description="E.V. Task 014F-10 Controlled Human-Augmented Retraining")
    parser.add_argument("--epochs", type=int, default=45, help="Training epochs")
    parser.add_argument("--lr", type=float, default=8e-4, help="Learning rate")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size")
    parser.add_argument("--output-dir", type=str, default=DEFAULT_CANDIDATE_OUTPUT_DIR, help="Output directory")
    parser.add_argument("--model-name", type=str, default=DEFAULT_CANDIDATE_FILENAME, help="Output model filename")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--neg-weight", type=float, default=1.4, help="Negative penalty weight")

    args = parser.parse_args()

    start_time = time.monotonic()
    logger.info("=== E.V. TASK 014F-10: CONTROLLED HUMAN-AUGMENTED WAKE-WORD RETRAINING ===")

    # Phase 1: Verify Baseline Model Immutability before starting
    pre_sha = verify_active_model_hash()
    logger.info("Phase 1 Passed: Active model hey_ev.onnx verified SHA: %s", pre_sha)

    # Phase 2 & 3: Generate Dataset with strict holdout exclusion & leakage audit
    pipeline = WakeWordDatasetPipeline(random_seed=args.seed)
    metadata, clips, labels = pipeline.generate_hardened_audio_dataset(
        num_positive_base=48,
        augmentations_per_positive=8,
        augmentations_per_negative=6,
    )

    # Extract Features
    X_train, y_train, X_val, y_val, _, _ = pipeline.extract_features(clips, labels, metadata)

    # Phase 4 & 5: Train Candidate Model
    logger.info("Training speaker-adapted candidate model with deterministic seed %d...", args.seed)
    candidate_model, val_metrics = train_hey_ev_model(
        X_train,
        y_train,
        X_val,
        y_val,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
        neg_penalty_weight=args.neg_weight,
        random_seed=args.seed,
    )

    # Phase 6: Save Candidate Model (NEVER overwrites hey_ev.onnx)
    output_candidate_path = Path(args.output_dir) / args.model_name
    export_model_to_onnx(candidate_model, str(output_candidate_path))
    candidate_sha = compute_file_sha256(output_candidate_path)
    logger.info("Candidate exported to: %s (SHA256: %s)", output_candidate_path, candidate_sha)

    # Phase 8: Final Locked Holdout Evaluation
    logger.info("Executing Final Locked Human Holdout Benchmark...")
    X_holdout, y_holdout, holdout_samples = pipeline.extract_locked_holdout_features()

    comparison = compare_models_on_locked_holdout(
        DEFAULT_ACTIVE_MODEL,
        str(output_candidate_path),
        X_holdout,
        y_holdout,
        holdout_samples,
        human_dir=pipeline.human_dir,
    )

    # Phase 14: Verify OpenWakeWord runtime compatibility
    verify_with_openwakeword_provider(output_candidate_path)

    # Phase 16: Verify Active Model Immutability after task
    post_sha = verify_active_model_hash()
    assert post_sha == pre_sha == EXPECTED_ACTIVE_SHA
    logger.info("Phase 16 Passed: Active model hey_ev.onnx remains 100%% byte-for-byte identical (SHA: %s)", post_sha)

    # Save Reproducibility Record
    rep_record = {
        "task": "TASK_014F_10",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "active_baseline_model": {
            "path": DEFAULT_ACTIVE_MODEL,
            "sha256": post_sha,
        },
        "candidate_model": {
            "path": str(output_candidate_path),
            "sha256": candidate_sha,
            "architecture": "OpenWakeWordNet(16,96 -> 128 -> FCNBlock(128) -> Sigmoid)",
        },
        "holdout_manifest": {
            "path": str(pipeline.holdout_manifest_path),
            "samples_count": len(holdout_samples),
        },
        "training_config": {
            "seed": args.seed,
            "epochs": args.epochs,
            "batch_size": args.batch_size,
            "learning_rate": args.lr,
            "neg_penalty_weight": args.neg_weight,
            "optimizer": "AdamW",
            "weight_decay": 1e-4,
        },
        "dataset_summary": {
            "total_training_clips": len(X_train),
            "total_val_clips": len(X_val),
            "leakage_audit": pipeline.last_leakage_audit,
        },
        "development_val_metrics": val_metrics,
        "locked_holdout_comparison": comparison,
    }

    rep_path = Path(args.output_dir) / "reproducibility_record_014f10.json"
    with open(rep_path, "w", encoding="utf-8") as rf:
        json.dump(rep_record, rf, indent=2)
    logger.info("Reproducibility record saved to: %s", rep_path)

    elapsed = time.monotonic() - start_time
    logger.info("=== E.V. TASK 014F-10 COMPLETE in %.2f seconds ===", elapsed)


if __name__ == "__main__":
    main()
