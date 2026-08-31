from dataclasses import dataclass

from .enums import Severity


class RuleCode:
    SENDER_REPLY_TO_MISMATCH = "R01"
    DISPLAY_LINK_MISMATCH = "R02"
    BLACKLIST_HIT = "R03"
    URGENT_LANGUAGE = "R04"
    CREDENTIAL_REQUEST = "R05"
    SUSPICIOUS_URL = "R06"
    RISKY_ATTACHMENT = "R07"
    MISSING_SENDER = "R08"
    HEADER_ANOMALY = "R09"
    BRAND_IMPERSONATION = "R10"


@dataclass(frozen=True)
class RuleSpec:
    code: str
    title: str
    default_score: float
    severity: Severity
    max_hits_per_email: int = 1


RULE_CATALOG = {
    RuleCode.SENDER_REPLY_TO_MISMATCH: RuleSpec(
        RuleCode.SENDER_REPLY_TO_MISMATCH,
        "发件人与 Reply-To 域名不一致",
        15.0,
        Severity.WARNING,
    ),
    RuleCode.DISPLAY_LINK_MISMATCH: RuleSpec(
        RuleCode.DISPLAY_LINK_MISMATCH,
        "链接显示信息与真实目标不一致",
        20.0,
        Severity.CRITICAL,
    ),
    RuleCode.BLACKLIST_HIT: RuleSpec(
        RuleCode.BLACKLIST_HIT,
        "URL 或域名命中黑名单",
        40.0,
        Severity.CRITICAL,
    ),
    RuleCode.URGENT_LANGUAGE: RuleSpec(
        RuleCode.URGENT_LANGUAGE,
        "正文包含紧迫性诱导语言",
        10.0,
        Severity.WARNING,
    ),
    RuleCode.CREDENTIAL_REQUEST: RuleSpec(
        RuleCode.CREDENTIAL_REQUEST,
        "邮件要求提交账号或敏感信息",
        15.0,
        Severity.WARNING,
    ),
    RuleCode.SUSPICIOUS_URL: RuleSpec(
        RuleCode.SUSPICIOUS_URL,
        "URL 存在可疑结构特征",
        10.0,
        Severity.WARNING,
    ),
    RuleCode.RISKY_ATTACHMENT: RuleSpec(
        RuleCode.RISKY_ATTACHMENT,
        "附件类型或文件名存在风险提示",
        20.0,
        Severity.CRITICAL,
    ),
    RuleCode.MISSING_SENDER: RuleSpec(
        RuleCode.MISSING_SENDER,
        "发件人字段缺失或格式异常",
        5.0,
        Severity.INFO,
    ),
    RuleCode.HEADER_ANOMALY: RuleSpec(
        RuleCode.HEADER_ANOMALY,
        "邮件头存在异常或不完整信息",
        10.0,
        Severity.WARNING,
    ),
    RuleCode.BRAND_IMPERSONATION: RuleSpec(
        RuleCode.BRAND_IMPERSONATION,
        "邮件内容疑似冒充权威品牌",
        10.0,
        Severity.WARNING,
    ),
}

MAX_RULE_SCORE = 100.0
