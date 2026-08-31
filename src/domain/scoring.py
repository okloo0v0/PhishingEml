from .enums import ResultLabel, RiskLevel


MODEL_WEIGHT = 0.65
RULE_WEIGHT = 0.35
LOW_RISK_THRESHOLD = 30.0
HIGH_RISK_THRESHOLD = 60.0
MODEL_PHISHING_THRESHOLD = 0.50


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))


def normalize_rule_score(rule_score: float) -> float:
    return clamp(rule_score, 0.0, 100.0) / 100.0


def fuse_scores(model_probability: float, rule_score: float) -> float:
    model_probability = clamp(model_probability, 0.0, 1.0)
    rule_probability = normalize_rule_score(rule_score)
    final_probability = (
        MODEL_WEIGHT * model_probability
        + RULE_WEIGHT * rule_probability
    )
    return round(clamp(final_probability * 100.0, 0.0, 100.0), 1)


def risk_level_for_score(final_score: float) -> RiskLevel:
    score = clamp(final_score, 0.0, 100.0)
    if score < LOW_RISK_THRESHOLD:
        return RiskLevel.LOW
    if score < HIGH_RISK_THRESHOLD:
        return RiskLevel.MEDIUM
    return RiskLevel.HIGH


def label_for_probability(model_probability: float) -> ResultLabel:
    if model_probability >= MODEL_PHISHING_THRESHOLD:
        return ResultLabel.PHISHING
    return ResultLabel.LEGITIMATE

