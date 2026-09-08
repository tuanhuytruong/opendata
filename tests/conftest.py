"""Shared test isolation for in-memory request rate-limit state."""

from collections.abc import Iterator
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "api"))
from main import InMemoryRateLimitMiddleware  # noqa: E402


@pytest.fixture(autouse=True)
def reset_in_memory_rate_limit() -> Iterator[None]:
    InMemoryRateLimitMiddleware.buckets.clear()
    yield
    InMemoryRateLimitMiddleware.buckets.clear()
