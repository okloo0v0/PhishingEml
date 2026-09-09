"""Audit the V1/V1.1/V1.2 data archive layout without network access."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_CATALOG = ROOT / "data" / "v1.2" / "manifests" / "source_catalog.csv"
DEFAULT_ARCHIVE_CATALOG = ROOT / "data" / "v1.2" / "manifests" / "archive_catalog.csv"

SOURCE_FIELDS = {
    "source_id", "source_type", "language", "attack_scope", "source_url",
    "license_status", "local_path", "status", "downloaded_at", "sha256", "notes",
}
ARCHIVE_FIELDS = {"version", "logical_role", "canonical_path", "archive_path", "copy_policy", "status"}
ALLOWED_LICENSE_STATUS = {"pending", "review_required", "verified"}
ALLOWED_STATUS = {"planned", "downloaded", "existing", "failed", "available", "rejected"}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        fields = set(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
        if any(None in row for row in rows):
            raise ValueError(f"malformed CSV row contains extra fields: {path}")
        return rows, fields


def audit(source_catalog: Path = DEFAULT_SOURCE_CATALOG, archive_catalog: Path = DEFAULT_ARCHIVE_CATALOG) -> dict[str, int]:
    source_rows, source_fields = _read_csv(source_catalog)
    archive_rows, archive_fields = _read_csv(archive_catalog)
    if source_fields != SOURCE_FIELDS:
        raise ValueError(f"source catalog fields mismatch: {sorted(source_fields)}")
    if archive_fields != ARCHIVE_FIELDS:
        raise ValueError(f"archive catalog fields mismatch: {sorted(archive_fields)}")
    source_ids: set[str] = set()
    for row in source_rows:
        source_id = row["source_id"].strip()
        if not source_id or source_id in source_ids:
            raise ValueError(f"duplicate or empty source_id: {source_id!r}")
        source_ids.add(source_id)
        parsed = urlparse(row["source_url"])
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(f"source_url must be absolute HTTP(S): {row['source_url']!r}")
        if row["license_status"] not in ALLOWED_LICENSE_STATUS:
            raise ValueError(f"unsupported license_status: {row['license_status']!r}")
        if row["status"] not in ALLOWED_STATUS:
            raise ValueError(f"unsupported source status: {row['status']!r}")
        local_path = Path(row["local_path"])
        if local_path.is_absolute() or ".." in local_path.parts or local_path.parts[:3] != ("data", "v1.2", "raw_refs"):
            raise ValueError(f"source local_path must remain under data/v1.2/raw_refs: {local_path}")
        if row["status"] in {"downloaded", "existing"} and not row["sha256"]:
            raise ValueError(f"available source must have sha256: {source_id}")
    archive_versions = {row["version"] for row in archive_rows}
    if archive_versions != {"v1", "v1.1", "v1.2"}:
        raise ValueError(f"archive must cover v1, v1.1 and v1.2: {sorted(archive_versions)}")
    for row in archive_rows:
        if row["version"] not in {"v1", "v1.1", "v1.2"}:
            raise ValueError(f"unsupported archive version: {row['version']}")
        if row["status"] not in {"planned", "available"}:
            raise ValueError(f"unsupported archive status: {row['status']}")
    return {
        "source_rows": len(source_rows),
        "archive_rows": len(archive_rows),
        "planned_sources": sum(row["status"] == "planned" for row in source_rows),
        "verified_sources": sum(row["license_status"] == "verified" for row in source_rows),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-catalog", type=Path, default=DEFAULT_SOURCE_CATALOG)
    parser.add_argument("--archive-catalog", type=Path, default=DEFAULT_ARCHIVE_CATALOG)
    args = parser.parse_args()
    print(audit(args.source_catalog, args.archive_catalog))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
