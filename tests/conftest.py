"""Pytest configuration and shared fixtures."""
from __future__ import annotations

import pytest

from app.processing.classify_rules import invalidate_cache


@pytest.fixture(autouse=True)
def reset_classify_cache():
    """Force classify_rules to use baseline rules for every test (no DB dependency)."""
    invalidate_cache()
    yield
    invalidate_cache()
