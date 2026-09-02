from pathlib import Path

from scripts.prepare_supplemental_dataset import SPECS, _source_hash


def test_supplemental_label_mappings_are_explicit():
    assert SPECS["Nigerian_5.csv"]["mapping"] == {"0": "legitimate", "1": "phishing"}
    assert SPECS["SpamAssasin.csv"]["mapping"] == {"0": "legitimate", "1": "spam_other"}
    assert SPECS["Nigerian_Fraud.csv"]["mapping"] == {"1": "phishing"}
    assert SPECS["Nazario.csv"]["mapping"] == {"1": "phishing"}


def test_supplemental_source_hash_is_stable_and_content_based():
    row = {
        "sender": "a@example.invalid",
        "receiver": "b@example.invalid",
        "date": "2026-01-01",
        "subject": "Subject",
        "body": "Body",
        "label": "1",
    }
    assert _source_hash(row) == _source_hash(dict(row))
    changed = {**row, "body": "Changed"}
    assert _source_hash(row) != _source_hash(changed)
