"""Generate production-compatible metadata for the V1.1 model artifact."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.generate_model_metadata import generate


def generate_v1_1() -> dict[str, object]:
    return generate(
        model_path=ROOT / "models" / "phishing_model_v1_1.joblib",
        training_path=ROOT / "data" / "manifests" / "model_training_summary_v1_1.json",
        evaluation_path=ROOT / "data" / "manifests" / "model_evaluation_summary_v1_1.json",
        split_path=ROOT / "data" / "manifests" / "split_summary.json",
        dedup_report_path=ROOT / "data" / "manifests" / "dedup_combined_report.json",
        metadata_path=ROOT / "models" / "model_meta_v1_1.json",
        experiments_path=ROOT / "docs" / "experiments.csv",
    )


if __name__ == "__main__":
    print(json.dumps(generate_v1_1(), ensure_ascii=False, indent=2))
