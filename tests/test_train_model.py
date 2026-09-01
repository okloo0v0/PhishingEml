import csv

from scripts.train_model import EXPECTED_CLASSES, build_pipeline, train


def test_build_pipeline_uses_frozen_classifier_configuration():
    pipeline = build_pipeline()
    assert pipeline.named_steps["tfidf"].ngram_range == (1, 2)
    assert pipeline.named_steps["classifier"].class_weight == "balanced"
    assert EXPECTED_CLASSES == ["legitimate", "phishing"]


def test_train_fits_only_train_rows_and_writes_probability_predictions(tmp_path):
    input_path = tmp_path / "emails.csv"
    with input_path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=["id", "source", "label", "model_text", "split"])
        writer.writeheader()
        rows = [
            ("p1", "phishing", "urgent verify account", "train"),
            ("p2", "phishing", "account verification required", "train"),
            ("l1", "legitimate", "team meeting agenda", "train"),
            ("l2", "legitimate", "project meeting notes", "train"),
            ("p3", "phishing", "urgent verify", "valid"),
            ("l3", "legitimate", "meeting notes", "test"),
        ]
        for record_id, label, model_text, split in rows:
            writer.writerow({"id": record_id, "source": "fixture", "label": label, "model_text": model_text, "split": split})
    model_path = tmp_path / "model.joblib"
    summary_path = tmp_path / "summary.json"
    predictions_path = tmp_path / "predictions.csv"
    summary = train(input_path, model_path, summary_path, predictions_path)
    assert model_path.exists()
    assert summary["label_order"] == EXPECTED_CLASSES
    with predictions_path.open(encoding="utf-8", newline="") as source:
        predictions = list(csv.DictReader(source))
    assert len(predictions) == 2
    assert all(0.0 <= float(row["phishing_probability"]) <= 1.0 for row in predictions)
