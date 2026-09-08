import json
import unittest
from pathlib import Path

from src.detection.rules import evaluate_rules
from src.domain.schemas import to_jsonable
from src.parsers.email_parser import parse_email


CASE_ROOT = Path(__file__).parent / "member2_cases"
SAMPLE_DIR = CASE_ROOT / "samples"
EXPECTED_DIR = CASE_ROOT / "expected"
ACTUAL_DIR = CASE_ROOT / "actual_outputs"


class Member2SampleCaseTests(unittest.TestCase):
    def test_sample_cases_match_expected_outputs(self) -> None:
        ACTUAL_DIR.mkdir(parents=True, exist_ok=True)

        sample_paths = sorted(SAMPLE_DIR.glob("*.eml"))
        self.assertGreaterEqual(len(sample_paths), 5)

        for sample_path in sample_paths:
            with self.subTest(sample=sample_path.name):
                case_name = sample_path.stem
                expected_path = EXPECTED_DIR / f"{case_name}.json"
                self.assertTrue(expected_path.exists(), f"missing {expected_path}")

                parsed_email = parse_email(sample_path.read_bytes())
                rule_result = evaluate_rules(parsed_email)
                actual = {
                    "sample": sample_path.name,
                    "summary": _summary(parsed_email, rule_result),
                    "parsed_email": to_jsonable(parsed_email),
                    "rule_evaluation": to_jsonable(rule_result),
                }
                (ACTUAL_DIR / f"{case_name}.actual.json").write_text(
                    json.dumps(actual, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

                expected = json.loads(expected_path.read_text(encoding="utf-8"))
                _assert_expected_subset(self, actual["summary"], expected)


def _summary(parsed_email, rule_result) -> dict:
    return {
        "subject": parsed_email.subject,
        "sender_domain": parsed_email.sender.domain,
        "reply_to_domain": parsed_email.reply_to.domain if parsed_email.reply_to else None,
        "url_count": len(parsed_email.urls),
        "attachment_count": len(parsed_email.attachments),
        "parse_warnings": parsed_email.parse_warnings,
        "rule_codes": [item.code for item in rule_result.explanations],
        "rule_score": rule_result.rule_score,
        "urls": [
            {
                "raw_url": url.raw_url,
                "normalized_url": url.normalized_url,
                "display_text": url.display_text,
                "scheme": url.scheme,
                "host": url.host,
                "registrable_domain": url.registrable_domain,
                "port": url.port,
                "path": url.path,
                "query": url.query,
                "is_https": url.is_https,
                "uses_ip": url.uses_ip,
                "is_shortener": url.is_shortener,
                "suspicious_tokens": url.suspicious_tokens,
            }
            for url in parsed_email.urls
        ],
        "attachments": [
            {
                "filename": attachment.filename,
                "mime_type": attachment.mime_type,
                "size": attachment.size,
                "sha256": attachment.sha256,
                "extension": attachment.extension,
                "risk_hints": attachment.risk_hints,
            }
            for attachment in parsed_email.attachments
        ],
    }


def _assert_expected_subset(testcase: unittest.TestCase, summary: dict, expected: dict) -> None:
    for key in (
        "subject",
        "sender_domain",
        "reply_to_domain",
        "url_count",
        "attachment_count",
    ):
        testcase.assertEqual(summary[key], expected[key], key)

    for warning in expected.get("parse_warnings_contains", []):
        testcase.assertIn(warning, summary["parse_warnings"])

    testcase.assertEqual(summary["rule_codes"], expected["rule_codes"])

    testcase.assertEqual(len(summary["urls"]), len(expected["urls"]))
    for actual_url, expected_url in zip(summary["urls"], expected["urls"], strict=True):
        for key, value in expected_url.items():
            if key == "suspicious_tokens_contains":
                for token in value:
                    testcase.assertIn(token, actual_url["suspicious_tokens"])
            else:
                testcase.assertEqual(actual_url[key], value, key)

    testcase.assertEqual(len(summary["attachments"]), len(expected["attachments"]))
    for actual_attachment, expected_attachment in zip(
        summary["attachments"],
        expected["attachments"],
        strict=True,
    ):
        for key, value in expected_attachment.items():
            if key == "risk_hints_contains":
                for hint in value:
                    testcase.assertIn(hint, actual_attachment["risk_hints"])
            else:
                testcase.assertEqual(actual_attachment[key], value, key)


if __name__ == "__main__":
    unittest.main()
