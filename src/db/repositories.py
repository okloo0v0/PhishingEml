"""Data access layer. Repositories map ORM rows to contract domain objects."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from src.db.models import (
    Attachment,
    BlacklistIndicator,
    Detection,
    Email,
    EmailUrl,
    iso_z,
    utcnow,
)
from src.domain.enums import (
    BlacklistSource,
    BlacklistStatus,
    IndicatorType,
    ResultLabel,
    RiskLevel,
)
from src.domain.schemas import (
    BlacklistItem,
    DetectionSummary,
    Mailbox,
    Pagination,
    ParsedEmail,
    to_jsonable,
)


def dumps(value: Any) -> str:
    return json.dumps(to_jsonable(value), ensure_ascii=False)


def loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def _mailbox(payload: Any) -> Mailbox:
    data = loads(payload, {}) if isinstance(payload, str) else (payload or {})
    return Mailbox(
        display_name=data.get("display_name", ""),
        address=data.get("address", ""),
        domain=data.get("domain", ""),
        is_valid=bool(data.get("is_valid", False)),
    )


class DetectionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def save_analysis(
        self,
        parsed: ParsedEmail,
        result: Any,
        filename: str,
        file_hash: str,
    ) -> int:
        email = Email(
            file_hash=file_hash,
            filename=filename,
            subject=parsed.subject,
            sender=dumps(parsed.sender),
            reply_to=dumps(parsed.reply_to) if parsed.reply_to is not None else None,
            text_body=parsed.text_body,
            html_body=parsed.html_body,
            parse_warnings=dumps(parsed.parse_warnings),
        )
        self.session.add(email)
        self.session.flush()

        for url in result.urls:
            self.session.add(
                EmailUrl(
                    email_id=email.id,
                    display_text=url.display_text,
                    raw_url=url.raw_url,
                    normalized_url=url.normalized_url,
                    domain=url.registrable_domain or url.host,
                    features=dumps(
                        {
                            "scheme": url.scheme,
                            "is_https": url.is_https,
                            "uses_ip": url.uses_ip,
                            "is_shortener": url.is_shortener,
                            "suspicious_tokens": url.suspicious_tokens,
                            "blacklist_indicator_id": url.blacklist_indicator_id,
                        }
                    ),
                    blacklist_hit=url.blacklist_hit,
                )
            )

        for att in result.attachments:
            self.session.add(
                Attachment(
                    email_id=email.id,
                    filename=att.filename,
                    mime_type=att.mime_type,
                    size=att.size,
                    sha256=att.sha256,
                    risk_hints=dumps(att.risk_hints),
                )
            )

        detection = Detection(
            email_id=email.id,
            result_label=result.result_label.value,
            risk_level=result.risk_level.value,
            model_probability=result.model_probability,
            rule_score=result.rule_score,
            final_score=result.final_score,
            model_version=result.model_version,
            explanations=dumps(result.explanations),
            advice=dumps(result.advice),
        )
        self.session.add(detection)
        self.session.commit()
        return detection.id

    def list_detections(
        self, page: int, page_size: int, risk_level: str | None
    ) -> tuple[list[DetectionSummary], int]:
        conditions = []
        if risk_level:
            conditions.append(Detection.risk_level == risk_level)

        total = self.session.scalar(
            select(func.count()).select_from(Detection).where(*conditions)
        )

        stmt = (
            select(Detection)
            .options(
                joinedload(Detection.email).joinedload(Email.urls),
                joinedload(Detection.email).joinedload(Email.attachments),
            )
            .where(*conditions)
            .order_by(Detection.created_at.desc(), Detection.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        detections = self.session.scalars(stmt).unique().all()
        items = [
            DetectionSummary(
                detection_id=d.id,
                subject=d.email.subject or "",
                result_label=ResultLabel(d.result_label),
                risk_level=RiskLevel(d.risk_level),
                final_score=d.final_score,
                url_count=len(d.email.urls),
                attachment_count=len(d.email.attachments),
                model_version=d.model_version,
                created_at=iso_z(d.created_at),
            )
            for d in detections
        ]
        return items, total or 0

    def get_detection(self, detection_id: int) -> Detection | None:
        stmt = (
            select(Detection)
            .options(
                joinedload(Detection.email)
                .joinedload(Email.urls),
                joinedload(Detection.email)
                .joinedload(Email.attachments),
            )
            .where(Detection.id == detection_id)
        )
        return self.session.scalars(stmt).unique().first()

    def delete_detection(self, detection_id: int) -> bool:
        detection = self.session.get(Detection, detection_id)
        if detection is None:
            return False
        self.session.delete(detection)
        self.session.commit()
        return True


class BlacklistRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_indicators(
        self, keyword: str | None, status: str | None, page: int, page_size: int
    ) -> tuple[list[BlacklistItem], int]:
        conditions = []
        if keyword:
            conditions.append(BlacklistIndicator.indicator.contains(keyword))
        if status:
            conditions.append(BlacklistIndicator.status == status)

        total = self.session.scalar(
            select(func.count()).select_from(BlacklistIndicator).where(*conditions)
        )
        rows = self.session.scalars(
            select(BlacklistIndicator)
            .where(*conditions)
            .order_by(BlacklistIndicator.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()

        items = [
            BlacklistItem(
                id=row.id,
                indicator=row.indicator,
                indicator_type=IndicatorType(row.indicator_type),
                source=BlacklistSource(row.source),
                status=BlacklistStatus(row.status),
                confidence=row.confidence,
                note=row.note or "",
                hit_count=self.hit_count(row),
                created_at=iso_z(row.created_at),
                updated_at=iso_z(row.updated_at),
            )
            for row in rows
        ]
        return items, total or 0

    def hit_count(self, row: BlacklistIndicator) -> int:
        column = (
            EmailUrl.normalized_url
            if row.indicator_type == IndicatorType.URL.value
            else EmailUrl.domain
        )
        return self.session.scalar(
            select(func.count()).select_from(EmailUrl).where(column == row.indicator)
        ) or 0

    def get_by_id(self, indicator_id: int) -> BlacklistIndicator | None:
        return self.session.get(BlacklistIndicator, indicator_id)

    def get_by_indicator(
        self, indicator: str, indicator_type: str
    ) -> BlacklistIndicator | None:
        return self.session.scalar(
            select(BlacklistIndicator).where(
                BlacklistIndicator.indicator == indicator,
                BlacklistIndicator.indicator_type == indicator_type,
            )
        )

    def create(
        self,
        indicator: str,
        indicator_type: str,
        source: str,
        confidence: float | None,
        note: str | None,
    ) -> BlacklistIndicator:
        row = BlacklistIndicator(
            indicator=indicator,
            indicator_type=indicator_type,
            source=source,
            status=BlacklistStatus.ACTIVE.value,
            confidence=confidence,
            note=note or "",
        )
        self.session.add(row)
        self.session.commit()
        return row

    def update(
        self, row: BlacklistIndicator, **fields: Any
    ) -> BlacklistIndicator:
        for key, value in fields.items():
            if hasattr(row, key):
                setattr(row, key, value)
        row.updated_at = utcnow()
        self.session.commit()
        return row

    def active_sets(self) -> tuple[set[str], set[str]]:
        rows = self.session.scalars(
            select(BlacklistIndicator).where(
                BlacklistIndicator.status == BlacklistStatus.ACTIVE.value
            )
        ).all()
        urls = {r.indicator for r in rows if r.indicator_type == IndicatorType.URL.value}
        domains = {
            r.indicator for r in rows if r.indicator_type == IndicatorType.DOMAIN.value
        }
        return urls, domains


class StatisticsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def overview(self) -> dict[str, Any]:
        total = self.session.scalar(select(func.count()).select_from(Detection)) or 0

        risk_rows = self.session.execute(
            select(Detection.risk_level, func.count()).group_by(Detection.risk_level)
        ).all()
        risk_counts = {RiskLevel.LOW.value: 0, RiskLevel.MEDIUM.value: 0, RiskLevel.HIGH.value: 0}
        for level, count in risk_rows:
            risk_counts[level] = count

        label_rows = self.session.execute(
            select(Detection.result_label, func.count()).group_by(Detection.result_label)
        ).all()
        result_counts = {ResultLabel.LEGITIMATE.value: 0, ResultLabel.PHISHING.value: 0}
        for label, count in label_rows:
            result_counts[label] = count

        rule_hit_counts: dict[str, int] = {}
        for (explanations,) in self.session.execute(select(Detection.explanations)).all():
            for explanation in loads(explanations, []):
                code = explanation.get("code") if isinstance(explanation, dict) else None
                if code:
                    rule_hit_counts[code] = rule_hit_counts.get(code, 0) + 1

        attachment_type_counts: dict[str, int] = {}
        for (mime_type,) in self.session.execute(select(Attachment.mime_type)).all():
            key = mime_type or "unknown"
            attachment_type_counts[key] = attachment_type_counts.get(key, 0) + 1

        daily_counts: dict[str, int] = {}
        for (created_at,) in self.session.execute(select(Detection.created_at)).all():
            day = created_at.date().isoformat()
            daily_counts[day] = daily_counts.get(day, 0) + 1

        return {
            "total_detections": total,
            "risk_counts": risk_counts,
            "result_counts": result_counts,
            "rule_hit_counts": rule_hit_counts,
            "attachment_type_counts": attachment_type_counts,
            "daily_counts": dict(sorted(daily_counts.items())),
        }


def pagination_for(page: int, page_size: int, total: int) -> Pagination:
    total_pages = (total + page_size - 1) // page_size if total else 0
    return Pagination(page=page, page_size=page_size, total=total, total_pages=total_pages)
