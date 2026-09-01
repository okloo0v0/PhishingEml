from src.detection.text_features import (
    FEATURE_VERSION,
    MODEL_TEXT_MAX_CHARS,
    clean_email_text,
)


def test_clean_email_text_replaces_sensitive_tokens_and_keeps_contract():
    cleaned = clean_email_text(
        "Urgent alice@example.com",
        "Visit https://example.invalid/login?id=123456 and call 123456789.",
    )
    assert cleaned.feature_version == FEATURE_VERSION == "text-v1"
    assert "alice@example.com" not in cleaned.model_text
    assert "https://example.invalid" not in cleaned.model_text
    assert "<EMAIL>" in cleaned.model_text
    assert "<URL>" in cleaned.model_text
    assert "<NUMBER>" in cleaned.model_text
    assert cleaned.url_replacements == 1
    assert cleaned.email_replacements == 1


def test_clean_email_text_replaces_address_before_sentence_punctuation():
    cleaned = clean_email_text("", "Contact info@example.invalid.")
    assert cleaned.text_body == "Contact <EMAIL>."
    assert cleaned.email_replacements == 1


def test_clean_email_text_truncates_after_cleaning():
    cleaned = clean_email_text("Subject", "x" * (MODEL_TEXT_MAX_CHARS + 100))
    assert len(cleaned.model_text) == MODEL_TEXT_MAX_CHARS
    assert cleaned.truncated is True
    assert "model_text_truncated" in cleaned.warnings


def test_clean_email_text_handles_empty_fields():
    cleaned = clean_email_text("", "  \r\n  ")
    assert cleaned.model_text == "\n"
    assert set(cleaned.warnings) == {"empty_subject", "empty_text_body"}
