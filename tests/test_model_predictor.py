import hashlib
import json

import joblib
import pytest

from scripts.train_model import build_pipeline
import src.detection.model_predictor as model_predictor_module
from src.detection.model_predictor import ModelPredictor
from src.detection.multiview_features import build_multiview_record
from src.detection.multiview_model import MultiViewPhishingClassifier
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


def test_predictor_supports_v1_1_multiview_artifact(tmp_path):
    samples = [
        ("Urgent password", "Verify account now", "phishing"),
        ("Wire transfer", "Confidential payment request", "phishing"),
        ("Team meeting", "Weekly project agenda", "legitimate"),
        ("Course notes", "Lecture schedule", "legitimate"),
    ]
    model = MultiViewPhishingClassifier(
        word_max_features=100,
        char_max_features=200,
        min_df=1,
        cv_splits=2,
    ).fit(
        [build_multiview_record(subject, body) for subject, body, _ in samples],
        [label for _, _, label in samples],
    )
    model_path = tmp_path / "phishing_model_v1_1.joblib"
    metadata_path = tmp_path / "model_meta_v1_1.json"
    joblib.dump(model, model_path)
    digest = hashlib.sha256(model_path.read_bytes()).hexdigest()
    metadata_path.write_text(
        json.dumps(
            {
                "model_name": "multiview_late_fusion_logistic_regression",
                "model_version": "v1.1.0-test",
                "feature_version": "text-structure-v2",
                "trained_at": "2026-09-08T00:00:00Z",
                "label_order": ["legitimate", "phishing"],
                "metrics": {"test_f1": 1.0},
                "artifact_filename": model_path.name,
                "metadata_filename": metadata_path.name,
                "artifact_sha256": digest,
            }
        ),
        encoding="utf-8",
    )

    predictor = ModelPredictor(model_path, metadata_path)
    prediction = predictor.predict(
        ModelInput(
            subject="Urgent payment",
            text_body="Immediately confirm the bank account",
            feature_version="text-structure-v2",
        )
    )

    assert prediction.model_version == "v1.1.0-test"
    assert prediction.feature_version == "text-structure-v2"
    assert 0.0 <= prediction.phishing_probability <= 1.0


def test_predictor_defaults_to_v1_0_when_v1_1_pair_is_missing(tmp_path, monkeypatch):
    model_path, metadata_path = _write_fixture(tmp_path)
    monkeypatch.setattr(model_predictor_module, "V1_1_MODEL_PATH", tmp_path / "missing-v1-1.joblib")
    monkeypatch.setattr(model_predictor_module, "V1_1_METADATA_PATH", tmp_path / "missing-v1-1.json")
    monkeypatch.setattr(model_predictor_module, "V1_2_MODEL_PATH", tmp_path / "missing-v1-2.joblib")
    monkeypatch.setattr(model_predictor_module, "V1_2_METADATA_PATH", tmp_path / "missing-v1-2.json")
    monkeypatch.setattr(model_predictor_module, "DEFAULT_MODEL_PATH", model_path)
    monkeypatch.setattr(model_predictor_module, "DEFAULT_METADATA_PATH", metadata_path)

    predictor = ModelPredictor()

    assert predictor.metadata.model_version == "test-model"
    assert predictor.metadata.feature_version == "text-v1"


def test_predictor_defaults_to_v1_2_when_valid_pair_exists(tmp_path, monkeypatch):
    model_path, _ = _write_fixture(tmp_path)
    metadata_path = tmp_path / "model_meta_v1_2.json"
    payload = json.loads((tmp_path / "model_meta.json").read_text(encoding="utf-8"))
    payload["model_version"] = "v1.2.0-test"
    payload["artifact_filename"] = model_path.name
    payload["metadata_filename"] = metadata_path.name
    metadata_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(model_predictor_module, "V1_2_MODEL_PATH", model_path)
    monkeypatch.setattr(model_predictor_module, "V1_2_METADATA_PATH", metadata_path)
    monkeypatch.setattr(model_predictor_module, "V1_1_MODEL_PATH", tmp_path / "missing-v1-1.joblib")
    monkeypatch.setattr(model_predictor_module, "V1_1_METADATA_PATH", tmp_path / "missing-v1-1.json")
    predictor = ModelPredictor()
    assert predictor.metadata.model_version == "v1.2.0-test"
