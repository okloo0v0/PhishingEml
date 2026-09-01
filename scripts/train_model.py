"""Train the frozen TF-IDF + Logistic Regression baseline pipeline."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "processed" / "emails.csv"
DEFAULT_MODEL = ROOT / "models" / "phishing_model.joblib"
DEFAULT_SUMMARY = ROOT / "data" / "manifests" / "model_training_summary.json"
DEFAULT_PREDICTIONS = ROOT / "data" / "processed" / "model_predictions.csv"
MODEL_VERSION = "v1.0.0"
FEATURE_VERSION = "text-v1"
RANDOM_STATE = 42
EXPECTED_CLASSES = ["legitimate", "phishing"]


def _display_path(path: Path) -> str:
    """Use a repository-relative path when possible, otherwise an absolute path."""

    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _read_rows(path: Path) -> list[dict[str, str]]:
    """Read the split CSV, allowing long email text fields."""

    try:
        csv.field_size_limit(sys.maxsize)
    except OverflowError:
        csv.field_size_limit(2**31 - 1)
    with path.open(encoding="utf-8", newline="") as source:
        return list(csv.DictReader(source))


def build_pipeline() -> Pipeline:
    """Build the fixed baseline pipeline from the project plan."""

    return Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    lowercase=True,
                    ngram_range=(1, 2),
                    min_df=2,
                    max_features=50_000,
                    sublinear_tf=True,
                ),
            ),
            (
                "classifier",
                LogisticRegression(
                    max_iter=1000,
                    class_weight="balanced",
                    random_state=RANDOM_STATE,
                ),
            ),
        ]
    )


def _validate_rows(rows: list[dict[str, str]]) -> None:
    required = {"id", "source", "label", "model_text", "split"}
    for row in rows:
        missing = required.difference(row)
        if missing:
            raise ValueError(f"missing required CSV fields: {sorted(missing)}")
        if row["label"] not in EXPECTED_CLASSES:
            raise ValueError(f"unsupported training label: {row['label']}")
        if row["split"] not in {"train", "valid", "test"}:
            raise ValueError(f"unsupported split: {row['split']}")
        if not row["model_text"].strip():
            raise ValueError(f"empty model_text for record {row['id']}")


def _write_predictions(path: Path, pipeline: Pipeline, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(
            output,
            fieldnames=["id", "source", "split", "label", "predicted_label", "phishing_probability"],
        )
        writer.writeheader()
        for row in rows:
            probability = float(pipeline.predict_proba([row["model_text"]])[0][1])
            writer.writerow(
                {
                    "id": row["id"],
                    "source": row["source"],
                    "split": row["split"],
                    "label": row["label"],
                    "predicted_label": "phishing" if probability >= 0.50 else "legitimate",
                    "phishing_probability": f"{probability:.10f}",
                }
            )


def train(
    input_path: Path = DEFAULT_INPUT,
    model_path: Path = DEFAULT_MODEL,
    summary_path: Path = DEFAULT_SUMMARY,
    predictions_path: Path = DEFAULT_PREDICTIONS,
) -> dict[str, object]:
    """Fit the pipeline on train only and emit reproducibility metadata."""

    rows = _read_rows(input_path)
    _validate_rows(rows)
    train_rows = [row for row in rows if row["split"] == "train"]
    evaluation_rows = [row for row in rows if row["split"] in {"valid", "test"}]
    labels = {row["label"] for row in train_rows}
    if labels != set(EXPECTED_CLASSES):
        raise ValueError(f"train split must contain both classes, got {sorted(labels)}")

    pipeline = build_pipeline()
    pipeline.fit([row["model_text"] for row in train_rows], [row["label"] for row in train_rows])
    classes = [str(value) for value in pipeline.named_steps["classifier"].classes_]
    if classes != EXPECTED_CLASSES:
        raise ValueError(f"unexpected classifier class order: {classes}")

    model_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, model_path)
    _write_predictions(predictions_path, pipeline, evaluation_rows)
    summary = {
        "model_name": "tfidf_logistic_regression",
        "model_version": MODEL_VERSION,
        "feature_version": FEATURE_VERSION,
        "trained_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "label_order": EXPECTED_CLASSES,
        "input_path": _display_path(input_path),
        "artifact_filename": _display_path(model_path),
        "predictions_path": _display_path(predictions_path),
        "random_state": RANDOM_STATE,
        "train_count": len(train_rows),
        "valid_count": sum(row["split"] == "valid" for row in rows),
        "test_count": sum(row["split"] == "test" for row in rows),
        "tfidf": {
            "lowercase": True,
            "ngram_range": [1, 2],
            "min_df": 2,
            "max_features": 50_000,
            "sublinear_tf": True,
        },
        "classifier": {"max_iter": 1000, "class_weight": "balanced"},
        "probability_semantics": "predict_proba[:, 1] is phishing_probability; threshold=0.50",
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--predictions", type=Path, default=DEFAULT_PREDICTIONS)
    args = parser.parse_args()
    print(json.dumps(train(args.input, args.model, args.summary, args.predictions), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
