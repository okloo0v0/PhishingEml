import json

from scripts.prepare_v1_2_intent_dataset import prepare
from scripts.train_intent_branch import train


def test_v1_2_intent_prepare_and_train(tmp_path):
    source = tmp_path / "emails.csv"
    source.write_text(
        "id,source,label,subject,text_body\n"
        "1,a,legitimate,Notice,No action is required\n"
        "2,a,phishing,Verify,Reply with your password\n"
        "3,b,legitimate,Invoice,Payment completed\n"
        "4,b,phishing,Approve,Authorize using device code\n"
        "5,c,legitimate,Update,Your document is ready\n"
        "6,c,phishing,Transfer,Change bank account for payment\n",
        encoding="utf-8",
    )
    dataset = tmp_path / "intent.jsonl"
    prep_summary = tmp_path / "prep.json"
    result = prepare(source, dataset, prep_summary, limit=6)
    assert result["record_count"] == 6
    model_summary = train(dataset, tmp_path / "model.joblib", tmp_path / "train.json")
    assert model_summary["train_count"] == 4
    assert "credential_request" in model_summary["metrics"]
