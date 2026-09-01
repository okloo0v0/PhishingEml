"""Convert selected supplemental CSV corpora into cleaned JSONL records."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.detection.text_features import clean_email_text

try:
    csv.field_size_limit(sys.maxsize)
except OverflowError:
    csv.field_size_limit(2**31 - 1)

RAW_DIR = ROOT / "data" / "raw" / "supplemental_zenodo"
DEFAULT_OUTPUT = ROOT / "data" / "processed" / "supplemental_cleaned_emails.jsonl"
DEFAULT_STATS = ROOT / "data" / "manifests" / "supplemental_summary.json"

SPECS = {
    "Nigerian_5.csv": {"source": "zenodo_nigerian_5", "mapping": {"0": "legitimate", "1": "phishing"}},
    "SpamAssasin.csv": {"source": "zenodo_spamassassin_csv", "mapping": {"0": "legitimate", "1": "spam_other"}},
    "Nigerian_Fraud.csv": {"source": "zenodo_nigerian_fraud", "mapping": {"1": "phishing"}},
    "Nazario.csv": {"source": "zenodo_nazario_csv", "mapping": {"1": "phishing"}},
}


def _source_hash(row: dict[str, str]) -> str:
    payload = {key: row.get(key, "") for key in ("sender", "receiver", "date", "subject", "body", "label")}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def prepare(files: list[Path], output: Path, stats: Path) -> dict[str, object]:
    """Read only subject/body fields and apply the shared text-v1 cleaner."""
    output.parent.mkdir(parents=True, exist_ok=True)
    stats.parent.mkdir(parents=True, exist_ok=True)
    counts: Counter[str] = Counter()
    warnings: Counter[str] = Counter()
    total = 0
    with output.open("w", encoding="utf-8") as destination:
        for path in files:
            spec = SPECS[path.name]
            with path.open(encoding="utf-8-sig", newline="") as source:
                for index, row in enumerate(csv.DictReader(source)):
                    label = spec["mapping"].get(str(row.get("label", "")).strip())
                    if label is None:
                        continue
                    cleaned = clean_email_text(row.get("subject", ""), row.get("body", ""))
                    record = {
                        "id": f"{spec['source']}-{index:06d}",
                        "source": spec["source"], "label": label,
                        "subject": cleaned.subject, "text_body": cleaned.text_body,
                        "source_hash": _source_hash(row), "parse_warnings": [],
                        **cleaned.to_jsonable(), "cleaning_warnings": list(cleaned.warnings),
                    }
                    destination.write(json.dumps(record, ensure_ascii=False) + "\n")
                    total += 1
                    counts[label] += 1
                    warnings.update(cleaned.warnings)
    summary = {
        "input_files": [path.relative_to(ROOT).as_posix() for path in files],
        "output_path": output.relative_to(ROOT).as_posix(), "feature_version": "text-v1",
        "total_records": total, "counts_by_label": dict(sorted(counts.items())),
        "warning_counts": dict(sorted(warnings.items())),
    }
    stats.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", action="append", dest="files", choices=sorted(SPECS))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--stats", type=Path, default=DEFAULT_STATS)
    args = parser.parse_args()
    files = [RAW_DIR / name for name in (args.files or list(SPECS))]
    print(json.dumps(prepare(files, args.output, args.stats), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
