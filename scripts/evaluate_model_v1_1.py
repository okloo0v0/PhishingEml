"""Evaluate V1.1 with calibration, branch, hard-negative, and baseline metrics."""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.train_model_v1_1 import hard_negative_split
from src.detection.multiview_features import records_from_rows


DEFAULT_INPUT = ROOT / "data" / "processed" / "emails.csv"
DEFAULT_MODEL = ROOT / "models" / "phishing_model_v1_1.joblib"
DEFAULT_BASELINE_MODEL = ROOT / "models" / "phishing_model.joblib"
DEFAULT_CROSS_SOURCE = ROOT / "data" / "processed" / "cross_source_test.jsonl"
DEFAULT_HARD_NEGATIVE = ROOT / "data" / "processed" / "hard_negative_emails.jsonl"
DEFAULT_SUMMARY = ROOT / "data" / "manifests" / "model_evaluation_summary_v1_1.json"
DEFAULT_PREDICTIONS = ROOT / "data" / "processed" / "evaluation_predictions_v1_1.csv"
DEFAULT_ERRORS = ROOT / "data" / "processed" / "error_samples_v1_1.csv"

EXPECTED_CLASSES = ["legitimate", "phishing"]
CONTRACT_THRESHOLD = 0.50


def _read_csv(path: Path) -> list[dict[str, Any]]:
    try:
        csv.field_size_limit(sys.maxsize)
    except OverflowError:
        csv.field_size_limit(2**31 - 1)
    with path.open(encoding="utf-8", newline="") as source:
        return [dict(row) for row in csv.DictReader(source)]


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as source:
        return [json.loads(line) for line in source if line.strip()]


def _binary_labels(labels: list[str]) -> np.ndarray:
    return np.asarray([1 if label == "phishing" else 0 for label in labels], dtype=np.uint8)


def _expected_calibration_error(
    actual: np.ndarray,
    probabilities: np.ndarray,
    bins: int = 10,
) -> float:
    boundaries = np.linspace(0.0, 1.0, bins + 1)
    total = len(actual)
    error = 0.0
    for index in range(bins):
        if index == bins - 1:
            mask = (probabilities >= boundaries[index]) & (probabilities <= boundaries[index + 1])
        else:
            mask = (probabilities >= boundaries[index]) & (probabilities < boundaries[index + 1])
        if not np.any(mask):
            continue
        error += float(np.mean(mask)) * abs(float(np.mean(actual[mask])) - float(np.mean(probabilities[mask])))
    return error if total else 0.0


def metrics(labels: list[str], probabilities: np.ndarray, threshold: float) -> dict[str, object]:
    predicted = np.where(probabilities >= threshold, "phishing", "legitimate").tolist()
    actual = _binary_labels(labels)
    matrix = confusion_matrix(labels, predicted, labels=EXPECTED_CLASSES)
    tn, fp, fn, tp = matrix.ravel()
    return {
        "threshold": threshold,
        "support": len(labels),
        "precision": precision_score(labels, predicted, pos_label="phishing", zero_division=0),
        "recall": recall_score(labels, predicted, pos_label="phishing", zero_division=0),
        "f1": f1_score(labels, predicted, pos_label="phishing", zero_division=0),
        "accuracy": accuracy_score(labels, predicted),
        "false_positive_rate": float(fp / (fp + tn)) if fp + tn else 0.0,
        "false_negative_rate": float(fn / (fn + tp)) if fn + tp else 0.0,
        "pr_auc": average_precision_score(actual, probabilities) if len(set(actual)) == 2 else None,
        "brier_score": brier_score_loss(actual, probabilities),
        "expected_calibration_error": _expected_calibration_error(actual, probabilities),
        "confusion_matrix": matrix.tolist(),
        "predicted_counts": dict(sorted(Counter(predicted).items())),
        "actual_counts": dict(sorted(Counter(labels).items())),
    }


def paired_pr_auc_bootstrap(
    labels: list[str],
    candidate: np.ndarray,
    baseline: np.ndarray,
    *,
    iterations: int = 500,
    random_state: int = 42,
) -> dict[str, float | int]:
    """Estimate a paired confidence interval for candidate-minus-baseline PR-AUC."""

    actual = _binary_labels(labels)
    if len(set(actual)) != 2:
        raise ValueError("paired PR-AUC bootstrap requires both labels")
    rng = np.random.default_rng(random_state)
    differences: list[float] = []
    while len(differences) < iterations:
        indices = rng.integers(0, len(actual), size=len(actual))
        sampled_actual = actual[indices]
        if len(set(sampled_actual)) != 2:
            continue
        differences.append(
            float(
                average_precision_score(sampled_actual, candidate[indices])
                - average_precision_score(sampled_actual, baseline[indices])
            )
        )
    return {
        "iterations": iterations,
        "mean_difference": float(np.mean(differences)),
        "ci95_lower": float(np.percentile(differences, 2.5)),
        "ci95_upper": float(np.percentile(differences, 97.5)),
    }


def _model_probability(model, records: list[dict[str, Any]]) -> np.ndarray:
    classes = [str(value) for value in model.classes_]
    if classes != EXPECTED_CLASSES:
        raise ValueError(f"unexpected classifier class order: {classes}")
    return model.predict_proba(records)[:, classes.index("phishing")]


def _baseline_probability(model, rows: list[dict[str, Any]]) -> np.ndarray:
    classes = [str(value) for value in model.classes_]
    if classes != EXPECTED_CLASSES:
        raise ValueError(f"unexpected baseline class order: {classes}")
    return model.predict_proba([str(row.get("model_text", "")) for row in rows])[:, 1]


def _per_source(
    rows: list[dict[str, Any]],
    probabilities: np.ndarray,
    threshold: float,
) -> dict[str, object]:
    result: dict[str, object] = {}
    for source in sorted({str(row.get("source", "unknown")) for row in rows}):
        indices = [index for index, row in enumerate(rows) if str(row.get("source", "unknown")) == source]
        source_probabilities = probabilities[indices]
        source_labels = [str(rows[index]["label"]) for index in indices]
        result[source] = metrics(source_labels, source_probabilities, threshold)
    return result


def _write_predictions(
    path: Path,
    collections: dict[str, list[dict[str, Any]]],
    probabilities: dict[str, np.ndarray],
    tuned_threshold: float,
) -> list[dict[str, object]]:
    output_rows: list[dict[str, object]] = []
    for dataset, rows in collections.items():
        for row, probability in zip(rows, probabilities[dataset]):
            label = str(row["label"])
            contract_prediction = "phishing" if probability >= CONTRACT_THRESHOLD else "legitimate"
            tuned_prediction = "phishing" if probability >= tuned_threshold else "legitimate"
            output_rows.append(
                {
                    "dataset": dataset,
                    "id": str(row["id"]),
                    "source": str(row["source"]),
                    "label": label,
                    "predicted_label": contract_prediction,
                    "predicted_label_tuned": tuned_prediction,
                    "phishing_probability": f"{float(probability):.10f}",
                    "is_error": label != contract_prediction,
                    "is_error_tuned": label != tuned_prediction,
                }
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(output_rows[0]) if output_rows else [])
        if output_rows:
            writer.writeheader()
            writer.writerows(output_rows)
    return output_rows


def _latency(model, records: list[dict[str, Any]], limit: int = 50) -> dict[str, float]:
    durations: list[float] = []
    for record in records[:limit]:
        started = time.perf_counter()
        model.predict_proba([record])
        durations.append((time.perf_counter() - started) * 1000.0)
    if not durations:
        return {"samples": 0, "p50_ms": 0.0, "p95_ms": 0.0}
    return {
        "samples": len(durations),
        "p50_ms": float(np.percentile(durations, 50)),
        "p95_ms": float(np.percentile(durations, 95)),
    }


def evaluate(
    input_path: Path = DEFAULT_INPUT,
    model_path: Path = DEFAULT_MODEL,
    cross_source_path: Path = DEFAULT_CROSS_SOURCE,
    hard_negative_path: Path = DEFAULT_HARD_NEGATIVE,
    summary_path: Path = DEFAULT_SUMMARY,
    predictions_path: Path = DEFAULT_PREDICTIONS,
    errors_path: Path = DEFAULT_ERRORS,
    baseline_model_path: Path | None = DEFAULT_BASELINE_MODEL,
) -> dict[str, object]:
    rows = _read_csv(input_path)
    cross_rows = _read_jsonl(cross_source_path)
    raw_hard_rows = _read_jsonl(hard_negative_path)
    hard_rows = [
        {**row, "original_label": "spam_other", "label": "legitimate", "split": "test"}
        for row in raw_hard_rows
        if hard_negative_split(row) == "test"
    ]
    hard_valid_rows = [
        {**row, "original_label": "spam_other", "label": "legitimate", "split": "valid"}
        for row in raw_hard_rows
        if hard_negative_split(row) == "valid"
    ]
    valid_rows = [row for row in rows if row["split"] == "valid"] + hard_valid_rows
    test_rows = [row for row in rows if row["split"] == "test"]
    collections = {
        "valid": valid_rows,
        "test": test_rows,
        "cross_source_test": cross_rows,
        "hard_negative_test": hard_rows,
    }

    model = joblib.load(model_path)
    records = {name: records_from_rows(items) for name, items in collections.items()}
    probabilities = {name: _model_probability(model, values) for name, values in records.items()}
    valid_labels = [str(row["label"]) for row in valid_rows]
    candidates = [round(value, 2) for value in np.arange(0.30, 0.701, 0.01)]
    tuning = [metrics(valid_labels, probabilities["valid"], threshold) for threshold in candidates]
    best = max(tuning, key=lambda item: (item["f1"], item["recall"], -abs(item["threshold"] - 0.50)))
    tuned_threshold = float(best["threshold"])
    prediction_rows = _write_predictions(predictions_path, collections, probabilities, tuned_threshold)

    errors = [row for row in prediction_rows if row["is_error"] or row["is_error_tuned"]]
    errors_path.parent.mkdir(parents=True, exist_ok=True)
    with errors_path.open("w", encoding="utf-8", newline="") as output:
        fields = list(prediction_rows[0]) if prediction_rows else []
        writer = csv.DictWriter(output, fieldnames=fields)
        if fields:
            writer.writeheader()
            writer.writerows(errors)

    result: dict[str, object] = {
        "model_path": str(model_path),
        "label_order": EXPECTED_CLASSES,
        "contract_threshold": CONTRACT_THRESHOLD,
        "selected_threshold": tuned_threshold,
        "tuning_policy": "base valid + reserved hard-negative valid; maximize F1, then recall, then closeness to 0.50",
        "hard_negative_split_policy": "reserved test partition only; never used by this evaluation for fitting or threshold tuning",
    }
    for name, dataset_rows in collections.items():
        labels = [str(row["label"]) for row in dataset_rows]
        result[name] = {
            "contract_metrics": metrics(labels, probabilities[name], CONTRACT_THRESHOLD),
            "tuned_metrics": metrics(labels, probabilities[name], tuned_threshold),
            "per_source_contract": _per_source(dataset_rows, probabilities[name], CONTRACT_THRESHOLD),
        }
    result["hard_negative"] = result.pop("hard_negative_test")

    result["branch_metrics"] = {
        dataset: {
            branch: metrics(
                [str(row["label"]) for row in collections[dataset]],
                branch_probabilities,
                CONTRACT_THRESHOLD,
            )
            for branch, branch_probabilities in model.predict_view_proba(records[dataset]).items()
        }
        for dataset in ("test", "cross_source_test", "hard_negative_test")
    }
    result["latency"] = _latency(model, records["test"])
    result["predictions_path"] = str(predictions_path)
    result["errors_path"] = str(errors_path)
    result["test_set_used_once_after_tuning"] = True

    if baseline_model_path is not None and baseline_model_path.is_file():
        baseline = joblib.load(baseline_model_path)
        baseline_probabilities = {
            name: _baseline_probability(baseline, dataset_rows)
            for name, dataset_rows in collections.items()
        }
        result["baseline_same_set"] = {
            name: metrics(
                [str(row["label"]) for row in dataset_rows],
                baseline_probabilities[name],
                CONTRACT_THRESHOLD,
            )
            for name, dataset_rows in collections.items()
        }
        result["paired_comparison"] = {
            name: {
                "f1_difference": float(
                    result[name if name != "hard_negative_test" else "hard_negative"]["contract_metrics"]["f1"]
                    - result["baseline_same_set"][name]["f1"]
                ),
                "brier_difference": float(
                    result[name if name != "hard_negative_test" else "hard_negative"]["contract_metrics"]["brier_score"]
                    - result["baseline_same_set"][name]["brier_score"]
                ),
                **(
                    {
                        "pr_auc_bootstrap": paired_pr_auc_bootstrap(
                            [str(row["label"]) for row in collections[name]],
                            probabilities[name],
                            baseline_probabilities[name],
                        )
                    }
                    if name in {"test", "cross_source_test"}
                    else {}
                ),
            }
            for name in collections
        }
        candidate_hard_fpr = result["hard_negative"]["contract_metrics"]["false_positive_rate"]
        baseline_hard_fpr = result["baseline_same_set"]["hard_negative_test"]["false_positive_rate"]
        result["paired_comparison"]["hard_negative_test"]["false_positive_rate_relative_reduction"] = (
            float((baseline_hard_fpr - candidate_hard_fpr) / baseline_hard_fpr)
            if baseline_hard_fpr
            else 0.0
        )

    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--cross-source", type=Path, default=DEFAULT_CROSS_SOURCE)
    parser.add_argument("--hard-negative", type=Path, default=DEFAULT_HARD_NEGATIVE)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--predictions", type=Path, default=DEFAULT_PREDICTIONS)
    parser.add_argument("--errors", type=Path, default=DEFAULT_ERRORS)
    parser.add_argument("--baseline-model", type=Path, default=DEFAULT_BASELINE_MODEL)
    args = parser.parse_args()
    print(
        json.dumps(
            evaluate(
                args.input,
                args.model,
                args.cross_source,
                args.hard_negative,
                args.summary,
                args.predictions,
                args.errors,
                args.baseline_model,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
