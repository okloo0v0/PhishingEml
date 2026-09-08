from src.detection.multiview_features import (
    FEATURE_VERSION,
    INTENT_FEATURE_NAMES,
    STRUCTURE_FEATURE_NAMES,
    build_multiview_record,
    records_from_rows,
    select_intent_matrix,
    select_structure_matrix,
)
from src.parsers.email_parser import parse_email


def test_multiview_features_keep_text_views_and_extract_static_signals():
    parsed = parse_email(
        b"From: Finance <finance@example.invalid>\r\n"
        b"Reply-To: agent@outside.invalid\r\n"
        b"To: user@example.invalid\r\n"
        b"Subject: Urgent payment\r\n"
        b"Content-Type: text/html; charset=utf-8\r\n\r\n"
        b"<p>Immediately confirm the bank account.</p>"
        b"<a href='http://192.0.2.10/login'>example.invalid</a>"
    )

    record = build_multiview_record(parsed.subject, parsed.text_body, parsed)

    assert FEATURE_VERSION == "text-structure-v2"
    assert "<URL>" not in record["char_text"]
    assert record["structure"]["url_count"] == 1.0
    assert record["structure"]["ip_url_count"] == 1.0
    assert record["structure"]["sender_reply_domain_mismatch"] == 1.0
    assert record["structure"]["html_link_count"] == 1.0
    assert record["intent"]["payment_present"] == 1.0
    assert record["intent"]["urgency_action_pair"] == 1.0


def test_multiview_numeric_selectors_have_frozen_column_order():
    record = build_multiview_record("Meeting", "Normal project update")

    structure = select_structure_matrix([record])
    intent = select_intent_matrix([record])

    assert structure.shape == (1, len(STRUCTURE_FEATURE_NAMES))
    assert intent.shape == (1, len(INTENT_FEATURE_NAMES))
    assert structure.dtype.name == "float64"


def test_dataset_rows_prefer_raw_fields_for_v1_1_views():
    record = records_from_rows(
        [
            {
                "raw_subject": "Raw account URL",
                "raw_text_body": "Visit https://example.invalid/login",
                "subject": "Clean account URL",
                "text_body": "Visit <URL>",
            }
        ]
    )[0]

    assert "https://example.invalid/login" in record["char_text"]
    assert record["structure"]["url_count"] == 1.0
