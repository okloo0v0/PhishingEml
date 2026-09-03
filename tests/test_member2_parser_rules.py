import unittest

from src.detection.rules import evaluate_rules
from src.domain.rule_contract import RuleCode
from src.parsers.email_parser import parse_email
from src.parsers.url_parser import extract_urls_from_html, normalize_url


class Member2ParserRuleTests(unittest.TestCase):
    def test_url_normalization_is_static_and_extracts_features(self) -> None:
        parsed = normalize_url("Example.Invalid:8080/login?next=%2Fsecure")

        self.assertEqual(parsed.normalized_url, "http://example.invalid:8080/login?next=%2Fsecure")
        self.assertEqual(parsed.scheme, "http")
        self.assertEqual(parsed.host, "example.invalid")
        self.assertEqual(parsed.registrable_domain, "example.invalid")
        self.assertEqual(parsed.port, 8080)
        self.assertFalse(parsed.is_https)
        self.assertIn("missing_scheme", parsed.suspicious_tokens)
        self.assertIn("encoded_chars", parsed.suspicious_tokens)

    def test_html_links_keep_display_text_for_mismatch_rule(self) -> None:
        urls = extract_urls_from_html(
            '<a href="https://evil.example/login">https://bank.example/secure</a>'
        )

        self.assertEqual(len(urls), 1)
        self.assertEqual(urls[0].display_text, "https://bank.example/secure")
        self.assertEqual(urls[0].host, "evil.example")

    def test_email_parser_extracts_bodies_urls_headers_and_attachment_metadata(self) -> None:
        raw = (
            "From: Support <support@example.invalid>\n"
            "Reply-To: Help <help@other.invalid>\n"
            "To: user@example.invalid\n"
            "Subject: Verify now\n"
            "Message-ID: <demo-1@example.invalid>\n"
            "Date: Tue, 1 Sep 2026 10:00:00 +0000\n"
            "MIME-Version: 1.0\n"
            "Content-Type: multipart/mixed; boundary=outer\n"
            "\n"
            "--outer\n"
            "Content-Type: text/html; charset=utf-8\n"
            "\n"
            '<p>Urgent login required <a href="http://192.0.2.1/login">portal</a></p>\n'
            "--outer\n"
            "Content-Type: application/octet-stream\n"
            "Content-Disposition: attachment; filename=\"notice.pdf.exe\"\n"
            "\n"
            "fake-binary\n"
            "--outer--\n"
        )

        parsed = parse_email(raw)

        self.assertEqual(parsed.sender.domain, "example.invalid")
        self.assertEqual(parsed.reply_to.domain, "other.invalid")
        self.assertIn("urgent login required", parsed.text_body.lower())
        self.assertEqual(parsed.urls[0].host, "192.0.2.1")
        self.assertTrue(parsed.urls[0].uses_ip)
        self.assertEqual(parsed.attachments[0].extension, ".exe")
        self.assertIn("double_extension", parsed.attachments[0].risk_hints)
        self.assertIn("from", parsed.headers)

    def test_rule_engine_hits_each_rule_once_and_scores_from_contract(self) -> None:
        parsed = parse_email(
            "From: Support <support@example.invalid>\n"
            "Reply-To: Help <help@other.invalid>\n"
            "Subject: Microsoft urgent password verify\n"
            "Content-Type: text/html; charset=utf-8\n"
            "\n"
            '<a href="http://192.0.2.1/login">https://microsoft.example/login</a>'
        )
        parsed.urls[0].blacklist_hit = True

        result = evaluate_rules(parsed)
        codes = [item.code for item in result.explanations]

        self.assertIn(RuleCode.SENDER_REPLY_TO_MISMATCH, codes)
        self.assertIn(RuleCode.DISPLAY_LINK_MISMATCH, codes)
        self.assertIn(RuleCode.BLACKLIST_HIT, codes)
        self.assertIn(RuleCode.URGENT_LANGUAGE, codes)
        self.assertIn(RuleCode.CREDENTIAL_REQUEST, codes)
        self.assertIn(RuleCode.SUSPICIOUS_URL, codes)
        self.assertIn(RuleCode.BRAND_IMPERSONATION, codes)
        self.assertEqual(len(codes), len(set(codes)))
        self.assertLessEqual(result.rule_score, 100.0)


if __name__ == "__main__":
    unittest.main()
