import unittest
from unittest.mock import patch

from src.config import get_settings
from src.domain.enums import (
    BlacklistMatchType,
    BlacklistSource,
    IndicatorType,
    ResultLabel,
    RiskLevel,
    Severity,
)
from src.domain.rule_contract import MAX_RULE_SCORE, RULE_CATALOG, RuleCode
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
    ModelPrediction,
    Pagination,
    to_jsonable,
    validate_detection_result,
    validate_model_prediction,
    validate_pagination,
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
            blacklist_match_type=BlacklistMatchType.EXACT_URL,
            blacklist_indicator_id=7,
            blacklist_source=BlacklistSource.MANUAL,
            blacklist_confidence=0.9,
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
        self.assertEqual(payload["urls"][0]["blacklist_match_type"], "exact_url")
        self.assertEqual(payload["urls"][0]["blacklist_source"], "manual")

        counts = {RiskLevel.LOW: 0, RiskLevel.HIGH: 1}
        self.assertEqual(to_jsonable(counts), {"low": 0, "high": 1})

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

    def test_network_enablement_is_rejected(self) -> None:
        with patch.dict("os.environ", {"ALLOW_NETWORK": "true"}):
            with self.assertRaisesRegex(ValueError, "not supported"):
                get_settings()

    def test_model_prediction_contract(self) -> None:
        prediction = ModelPrediction(
            result_label=ResultLabel.PHISHING,
            phishing_probability=0.5,
            model_version="v1.0.0",
            feature_version="text-v1",
        )
        validate_model_prediction(prediction)

        with self.assertRaises(ValueError):
            validate_model_prediction(
                ModelPrediction(
                    result_label=ResultLabel.LEGITIMATE,
                    phishing_probability=0.5,
                    model_version="v1.0.0",
                    feature_version="text-v1",
                )
            )
        with self.assertRaises(ValueError):
            validate_model_prediction(
                ModelPrediction(
                    result_label=ResultLabel.PHISHING,
                    phishing_probability=1.1,
                    model_version="v1.0.0",
                    feature_version="text-v1",
                )
            )

    def test_detection_result_rejects_contract_mismatches(self) -> None:
        base = dict(
            result_label=ResultLabel.PHISHING,
            risk_level=RiskLevel.HIGH,
            model_probability=0.8,
            rule_score=60.0,
            final_score=fuse_scores(0.8, 60.0),
            model_version="v1.0.0",
        )
        for field, value in (
            ("final_score", 1.0),
            ("risk_level", RiskLevel.LOW),
            ("result_label", ResultLabel.LEGITIMATE),
        ):
            candidate = DetectionResult(**{**base, field: value})
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    validate_detection_result(candidate)

        with self.assertRaises(ValueError):
            validate_detection_result(
                DetectionResult(**{**base, "model_probability": float("nan")})
            )

    def test_pagination_contract(self) -> None:
        validate_pagination(Pagination(page=1, page_size=10, total=0, total_pages=0))
        validate_pagination(Pagination(page=2, page_size=10, total=11, total_pages=2))
        for pagination in (
            Pagination(page=0, page_size=10, total=1, total_pages=1),
            Pagination(page=1, page_size=0, total=0, total_pages=0),
            Pagination(page=1, page_size=10, total=11, total_pages=1),
            Pagination(page=3, page_size=10, total=11, total_pages=2),
        ):
            with self.subTest(pagination=pagination):
                with self.assertRaises(ValueError):
                    validate_pagination(pagination)

    def test_rule_catalog_is_stable(self) -> None:
        self.assertEqual(len(RULE_CATALOG), 10)
        self.assertEqual(RULE_CATALOG[RuleCode.BLACKLIST_HIT].default_score, 40.0)
        self.assertTrue(all(spec.max_hits_per_email >= 1 for spec in RULE_CATALOG.values()))
        self.assertEqual(MAX_RULE_SCORE, 100.0)
        self.assertEqual(IndicatorType.URL.value, "url")


if __name__ == "__main__":
    unittest.main()

