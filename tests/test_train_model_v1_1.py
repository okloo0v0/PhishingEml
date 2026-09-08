import csv
import json

from scripts.train_model_v1_1 import hard_negative_split, train


def _write_rows(path):
    fields = ["id", "source", "label", "subject", "text_body", "model_text", "split"]
    rows = []
    for split in ("train", "valid", "test"):
        rows.extend(
            [
                [f"p-{split}-1", "fixture", "phishing", "Urgent password", "Verify account now", "", split],
                [f"p-{split}-2", "fixture", "phishing", "Wire transfer", "Confidential payment", "", split],
                [f"l-{split}-1", "fixture", "legitimate", "Team meeting", "Project update", "", split],
                [f"l-{split}-2", "fixture", "legitimate", "Course notes", "Lecture schedule", "", split],
            ]
        )
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.writer(output)
        writer.writerow(fields)
        writer.writerows(rows)


def _write_hard_rows(path):
    with path.open("w", encoding="utf-8") as output:
        for index in range(30):
            output.write(
                json.dumps(
                    {
                        "id": f"spam-{index}",
                        "source": "fixture-spam",
                        "label": "spam_other",
                        "subject": "Special offer",
                        "text_body": f"Newsletter promotion number {index}",
                        "dedup_group": f"group-{index}",
                    }
                )
                + "\n"
            )


def test_hard_negative_split_is_stable():
    row = {"id": "same", "source": "fixture", "dedup_group": "group"}
    assert hard_negative_split(row) == hard_negative_split(dict(row))
    assert hard_negative_split(row) in {"train", "valid", "test"}


def test_train_v1_1_writes_versioned_artifact_and_preserves_hard_test(tmp_path):
    input_path = tmp_path / "emails.csv"
    hard_path = tmp_path / "hard.jsonl"
    _write_rows(input_path)
    _write_hard_rows(hard_path)
    model_path = tmp_path / "model.joblib"

    summary = train(
        input_path,
        hard_path,
        model_path,
        tmp_path / "summary.json",
        tmp_path / "predictions.csv",
        tmp_path / "log.json",
        word_max_features=200,
        char_max_features=300,
        min_df=1,
        cv_splits=2,
    )

    assert model_path.exists()
    assert summary["model_version"] == "v1.1.0"
    assert summary["feature_version"] == "text-structure-v2"
    assert summary["hard_negative_counts"]["train"] > 0
    assert summary["hard_negative_counts"]["test"] > 0
    assert summary["artifact_sha256"]
