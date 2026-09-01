"""Download fixed public email corpus files for the member-1 pipeline.

This script only downloads the explicitly listed corpus URLs. It never follows
URLs found inside an email and never extracts or executes email attachments.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
MANIFEST_DIR = ROOT / "data" / "manifests"
MANIFEST_PATH = MANIFEST_DIR / "sources.csv"

CORPORA: dict[str, tuple[str, str, str]] = {
    "nazario_20051114": (
        "nazario",
        "https://monkey.org/~jose/phishing/20051114.mbox",
        "CC BY 4.0; see LICENSE.txt at the source site",
    ),
    "nazario_phishing0": (
        "nazario",
        "https://monkey.org/~jose/phishing/phishing0.mbox",
        "CC BY 4.0; see LICENSE.txt at the source site",
    ),
    "nazario_phishing1": (
        "nazario",
        "https://monkey.org/~jose/phishing/phishing1.mbox",
        "CC BY 4.0; see LICENSE.txt at the source site",
    ),
    "nazario_phishing2": (
        "nazario",
        "https://monkey.org/~jose/phishing/phishing2.mbox",
        "CC BY 4.0; see LICENSE.txt at the source site",
    ),
    "nazario_phishing3": (
        "nazario",
        "https://monkey.org/~jose/phishing/phishing3.mbox",
        "CC BY 4.0; see LICENSE.txt at the source site",
    ),
    "nazario_2021": (
        "nazario",
        "https://monkey.org/~jose/phishing/phishing-2021",
        "CC BY 4.0; see LICENSE.txt at the source site",
    ),
    "nazario_2022": (
        "nazario",
        "https://monkey.org/~jose/phishing/phishing-2022",
        "CC BY 4.0; see LICENSE.txt at the source site",
    ),
    "nazario_2023": (
        "nazario",
        "https://monkey.org/~jose/phishing/phishing-2023",
        "CC BY 4.0; see LICENSE.txt at the source site",
    ),
    "nazario_2024": (
        "nazario",
        "https://monkey.org/~jose/phishing/phishing-2024",
        "CC BY 4.0; see LICENSE.txt at the source site",
    ),
    "nazario_2025": (
        "nazario",
        "https://monkey.org/~jose/phishing/phishing-2025",
        "CC BY 4.0; see LICENSE.txt at the source site",
    ),
    "spamassassin_easy_ham": (
        "spamassassin_ham",
        "https://spamassassin.apache.org/old/publiccorpus/20021010_easy_ham.tar.bz2",
        "SpamAssassin Public Corpus terms/readme",
    ),
    "spamassassin_hard_ham": (
        "spamassassin_ham",
        "https://spamassassin.apache.org/old/publiccorpus/20021010_hard_ham.tar.bz2",
        "SpamAssassin Public Corpus terms/readme",
    ),
    "spamassassin_easy_ham_2": (
        "spamassassin_ham",
        "https://spamassassin.apache.org/old/publiccorpus/20030228_easy_ham.tar.bz2",
        "SpamAssassin Public Corpus terms/readme",
    ),
    "spamassassin_easy_ham_3": (
        "spamassassin_ham",
        "https://spamassassin.apache.org/old/publiccorpus/20030228_easy_ham_2.tar.bz2",
        "SpamAssassin Public Corpus terms/readme",
    ),
    "spamassassin_hard_ham_2": (
        "spamassassin_ham",
        "https://spamassassin.apache.org/old/publiccorpus/20030228_hard_ham.tar.bz2",
        "SpamAssassin Public Corpus terms/readme",
    ),
}


@dataclass(frozen=True)
class DownloadRecord:
    key: str
    source: str
    url: str
    license_note: str
    local_path: str
    status: str
    size_bytes: int
    sha256: str
    downloaded_at: str
    error: str = ""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_file(url: str, destination: Path) -> None:
    request = Request(url, headers={"User-Agent": "PhishingEml-course-project/1.0"})
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    try:
        with urlopen(request, timeout=60) as response, temporary.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def collect(selected: list[str]) -> list[DownloadRecord]:
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    existing_manifest: dict[str, dict[str, str]] = {}
    if MANIFEST_PATH.exists():
        with MANIFEST_PATH.open(newline="", encoding="utf-8") as handle:
            existing_manifest = {row["key"]: row for row in csv.DictReader(handle)}
    records: list[DownloadRecord] = []
    for key in selected:
        source, url, license_note = CORPORA[key]
        filename = url.rsplit("/", 1)[-1]
        destination = RAW_DIR / source / filename
        timestamp = existing_manifest.get(key, {}).get("downloaded_at") or (
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        )
        try:
            if not destination.exists():
                logging.info("Downloading %s", url)
                download_file(url, destination)
                status = "downloaded"
            else:
                logging.info("Keeping existing file %s", destination)
                status = "existing"
            records.append(
                DownloadRecord(
                    key=key,
                    source=source,
                    url=url,
                    license_note=license_note,
                    local_path=destination.relative_to(ROOT).as_posix(),
                    status=status,
                    size_bytes=destination.stat().st_size,
                    sha256=sha256_file(destination),
                    downloaded_at=timestamp,
                )
            )
        except (HTTPError, URLError, OSError, TimeoutError) as exc:
            logging.error("Failed to download %s: %s", url, exc)
            records.append(
                DownloadRecord(
                    key=key,
                    source=source,
                    url=url,
                    license_note=license_note,
                    local_path=destination.relative_to(ROOT).as_posix(),
                    status="failed",
                    size_bytes=0,
                    sha256="",
                    downloaded_at=timestamp,
                    error=f"{type(exc).__name__}: download failed",
                )
            )
    merged: dict[str, dict[str, object]] = {}
    for row in existing_manifest.values():
        row["size_bytes"] = int(row["size_bytes"])
        merged[row["key"]] = row
    merged.update({record.key: record.__dict__ for record in records})

    with MANIFEST_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(DownloadRecord.__annotations__))
        writer.writeheader()
        writer.writerows(merged[key] for key in sorted(merged))
    return records


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        action="append",
        choices=sorted(CORPORA),
        dest="sources",
        help="Corpus key to download; repeatable. Defaults to the first collection batch.",
    )
    parser.add_argument("--list", action="store_true", help="List available corpus keys")
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args()
    if args.list:
        for key, (_, url, _) in CORPORA.items():
            print(f"{key}\t{url}")
        return 0
    selected = args.sources or list(CORPORA)
    records = collect(selected)
    downloaded = sum(record.status in {"downloaded", "existing"} for record in records)
    failed = sum(record.status == "failed" for record in records)
    print(f"Recorded {downloaded} corpus files; failed={failed}; manifest={MANIFEST_PATH}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
