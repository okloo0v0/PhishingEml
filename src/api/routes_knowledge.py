"""Knowledge articles and user feedback."""

from __future__ import annotations

import itertools
import logging

from fastapi import APIRouter, Depends, Query, Request

from src.api.responses import ok
from src.api.schemas import FeedbackCreate
from src.db.models import iso_z, utcnow
from src.db.repositories import DetectionRepository
from src.domain.enums import FeedbackLabel
from src.domain.errors import DomainError, ErrorCode
from src.domain.schemas import to_jsonable
from src.services.statistics_service import list_knowledge
from src.api.deps import get_db
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
router = APIRouter()

_feedback_counter = itertools.count(1)


@router.get("/knowledge")
def knowledge(
    request: Request,
    keyword: str | None = Query(default=None),
    category: str | None = Query(default=None),
):
    return ok(request, list_knowledge(keyword, category))


@router.post("/feedback")
def feedback(
    payload: FeedbackCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    if payload.label not in {label.value for label in FeedbackLabel}:
        raise DomainError(ErrorCode.INVALID_FEEDBACK, "反馈标签取值非法", 400)
    if len(payload.note) > 500:
        raise DomainError(ErrorCode.INVALID_FEEDBACK, "反馈备注过长", 400)

    repo = DetectionRepository(db)
    if repo.get_detection(payload.detection_id) is None:
        raise DomainError(ErrorCode.RECORD_NOT_FOUND, "检测记录不存在", 404)

    # 契约未冻结 feedback 表；第一版只做校验与日志，不持久化、不重训。
    logger.info(
        "feedback received: detection_id=%s label=%s",
        payload.detection_id,
        payload.label,
    )
    return ok(
        request,
        to_jsonable(
            {
                "feedback_id": next(_feedback_counter),
                "detection_id": payload.detection_id,
                "label": payload.label,
                "created_at": iso_z(utcnow()),
            }
        ),
    )
