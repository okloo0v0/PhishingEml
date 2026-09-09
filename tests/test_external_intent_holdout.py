import json
from pathlib import Path

import joblib

from scripts.evaluate_external_intent_holdout import _load_candidates, _sample_balanced, evaluate
from src.detection.text_features import clean_email_text


class DummyIntentModel:
    def predict_labels(self, rows, thresholds):
        return [["social_pressure"] if "risk" in row["text_body"] else [] for row in rows]


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_external_candidates_drop_training_overlap(tmp_path):
    cleaned = clean_email_text("", "duplicate message")
    training = tmp_path / "training.jsonl"
    _write_jsonl(training, [{"subject": "", "text_body": cleaned.text_body}])
    external = tmp_path / "external.jsonl"
    _write_jsonl(external, [{"text": "duplicate message", "label": 0}, {"text": "new risk message", "label": 1}])

    from scripts.evaluate_external_intent_holdout import _known_fingerprints

    candidates, overlap = _load_candidates(external, _known_fingerprints(training))
    assert overlap == 1
    assert len(candidates) == 1


def test_external_holdout_is_balanced_and_not_used_for_exact_intent_validation(tmp_path):
    external = tmp_path / "external.jsonl"
    rows = [
        {"text": f"safe message {index}", "label": 0} for index in range(4)
    ] + [{"text": f"risk message {index}", "label": 1} for index in range(4)]
    _write_jsonl(external, rows)
    training = tmp_path / "training.jsonl"
    _write_jsonl(training, [{"subject": "training", "text_body": "unrelated"}])
    model = tmp_path / "model.joblib"
    joblib.dump(DummyIntentModel(), model)
    thresholds = tmp_path / "thresholds.json"
    thresholds.write_text(json.dumps({"thresholds": {"social_pressure": 0.5}, "provisional": True}), encoding="utf-8")

    report = evaluate(
        external,
        training,
        model,
        thresholds,
        tmp_path / "holdout.jsonl",
        tmp_path / "report.json",
        sample_size=4,
        seed=12,
    )

    assert report["human_label_counts"] == {0: 2, 1: 2}
    assert report["source_isolated_from_training"] is True
    assert "exact" in report["isolation_scope"]
    assert report["intent_exact_validation"] is False
    assert report["metrics"]["f1"] == 1.0


def test_balanced_sampler_rejects_odd_size():
    try:
        _sample_balanced([], sample_size=3, seed=1)
    except ValueError as exc:
        assert "positive even" in str(exc)
    else:
        raise AssertionError("odd sample size should be rejected")
