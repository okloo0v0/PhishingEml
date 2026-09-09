"""Run controlled V1.1 view ablations on fixed base and curated test sets."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.evaluate_model_v1_1 import CONTRACT_THRESHOLD, metrics
from scripts.train_model_v1_1 import _read_csv, _read_jsonl, prepare_training_collections
from src.detection.multiview_features import records_from_rows
from src.detection.multiview_model import MultiViewPhishingClassifier


DEFAULT_INPUT = ROOT / "data" / "processed" / "emails.csv"
DEFAULT_HARD_NEGATIVE = ROOT / "data" / "processed" / "hard_negative_emails.jsonl"
DEFAULT_SUPPLEMENT = ROOT / "data" / "processed" / "v1_1_1_curated_train.jsonl"
DEFAULT_CHINESE_TEST = ROOT / "data" / "processed" / "v1_1_1_chinese_test.jsonl"
DEFAULT_MODERN_TEST = ROOT / "data" / "processed" / "v1_1_1_modern_attack_test.jsonl"
DEFAULT_BOUNDARY_TEST = ROOT / "data" / "processed" / "v1_1_1_boundary_test.jsonl"
DEFAULT_SUMMARY = ROOT / "data" / "manifests" / "v1_1_1_ablation_summary.json"

VARIANTS: dict[str, tuple[str, ...]] = {
    "word": ("word",),
    "word_char": ("word", "char"),
    "word_char_structure": ("word", "char", "structure"),
    "word_char_intent": ("word", "char", "intent"),
    "full_multiview": ("word", "char", "structure", "intent"),
}


def _fingerprints(rows: list[dict[str, object]]) -> set[str]:
    return {
        str(row.get("content_fingerprint", ""))
        for row in rows
        if row.get("content_fingerprint")
    }


def _validate_disjoint(train_rows: list[dict[str, object]], tests: dict[str, list[dict[str, object]]]) -> None:
    train_fingerprints = _fingerprints(train_rows)
    for name, rows in tests.items():
        labels = Counter(str(row.get("label", "")) for row in rows)
        if set(labels) != {"legitimate", "phishing"}:
            raise ValueError(f"{name} must contain both binary labels")
        if train_fingerprints.intersection(_fingerprints(rows)):
            raise ValueError(f"{name} overlaps model training content")


def run(
    input_path: Path = DEFAULT_INPUT,
    hard_negative_path: Path = DEFAULT_HARD_NEGATIVE,
    supplement_path: Path = DEFAULT_SUPPLEMENT,
    chinese_test_path: Path = DEFAULT_CHINESE_TEST,
    modern_test_path: Path = DEFAULT_MODERN_TEST,
    boundary_test_path: Path = DEFAULT_BOUNDARY_TEST,
    summary_path: Path = DEFAULT_SUMMARY,
    *,
    word_max_features: int = 50_000,
    char_max_features: int = 60_000,
    min_df: int = 2,
    cv_splits: int = 5,
) -> dict[str, object]:
    """Fit each view subset on identical data and compare fixed test partitions."""

    base_rows = [dict(row) for row in _read_csv(input_path)]
    hard_rows = _read_jsonl(hard_negative_path)
    supplement_rows = _read_jsonl(supplement_path)
    collections = prepare_training_collections(base_rows, hard_rows, supplement_rows)
    train_rows = (
        collections["train"]
        + collections.get("hard_train", [])
        + collections["supplement_train"]
    )
    tests = {
        "base_test": [row for row in base_rows if row["split"] == "test"],
        "chinese_test": _read_jsonl(chinese_test_path),
        "modern_attack_test": _read_jsonl(modern_test_path),
        "boundary_test": _read_jsonl(boundary_test_path),
    }
    _validate_disjoint(train_rows, tests)
    train_records = records_from_rows(train_rows)
    train_labels = [str(row["label"]) for row in train_rows]
    test_records = {name: records_from_rows(rows) for name, rows in tests.items()}
    output: dict[str, object] = {
        "protocol": "same train rows, same fixed test partitions, enabled views vary one configuration at a time",
        "threshold": CONTRACT_THRESHOLD,
        "train_count": len(train_rows),
        "base_train_count": len(collections["train"]),
        "curated_supplement_train_count": len(collections["supplement_train"]),
        "hard_negative_train_count": len(collections.get("hard_train", [])),
        "hard_negative_policy": "unchanged stable SHA-256 partition",
        "test_counts": {name: len(rows) for name, rows in tests.items()},
        "variants": {},
    }
    for name, enabled_views in VARIANTS.items():
        model = MultiViewPhishingClassifier(
            word_max_features=word_max_features,
            char_max_features=char_max_features,
            min_df=min_df,
            cv_splits=cv_splits,
            random_state=42,
            enabled_views=enabled_views,
        ).fit(train_records, train_labels)
        probabilities = {
            dataset: model.predict_proba(records)[:, 1]
            for dataset, records in test_records.items()
        }
        output["variants"][name] = {
            "enabled_views": list(enabled_views),
            "metrics": {
                dataset: metrics(
                    [str(row["label"]) for row in tests[dataset]],
                    probabilities[dataset],
                    CONTRACT_THRESHOLD,
                )
                for dataset in tests
            },
            "oof_fusion_weights": {
                view: float(weight)
                for view, weight in zip(model.branch_names_, model.meta_classifier_.coef_[0])
            },
            "oof_splits": model.oof_splits_,
        }

    full = output["variants"]["full_multiview"]["metrics"]
    structure = output["variants"]["word_char_structure"]["metrics"]
    intent = output["variants"]["word_char_intent"]["metrics"]
    word_char = output["variants"]["word_char"]["metrics"]
    output["incremental_f1"] = {
        dataset: {
            "structure_over_word_char": float(structure[dataset]["f1"] - word_char[dataset]["f1"]),
            "intent_over_word_char": float(intent[dataset]["f1"] - word_char[dataset]["f1"]),
            "full_over_word_char": float(full[dataset]["f1"] - word_char[dataset]["f1"]),
        }
        for dataset in tests
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--hard-negative", type=Path, default=DEFAULT_HARD_NEGATIVE)
    parser.add_argument("--supplement", type=Path, default=DEFAULT_SUPPLEMENT)
    parser.add_argument("--chinese-test", type=Path, default=DEFAULT_CHINESE_TEST)
    parser.add_argument("--modern-test", type=Path, default=DEFAULT_MODERN_TEST)
    parser.add_argument("--boundary-test", type=Path, default=DEFAULT_BOUNDARY_TEST)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--word-max-features", type=int, default=50_000)
    parser.add_argument("--char-max-features", type=int, default=60_000)
    parser.add_argument("--min-df", type=int, default=2)
    parser.add_argument("--cv-splits", type=int, default=5)
    args = parser.parse_args()
    print(
        json.dumps(
            run(
                args.input,
                args.hard_negative,
                args.supplement,
                args.chinese_test,
                args.modern_test,
                args.boundary_test,
                args.summary,
                word_max_features=args.word_max_features,
                char_max_features=args.char_max_features,
                min_df=args.min_df,
                cv_splits=args.cv_splits,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
