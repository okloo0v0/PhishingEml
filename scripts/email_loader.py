"""Read public email corpora into Member 1's intermediate dataset.

This module is a script-only data-preparation adapter.  It exists to read the
mbox and tar containers used by the public training corpora and must not be
imported by the web application.  Member 2 owns the production MIME parser in
``src/parsers/``; integration code must use that parser's ``ParsedEmail``
contract instead.

The adapter reads only message text in memory.  It does not access URLs and it
does not extract, write, render, or execute attachment payloads.
"""

from __future__ import annotations

import hashlib
import mailbox
import tarfile
from dataclasses import asdict, dataclass, field
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Iterator

from bs4 import BeautifulSoup


EMAIL_PARSER = BytesParser(policy=policy.default)


@dataclass
class ParsedText:
    subject: str = ""
    text_body: str = ""
    html_body: str = ""
    parse_warnings: list[str] = field(default_factory=list)


@dataclass
class RawEmailRecord:
    """Intermediate record consumed by the cleaning pipeline."""

    id: str
    source: str
    label: str
    subject: str
    text_body: str
    source_hash: str
    parse_warnings: list[str] = field(default_factory=list)

    def to_jsonable(self) -> dict[str, object]:
        return asdict(self)


def _decode_part(part) -> tuple[str, str | None]:
    """Decode a text MIME part and report any safe fallback used."""
    try:
        content = part.get_content()
        return (content if isinstance(content, str) else str(content), None)
    except (LookupError, UnicodeError, TypeError):
        payload = part.get_payload(decode=True)
        if payload is None:
            return "", "empty_part_payload"
        charset = part.get_content_charset() or "utf-8"
        try:
            return payload.decode(charset, errors="replace"), "content_decode_fallback"
        except LookupError:
            return payload.decode("utf-8", errors="replace"), "unknown_charset_fallback"


def _html_to_text(value: str) -> str:
    """Convert HTML to visible text without rendering or executing it."""
    soup = BeautifulSoup(value, "html.parser")
    for node in soup(["script", "style", "noscript"]):
        node.decompose()
    return soup.get_text(" ", strip=True)


def parse_email_bytes(raw: bytes) -> ParsedText:
    """Extract corpus text fields without touching attachment payloads.

    This is deliberately limited to Member 1's offline dataset preparation and
    is not the application's canonical email parsing implementation.
    """

    warnings: list[str] = []
    try:
        message = EMAIL_PARSER.parsebytes(raw)
    except Exception as exc:
        return ParsedText(parse_warnings=[f"parse_error:{type(exc).__name__}"])

    # A corpus member without any RFC-style header is not a usable email
    # sample; avoid silently treating the entire blob as model text.
    header_block = raw.split(b"\n\n", 1)[0].split(b"\r\n\r\n", 1)[0]
    if not any(b":" in line for line in header_block.splitlines() if line):
        return ParsedText(parse_warnings=["missing_headers"])

    try:
        subject = str(message.get("subject", ""))
    except (UnicodeError, ValueError):
        subject = ""
        warnings.append("subject_decode_failed")

    text_parts: list[str] = []
    html_parts: list[str] = []
    parts = message.walk() if message.is_multipart() else [message]
    for part in parts:
        if part.is_multipart() or part.get_content_disposition() == "attachment":
            continue
        content_type = part.get_content_type().lower()
        if content_type not in {"text/plain", "text/html"}:
            continue
        try:
            value, warning = _decode_part(part)
        except Exception as exc:
            warnings.append(f"part_decode_error:{type(exc).__name__}")
            continue
        if warning is not None:
            warnings.append(warning)
        if content_type == "text/html":
            html_parts.append(value)
            try:
                text_parts.append(_html_to_text(value))
            except Exception as exc:
                warnings.append(f"html_text_error:{type(exc).__name__}")
        else:
            text_parts.append(value)

    if not text_parts and message.is_multipart():
        warnings.append("empty_text_body")
    return ParsedText(
        subject=subject,
        text_body="\n".join(part for part in text_parts if part).strip(),
        html_body="\n".join(html_parts),
        parse_warnings=warnings,
    )


def _record(raw: bytes, source: str, label: str, item_id: str) -> RawEmailRecord:
    parsed = parse_email_bytes(raw)
    return RawEmailRecord(
        id=item_id,
        source=source,
        label=label,
        subject=parsed.subject,
        text_body=parsed.text_body,
        source_hash=hashlib.sha256(raw).hexdigest(),
        parse_warnings=parsed.parse_warnings,
    )


def _iter_mbox(path: Path, source: str, label: str) -> Iterator[RawEmailRecord]:
    """Yield in-memory records from a public mbox corpus container."""
    corpus = mailbox.mbox(path, create=False)
    try:
        for index, message in enumerate(corpus):
            raw = message.as_bytes(policy=policy.default)
            yield _record(raw, source, label, f"{source}-{path.stem}-{index:06d}")
    finally:
        corpus.close()


def _iter_tar(path: Path, source: str, label: str) -> Iterator[RawEmailRecord]:
    """Yield records from tar members without extracting them to disk."""
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
            yield _record(raw, source, label, f"{source}-{path.stem}-{index:06d}")
            index += 1


def iter_corpus_records(root: Path) -> Iterator[RawEmailRecord]:
    """Yield corpus records using the labels encoded by source directories.

    Only known public-corpus directories are accepted. Unknown files are left
    untouched so an accidental local dataset cannot silently enter training.
    """

    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == ".gitkeep":
            continue
        source = path.parent.name
        label = "phishing" if source == "nazario" else "legitimate" if source == "spamassassin_ham" else "unknown"
        if label == "unknown":
            continue
        if path.suffix == ".mbox" or path.name.startswith("phishing-"):
            yield from _iter_mbox(path, source, label)
        elif path.name.endswith((".tar.bz2", ".tar.gz", ".tgz")):
            yield from _iter_tar(path, source, label)
