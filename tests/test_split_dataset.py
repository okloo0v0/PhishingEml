from scripts.split_dataset import _group_split, _select_cross_source


def _record(record_id: str, group: str, source: str, label: str):
    return {"id": record_id, "dedup_group": group, "source": source, "label": label, "model_text": "text"}


def test_group_split_is_deterministic_and_disjoint():
    records = [
        _record(f"p{i}", f"gp{i}", "phish", "phishing") for i in range(20)
    ] + [
        _record(f"l{i}", f"gl{i}", "ham", "legitimate") for i in range(20)
    ]
    first = _group_split(records)
    second = _group_split(records)
    assert {key: [item["id"] for item in value] for key, value in first.items()} == {
        key: [item["id"] for item in value] for key, value in second.items()
    }
    groups = [set(item["dedup_group"] for item in first[name]) for name in ("train", "valid", "test")]
    assert groups[0].isdisjoint(groups[1])
    assert groups[0].isdisjoint(groups[2])
    assert groups[1].isdisjoint(groups[2])


def test_cross_source_holdout_is_deterministic_and_balanced():
    records = [
        _record(f"a{i}", f"ga{i}", "source-a", "phishing") for i in range(20)
    ] + [
        _record(f"b{i}", f"gb{i}", "source-b", "legitimate") for i in range(20)
    ]
    held_out, remaining = _select_cross_source(records, 0.1)
    assert len(held_out) == 4
    assert len(remaining) == 36
    assert {item["source"] for item in held_out} == {"source-a", "source-b"}
