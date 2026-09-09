import json

from scripts.evaluate_intent_branch import evaluate


def test_intent_evaluation_excludes_synthetic_rows_from_test(tmp_path):
    base = tmp_path / "base.jsonl"
    supplement = tmp_path / "supplement.jsonl"
    base_rows = []
    for index in range(20):
        intent = "credential_request" if index % 2 else "benign_notice"
        base_rows.append({"subject": "Verify" if index % 2 else "Notice", "text_body": "Reply with password" if index % 2 else "No action is required", "intent_labels": [intent]})
    base.write_text("\n".join(json.dumps(row) for row in base_rows) + "\n", encoding="utf-8")
    supplement.write_text(json.dumps({"subject": "Synthetic", "text_body": "Approve device code", "intent_labels": ["oauth_authorization"], "data_origin": "synthetic_template"}) + "\n", encoding="utf-8")
    result = evaluate(base, supplement, tmp_path / "summary.json")
    assert result["test_contains_synthetic"] is False
    assert result["train_supplement_count"] == 1
    assert result["test_base_count"] == 4
