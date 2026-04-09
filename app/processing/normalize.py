from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_content",
    "utm_term",
    "ref",
    "ref_src",
}


def canonicalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    scheme = parsed.scheme.lower() or "https"
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/") or "/"
    filtered_query = [(k, v) for k, v in parse_qsl(parsed.query) if k.lower() not in TRACKING_PARAMS]
    query = urlencode(filtered_query)
    return urlunparse((scheme, netloc, path, "", query, ""))


def normalize_text(text: str) -> str:
    text = text.lower().replace("вкр", "вкр").replace("антиплаг", "антиплагиат")
    text = re.sub(r"\s+", " ", text)
    return text.strip()
