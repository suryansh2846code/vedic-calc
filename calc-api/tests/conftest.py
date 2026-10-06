"""Shared fixtures.

The reference chart is the one used throughout the engine's own test suite —
15 March 1990, 10:30 IST, Mumbai — so that failures here can be compared
against the engine's expectations directly.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from calc_api.main import app

# Mumbai, 15 March 1990, 10:30 IST.
REFERENCE_BIRTH = {
    "year": 1990,
    "month": 3,
    "day": 15,
    "hour": 10,
    "minute": 30,
    "latitude": 19.0760,
    "longitude": 72.8777,
    "timezone_offset": 5.5,
}


@pytest.fixture()
def client() -> TestClient:
    """A test client with authentication disabled (no ``CALC_API_KEY`` set)."""
    return TestClient(app)


@pytest.fixture()
def birth() -> dict:
    """A copy of the reference birth data, safe for a test to mutate."""
    return dict(REFERENCE_BIRTH)
