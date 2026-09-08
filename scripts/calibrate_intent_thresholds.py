"""Calibrate provisional intent thresholds on fixed manually labeled boundaries."""

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

from scripts.run_intent_boundary_eval import CASES


def calibrate(model_path: Path, output: Path) -> dict[str, object]:
    model = joblib.load(model_path)
    rows = [{"subject": subject, "text_body": body} for _, subject, body, _ in CASES]
    probabilities = model.predict_proba(rows)
    actual = np.asarray([[1 if name in expected else 0 for name in model.classes_] for _, _, _, expected in CASES], dtype=np.uint8)
    thresholds: dict[str, float] = {}
    metrics: dict[str, dict[str, float | int]] = {}
    for index, name in enumerate(model.classes_):
        support = int(actual[:, index].sum())
        negative_support = int(len(actual) - support)
        best = (0.5, -1.0, 0.0, 0.0)
        for threshold in np.arange(0.20, 0.91, 0.05):
            predicted = probabilities[:, index] >= threshold
            precision = float(precision_score(actual[:, index], predicted, zero_division=0))
            recall = float(recall_score(actual[:, index], predicted, zero_division=0))
            score = float(f1_score(actual[:, index], predicted, zero_division=0))
            candidate = (round(float(threshold), 2), score, precision, recall)
            if precision >= 0.80 and (score > best[1] or (score == best[1] and candidate[0] > best[0])):
                best = candidate
        thresholds[name] = best[0]
        metrics[name] = {"positive_support": support, "negative_support": negative_support, "precision": best[2], "recall": best[3], "f1": max(0.0, best[1])}
    default_predictions = probabilities >= 0.5
    calibrated_predictions = np.asarray(
        [probabilities[:, index] >= thresholds[name] for index, name in enumerate(model.classes_)]
    ).T
    default_exact_match_rate = float(np.all(default_predictions == actual, axis=1).mean())
    calibrated_exact_match_rate = float(np.all(calibrated_predictions == actual, axis=1).mean())
    accepted = calibrated_exact_match_rate >= default_exact_match_rate
    result = {
        "model_path": str(model_path),
        "calibration_set": "fixed manually labeled boundary cases",
        "case_count": len(CASES),
        "thresholds": thresholds,
        "probability_source": "final predict_proba output, including semantic guardrails",
        "selection_policy": "maximize F1 subject to precision >= 0.80; prefer higher threshold on ties",
        "metrics": metrics,
        "default_exact_match_rate": default_exact_match_rate,
        "calibrated_exact_match_rate": calibrated_exact_match_rate,
        "accepted_for_intent_decision": accepted,
        "provisional": True,
        "use_as_final_fusion_weight": False,
        "note": "Do not promote thresholds or fusion weights until a larger human-labeled, source-separated set is available.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=ROOT / "models/intent_branch_v1_2.joblib")
    parser.add_argument("--output", type=Path, default=ROOT / "data/v1.2/manifests/intent_threshold_calibration.json")
    args = parser.parse_args()
    print(json.dumps(calibrate(args.model, args.output), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
