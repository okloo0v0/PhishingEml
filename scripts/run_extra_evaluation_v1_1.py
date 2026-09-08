"""Evaluate V1.1 on unseen Ling hard negatives and synthetic boundary cases."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

import joblib
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.evaluate_model_v1_1 import CONTRACT_THRESHOLD, metrics
from scripts.run_extra_evaluation import TRAIN_PATH, _load_ling, _load_synthetic
from src.detection.multiview_features import records_from_rows


DEFAULT_MODEL = ROOT / "models" / "phishing_model_v1_1.joblib"
DEFAULT_BASELINE = ROOT / "models" / "phishing_model.joblib"
DEFAULT_PREDICTIONS = ROOT / "data" / "processed" / "extra_evaluation_predictions_v1_1.csv"
DEFAULT_SUMMARY = ROOT / "data" / "manifests" / "extra_evaluation_summary_v1_1.json"


def _probabilities(model, rows: list[dict[str, object]]) -> np.ndarray:
    classes = [str(value) for value in model.classes_]
    return model.predict_proba(records_from_rows(rows))[:, classes.index("phishing")]


def _baseline_probabilities(model, rows: list[dict[str, object]]) -> np.ndarray:
    return model.predict_proba([str(row["model_text"]) for row in rows])[:, 1]


def run(
    model_path: Path = DEFAULT_MODEL,
    baseline_path: Path | None = DEFAULT_BASELINE,
    predictions_path: Path = DEFAULT_PREDICTIONS,
    summary_path: Path = DEFAULT_SUMMARY,
) -> dict[str, object]:
    with TRAIN_PATH.open(encoding="utf-8") as source:
        known_fingerprints = {
            json.loads(line)["content_fingerprint"] for line in source if line.strip()
        }
    ling = [row for row in _load_ling() if row["content_fingerprint"] not in known_fingerprints]
    synthetic = [
        row for row in _load_synthetic() if row["content_fingerprint"] not in known_fingerprints
    ]
    model = joblib.load(model_path)
    collections = {"ling_hard_negative": ling, "synthetic_binary": synthetic}
    probabilities = {name: _probabilities(model, rows) for name, rows in collections.items()}
    synthetic_metrics = metrics(
        [str(row["label"]) for row in synthetic],
        probabilities["synthetic_binary"],
        CONTRACT_THRESHOLD,
    )
    ling_probabilities = probabilities["ling_hard_negative"]
    summary: dict[str, object] = {
        "model_version": "v1.1.0",
        "threshold": CONTRACT_THRESHOLD,
        "source_overlap": {
            "ling_unseen": len(ling),
            "synthetic_unseen": len(synthetic),
        },
        "ling_hard_negative": {
            "support": len(ling),
            "spam_other_count": sum(row["label"] == "spam_other" for row in ling),
            "phishing_rate": float(np.mean(ling_probabilities >= CONTRACT_THRESHOLD)),
            "mean_phishing_probability": float(np.mean(ling_probabilities)),
            "max_phishing_probability": float(np.max(ling_probabilities)),
            "predicted_counts": dict(
                sorted(
                    Counter(
                        "phishing" if value >= CONTRACT_THRESHOLD else "legitimate"
                        for value in ling_probabilities
                    ).items()
                )
            ),
        },
        "synthetic_binary": {"metrics": synthetic_metrics},
    }
    if baseline_path is not None and baseline_path.is_file():
        baseline = joblib.load(baseline_path)
        baseline_ling = _baseline_probabilities(baseline, ling)
        baseline_synthetic = _baseline_probabilities(baseline, synthetic)
        summary["baseline_same_set"] = {
            "ling_phishing_rate": float(np.mean(baseline_ling >= CONTRACT_THRESHOLD)),
            "synthetic_metrics": metrics(
                [str(row["label"]) for row in synthetic],
                baseline_synthetic,
                CONTRACT_THRESHOLD,
            ),
        }

    output_rows: list[dict[str, object]] = []
    for dataset, rows in collections.items():
        for row, probability in zip(rows, probabilities[dataset]):
            output_rows.append(
                {
                    "dataset": dataset,
                    "id": row["id"],
                    "source": row["source"],
                    "label": row["label"],
                    "predicted_label": "phishing" if probability >= CONTRACT_THRESHOLD else "legitimate",
                    "phishing_probability": f"{float(probability):.10f}",
                }
            )
    predictions_path.parent.mkdir(parents=True, exist_ok=True)
    with predictions_path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(output_rows[0]))
        writer.writeheader()
        writer.writerows(output_rows)
    summary["predictions_path"] = predictions_path.relative_to(ROOT).as_posix()
    summary["safety_note"] = (
        "Ling labels remain legitimate/spam_other for reporting; no spam sample is relabeled as phishing. "
        "Exact training fingerprints are excluded."
    )
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--predictions", type=Path, default=DEFAULT_PREDICTIONS)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    args = parser.parse_args()
    print(json.dumps(run(args.model, args.baseline, args.predictions, args.summary), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
