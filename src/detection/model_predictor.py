"""Local inference adapter for the frozen phishing model pipeline."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import joblib

from src.domain.enums import ResultLabel
from src.domain.errors import DomainError, ErrorCode
from src.domain.schemas import ModelInput, ModelMetadata, ModelPrediction, validate_model_prediction
from src.domain.scoring import label_for_probability
from src.detection.text_features import FEATURE_VERSION, clean_email_text

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_PATH = ROOT / "models" / "phishing_model.joblib"
DEFAULT_METADATA_PATH = ROOT / "models" / "model_meta.json"
EXPECTED_LABEL_ORDER = [ResultLabel.LEGITIMATE, ResultLabel.PHISHING]


def _model_not_ready(message: str, cause: Exception | None = None) -> DomainError:
    """Build the shared 503 error without exposing loader internals."""
    error = DomainError(ErrorCode.MODEL_NOT_READY, message, 503)
    if cause is not None:
        error.__cause__ = cause
    return error


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _metadata_from_json(payload: dict[str, Any]) -> ModelMetadata:
    required = ("model_name", "model_version", "feature_version", "trained_at", "label_order", "metrics")
    if any(not payload.get(field) for field in required):
        raise ValueError("model metadata is incomplete")
    label_order = [ResultLabel(str(label)) for label in payload["label_order"]]
    return ModelMetadata(
        model_name=str(payload["model_name"]),
        model_version=str(payload["model_version"]),
        feature_version=str(payload["feature_version"]),
        trained_at=str(payload["trained_at"]),
        label_order=label_order,
        metrics={str(key): float(value) for key, value in dict(payload["metrics"]).items()},
        artifact_filename=str(payload.get("artifact_filename", "phishing_model.joblib")),
        metadata_filename=str(payload.get("metadata_filename", "model_meta.json")),
    )


class ModelPredictor:
    """Load and run the versioned local model without network or fallback training."""

    def __init__(
        self,
        model_path: Path = DEFAULT_MODEL_PATH,
        metadata_path: Path = DEFAULT_METADATA_PATH,
    ) -> None:
        self.model_path = Path(model_path)
        self.metadata_path = Path(metadata_path)
        self.metadata, self._pipeline = self._load()
        self._phishing_index = EXPECTED_LABEL_ORDER.index(ResultLabel.PHISHING)

    def _load(self) -> tuple[ModelMetadata, Any]:
        if not self.model_path.is_file() or not self.metadata_path.is_file():
            raise _model_not_ready("模型文件或元数据不存在")
        try:
            payload = json.loads(self.metadata_path.read_text(encoding="utf-8"))
            metadata = _metadata_from_json(payload)
            if metadata.feature_version != FEATURE_VERSION:
                raise ValueError("feature version does not match the runtime")
            if metadata.label_order != EXPECTED_LABEL_ORDER:
                raise ValueError("label order does not match the contract")
            expected_hash = str(payload.get("artifact_sha256", ""))
            if not expected_hash or _sha256(self.model_path) != expected_hash:
                raise ValueError("model artifact integrity check failed")
            pipeline = joblib.load(self.model_path)
            classes = [str(value) for value in getattr(pipeline, "classes_", ())]
            if classes != [label.value for label in EXPECTED_LABEL_ORDER]:
                raise ValueError("model classes do not match the contract")
            if not callable(getattr(pipeline, "predict_proba", None)):
                raise ValueError("model does not provide predict_proba")
            return metadata, pipeline
        except DomainError:
            raise
        except Exception as exc:
            raise _model_not_ready("模型加载或完整性校验失败", exc) from exc

    def predict(self, model_input: ModelInput) -> ModelPrediction:
        """Return a contract-compatible prediction for one email text input."""
        if not isinstance(model_input, ModelInput):
            raise TypeError("model_input must be a ModelInput")
        if model_input.feature_version != self.metadata.feature_version:
            raise ValueError("model_input feature_version does not match the loaded model")

        if model_input.subject or model_input.text_body:
            model_text = clean_email_text(model_input.subject, model_input.text_body).model_text
        else:
            model_text = model_input.model_text or ""
        try:
            probabilities = self._pipeline.predict_proba([model_text])
            probability = float(probabilities[0][self._phishing_index])
        except Exception as exc:
            raise _model_not_ready("模型推理失败", exc) from exc
        prediction = ModelPrediction(
            result_label=label_for_probability(probability),
            phishing_probability=probability,
            model_version=self.metadata.model_version,
            feature_version=self.metadata.feature_version,
        )
        validate_model_prediction(prediction)
        return prediction
