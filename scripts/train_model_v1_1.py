"""Train the V1.1 word/char/structure/intent late-fusion model."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import joblib

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.detection.multiview_features import FEATURE_VERSION, records_from_rows
from src.detection.multiview_model import EXPECTED_CLASSES, MultiViewPhishingClassifier


DEFAULT_INPUT = ROOT / "data" / "processed" / "emails.csv"
DEFAULT_HARD_NEGATIVE = ROOT / "data" / "processed" / "hard_negative_emails.jsonl"
DEFAULT_MODEL = ROOT / "models" / "phishing_model_v1_1.joblib"
DEFAULT_SUMMARY = ROOT / "data" / "manifests" / "model_training_summary_v1_1.json"
DEFAULT_PREDICTIONS = ROOT / "data" / "processed" / "model_predictions_v1_1.csv"
DEFAULT_LOG = ROOT / "data" / "manifests" / "model_training_log_v1_1.json"

MODEL_VERSION = "v1.1.0"
RANDOM_STATE = 42
HARD_NEGATIVE_SPLIT_POLICY = "stable SHA-256 bucket: train=0..5, valid=6..7, test=8..9"


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_csv(path: Path) -> list[dict[str, str]]:
    try:
        csv.field_size_limit(sys.maxsize)
    except OverflowError:
        csv.field_size_limit(2**31 - 1)
    with path.open(encoding="utf-8", newline="") as source:
        return list(csv.DictReader(source))


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    with path.open(encoding="utf-8") as source:
        return [json.loads(line) for line in source if line.strip()]


def hard_negative_split(row: dict[str, object]) -> str:
    """Assign a reproducible hard-negative partition without using row order."""

    identity = "|".join(
        str(row.get(field, "")) for field in ("source", "id", "dedup_group", "content_fingerprint")
    )
    bucket = int(hashlib.sha256(identity.encode("utf-8")).hexdigest()[:8], 16) % 10
    return "train" if bucket <= 5 else "valid" if bucket <= 7 else "test"


def _as_negative(row: dict[str, object], split: str) -> dict[str, object]:
    return {**row, "original_label": str(row.get("label", "")), "label": "legitimate", "split": split}


def prepare_training_collections(
    rows: list[dict[str, object]],
    hard_rows: list[dict[str, object]],
    supplement_rows: list[dict[str, object]] | None = None,
) -> dict[str, list[dict[str, object]]]:
    required = {"id", "source", "label", "subject", "text_body", "split"}
    for row in rows:
        missing = required.difference(row)
        if missing:
            raise ValueError(f"missing required CSV fields: {sorted(missing)}")
        if str(row["label"]) not in EXPECTED_CLASSES:
            raise ValueError(f"unsupported binary label: {row['label']}")
    for row in hard_rows:
        if str(row.get("label", "")) != "spam_other":
            raise ValueError("hard-negative input must contain only spam_other records")

    supplement_rows = supplement_rows or []
    for row in supplement_rows:
        if str(row.get("label", "")) not in EXPECTED_CLASSES:
            raise ValueError("curated supplement must contain only binary labels")
        partition = str(row.get("dataset_partition", "train"))
        if partition != "train":
            raise ValueError("only the curated train partition may enter model training")

    collections = {
        split: [dict(row) for row in rows if str(row["split"]) == split]
        for split in ("train", "valid", "test")
    }
    for row in hard_rows:
        split = hard_negative_split(row)
        collections.setdefault(f"hard_{split}", []).append(_as_negative(row, split))
    collections["supplement_train"] = [dict(row) for row in supplement_rows]

    base_fingerprints = {
        str(row.get("content_fingerprint", ""))
        for row in collections["train"]
        if row.get("content_fingerprint")
    }
    supplement_fingerprints = {
        str(row.get("content_fingerprint", ""))
        for row in collections["supplement_train"]
        if row.get("content_fingerprint")
    }
    if base_fingerprints.intersection(supplement_fingerprints):
        raise ValueError("curated supplement overlaps the base train split")
    return collections


def _write_predictions(
    path: Path,
    model: MultiViewPhishingClassifier,
    collections: dict[str, list[dict[str, object]]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["dataset", "id", "source", "label", "predicted_label", "phishing_probability"]
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for name in ("valid", "test", "hard_valid", "hard_test"):
            rows = collections.get(name, [])
            if not rows:
                continue
            probabilities = model.predict_proba(records_from_rows(rows))[:, 1]
            for row, probability in zip(rows, probabilities):
                writer.writerow(
                    {
                        "dataset": name,
                        "id": row["id"],
                        "source": row["source"],
                        "label": row["label"],
                        "predicted_label": "phishing" if probability >= 0.50 else "legitimate",
                        "phishing_probability": f"{float(probability):.10f}",
                    }
                )


def train(
    input_path: Path = DEFAULT_INPUT,
    hard_negative_path: Path = DEFAULT_HARD_NEGATIVE,
    model_path: Path = DEFAULT_MODEL,
    summary_path: Path = DEFAULT_SUMMARY,
    predictions_path: Path = DEFAULT_PREDICTIONS,
    log_path: Path = DEFAULT_LOG,
    *,
    supplement_path: Path | None = None,
    model_version: str = MODEL_VERSION,
    word_max_features: int = 50_000,
    char_max_features: int = 60_000,
    min_df: int = 2,
    cv_splits: int = 5,
    enabled_views: tuple[str, ...] = ("word", "char", "structure", "intent"),
) -> dict[str, object]:
    """Fit V1.1 on binary data, stable hard negatives, and an optional train-only supplement."""

    rows = [dict(row) for row in _read_csv(input_path)]
    hard_rows = _read_jsonl(hard_negative_path)
    supplement_rows = _read_jsonl(supplement_path) if supplement_path is not None else []
    collections = prepare_training_collections(rows, hard_rows, supplement_rows)
    train_rows = (
        collections["train"]
        + collections.get("hard_train", [])
        + collections["supplement_train"]
    )
    labels = [str(row["label"]) for row in train_rows]
    if sorted(set(labels)) != EXPECTED_CLASSES:
        raise ValueError(f"train split must contain both classes, got {sorted(set(labels))}")

    model = MultiViewPhishingClassifier(
        word_max_features=word_max_features,
        char_max_features=char_max_features,
        min_df=min_df,
        cv_splits=cv_splits,
        random_state=RANDOM_STATE,
        enabled_views=enabled_views,
    )
    model.fit(records_from_rows(train_rows), labels)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_path)
    _write_predictions(predictions_path, model, collections)

    hard_counts = {
        split: len(collections.get(f"hard_{split}", []))
        for split in ("train", "valid", "test")
    }
    summary = {
        "model_name": "multiview_late_fusion_logistic_regression",
        "model_version": model_version,
        "feature_version": FEATURE_VERSION,
        "trained_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "label_order": EXPECTED_CLASSES,
        "input_path": _display_path(input_path),
        "hard_negative_path": _display_path(hard_negative_path),
        "curated_supplement_path": _display_path(supplement_path)
        if supplement_path is not None
        else None,
        "artifact_filename": model_path.name,
        "artifact_sha256": _sha256_file(model_path),
        "predictions_path": _display_path(predictions_path),
        "random_state": RANDOM_STATE,
        "train_count": len(train_rows),
        "base_train_count": len(collections["train"]),
        "curated_supplement_train_count": len(collections["supplement_train"]),
        "valid_count": len(collections["valid"]) + hard_counts["valid"],
        "test_count": len(collections["test"]) + hard_counts["test"],
        "hard_negative_counts": hard_counts,
        "hard_negative_split_policy": HARD_NEGATIVE_SPLIT_POLICY,
        "training_label_counts": dict(sorted(Counter(labels).items())),
        "features": [f"{name}_tfidf" if name in {"word", "char"} else name for name in enabled_views],
        "model_config": {
            "word_ngram_range": [1, 2],
            "word_max_features": word_max_features,
            "char_analyzer": "char_wb",
            "char_ngram_range": [3, 5],
            "char_max_features": char_max_features,
            "min_df": min_df,
            "oof_splits": model.oof_splits_,
            "branch_classifier": "class_weight=balanced LogisticRegression",
            "meta_classifier": "non-negative constrained LogisticRegression + sigmoid calibration",
        },
        "tfidf": {
            "word_ngram_range": [1, 2],
            "char_ngram_range": [3, 5],
            "min_df": min_df,
        },
        "classifier": {
            "type": "OOF late-fusion LogisticRegression",
            "branch_class_weight": "balanced",
            "meta_constraint": "non-negative branch weights",
            "probability_calibration": "sigmoid CalibratedClassifierCV on OOF fusion scores",
        },
        "probability_semantics": "predict_proba[:, 1] is calibrated-fusion phishing_probability; threshold=0.50",
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        json.dumps(
            {
                "event": "model_v1_1_trained",
                "trained_at": summary["trained_at"],
                "model_version": model_version,
                "artifact_filename": summary["artifact_filename"],
                "artifact_sha256": summary["artifact_sha256"],
                "train_count": summary["train_count"],
                "hard_negative_counts": hard_counts,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--hard-negative", type=Path, default=DEFAULT_HARD_NEGATIVE)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--predictions", type=Path, default=DEFAULT_PREDICTIONS)
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--supplement", type=Path)
    parser.add_argument("--model-version", default=MODEL_VERSION)
    parser.add_argument("--word-max-features", type=int, default=50_000)
    parser.add_argument("--char-max-features", type=int, default=60_000)
    parser.add_argument("--min-df", type=int, default=2)
    parser.add_argument("--cv-splits", type=int, default=5)
    parser.add_argument("--disable-intent", action="store_true", help="Train the stable word/char/structure fusion without the experimental intent view.")
    args = parser.parse_args()
    result = train(
        args.input,
        args.hard_negative,
        args.model,
        args.summary,
        args.predictions,
        args.log,
        supplement_path=args.supplement,
        model_version=args.model_version,
        word_max_features=args.word_max_features,
        char_max_features=args.char_max_features,
        min_df=args.min_df,
        cv_splits=args.cv_splits,
        enabled_views=("word", "char", "structure") if args.disable_intent else ("word", "char", "structure", "intent"),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
