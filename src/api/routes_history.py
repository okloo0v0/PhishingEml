"""Detection history: list, detail, delete."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from src.api.deps import get_history_service
from src.api.responses import ok
from src.domain.enums import RiskLevel
from src.domain.errors import DomainError, ErrorCode
from src.domain.schemas import to_jsonable
from src.services.history_service import HistoryService

router = APIRouter()


@router.get("/detections")
def list_detections(
    request: Request,
    page: int = Query(default=1),
    page_size: int = Query(default=20),
    risk_level: str | None = Query(default=None),
    service: HistoryService = Depends(get_history_service),
):
    if page < 1 or not 1 <= page_size <= 100:
        raise DomainError(ErrorCode.INVALID_PAGINATION, "分页参数不合法", 400)
    if risk_level is not None and risk_level not in {r.value for r in RiskLevel}:
        raise DomainError(ErrorCode.VALIDATION_ERROR, "risk_level 取值非法", 400)
    response = service.list(page, page_size, risk_level)
    return ok(request, to_jsonable(response))


@router.get("/detections/{detection_id}")
def get_detection(
    detection_id: int,
    request: Request,
    service: HistoryService = Depends(get_history_service),
):
    detail = service.detail(detection_id)
    if detail is None:
        raise DomainError(ErrorCode.RECORD_NOT_FOUND, "检测记录不存在", 404)
    return ok(request, detail)


@router.delete("/detections/{detection_id}")
def delete_detection(
    detection_id: int,
    request: Request,
    service: HistoryService = Depends(get_history_service),
):
    if not service.delete(detection_id):
        raise DomainError(ErrorCode.RECORD_NOT_FOUND, "检测记录不存在", 404)
    return ok(request, {})
