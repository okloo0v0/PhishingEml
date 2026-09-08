from scripts.audit_v1_2_data_layout import audit
from scripts.audit_v1_2_sources import audit as audit_sources


def test_v1_2_archive_and_source_catalog_are_auditable():
    result = audit()
    assert result["source_rows"] >= 4
    assert result["archive_rows"] >= 3
    assert result["planned_sources"] < result["source_rows"]
    assert result["verified_sources"] == 0


def test_downloaded_v1_2_sources_have_offline_audit_manifest():
    records = audit_sources()
    csv_records = [row for row in records if row["file_type"] == "csv"]
    assert len(csv_records) == 2
    assert sum(int(row["row_count"]) for row in csv_records) == 6776
    assert any(row["data_origin"] == "llm_generated" for row in csv_records)
    assert all(row["sha256"] for row in records)
