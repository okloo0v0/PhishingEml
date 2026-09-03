"""API contract tests for the backend layer."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.api.deps import get_db, get_predictor
from src.db.database import init_db
from src.domain.enums import ResultLabel
from src.domain.errors import DomainError, ErrorCode
from src.domain.schemas import ModelPrediction
from src.main import app


class FakePredictor:
    def predict(self, model_input):
        return ModelPrediction(
            result_label=ResultLabel.PHISHING,
            phishing_probability=0.9,
            model_version="test-model",
            feature_version="text-v1",
        )


@pytest.fixture
def client(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}",
        connect_args={"check_same_thread": False},
    )
    init_db(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_predictor] = lambda: FakePredictor()

    yield TestClient(app)

    app.dependency_overrides.clear()


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    assert "request_id" in resp.json()


def test_analyze_empty_input(client):
    resp = client.post("/api/emails/analyze")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INPUT_REQUIRED"


def test_analyze_input_conflict(client):
    resp = client.post(
        "/api/emails/analyze",
        files={"file": ("mail.eml", b"Subject: hi", "message/rfc822")},
        data={"raw_text": "Subject: hi"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INPUT_CONFLICT"


def test_analyze_invalid_file_type(client):
    resp = client.post(
        "/api/emails/analyze",
        files={"file": ("note.txt", b"hello", "text/plain")},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_FILE_TYPE"


def test_analyze_success(client):
    raw = b"From: a@example.com\r\nSubject: test\r\n\r\nhello"
    resp = client.post(
        "/api/emails/analyze",
        files={"file": ("mail.eml", raw, "message/rfc822")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["result_label"] == "phishing"
    assert body["data"]["model_version"] == "test-model"
    assert body["data"]["detection_id"] is not None


def test_analyze_model_not_ready(client):
    def override_predictor():
        raise DomainError(ErrorCode.MODEL_NOT_READY, "模型未就绪", 503)

    app.dependency_overrides[get_predictor] = override_predictor
    resp = client.post(
        "/api/emails/analyze",
        files={"file": ("mail.eml", b"Subject: hi", "message/rfc822")},
    )
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "MODEL_NOT_READY"


def test_blacklist_create_and_duplicate(client):
    resp = client.post(
        "/api/blacklist",
        json={"indicator": "bad.example.invalid", "indicator_type": "domain", "source": "manual"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["indicator"] == "bad.example.invalid"

    dup = client.post(
        "/api/blacklist",
        json={"indicator": "bad.example.invalid", "indicator_type": "domain", "source": "manual"},
    )
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "DUPLICATE_INDICATOR"


def test_history_list_empty(client):
    resp = client.get("/api/detections")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["pagination"]["total"] == 0
    assert body["data"]["items"] == []


def test_analysis_integrates_member2_rules_and_blacklist_metadata(client):
    blacklist = client.post(
        "/api/blacklist",
        json={
            "indicator": "bad.example.invalid",
            "indicator_type": "domain",
            "source": "manual",
            "confidence": 0.95,
        },
    )
    assert blacklist.status_code == 200
    indicator_id = blacklist.json()["data"]["id"]

    raw = (
        b"From: notice@example.invalid\r\n"
        b"Subject: Verify account\r\n"
        b"Reply-To: support@other.invalid\r\n"
        b"Message-ID: <integration@example.invalid>\r\n"
        b"Date: Tue, 1 Sep 2026 10:00:00 +0000\r\n"
        b"\r\n"
        b"Urgent: verify your password at http://bad.example.invalid/login"
    )
    response = client.post(
        "/api/emails/analyze",
        files={"file": ("integration.eml", raw, "message/rfc822")},
    )
    assert response.status_code == 200
    result = response.json()["data"]
    assert result["rule_score"] >= 40.0
    assert "R01" in {item["code"] for item in result["explanations"]}
    assert "R03" in {item["code"] for item in result["explanations"]}
    assert result["urls"][0]["blacklist_hit"] is True
    assert result["urls"][0]["blacklist_match_type"] == "registrable_domain"
    assert result["urls"][0]["blacklist_indicator_id"] == indicator_id
    assert result["urls"][0]["blacklist_source"] == "manual"
    assert result["urls"][0]["blacklist_confidence"] == 0.95

    detail = client.get(f"/api/detections/{result['detection_id']}")
    assert detail.status_code == 200
    assert detail.json()["data"]["urls"][0]["blacklist_indicator_id"] == indicator_id
