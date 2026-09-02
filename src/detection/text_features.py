"""Canonical text cleaning shared by training and model inference."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass

FEATURE_VERSION = "text-v1"
MODEL_TEXT_MAX_CHARS = 20_000

_EMAIL_RE = re.compile(
    r"(?i)(?<![A-Z0-9._%+\-])[A-Z0-9._%+\-]+@(?:[A-Z0-9-]+\.)+[A-Z0-9-]*[A-Z0-9](?![A-Z0-9-])"
)
_URL_RE = re.compile(r"(?i)(?:https?://|ftp://|www\.)[^\s<>\"]+")
_LONG_NUMBER_RE = re.compile(r"(?<!\w)\d{5,}(?!\w)")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SPACE_RE = re.compile(r"[ \t\f\v]+")
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")

@dataclass(frozen=True)
class CleanedText:
    """Canonical model text plus non-sensitive cleaning measurements."""
    subject: str
    text_body: str
    model_text: str
    feature_version: str = FEATURE_VERSION
    original_chars: int = 0
    cleaned_chars: int = 0
    email_replacements: int = 0
    url_replacements: int = 0
    number_replacements: int = 0
    truncated: bool = False
    warnings: tuple[str, ...] = ()

    def to_jsonable(self) -> dict[str, object]:
        return asdict(self)

def _normalize(value: str) -> str:
    """Normalize Unicode and whitespace without interpreting message markup."""
    value = unicodedata.normalize("NFKC", value or "")
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = _CONTROL_RE.sub(" ", value)
    value = _SPACE_RE.sub(" ", value)
    value = re.sub(r" *\n *", "\n", value)
    return _MULTI_NEWLINE_RE.sub("\n\n", value).strip()

def _clean_field(value: str) -> tuple[str, int, int, int]:
    value = _normalize(value)
    email_count = len(_EMAIL_RE.findall(value))
    value = _EMAIL_RE.sub("<EMAIL>", value)
    url_count = len(_URL_RE.findall(value))
    value = _URL_RE.sub("<URL>", value)
    number_count = len(_LONG_NUMBER_RE.findall(value))
    value = _LONG_NUMBER_RE.sub("<NUMBER>", value)
    return value, email_count, url_count, number_count

def clean_email_text(subject: str, text_body: str) -> CleanedText:
    """Build the exact text-v1 input used by training and inference."""
    original_chars = len(subject or "") + len(text_body or "")
    clean_subject, subject_emails, subject_urls, subject_numbers = _clean_field(subject)
    clean_body, body_emails, body_urls, body_numbers = _clean_field(text_body)
    full_length = len(clean_subject) + len(clean_body) + 1
    model_text = f"{clean_subject}\n{clean_body}"[:MODEL_TEXT_MAX_CHARS]
    warnings: list[str] = []
    if not clean_subject:
        warnings.append("empty_subject")
    if not clean_body:
        warnings.append("empty_text_body")
    truncated = full_length > MODEL_TEXT_MAX_CHARS
    if truncated:
        warnings.append("model_text_truncated")
    return CleanedText(
        subject=clean_subject, text_body=clean_body, model_text=model_text,
        original_chars=original_chars, cleaned_chars=len(model_text),
        email_replacements=subject_emails + body_emails,
        url_replacements=subject_urls + body_urls,
        number_replacements=subject_numbers + body_numbers,
        truncated=truncated, warnings=tuple(warnings),
    )
