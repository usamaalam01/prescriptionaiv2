"""Rate limiter unit tests."""

import pytest
from fastapi import HTTPException

from app.core.rate_limit import SlidingWindowLimiter


def test_sliding_window_allows_then_blocks():
    lim = SlidingWindowLimiter()
    for _ in range(3):
        lim.check("t1", limit=3, window_seconds=60)
    with pytest.raises(HTTPException) as exc:
        lim.check("t1", limit=3, window_seconds=60)
    assert exc.value.status_code == 429


def test_sliding_window_keys_are_independent():
    lim = SlidingWindowLimiter()
    lim.check("a", limit=1, window_seconds=60)
    lim.check("b", limit=1, window_seconds=60)
    with pytest.raises(HTTPException):
        lim.check("a", limit=1, window_seconds=60)
