"""Tune on valid and evaluate the frozen phishing baseline on held-out data."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

import joblib
import numpy as np
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "processed" / "emails.csv"
DEFAULT_MODEL = ROOT / "models" / "phishing_model.joblib"
DEFAULT_CROSS_SOURCE = ROOT / "data" / "processed" / "cross_source_test.jsonl"
DEFAULT_HARD_NEGATIVE = ROOT / "data" / "processed" / "hard_negative_emails.jsonl"
DEFAULT_SUMMARY = ROOT / "data" / "manifests" / "model_evaluation_summary.json"
DEFAULT_PREDICTIONS = ROOT / "data" / "processed" / "evaluation_predictions.csv"
DEFAULT_ERRORS = ROOT / "data" / "processed" / "error_samples.csv"
EXPECTED_CLASSES = ["legitimate", "phishing"]
CONTRACT_THRESHOLD = 0.50


def _read_csv(path: Path) -> list[dict[str, str]]:
    csv.field_size_limit(2**31 - 1)
    with path.open(encoding="utf-8", newline="") as source:
        return list(csv.DictReader(source))


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    with path.open(encoding="utf-8") as source:
        return [json.loads(line) for line in source if line.strip()]


def _metrics(labels: list[str], probabilities: np.ndarray, threshold: float) -> dict[str, object]:
    predicted = np.where(probabilities >= threshold, "phishing", "legitimate").tolist()
    return {
        "threshold": threshold,
        "support": len(labels),
        "precision": precision_score(labels, predicted, labels=EXPECTED_CLASSES, pos_label="phishing", zero_division=0),
        "recall": recall_score(labels, predicted, labels=EXPECTED_CLASSES, pos_label="phishing", zero_division=0),
        "f1": f1_score(labels, predicted, labels=EXPECTED_CLASSES, pos_label="phishing", zero_division=0),
        "accuracy": accuracy_score(labels, predicted),
        "confusion_matrix": confusion_matrix(labels, predicted, labels=EXPECTED_CLASSES).tolist(),
        "predicted_counts": dict(sorted(Counter(predicted).items())),
        "actual_counts": dict(sorted(Counter(labels).items())),
    }


def _per_source(rows: list[dict[str, object]], probabilities: np.ndarray, threshold: float) -> dict[str, object]:
    result: dict[str, object] = {}
    for source in sorted({str(row["source"]) for row in rows}):
        indices = [index for index, row in enumerate(rows) if str(row["source"]) == source]
        labels = [str(rows[index]["label"]) for index in indices]
        result[source] = _metrics(labels, probabilities[indices], threshold)
    return result


def _write_predictions(path: Path, collections: dict[str, list[dict[str, object]]], model, tuned_threshold: float) -> list[dict[str, object]]:
    path.parent.mkdir(parents=True, exist_ok=True)
    all_predictions: list[dict[str, object]] = []
    for dataset_name, rows in collections.items():
        if not rows:
            continue
        probabilities = model.predict_proba([str(row["model_text"]) for row in rows])[:, 1]
        for row, probability in zip(rows, probabilities):
            label = str(row["label"])
            predicted_contract = "phishing" if probability >= CONTRACT_THRESHOLD else "legitimate"
            predicted_tuned = "phishing" if probability >= tuned_threshold else "legitimate"
            all_predictions.append({
                "dataset": dataset_name,
                "id": str(row["id"]),
                "source": str(row["source"]),
                "split": str(row.get("split", dataset_name)),
                "label": label,
                "predicted_label": predicted_contract,
                "predicted_label_tuned": predicted_tuned,
                "phishing_probability": f"{float(probability):.10f}",
                "is_error": label in EXPECTED_CLASSES and label != predicted_contract,
                "is_error_tuned": label in EXPECTED_CLASSES and label != predicted_tuned,
                "error_type": "false_positive" if label == "legitimate" and predicted_contract == "phishing" else "false_negative" if label == "phishing" and predicted_contract == "legitimate" else "",
                "error_type_tuned": "false_positive" if label == "legitimate" and predicted_tuned == "phishing" else "false_negative" if label == "phishing" and predicted_tuned == "legitimate" else "",
            })
    with path.open("w", encoding="utf-8", newline="") as output:
        fields = ["dataset", "id", "source", "split", "label", "predicted_label", "predicted_label_tuned", "phishing_probability", "is_error", "is_error_tuned", "error_type", "error_type_tuned"]
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        writer.writerows(all_predictions)
    return all_predictions


def evaluate(
    input_path: Path = DEFAULT_INPUT,
    model_path: Path = DEFAULT_MODEL,
    cross_source_path: Path = DEFAULT_CROSS_SOURCE,
    hard_negative_path: Path = DEFAULT_HARD_NEGATIVE,
    summary_path: Path = DEFAULT_SUMMARY,
    predictions_path: Path = DEFAULT_PREDICTIONS,
    errors_path: Path = DEFAULT_ERRORS,
) -> dict[str, object]:
    rows = _read_csv(input_path)
    model = joblib.load(model_path)
    classes = [str(value) for value in model.named_steps["classifier"].classes_]
    if classes != EXPECTED_CLASSES:
        raise ValueError(f"unexpected classifier class order: {classes}")
    valid_rows = [row for row in rows if row["split"] == "valid"]
    test_rows = [row for row in rows if row["split"] == "test"]
    cross_rows = _read_jsonl(cross_source_path)
    hard_rows = _read_jsonl(hard_negative_path)
    valid_probabilities = model.predict_proba([row["model_text"] for row in valid_rows])[:, 1]
    candidates = [round(value, 2) for value in np.arange(0.30, 0.701, 0.01)]
    tuning = [_metrics([row["label"] for row in valid_rows], valid_probabilities, threshold) for threshold in candidates]
    best = max(tuning, key=lambda item: (item["f1"], item["recall"], -abs(item["threshold"] - 0.50)))
    threshold = float(best["threshold"])
    collections = {"valid": valid_rows, "test": test_rows, "cross_source_test": cross_rows, "hard_negative": hard_rows}
    predictions = _write_predictions(predictions_path, collections, model, threshold)
    test_probabilities = model.predict_proba([row["model_text"] for row in test_rows])[:, 1]
    cross_probabilities = model.predict_proba([str(row["model_text"]) for row in cross_rows])[:, 1]
    hard_probabilities = model.predict_proba([str(row["model_text"]) for row in hard_rows])[:, 1]
    binary_predictions = [row for row in predictions if row["dataset"] in {"test", "cross_source_test"}]
    errors = [row for row in binary_predictions if row["is_error"] or row["is_error_tuned"]]
    errors_path.parent.mkdir(parents=True, exist_ok=True)
    with errors_path.open("w", encoding="utf-8", newline="") as output:
        fields = ["dataset", "id", "source", "split", "label", "predicted_label", "predicted_label_tuned", "phishing_probability", "error_type", "error_type_tuned"]
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: row[field] for field in fields} for row in errors)
    summary = {
        "model_path": str(model_path),
        "label_order": classes,
        "contract_threshold": CONTRACT_THRESHOLD,
        "tuning_policy": "valid only; threshold candidates 0.30..0.70 step 0.01; maximize F1, then recall, then closeness to 0.50; tuned threshold is diagnostic until contract approval",
        "selected_threshold": threshold,
        "valid": {"contract_metrics": _metrics([row["label"] for row in valid_rows], valid_probabilities, CONTRACT_THRESHOLD), "tuned_metrics": best, "candidate_count": len(candidates), "all_candidates": tuning},
        "test": {"contract_metrics": _metrics([row["label"] for row in test_rows], test_probabilities, CONTRACT_THRESHOLD), "tuned_metrics": _metrics([row["label"] for row in test_rows], test_probabilities, threshold), "per_source_contract": _per_source(test_rows, test_probabilities, CONTRACT_THRESHOLD), "per_source_tuned": _per_source(test_rows, test_probabilities, threshold)},
        "cross_source_test": {"contract_metrics": _metrics([str(row["label"]) for row in cross_rows], cross_probabilities, CONTRACT_THRESHOLD), "tuned_metrics": _metrics([str(row["label"]) for row in cross_rows], cross_probabilities, threshold), "per_source_contract": _per_source(cross_rows, cross_probabilities, CONTRACT_THRESHOLD), "per_source_tuned": _per_source(cross_rows, cross_probabilities, threshold)},
        "hard_negative": {"support": len(hard_rows), "contract_phishing_rate": float(np.mean(hard_probabilities >= CONTRACT_THRESHOLD)), "tuned_phishing_rate": float(np.mean(hard_probabilities >= threshold)), "mean_phishing_probability": float(np.mean(hard_probabilities)), "max_phishing_probability": float(np.max(hard_probabilities))},
        "predictions_path": str(predictions_path),
        "errors_path": str(errors_path),
        "error_counts_contract": dict(sorted(Counter(str(row["error_type"]) for row in binary_predictions if row["is_error"]).items())),
        "error_counts_tuned": dict(sorted(Counter(str(row["error_type_tuned"]) for row in binary_predictions if row["is_error_tuned"]).items())),
        "test_set_used_once_after_tuning": True,
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--cross-source", type=Path, default=DEFAULT_CROSS_SOURCE)
    parser.add_argument("--hard-negative", type=Path, default=DEFAULT_HARD_NEGATIVE)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--predictions", type=Path, default=DEFAULT_PREDICTIONS)
    parser.add_argument("--errors", type=Path, default=DEFAULT_ERRORS)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.input, args.model, args.cross_source, args.hard_negative, args.summary, args.predictions, args.errors), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
