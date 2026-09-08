"""Pydantic request bodies for the API layer."""

from __future__ import annotations

from pydantic import BaseModel


class BlacklistCreate(BaseModel):
    indicator: str
    indicator_type: str
    source: str = "manual"
    note: str | None = None
    confidence: float | None = None


class BlacklistUpdate(BaseModel):
    status: str | None = None
    confidence: float | None = None
    note: str | None = None


class FeedbackCreate(BaseModel):
    detection_id: int
    label: str
    note: str = ""
