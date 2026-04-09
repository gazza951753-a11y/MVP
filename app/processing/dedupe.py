from __future__ import annotations

import hashlib

from app.processing.normalize import normalize_text


def make_fingerprint(text: str, source_url: str) -> str:
    base = f"{normalize_text(text)}::{source_url.strip().lower()}"
    return f"sha256:{hashlib.sha256(base.encode('utf-8')).hexdigest()}"
