"""Register and download the selected supplemental public CSV corpora."""

from __future__ import annotations

import argparse
import csv
import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw" / "supplemental_zenodo"
MANIFEST_PATH = ROOT / "data" / "manifests" / "sources.csv"


@dataclass(frozen=True)
class SupplementalSpec:
    key: str
    filename: str
    label_mapping: str
    license_note: str
    url: str


SOURCES = {
    "zenodo_nigerian_5": SupplementalSpec(
        "zenodo_nigerian_5", "Nigerian_5.csv", "0=legitimate;1=phishing",
        "CC BY 4.0; Zenodo record 8339691", "https://zenodo.org/api/records/8339691/files/Nigerian_5.csv/content",
    ),
    "zenodo_spamassassin_csv": SupplementalSpec(
        "zenodo_spamassassin_csv", "SpamAssasin.csv", "0=legitimate;1=spam_other",
        "CC BY 4.0; Zenodo record 8339691", "https://zenodo.org/api/records/8339691/files/SpamAssasin.csv/content",
    ),
    "zenodo_nigerian_fraud": SupplementalSpec(
        "zenodo_nigerian_fraud", "Nigerian_Fraud.csv", "1=phishing",
        "CC BY 4.0; Zenodo record 8339691", "https://zenodo.org/api/records/8339691/files/Nigerian_Fraud.csv/content",
    ),
    "zenodo_nazario_csv": SupplementalSpec(
        "zenodo_nazario_csv", "Nazario.csv", "1=phishing",
        "CC BY 4.0; Zenodo record 8339691", "https://zenodo.org/api/records/8339691/files/Nazario.csv/content",
    ),
    "zenodo_ling_csv": SupplementalSpec(
        "zenodo_ling_csv", "Ling.csv", "0=legitimate;1=spam_other",
        "CC BY 4.0; Zenodo record 8339691", "https://zenodo.org/api/records/8339691/files/Ling.csv/content",
    ),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download(url: str, destination: Path) -> None:
    request = Request(url, headers={"User-Agent": "PhishingEml-course-project/1.0"})
    temporary = destination.with_suffix(destination.suffix + ".part")
    try:
        with urlopen(request, timeout=180) as response, temporary.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def collect(keys: list[str]) -> list[dict[str, object]]:
    """Download selected files and merge non-sensitive records into sources.csv."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    existing: dict[str, dict[str, str]] = {}
    if MANIFEST_PATH.exists():
        with MANIFEST_PATH.open(newline="", encoding="utf-8") as handle:
            existing = {row["key"]: row for row in csv.DictReader(handle)}
    records: list[dict[str, object]] = []
    for key in keys:
        spec = SOURCES[key]
        destination = RAW_DIR / spec.filename
        timestamp = existing.get(key, {}).get("downloaded_at") or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        try:
            if not destination.exists():
                logging.info("Downloading %s", spec.filename)
                _download(spec.url, destination)
                status = "downloaded"
            else:
                status = "existing"
            records.append({
                "key": key, "source": "supplemental_zenodo", "url": spec.url,
                "license_note": spec.license_note, "local_path": destination.relative_to(ROOT).as_posix(),
                "status": status, "size_bytes": destination.stat().st_size,
                "sha256": _sha256(destination), "downloaded_at": timestamp, "error": "",
            })
        except Exception as exc:
            records.append({
                "key": key, "source": "supplemental_zenodo", "url": spec.url,
                "license_note": spec.license_note, "local_path": destination.relative_to(ROOT).as_posix(),
                "status": "failed", "size_bytes": 0, "sha256": "", "downloaded_at": timestamp,
                "error": f"{type(exc).__name__}: download failed",
            })
    merged = {**existing, **{str(row["key"]): row for row in records}}
    with MANIFEST_PATH.open("w", newline="", encoding="utf-8") as handle:
        fields = ["key", "source", "url", "license_note", "local_path", "status", "size_bytes", "sha256", "downloaded_at", "error"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(merged[key] for key in sorted(merged))
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", action="append", choices=sorted(SOURCES))
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()
    if args.list:
        for key, spec in SOURCES.items():
            print(f"{key}\t{spec.filename}\t{spec.label_mapping}")
        return 0
    selected = args.source or list(SOURCES)
    records = collect(selected)
    failed = sum(row["status"] == "failed" for row in records)
    print(f"Recorded {len(records) - failed} supplemental files; failed={failed}; manifest={MANIFEST_PATH}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
