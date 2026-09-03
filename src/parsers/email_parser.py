import hashlib
import re
from email.header import decode_header, make_header
from email import policy
from email.message import EmailMessage, Message
from email.parser import BytesParser, Parser
from email.utils import getaddresses, parseaddr
from pathlib import PurePath

from src.domain.schemas import AttachmentMeta, Mailbox, ParsedEmail
from src.parsers.url_parser import extract_urls_from_html, extract_urls_from_text, html_to_text


EMAIL_PATTERN = re.compile(r"^[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+$")
RISKY_EXTENSIONS = {
    ".bat",
    ".cmd",
    ".com",
    ".exe",
    ".hta",
    ".js",
    ".jse",
    ".lnk",
    ".msi",
    ".ps1",
    ".scr",
    ".vbs",
    ".wsf",
}
DOCUMENT_EXTENSIONS = {".doc", ".docm", ".xls", ".xlsm", ".ppt", ".pptm", ".pdf"}
ARCHIVE_EXTENSIONS = {".7z", ".rar", ".zip"}


class EmailParser:
    """Small framework-independent adapter used by the analysis service."""

    def parse(self, raw: bytes | str) -> ParsedEmail:
        return parse_email(raw)


def parse_email(raw: bytes | str) -> ParsedEmail:
    warnings: list[str] = []
    try:
        message = _parse_message(raw)
    except Exception as exc:
        warnings.append(f"parse_error:{exc.__class__.__name__}")
        message = Parser(policy=policy.default).parsestr(str(raw or ""))

    parsed = ParsedEmail(parse_warnings=warnings)
    parsed.headers = _headers_to_dict(message)
    parsed.message_id = _decode_header_value(message.get("message-id", ""))
    parsed.subject = _decode_header_value(message.get("subject", ""))
    parsed.date = _decode_header_value(message.get("date", ""))
    parsed.sender = parse_mailbox(str(message.get("from", "")))
    parsed.reply_to = _optional_mailbox(str(message.get("reply-to", "")))
    parsed.return_path = _optional_mailbox(str(message.get("return-path", "")))
    parsed.recipients = parse_mailboxes(str(message.get("to", "")))
    parsed.cc = parse_mailboxes(str(message.get("cc", "")))

    if not parsed.sender.address:
        parsed.parse_warnings.append("missing_from")
    elif not parsed.sender.is_valid:
        parsed.parse_warnings.append("invalid_from")
    if not parsed.message_id:
        parsed.parse_warnings.append("missing_message_id")
    if not parsed.date:
        parsed.parse_warnings.append("missing_date")

    text_parts: list[str] = []
    html_parts: list[str] = []
    for part in _iter_leaf_parts(message):
        filename = part.get_filename()
        content_disposition = part.get_content_disposition()
        content_type = part.get_content_type()
        is_attachment = content_disposition == "attachment" or bool(filename)
        if is_attachment:
            parsed.attachments.append(_attachment_meta(part))
            continue
        if content_type == "text/plain":
            text_parts.append(_safe_content(part, parsed.parse_warnings))
        elif content_type == "text/html":
            html_parts.append(_safe_content(part, parsed.parse_warnings))

    has_text_body = bool(text_parts)
    parsed.text_body = "\n".join(part for part in text_parts if part).strip()
    parsed.html_body = "\n".join(part for part in html_parts if part).strip()
    if not parsed.text_body and parsed.html_body:
        parsed.text_body = html_to_text(parsed.html_body)

    text_urls = extract_urls_from_text(parsed.text_body) if has_text_body else []
    parsed.urls = _dedupe_urls(text_urls + extract_urls_from_html(parsed.html_body))
    return parsed


def parse_mailbox(value: str) -> Mailbox:
    display_name, address = parseaddr(value or "")
    address = address.strip().lower()
    domain = address.rsplit("@", 1)[1] if "@" in address else ""
    return Mailbox(
        display_name=display_name.strip(),
        address=address,
        domain=domain.lower(),
        is_valid=bool(EMAIL_PATTERN.match(address)),
    )


def parse_mailboxes(value: str) -> list[Mailbox]:
    return [
        mailbox
        for display_name, address in getaddresses([value or ""])
        if (mailbox := parse_mailbox(f"{display_name} <{address}>")).address
    ]


def _decode_header_value(value: object) -> str:
    try:
        return str(make_header(decode_header(str(value or "")))).strip()
    except Exception:
        return str(value or "").strip()


def attachment_risk_hints(filename: str, mime_type: str) -> list[str]:
    hints: list[str] = []
    suffixes = [suffix.lower() for suffix in PurePath(filename or "").suffixes]
    extension = suffixes[-1] if suffixes else ""
    if extension in RISKY_EXTENSIONS:
        hints.append("risky_extension")
    if len(suffixes) >= 2 and suffixes[-2] in DOCUMENT_EXTENSIONS and suffixes[-1] in RISKY_EXTENSIONS:
        hints.append("double_extension")
    if extension in ARCHIVE_EXTENSIONS:
        hints.append("archive_attachment")
    if "application/octet-stream" in (mime_type or "").lower() and extension in RISKY_EXTENSIONS:
        hints.append("executable_like_content_type")
    return _dedupe(hints)


def _parse_message(raw: bytes | str) -> EmailMessage | Message:
    if isinstance(raw, bytes):
        return BytesParser(policy=policy.default).parsebytes(raw)
    return Parser(policy=policy.default).parsestr(raw)


def _headers_to_dict(message: EmailMessage | Message) -> dict[str, str]:
    headers: dict[str, list[str]] = {}
    for name, value in message.items():
        headers.setdefault(name.lower(), []).append(str(value))
    return {name: "\n".join(values) for name, values in headers.items()}


def _optional_mailbox(value: str) -> Mailbox | None:
    mailbox = parse_mailbox(value)
    return mailbox if mailbox.address else None


def _iter_leaf_parts(message: EmailMessage | Message):
    if message.is_multipart():
        for part in message.walk():
            if not part.is_multipart():
                yield part
    else:
        yield message


def _safe_content(part: EmailMessage | Message, warnings: list[str]) -> str:
    try:
        content = part.get_content()
    except Exception as exc:
        warnings.append(f"decode_error:{exc.__class__.__name__}")
        payload = part.get_payload(decode=True) or b""
        charset = part.get_content_charset() or "utf-8"
        content = payload.decode(charset, errors="replace")
    return content if isinstance(content, str) else str(content)


def _attachment_meta(part: EmailMessage | Message) -> AttachmentMeta:
    filename = part.get_filename() or "unnamed"
    payload = part.get_payload(decode=True) or b""
    mime_type = part.get_content_type() or "application/octet-stream"
    suffixes = PurePath(filename).suffixes
    extension = suffixes[-1].lower() if suffixes else ""
    return AttachmentMeta(
        filename=filename,
        mime_type=mime_type,
        size=len(payload),
        sha256=hashlib.sha256(payload).hexdigest() if payload else "",
        extension=extension,
        risk_hints=attachment_risk_hints(filename, mime_type),
    )


def _dedupe_urls(urls):
    result = []
    seen: set[tuple[str, str]] = set()
    for url in urls:
        key = (url.raw_url, url.display_text)
        if key not in seen:
            result.append(url)
            seen.add(key)
    return result


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result
