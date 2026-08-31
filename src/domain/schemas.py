import math
from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum
from typing import Any

from .enums import (
    BlacklistMatchType,
    BlacklistSource,
    BlacklistStatus,
    FeedbackLabel,
    IndicatorType,
    ResultLabel,
    RiskLevel,
    Severity,
)
from .scoring import fuse_scores, label_for_probability, risk_level_for_score


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
    blacklist_match_type: BlacklistMatchType | None = None
    blacklist_indicator_id: int | None = None
    blacklist_source: BlacklistSource | None = None
    blacklist_confidence: float | None = None


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
class ModelInput:
    subject: str = ""
    text_body: str = ""
    model_text: str = ""
    feature_version: str = "text-v1"


@dataclass
class FeatureVector:
    feature_version: str
    model_text: str
    numeric_features: dict[str, float] = field(default_factory=dict)


@dataclass
class ModelPrediction:
    result_label: ResultLabel
    phishing_probability: float
    model_version: str
    feature_version: str


@dataclass
class ModelMetadata:
    model_name: str
    model_version: str
    feature_version: str
    trained_at: str
    label_order: list[ResultLabel]
    metrics: dict[str, float] = field(default_factory=dict)
    artifact_filename: str = "phishing_model.joblib"
    metadata_filename: str = "model_meta.json"


@dataclass
class BlacklistMatch:
    indicator_id: int
    indicator: str
    indicator_type: IndicatorType
    match_type: BlacklistMatchType
    source: BlacklistSource
    confidence: float | None = None


@dataclass
class Pagination:
    page: int
    page_size: int
    total: int
    total_pages: int


@dataclass
class DetectionSummary:
    detection_id: int
    subject: str
    result_label: ResultLabel
    risk_level: RiskLevel
    final_score: float
    url_count: int
    attachment_count: int
    model_version: str
    created_at: str


@dataclass
class HistoryResponse:
    items: list[DetectionSummary]
    pagination: Pagination


@dataclass
class BlacklistItem:
    id: int
    indicator: str
    indicator_type: IndicatorType
    source: BlacklistSource
    status: BlacklistStatus
    confidence: float | None
    note: str
    hit_count: int
    created_at: str
    updated_at: str


@dataclass
class StatisticsOverview:
    total_detections: int
    risk_counts: dict[RiskLevel, int]
    result_counts: dict[ResultLabel, int]
    rule_hit_counts: dict[str, int]
    attachment_type_counts: dict[str, int]
    daily_counts: dict[str, int]


@dataclass
class ModelMetrics:
    model_name: str
    model_version: str
    feature_version: str
    trained_at: str
    sample_counts: dict[str, int]
    metrics: dict[str, float]
    confusion_matrix: list[list[int]]


@dataclass
class KnowledgeArticle:
    id: int
    category: str
    title: str
    summary: str
    content: str
    sort_order: int = 0


@dataclass
class FeedbackRequest:
    detection_id: int
    label: FeedbackLabel
    note: str = ""


@dataclass
class FeedbackResponse:
    feedback_id: int
    detection_id: int
    label: FeedbackLabel
    created_at: str


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
        return {to_jsonable(key): to_jsonable(item) for key, item in value.items()}
    return value


def validate_detection_result(result: DetectionResult) -> None:
    for value_name, value in (
        ("model_probability", result.model_probability),
        ("rule_score", result.rule_score),
        ("final_score", result.final_score),
    ):
        if not math.isfinite(value):
            raise ValueError(f"{value_name} must be finite")
    if not 0.0 <= result.model_probability <= 1.0:
        raise ValueError("model_probability must be between 0 and 1")
    if not 0.0 <= result.rule_score <= 100.0:
        raise ValueError("rule_score must be between 0 and 100")
    if not 0.0 <= result.final_score <= 100.0:
        raise ValueError("final_score must be between 0 and 100")
    if not result.model_version:
        raise ValueError("model_version must not be empty")
    expected_score = fuse_scores(
        result.model_probability,
        result.rule_score,
    )
    if abs(result.final_score - expected_score) > 0.05:
        raise ValueError("final_score does not match the scoring contract")
    if result.risk_level != risk_level_for_score(result.final_score):
        raise ValueError("risk_level does not match final_score")
    if result.result_label != label_for_probability(result.model_probability):
        raise ValueError("result_label does not match model_probability")


def validate_model_prediction(prediction: ModelPrediction) -> None:
    if not math.isfinite(prediction.phishing_probability):
        raise ValueError("phishing_probability must be finite")
    if not 0.0 <= prediction.phishing_probability <= 1.0:
        raise ValueError("phishing_probability must be between 0 and 1")
    if not prediction.model_version:
        raise ValueError("model_version must not be empty")
    if not prediction.feature_version:
        raise ValueError("feature_version must not be empty")
    if prediction.result_label != label_for_probability(
        prediction.phishing_probability
    ):
        raise ValueError("result_label does not match phishing_probability")


def validate_pagination(pagination: Pagination) -> None:
    if pagination.page < 1:
        raise ValueError("page must be at least 1")
    if not 1 <= pagination.page_size <= 100:
        raise ValueError("page_size must be between 1 and 100")
    if pagination.total < 0 or pagination.total_pages < 0:
        raise ValueError("pagination totals must not be negative")
    expected_total_pages = (
        (pagination.total + pagination.page_size - 1) // pagination.page_size
        if pagination.total
        else 0
    )
    if pagination.total_pages != expected_total_pages:
        raise ValueError("total_pages does not match total and page_size")
    if pagination.page > max(1, pagination.total_pages):
        raise ValueError("page is out of range")
