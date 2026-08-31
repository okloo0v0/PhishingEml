from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum
from typing import Any

from .enums import ResultLabel, RiskLevel, Severity


@dataclass
class Mailbox:
    display_name: str = ""
    address: str = ""
    domain: str = ""
    is_valid: bool = False


@dataclass
class ParsedUrl:
    raw_url: str
    normalized_url: str
    display_text: str = ""
    scheme: str = ""
    host: str = ""
    registrable_domain: str = ""
    port: int | None = None
    path: str = ""
    query: str = ""
    is_https: bool = False
    uses_ip: bool = False
    is_shortener: bool = False
    suspicious_tokens: list[str] = field(default_factory=list)
    blacklist_hit: bool = False
    blacklist_match_type: str | None = None


@dataclass
class AttachmentMeta:
    filename: str
    mime_type: str
    size: int
    sha256: str
    extension: str = ""
    risk_hints: list[str] = field(default_factory=list)


@dataclass
class ParsedEmail:
    message_id: str = ""
    subject: str = ""
    date: str = ""
    sender: Mailbox = field(default_factory=Mailbox)
    reply_to: Mailbox | None = None
    return_path: Mailbox | None = None
    recipients: list[Mailbox] = field(default_factory=list)
    cc: list[Mailbox] = field(default_factory=list)
    text_body: str = ""
    html_body: str = ""
    urls: list[ParsedUrl] = field(default_factory=list)
    attachments: list[AttachmentMeta] = field(default_factory=list)
    headers: dict[str, str] = field(default_factory=dict)
    parse_warnings: list[str] = field(default_factory=list)


@dataclass
class Explanation:
    code: str
    title: str
    detail: str
    evidence: str = ""
    score: float = 0.0
    severity: Severity = Severity.WARNING


@dataclass
class DetectionResult:
    result_label: ResultLabel
    risk_level: RiskLevel
    model_probability: float
    rule_score: float
    final_score: float
    model_version: str
    explanations: list[Explanation] = field(default_factory=list)
    urls: list[ParsedUrl] = field(default_factory=list)
    attachments: list[AttachmentMeta] = field(default_factory=list)
    advice: list[str] = field(default_factory=list)
    parse_warnings: list[str] = field(default_factory=list)
    detection_id: int | None = None
    created_at: str | None = None


@dataclass
class AnalyzeResponse:
    success: bool
    data: DetectionResult
    request_id: str


@dataclass
class ErrorResponse:
    success: bool
    error: dict[str, str]
    request_id: str


def to_jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {
            key: to_jsonable(item)
            for key, item in asdict(value).items()
        }
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    return value


def validate_detection_result(result: DetectionResult) -> None:
    if not 0.0 <= result.model_probability <= 1.0:
        raise ValueError("model_probability must be between 0 and 1")
    if not 0.0 <= result.rule_score <= 100.0:
        raise ValueError("rule_score must be between 0 and 100")
    if not 0.0 <= result.final_score <= 100.0:
        raise ValueError("final_score must be between 0 and 100")
    if not result.model_version:
        raise ValueError("model_version must not be empty")

