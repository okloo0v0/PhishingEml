"""Build a controlled V1.2 intent dataset from the existing cleaned corpus."""

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
from src.detection.text_features import clean_email_text

try:
    csv.field_size_limit(sys.maxsize)
except OverflowError:
    csv.field_size_limit(2**31 - 1)


def _fingerprint(subject: str, body: str) -> str:
    return hashlib.sha256(f"{subject}\n{body}".encode("utf-8", errors="replace")).hexdigest()


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _read_rows(path: Path, *, limit: int, seed: int) -> list[dict[str, str]]:
    rng = random.Random(seed)
    buckets: dict[str, list[dict[str, str]]] = {}
    with path.open(encoding="utf-8", newline="", errors="replace") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            label = str(row.get("label", ""))
            if label not in {"legitimate", "phishing"}:
                continue
            subject = str(row.get("subject", row.get("raw_subject", "")) or "")
            body = str(row.get("text_body", row.get("raw_text_body", "")) or "")
            cleaned = clean_email_text(subject, body)
            if not cleaned.model_text.strip():
                continue
            item = {
                "id": str(row.get("id", "")),
                "source": str(row.get("source", "")),
                "label": label,
                "subject": cleaned.subject,
                "text_body": cleaned.text_body,
                "content_fingerprint": _fingerprint(cleaned.subject, cleaned.text_body),
            }
            buckets.setdefault(label, []).append(item)
    per_label = limit // 2
    selected: list[dict[str, str]] = []
    for label in ("legitimate", "phishing"):
        items = buckets.get(label, [])
        rng.shuffle(items)
        selected.extend(items[:per_label])
    rng.shuffle(selected)
    seen: set[str] = set()
    output: list[dict[str, str]] = []
    for item in selected:
        fp = item["content_fingerprint"]
        if fp in seen:
            continue
        seen.add(fp)
        labels, provenance = infer_intent_labels(item["subject"], item["text_body"])
        output.append({**item, "intent_labels": labels, "intent_label_provenance": provenance})
    return output


def prepare(input_path: Path, output_path: Path, summary_path: Path, *, limit: int = 24_000, seed: int = 42) -> dict[str, object]:
    rows = _read_rows(input_path, limit=limit, seed=seed)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    label_counts = Counter(row["label"] for row in rows)
    intent_counts = Counter(name for row in rows for name in row["intent_labels"])
    summary = {
        "input_path": _display_path(input_path),
        "output_path": _display_path(output_path),
        "record_count": len(rows),
        "label_counts": dict(sorted(label_counts.items())),
        "intent_counts": dict(sorted(intent_counts.items())),
        "intent_label_provenance": "weak_pattern_v1",
        "sampling": "deterministic balanced label cap with content-fingerprint deduplication",
        "seed": seed,
        "limit": limit,
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "data/processed/emails.csv")
    parser.add_argument("--output", type=Path, default=ROOT / "data/v1.2/processed/intent_dataset.jsonl")
    parser.add_argument("--summary", type=Path, default=ROOT / "data/v1.2/manifests/intent_dataset_summary.json")
    parser.add_argument("--limit", type=int, default=24_000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    print(json.dumps(prepare(args.input, args.output, args.summary, limit=args.limit, seed=args.seed), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
