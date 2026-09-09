from src.detection.deepseek_client import (
    _comparison_payload,
    _email_evidence_payload,
    _validate_assessment,
    _validate_comparison,
)
from src.detection.rule_engine import RuleEngine
from src.domain.enums import ResultLabel
from src.domain.schemas import Explanation, ModelPrediction
from src.parsers.email_parser import parse_email


class _BlacklistRepo:
    def __init__(self):
        self.items = {}

    def active_sets(self):
        return ({value for kind, value in self.items if kind == "url"}, set())

    def active_metadata(self):
        return {}

    def create_if_missing(self, indicator, indicator_type, source, confidence, note):
        self.items[(indicator_type, indicator)] = {
            "source": source, "confidence": confidence, "note": note
        }


class _DetectionRepo:
    def save_analysis(self, parsed, result, filename, file_hash):
        return 1


class _Predictor:
    def predict(self, model_input):
        return ModelPrediction(
            result_label=ResultLabel.LEGITIMATE,
            phishing_probability=0.1,
            model_version="test",
            feature_version="text-v1",
        )


def test_visual_confusion_is_a_separate_rule_and_auto_blacklist_signal():
    parsed = parse_email(
        b"From: notice@example.invalid\r\n"
        b"Subject: account\r\n\r\n"
        b"Open https://g00gle.com/login\r\n"
    )
    assert "lookalike_characters" in parsed.urls[0].suspicious_tokens

    repo = _BlacklistRepo()
    from src.services.analysis_service import AnalysisService

    result = AnalysisService(
        parsed_parser := type("Parser", (), {"parse": lambda self, content: parsed})(),
        RuleEngine(),
        _Predictor(),
        repo,
        _DetectionRepo(),
    ).analyze(b"raw", "mail.eml")

    assert "R06" in {item.code for item in result.explanations}
    assert ("url", "https://g00gle.com/login") in repo.items


def test_llm_assessment_validation_keeps_a_small_json_contract():
    result = _validate_assessment({
        "verdict": "phishing",
        "confidence": 0.91,
        "summary": " suspicious   message ",
        "key_findings": ["link mismatch"],
        "recommendations": ["do not click"],
        "uncertainty": "manual review",
        "ignored": "not returned",
    })
    assert result.verdict == "phishing"
    assert result.confidence == 0.91
    assert result.summary == "suspicious message"
    assert result.key_findings == ["link mismatch"]


def test_independent_llm_payload_excludes_local_detection_results():
    email = parse_email(
        b"From: notice@example.invalid\r\n"
        b"Subject: Verify account\r\n\r\n"
        b"Open https://g00gle.com/login"
    )

    payload = _email_evidence_payload(email)

    assert set(payload) == {"email_evidence"}
    assert "rule_score" not in str(payload)
    assert "model_phishing_probability" not in str(payload)
    assert "final_score" not in str(payload)
    assert "risk_level" not in str(payload)


def test_llm_comparison_payload_contains_local_results_only_after_independent_verdict():
    independent = _validate_assessment({
        "verdict": "suspicious",
        "confidence": 0.72,
        "summary": "独立判断发现身份核验请求。",
        "key_findings": ["正文要求提交账号信息"],
        "uncertainty": "未访问链接。",
    })
    payload = _comparison_payload(
        independent,
        70.0,
        [Explanation(code="R05", title="敏感信息请求", detail="", evidence="password")],
        0.91,
        83.2,
        "high",
        "phishing",
        "v1.2",
    )
    comparison = _validate_comparison({
        "local_alignment": "partial",
        "local_comparison": "独立判断支持风险，但对链接性质保持保留。",
        "recommendations": ["不要提交密码"],
    })

    assert payload["independent_assessment"]["verdict"] == "suspicious"
    assert payload["local_detection"]["final_score"] == 83.2
    assert payload["local_detection"]["result_label"] == "phishing"
    assert comparison["local_alignment"] == "partial"
