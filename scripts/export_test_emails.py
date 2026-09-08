"""Export exact raw MIME messages belonging to a model evaluation split.

Only local public-corpus archives are read. Exported messages are intended for
local platform testing and should remain under an ignored directory such as
``tmp/testset_eml``.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import mailbox
import tarfile
from email import policy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INDEX = ROOT / "data" / "processed" / "emails.csv"
DEFAULT_INPUT = ROOT / "data" / "raw"
DEFAULT_OUTPUT = ROOT / "tmp" / "testset_eml"

# Model input rows contain long message bodies; the stdlib default is 128 KiB.
csv.field_size_limit(10_000_000)


def _iter_raw_messages(root: Path):
    """Yield ``(id, source, raw_bytes)`` using the same IDs as email_loader."""

    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == ".gitkeep":
            continue
        source = path.parent.name
        if source not in {"nazario", "spamassassin_ham"}:
            continue
        if path.suffix == ".mbox" or path.name.startswith("phishing-"):
            corpus = mailbox.mbox(path, create=False)
            try:
                for index, message in enumerate(corpus):
                    raw = message.as_bytes(policy=policy.default)
                    yield f"{source}-{path.stem}-{index:06d}", source, raw
            finally:
                corpus.close()
        elif path.name.endswith((".tar.bz2", ".tar.gz", ".tgz")):
            with tarfile.open(path, mode="r:*") as archive:
                index = 0
                for member in archive:
                    if not member.isfile():
                        continue
                    name = member.name.rsplit("/", 1)[-1]
                    if name.startswith(("cmds", "README")):
                        continue
                    extracted = archive.extractfile(member)
                    if extracted is None:
                        continue
                    raw = extracted.read()
                    yield f"{source}-{path.stem}-{index:06d}", source, raw
                    index += 1


def export_test_emails(
    index_path: Path = DEFAULT_INDEX,
    input_dir: Path = DEFAULT_INPUT,
    output_dir: Path = DEFAULT_OUTPUT,
    split: str = "test",
) -> dict[str, object]:
    """Export messages and return a non-sensitive manifest summary."""

    expected: dict[str, dict[str, str]] = {}
    with index_path.open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        for row in reader:
            if row.get("split") == split and row.get("source") in {"nazario", "spamassassin_ham"}:
                expected[str(row["id"])] = row

    output_dir.mkdir(parents=True, exist_ok=True)
    exported: list[str] = []
    exported_files: list[dict[str, str]] = []
    missing: list[str] = []
    hash_mismatch: list[str] = []
    seen: set[str] = set()

    for message_id, _source, raw in _iter_raw_messages(input_dir):
        if message_id not in expected:
            continue
        seen.add(message_id)
        digest = hashlib.sha256(raw).hexdigest()
        if digest != expected[message_id].get("source_hash"):
            hash_mismatch.append(message_id)
            continue
        # Use a sequential safe filename because corpus-derived IDs can collide
        # across archive naming conventions on Windows.
        filename = f"test-{len(exported) + 1:04d}.eml"
        (output_dir / filename).write_bytes(raw)
        exported.append(message_id)
        exported_files.append(
            {
                "filename": filename,
                "id": message_id,
                "source": expected[message_id].get("source", ""),
                "label": expected[message_id].get("label", ""),
            }
        )

    missing = sorted(set(expected) - seen)
    manifest = {
        "index_path": index_path.relative_to(ROOT).as_posix(),
        "split": split,
        "requested_records": len(expected),
        "exported_records": len(exported),
        "missing_records": len(missing),
        "hash_mismatch_records": len(hash_mismatch),
        "output_dir": output_dir.relative_to(ROOT).as_posix()
        if output_dir.is_relative_to(ROOT)
        else str(output_dir),
        "sources": {
            source: sum(1 for row in expected.values() if row.get("source") == source)
            for source in sorted({row.get("source", "") for row in expected.values()})
        },
        "files": exported_files,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--split", default="test")
    args = parser.parse_args()
    print(json.dumps(export_test_emails(args.index, args.input_dir, args.output_dir, args.split), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
