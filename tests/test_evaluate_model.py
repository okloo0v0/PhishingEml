from scripts.evaluate_model import _metrics


def test_metrics_include_binary_contract_fields():
    metrics = _metrics(["legitimate", "phishing", "phishing"], __import__("numpy").array([0.1, 0.8, 0.2]), 0.5)
    assert metrics["support"] == 3
    assert 0.0 <= metrics["precision"] <= 1.0
    assert len(metrics["confusion_matrix"]) == 2
