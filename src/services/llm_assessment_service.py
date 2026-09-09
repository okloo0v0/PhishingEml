"""On-demand LLM assessment for an already persisted local detection."""

from __future__ import annotations

from typing import Any

from src.db.models import iso_z, utcnow
from src.db.repositories import DetectionRepository, loads
from src.detection.deepseek_client import DeepSeekUnavailable
from src.domain.enums import Severity
from src.domain.errors import DomainError, ErrorCode
from src.domain.schemas import Explanation, Mailbox, ParsedEmail
from src.services.history_service import _attachment_from_row, _url_from_row


def _mailbox(value: str | None) -> Mailbox:
    payload = loads(value, {}) if value else {}
    return Mailbox(
        display_name=str(payload.get("display_name", "")),
        address=str(payload.get("address", "")),
        domain=str(payload.get("domain", "")),
        is_valid=bool(payload.get("is_valid", False)),
    )


def _explanations(value: str | None) -> list[Explanation]:
    items: list[Explanation] = []
    for payload in loads(value, []):
        if not isinstance(payload, dict):
            continue
        try:
            severity = Severity(payload.get("severity", Severity.WARNING.value))
        except ValueError:
            severity = Severity.WARNING
        items.append(
            Explanation(
                code=str(payload.get("code", "")),
                title=str(payload.get("title", "")),
                detail=str(payload.get("detail", "")),
                evidence=str(payload.get("evidence", "")),
                score=float(payload.get("score", 0.0)),
                severity=severity,
            )
        )
    return items


class LlmAssessmentService:
    """Generate and persist an optional explanation without changing local scoring."""

    def __init__(self, detection_repo: DetectionRepository, llm_client) -> None:
        self.detection_repo = detection_repo
        self.llm_client = llm_client

    def assess(self, detection_id: int) -> dict[str, Any]:
        detection = self.detection_repo.get_detection(detection_id)
        if detection is None:
            raise DomainError(ErrorCode.RECORD_NOT_FOUND, "检测记录不存在", 404)
        if self.llm_client is None or not self.llm_client.enabled:
            raise DomainError(ErrorCode.LLM_NOT_ENABLED, "智能辅助解读未启用", 503)

        email = detection.email
        parsed = ParsedEmail(
            subject=email.subject or "",
            sender=_mailbox(email.sender),
            reply_to=_mailbox(email.reply_to) if email.reply_to else None,
            text_body=email.text_body or "",
            html_body=email.html_body or "",
            urls=[_url_from_row(row) for row in email.urls],
            attachments=[_attachment_from_row(row) for row in email.attachments],
            parse_warnings=loads(email.parse_warnings, []),
        )
        try:
            assessment = self.llm_client.assess(
                parsed,
                detection.rule_score,
                _explanations(detection.explanations),
                detection.model_probability,
            )
        except DeepSeekUnavailable:
            self.detection_repo.update_llm_assessment(detection, None, "unavailable")
            return {
                "detection_id": detection.id,
                "llm_status": "unavailable",
                "llm_assessment": None,
            }

        assessment.provider = "DeepSeek"
        assessment.model_name = str(getattr(self.llm_client, "model", ""))
        assessment.generated_at = iso_z(utcnow())
        self.detection_repo.update_llm_assessment(detection, assessment, "completed")
        return {
            "detection_id": detection.id,
            "llm_status": "completed",
            "llm_assessment": assessment,
        }
