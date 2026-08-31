from enum import Enum


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ResultLabel(str, Enum):
    LEGITIMATE = "legitimate"
    PHISHING = "phishing"


class IndicatorType(str, Enum):
    URL = "url"
    DOMAIN = "domain"


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class FeedbackLabel(str, Enum):
    CONFIRMED_PHISHING = "confirmed_phishing"
    FALSE_POSITIVE = "false_positive"
    UNSURE = "unsure"


class BlacklistStatus(str, Enum):
    ACTIVE = "active"
    REVIEW = "review"
    FALSE_POSITIVE = "false_positive"


class BlacklistSource(str, Enum):
    MANUAL = "manual"
    IMPORT = "import"
    PHISHTANK = "phishtank"


class BlacklistMatchType(str, Enum):
    EXACT_URL = "exact_url"
    REGISTRABLE_DOMAIN = "registrable_domain"
