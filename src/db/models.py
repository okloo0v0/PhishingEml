"""SQLAlchemy ORM models matching the frozen database contract."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from src.db.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso_z(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class Email(Base):
    __tablename__ = "emails"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_hash = Column(String(64), nullable=False)
    filename = Column(String(255))
    subject = Column(Text)
    sender = Column(Text)
    reply_to = Column(Text)
    text_body = Column(Text)
    html_body = Column(Text)
    parse_warnings = Column(Text)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    detections = relationship(
        "Detection", back_populates="email", cascade="all, delete-orphan"
    )
    urls = relationship("EmailUrl", back_populates="email", cascade="all, delete-orphan")
    attachments = relationship(
        "Attachment", back_populates="email", cascade="all, delete-orphan"
    )


class Detection(Base):
    __tablename__ = "detections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email_id = Column(Integer, ForeignKey("emails.id"), nullable=False)
    result_label = Column(String(32), nullable=False)
    risk_level = Column(String(16), nullable=False)
    model_probability = Column(Float, nullable=False)
    rule_score = Column(Float, nullable=False)
    final_score = Column(Float, nullable=False)
    model_version = Column(String(64), nullable=False)
    explanations = Column(Text, nullable=False)
    advice = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    email = relationship("Email", back_populates="detections")


class EmailUrl(Base):
    __tablename__ = "email_urls"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email_id = Column(Integer, ForeignKey("emails.id"), nullable=False)
    display_text = Column(Text)
    raw_url = Column(Text, nullable=False)
    normalized_url = Column(Text, nullable=False)
    domain = Column(String(255))
    features = Column(Text, nullable=False)
    blacklist_hit = Column(Boolean, default=False, nullable=False)

    email = relationship("Email", back_populates="urls")


class Attachment(Base):
    __tablename__ = "attachments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email_id = Column(Integer, ForeignKey("emails.id"), nullable=False)
    filename = Column(String(255))
    mime_type = Column(String(255))
    size = Column(Integer, default=0, nullable=False)
    sha256 = Column(String(64))
    risk_hints = Column(Text, nullable=False)

    email = relationship("Email", back_populates="attachments")


class BlacklistIndicator(Base):
    __tablename__ = "blacklist_indicators"

    id = Column(Integer, primary_key=True, autoincrement=True)
    indicator = Column(String(2048), nullable=False, unique=True)
    indicator_type = Column(String(16), nullable=False)
    source = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False, default="active")
    confidence = Column(Float)
    note = Column(Text)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
