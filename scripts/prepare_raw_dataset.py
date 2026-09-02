"""Build Member 1's pre-cleaning JSONL from public corpus containers.

This command uses the adjacent script-only corpus adapter. It is intentionally
separate from Member 2's production parser under ``src/parsers/``.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from email_loader import iter_corpus_records


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "raw"
DEFAULT_OUTPUT = ROOT / "data" / "processed" / "raw_emails.jsonl"
DEFAULT_STATS = ROOT / "data" / "manifests" / "raw_parse_summary.json"


def prepare(input_dir: Path, output_path: Path, stats_path: Path) -> dict[str, object]:
    """Write intermediate records and aggregate non-sensitive parse metrics."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    counts = Counter()
    warning_counts = Counter()
    failed = 0
    total = 0
    with output_path.open("w", encoding="utf-8") as output:
        for record in iter_corpus_records(input_dir):
            output.write(json.dumps(record.to_jsonable(), ensure_ascii=False) + "\n")
            total += 1
            counts[(record.source, record.label)] += 1
            for warning in record.parse_warnings:
                warning_counts[warning] += 1
            if not record.subject and not record.text_body:
                failed += 1
    summary = {
        "input_dir": input_dir.relative_to(ROOT).as_posix(),
        "output_path": output_path.relative_to(ROOT).as_posix(),
        "total_records": total,
        "empty_records": failed,
        "counts_by_source_label": {
            f"{source}:{label}": count for (source, label), count in sorted(counts.items())
        },
        "warning_counts": dict(sorted(warning_counts.items())),
    }
    stats_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--stats", type=Path, default=DEFAULT_STATS)
    args = parser.parse_args()
    summary = prepare(args.input_dir, args.output, args.stats)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
