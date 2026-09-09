"""Filter the LLMGen GPT corpus into a small, auditable V1.2 supplement."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.detection.intent_branch import infer_intent_labels
try:
    csv.field_size_limit(sys.maxsize)
except OverflowError:
    csv.field_size_limit(2**31 - 1)


def prepare(input_path: Path, output_path: Path, summary_path: Path, *, limit: int = 2000, seed: int = 42) -> dict[str, object]:
    rng = random.Random(seed)
    candidates: list[dict[str, object]] = []
    seen: set[str] = set()
    rejected = Counter()
    with input_path.open(encoding="utf-8-sig", newline="", errors="replace") as handle:
        for index, row in enumerate(csv.DictReader(handle)):
            label = str(row.get("label", "")).strip()
            content = str(row.get("content", "") or "").strip()
            if label not in {"0", "1"}:
                rejected["invalid_label"] += 1
                continue
            if not (120 <= len(content) <= 20_000):
                rejected["length"] += 1
                continue
            fingerprint = hashlib.sha256(content.casefold().encode("utf-8", errors="replace")).hexdigest()
            if fingerprint in seen:
                rejected["duplicate"] += 1
                continue
            seen.add(fingerprint)
            intent_labels, _ = infer_intent_labels("", content)
            candidates.append({
                "id": f"llmgen-gpt-{index:05d}",
                "source": "llmgen_gpt_2025",
                "label": "phishing" if label == "1" else "legitimate",
                "subject": content.splitlines()[0][:240] if content.splitlines() else "",
                "text_body": content,
                "content_fingerprint": fingerprint,
                "intent_labels": intent_labels,
                "intent_label_provenance": "weak_pattern_v1_on_llm_generated",
                "data_origin": "llm_generated",
            })
    by_label = {label: [row for row in candidates if row["label"] == label] for label in ("legitimate", "phishing")}
    per_label = limit // 2
    selected: list[dict[str, object]] = []
    for label in ("legitimate", "phishing"):
        rng.shuffle(by_label[label])
        selected.extend(by_label[label][:per_label])
    rng.shuffle(selected)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for row in selected:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    summary = {
        "input_path": str(input_path),
        "output_path": str(output_path),
        "input_candidates": len(candidates),
        "selected_records": len(selected),
        "label_counts": dict(sorted(Counter(row["label"] for row in selected).items())),
        "rejected_counts": dict(sorted(rejected.items())),
        "data_origin": "llm_generated",
        "role": "supplement_only; never independent final test",
        "seed": seed,
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "data/v1.2/raw_refs/llmgen_2025/GPT_Phishing_Email_dataset.csv")
    parser.add_argument("--output", type=Path, default=ROOT / "data/v1.2/processed/gpt_supplement_filtered.jsonl")
    parser.add_argument("--summary", type=Path, default=ROOT / "data/v1.2/manifests/gpt_supplement_summary.json")
    parser.add_argument("--limit", type=int, default=2000)
    args = parser.parse_args()
    print(json.dumps(prepare(args.input, args.output, args.summary, limit=args.limit), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
