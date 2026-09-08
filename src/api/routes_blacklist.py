"""Blacklist management: list, create, update."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from src.api.deps import get_blacklist_service
from src.api.responses import ok
from src.api.schemas import BlacklistCreate, BlacklistUpdate
from src.domain.errors import DomainError, ErrorCode
from src.services.blacklist_service import BlacklistService

router = APIRouter()


@router.get("/blacklist")
def list_blacklist(
    request: Request,
    keyword: str | None = Query(default=None),
    status: str | None = Query(default=None),
    page: int = Query(default=1),
    page_size: int = Query(default=20),
    service: BlacklistService = Depends(get_blacklist_service),
):
    if page < 1 or not 1 <= page_size <= 100:
        raise DomainError(ErrorCode.INVALID_PAGINATION, "分页参数不合法", 400)
    return ok(request, service.list(keyword, status, page, page_size))


@router.post("/blacklist")
def create_blacklist(
    payload: BlacklistCreate,
    request: Request,
    service: BlacklistService = Depends(get_blacklist_service),
):
    return ok(
        request,
        service.create(
            payload.indicator,
            payload.indicator_type,
            payload.source,
            payload.note,
            payload.confidence,
        ),
    )


@router.patch("/blacklist/{indicator_id}")
def update_blacklist(
    indicator_id: int,
    payload: BlacklistUpdate,
    request: Request,
    service: BlacklistService = Depends(get_blacklist_service),
):
    return ok(
        request,
        service.update(
            indicator_id,
            payload.status,
            payload.confidence,
            payload.note,
        ),
    )
