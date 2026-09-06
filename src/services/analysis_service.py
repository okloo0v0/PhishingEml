"""Analysis orchestration: parse -> rules -> model -> fuse -> validate -> save."""

from __future__ import annotations

import hashlib

from src.db.models import iso_z, utcnow
from src.db.repositories import BlacklistRepository, DetectionRepository
from src.domain.enums import RiskLevel
from src.domain.scoring import fuse_scores, risk_level_for_score
from src.domain.schemas import DetectionResult, ModelInput, validate_detection_result


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _advice_for(risk_level: RiskLevel) -> list[str]:
    base = [
        "不要点击邮件中的链接或下载附件",
        "通过官方渠道核实发件人身份",
    ]
    if risk_level is RiskLevel.HIGH:
        return [
            "该邮件疑似钓鱼，请勿点击链接、回复敏感信息或下载附件",
            "如涉及账号，请通过官方网站修改密码并上报",
        ]
    if risk_level is RiskLevel.MEDIUM:
        return [
            "邮件存在可疑特征，请通过官方渠道核实后再操作",
            "不要向邮件中出现的地址提供账号、密码或验证码",
        ]
    return base


class AnalysisService:
    def __init__(
        self,
        parser,
        rule_engine,
        predictor,
        blacklist_repo: BlacklistRepository,
        detection_repo: DetectionRepository,
    ) -> None:
        self.parser = parser
        self.rule_engine = rule_engine
        self.predictor = predictor
        self.blacklist_repo = blacklist_repo
        self.detection_repo = detection_repo

    def analyze(self, content: bytes, filename: str) -> DetectionResult:
        file_hash = _sha256(content)
        parsed = self.parser.parse(content)

        url_blacklist, domain_blacklist = self.blacklist_repo.active_sets()
        blacklist_metadata = self.blacklist_repo.active_metadata()
        rule_score, explanations = self.rule_engine.evaluate(
            parsed, url_blacklist, domain_blacklist, blacklist_metadata
        )

        prediction = self.predictor.predict(
            ModelInput(subject=parsed.subject, text_body=parsed.text_body)
        )
        final_score = fuse_scores(prediction.phishing_probability, rule_score)
        risk_level = risk_level_for_score(final_score)

        result = DetectionResult(
            result_label=prediction.result_label,
            risk_level=risk_level,
            model_probability=prediction.phishing_probability,
            rule_score=rule_score,
            final_score=final_score,
            model_version=prediction.model_version,
            explanations=explanations,
            urls=parsed.urls,
            attachments=parsed.attachments,
            advice=_advice_for(risk_level),
            parse_warnings=parsed.parse_warnings,
        )
        validate_detection_result(result)

        detection_id = self.detection_repo.save_analysis(
            parsed, result, filename, file_hash
        )
        result.detection_id = detection_id
        result.created_at = iso_z(utcnow())
        return result
