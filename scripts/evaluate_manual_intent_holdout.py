"""Evaluate the intent model on manually adjudicated external rows."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import joblib
import numpy as np
from sklearn.metrics import f1_score, precision_score, recall_score

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.detection.intent_branch import INTENT_ONTOLOGY, multilabel_matrix

INTENT_NAMES = tuple(INTENT_ONTOLOGY)


def evaluate(model_path: Path, test_path: Path, thresholds_path: Path, report_path: Path) -> dict[str, object]:
    rows = [json.loads(line) for line in test_path.open(encoding="utf-8") if line.strip()]
    model = joblib.load(model_path)
    calibration = json.loads(thresholds_path.read_text(encoding="utf-8"))
    thresholds = {name: float(value) for name, value in calibration["thresholds"].items()}
    actual = multilabel_matrix(rows)
    predicted_labels = model.predict_labels(rows, thresholds)
    predicted = np.zeros_like(actual)
    for row_index, labels in enumerate(predicted_labels):
        for label in labels:
            if label in INTENT_ONTOLOGY:
                predicted[row_index, INTENT_NAMES.index(label)] = 1
    exact = float(np.mean(np.all(actual == predicted, axis=1)))
    result = {
        "model_path": str(model_path),
        "test_path": str(test_path),
        "test_count": len(rows),
        "training_action": "none; evaluate existing model only",
        "label_provenance": "manual_adjudication_difraud_v1",
        "thresholds_provisional": bool(calibration.get("provisional", True)),
        "exact_match": exact,
        "micro_precision": float(precision_score(actual, predicted, average="micro", zero_division=0)),
        "micro_recall": float(recall_score(actual, predicted, average="micro", zero_division=0)),
        "micro_f1": float(f1_score(actual, predicted, average="micro", zero_division=0)),
        "per_intent_f1": {name: float(f1_score(actual[:, i], predicted[:, i], zero_division=0)) for i, name in enumerate(INTENT_NAMES)},
        "note": "All rows are an independent evaluation set for the existing model; no rows were used for retraining or threshold fitting.",
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=ROOT / "models/intent_branch_v1_2_manual.joblib")
    parser.add_argument("--test", type=Path, default=ROOT / "data/v1.2/processed/difraud_manual_intents_test.jsonl")
    parser.add_argument("--thresholds", type=Path, default=ROOT / "data/v1.2/manifests/intent_threshold_calibration.json")
    parser.add_argument("--report", type=Path, default=ROOT / "data/v1.2/manifests/intent_manual_holdout_eval.json")
    args = parser.parse_args()
    print(json.dumps(evaluate(args.model, args.test, args.thresholds, args.report), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
