import hashlib
import json

import joblib
import pytest

from scripts.train_model import build_pipeline
from src.detection.model_predictor import ModelPredictor
from src.domain.enums import ResultLabel
from src.domain.errors import DomainError, ErrorCode
from src.domain.schemas import ModelInput


def _write_fixture(tmp_path):
    model_path = tmp_path / "phishing_model.joblib"
    metadata_path = tmp_path / "model_meta.json"
    pipeline = build_pipeline()
    pipeline.fit(
        [
            "urgent verify account immediately",
            "account security confirmation required",
            "weekly team meeting agenda",
            "project planning notes for team",
        ],
        ["phishing", "phishing", "legitimate", "legitimate"],
    )
    joblib.dump(pipeline, model_path)
    digest = hashlib.sha256(model_path.read_bytes()).hexdigest()
    metadata_path.write_text(json.dumps({
        "model_name": "tfidf_logistic_regression",
        "model_version": "test-model",
        "feature_version": "text-v1",
        "trained_at": "2026-09-01T00:00:00Z",
        "label_order": ["legitimate", "phishing"],
        "metrics": {"test_f1": 1.0},
        "artifact_filename": model_path.name,
        "metadata_filename": metadata_path.name,
        "artifact_sha256": digest,
    }), encoding="utf-8")
    return model_path, metadata_path


def test_predictor_cleans_parser_fields_and_returns_contract_prediction(tmp_path):
    model_path, metadata_path = _write_fixture(tmp_path)
    predictor = ModelPredictor(model_path, metadata_path)

    prediction = predictor.predict(ModelInput(subject="Urgent account alert", text_body="Verify at https://example.invalid/login"))

    assert prediction.model_version == "test-model"
    assert prediction.feature_version == "text-v1"
    assert 0.0 <= prediction.phishing_probability <= 1.0
    assert prediction.result_label in {ResultLabel.LEGITIMATE, ResultLabel.PHISHING}


def test_predictor_accepts_prebuilt_model_text_for_empty_fields(tmp_path):
    model_path, metadata_path = _write_fixture(tmp_path)
    prediction = ModelPredictor(model_path, metadata_path).predict(ModelInput(model_text="team meeting notes"))

    assert prediction.result_label == ResultLabel.LEGITIMATE


def test_predictor_maps_missing_artifact_to_model_not_ready(tmp_path):
    with pytest.raises(DomainError) as error:
        ModelPredictor(tmp_path / "missing.joblib", tmp_path / "missing.json")

    assert error.value.code == ErrorCode.MODEL_NOT_READY
    assert error.value.status_code == 503


def test_predictor_rejects_feature_version_mismatch(tmp_path):
    model_path, metadata_path = _write_fixture(tmp_path)
    predictor = ModelPredictor(model_path, metadata_path)

    with pytest.raises(ValueError, match="feature_version"):
        predictor.predict(ModelInput(model_text="text", feature_version="text-v2"))
