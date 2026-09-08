"""FastAPI dependency wiring: sessions, predictor singleton, services."""

from __future__ import annotations

from functools import lru_cache

from fastapi import Depends
from sqlalchemy.orm import Session

from src.db.database import SessionLocal
from src.db.repositories import (
    BlacklistRepository,
    DetectionRepository,
    StatisticsRepository,
)
from src.detection.model_predictor import ModelPredictor
from src.detection.rule_engine import RuleEngine
from src.parsers.email_parser import EmailParser
from src.services.analysis_service import AnalysisService
from src.services.blacklist_service import BlacklistService
from src.services.history_service import HistoryService
from src.services.statistics_service import StatisticsService


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@lru_cache(maxsize=1)
def get_predictor() -> ModelPredictor:
    return ModelPredictor()


_parser = EmailParser()
_rule_engine = RuleEngine()


def get_analysis_service(
    db: Session = Depends(get_db),
    predictor: ModelPredictor = Depends(get_predictor),
) -> AnalysisService:
    return AnalysisService(
        _parser,
        _rule_engine,
        predictor,
        BlacklistRepository(db),
        DetectionRepository(db),
    )


def get_history_service(db: Session = Depends(get_db)) -> HistoryService:
    return HistoryService(DetectionRepository(db))


def get_blacklist_service(db: Session = Depends(get_db)) -> BlacklistService:
    return BlacklistService(BlacklistRepository(db))


def get_statistics_service(db: Session = Depends(get_db)) -> StatisticsService:
    return StatisticsService(StatisticsRepository(db))
