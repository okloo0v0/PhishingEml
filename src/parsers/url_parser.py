import html
import ipaddress
import re
from html.parser import HTMLParser
from urllib.parse import SplitResult, urlsplit, urlunsplit

from src.domain.schemas import ParsedUrl


SHORTENER_DOMAINS = {
    "bit.ly",
    "cutt.ly",
    "goo.gl",
    "is.gd",
    "ow.ly",
    "rebrand.ly",
    "s.id",
    "t.co",
    "tinyurl.com",
    "v.gd",
}

SUSPICIOUS_TOKEN_KEYWORDS = {
    "account",
    "bank",
    "confirm",
    "login",
    "password",
    "secure",
    "signin",
    "update",
    "verify",
    "wallet",
}

SECOND_LEVEL_SUFFIXES = {
    "ac.cn",
    "ac.uk",
    "co.jp",
    "co.uk",
    "com.au",
    "com.cn",
    "com.hk",
    "com.sg",
    "edu.cn",
    "gov.cn",
    "net.cn",
    "org.cn",
}

URL_PATTERN = re.compile(
    r"(?i)(?<!@)\b((?:https?://|www\.)[^\s<>'\"]+|"
    r"(?:[a-z0-9-]+\.)+[a-z]{2,}(?:/[^\s<>'\"]*)?)"
)


class _LinkExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._current_href: str | None = None
        self._text_parts: list[str] = []
        self.text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        attr_map = {name.lower(): value or "" for name, value in attrs}
        href = attr_map.get("href", "").strip()
        if href:
            self._current_href = href
            self._text_parts = []

    def handle_data(self, data: str) -> None:
        self.text_parts.append(data)
        if self._current_href is not None:
            self._text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or self._current_href is None:
            return
        self.links.append((self._current_href, " ".join(self._text_parts).strip()))
        self._current_href = None
        self._text_parts = []


def html_to_text(value: str) -> str:
    parser = _LinkExtractor()
    parser.feed(value or "")
    return html.unescape(" ".join(part.strip() for part in parser.text_parts if part.strip()))


def extract_urls_from_html(value: str) -> list[ParsedUrl]:
    parser = _LinkExtractor()
    parser.feed(value or "")
    urls = [normalize_url(href, display_text=text) for href, text in parser.links]
    existing = {(url.raw_url, url.display_text) for url in urls}
    link_display_urls = {url.display_text.strip() for url in urls if url.display_text.strip()}
    for url in extract_urls_from_text(html_to_text(value)):
        if url.raw_url in link_display_urls:
            continue
        key = (url.raw_url, url.display_text)
        if key not in existing:
            urls.append(url)
            existing.add(key)
    return urls


def extract_urls_from_text(value: str) -> list[ParsedUrl]:
    urls: list[ParsedUrl] = []
    seen: set[str] = set()
    for match in URL_PATTERN.finditer(value or ""):
        raw_url = match.group(1).rstrip(".,;:!?)\u3002\uff0c\uff1b")
        if raw_url in seen:
            continue
        urls.append(normalize_url(raw_url))
        seen.add(raw_url)
    return urls


def normalize_url(raw_url: str, display_text: str = "") -> ParsedUrl:
    raw = (raw_url or "").strip()
    candidate = raw
    suspicious_tokens: list[str] = []
    if candidate and not re.match(r"(?i)^[a-z][a-z0-9+.-]*://", candidate):
        if candidate.startswith("www.") or re.match(r"(?i)^(?:[a-z0-9-]+\.)+[a-z]{2,}(?:[/:?#]|$)", candidate):
            candidate = f"http://{candidate}"
            suspicious_tokens.append("missing_scheme")

    try:
        parsed = urlsplit(candidate)
    except ValueError:
        return ParsedUrl(
            raw_url=raw,
            normalized_url="",
            display_text=display_text,
            suspicious_tokens=suspicious_tokens + ["parse_error"],
        )

    if not parsed.scheme or not parsed.netloc:
        return ParsedUrl(
            raw_url=raw,
            normalized_url="",
            display_text=display_text,
            suspicious_tokens=suspicious_tokens + ["parse_error"],
        )

    scheme = parsed.scheme.lower()
    host = _normalize_host(parsed.hostname or "")
    try:
        port = parsed.port
    except ValueError:
        return ParsedUrl(
            raw_url=raw,
            normalized_url="",
            display_text=display_text,
            scheme=scheme,
            host=host,
            suspicious_tokens=_dedupe(suspicious_tokens + ["parse_error"]),
        )
    if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
        port = None

    authority = _format_authority(host, port)
    normalized = urlunsplit(
        SplitResult(scheme, authority, parsed.path or "", parsed.query or "", "")
    )
    uses_ip = _is_ip(host)
    registrable_domain = "" if uses_ip or host == "localhost" else get_registrable_domain(host)
    shortener_key = registrable_domain or host
    suspicious_tokens.extend(
        _suspicious_tokens(
            raw=raw,
            parsed=parsed,
            host=host,
            registrable_domain=registrable_domain,
            uses_ip=uses_ip,
            is_shortener=shortener_key in SHORTENER_DOMAINS,
        )
    )

    return ParsedUrl(
        raw_url=raw,
        normalized_url=normalized,
        display_text=display_text,
        scheme=scheme,
        host=host,
        registrable_domain=registrable_domain,
        port=port,
        path=parsed.path or "",
        query=parsed.query or "",
        is_https=scheme == "https",
        uses_ip=uses_ip,
        is_shortener=shortener_key in SHORTENER_DOMAINS,
        suspicious_tokens=_dedupe(suspicious_tokens),
    )


def get_registrable_domain(host: str) -> str:
    host = host.lower().rstrip(".")
    if not host or host == "localhost" or _is_ip(host):
        return ""
    labels = [label for label in host.split(".") if label]
    if len(labels) < 2:
        return ""
    suffix = ".".join(labels[-2:])
    if suffix in SECOND_LEVEL_SUFFIXES and len(labels) >= 3:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def _normalize_host(host: str) -> str:
    host = host.strip().rstrip(".").lower()
    if not host:
        return ""
    if ":" in host and _is_ip(host):
        return ipaddress.ip_address(host).compressed.lower()
    try:
        return host.encode("idna").decode("ascii")
    except UnicodeError:
        return host


def _format_authority(host: str, port: int | None) -> str:
    authority_host = f"[{host}]" if ":" in host and _is_ip(host) else host
    return f"{authority_host}:{port}" if port is not None else authority_host


def _is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host.strip("[]"))
        return True
    except ValueError:
        return False


def _suspicious_tokens(
    raw: str,
    parsed,
    host: str,
    registrable_domain: str,
    uses_ip: bool,
    is_shortener: bool,
) -> list[str]:
    tokens: list[str] = []
    lowered = raw.lower()
    combined = f"{parsed.path} {parsed.query}".lower()
    if parsed.scheme.lower() != "https":
        tokens.append("non_https")
    if uses_ip:
        tokens.append("ip_host")
    if is_shortener:
        tokens.append("shortener")
    if len(raw) >= 120:
        tokens.append("long_url")
    if "@" in parsed.netloc:
        tokens.append("userinfo")
    if "%" in parsed.path or "%" in parsed.query:
        tokens.append("encoded_chars")
    if registrable_domain and host.endswith(registrable_domain):
        subdomain = host[: -len(registrable_domain)].strip(".")
        if subdomain.count(".") >= 2:
            tokens.append("many_subdomains")
    for keyword in SUSPICIOUS_TOKEN_KEYWORDS:
        if keyword in combined or keyword in lowered:
            tokens.append(keyword)
    if "xn--" in host:
        tokens.append("punycode")
    return tokens


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result
