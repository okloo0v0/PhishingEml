import json

from scripts.prepare_gpt_supplement import prepare


def test_gpt_supplement_is_balanced_and_marked_generated(tmp_path):
    source = tmp_path / "gpt.csv"
    source.write_text("content,label\n" + "A useful email body with enough content for filtering purposes " * 4 + ",0\n" + "A phishing email body with enough content for filtering purposes " * 4 + ",1\n", encoding="utf-8")
    result = prepare(source, tmp_path / "out.jsonl", tmp_path / "summary.json", limit=2)
    assert result["selected_records"] == 2
    rows = [json.loads(line) for line in (tmp_path / "out.jsonl").read_text(encoding="utf-8").splitlines()]
    assert {row["data_origin"] for row in rows} == {"llm_generated"}
