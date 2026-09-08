import csv
import json

import numpy as np

from scripts.evaluate_model_v1_1 import evaluate, metrics, paired_pr_auc_bootstrap
from scripts.train_model_v1_1 import train


def _write_binary_rows(path):
    fields = ["id", "source", "label", "subject", "text_body", "model_text", "split"]
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for split in ("train", "valid", "test"):
            for index, (label, subject, body) in enumerate(
                [
                    ("phishing", "Urgent password", "Verify account immediately"),
                    ("phishing", "Payment change", "Confidential wire transfer"),
                    ("legitimate", "Team meeting", "Weekly project agenda"),
                    ("legitimate", "Course update", "Lecture schedule"),
                ]
            ):
                writer.writerow(
                    {
                        "id": f"{split}-{index}",
                        "source": "fixture",
                        "label": label,
                        "subject": subject,
                        "text_body": body,
                        "model_text": f"{subject}\n{body}",
                        "split": split,
                    }
                )


def _write_jsonl(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_v1_1_metrics_include_calibration_and_false_positive_rate():
    result = metrics(
        ["legitimate", "legitimate", "phishing", "phishing"],
        np.asarray([0.1, 0.8, 0.6, 0.9]),
        0.5,
    )

    assert result["false_positive_rate"] == 0.5
    assert result["pr_auc"] is not None
    assert 0.0 <= result["brier_score"] <= 1.0
    assert 0.0 <= result["expected_calibration_error"] <= 1.0


def test_paired_pr_auc_bootstrap_reports_candidate_difference():
    labels = ["legitimate", "legitimate", "phishing", "phishing"]
    baseline = np.asarray([0.4, 0.3, 0.6, 0.7])
    candidate = np.asarray([0.1, 0.2, 0.8, 0.9])

    result = paired_pr_auc_bootstrap(labels, candidate, baseline, iterations=20)

    assert result["iterations"] == 20
    assert result["ci95_lower"] <= result["mean_difference"] <= result["ci95_upper"]


def test_evaluate_v1_1_keeps_reserved_hard_negative_test(tmp_path):
    input_path = tmp_path / "emails.csv"
    hard_path = tmp_path / "hard.jsonl"
    cross_path = tmp_path / "cross.jsonl"
    model_path = tmp_path / "model.joblib"
    _write_binary_rows(input_path)
    hard_rows = [
        {
            "id": f"spam-{index}",
            "source": "fixture-spam",
            "label": "spam_other",
            "subject": "Special offer",
            "text_body": f"Newsletter promotion {index}",
            "model_text": f"Special offer\nNewsletter promotion {index}",
            "dedup_group": f"spam-group-{index}",
        }
        for index in range(40)
    ]
    _write_jsonl(hard_path, hard_rows)
    _write_jsonl(
        cross_path,
        [
            {
                "id": "cross-p",
                "source": "cross",
                "label": "phishing",
                "subject": "Account warning",
                "text_body": "Verify password now",
                "model_text": "Account warning\nVerify password now",
            },
            {
                "id": "cross-l",
                "source": "cross",
                "label": "legitimate",
                "subject": "Project update",
                "text_body": "Meeting agenda",
                "model_text": "Project update\nMeeting agenda",
            },
        ],
    )
    train(
        input_path,
        hard_path,
        model_path,
        tmp_path / "train-summary.json",
        tmp_path / "train-predictions.csv",
        tmp_path / "train-log.json",
        word_max_features=200,
        char_max_features=300,
        min_df=1,
        cv_splits=2,
    )

    result = evaluate(
        input_path,
        model_path,
        cross_path,
        hard_path,
        tmp_path / "evaluation.json",
        tmp_path / "evaluation.csv",
        tmp_path / "errors.csv",
        baseline_model_path=None,
    )

    assert result["test"]["contract_metrics"]["support"] == 4
    assert result["hard_negative"]["contract_metrics"]["support"] > 0
    assert set(result["branch_metrics"]["test"]) == {"word", "char", "structure", "intent"}
    assert result["latency"]["p95_ms"] >= 0.0
