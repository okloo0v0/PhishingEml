"""Deduplicate cleaned records before splitting the training dataset.

The script removes byte-identical mail through ``source_hash`` and then removes
exact duplicates of canonical ``text-v1`` model text.  It does not make a
semantic claim from approximate text similarity: candidate near-duplicates are
only measured and recorded for review.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "processed" / "cleaned_emails.jsonl"
DEFAULT_OUTPUT = ROOT / "data" / "processed" / "deduplicated_emails.jsonl"
DEFAULT_REPORT = ROOT / "data" / "manifests" / "dedup_report.json"
_TOKEN_RE = re.compile(r"(?u)\b\w{2,}\b")


def content_fingerprint(model_text: str) -> str:
    """Return the stable SHA-256 group key for canonical model text."""

    return hashlib.sha256(model_text.encode("utf-8")).hexdigest()


def _simhash(model_text: str) -> int:
    """Return a deterministic 64-bit token SimHash for audit-only matching."""

    weights = [0] * 64
    for token in _TOKEN_RE.findall(model_text.lower()):
        token_hash = int.from_bytes(
            hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest(), "big"
        )
        for bit in range(64):
            weights[bit] += 1 if token_hash & (1 << bit) else -1
    return sum(1 << bit for bit, weight in enumerate(weights) if weight >= 0)


def _hamming_distance(left: int, right: int) -> int:
    return (left ^ right).bit_count()


def _near_duplicate_audit(records: list[dict[str, object]]) -> dict[str, int]:
    """Count conservative SimHash candidate groups without altering records.

    A pair must share one 16-bit band and have Hamming distance <= 3. This is
    an intentionally incomplete candidate search, suitable for highlighting
    residual template risk rather than asserting semantic duplication.
    """

    buckets: dict[tuple[int, int], list[tuple[str, int]]] = defaultdict(list)
    for record in records:
        fingerprint = str(record["content_fingerprint"])
        value = _simhash(str(record.get("model_text", "")))
        for band in range(4):
            buckets[(band, (value >> (band * 16)) & 0xFFFF)].append((fingerprint, value))

    candidate_pairs: set[tuple[str, str]] = set()
    for bucket in buckets.values():
        for index, (left_id, left_hash) in enumerate(bucket):
            for right_id, right_hash in bucket[index + 1 :]:
                if left_id == right_id or _hamming_distance(left_hash, right_hash) > 3:
                    continue
                candidate_pairs.add(tuple(sorted((left_id, right_id))))

    candidate_nodes = {node for pair in candidate_pairs for node in pair}
    return {
        "near_duplicate_candidate_pairs": len(candidate_pairs),
        "near_duplicate_candidate_records": len(candidate_nodes),
    }


def _quality_key(record: dict[str, object]) -> tuple[int, int, str]:
    """Choose a reproducible representative without using label information."""

    warnings = record.get("parse_warnings", [])
    return (
        len(warnings) if isinstance(warnings, list) else 0,
        -int(record.get("original_chars", 0)),
        str(record.get("id", "")),
    )


def _representatives_by_key(
    records: Iterable[dict[str, object]], key_name: str
) -> tuple[list[dict[str, object]], int, int]:
    groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    for record in records:
        groups[str(record[key_name])].append(record)
    representatives = [min(group, key=_quality_key) for group in groups.values()]
    duplicate_groups = sum(len(group) > 1 for group in groups.values())
    removed = sum(len(group) - 1 for group in groups.values())
    return sorted(representatives, key=lambda record: str(record["id"])), duplicate_groups, removed


def deduplicate(records: list[dict[str, object]]) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Return safe representatives and a report suitable for experiment records."""

    for record in records:
        record["content_fingerprint"] = content_fingerprint(str(record.get("model_text", "")))

    raw_unique, raw_duplicate_groups, raw_removed = _representatives_by_key(records, "source_hash")
    by_fingerprint: dict[str, list[dict[str, object]]] = defaultdict(list)
    for record in raw_unique:
        by_fingerprint[str(record["content_fingerprint"])].append(record)

    retained: list[dict[str, object]] = []
    content_duplicate_groups = 0
    content_removed = 0
    conflict_groups = 0
    conflict_records = 0
    for fingerprint, group in by_fingerprint.items():
        labels = {str(record.get("label", "")) for record in group}
        if len(labels) > 1:
            conflict_groups += 1
            conflict_records += len(group)
            continue
        if len(group) > 1:
            content_duplicate_groups += 1
            content_removed += len(group) - 1
        representative = min(group, key=_quality_key).copy()
        # Exact normalized text forms the no-cross-split template group.
        representative["dedup_group"] = fingerprint
        retained.append(representative)

    retained.sort(key=lambda record: str(record["id"]))
    near_duplicate_audit = _near_duplicate_audit(retained)
    report = {
        "input_records": len(records),
        "retained_records": len(retained),
        "removed_records": len(records) - len(retained),
        "raw_hash_duplicate_groups": raw_duplicate_groups,
        "raw_hash_removed": raw_removed,
        "content_duplicate_groups": content_duplicate_groups,
        "content_duplicate_removed": content_removed,
        "label_conflict_groups_dropped": conflict_groups,
        "label_conflict_records_dropped": conflict_records,
        "counts_by_source_label": {
            f"{source}:{label}": count
            for (source, label), count in sorted(
                Counter((str(record.get("source", "")), str(record.get("label", ""))) for record in retained).items()
            )
        },
        "leakage_group": "dedup_group is the SHA-256 of canonical text-v1 model_text",
        **near_duplicate_audit,
        "near_duplicate_policy": "SimHash candidates are audit-only and are not deleted. Semantic near-duplicate and thread grouping require sender/thread metadata from the production parser.",
    }
    return retained, report


def prepare(input_paths: list[Path], output_path: Path, report_path: Path) -> dict[str, object]:
    """Load JSONL, write deduplicated JSONL, and persist the audit report."""

    records: list[dict[str, object]] = []
    for input_path in input_paths:
        records.extend(
            json.loads(line)
            for line in input_path.open(encoding="utf-8")
            if line.strip()
        )
    retained, report = deduplicate(records)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as output:
        for record in retained:
            output.write(json.dumps(record, ensure_ascii=False) + "\n")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, action="append")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    input_paths = args.input or [DEFAULT_INPUT]
    print(json.dumps(prepare(input_paths, args.output, args.report), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
