import unittest

from src.config import get_settings
from src.domain.enums import ResultLabel, RiskLevel, Severity
from src.domain.scoring import (
    HIGH_RISK_THRESHOLD,
    LOW_RISK_THRESHOLD,
    fuse_scores,
    label_for_probability,
    risk_level_for_score,
)
from src.domain.schemas import (
    AttachmentMeta,
    DetectionResult,
    Explanation,
    Mailbox,
    ParsedEmail,
    ParsedUrl,
    to_jsonable,
    validate_detection_result,
)


class DomainContractTests(unittest.TestCase):
    def test_risk_thresholds_are_frozen(self) -> None:
        self.assertEqual(risk_level_for_score(LOW_RISK_THRESHOLD - 0.1), RiskLevel.LOW)
        self.assertEqual(risk_level_for_score(LOW_RISK_THRESHOLD), RiskLevel.MEDIUM)
        self.assertEqual(
            risk_level_for_score(HIGH_RISK_THRESHOLD - 0.1),
            RiskLevel.MEDIUM,
        )
        self.assertEqual(risk_level_for_score(HIGH_RISK_THRESHOLD), RiskLevel.HIGH)

    def test_score_fusion_clamps_invalid_values(self) -> None:
        self.assertEqual(fuse_scores(-1.0, -50.0), 0.0)
        self.assertEqual(fuse_scores(2.0, 150.0), 100.0)

    def test_model_label_uses_probability_threshold(self) -> None:
        self.assertEqual(label_for_probability(0.49), ResultLabel.LEGITIMATE)
        self.assertEqual(label_for_probability(0.50), ResultLabel.PHISHING)

    def test_detection_result_is_json_serializable(self) -> None:
        url = ParsedUrl(
            raw_url="http://example.invalid/login",
            normalized_url="http://example.invalid/login",
            host="example.invalid",
            registrable_domain="example.invalid",
        )
        attachment = AttachmentMeta(
            filename="notice.pdf.exe",
            mime_type="application/octet-stream",
            size=120,
            sha256="a" * 64,
            extension=".exe",
        )
        email = ParsedEmail(
            subject="Account notice",
            sender=Mailbox(address="sender@example.invalid"),
            urls=[url],
            attachments=[attachment],
        )
        result = DetectionResult(
            result_label=ResultLabel.PHISHING,
            risk_level=RiskLevel.HIGH,
            model_probability=0.91,
            rule_score=75.0,
            final_score=85.4,
            model_version="v1.0.0",
            explanations=[
                Explanation(
                    code="R05",
                    title="Link mismatch",
                    detail="Displayed and destination domains differ.",
                    severity=Severity.CRITICAL,
                )
            ],
            urls=email.urls,
            attachments=email.attachments,
        )

        validate_detection_result(result)
        payload = to_jsonable(result)

        self.assertEqual(payload["result_label"], "phishing")
        self.assertEqual(payload["risk_level"], "high")
        self.assertEqual(payload["urls"][0]["host"], "example.invalid")
        self.assertEqual(payload["attachments"][0]["extension"], ".exe")
        self.assertEqual(payload["explanations"][0]["severity"], "critical")

    def test_invalid_detection_score_is_rejected(self) -> None:
        result = DetectionResult(
            result_label=ResultLabel.LEGITIMATE,
            risk_level=RiskLevel.LOW,
            model_probability=0.2,
            rule_score=0.0,
            final_score=101.0,
            model_version="v1.0.0",
        )

        with self.assertRaises(ValueError):
            validate_detection_result(result)

    def test_network_is_disabled_by_default(self) -> None:
        self.assertFalse(get_settings().allow_network)


if __name__ == "__main__":
    unittest.main()

