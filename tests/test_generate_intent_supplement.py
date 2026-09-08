import json

from scripts.generate_intent_supplement import generate


def test_synthetic_intent_supplement_is_explicitly_marked(tmp_path):
    output = tmp_path / "supplement.jsonl"
    summary = generate(output, per_intent=3)
    assert summary["record_count"] == 15
    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert all(row["data_origin"] == "synthetic_template" for row in rows)
    assert all(row["intent_label_provenance"] == "synthetic_template_v1" for row in rows)
