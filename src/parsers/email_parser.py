"""Minimal MIME parser placeholder.

成员2 将用完整实现替换此模块：MIME 遍历、URL 规范化、附件风险提示、
发件人关系规则等。此占位版本只提取后端编排所需的 subject/from/reply_to/正文，
以便成员3 独立跑通分析链路。字段语义以 src/domain/schemas.py 为准。
"""

from __future__ import annotations

from email import policy
from email.parser import BytesParser
from email.utils import getaddresses, parseaddr

from src.domain.schemas import Mailbox, ParsedEmail


def _mailbox(raw_header: str | None) -> Mailbox | None:
    if not raw_header:
        return None
    display_name, address = parseaddr(raw_header)
    if not address:
        return None
    domain = address.rsplit("@", 1)[-1].lower() if "@" in address else ""
    return Mailbox(
        display_name=display_name or "",
        address=address,
        domain=domain,
        is_valid="@" in address and bool(domain),
    )


class EmailParser:
    def parse(self, raw: bytes) -> ParsedEmail:
        warnings: list[str] = []
        try:
            msg = BytesParser(policy=policy.default).parsebytes(raw)
        except Exception as exc:  # 损坏 MIME 尽量返回部分结果
            msg = None
            warnings.append(f"parse_error: {exc}")

        if msg is None:
            return ParsedEmail(parse_warnings=warnings)

        subject = msg.get("Subject", "") or ""
        if not msg.get("From"):
            warnings.append("missing_from")

        text_parts: list[str] = []
        html_parts: list[str] = []
        for part in msg.walk():
            if part.is_multipart():
                continue
            content_type = part.get_content_type()
            try:
                payload = part.get_content()
            except Exception:
                warnings.append("undecodable_part")
                continue
            if not isinstance(payload, str):
                continue
            if content_type == "text/plain":
                text_parts.append(payload)
            elif content_type == "text/html":
                html_parts.append(payload)

        sender = _mailbox(msg.get("From")) or Mailbox()
        reply_to = _mailbox(msg.get("Reply-To"))
        recipients = [m for m in (_mailbox(v) for v in getaddresses([msg.get("To", "")])) if m]

        return ParsedEmail(
            message_id=msg.get("Message-ID", "") or "",
            subject=subject,
            date=msg.get("Date", "") or "",
            sender=sender,
            reply_to=reply_to,
            recipients=recipients or [],
            text_body="\n".join(text_parts),
            html_body="\n".join(html_parts),
            parse_warnings=warnings,
        )
