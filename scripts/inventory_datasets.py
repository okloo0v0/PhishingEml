"""Count messages in downloaded corpus containers without extracting content."""

from __future__ import annotations

import csv
import mailbox
import tarfile
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
OUTPUT = ROOT / "data" / "manifests" / "inventory.csv"


@dataclass(frozen=True)
class InventoryRecord:
    source: str
    local_path: str
    container_type: str
    message_count: int
    size_bytes: int
    status: str
    error: str = ""


def count_mbox(path: Path) -> int:
    corpus = mailbox.mbox(path, create=False)
    try:
        return len(corpus)
    finally:
        corpus.close()


def count_tar_messages(path: Path) -> int:
    with tarfile.open(path, mode="r:*") as archive:
        return sum(
            member.isfile()
            and not member.name.rsplit("/", 1)[-1].startswith(("cmds", "README"))
            for member in archive.getmembers()
        )


def inspect(path: Path) -> InventoryRecord:
    relative = path.relative_to(ROOT).as_posix()
    source = path.parent.name
    try:
        if path.suffix == ".mbox" or path.name.startswith("phishing-"):
            container_type = "mbox"
            count = count_mbox(path)
        elif path.name.endswith((".tar.bz2", ".tar.gz", ".tgz")):
            container_type = "tar"
            count = count_tar_messages(path)
        else:
            container_type = "unknown"
            count = 0
        return InventoryRecord(
            source=source,
            local_path=relative,
            container_type=container_type,
            message_count=count,
            size_bytes=path.stat().st_size,
            status="ok" if container_type != "unknown" else "skipped",
        )
    except (OSError, mailbox.Error, tarfile.TarError) as exc:
        return InventoryRecord(
            source=source,
            local_path=relative,
            container_type="unknown",
            message_count=0,
            size_bytes=path.stat().st_size,
            status="failed",
            error=str(exc),
        )


def main() -> None:
    paths = sorted(path for path in RAW_DIR.rglob("*") if path.is_file() and path.name != ".gitkeep")
    records = [inspect(path) for path in paths]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(InventoryRecord.__annotations__))
        writer.writeheader()
        writer.writerows(asdict(record) for record in records)

    totals: dict[str, int] = {}
    for record in records:
        totals[record.source] = totals.get(record.source, 0) + record.message_count
    for source, count in sorted(totals.items()):
        print(f"{source}: {count} messages")
    print(f"inventory={OUTPUT}")


if __name__ == "__main__":
    main()
