"""
Streaming Holdout Evaluation for E.V. Wake-Word Models.
Compares models using the official openWakeWord streaming pipeline (predict_clip).
"""
import json
from pathlib import Path
import openwakeword
from openwakeword.model import Model

manifest_path = Path(r"D:\EV\models\wakeword\dataset\human\locked_human_holdout_manifest.json")
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
human_dir = manifest_path.parent

base_model_path = r"D:\EV\models\wakeword\hey_ev.onnx"
cand_model_path = r"D:\EV\models\wakeword\candidates\hey_ev_human_v2.onnx"

base_oww = Model(wakeword_models=[base_model_path], inference_framework="onnx")
cand_oww = Model(wakeword_models=[cand_model_path], inference_framework="onnx")

print("=" * 100)
print(f"{'Label':<6} | {'Category':<16} | {'Base Score':<10} | {'Cand Score':<10} | Phrase & Condition")
print("=" * 100)

base_scores = []
cand_scores = []

for s in manifest["samples"]:
    p = str(human_dir / s["relative_path"])
    base_oww.reset()
    b_preds = base_oww.predict_clip(p, padding=0)
    b_max = float(max([x[list(x.keys())[0]] for x in b_preds])) if b_preds else 0.0

    cand_oww.reset()
    c_preds = cand_oww.predict_clip(p, padding=0)
    c_max = float(max([x[list(x.keys())[0]] for x in c_preds])) if c_preds else 0.0

    base_scores.append(b_max)
    cand_scores.append(c_max)

    print(f"{s['target_label']:<6} | {s['category']:<16} | {b_max:<10.4f} | {c_max:<10.4f} | {s['phrase']} ({s.get('condition', '')})")

thresholds = [0.30, 0.40, 0.50, 0.55, 0.60, 0.65, 0.70]
print("\n" + "=" * 105)
print(f"{'Thresh':<8} | {'Model':<10} | {'Recall (TP/17)':<18} | {'HardNeg FP (/12)':<18} | {'GenNeg FP (/4)':<16} | {'Acc':<8} | {'F1':<8}")
print("=" * 105)

samples = manifest["samples"]
pos_idx = [i for i, s in enumerate(samples) if s["category"] == "POSITIVE"]
hn_idx = [i for i, s in enumerate(samples) if s["category"] == "HARD_NEGATIVE"]
gn_idx = [i for i, s in enumerate(samples) if s["category"] == "GENERAL_NEGATIVE"]

for th in thresholds:
    for name, scores in [("Active", base_scores), ("Candidate", cand_scores)]:
        tp = sum(1 for i in pos_idx if scores[i] >= th)
        fn = sum(1 for i in pos_idx if scores[i] < th)
        fp_hn = sum(1 for i in hn_idx if scores[i] >= th)
        fp_gn = sum(1 for i in gn_idx if scores[i] >= th)
        fp = fp_hn + fp_gn
        tn = (len(hn_idx) - fp_hn) + (len(gn_idx) - fp_gn)

        acc = (tp + tn) / len(samples)
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

        rec_str = f"{tp}/17 ({rec*100:.1f}%)"
        hn_str = f"{fp_hn}/12 ({fp_hn/12*100:.1f}%)"
        gn_str = f"{fp_gn}/4 ({fp_gn/4*100:.1f}%)"

        print(f"{th:<8.2f} | {name:<10} | {rec_str:<18} | {hn_str:<18} | {gn_str:<16} | {acc:<8.4f} | {f1:<8.4f}")
    print("-" * 105)
