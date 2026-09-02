"""Apply canonical text-v1 cleaning to the pre-cleaning JSONL."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.detection.text_features import (
    FEATURE_VERSION,
    MODEL_TEXT_MAX_CHARS,
    clean_email_text,
)

DEFAULT_INPUT = ROOT / "data" / "processed" / "raw_emails.jsonl"
DEFAULT_OUTPUT = ROOT / "data" / "processed" / "cleaned_emails.jsonl"
DEFAULT_STATS = ROOT / "data" / "manifests" / "clean_summary.json"

def prepare(input_path: Path, output_path: Path, stats_path: Path) -> dict[str, object]:
    """Clean every record while preserving source, label and provenance fields."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    warning_counts: Counter[str] = Counter()
    label_counts: Counter[str] = Counter()
    replacement_counts: Counter[str] = Counter()
    total = 0
    with input_path.open(encoding="utf-8") as source, output_path.open("w", encoding="utf-8") as output:
        for line in source:
            if not line.strip():
                continue
            record = json.loads(line)
            cleaned = clean_email_text(record.get("subject", ""), record.get("text_body", ""))
            result = {**record, **cleaned.to_jsonable(), "cleaning_warnings": list(cleaned.warnings)}
            output.write(json.dumps(result, ensure_ascii=False) + "\n")
            total += 1
            label_counts[str(record.get("label", ""))] += 1
            for warning in cleaned.warnings:
                warning_counts[warning] += 1
            replacement_counts["emails"] += cleaned.email_replacements
            replacement_counts["urls"] += cleaned.url_replacements
            replacement_counts["numbers"] += cleaned.number_replacements
    summary = {
        "input_path": input_path.relative_to(ROOT).as_posix(),
        "output_path": output_path.relative_to(ROOT).as_posix(),
        "feature_version": FEATURE_VERSION,
        "max_text_chars": MODEL_TEXT_MAX_CHARS,
        "total_records": total,
        "counts_by_label": dict(sorted(label_counts.items())),
        "replacement_counts": dict(sorted(replacement_counts.items())),
        "warning_counts": dict(sorted(warning_counts.items())),
    }
    stats_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--stats", type=Path, default=DEFAULT_STATS)
    args = parser.parse_args()
    print(json.dumps(prepare(args.input, args.output, args.stats), ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
