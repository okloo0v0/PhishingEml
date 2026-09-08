from scripts.audit_v1_2_data_layout import audit


def test_v1_2_archive_and_source_catalog_are_auditable():
    result = audit()
    assert result["source_rows"] >= 4
    assert result["archive_rows"] >= 3
    assert result["planned_sources"] == result["source_rows"]
    assert result["verified_sources"] == 0
