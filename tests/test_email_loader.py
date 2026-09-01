from pathlib import Path

from scripts.email_loader import iter_corpus_records, parse_email_bytes


def test_parse_plain_and_html_parts_without_attachment_payload():
    raw = (
        b"From: sender@example.invalid\n"
        b"Subject: Hello\n"
        b"MIME-Version: 1.0\n"
        b"Content-Type: multipart/mixed; boundary=abc\n\n"
        b"--abc\nContent-Type: text/html; charset=utf-8\n\n"
        b"<html><style>.x{}</style><script>alert(1)</script><p>Visible</p></html>\n"
        b"--abc\nContent-Type: application/octet-stream\n"
        b"Content-Disposition: attachment; filename=bad.exe\n\n"
        b"binary-payload\n--abc--\n"
    )
    parsed = parse_email_bytes(raw)
    assert parsed.subject == "Hello"
    assert parsed.text_body == "Visible"
    assert "binary-payload" not in parsed.text_body


def test_malformed_message_returns_warning_instead_of_raising():
    parsed = parse_email_bytes(b"not a valid message")
    assert parsed.subject == ""
    assert parsed.text_body == ""
    assert parsed.parse_warnings == ["missing_headers"]


def test_unknown_charset_uses_safe_utf8_fallback():
    raw = (
        b"From: sender@example.invalid\n"
        b"Subject: Encoding\n"
        b"Content-Type: text/plain; charset=charset=\n\n"
        b"Readable text"
    )
    parsed = parse_email_bytes(raw)
    assert parsed.text_body == "Readable text"
    assert "unknown_charset_fallback" in parsed.parse_warnings


def test_iter_corpus_records_uses_source_directory_labels(tmp_path: Path):
    raw_dir = tmp_path / "raw" / "nazario"
    raw_dir.mkdir(parents=True)
    (raw_dir / "demo.mbox").write_bytes(
        b"From sender@example.invalid Tue Jan  1 00:00:00 2020\n"
        b"Subject: Demo\nContent-Type: text/plain\n\nBody\n"
    )
    records = list(iter_corpus_records(tmp_path / "raw"))
    assert len(records) == 1
    assert records[0].label == "phishing"
    assert records[0].source_hash
