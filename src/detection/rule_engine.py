"""Rule engine placeholder.

成员2 将实现 R01--R10 规则（规则目录见 src/domain/rule_contract.py）与
URL/域名黑名单匹配。此占位版本返回 0 分和空解释，保证后端编排可独立运行。
接口签名按详细实现方案固定：evaluate(parsed, url_blacklist, domain_blacklist)
-> (rule_score, explanations)。
"""

from __future__ import annotations

from src.domain.schemas import Explanation, ParsedEmail


class RuleEngine:
    def evaluate(
        self,
        email: ParsedEmail,
        url_blacklist: set[str],
        domain_blacklist: set[str],
    ) -> tuple[float, list[Explanation]]:
        return 0.0, []
