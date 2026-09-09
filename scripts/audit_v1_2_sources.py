"""Create a local, offline audit summary for downloaded V1.2 datasets."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = ROOT / "data" / "v1.2" / "raw_refs"
DEFAULT_OUTPUT = ROOT / "data" / "v1.2" / "manifests" / "source_audit.csv"

csv.field_size_limit(10_000_000)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _audit_csv(path: Path) -> dict[str, object]:
    labels: dict[str, int] = {}
    rows = 0
    fields: list[str] = []
    null_label_rows = 0
    with path.open(encoding="utf-8-sig", newline="", errors="replace") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        label_field = "label" if "label" in fields else ("Email Type" if "Email Type" in fields else None)
        for row in reader:
            rows += 1
            label = (row.get(label_field) or "").strip() if label_field else ""
            if not label:
                null_label_rows += 1
            labels[label or "<missing>"] = labels.get(label or "<missing>", 0) + 1
    return {
        "file_type": "csv",
        "row_count": rows,
        "fields": json.dumps(fields, ensure_ascii=True),
        "label_counts": json.dumps(labels, ensure_ascii=True, sort_keys=True),
        "missing_label_rows": null_label_rows,
        "sha256": _sha256(path),
    }


def _audit_jsonl(path: Path) -> dict[str, object]:
    rows = 0
    labels: dict[str, int] = {}
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            rows += 1
            label = str(row.get("label", "<missing>"))
            labels[label] = labels.get(label, 0) + 1
    return {
        "file_type": "jsonl",
        "row_count": rows,
        "fields": json.dumps(["text", "label"]),
        "label_counts": json.dumps(labels, sort_keys=True),
        "missing_label_rows": labels.get("<missing>", 0),
        "sha256": _sha256(path),
    }


def audit(output: Path = DEFAULT_OUTPUT) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for path in sorted(RAW_ROOT.rglob("*")):
        if not path.is_file() or path.name.endswith(".part"):
            continue
        relative = path.relative_to(ROOT).as_posix()
        record: dict[str, object] = {
            "local_path": relative,
            "size_bytes": path.stat().st_size,
            "audit_status": "inspected",
            "data_origin": "unknown",
            "recommended_role": "review_required",
            "notes": "",
        }
        if path.suffix.lower() == ".csv":
            record.update(_audit_csv(path))
            if "llmgen_2025" in relative:
                record.update(data_origin="llm_generated", recommended_role="auxiliary_training_or_robustness")
                record["notes"] = "Do not use as an independent final test set; inspect synthetic artifacts."
            elif "figshare_2024" in relative:
                record.update(data_origin="historical_public_email_corpus", recommended_role="candidate_training_after_dedup")
                record["notes"] = "2024 republication; sample dates are historical and must be measured before temporal split."
            elif "twente_2024" in relative:
                record.update(data_origin="mixed_real_and_artificial", recommended_role="validation_only")
                record["notes"] = "2,000 labeled full-text emails; mixed real and artificial; do not use for training."
        elif path.suffix.lower() == ".jsonl":
            record.update(_audit_jsonl(path))
            if "difraud_2020" in relative:
                record.update(data_origin="human_labeled_real_user_email", recommended_role="source_isolated_validation_only")
                record["notes"] = "Upstream test split; 2020 benchmark outside freshness window; never use for training."
        elif "epvme_2023" in relative:
            record.update(file_type="text", sha256=_sha256(path), recommended_role="protocol_attack_audit_only")
            record["data_origin"] = "constructed_adversarial_corpus"
            record["notes"] = "README/LICENSE only; do not download the EML archive in Phase 1."
        records.append(record)
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = ["local_path", "file_type", "size_bytes", "row_count", "fields", "label_counts", "missing_label_rows", "sha256", "audit_status", "data_origin", "recommended_role", "notes"]
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    records = audit(args.output)
    print(f"audited_files={len(records)}; output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
