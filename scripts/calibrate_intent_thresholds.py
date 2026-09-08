"""Calibrate provisional intent thresholds on fixed manually labeled boundaries."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import joblib
import numpy as np
from sklearn.metrics import f1_score

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
    scores: dict[str, float] = {}
    for index, name in enumerate(model.classes_):
        best = (0.5, -1.0)
        for threshold in np.arange(0.30, 0.91, 0.05):
            score = float(f1_score(actual[:, index], probabilities[:, index] >= threshold, zero_division=0))
            if score > best[1]:
                best = (round(float(threshold), 2), score)
        thresholds[name] = best[0]
        scores[name] = best[1]
    result = {
        "model_path": str(model_path),
        "calibration_set": "fixed manually labeled boundary cases",
        "case_count": len(CASES),
        "thresholds": thresholds,
        "f1_on_calibration_set": scores,
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
