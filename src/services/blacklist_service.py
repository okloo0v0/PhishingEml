"""Blacklist management with indicator validation and duplicate detection."""

from __future__ import annotations

from typing import Any

from src.db.models import iso_z
from src.db.repositories import BlacklistRepository, pagination_for
from src.domain.enums import BlacklistSource, BlacklistStatus, IndicatorType
from src.domain.errors import DomainError, ErrorCode
from src.domain.schemas import BlacklistItem, to_jsonable


def _raise(code: ErrorCode, message: str, status_code: int) -> None:
    raise DomainError(code, message, status_code)


def _normalize_indicator(indicator: str, indicator_type: str) -> str:
    value = indicator.strip()
    if not value:
        _raise(ErrorCode.BLACKLIST_INVALID, "黑名单指标不能为空", 422)
    if indicator_type == IndicatorType.DOMAIN.value:
        lowered = value.lower()
        if "://" in lowered or "/" in lowered or "?" in lowered:
            _raise(
                ErrorCode.BLACKLIST_INVALID,
                "domain 指标不能包含 scheme、path 或 query",
                422,
            )
        return lowered
    return value


def _validate_confidence(confidence: float | None) -> float | None:
    if confidence is None:
        return None
    if not 0.0 <= confidence <= 1.0:
        _raise(ErrorCode.BLACKLIST_INVALID, "confidence 必须在 0--1", 422)
    return confidence


class BlacklistService:
    def __init__(self, blacklist_repo: BlacklistRepository) -> None:
        self.blacklist_repo = blacklist_repo

    def list(
        self,
        keyword: str | None,
        status: str | None,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        if status and status not in {s.value for s in BlacklistStatus}:
            _raise(ErrorCode.BLACKLIST_INVALID, "status 取值非法", 422)
        items, total = self.blacklist_repo.list_indicators(
            keyword, status, page, page_size
        )
        return {
            "items": to_jsonable(items),
            "pagination": to_jsonable(pagination_for(page, page_size, total)),
        }

    def create(
        self,
        indicator: str,
        indicator_type: str,
        source: str,
        note: str | None,
        confidence: float | None,
    ) -> dict[str, Any]:
        if indicator_type not in {t.value for t in IndicatorType}:
            _raise(ErrorCode.BLACKLIST_INVALID, "indicator_type 取值非法", 422)
        if source not in {s.value for s in BlacklistSource}:
            _raise(ErrorCode.BLACKLIST_INVALID, "source 取值非法", 422)
        confidence = _validate_confidence(confidence)

        normalized = _normalize_indicator(indicator, indicator_type)
        if self.blacklist_repo.get_by_indicator(normalized, indicator_type):
            _raise(ErrorCode.DUPLICATE_INDICATOR, "黑名单指标已存在", 409)

        row = self.blacklist_repo.create(
            normalized, indicator_type, source, confidence, note
        )
        return to_jsonable(
            BlacklistItem(
                id=row.id,
                indicator=row.indicator,
                indicator_type=IndicatorType(row.indicator_type),
                source=BlacklistSource(row.source),
                status=BlacklistStatus(row.status),
                confidence=row.confidence,
                note=row.note or "",
                hit_count=0,
                created_at=iso_z(row.created_at),
                updated_at=iso_z(row.updated_at),
            )
        )

    def update(
        self,
        indicator_id: int,
        status: str | None,
        confidence: float | None,
        note: str | None,
    ) -> dict[str, Any]:
        row = self.blacklist_repo.get_by_id(indicator_id)
        if row is None:
            _raise(ErrorCode.RECORD_NOT_FOUND, "黑名单记录不存在", 404)

        fields: dict[str, Any] = {}
        if status is not None:
            if status not in {s.value for s in BlacklistStatus}:
                _raise(ErrorCode.BLACKLIST_INVALID, "status 取值非法", 422)
            fields["status"] = status
        if confidence is not None:
            fields["confidence"] = _validate_confidence(confidence)
        if note is not None:
            fields["note"] = note

        row = self.blacklist_repo.update(row, **fields)
        return to_jsonable(
            BlacklistItem(
                id=row.id,
                indicator=row.indicator,
                indicator_type=IndicatorType(row.indicator_type),
                source=BlacklistSource(row.source),
                status=BlacklistStatus(row.status),
                confidence=row.confidence,
                note=row.note or "",
                hit_count=self.blacklist_repo.hit_count(row),
                created_at=iso_z(row.created_at),
                updated_at=iso_z(row.updated_at),
            )
        )
