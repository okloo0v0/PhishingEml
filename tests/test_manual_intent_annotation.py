import json

from scripts.annotate_difraud_intents import MANUAL_LABELS, annotate


def test_manual_annotation_covers_fixed_external_sample(tmp_path):
    source = tmp_path / "source.jsonl"
    source.write_text("".join(json.dumps({"id": str(i), "text_body": "x"}) + "\n" for i in range(100)), encoding="utf-8")
    result = annotate(source, tmp_path / "labeled.jsonl", tmp_path / "train.jsonl", tmp_path / "test.jsonl")
    assert result["labeled_count"] == 100
    assert result["train_count"] == 70
    assert result["test_count"] == 30
    assert result["intent_counts"]["credential_request"] == 32
    assert len(MANUAL_LABELS) == 100
