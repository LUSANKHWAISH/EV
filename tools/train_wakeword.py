"""
Reproducible Hardened PyTorch Training Pipeline for "Hey EV" (Task 014F-5).

Trains an openWakeWord DNN model on the hardened, hard-negative mined dataset.
Performs:
  1. Train / Validation / Holdout 3-way evaluation.
  2. Weighted BCE loss penalizing hard-negative prefix false positives.
  3. Per-phrase hard-negative breakdown ("Hey Everyone", "Hey Evan", "Hey Stevie", etc.).
  4. Side-by-side comparison against baseline model (D:\\EV\\models\\wakeword\\hey_ev_v1_baseline.onnx).
  5. Export of validated hardened model to D:\\EV\\models\\wakeword\\hey_ev.onnx.
"""
from __future__ import annotations

import argparse
import copy
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
from tools.wakeword_dataset import SampleMetadata, WakeWordDatasetPipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ev.wakeword.training")

DEFAULT_MODEL_OUTPUT_DIR = r"D:\EV\models\wakeword"
DEFAULT_MODEL_FILENAME = "hey_ev.onnx"
DEFAULT_BASELINE_MODEL = r"D:\EV\models\wakeword\hey_ev_v1_baseline.onnx"


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
    epochs: int = 40,
    batch_size: int = 32,
    learning_rate: float = 8e-4,
    weight_decay: float = 1e-4,
    neg_penalty_weight: float = 1.3,
    random_seed: int = 42,
    device: str = "cpu",
) -> Tuple[OpenWakeWordNet, Dict[str, float]]:
    """
    Train OpenWakeWordNet with weighted negative loss to penalize confusable false alarms.
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
        # Loss: - [ y*log(p) + w_neg*(1-y)*log(1-p) ]
        loss = -(targets * torch.log(preds) + neg_penalty_weight * (1.0 - targets) * torch.log(1.0 - preds))
        return torch.mean(loss)

    optimizer = optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=weight_decay)

    best_val_loss = float("inf")
    best_val_f1 = 0.0
    best_weights = copy.deepcopy(model.state_dict())
    best_metrics: Dict[str, float] = {}

    logger.info("Starting hardened training loop for %d epochs (neg_weight=%.2f)...", epochs, neg_penalty_weight)

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

        # Validation
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
    logger.info("Hardened training complete. Best checkpoint at epoch %d: F1=%.3f, ValLoss=%.4f", best_metrics["epoch"], best_metrics["val_f1"], best_metrics["val_loss"])
    return model, best_metrics


# ============================================================================
# Benchmark & Hard-Negative Evaluation
# ============================================================================
def evaluate_model_on_holdout(
    model: OpenWakeWordNet,
    X_holdout: np.ndarray,
    y_holdout: np.ndarray,
    metadata_holdout: List[SampleMetadata],
    threshold: float = 0.50,
) -> Dict[str, Any]:
    """
    Evaluate model across all holdout samples and calculate per-phrase hard-negative breakdown.
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

    # Per-phrase breakdown
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
                # For positive, report recall
                rec = float(np.mean(phrase_preds == 1))
                phrase_breakdown[target_phrase] = {
                    "count": len(matching_idx),
                    "recall": round(rec, 3),
                    "max_score": round(max_s, 3),
                    "mean_score": round(mean_s, 3),
                }
            else:
                # For negative, report rejection rate
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
    """
    Side-by-side holdout comparison between baseline model and hardened model.
    """
    logger.info("Evaluating baseline model from %s on holdout set...", baseline_onnx_path)
    if not os.path.exists(baseline_onnx_path):
        logger.warning("Baseline model not found at %s. Skipping comparison.", baseline_onnx_path)
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

    logger.info("=== MODEL COMPARISON (HOLDOUT SET) ===")
    logger.info("Baseline: Accuracy=%.3f, F1=%.3f (TP=%d, FP=%d, FN=%d)", base_acc, base_f1, base_tp, base_fp, base_fn)
    logger.info("Hardened: Accuracy=%.3f, F1=%.3f (TP=%d, FP=%d, FN=%d)", hardened_eval["accuracy"], hardened_eval["f1"], hardened_eval["tp"], hardened_eval["fp"], hardened_eval["fn"])

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
# Model Export & Validation
# ============================================================================
def export_model_to_onnx(
    model: OpenWakeWordNet,
    output_onnx_path: str,
) -> Path:
    """Export PyTorch model to ONNX format compatible with openWakeWord."""
    output_path = Path(output_onnx_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    model.eval()
    model.to("cpu")
    dummy_input = torch.randn(1, 16, 96, dtype=torch.float32)

    logger.info("Exporting hardened model to ONNX at %s...", output_path)
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
    parser = argparse.ArgumentParser(description="E.V. Task 014F-5 Hardened Training Pipeline")
    parser.add_argument("--epochs", type=int, default=40, help="Training epochs")
    parser.add_argument("--lr", type=float, default=8e-4, help="Learning rate")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size")
    parser.add_argument("--output-dir", type=str, default=DEFAULT_MODEL_OUTPUT_DIR, help="Output directory")
    parser.add_argument("--model-name", type=str, default=DEFAULT_MODEL_FILENAME, help="Output model filename")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")

    args = parser.parse_args()

    start_time = time.monotonic()
    logger.info("=== E.V. TASK 014F-5: HARDENED 'HEY EV' TRAINING PIPELINE ===")

    # Step 1: Hardened Dataset Generation
    pipeline = WakeWordDatasetPipeline(random_seed=args.seed)
    metadata, clips, labels = pipeline.generate_hardened_audio_dataset(
        num_positive_base=48,
        augmentations_per_positive=8,
        augmentations_per_negative=6,
    )

    # Step 2: Feature Extraction (Train / Val / Holdout)
    X_train, y_train, X_val, y_val, X_holdout, y_holdout = pipeline.extract_features(clips, labels, metadata)
    meta_holdout = [m for m in metadata if m.split == "holdout"]

    # Step 3: Hardened Model Training
    hardened_model, val_metrics = train_hey_ev_model(
        X_train,
        y_train,
        X_val,
        y_val,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
        neg_penalty_weight=1.3,
        random_seed=args.seed,
    )

    # Step 4: Comparison with Baseline on Unbiased Holdout Set
    comparison = compare_with_baseline_model(
        DEFAULT_BASELINE_MODEL,
        hardened_model,
        X_holdout,
        y_holdout,
        meta_holdout,
    )

    # Step 5: Export Hardened Model to ONNX
    output_path = Path(args.output_dir) / args.model_name
    export_model_to_onnx(hardened_model, str(output_path))

    # Step 6: Verify OpenWakeWord Provider
    verify_with_openwakeword_provider(output_path)

    elapsed = time.monotonic() - start_time
    logger.info("=== HARDENED TRAINING & EXPORT COMPLETED in %.2f seconds ===", elapsed)
    logger.info("Exported Model: %s (Size: %d bytes)", output_path, output_path.stat().st_size)
    logger.info("Validation Metrics: %s", val_metrics)
    logger.info("Holdout Breakdown: %s", comparison.get("hardened", {}).get("phrase_breakdown", {}))


if __name__ == "__main__":
    main()
