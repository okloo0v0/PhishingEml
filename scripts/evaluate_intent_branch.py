"""Evaluate intent branch on a synthetic-free holdout from the base corpus."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.detection.intent_branch import INTENT_ONTOLOGY, IntentBranch, multilabel_matrix


def _read(path: Path) -> list[dict[str, object]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def evaluate(base_path: Path, supplement_path: Path | None, output: Path, *, seed: int = 42) -> dict[str, object]:
    base_rows = _read(base_path)
    supplement_rows = _read(supplement_path) if supplement_path is not None else []
    train_rows, test_rows = train_test_split(base_rows, test_size=0.2, random_state=seed)
    model = IntentBranch(random_state=seed)
    model.fit(train_rows + supplement_rows)
    actual = multilabel_matrix(test_rows)
    probabilities = model.predict_proba(test_rows)
    predicted = (probabilities >= 0.5).astype(np.uint8)
    metrics = {}
    for index, name in enumerate(INTENT_ONTOLOGY):
        metrics[name] = {
            "support": int(actual[:, index].sum()),
            "precision": float(precision_score(actual[:, index], predicted[:, index], zero_division=0)),
            "recall": float(recall_score(actual[:, index], predicted[:, index], zero_division=0)),
            "f1": float(f1_score(actual[:, index], predicted[:, index], zero_division=0)),
        }
    result = {
        "model_version": "v1.2.0-intent-weak-plus-synthetic",
        "base_path": _display_path(base_path),
        "supplement_path": _display_path(supplement_path) if supplement_path else None,
        "train_base_count": len(train_rows),
        "train_supplement_count": len(supplement_rows),
        "test_base_count": len(test_rows),
        "test_contains_synthetic": False,
        "split": "base corpus 80/20 random holdout; synthetic rows train-only",
        "seed": seed,
        "metrics": metrics,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=ROOT / "data/v1.2/processed/intent_dataset.jsonl")
    parser.add_argument("--supplement", type=Path, default=ROOT / "data/v1.2/processed/intent_supplement_synthetic.jsonl")
    parser.add_argument("--output", type=Path, default=ROOT / "data/v1.2/manifests/intent_branch_real_holdout_summary.json")
    args = parser.parse_args()
    supplement = args.supplement if args.supplement.exists() else None
    print(json.dumps(evaluate(args.base, supplement, args.output), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
