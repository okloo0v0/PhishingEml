import re
from dataclasses import dataclass, field

from src.domain.rule_contract import MAX_RULE_SCORE, RULE_CATALOG, RuleCode
from src.domain.schemas import Explanation, ParsedEmail
from src.parsers.url_parser import get_registrable_domain, normalize_url


URGENT_PATTERNS = (
    "urgent",
    "immediately",
    "limited time",
    "within 24 hours",
    "account suspended",
    "verify now",
    "\u7d27\u6025",
    "\u7acb\u5373",
    "\u9a6c\u4e0a",
    "\u9650\u65f6",
    "\u8fc7\u671f",
    "\u6682\u505c",
    "\u51bb\u7ed3",
)
SENSITIVE_PATTERNS = (
    "password",
    "verification code",
    "credit card",
    "bank card",
    "login",
    "credential",
    "verification",
    "\u5bc6\u7801",
    "\u9a8c\u8bc1\u7801",
    "\u94f6\u884c\u5361",
    "\u8eab\u4efd\u8bc1",
    "\u8d26\u6237",
    "\u8d26\u53f7",
    "\u767b\u5f55",
)
BRAND_PATTERNS = (
    "paypal",
    "microsoft",
    "apple",
    "google",
    "amazon",
    "alipay",
    "bank",
    "wechat",
    "office 365",
    "\u817e\u8baf",
    "\u963f\u91cc",
    "\u652f\u4ed8\u5b9d",
    "\u5fae\u4fe1",
    "\u94f6\u884c",
)


@dataclass
class RuleEvaluation:
    rule_score: float = 0.0
    explanations: list[Explanation] = field(default_factory=list)


def evaluate_rules(email: ParsedEmail) -> RuleEvaluation:
    explanations: list[Explanation] = []
    _add_sender_reply_to_mismatch(email, explanations)
    _add_display_link_mismatch(email, explanations)
    _add_blacklist_hit(email, explanations)
    _add_urgent_language(email, explanations)
    _add_credential_request(email, explanations)
    _add_suspicious_url(email, explanations)
    _add_risky_attachment(email, explanations)
    _add_missing_sender(email, explanations)
    _add_header_anomaly(email, explanations)
    _add_brand_impersonation(email, explanations)

    deduped: list[Explanation] = []
    seen: set[str] = set()
    for explanation in explanations:
        if explanation.code in seen:
            continue
        deduped.append(explanation)
        seen.add(explanation.code)

    score = min(sum(item.score for item in deduped), MAX_RULE_SCORE)
    return RuleEvaluation(rule_score=round(score, 1), explanations=deduped)


def _explanation(code: str, detail: str, evidence: str = "") -> Explanation:
    spec = RULE_CATALOG[code]
    return Explanation(
        code=code,
        title=spec.title,
        detail=detail,
        evidence=_clip(evidence),
        score=spec.default_score,
        severity=spec.severity,
    )


def _add_sender_reply_to_mismatch(email: ParsedEmail, explanations: list[Explanation]) -> None:
    if email.sender.domain and email.reply_to and email.reply_to.domain:
        if email.sender.domain != email.reply_to.domain:
            explanations.append(
                _explanation(
                    RuleCode.SENDER_REPLY_TO_MISMATCH,
                    "From and Reply-To domains differ; replies may be routed elsewhere.",
                    f"from={email.sender.domain}; reply_to={email.reply_to.domain}",
                )
            )


def _add_display_link_mismatch(email: ParsedEmail, explanations: list[Explanation]) -> None:
    for url in email.urls:
        display = (url.display_text or "").strip()
        if not display:
            continue
        display_url = normalize_url(display)
        display_domain = display_url.registrable_domain or get_registrable_domain(display.lower())
        target_domain = url.registrable_domain or url.host
        if display_domain and target_domain and display_domain != target_domain:
            explanations.append(
                _explanation(
                    RuleCode.DISPLAY_LINK_MISMATCH,
                    "Visible link text and actual target domain differ.",
                    f"display={display_domain}; target={target_domain}",
                )
            )
            return


def _add_blacklist_hit(email: ParsedEmail, explanations: list[Explanation]) -> None:
    for url in email.urls:
        if url.blacklist_hit:
            explanations.append(
                _explanation(
                    RuleCode.BLACKLIST_HIT,
                    "URL or domain matched an offline blacklist indicator.",
                    url.normalized_url or url.raw_url,
                )
            )
            return


def _add_urgent_language(email: ParsedEmail, explanations: list[Explanation]) -> None:
    text = _combined_text(email)
    if _contains_any(text, URGENT_PATTERNS):
        explanations.append(
            _explanation(
                RuleCode.URGENT_LANGUAGE,
                "Body contains urgency language that may pressure the user.",
                _first_match(text, URGENT_PATTERNS),
            )
        )


def _add_credential_request(email: ParsedEmail, explanations: list[Explanation]) -> None:
    text = _combined_text(email)
    if _contains_any(text, SENSITIVE_PATTERNS):
        explanations.append(
            _explanation(
                RuleCode.CREDENTIAL_REQUEST,
                "Body appears to request credentials or other sensitive information.",
                _first_match(text, SENSITIVE_PATTERNS),
            )
        )


def _add_suspicious_url(email: ParsedEmail, explanations: list[Explanation]) -> None:
    for url in email.urls:
        if url.suspicious_tokens:
            explanations.append(
                _explanation(
                    RuleCode.SUSPICIOUS_URL,
                    "URL contains suspicious structural features.",
                    f"{url.host or url.raw_url}: {', '.join(url.suspicious_tokens[:5])}",
                )
            )
            return


def _add_risky_attachment(email: ParsedEmail, explanations: list[Explanation]) -> None:
    for attachment in email.attachments:
        if attachment.risk_hints:
            explanations.append(
                _explanation(
                    RuleCode.RISKY_ATTACHMENT,
                    "Attachment filename or extension has risk hints; only metadata is recorded.",
                    f"{attachment.filename}: {', '.join(attachment.risk_hints)}",
                )
            )
            return


def _add_missing_sender(email: ParsedEmail, explanations: list[Explanation]) -> None:
    if not email.sender.address or not email.sender.is_valid:
        explanations.append(
            _explanation(
                RuleCode.MISSING_SENDER,
                "Sender is missing or has an invalid email format.",
                email.sender.address or "missing_from",
            )
        )


def _add_header_anomaly(email: ParsedEmail, explanations: list[Explanation]) -> None:
    warning_hits = [item for item in email.parse_warnings if item.startswith(("missing_", "invalid_", "decode_"))]
    if warning_hits:
        explanations.append(
            _explanation(
                RuleCode.HEADER_ANOMALY,
                "Headers or MIME content contain incomplete or abnormal information.",
                ", ".join(warning_hits[:4]),
            )
        )


def _add_brand_impersonation(email: ParsedEmail, explanations: list[Explanation]) -> None:
    text = _combined_text(email)
    sender_domain = email.sender.domain
    for brand in BRAND_PATTERNS:
        if brand.lower() in text and sender_domain and brand.lower().replace(" ", "") not in sender_domain:
            explanations.append(
                _explanation(
                    RuleCode.BRAND_IMPERSONATION,
                    "Subject or body mentions a known brand, but sender domain does not match.",
                    f"brand={brand}; sender_domain={sender_domain}",
                )
            )
            return


def _combined_text(email: ParsedEmail) -> str:
    return f"{email.subject}\n{email.text_body}".lower()


def _contains_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(pattern.lower() in text for pattern in patterns)


def _first_match(text: str, patterns: tuple[str, ...]) -> str:
    for pattern in patterns:
        match = re.search(re.escape(pattern), text, flags=re.IGNORECASE)
        if match:
            return match.group(0)
    return ""


def _clip(value: str, limit: int = 160) -> str:
    normalized = " ".join((value or "").split())
    return normalized[:limit]
