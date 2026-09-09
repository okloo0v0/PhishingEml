"""Explicit user-triggered LLM assistance for saved detections."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from src.api.deps import get_llm_assessment_service
from src.api.responses import ok
from src.domain.schemas import to_jsonable
from src.services.llm_assessment_service import LlmAssessmentService

router = APIRouter()


@router.post("/detections/{detection_id}/llm-assessment")
def create_llm_assessment(
    detection_id: int,
    request: Request,
    service: LlmAssessmentService = Depends(get_llm_assessment_service),
):
    return ok(request, to_jsonable(service.assess(detection_id)))
