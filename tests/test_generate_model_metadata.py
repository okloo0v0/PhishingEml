import json

from scripts.generate_model_metadata import generate


def test_generate_metadata_is_contract_compatible(tmp_path):
    model = tmp_path / "model.joblib"
    model.write_bytes(b"fixture-model")
    training = tmp_path / "training.json"
    training.write_text(json.dumps({
        "model_name": "tfidf_logistic_regression", "model_version": "v1.0.0",
        "feature_version": "text-v1", "trained_at": "2026-09-01T00:00:00Z",
        "label_order": ["legitimate", "phishing"], "random_state": 42,
        "train_count": 4, "valid_count": 1, "test_count": 1,
        "tfidf": {}, "classifier": {}, "artifact_sha256": "",
    }), encoding="utf-8")
    evaluation = tmp_path / "evaluation.json"
    evaluation.write_text(json.dumps({
        "contract_threshold": 0.5, "selected_threshold": 0.44,
        "test": {"contract_metrics": {"precision": 1, "recall": 1, "f1": 1, "accuracy": 1, "confusion_matrix": [[1, 0], [0, 1]]}},
        "cross_source_test": {"contract_metrics": {"precision": 1, "recall": 1, "f1": 1, "accuracy": 1, "confusion_matrix": [[1, 0], [0, 1]]}},
    }), encoding="utf-8")
    split = tmp_path / "split.json"
    split.write_text(json.dumps({"source_counts": {}, "hard_negative_records": 0}), encoding="utf-8")
    report = tmp_path / "dedup_combined_report.json"
    report.write_text("{}", encoding="utf-8")
    metadata = tmp_path / "model_meta.json"
    experiments = tmp_path / "experiments.csv"
    result = generate(model, training, evaluation, split, report, metadata, experiments)
    assert result["label_order"] == ["legitimate", "phishing"]
    assert result["artifact_sha256"]
    assert json.loads(metadata.read_text(encoding="utf-8"))["metadata_filename"] == "model_meta.json"
