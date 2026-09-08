"""Select a small human-review queue for weak intent labels."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build(input_path: Path, output_path: Path, summary_path: Path, *, limit: int = 300, seed: int = 42) -> dict[str, object]:
    rows = [json.loads(line) for line in input_path.open(encoding="utf-8") if line.strip()]
    rng = random.Random(seed)
    no_intent_legitimate = [row for row in rows if row.get("label") == "legitimate" and not row.get("intent_labels")]
    ambiguous = [row for row in rows if row.get("label") == "legitimate" and row.get("intent_labels") in (["social_pressure"], ["reply_or_data_request"])]
    rng.shuffle(no_intent_legitimate)
    rng.shuffle(ambiguous)
    selected = no_intent_legitimate[: max(1, limit * 2 // 3)] + ambiguous[: max(1, limit // 3)]
    selected = selected[:limit]
    queue = []
    for index, row in enumerate(selected):
        queue.append({
            "review_id": f"intent-review-{index:04d}",
            "id": row.get("id", ""),
            "source": row.get("source", ""),
            "label": row.get("label", ""),
            "subject": row.get("subject", ""),
            "text_body": row.get("text_body", ""),
            "weak_intent_labels": row.get("intent_labels", []),
            "manual_intent_labels": [],
            "review_status": "pending",
        })
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for row in queue:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    summary = {
        "input_path": input_path.relative_to(ROOT).as_posix(),
        "output_path": output_path.relative_to(ROOT).as_posix(),
        "queue_count": len(queue),
        "selection": {"no_intent_legitimate": min(len(no_intent_legitimate), max(1, limit * 2 // 3)), "ambiguous_legitimate": min(len(ambiguous), max(1, limit // 3))},
        "manual_annotation_required": True,
        "seed": seed,
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "data/v1.2/processed/intent_dataset.jsonl")
    parser.add_argument("--output", type=Path, default=ROOT / "data/v1.2/processed/intent_review_queue.jsonl")
    parser.add_argument("--summary", type=Path, default=ROOT / "data/v1.2/manifests/intent_review_queue_summary.json")
    parser.add_argument("--limit", type=int, default=300)
    args = parser.parse_args()
    print(json.dumps(build(args.input, args.output, args.summary, limit=args.limit), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
