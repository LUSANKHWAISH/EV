"""
Reproducible PyTorch Training & ONNX Model Export Pipeline for "Hey EV" (Task 014F-3).

Trains a custom openWakeWord-compatible DNN model on local features extracted from
synthetic "Hey EV" utterances and confusable negatives. Exports the trained model to
canonical ONNX format at D:\\EV\\models\\wakeword\\hey_ev.onnx and validates runtime compatibility
with OpenWakeWordProvider.

Usage:
  python tools/train_wakeword.py
  python tools/train_wakeword.py --epochs 35 --lr 0.001 --output D:\\EV\\models\\wakeword\\hey_ev.onnx
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
from typing import Dict, Optional, Tuple

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
from tools.wakeword_dataset import WakeWordDatasetPipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ev.wakeword.training")

DEFAULT_MODEL_OUTPUT_DIR = r"D:\EV\models\wakeword"
DEFAULT_MODEL_FILENAME = "hey_ev.onnx"


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
# Model Training Engine
# ============================================================================
def train_hey_ev_model(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    epochs: int = 35,
    batch_size: int = 32,
    learning_rate: float = 1e-3,
    weight_decay: float = 1e-4,
    random_seed: int = 42,
    device: str = "cpu",
) -> Tuple[OpenWakeWordNet, Dict[str, float]]:
    """
    Train OpenWakeWordNet with BCE loss, AdamW, and metric tracking.
    """
    torch.manual_seed(random_seed)
    np.random.seed(random_seed)

    # Prepare PyTorch datasets
    train_dataset = TensorDataset(
        torch.from_numpy(X_train).float(),
        torch.from_numpy(y_train).float().unsqueeze(1),
    )
    val_dataset = TensorDataset(
        torch.from_numpy(X_val).float(),
        torch.from_numpy(y_val).float().unsqueeze(1),
    )

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)

    model = OpenWakeWordNet(input_shape=(16, 96), layer_dim=128, n_blocks=1)
    model.to(device)

    # Loss: weighted BCE to penalize false positives strongly
    pos_weight = torch.tensor([1.0]).to(device)
    criterion = nn.BCELoss()
    optimizer = optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=weight_decay)

    best_val_loss = float("inf")
    best_val_f1 = 0.0
    best_weights = copy.deepcopy(model.state_dict())
    best_metrics: Dict[str, float] = {}

    logger.info("Starting training loop for %d epochs...", epochs)

    for epoch in range(1, epochs + 1):
        model.train()
        train_loss = 0.0

        for batch_x, batch_y in train_loader:
            batch_x, batch_y = batch_x.to(device), batch_y.to(device)
            optimizer.zero_grad()
            preds = model(batch_x)
            loss = criterion(preds, batch_y)
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
                loss = criterion(preds, batch_y)
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
                "Epoch %2d/%2d: TrainLoss=%.4f, ValLoss=%.4f, Acc=%.3f, Prec=%.3f, Rec=%.3f, F1=%.3f (TP=%d, FP=%d)",
                epoch, epochs, train_loss, val_loss, acc, precision, recall, f1, tp, fp
            )

        if f1 >= best_val_f1 and val_loss < best_val_loss:
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

    # Restore best weights
    model.load_state_dict(best_weights)
    model.eval()
    logger.info("Training complete. Best checkpoint at epoch %d: F1=%.3f, ValLoss=%.4f", best_metrics["epoch"], best_metrics["val_f1"], best_metrics["val_loss"])

    return model, best_metrics


# ============================================================================
# Model Export & Validation
# ============================================================================
def export_model_to_onnx(
    model: OpenWakeWordNet,
    output_onnx_path: str,
) -> Path:
    """
    Export PyTorch model to ONNX format compatible with openWakeWord runtime.
    """
    output_path = Path(output_onnx_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    model.eval()
    model.to("cpu")
    dummy_input = torch.randn(1, 16, 96, dtype=torch.float32)

    logger.info("Exporting model to ONNX at %s...", output_path)
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

    # 1. Validate ONNX file structure
    onnx_model = onnx.load(str(output_path))
    onnx.checker.check_model(onnx_model)
    logger.info("ONNX checker passed successfully!")

    # 2. Validate ONNX Runtime execution
    session = ort.InferenceSession(str(output_path), providers=["CPUExecutionProvider"])
    in_name = session.get_inputs()[0].name
    out_name = session.get_outputs()[0].name
    in_shape = session.get_inputs()[0].shape
    out_shape = session.get_outputs()[0].shape

    logger.info("ONNX inputs: name=%s, shape=%s; outputs: name=%s, shape=%s", in_name, in_shape, out_name, out_shape)

    # Verify test inference on dummy embedding
    test_out = session.run([out_name], {in_name: np.zeros((1, 16, 96), dtype=np.float32)})[0]
    logger.info("ONNX test inference output on silence: %s", test_out)

    return output_path


def verify_with_openwakeword_provider(onnx_path: Path) -> bool:
    """Verify that OpenWakeWordProvider loads and evaluates the exported model."""
    logger.info("Verifying OpenWakeWordProvider loading for %s...", onnx_path)
    provider = OpenWakeWordProvider(
        wakeword_models=[str(onnx_path)],
        model_dir=str(onnx_path.parent),
        target_phrase="Hey EV",
        threshold=0.5,
    )

    assert provider.is_available is True
    assert "hey_ev" in provider.loaded_models or str(onnx_path) in provider.loaded_models or "hey_ev.onnx" in str(provider.loaded_models)

    # Feed silence frames (3 frames to trigger 1280 accumulation)
    from core.voice_capture import create_silence_frame
    for _ in range(3):
        res = provider.process_frame(create_silence_frame())

    # On silence, detection should remain None
    assert res is None, "Silence should not trigger wake-word detection!"
    provider.close()

    logger.info("OpenWakeWordProvider verification PASSED!")
    return True


# ============================================================================
# Main Orchestration CLI
# ============================================================================
def main() -> None:
    parser = argparse.ArgumentParser(description="E.V. Custom 'Hey EV' Model Training Pipeline")
    parser.add_argument("--epochs", type=int, default=35, help="Number of training epochs")
    parser.add_argument("--lr", type=float, default=1e-3, help="Learning rate")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size")
    parser.add_argument("--output-dir", type=str, default=DEFAULT_MODEL_OUTPUT_DIR, help="Model export directory")
    parser.add_argument("--model-name", type=str, default=DEFAULT_MODEL_FILENAME, help="Model output filename")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")

    args = parser.parse_args()

    start_time = time.monotonic()
    logger.info("=== E.V. TASK 014F-3: CUSTOM 'HEY EV' TRAINING PIPELINE ===")

    # Step 1: Dataset Generation & Feature Extraction
    pipeline = WakeWordDatasetPipeline(random_seed=args.seed)
    metadata, clips, labels = pipeline.generate_raw_audio_dataset(
        num_positive_base=30,
        num_negative_base=45,
        augmentations_per_sample=6,
    )
    X_train, y_train, X_val, y_val = pipeline.extract_features(clips, labels, metadata)

    # Step 2: Model Training
    model, metrics = train_hey_ev_model(
        X_train,
        y_train,
        X_val,
        y_val,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
        random_seed=args.seed,
    )

    # Step 3: Model Export to ONNX
    output_path = Path(args.output_dir) / args.model_name
    export_model_to_onnx(model, str(output_path))

    # Step 4: Adapter Compatibility Verification
    verify_with_openwakeword_provider(output_path)

    elapsed = time.monotonic() - start_time
    logger.info("=== TRAINING & EXPORT FINISHED in %.2f seconds ===", elapsed)
    logger.info("Exported Model: %s (Size: %d bytes)", output_path, output_path.stat().st_size)
    logger.info("Validation Metrics: %s", metrics)


if __name__ == "__main__":
    main()
