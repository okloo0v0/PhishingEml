import json

from scripts.prepare_clean_dataset import prepare


def test_prepare_clean_dataset_preserves_raw_fields_for_v1_1(tmp_path):
    source = tmp_path / "raw.jsonl"
    output = tmp_path / "cleaned.jsonl"
    stats = tmp_path / "stats.json"
    source.write_text(
        json.dumps(
            {
                "id": "fixture-1",
                "source": "fixture",
                "label": "phishing",
                "subject": "Raw https://example.invalid/login",
                "text_body": "Contact analyst@example.invalid now",
                "source_hash": "hash",
                "parse_warnings": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    prepare(source, output, stats)
    record = json.loads(output.read_text(encoding="utf-8").splitlines()[0])

    assert record["raw_subject"] == "Raw https://example.invalid/login"
    assert record["raw_text_body"] == "Contact analyst@example.invalid now"
    assert record["subject"] != record["raw_subject"]
    assert record["text_body"] != record["raw_text_body"]
