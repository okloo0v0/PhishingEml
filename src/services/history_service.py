"""Detection history read/delete and detail reconstruction."""

from __future__ import annotations

from typing import Any

from src.db.models import iso_z
from src.db.repositories import DetectionRepository, loads
from src.domain.enums import BlacklistMatchType, BlacklistSource, ResultLabel, RiskLevel
from src.domain.schemas import (
    AttachmentMeta,
    HistoryResponse,
    Pagination,
    ParsedUrl,
    to_jsonable,
)


def _url_from_row(row) -> ParsedUrl:
    features = loads(row.features, {})
    return ParsedUrl(
        raw_url=row.raw_url,
        normalized_url=row.normalized_url,
        display_text=row.display_text or "",
        scheme=features.get("scheme", ""),
        host=row.domain or "",
        registrable_domain=row.domain or "",
        is_https=bool(features.get("is_https", False)),
        uses_ip=bool(features.get("uses_ip", False)),
        is_shortener=bool(features.get("is_shortener", False)),
        suspicious_tokens=list(features.get("suspicious_tokens", [])),
        blacklist_hit=bool(row.blacklist_hit),
        blacklist_indicator_id=features.get("blacklist_indicator_id"),
        blacklist_match_type=(
            BlacklistMatchType(features["blacklist_match_type"])
            if features.get("blacklist_match_type")
            else None
        ),
        blacklist_source=(
            BlacklistSource(features["blacklist_source"])
            if features.get("blacklist_source")
            else None
        ),
        blacklist_confidence=features.get("blacklist_confidence"),
    )


def _attachment_from_row(row) -> AttachmentMeta:
    return AttachmentMeta(
        filename=row.filename or "",
        mime_type=row.mime_type or "",
        size=row.size,
        sha256=row.sha256 or "",
        risk_hints=loads(row.risk_hints, []),
    )


class HistoryService:
    def __init__(self, detection_repo: DetectionRepository) -> None:
        self.detection_repo = detection_repo

    def list(
        self, page: int, page_size: int, risk_level: str | None
    ) -> HistoryResponse:
        items, total = self.detection_repo.list_detections(page, page_size, risk_level)
        total_pages = (total + page_size - 1) // page_size if total else 0
        return HistoryResponse(
            items=items,
            pagination=Pagination(
                page=page, page_size=page_size, total=total, total_pages=total_pages
            ),
        )

    def detail(self, detection_id: int) -> dict[str, Any] | None:
        detection = self.detection_repo.get_detection(detection_id)
        if detection is None:
            return None
        email = detection.email
        return to_jsonable(
            {
                "detection_id": detection.id,
                "result_label": ResultLabel(detection.result_label),
                "risk_level": RiskLevel(detection.risk_level),
                "model_probability": detection.model_probability,
                "rule_score": detection.rule_score,
                "final_score": detection.final_score,
                "model_version": detection.model_version,
                "explanations": loads(detection.explanations, []),
                "advice": loads(detection.advice, []),
                "created_at": iso_z(detection.created_at),
                "email": {
                    "subject": email.subject or "",
                    "sender": loads(email.sender, {}) if email.sender else {},
                    "reply_to": loads(email.reply_to, {}) if email.reply_to else None,
                    "text_body": email.text_body or "",
                    "html_body": email.html_body or "",
                    "filename": email.filename or "",
                    "parse_warnings": loads(email.parse_warnings, []),
                },
                "urls": [_url_from_row(row) for row in email.urls],
                "attachments": [_attachment_from_row(row) for row in email.attachments],
            }
        )

    def delete(self, detection_id: int) -> bool:
        return self.detection_repo.delete_detection(detection_id)
