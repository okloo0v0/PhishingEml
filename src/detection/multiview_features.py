"""Shared static feature construction for the V1.1 multi-view model."""

from __future__ import annotations

import re
import unicodedata
import json
from collections.abc import Iterable, Sequence
from typing import Any

import numpy as np

from src.detection.text_features import MODEL_TEXT_MAX_CHARS, clean_email_text
from src.detection.intent_branch import infer_intent_labels
from src.domain.schemas import AttachmentMeta, Mailbox, ParsedEmail, ParsedUrl
from src.parsers.url_parser import extract_urls_from_text, get_registrable_domain, normalize_url


FEATURE_VERSION = "text-structure-v2"

_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_EMAIL_RE = re.compile(r"(?i)[A-Z0-9._%+\-]+@(?:[A-Z0-9-]+\.)+[A-Z]{2,}")
_WORD_RE = re.compile(r"\b\w+\b", flags=re.UNICODE)
_HTML_TAG_RE = re.compile(r"<\s*[a-zA-Z][^>]*>")
_HTML_IMAGE_RE = re.compile(r"<\s*img\b", flags=re.IGNORECASE)
_HTML_LINK_RE = re.compile(r"<\s*a\b", flags=re.IGNORECASE)

INTENT_PATTERNS: dict[str, tuple[str, ...]] = {
    "credential": (
        "password", "passcode", "credential", "verification code", "security code",
        "密码", "验证码", "口令", "登录信息",
    ),
    "payment": (
        "payment", "invoice", "wire transfer", "bank account", "beneficiary",
        "付款", "发票", "转账", "收款账户", "银行账户",
    ),
    "download": (
        "download", "open the attachment", "enable macros", "shared document",
        "下载", "打开附件", "启用宏", "共享文件",
    ),
    "reply": (
        "reply", "respond", "send me", "provide the", "confirm by email",
        "回复", "回信", "发送给我", "提供", "邮件确认",
    ),
    "authorization": (
        "device code", "verification page", "authorize", "oauth", "approve sign-in",
        "设备代码", "授权", "批准登录", "身份验证页面",
    ),
    "urgency": (
        "urgent", "immediately", "within 24 hours", "final warning", "act now",
        "紧急", "立即", "马上", "限时", "最后通知",
    ),
    "authority": (
        "chief executive", "ceo", "director", "administrator", "human resources",
        "总经理", "董事", "管理员", "人力资源", "领导",
    ),
    "secrecy": (
        "confidential", "do not discuss", "keep this private", "between us",
        "保密", "不要告诉", "不要讨论", "仅限你我",
    ),
    "bypass": (
        "skip approval", "bypass", "do not call", "outside the process",
        "跳过审批", "绕过", "不要电话确认", "特殊流程",
    ),
}

STRUCTURE_FEATURE_NAMES = (
    "subject_chars",
    "body_chars",
    "word_count",
    "line_count",
    "non_ascii_ratio",
    "uppercase_ratio",
    "digit_ratio",
    "exclamation_count",
    "question_count",
    "email_address_count",
    "url_count",
    "distinct_domain_count",
    "https_url_ratio",
    "ip_url_count",
    "shortener_url_count",
    "punycode_url_count",
    "suspicious_url_token_count",
    "nested_url_count",
    "display_link_mismatch_count",
    "sender_present",
    "reply_to_present",
    "sender_reply_domain_mismatch",
    "return_path_domain_mismatch",
    "recipient_count",
    "header_count",
    "parse_warning_count",
    "attachment_count",
    "risky_attachment_count",
    "html_present",
    "html_tag_count",
    "html_link_count",
    "html_image_count",
    "text_to_html_ratio",
)

INTENT_FEATURE_NAMES = tuple(
    [f"{name}_hits" for name in INTENT_PATTERNS]
    + [f"{name}_present" for name in INTENT_PATTERNS]
    + ["intent_category_count", "intent_hit_count", "urgency_action_pair"]
)


def _char_text(subject: str, text_body: str) -> str:
    value = f"{subject or ''}\n{text_body or ''}"
    value = unicodedata.normalize("NFKC", value)
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = _CONTROL_RE.sub(" ", value)
    return value[:MODEL_TEXT_MAX_CHARS]


def _ratio(count: int, total: int) -> float:
    return float(count) / float(total) if total else 0.0


def _display_mismatch(url: ParsedUrl) -> bool:
    display = (url.display_text or "").strip()
    if not display:
        return False
    parsed_display = normalize_url(display)
    display_domain = parsed_display.registrable_domain or get_registrable_domain(display.lower())
    target_domain = url.registrable_domain or url.host
    return bool(display_domain and target_domain and display_domain != target_domain)


def _structure_features(
    subject: str,
    text_body: str,
    char_text: str,
    parsed_email: ParsedEmail | None,
) -> dict[str, float]:
    urls = list(parsed_email.urls) if parsed_email is not None else extract_urls_from_text(char_text)
    domains = {url.registrable_domain or url.host for url in urls if url.registrable_domain or url.host}
    alpha_chars = [char for char in char_text if char.isalpha()]
    attachments = parsed_email.attachments if parsed_email is not None else []
    html_body = parsed_email.html_body if parsed_email is not None else ""
    sender = parsed_email.sender if parsed_email is not None else None
    reply_to = parsed_email.reply_to if parsed_email is not None else None
    return_path = parsed_email.return_path if parsed_email is not None else None
    sender_domain = sender.domain if sender is not None else ""
    nested_markers = ("http%3a", "https%3a", "url=http", "redirect=http", "target=http")

    values = {
        "subject_chars": float(len(subject or "")),
        "body_chars": float(len(text_body or "")),
        "word_count": float(len(_WORD_RE.findall(char_text))),
        "line_count": float(max(1, char_text.count("\n") + 1)),
        "non_ascii_ratio": _ratio(sum(ord(char) > 127 for char in char_text), len(char_text)),
        "uppercase_ratio": _ratio(sum(char.isupper() for char in alpha_chars), len(alpha_chars)),
        "digit_ratio": _ratio(sum(char.isdigit() for char in char_text), len(char_text)),
        "exclamation_count": float(char_text.count("!") + char_text.count("！")),
        "question_count": float(char_text.count("?") + char_text.count("？")),
        "email_address_count": float(len(_EMAIL_RE.findall(char_text))),
        "url_count": float(len(urls)),
        "distinct_domain_count": float(len(domains)),
        "https_url_ratio": _ratio(sum(url.is_https for url in urls), len(urls)),
        "ip_url_count": float(sum(url.uses_ip for url in urls)),
        "shortener_url_count": float(sum(url.is_shortener for url in urls)),
        "punycode_url_count": float(sum("xn--" in (url.host or "") for url in urls)),
        "suspicious_url_token_count": float(sum(len(url.suspicious_tokens) for url in urls)),
        "nested_url_count": float(
            sum(any(marker in (url.query or "").lower() for marker in nested_markers) for url in urls)
        ),
        "display_link_mismatch_count": float(sum(_display_mismatch(url) for url in urls)),
        "sender_present": float(bool(sender and sender.address)),
        "reply_to_present": float(bool(reply_to and reply_to.address)),
        "sender_reply_domain_mismatch": float(
            bool(sender_domain and reply_to and reply_to.domain and sender_domain != reply_to.domain)
        ),
        "return_path_domain_mismatch": float(
            bool(sender_domain and return_path and return_path.domain and sender_domain != return_path.domain)
        ),
        "recipient_count": float(len(parsed_email.recipients) + len(parsed_email.cc)) if parsed_email else 0.0,
        "header_count": float(len(parsed_email.headers)) if parsed_email else 0.0,
        "parse_warning_count": float(len(parsed_email.parse_warnings)) if parsed_email else 0.0,
        "attachment_count": float(len(attachments)),
        "risky_attachment_count": float(sum(bool(item.risk_hints) for item in attachments)),
        "html_present": float(bool(html_body)),
        "html_tag_count": float(len(_HTML_TAG_RE.findall(html_body))),
        "html_link_count": float(len(_HTML_LINK_RE.findall(html_body))),
        "html_image_count": float(len(_HTML_IMAGE_RE.findall(html_body))),
        "text_to_html_ratio": _ratio(len(text_body or ""), len(html_body)),
    }
    return values


def _intent_features(char_text: str) -> dict[str, float]:
    lowered = char_text.casefold()
    hits = {
        name: sum(lowered.count(pattern.casefold()) for pattern in patterns)
        for name, patterns in INTENT_PATTERNS.items()
    }
    result = {f"{name}_hits": float(count) for name, count in hits.items()}
    result.update({f"{name}_present": float(count > 0) for name, count in hits.items()})
    result["intent_category_count"] = float(sum(count > 0 for count in hits.values()))
    result["intent_hit_count"] = float(sum(hits.values()))
    action_hits = hits["credential"] + hits["payment"] + hits["download"] + hits["authorization"]
    result["urgency_action_pair"] = float(hits["urgency"] > 0 and action_hits > 0)
    return result


def build_multiview_record(
    subject: str,
    text_body: str,
    parsed_email: ParsedEmail | None = None,
) -> dict[str, Any]:
    """Build all V1.1 views without network access or attachment processing."""

    cleaned = clean_email_text(subject, text_body)
    char_text = _char_text(subject, text_body)
    return {
        "word_text": cleaned.model_text,
        "char_text": char_text,
        "structure": _structure_features(subject, text_body, char_text, parsed_email),
        "intent": _intent_features(char_text),
        "intent_labels": infer_intent_labels(subject, text_body)[0],
        "intent_label_provenance": "weak_pattern_v1",
    }


def _context_value(row: dict[str, Any]) -> dict[str, Any] | None:
    """Return a safe serialized ParsedEmail context stored with a training row."""

    for key in ("parsed_email", "parsed_email_json", "v1_1_parsed_email"):
        value = row.get(key)
        if isinstance(value, dict):
            return value
        if isinstance(value, str) and value.strip():
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
    return None


def _mailbox_from_context(value: object) -> Mailbox | None:
    if not isinstance(value, dict):
        return None
    address = str(value.get("address", ""))
    if not address:
        return None
    return Mailbox(
        display_name=str(value.get("display_name", "")),
        address=address,
        domain=str(value.get("domain", "")),
        is_valid=bool(value.get("is_valid", False)),
    )


def parsed_email_from_row(row: dict[str, Any]) -> ParsedEmail | None:
    """Rebuild static email metadata for offline V1.1 feature extraction.

    The context stores no attachment bytes and is optional so historical text-only
    rows remain compatible with the V1.1 training pipeline.
    """

    context = _context_value(row)
    if context is None:
        return None

    urls: list[ParsedUrl] = []
    for item in context.get("urls", []):
        if not isinstance(item, dict) or not item.get("raw_url"):
            continue
        urls.append(
            ParsedUrl(
                raw_url=str(item["raw_url"]),
                normalized_url=str(item.get("normalized_url", item["raw_url"])),
                display_text=str(item.get("display_text", "")),
                scheme=str(item.get("scheme", "")),
                host=str(item.get("host", "")),
                registrable_domain=str(item.get("registrable_domain", "")),
                port=item.get("port") if isinstance(item.get("port"), int) else None,
                path=str(item.get("path", "")),
                query=str(item.get("query", "")),
                is_https=bool(item.get("is_https", False)),
                uses_ip=bool(item.get("uses_ip", False)),
                is_shortener=bool(item.get("is_shortener", False)),
                suspicious_tokens=[str(token) for token in item.get("suspicious_tokens", [])],
            )
        )

    attachments: list[AttachmentMeta] = []
    for item in context.get("attachments", []):
        if not isinstance(item, dict) or not item.get("filename"):
            continue
        attachments.append(
            AttachmentMeta(
                filename=str(item["filename"]),
                mime_type=str(item.get("mime_type", "application/octet-stream")),
                size=int(item.get("size", 0) or 0),
                sha256=str(item.get("sha256", "")),
                extension=str(item.get("extension", "")),
                risk_hints=[str(hint) for hint in item.get("risk_hints", [])],
            )
        )

    sender = _mailbox_from_context(context.get("sender")) or Mailbox()
    recipients = [
        mailbox
        for item in context.get("recipients", [])
        if (mailbox := _mailbox_from_context(item)) is not None
    ]
    cc = [
        mailbox
        for item in context.get("cc", [])
        if (mailbox := _mailbox_from_context(item)) is not None
    ]
    headers = context.get("headers", {})
    return ParsedEmail(
        message_id=str(context.get("message_id", "")),
        subject=str(context.get("subject", "")),
        date=str(context.get("date", "")),
        sender=sender,
        reply_to=_mailbox_from_context(context.get("reply_to")),
        return_path=_mailbox_from_context(context.get("return_path")),
        recipients=recipients,
        cc=cc,
        text_body=str(context.get("text_body", "")),
        html_body=str(context.get("html_body", "")),
        urls=urls,
        attachments=attachments,
        headers={str(key): str(value) for key, value in headers.items()}
        if isinstance(headers, dict)
        else {},
        parse_warnings=[str(warning) for warning in context.get("parse_warnings", [])],
    )


def records_from_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert dataset rows into the exact records consumed by V1.1."""

    return [
        build_multiview_record(
            str(row.get("raw_subject") or row.get("subject") or ""),
            str(row.get("raw_text_body") or row.get("text_body") or ""),
            parsed_email_from_row(row),
        )
        for row in rows
    ]


def select_word_text(records: Sequence[dict[str, Any]]) -> list[str]:
    return [str(record.get("word_text", "")) for record in records]


def select_char_text(records: Sequence[dict[str, Any]]) -> list[str]:
    return [str(record.get("char_text", "")) for record in records]


def _numeric_matrix(
    records: Sequence[dict[str, Any]],
    view: str,
    names: tuple[str, ...],
) -> np.ndarray:
    return np.asarray(
        [[float(dict(record.get(view, {})).get(name, 0.0)) for name in names] for record in records],
        dtype=np.float64,
    )


def select_structure_matrix(records: Sequence[dict[str, Any]]) -> np.ndarray:
    return _numeric_matrix(records, "structure", STRUCTURE_FEATURE_NAMES)


def select_intent_matrix(records: Sequence[dict[str, Any]]) -> np.ndarray:
    return _numeric_matrix(records, "intent", INTENT_FEATURE_NAMES)
