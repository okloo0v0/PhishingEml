"""Validate labels and create leakage-safe train/valid/test datasets."""

from __future__ import annotations

import argparse
import csv
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "processed" / "deduplicated_emails_combined.jsonl"
DEFAULT_OUTPUT = ROOT / "data" / "processed" / "emails.csv"
DEFAULT_CROSS_SOURCE = ROOT / "data" / "processed" / "cross_source_test.jsonl"
DEFAULT_HARD_NEGATIVE = ROOT / "data" / "processed" / "hard_negative_emails.jsonl"
DEFAULT_SUMMARY = ROOT / "data" / "manifests" / "split_summary.json"
DEFAULT_DROPS = ROOT / "data" / "manifests" / "label_drop_report.json"

ALLOWED_LABELS = {"phishing", "legitimate", "spam_other"}
BINARY_LABELS = {"phishing", "legitimate"}
RANDOM_STATE = 42
CROSS_SOURCE_FRACTION = 0.10


def _load(path: Path) -> list[dict[str, object]]:
    with path.open(encoding="utf-8") as source:
        return [json.loads(line) for line in source if line.strip()]


def _group_split(records: list[dict[str, object]], seed: int = RANDOM_STATE) -> dict[str, list[dict[str, object]]]:
    """Create deterministic stratified splits while keeping dedup groups intact."""

    groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    for record in records:
        groups[str(record["dedup_group"])].append(record)
    group_items = list(groups.items())
    if any(len({str(item.get("label")) for item in members}) > 1 for _, members in group_items):
        raise ValueError("a dedup_group contains conflicting labels")
    indices = list(range(len(group_items)))
    labels = [str(group_items[index][1][0]["label"]) for index in indices]
    try:
        train_idx, test_idx = train_test_split(
            indices, test_size=0.15, random_state=seed, stratify=labels
        )
        train_labels = [labels[index] for index in train_idx]
        train_idx, valid_idx = train_test_split(
            train_idx,
            test_size=0.15 / 0.85,
            random_state=seed,
            stratify=train_labels,
        )
    except ValueError as exc:
        raise ValueError(f"unable to create stratified splits: {exc}") from exc

    def flatten(selected: list[int]) -> list[dict[str, object]]:
        return [record for index in selected for record in group_items[index][1]]

    result = {"train": flatten(train_idx), "valid": flatten(valid_idx), "test": flatten(test_idx)}
    _assert_no_group_overlap(result)
    return result


def _assert_no_group_overlap(splits: dict[str, list[dict[str, object]]]) -> None:
    seen: dict[str, str] = {}
    for split_name, records in splits.items():
        for record in records:
            group = str(record["dedup_group"])
            previous = seen.setdefault(group, split_name)
            if previous != split_name:
                raise ValueError(f"dedup_group appears in both {previous} and {split_name}")


def _select_cross_source(records: list[dict[str, object]], fraction: float) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Hold out a source-balanced sample without using the labels across groups."""

    grouped: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for record in records:
        grouped[(str(record["source"]), str(record["label"]))].append(record)
    rng = random.Random(RANDOM_STATE)
    held_out: list[dict[str, object]] = []
    remaining: list[dict[str, object]] = []
    for key in sorted(grouped):
        members = sorted(grouped[key], key=lambda item: str(item["id"]))
        rng.shuffle(members)
        count = max(1, int(len(members) * fraction)) if len(members) >= 10 else 0
        held_out.extend(members[:count])
        remaining.extend(members[count:])
    return held_out, remaining


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as output:
        for record in sorted(records, key=lambda item: str(item["id"])):
            output.write(json.dumps(record, ensure_ascii=False) + "\n")


def _write_csv(path: Path, splits: dict[str, list[dict[str, object]]]) -> None:
    fields = [
        "id", "source", "label", "subject", "text_body", "model_text",
        "source_hash", "content_fingerprint", "dedup_group", "split",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for split_name in ("train", "valid", "test"):
            for record in sorted(splits[split_name], key=lambda item: str(item["id"])):
                writer.writerow({field: record.get(field, "") for field in fields[:-1]} | {"split": split_name})


def _counts(records: list[dict[str, object]]) -> dict[str, int]:
    return dict(sorted(Counter(str(record.get("label", "")) for record in records).items()))


def prepare(
    input_path: Path,
    output_path: Path,
    cross_source_path: Path,
    hard_negative_path: Path,
    summary_path: Path,
    drops_path: Path,
) -> dict[str, object]:
    records = _load(input_path)
    valid: list[dict[str, object]] = []
    hard_negative: list[dict[str, object]] = []
    drop_counts: Counter[str] = Counter()
    for record in records:
        label = str(record.get("label", ""))
        if label not in ALLOWED_LABELS:
            drop_counts["invalid_label"] += 1
            continue
        if not str(record.get("model_text", "")).strip():
            drop_counts["empty_model_text"] += 1
            continue
        if not str(record.get("dedup_group", "")).strip():
            drop_counts["missing_dedup_group"] += 1
            continue
        if label == "spam_other":
            hard_negative.append(record)
        else:
            valid.append(record)

    cross_source, remaining = _select_cross_source(valid, CROSS_SOURCE_FRACTION)
    splits = _group_split(remaining)
    _write_csv(output_path, splits)
    _write_jsonl(cross_source_path, cross_source)
    _write_jsonl(hard_negative_path, hard_negative)

    all_split_records = [record for values in splits.values() for record in values]
    summary = {
        "input_path": input_path.relative_to(ROOT).as_posix(),
        "output_path": output_path.relative_to(ROOT).as_posix(),
        "cross_source_test_path": cross_source_path.relative_to(ROOT).as_posix(),
        "hard_negative_path": hard_negative_path.relative_to(ROOT).as_posix(),
        "random_state": RANDOM_STATE,
        "split_policy": "70/15/15 stratified by label after a 10% source-label-balanced cross-source holdout",
        "total_input_records": len(records),
        "binary_records_after_validation": len(valid),
        "hard_negative_records": len(hard_negative),
        "cross_source_test_records": len(cross_source),
        "split_counts": {
            split: {"records": len(items), "labels": _counts(items)}
            for split, items in splits.items()
        },
        "source_counts": {
            split: dict(sorted(Counter(str(item["source"]) for item in items).items()))
            for split, items in splits.items()
        },
        "cross_source_counts": {
            f"{source}:{label}": count
            for (source, label), count in sorted(
                Counter((str(item["source"]), str(item["label"])) for item in cross_source).items()
            )
        },
        "hard_negative_counts": _counts(hard_negative),
        "empty_or_non_ascii": {
            "empty_model_text_after_validation": sum(not str(item["model_text"]).strip() for item in all_split_records),
            "non_ascii_records": sum(any(ord(char) > 127 for char in str(item["model_text"])) for item in all_split_records),
        },
        "dedup_group_overlap_check": "passed",
        "drop_counts": dict(sorted(drop_counts.items())),
        "limitations": [
            "Cross-source test is source-label-balanced sampling, not a strict leave-one-source-out evaluation.",
            "Thread and sender grouping remain unavailable because the intermediate records do not contain reliable parsed header metadata.",
        ],
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    drops_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    drops_path.write_text(json.dumps({"drop_counts": dict(sorted(drop_counts.items())), "allowed_labels": sorted(ALLOWED_LABELS)}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--cross-source", type=Path, default=DEFAULT_CROSS_SOURCE)
    parser.add_argument("--hard-negative", type=Path, default=DEFAULT_HARD_NEGATIVE)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--drops", type=Path, default=DEFAULT_DROPS)
    args = parser.parse_args()
    print(json.dumps(prepare(args.input, args.output, args.cross_source, args.hard_negative, args.summary, args.drops), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
