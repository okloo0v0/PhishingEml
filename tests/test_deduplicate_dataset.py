from scripts.deduplicate_dataset import content_fingerprint, deduplicate


def _record(record_id: str, source_hash: str, text: str, label: str, warnings=None):
    return {
        "id": record_id,
        "source_hash": source_hash,
        "model_text": text,
        "label": label,
        "source": "fixture",
        "original_chars": len(text),
        "parse_warnings": warnings or [],
    }


def test_deduplicate_removes_raw_and_canonical_text_duplicates_deterministically():
    records = [
        _record("b", "same-raw", "one", "phishing", ["warning"]),
        _record("a", "same-raw", "one", "phishing"),
        _record("c", "other-raw", "one", "phishing"),
        _record("d", "last-raw", "two", "legitimate"),
    ]
    retained, report = deduplicate(records)
    assert [record["id"] for record in retained] == ["a", "d"]
    assert retained[0]["content_fingerprint"] == content_fingerprint("one")
    assert retained[0]["dedup_group"] == content_fingerprint("one")
    assert report["raw_hash_removed"] == 1
    assert report["content_duplicate_removed"] == 1
    assert report["near_duplicate_candidate_pairs"] >= 0


def test_deduplicate_drops_conflicting_labels_for_identical_model_text():
    records = [
        _record("p", "raw-p", "same text", "phishing"),
        _record("l", "raw-l", "same text", "legitimate"),
    ]
    retained, report = deduplicate(records)
    assert retained == []
    assert report["label_conflict_groups_dropped"] == 1
    assert report["label_conflict_records_dropped"] == 2
