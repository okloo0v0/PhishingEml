"""Adapter between the backend blacklist repository and member 2's rules."""

from __future__ import annotations

from typing import Any

from src.detection.rules import evaluate_rules
from src.domain.enums import BlacklistMatchType, BlacklistSource, IndicatorType
from src.domain.schemas import Explanation, ParsedEmail


class RuleEngine:
    def evaluate(
        self,
        email: ParsedEmail,
        url_blacklist: set[str],
        domain_blacklist: set[str],
        blacklist_metadata: dict[tuple[str, str], dict[str, Any]] | None = None,
    ) -> tuple[float, list[Explanation]]:
        """Annotate URL matches and execute the complete R01-R10 rule set."""

        metadata = blacklist_metadata or {}
        for url in email.urls:
            exact_key = (IndicatorType.URL.value, url.normalized_url)
            if url.normalized_url and url.normalized_url in url_blacklist:
                self._mark_blacklist(
                    url, BlacklistMatchType.EXACT_URL, metadata.get(exact_key)
                )
                continue

            # Domain indicators may be either a registrable domain or a full
            # hostname, so compare both forms without weakening exact URL priority.
            for domain in (url.registrable_domain, url.host):
                if not domain or domain not in domain_blacklist:
                    continue
                domain_key = (IndicatorType.DOMAIN.value, domain)
                self._mark_blacklist(
                    url,
                    BlacklistMatchType.REGISTRABLE_DOMAIN,
                    metadata.get(domain_key),
                )
                break

        result = evaluate_rules(email)
        return result.rule_score, result.explanations

    @staticmethod
    def _mark_blacklist(
        url,
        match_type: BlacklistMatchType,
        metadata: dict[str, Any] | None,
    ) -> None:
        url.blacklist_hit = True
        url.blacklist_match_type = match_type
        if not metadata:
            return
        url.blacklist_indicator_id = metadata.get("id")
        source = metadata.get("source")
        if source:
            url.blacklist_source = BlacklistSource(source)
        url.blacklist_confidence = metadata.get("confidence")
