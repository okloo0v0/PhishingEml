"""Train and evaluate the V1.2 behavior-intent multilabel branch."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import joblib
import numpy as np
from sklearn.metrics import f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.detection.intent_branch import INTENT_ONTOLOGY, IntentBranch, multilabel_matrix


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def train(input_path: Path, model_path: Path, summary_path: Path, *, seed: int = 42) -> dict[str, object]:
    rows = _read_jsonl(input_path)
    if len(rows) < 4:
        raise ValueError("intent dataset is too small")
    train_rows, test_rows = train_test_split(rows, test_size=0.2, random_state=seed)
    model = IntentBranch(random_state=seed)
    model.fit(train_rows)
    probabilities = model.predict_proba(test_rows)
    actual = multilabel_matrix(test_rows)
    predicted = (probabilities >= 0.5).astype(np.uint8)
    metrics = {}
    for index, name in enumerate(INTENT_ONTOLOGY):
        metrics[name] = {
            "support": int(actual[:, index].sum()),
            "precision": float(precision_score(actual[:, index], predicted[:, index], zero_division=0)),
            "recall": float(recall_score(actual[:, index], predicted[:, index], zero_division=0)),
            "f1": float(f1_score(actual[:, index], predicted[:, index], zero_division=0)),
        }
    summary = {
        "model_version": "v1.2.0-intent-weak-v1",
        "input_path": _display_path(input_path),
        "model_path": _display_path(model_path),
        "train_count": len(train_rows),
        "test_count": len(test_rows),
        "intent_names": list(INTENT_ONTOLOGY),
        "label_provenance": "weak_pattern_v1",
        "split": "random 80/20; provisional only, not final generalization evidence",
        "metrics": metrics,
    }
    model_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_path)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "data/v1.2/processed/intent_dataset.jsonl")
    parser.add_argument("--model", type=Path, default=ROOT / "models/intent_branch_v1_2.joblib")
    parser.add_argument("--summary", type=Path, default=ROOT / "data/v1.2/manifests/intent_branch_training_summary.json")
    args = parser.parse_args()
    print(json.dumps(train(args.input, args.model, args.summary), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
