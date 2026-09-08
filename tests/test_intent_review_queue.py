import json

from scripts.build_intent_review_queue import build


def test_review_queue_is_pending_and_bounded(tmp_path):
    source = tmp_path / "intent.jsonl"
    rows = [
        {"id": "1", "source": "a", "label": "legitimate", "subject": "Notice", "text_body": "Hello", "intent_labels": []},
        {"id": "2", "source": "a", "label": "legitimate", "subject": "Urgent", "text_body": "Please reply", "intent_labels": ["reply_or_data_request"]},
    ]
    source.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    result = build(source, tmp_path / "queue.jsonl", tmp_path / "summary.json", limit=10)
    assert result["queue_count"] == 2
    queue = [json.loads(line) for line in (tmp_path / "queue.jsonl").read_text(encoding="utf-8").splitlines()]
    assert all(row["review_status"] == "pending" for row in queue)
