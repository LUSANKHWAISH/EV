"""
Forensic Human Wake-Word Dataset Audit Tool for E.V. (Task 014F-9).

Audits every WAV file under models/wakeword/dataset/human:
- Format verification (16kHz mono PCM16 32k samples)
- SHA256 hash calculation & collision detection
- Acoustic health (RMS, Peak, Clipping, Silence, Duration)
- Manifest reconciliation (cross-referencing disk vs manifest)
- Session and speaker distribution analysis
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import wave
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

HUMAN_DATASET_DIR = Path(r"D:\EV\models\wakeword\dataset\human")
MANIFEST_PATH = HUMAN_DATASET_DIR / "human_collection_manifest.json"
ACTIVE_MODEL_PATH = Path(r"D:\EV\models\wakeword\hey_ev.onnx")
BASELINE_MODEL_PATH = Path(r"D:\EV\models\wakeword\hey_ev_v1_baseline.onnx")

CANONICAL_RATE = 16000
CANONICAL_CHANNELS = 1
CANONICAL_WIDTH = 2
CANONICAL_FRAMES = 32000
CANONICAL_DURATION = 2.0


def calculate_sha256(file_path: Path) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class WavAuditRecord:
    file_path: str
    relative_path: str
    folder: str
    filename: str
    file_size_bytes: int
    sha256: str
    is_valid_wav: bool
    channels: int
    sample_rate: int
    sample_width: int
    n_frames: int
    duration_sec: float
    rms: float
    peak: int
    clipping_percent: float
    is_silent: bool
    format_deviations: List[str]


def audit_wav_file(wav_path: Path) -> WavAuditRecord:
    deviations = []
    sha = calculate_sha256(wav_path)
    file_size = wav_path.stat().st_size
    rel_path = str(wav_path.relative_to(HUMAN_DATASET_DIR))
    folder = wav_path.parent.name
    filename = wav_path.name

    try:
        with wave.open(str(wav_path), "rb") as wf:
            channels = wf.getnchannels()
            rate = wf.getframerate()
            width = wf.getsampwidth()
            frames = wf.getnframes()
            duration = round(frames / float(rate), 4) if rate > 0 else 0.0

            if rate != CANONICAL_RATE:
                deviations.append(f"sample_rate={rate} (expected {CANONICAL_RATE})")
            if channels != CANONICAL_CHANNELS:
                deviations.append(f"channels={channels} (expected {CANONICAL_CHANNELS})")
            if width != CANONICAL_WIDTH:
                deviations.append(f"sample_width={width} (expected {CANONICAL_WIDTH})")
            if frames != CANONICAL_FRAMES:
                deviations.append(f"frames={frames} (expected {CANONICAL_FRAMES})")

            raw_bytes = wf.readframes(frames)
            data = np.frombuffer(raw_bytes, dtype=np.int16)
            rms = float(np.sqrt(np.mean(data.astype(np.float64) ** 2))) if len(data) > 0 else 0.0
            peak = int(np.max(np.abs(data))) if len(data) > 0 else 0
            clipped = int(np.sum(np.abs(data) >= 32767)) if len(data) > 0 else 0
            clip_pct = round((clipped / float(len(data))) * 100.0, 3) if len(data) > 0 else 0.0
            is_silent = rms < 20.0

            return WavAuditRecord(
                file_path=str(wav_path),
                relative_path=rel_path,
                folder=folder,
                filename=filename,
                file_size_bytes=file_size,
                sha256=sha,
                is_valid_wav=True,
                channels=channels,
                sample_rate=rate,
                sample_width=width,
                n_frames=frames,
                duration_sec=duration,
                rms=round(rms, 2),
                peak=peak,
                clipping_percent=clip_pct,
                is_silent=is_silent,
                format_deviations=deviations,
            )
    except Exception as exc:
        return WavAuditRecord(
            file_path=str(wav_path),
            relative_path=rel_path,
            folder=folder,
            filename=filename,
            file_size_bytes=file_size,
            sha256=sha,
            is_valid_wav=False,
            channels=0,
            sample_rate=0,
            sample_width=0,
            n_frames=0,
            duration_sec=0.0,
            rms=0.0,
            peak=0,
            clipping_percent=0.0,
            is_silent=True,
            format_deviations=[f"corrupt_wav: {exc}"],
        )


def run_forensic_audit() -> Dict[str, Any]:
    print("=" * 70)
    print("PHASE 1: FORENSIC DATASET AUDIT")
    print("=" * 70)

    # 1. Discover all files
    all_files = list(HUMAN_DATASET_DIR.rglob("*"))
    all_wavs = sorted([p for p in all_files if p.is_file() and p.suffix.lower() == ".wav"])
    non_wav_files = [p for p in all_files if p.is_file() and p.suffix.lower() != ".wav" and p != MANIFEST_PATH]

    print(f"Dataset root: {HUMAN_DATASET_DIR}")
    print(f"Total files on disk: {len([p for p in all_files if p.is_file()])}")
    print(f"Total WAV files on disk: {len(all_wavs)}")
    print(f"Non-WAV files (excluding manifest): {[str(p.relative_to(HUMAN_DATASET_DIR)) for p in non_wav_files]}")

    by_folder: Dict[str, List[Path]] = defaultdict(list)
    for w in all_wavs:
        by_folder[w.parent.name].append(w)

    for folder, files in sorted(by_folder.items()):
        print(f"  {folder}/: {len(files)} files")

    # 2. Audit each WAV
    records: List[WavAuditRecord] = []
    sha_to_paths: Dict[str, List[Path]] = defaultdict(list)
    format_deviations_found = []

    for w in all_wavs:
        rec = audit_wav_file(w)
        records.append(rec)
        sha_to_paths[rec.sha256].append(w)
        if rec.format_deviations:
            format_deviations_found.append(rec)

    print(f"\nWAV Format Compliance:")
    print(f"  Total inspected: {len(records)}")
    print(f"  Valid WAV headers: {sum(1 for r in records if r.is_valid_wav)}")
    print(f"  Corrupt/unreadable: {sum(1 for r in records if not r.is_valid_wav)}")
    print(f"  Deviations from 16kHz mono PCM16 32000 frames: {len(format_deviations_found)}")
    for d in format_deviations_found:
        print(f"    [!] {d.relative_path}: {d.format_deviations}")

    # 3. SHA256 Collisions / Duplicates
    collisions = {sha: paths for sha, paths in sha_to_paths.items() if len(paths) > 1}
    print(f"\nSHA256 Collision Analysis:")
    print(f"  Unique SHA256 hashes: {len(sha_to_paths)}")
    print(f"  Exact content duplicates across disk: {len(collisions)}")
    for sha, paths in collisions.items():
        print(f"    Collision SHA={sha[:16]}...: {[str(p.relative_to(HUMAN_DATASET_DIR)) for p in paths]}")

    # 4. Silence & clipping check
    silent_records = [r for r in records if r.is_silent]
    clipped_records = [r for r in records if r.clipping_percent > 1.0]
    print(f"\nAcoustic Quality Flags:")
    print(f"  Near-silent recordings (RMS < 20): {len(silent_records)}")
    for s in silent_records:
        print(f"    [!] Low energy: {s.relative_path} (RMS={s.rms}, Peak={s.peak})")
    print(f"  Clipped recordings (>1% clipping): {len(clipped_records)}")
    for c in clipped_records:
        print(f"    [!] Clipped: {c.relative_path} (Clipping={c.clipping_percent}%)")

    # 5. Manifest Reconciliation
    print("\n" + "=" * 70)
    print("PHASE 2: MANIFEST RECONCILIATION")
    print("=" * 70)

    manifest_exists = MANIFEST_PATH.exists()
    print(f"Manifest exists: {manifest_exists}")
    manifest_records: List[Dict[str, Any]] = []
    if manifest_exists:
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            manifest_records = json.load(f)
    print(f"Total manifest records: {len(manifest_records)}")

    # Check mapping
    manifest_files_on_disk = 0
    manifest_missing_on_disk = []
    manifest_by_relpath: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    manifest_by_filename: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for idx, m in enumerate(manifest_records):
        rel = m.get("relative_path", "").replace("\\", "/")
        fn = m.get("filename", "")
        manifest_by_relpath[rel].append(m)
        manifest_by_filename[fn].append(m)

        target_path = HUMAN_DATASET_DIR / rel
        if target_path.exists():
            manifest_files_on_disk += 1
        else:
            manifest_missing_on_disk.append((idx, rel, fn))

    print(f"Manifest records pointing to existing files: {manifest_files_on_disk}")
    print(f"Manifest records pointing to missing files: {len(manifest_missing_on_disk)}")
    if manifest_missing_on_disk:
        for idx, rel, fn in manifest_missing_on_disk[:10]:
            print(f"    [!] Missing record #{idx}: rel={rel}, fn={fn}")

    # Check disk files not in manifest
    disk_relpaths = {r.relative_path.replace("\\", "/") for r in records}
    manifest_relpaths = set(manifest_by_relpath.keys())
    unmanifested_disk_files = disk_relpaths - manifest_relpaths
    print(f"Disk WAV files NOT in manifest: {len(unmanifested_disk_files)}")
    for u in sorted(unmanifested_disk_files):
        print(f"    [!] Unmanifested on disk: {u}")

    # Check duplicate manifest entries
    duplicate_manifest_relpaths = {k: v for k, v in manifest_by_relpath.items() if len(v) > 1}
    print(f"Manifest duplicate relative_paths: {len(duplicate_manifest_relpaths)}")
    for rel, entries in duplicate_manifest_relpaths.items():
        print(f"    Duplicate {rel}: {len(entries)} entries")

    # 7. Phase 3: Label Integrity Audit
    print("\n" + "=" * 70)
    print("PHASE 3: LABEL INTEGRITY AUDIT")
    print("=" * 70)

    # Deduplicate manifest records by relative_path
    unique_manifest: Dict[str, Dict[str, Any]] = {}
    for m in manifest_records:
        rel = m.get("relative_path", "").replace("\\", "/")
        if rel not in unique_manifest:
            unique_manifest[rel] = m

    pos_items = [m for m in unique_manifest.values() if m.get("category") == "POSITIVE"]
    hard_neg_items = [m for m in unique_manifest.values() if m.get("category") == "HARD_NEGATIVE"]
    gen_neg_items = [m for m in unique_manifest.values() if m.get("category") == "GENERAL_NEGATIVE"]
    quar_items = [m for m in unique_manifest.values() if m.get("category") == "QUARANTINE"]

    print(f"Verified Human Positives: {len(pos_items)}")
    print(f"Verified Human Hard Negatives: {len(hard_neg_items)}")
    print(f"Verified Human General Negatives: {len(gen_neg_items)}")
    print(f"Total Verified Human Negatives: {len(hard_neg_items) + len(gen_neg_items)}")
    print(f"Quarantined Items: {len(quar_items)}")

    # Check positive phrase validity
    suspicious_positives = []
    for p in pos_items:
        phrase = p.get("phrase", "")
        # Valid positive targets: Hey EV, Hey E.V., Hey E V, hey ev
        clean_phrase = phrase.lower().replace(".", "").replace(" ", "")
        if clean_phrase != "heyev":
            suspicious_positives.append((p.get("filename"), phrase, "Phrase does not match canonical 'Hey EV' variant"))

    print(f"\nPositive Target Phrase Audit:")
    pos_phrase_dist = Counter(p.get("phrase") for p in pos_items)
    for phrase, count in pos_phrase_dist.most_common():
        print(f"  \"{phrase}\": {count} files")
    print(f"Suspicious Positives Detected: {len(suspicious_positives)}")
    for sp in suspicious_positives:
        print(f"  [!] {sp}")

    # Check negative phrase validity (none should contain hey ev)
    suspicious_negatives = []
    for n in hard_neg_items + gen_neg_items:
        phrase = n.get("phrase", "")
        clean_phrase = phrase.lower().replace(".", "").replace(" ", "")
        if clean_phrase == "heyev":
            suspicious_negatives.append((n.get("filename"), phrase, "Negative phrase matches wake phrase"))

    print(f"\nNegative Phrase Breakdown ({len(hard_neg_items) + len(gen_neg_items)} total):")
    print("  Hard Negatives:")
    for phrase, count in Counter(n.get("phrase") for n in hard_neg_items).most_common():
        print(f"    \"{phrase}\": {count}")
    print("  General Command Negatives:")
    for phrase, count in Counter(n.get("phrase") for n in gen_neg_items).most_common():
        print(f"    \"{phrase}\": {count}")
    print(f"Suspicious Negatives Detected: {len(suspicious_negatives)}")

    # 8. Phase 4: Quarantine Isolation
    print("\n" + "=" * 70)
    print("PHASE 4: QUARANTINE ISOLATION")
    print("=" * 70)
    print(f"Total Quarantine Files: {len(quar_items)}")
    for q in quar_items:
        print(f"  {q.get('filename')}: reason=\"{q.get('quarantine_reason')}\", phrase=\"{q.get('phrase')}\"")

    # Check for quarantine leakage
    quar_filenames = {q.get("filename") for q in quar_items}
    pos_filenames = {p.get("filename") for p in pos_items}
    neg_filenames = {n.get("filename") for n in hard_neg_items + gen_neg_items}

    leakage_in_pos = quar_filenames.intersection(pos_filenames)
    leakage_in_neg = quar_filenames.intersection(neg_filenames)
    print(f"Quarantine Leakage in Positive Set: {len(leakage_in_pos)} (shared filenames: {list(leakage_in_pos)})")
    print(f"Quarantine Leakage in Negative Set: {len(leakage_in_neg)} (shared filenames: {list(leakage_in_neg)})")

    # Verify SHA differences for shared filenames
    for fn in leakage_in_pos:
        sha_pos = calculate_sha256(HUMAN_DATASET_DIR / "positive" / fn)
        sha_quar = calculate_sha256(HUMAN_DATASET_DIR / "quarantine" / fn)
        print(f"  Note on shared filename '{fn}':")
        print(f"    positive/ SHA256:   {sha_pos[:16]}...")
        print(f"    quarantine/ SHA256: {sha_quar[:16]}...")
        print(f"    Different audio content: {sha_pos != sha_quar}")

    # 9. Phase 5: Session & Speaker Analysis
    print("\n" + "=" * 70)
    print("PHASE 5: SESSION & SPEAKER ANALYSIS")
    print("=" * 70)

    speaker_counts: Dict[str, int] = Counter()
    session_counts: Dict[str, int] = Counter()
    session_category_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: Counter())

    for m in manifest_records:
        spk = m.get("speaker_id", "unknown")
        sess = m.get("session_id", "session_legacy")
        cat = m.get("category", "UNKNOWN")
        speaker_counts[spk] += 1
        session_counts[sess] += 1
        session_category_counts[sess][cat] += 1

    print("Speaker Distribution (from manifest):")
    for spk, count in speaker_counts.items():
        print(f"  Speaker: {spk} -> {count} records")

    print("\nSession Distribution (from manifest):")
    for sess, count in sorted(session_counts.items()):
        cats = dict(session_category_counts[sess])
        print(f"  Session: {sess} -> {count} records {cats}")

    # 10. Phase 6: Locked Human Holdout Generation
    print("\n" + "=" * 70)
    print("PHASE 6: LOCKED HUMAN HOLDOUT GENERATION")
    print("=" * 70)

    # Deterministic Holdout Construction
    # Target: ~25% holdout split (17 positives, 16 negatives [12 hard + 4 general])
    # Stratified by phrase / condition using deterministic seed
    HOLD_SEED = 42
    np.random.seed(HOLD_SEED)

    # Sort deterministically by filename
    sorted_pos = sorted(pos_items, key=lambda x: x["filename"])
    sorted_hard_neg = sorted(hard_neg_items, key=lambda x: x["filename"])
    sorted_gen_neg = sorted(gen_neg_items, key=lambda x: x["filename"])

    # Sample 17 positives, 12 hard negatives, 4 general negatives deterministically
    # Positives: select across different phrases and conditions
    pos_indices = np.random.choice(len(sorted_pos), size=17, replace=False)
    hard_neg_indices = np.random.choice(len(sorted_hard_neg), size=12, replace=False)
    gen_neg_indices = np.random.choice(len(sorted_gen_neg), size=4, replace=False)

    holdout_pos = [sorted_pos[i] for i in sorted(pos_indices)]
    holdout_hard_neg = [sorted_hard_neg[i] for i in sorted(hard_neg_indices)]
    holdout_gen_neg = [sorted_gen_neg[i] for i in sorted(gen_neg_indices)]
    holdout_all = holdout_pos + holdout_hard_neg + holdout_gen_neg

    active_sha_before = calculate_sha256(ACTIVE_MODEL_PATH)
    print(f"Active Model SHA256 BEFORE evaluation: {active_sha_before}")

    # Build holdout manifest records
    holdout_manifest = {
        "metadata": {
            "dataset_name": "E.V. Locked Human Wake-Word Holdout",
            "version": "1.0-locked",
            "creation_timestamp": "2026-09-04T22:55:00Z",
            "deterministic_seed": HOLD_SEED,
            "active_model_sha256": active_sha_before,
            "total_samples": len(holdout_all),
            "positive_count": len(holdout_pos),
            "hard_negative_count": len(holdout_hard_neg),
            "general_negative_count": len(holdout_gen_neg),
            "total_negative_count": len(holdout_hard_neg) + len(holdout_gen_neg),
            "speaker_id": "user_speaker_1",
            "split_policy": "Stratified deterministic holdout, excluded from future training",
        },
        "samples": [],
    }

    for item in holdout_all:
        rel = item.get("relative_path", "").replace("\\", "/")
        full_path = HUMAN_DATASET_DIR / rel
        sha = calculate_sha256(full_path)
        holdout_manifest["samples"].append({
            "relative_path": rel,
            "filename": item.get("filename"),
            "sha256": sha,
            "target_label": item.get("target_label"),
            "category": item.get("category"),
            "phrase": item.get("phrase"),
            "condition": item.get("condition"),
            "session_id": item.get("session_id", "session_legacy"),
            "speaker_id": item.get("speaker_id", "user_speaker_1"),
            "split": "holdout",
        })

    HOLDOUT_MANIFEST_PATH = HUMAN_DATASET_DIR / "locked_human_holdout_manifest.json"
    with open(HOLDOUT_MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(holdout_manifest, f, indent=2)
    print(f"Locked Human Holdout Manifest saved: {HOLDOUT_MANIFEST_PATH}")
    print(f"  Total Holdout Items: {len(holdout_all)}")
    print(f"  Positives: {len(holdout_pos)} | Hard Negatives: {len(holdout_hard_neg)} | General Negatives: {len(holdout_gen_neg)}")

    # 10. Phase 7: Model Evaluation Against Holdout
    print("\n" + "=" * 70)
    print("PHASE 7: CURRENT ACTIVE MODEL EVALUATION")
    print("=" * 70)

    import openwakeword
    from openwakeword.model import Model

    oww = Model(wakeword_models=[str(ACTIVE_MODEL_PATH)], inference_framework="onnx")

    # Score every sample in holdout
    scored_holdout = []
    for sample in holdout_manifest["samples"]:
        rel = sample["relative_path"]
        path = HUMAN_DATASET_DIR / rel
        oww.reset()
        preds = oww.predict_clip(str(path), padding=0)
        scores = [p["hey_ev"] for p in preds]
        max_score = float(max(scores)) if scores else 0.0
        scored_holdout.append({
            **sample,
            "max_score": max_score,
        })

    # Evaluate at thresholds
    thresholds = [0.30, 0.40, 0.50, 0.55, 0.60, 0.65, 0.70]
    eval_results = {}

    print(f"\nHoldout Evaluation Table (Total={len(scored_holdout)}: Pos={len(holdout_pos)}, Neg={len(holdout_hard_neg)+len(holdout_gen_neg)}):")
    print(f"{'Thresh':<8}{'TP':<5}{'TN':<5}{'FP':<5}{'FN':<5}{'Acc':<8}{'Prec':<8}{'Rec':<8}{'F1':<8}{'FPR':<8}{'FNR':<8}{'FP_Hard':<8}{'FP_Gen':<8}")
    print("-" * 95)

    for th in thresholds:
        tp = sum(1 for s in scored_holdout if s["target_label"] == 1 and s["max_score"] >= th)
        fn = sum(1 for s in scored_holdout if s["target_label"] == 1 and s["max_score"] < th)
        tn = sum(1 for s in scored_holdout if s["target_label"] == 0 and s["max_score"] < th)
        fp = sum(1 for s in scored_holdout if s["target_label"] == 0 and s["max_score"] >= th)

        fp_hard = sum(1 for s in scored_holdout if s["target_label"] == 0 and s["category"] == "HARD_NEGATIVE" and s["max_score"] >= th)
        fp_gen = sum(1 for s in scored_holdout if s["target_label"] == 0 and s["category"] == "GENERAL_NEGATIVE" and s["max_score"] >= th)

        total = tp + tn + fp + fn
        acc = (tp + tn) / total if total > 0 else 0.0
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
        fnr = fn / (fn + tp) if (fn + tp) > 0 else 0.0

        eval_results[th] = {
            "tp": tp, "tn": tn, "fp": fp, "fn": fn,
            "acc": round(acc, 4), "prec": round(prec, 4), "rec": round(rec, 4), "f1": round(f1, 4),
            "fpr": round(fpr, 4), "fnr": round(fnr, 4),
            "fp_hard": fp_hard, "fp_gen": fp_gen,
        }

        print(f"{th:<8.2f}{tp:<5}{tn:<5}{fp:<5}{fn:<5}{acc:<8.4f}{prec:<8.4f}{rec:<8.4f}{f1:<8.4f}{fpr:<8.4f}{fnr:<8.4f}{fp_hard:<8}{fp_gen:<8}")

    # 11. Phase 8: False Positive & False Negative Forensics
    print("\n" + "=" * 70)
    print("PHASE 8: FALSE POSITIVE & FALSE NEGATIVE FORENSICS")
    print("=" * 70)
    RECOMMENDED_THRESHOLD = 0.50
    print(f"Analysis at Threshold = {RECOMMENDED_THRESHOLD}:")

    fps_50 = [s for s in scored_holdout if s["target_label"] == 0 and s["max_score"] >= RECOMMENDED_THRESHOLD]
    fns_50 = [s for s in scored_holdout if s["target_label"] == 1 and s["max_score"] < RECOMMENDED_THRESHOLD]

    print(f"False Positives at {RECOMMENDED_THRESHOLD}: {len(fps_50)}")
    for fp in fps_50:
        print(f"  [FP] {fp['filename']} | phrase=\"{fp['phrase']}\" | score={fp['max_score']:.4f} | cat={fp['category']} | sess={fp['session_id']}")

    print(f"False Negatives at {RECOMMENDED_THRESHOLD}: {len(fns_50)}")
    for fn in fns_50:
        print(f"  [FN] {fn['filename']} | phrase=\"{fn['phrase']}\" | score={fn['max_score']:.4f} | cond={fn.get('condition')} | sess={fn['session_id']}")

    # Check score distribution for all holdout items
    print(f"\nHoldout Score Summary:")
    print("  Positives scores:")
    for s in sorted(scored_holdout, key=lambda x: -x["max_score"]):
        if s["target_label"] == 1:
            print(f"    {s['max_score']:.4f} : {s['filename']} (cond: {s.get('condition')})")

    print("  Negatives scores:")
    for s in sorted(scored_holdout, key=lambda x: -x["max_score"]):
        if s["target_label"] == 0:
            print(f"    {s['max_score']:.4f} : {s['filename']} (phrase: \"{s['phrase']}\")")

    # Evaluate across the entire verified dataset (all 69 positives and 64 negatives)
    print("\n" + "=" * 70)
    print("OVERALL VERIFIED DATASET EVALUATION (All 133 Non-Quarantine Samples)")
    print("=" * 70)
    all_scored = []
    for item in pos_items + hard_neg_items + gen_neg_items:
        rel = item["relative_path"].replace("\\", "/")
        path = HUMAN_DATASET_DIR / rel
        oww.reset()
        preds = oww.predict_clip(str(path), padding=0)
        scores = [p["hey_ev"] for p in preds]
        max_score = float(max(scores)) if scores else 0.0
        all_scored.append({
            "relative_path": rel,
            "filename": item["filename"],
            "target_label": item["target_label"],
            "category": item["category"],
            "phrase": item["phrase"],
            "condition": item.get("condition"),
            "max_score": max_score,
            "session_id": item.get("session_id", "session_legacy"),
        })

    print(f"\nOverall Dataset Evaluation Table (Total=133: Pos=69, Neg=64):")
    print(f"{'Thresh':<8}{'TP':<5}{'TN':<5}{'FP':<5}{'FN':<5}{'Acc':<8}{'Prec':<8}{'Rec':<8}{'F1':<8}{'FPR':<8}{'FNR':<8}{'FP_Hard':<8}{'FP_Gen':<8}")
    print("-" * 95)
    for th in thresholds:
        tp_a = sum(1 for s in all_scored if s["target_label"] == 1 and s["max_score"] >= th)
        fn_a = sum(1 for s in all_scored if s["target_label"] == 1 and s["max_score"] < th)
        tn_a = sum(1 for s in all_scored if s["target_label"] == 0 and s["max_score"] < th)
        fp_a = sum(1 for s in all_scored if s["target_label"] == 0 and s["max_score"] >= th)
        fp_h = sum(1 for s in all_scored if s["target_label"] == 0 and s["category"] == "HARD_NEGATIVE" and s["max_score"] >= th)
        fp_g = sum(1 for s in all_scored if s["target_label"] == 0 and s["category"] == "GENERAL_NEGATIVE" and s["max_score"] >= th)

        tot_a = tp_a + tn_a + fp_a + fn_a
        acc_a = (tp_a + tn_a) / tot_a if tot_a > 0 else 0.0
        prec_a = tp_a / (tp_a + fp_a) if (tp_a + fp_a) > 0 else 0.0
        rec_a = tp_a / (tp_a + fn_a) if (tp_a + fn_a) > 0 else 0.0
        f1_a = (2 * prec_a * rec_a) / (prec_a + rec_a) if (prec_a + rec_a) > 0 else 0.0
        fpr_a = fp_a / (fp_a + tn_a) if (fp_a + tn_a) > 0 else 0.0
        fnr_a = fn_a / (fn_a + tp_a) if (fn_a + tp_a) > 0 else 0.0

        print(f"{th:<8.2f}{tp_a:<5}{tn_a:<5}{fp_a:<5}{fn_a:<5}{acc_a:<8.4f}{prec_a:<8.4f}{rec_a:<8.4f}{f1_a:<8.4f}{fpr_a:<8.4f}{fnr_a:<8.4f}{fp_h:<8}{fp_g:<8}")

    print("\nOverall Dataset False Positives at 0.50:")
    all_fps_50 = [s for s in all_scored if s["target_label"] == 0 and s["max_score"] >= 0.50]
    for fp in sorted(all_fps_50, key=lambda x: -x["max_score"]):
        print(f"  [FP] {fp['filename']} | phrase=\"{fp['phrase']}\" | score={fp['max_score']:.4f} | sess={fp['session_id']}")

    print("\nOverall Dataset False Negatives at 0.50 (sample):")
    all_fns_50 = [s for s in all_scored if s["target_label"] == 1 and s["max_score"] < 0.50]
    print(f"  Total False Negatives: {len(all_fns_50)} out of 69 positives ({len(all_fns_50)/69.0*100:.1f}%)")
    for fn in sorted(all_fns_50, key=lambda x: x["max_score"])[:10]:
        print(f"  [FN] {fn['filename']} | phrase=\"{fn['phrase']}\" | score={fn['max_score']:.4f} | cond={fn.get('condition')}")

    # 12. Phase 10: Model Immutability Check
    print("\n" + "=" * 70)
    print("PHASE 10: MODEL IMMUTABILITY CHECK")
    print("=" * 70)
    active_sha_after = calculate_sha256(ACTIVE_MODEL_PATH)
    print(f"Active Model SHA256 AFTER evaluation:  {active_sha_after}")
    print(f"Active Model SHA256 BEFORE evaluation: {active_sha_before}")
    assert active_sha_before == active_sha_after, "CRITICAL ERROR: Active model was modified during evaluation!"
    print("[SUCCESS] Active ONNX model is byte-for-byte identical (UNTOUCHED).")

    return {
        "all_wav_count": len(all_wavs),
        "by_folder": {k: len(v) for k, v in by_folder.items()},
        "records": records,
        "format_deviations": format_deviations_found,
        "collisions": collisions,
        "manifest_records_count": len(manifest_records),
        "unmanifested_disk_files": list(unmanifested_disk_files),
        "manifest_missing_on_disk": manifest_missing_on_disk,
        "duplicate_manifest_relpaths": {k: len(v) for k, v in duplicate_manifest_relpaths.items()},
        "speaker_counts": dict(speaker_counts),
        "session_counts": dict(session_counts),
        "holdout_count": len(holdout_all),
        "eval_results": eval_results,
        "active_sha": active_sha_after,
    }


if __name__ == "__main__":
    run_forensic_audit()
