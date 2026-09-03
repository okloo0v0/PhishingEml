"""Dashboard statistics and offline model metrics."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from src.api.deps import get_statistics_service
from src.api.responses import ok
from src.services.statistics_service import StatisticsService

router = APIRouter()


@router.get("/statistics/overview")
def overview(
    request: Request,
    service: StatisticsService = Depends(get_statistics_service),
):
    return ok(request, service.overview())


@router.get("/model/metrics")
def model_metrics(
    request: Request,
    service: StatisticsService = Depends(get_statistics_service),
):
    return ok(request, service.model_metrics())
