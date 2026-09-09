import json
from types import SimpleNamespace

import src.services.statistics_service as statistics_module
from src.services.statistics_service import StatisticsService


def _write_metadata(path, version):
    path.write_text(
        json.dumps(
            {
                "model_name": "fixture",
                "model_version": version,
                "feature_version": "text-structure-v2" if version == "v1.1.0" else "text-v1",
                "trained_at": "2026-09-08T00:00:00Z",
                "train_count": 1,
                "valid_count": 1,
                "test_count": 1,
                "metrics": {"test_f1": 0.5},
                "test_confusion_matrix": [[1, 0], [0, 1]],
            }
        ),
        encoding="utf-8",
    )


def test_model_metrics_prefers_complete_v1_2_pair_and_falls_back(tmp_path, monkeypatch):
    v1_0_model = tmp_path / "phishing_model.joblib"
    v1_0_meta = tmp_path / "model_meta.json"
    v1_1_model = tmp_path / "phishing_model_v1_1.joblib"
    v1_1_meta = tmp_path / "model_meta_v1_1.json"
    v1_2_model = tmp_path / "phishing_model_v1_2.joblib"
    v1_2_meta = tmp_path / "model_meta_v1_2.json"
    for model in (v1_0_model, v1_1_model, v1_2_model):
        model.write_bytes(b"fixture")
    _write_metadata(v1_0_meta, "v1.0.0")
    _write_metadata(v1_1_meta, "v1.1.0")
    _write_metadata(v1_2_meta, "v1.2.0-four-view-validated")
    monkeypatch.setattr(statistics_module, "get_settings", lambda: SimpleNamespace(model_dir=tmp_path))

    service = StatisticsService(None)
    assert service.model_metrics()["model_version"] == "v1.2.0-four-view-validated"

    v1_2_model.unlink()
    v1_2_meta.unlink()
    assert service.model_metrics()["model_version"] == "v1.1.0"

    v1_1_model.unlink()
    v1_1_meta.unlink()
    assert service.model_metrics()["model_version"] == "v1.0.0"
