"""Evaluate risky intent activation on a source-isolated human-labeled holdout."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from collections import Counter
from pathlib import Path

import joblib
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.detection.text_features import clean_email_text

RISKY_INTENTS = {
    "credential_request",
    "oauth_authorization",
    "payment_change",
    "external_document_action",
    "reply_or_data_request",
    "social_pressure",
}


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _known_fingerprints(path: Path) -> set[str]:
    fingerprints: set[str] = set()
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            stored = str(row.get("content_fingerprint", ""))
            if stored:
                fingerprints.add(stored)
            cleaned = clean_email_text(str(row.get("subject", "")), str(row.get("text_body", "")))
            fingerprints.add(_sha256(cleaned.model_text))
    return fingerprints


def _load_candidates(path: Path, known: set[str]) -> tuple[list[dict[str, object]], int]:
    candidates: list[dict[str, object]] = []
    overlap_count = 0
    with path.open(encoding="utf-8") as handle:
        for index, line in enumerate(handle):
            if not line.strip():
                continue
            source = json.loads(line)
            label = int(source["label"])
            if label not in {0, 1}:
                continue
            cleaned = clean_email_text("", str(source.get("text", "")))
            pair_fingerprint = _sha256(f"{cleaned.subject}\n{cleaned.text_body}")
            model_fingerprint = _sha256(cleaned.model_text)
            if pair_fingerprint in known or model_fingerprint in known:
                overlap_count += 1
                continue
            candidates.append(
                {
                    "id": f"difraud-test-{index:05d}",
                    "source": "difraud_phishing_test",
                    "subject": cleaned.subject,
                    "text_body": cleaned.text_body,
                    "human_binary_label": label,
                    "content_fingerprint": pair_fingerprint,
                    "model_text_fingerprint": model_fingerprint,
                }
            )
    return candidates, overlap_count


def _sample_balanced(rows: list[dict[str, object]], *, sample_size: int, seed: int) -> list[dict[str, object]]:
    if sample_size <= 0 or sample_size % 2:
        raise ValueError("sample_size must be a positive even number")
    rng = random.Random(seed)
    selected: list[dict[str, object]] = []
    for label in (0, 1):
        bucket = [row for row in rows if row["human_binary_label"] == label]
        rng.shuffle(bucket)
        required = sample_size // 2
        if len(bucket) < required:
            raise ValueError(f"not enough label={label} rows: required={required}, available={len(bucket)}")
        selected.extend(bucket[:required])
    rng.shuffle(selected)
    return selected


def evaluate(
    input_path: Path,
    training_path: Path,
    model_path: Path,
    thresholds_path: Path,
    output_data: Path,
    output_report: Path,
    *,
    sample_size: int = 100,
    seed: int = 1202,
) -> dict[str, object]:
    known = _known_fingerprints(training_path)
    candidates, overlap_count = _load_candidates(input_path, known)
    rows = _sample_balanced(candidates, sample_size=sample_size, seed=seed)
    model = joblib.load(model_path)
    threshold_report = json.loads(thresholds_path.read_text(encoding="utf-8"))
    thresholds = {name: float(value) for name, value in threshold_report["thresholds"].items()}
    inputs = [{"subject": row["subject"], "text_body": row["text_body"]} for row in rows]
    predicted_intents = model.predict_labels(inputs, thresholds)
    actual = [int(row["human_binary_label"]) for row in rows]
    predicted = [int(bool(set(labels) & RISKY_INTENTS)) for labels in predicted_intents]

    output_data.parent.mkdir(parents=True, exist_ok=True)
    with output_data.open("w", encoding="utf-8") as handle:
        for row, labels, binary_prediction in zip(rows, predicted_intents, predicted):
            handle.write(
                json.dumps(
                    {**row, "predicted_intents": labels, "risky_intent_prediction": binary_prediction},
                    ensure_ascii=False,
                )
                + "\n"
            )

    intent_counts = Counter(name for labels in predicted_intents for name in labels)
    matrix = confusion_matrix(actual, predicted, labels=[0, 1]).tolist()
    report: dict[str, object] = {
        "source_id": "difraud_phishing_test",
        "source_split": "upstream test split only",
        "source_label_provenance": "human-labeled binary deception benchmark",
        "source_release": "Hugging Face repository 2023; underlying phishing benchmark 2020",
        "license": "MIT dataset card",
        "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
        "input_git_blob_oid": "89258551a9892a21907c4aae82e3f7be9ce80adb",
        "sample_size": len(rows),
        "sample_seed": seed,
        "human_label_counts": dict(sorted(Counter(actual).items())),
        "training_fingerprint_count": len(known),
        "exact_overlap_dropped": overlap_count,
        "source_isolated_from_training": True,
        "isolation_scope": "upstream test split plus exact content/model-text fingerprint exclusion",
        "intent_exact_validation": False,
        "evaluation_target": "presence of any risky intent versus human binary deception label",
        "thresholds_provisional": bool(threshold_report.get("provisional", True)),
        "metrics": {
            "accuracy": float(accuracy_score(actual, predicted)),
            "precision": float(precision_score(actual, predicted, zero_division=0)),
            "recall": float(recall_score(actual, predicted, zero_division=0)),
            "f1": float(f1_score(actual, predicted, zero_division=0)),
            "confusion_matrix_tn_fp_fn_tp": [matrix[0][0], matrix[0][1], matrix[1][0], matrix[1][1]],
        },
        "predicted_intent_counts": dict(sorted(intent_counts.items())),
        "limitations": [
            "The upstream human labels are binary deception labels, not the seven V1.2 intent labels.",
            "The underlying benchmark predates the 2022-2026 freshness window and cannot validate modern attacks.",
            "Source and exact-fingerprint isolation cannot exclude latent campaign or semantic-template overlap.",
            "This measures risky-intent activation as a proxy and must not recalibrate thresholds or fusion weights.",
        ],
    }
    output_report.parent.mkdir(parents=True, exist_ok=True)
    output_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "data/v1.2/raw_refs/difraud_2020/phishing_test.jsonl")
    parser.add_argument("--training", type=Path, default=ROOT / "data/v1.2/processed/.intent_training_merged.jsonl")
    parser.add_argument("--model", type=Path, default=ROOT / "models/intent_branch_v1_2.joblib")
    parser.add_argument("--thresholds", type=Path, default=ROOT / "data/v1.2/manifests/intent_threshold_calibration.json")
    parser.add_argument("--output-data", type=Path, default=ROOT / "data/v1.2/processed/difraud_external_holdout.jsonl")
    parser.add_argument("--output-report", type=Path, default=ROOT / "data/v1.2/manifests/intent_external_holdout_eval.json")
    parser.add_argument("--sample-size", type=int, default=100)
    parser.add_argument("--seed", type=int, default=1202)
    args = parser.parse_args()
    result = evaluate(args.input, args.training, args.model, args.thresholds, args.output_data, args.output_report, sample_size=args.sample_size, seed=args.seed)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
