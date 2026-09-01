"""Evaluate external hard negatives and safe synthetic boundary cases."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import joblib
import numpy as np
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score

# Allow direct execution via `uv run python scripts/run_extra_evaluation.py`.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.detection.text_features import clean_email_text

LING_PATH = ROOT / "data" / "raw" / "supplemental_zenodo" / "Ling.csv"
SYNTHETIC_PATH = ROOT / "data" / "samples" / "extra_evaluation_cases.jsonl"
TRAIN_PATH = ROOT / "data" / "processed" / "deduplicated_emails_combined.jsonl"
MODEL_PATH = ROOT / "models" / "phishing_model.joblib"
DEFAULT_PREDICTIONS = ROOT / "data" / "processed" / "extra_evaluation_predictions.csv"
DEFAULT_SUMMARY = ROOT / "data" / "manifests" / "extra_evaluation_summary.json"


def _hash_payload(payload: dict[str, str]) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _load_ling() -> list[dict[str, object]]:
    csv.field_size_limit(2**31 - 1)
    rows: list[dict[str, object]] = []
    with LING_PATH.open(encoding="utf-8-sig", newline="") as source:
        for index, row in enumerate(csv.DictReader(source)):
            label = {"0": "legitimate", "1": "spam_other"}.get(str(row.get("label", "")).strip())
            if label is None:
                continue
            cleaned = clean_email_text(row.get("subject", ""), row.get("body", ""))
            rows.append({"id": f"ling-{index:06d}", "source": "zenodo_ling_csv", "label": label, "model_text": cleaned.model_text, "content_fingerprint": hashlib.sha256(cleaned.model_text.encode("utf-8")).hexdigest()})
    return rows


def _load_synthetic() -> list[dict[str, object]]:
    rows = []
    with SYNTHETIC_PATH.open(encoding="utf-8") as source:
        for line in source:
            raw = json.loads(line)
            cleaned = clean_email_text(raw.get("subject", ""), raw.get("text_body", ""))
            rows.append({**raw, "model_text": cleaned.model_text, "content_fingerprint": hashlib.sha256(cleaned.model_text.encode("utf-8")).hexdigest()})
    return rows


def _metric(rows: list[dict[str, object]], probabilities: np.ndarray) -> dict[str, object]:
    labels = [str(row["label"]) for row in rows]
    predicted = ["phishing" if value >= 0.50 else "legitimate" for value in probabilities]
    return {"support": len(rows), "precision": precision_score(labels, predicted, labels=["legitimate", "phishing"], pos_label="phishing", zero_division=0), "recall": recall_score(labels, predicted, labels=["legitimate", "phishing"], pos_label="phishing", zero_division=0), "f1": f1_score(labels, predicted, labels=["legitimate", "phishing"], pos_label="phishing", zero_division=0), "accuracy": accuracy_score(labels, predicted), "confusion_matrix": confusion_matrix(labels, predicted, labels=["legitimate", "phishing"]).tolist()}


def run(predictions_path: Path = DEFAULT_PREDICTIONS, summary_path: Path = DEFAULT_SUMMARY) -> dict[str, object]:
    with TRAIN_PATH.open(encoding="utf-8") as source:
        known_fingerprints = {json.loads(line)["content_fingerprint"] for line in source if line.strip()}
    ling = _load_ling()
    synthetic = _load_synthetic()
    ling_unseen = [row for row in ling if row["content_fingerprint"] not in known_fingerprints]
    synthetic_unseen = [row for row in synthetic if row["content_fingerprint"] not in known_fingerprints]
    model = joblib.load(MODEL_PATH)
    all_rows = [("ling_hard_negative", ling_unseen), ("synthetic_binary", synthetic_unseen)]
    prediction_rows: list[dict[str, object]] = []
    summary: dict[str, object] = {"model_version": "v1.0.0", "threshold": 0.50, "source_overlap": {"ling_total": len(ling), "ling_exact_overlap": len(ling) - len(ling_unseen), "synthetic_total": len(synthetic), "synthetic_exact_overlap": len(synthetic) - len(synthetic_unseen)}}
    for dataset, rows in all_rows:
        probabilities = model.predict_proba([str(row["model_text"]) for row in rows])[:, 1] if rows else np.array([])
        if dataset == "synthetic_binary":
            summary[dataset] = {"metrics": _metric(rows, probabilities)}
        else:
            summary[dataset] = {"support": len(rows), "spam_other_count": sum(row["label"] == "spam_other" for row in rows), "phishing_rate": float(np.mean(probabilities >= 0.50)) if len(rows) else 0.0, "mean_phishing_probability": float(np.mean(probabilities)) if len(rows) else 0.0, "max_phishing_probability": float(np.max(probabilities)) if len(rows) else 0.0, "predicted_counts": dict(sorted(Counter("phishing" if value >= 0.50 else "legitimate" for value in probabilities).items()))}
        for row, probability in zip(rows, probabilities):
            prediction_rows.append({"dataset": dataset, "id": row["id"], "source": row["source"], "label": row["label"], "predicted_label": "phishing" if probability >= 0.50 else "legitimate", "phishing_probability": f"{float(probability):.10f}"})
    predictions_path.parent.mkdir(parents=True, exist_ok=True)
    with predictions_path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=["dataset", "id", "source", "label", "predicted_label", "phishing_probability"])
        writer.writeheader(); writer.writerows(prediction_rows)
    summary["predictions_path"] = predictions_path.relative_to(ROOT).as_posix()
    summary["safety_note"] = "Ling label 1 is retained as spam_other, never converted to phishing; exact overlaps with training fingerprints are excluded."
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, default=DEFAULT_PREDICTIONS)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    args = parser.parse_args()
    print(json.dumps(run(args.predictions, args.summary), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
