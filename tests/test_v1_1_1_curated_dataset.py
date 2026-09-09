import json

from scripts.build_v1_1_1_curated_dataset import build, build_collections
from src.detection.multiview_features import records_from_rows


def test_curated_v1_1_1_partitions_are_balanced_disjoint_and_feature_ready(tmp_path):
    collections = build_collections()

    assert {name: len(rows) for name, rows in collections.items()} == {
        "train": 168,
        "chinese_test": 80,
        "modern_attack_test": 84,
        "boundary_test": 112,
    }
    fingerprints = {
        name: {row["content_fingerprint"] for row in rows}
        for name, rows in collections.items()
    }
    assert not any(
        fingerprints[left].intersection(fingerprints[right])
        for index, left in enumerate(fingerprints)
        for right in list(fingerprints)[index + 1 :]
    )
    assert all("v1_1_parsed_email" in row for row in collections["train"])

    record = records_from_rows([collections["train"][0]])[0]
    assert record["structure"]["header_count"] > 0.0
    assert record["structure"]["sender_present"] == 1.0

    summary = build(
        tmp_path / "train.jsonl",
        tmp_path / "chinese.jsonl",
        tmp_path / "modern.jsonl",
        tmp_path / "boundary.jsonl",
        tmp_path / "summary.json",
    )
    assert summary["partitions"]["chinese_test"]["languages"] == {"zh": 80}
    assert json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))["hard_negative_policy"].startswith("unchanged")
