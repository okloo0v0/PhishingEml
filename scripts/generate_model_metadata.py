"""Generate contract-compatible model metadata and an experiment record."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = ROOT / "models" / "phishing_model.joblib"
DEFAULT_TRAINING = ROOT / "data" / "manifests" / "model_training_summary.json"
DEFAULT_EVALUATION = ROOT / "data" / "manifests" / "model_evaluation_summary.json"
DEFAULT_SPLIT = ROOT / "data" / "manifests" / "split_summary.json"
DEFAULT_DEDUP_REPORT = ROOT / "data" / "manifests" / "dedup_combined_report.json"
DEFAULT_META = ROOT / "models" / "model_meta.json"
DEFAULT_EXPERIMENTS = ROOT / "docs" / "experiments.csv"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _version(package: str) -> str:
    try:
        return importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def _relative_or_absolute(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def generate(
    model_path: Path = DEFAULT_MODEL,
    training_path: Path = DEFAULT_TRAINING,
    evaluation_path: Path = DEFAULT_EVALUATION,
    split_path: Path = DEFAULT_SPLIT,
    dedup_report_path: Path = DEFAULT_DEDUP_REPORT,
    metadata_path: Path = DEFAULT_META,
    experiments_path: Path = DEFAULT_EXPERIMENTS,
) -> dict[str, object]:
    """Create metadata from the exact artifacts produced by steps 6--8."""

    training = json.loads(training_path.read_text(encoding="utf-8"))
    evaluation = json.loads(evaluation_path.read_text(encoding="utf-8"))
    split = json.loads(split_path.read_text(encoding="utf-8"))
    artifact_sha256 = _sha256(model_path)
    expected_sha256 = training.get("artifact_sha256")
    if expected_sha256 and artifact_sha256 != expected_sha256:
        raise ValueError("model artifact SHA-256 does not match training summary")

    report_digest = _sha256(dedup_report_path)
    dataset_version = f"ds-{datetime.now(timezone.utc):%Y%m%d}-{report_digest[:8]}"
    test_metrics = evaluation["test"]["contract_metrics"]
    cross_metrics = evaluation["cross_source_test"]["contract_metrics"]
    metadata = {
        "model_name": training["model_name"],
        "model_version": training["model_version"],
        "feature_version": training["feature_version"],
        "trained_at": training["trained_at"],
        "label_order": training["label_order"],
        "metrics": {
            "test_precision": float(test_metrics["precision"]),
            "test_recall": float(test_metrics["recall"]),
            "test_f1": float(test_metrics["f1"]),
            "test_accuracy": float(test_metrics["accuracy"]),
            "cross_source_precision": float(cross_metrics["precision"]),
            "cross_source_recall": float(cross_metrics["recall"]),
            "cross_source_f1": float(cross_metrics["f1"]),
            "cross_source_accuracy": float(cross_metrics["accuracy"]),
        },
        "artifact_filename": model_path.name,
        "metadata_filename": metadata_path.name,
        "artifact_sha256": artifact_sha256,
        "artifact_path": _relative_or_absolute(model_path),
        "dataset_version": dataset_version,
        "dataset_manifest_sha256": report_digest,
        "random_state": training["random_state"],
        "train_count": training["train_count"],
        "valid_count": training["valid_count"],
        "test_count": training["test_count"],
        "max_text_chars": 20_000,
        "features": ["subject", "text_body", "tfidf_word_ngram_1_2"],
        "tfidf": training["tfidf"],
        "classifier": training["classifier"],
        "probability_threshold": evaluation["contract_threshold"],
        "tuned_threshold_diagnostic": evaluation["selected_threshold"],
        "test_confusion_matrix": test_metrics["confusion_matrix"],
        "cross_source_confusion_matrix": cross_metrics["confusion_matrix"],
        "dependencies": {
            "python": "3.11",
            "scikit-learn": _version("scikit-learn"),
            "joblib": _version("joblib"),
            "numpy": _version("numpy"),
            "pandas": _version("pandas"),
        },
        "source_counts": split["source_counts"],
        "hard_negative_count": split["hard_negative_records"],
    }
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    experiments_path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "experiment_id", "model_name", "model_version", "dataset_version", "feature_version",
        "random_state", "train_count", "valid_count", "test_count", "threshold",
        "test_precision", "test_recall", "test_f1", "test_accuracy", "cross_source_f1",
        "test_confusion_matrix", "artifact_sha256", "notes",
    ]
    experiment_id = f"{metadata['model_version']}-{dataset_version}"
    row = {
        "experiment_id": experiment_id,
        "model_name": metadata["model_name"],
        "model_version": metadata["model_version"],
        "dataset_version": dataset_version,
        "feature_version": metadata["feature_version"],
        "random_state": metadata["random_state"],
        "train_count": metadata["train_count"],
        "valid_count": metadata["valid_count"],
        "test_count": metadata["test_count"],
        "threshold": metadata["probability_threshold"],
        "test_precision": metadata["metrics"]["test_precision"],
        "test_recall": metadata["metrics"]["test_recall"],
        "test_f1": metadata["metrics"]["test_f1"],
        "test_accuracy": metadata["metrics"]["test_accuracy"],
        "cross_source_f1": metadata["metrics"]["cross_source_f1"],
        "test_confusion_matrix": json.dumps(test_metrics["confusion_matrix"], separators=(",", ":")),
        "artifact_sha256": artifact_sha256,
        "notes": "contract threshold 0.50; valid tuned threshold retained as diagnostic only",
    }
    existing: list[dict[str, str]] = []
    if experiments_path.exists():
        with experiments_path.open(encoding="utf-8", newline="") as source:
            existing = list(csv.DictReader(source))
    existing = [item for item in existing if item.get("experiment_id") != experiment_id]
    with experiments_path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        writer.writerows(existing)
        writer.writerow(row)
    return metadata


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--training", type=Path, default=DEFAULT_TRAINING)
    parser.add_argument("--evaluation", type=Path, default=DEFAULT_EVALUATION)
    parser.add_argument("--split", type=Path, default=DEFAULT_SPLIT)
    parser.add_argument("--dedup-report", type=Path, default=DEFAULT_DEDUP_REPORT)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_META)
    parser.add_argument("--experiments", type=Path, default=DEFAULT_EXPERIMENTS)
    args = parser.parse_args()
    print(json.dumps(generate(args.model, args.training, args.evaluation, args.split, args.dedup_report, args.metadata, args.experiments), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
