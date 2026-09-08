"""Download allowlisted V1.2 public datasets and update the audit catalog.

This script only fetches URLs declared in the local allowlist. It never follows
or visits URLs contained in email data and never extracts attachments.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data" / "v1.2" / "manifests" / "source_catalog.csv"
RAW_ROOT = ROOT / "data" / "v1.2" / "raw_refs"

SOURCES = {
    "figshare_seven_ling": ("figshare_2024", "Ling.csv", "en", "spam_phishing_text", "https://ndownloader.figshare.com/files/45117802", "CC BY 4.0", "2024-03-18"),
    "figshare_seven_enron": ("figshare_2024", "Enron.csv", "en", "legitimate_text", "https://ndownloader.figshare.com/files/45117805", "CC BY 4.0", "2024-03-18"),
    "figshare_seven_trec06": ("figshare_2024", "TREC-06.csv", "en", "spam_text", "https://ndownloader.figshare.com/files/45117808", "CC BY 4.0", "2024-03-18"),
    "figshare_seven_ceas08": ("figshare_2024", "CEAS-08.csv", "en", "spam_text", "https://ndownloader.figshare.com/files/45117811", "CC BY 4.0", "2024-03-18"),
    "figshare_seven_trec07": ("figshare_2024", "TREC-07.csv", "en", "spam_text", "https://ndownloader.figshare.com/files/45117814", "CC BY 4.0", "2024-03-18"),
    "figshare_seven_trec05": ("figshare_2024", "TREC-05.csv", "en", "spam_text", "https://ndownloader.figshare.com/files/45117817", "CC BY 4.0", "2024-03-18"),
    "figshare_seven_assassin": ("figshare_2024", "Assassin.csv", "en", "spam_text", "https://ndownloader.figshare.com/files/45117799", "CC BY 4.0", "2024-03-18"),
    "llmgen_cn": ("llmgen_2025", "CN_Phishing_Email_dataset.csv", "zh", "phishing_text_generated", "https://huggingface.co/datasets/Dizzzy0x00/LLMGen-Phishing-Email-Dataset/resolve/main/CN_Phishing_Email_dataset.csv", "Apache-2.0 dataset card", "2025-12-13"),
    "llmgen_gpt": ("llmgen_2025", "GPT_Phishing_Email_dataset.csv", "zh-en", "phishing_text_generated", "https://huggingface.co/datasets/Dizzzy0x00/LLMGen-Phishing-Email-Dataset/resolve/main/GPT_Phishing_Email_dataset.csv", "Apache-2.0 dataset card", "2025-12-13"),
    "epvme_readme": ("epvme_2023", "README.md", "en", "protocol_mime_ui_attack", "https://raw.githubusercontent.com/sunknighteric/EPVME-Dataset/main/README.md", "GPL-3.0 repository; verify dataset terms", "2023-03-23"),
    "epvme_license": ("epvme_2023", "LICENSE", "en", "protocol_mime_ui_attack", "https://raw.githubusercontent.com/sunknighteric/EPVME-Dataset/main/LICENSE", "GPL-3.0", "2023-03-23"),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    request = Request(url, headers={"User-Agent": "PhishingEml-v1.2-research/1.0"})
    try:
        with urlopen(request, timeout=180) as response, temporary.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _load_catalog() -> dict[str, dict[str, str]]:
    if not CATALOG.exists():
        return {}
    with CATALOG.open(encoding="utf-8", newline="") as handle:
        return {row["source_id"]: row for row in csv.DictReader(handle)}


def download(keys: list[str]) -> list[dict[str, str]]:
    existing = _load_catalog()
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    records: list[dict[str, str]] = []
    for key in keys:
        collection, filename, language, scope, url, license_note, published = SOURCES[key]
        destination = RAW_ROOT / collection / filename
        row = existing.get(key, {})
        try:
            if not destination.exists():
                logging.info("Downloading %s", key)
                _download(url, destination)
                status = "downloaded"
            else:
                status = "existing"
            records.append({
                "source_id": key, "source_type": "public_dataset", "language": language,
                "attack_scope": scope, "source_url": url, "license_status": "review_required",
                "local_path": destination.relative_to(ROOT).as_posix(), "status": status,
                "downloaded_at": row.get("downloaded_at") or now, "sha256": _sha256(destination),
                "notes": f"published_or_released={published}; inspect and sanitize before training",
            })
        except Exception as exc:
            records.append({
                "source_id": key, "source_type": "public_dataset", "language": language,
                "attack_scope": scope, "source_url": url, "license_status": "review_required",
                "local_path": destination.relative_to(ROOT).as_posix(), "status": "failed",
                "downloaded_at": row.get("downloaded_at") or now, "sha256": "",
                "notes": f"published_or_released={published}; {type(exc).__name__}: download failed",
            })
    merged = {**existing, **{row["source_id"]: row for row in records}}
    CATALOG.parent.mkdir(parents=True, exist_ok=True)
    fields = ["source_id", "source_type", "language", "attack_scope", "source_url", "license_status", "local_path", "status", "downloaded_at", "sha256", "notes"]
    with CATALOG.open("w", encoding="utf-8", newline="") as handle:
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
            print(f"{key}\t{spec[0]}/{spec[1]}\t{spec[4]}")
        return 0
    records = download(args.source or list(SOURCES))
    failed = sum(row["status"] == "failed" for row in records)
    print(f"downloaded_or_existing={len(records) - failed}; failed={failed}; catalog={CATALOG}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
