"""Phase 2 exit criterion: every endpoint, every benchmark chart.

The per-endpoint tests in ``test_endpoints.py`` use one chart. That catches
wiring mistakes but not the ones that only appear on unusual input — a southern
-hemisphere birth, a negative UTC offset, a near-midnight time, a planet exactly
on a sign boundary.

So this module sweeps **every endpoint across all ten charts** from
``benchmarks/accuracy.py`` — the same charts the accuracy report covers, so a
failure here can be compared against a known-good reference.

Three properties are asserted for each combination:

1. **200 and non-empty.** No endpoint may fall over on any chart.
2. **Determinism.** Two identical requests return byte-identical ``data``,
   which is what the consumer's cache depends on.
3. **No raw enum values leak.** Signs, planets and nakshatras must serialise as
   names. A numeric sign would mean ``to_jsonable`` was bypassed somewhere.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

# The ten charts from benchmarks/accuracy.py, verbatim. Chosen for spread:
# southern hemisphere (Sydney), negative UTC offsets (NYC, London), a
# near-midnight birth (Chennai), and UTC+0 (London).
BENCHMARK_CHARTS: dict[str, dict[str, Any]] = {
    "Mumbai 1990": dict(year=1990, month=3, day=15, hour=10, minute=30,
                        latitude=19.076, longitude=72.878, timezone_offset=5.5),
    "Delhi 1992": dict(year=1992, month=1, day=5, hour=6, minute=15,
                       latitude=28.614, longitude=77.209, timezone_offset=5.5),
    "NYC 1985": dict(year=1985, month=7, day=4, hour=14, minute=0,
                     latitude=40.7128, longitude=-74.006, timezone_offset=-4.0),
    "Chennai 2000": dict(year=2000, month=11, day=20, hour=23, minute=45,
                         latitude=13.083, longitude=80.27, timezone_offset=5.5),
    "London 1975": dict(year=1975, month=12, day=25, hour=3, minute=30,
                        latitude=51.5074, longitude=-0.1278, timezone_offset=0.0),
    "Varanasi 1988": dict(year=1988, month=8, day=15, hour=5, minute=0,
                          latitude=25.3176, longitude=83.0068, timezone_offset=5.5),
    "Kolkata 1995": dict(year=1995, month=6, day=21, hour=12, minute=0,
                         latitude=22.5726, longitude=88.3639, timezone_offset=5.5),
    "Jaipur 2005": dict(year=2005, month=4, day=10, hour=18, minute=30,
                        latitude=26.9124, longitude=75.7873, timezone_offset=5.5),
    "Sydney 1998": dict(year=1998, month=9, day=1, hour=8, minute=15,
                        latitude=-33.8688, longitude=151.2093, timezone_offset=10.0),
    "Tokyo 2010": dict(year=2010, month=2, day=14, hour=22, minute=0,
                       latitude=35.6762, longitude=139.6503, timezone_offset=9.0),
}

# A fixed date for every time-dependent endpoint. Pinned for the same reason the
# benchmark's REFERENCE_DATE is: a clock read would make these tests pass today
# and fail in three months with no code change.
AS_OF = "2026-03-23T12:00:00"

# Endpoints taking only {"birth": ...}.
CHART_ONLY_ENDPOINTS = [
    "/v1/chart",
    "/v1/yogas-doshas",
    "/v1/strength",
    "/v1/houses",
    "/v1/aspects",
    "/v1/states",
    "/v1/kp",
    "/v1/jaimini",
    "/v1/special/relationships",
    "/v1/special/avakhada",
    "/v1/special/sahams",
    "/v1/special/upagrahas",
    "/v1/special/lagnas",
    "/v1/special/functional",
    "/v1/special/chalit",
    "/v1/special/sudarshana",
    "/v1/special/combustion",
]

# The signs, as names. Any of these appearing as a bare integer in a response
# would mean an enum leaked through as its Swiss Ephemeris / 1-based value.
SIGN_NAMES = {
    "ARIES", "TAURUS", "GEMINI", "CANCER", "LEO", "VIRGO", "LIBRA",
    "SCORPIO", "SAGITTARIUS", "CAPRICORN", "AQUARIUS", "PISCES",
}


def _bodies_for(chart: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Build every endpoint's request body for one chart.

    Args:
        chart: Birth data.

    Returns:
        A mapping of endpoint path to request body, covering every endpoint
        that depends on a chart or a place.
    """
    moment = {
        "year": 2026, "month": 3, "day": 23,
        "latitude": chart["latitude"], "longitude": chart["longitude"],
        "timezone_offset": chart["timezone_offset"],
    }
    bodies: dict[str, dict[str, Any]] = {
        path: {"birth": chart} for path in CHART_ONLY_ENDPOINTS
    }
    bodies.update({
        "/v1/divisional": {"birth": chart, "division": 9},
        "/v1/dasha": {"birth": chart, "system": "vimsottari",
                      "levels": 2, "as_of": AS_OF},
        "/v1/transits": {"moment": moment, "birth": chart},
        "/v1/panchanga": moment,
        "/v1/muhurta": moment,
        "/v1/sade-sati": {"birth": chart, "as_of": AS_OF},
        "/v1/chandrashtama": {"birth": chart, "start": AS_OF,
                              "end": "2026-04-23T12:00:00"},
        "/v1/varshaphal": {"birth": chart, "year": 2026},
        "/v1/porutham": {"person1": chart, "person2": BENCHMARK_CHARTS["Mumbai 1990"]},
        "/v1/prashna": {**moment, "hour": 14, "minute": 30, "query_house": 10},
        "/v1/numerology": {"name": "Test Name", "year": chart["year"],
                           "month": chart["month"], "day": chart["day"]},
        "/v1/disha-shool": {"year": 2026, "month": 3, "day": 23},
        "/v1/render": {"birth": chart, "format": "svg", "style": "south"},
    })
    return bodies


ALL_PATHS = sorted(_bodies_for(BENCHMARK_CHARTS["Mumbai 1990"]))


def test_every_endpoint_is_covered(client):
    """Guard against an endpoint being added without being swept here.

    Compares the paths this module exercises against the app's own route table,
    so a new router cannot slip past the exit criterion unnoticed.
    """
    from calc_api.main import app

    registered = {
        route.path
        for route in app.routes
        if getattr(route, "methods", None) and "POST" in route.methods
    }
    # /v1/compatibility and /v1/muhurta/search take no birth block, so they are
    # exercised in test_endpoints.py instead of this chart sweep.
    exempt = {"/v1/compatibility", "/v1/muhurta/search"}
    missing = registered - set(ALL_PATHS) - exempt
    assert not missing, f"endpoints not covered by the chart sweep: {sorted(missing)}"


@pytest.mark.parametrize("chart_name", list(BENCHMARK_CHARTS))
@pytest.mark.parametrize("path", ALL_PATHS)
def test_endpoint_on_every_chart(client, path: str, chart_name: str):
    """Every endpoint must return usable data for every benchmark chart."""
    body = _bodies_for(BENCHMARK_CHARTS[chart_name])[path]

    response = client.post(path, json=body)
    assert response.status_code == 200, f"{path} on {chart_name}: {response.text[:300]}"

    payload = response.json()
    assert payload["data"], f"{path} on {chart_name}: empty data"
    assert payload["meta"]["engine_version"].startswith("0.1.0+fork.")


@pytest.mark.parametrize("chart_name", list(BENCHMARK_CHARTS))
def test_chart_is_deterministic_on_every_chart(client, chart_name: str):
    """Repeat requests must be byte-identical — the cache depends on it."""
    chart = BENCHMARK_CHARTS[chart_name]
    first = client.post("/v1/chart", json={"birth": chart}).json()["data"]
    second = client.post("/v1/chart", json={"birth": chart}).json()["data"]
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


@pytest.mark.parametrize("chart_name", list(BENCHMARK_CHARTS))
def test_no_raw_enum_values_leak(client, chart_name: str):
    """Signs, planets and nakshatras must serialise as names, not numbers.

    A numeric ``sign`` would mean ``to_jsonable`` was bypassed and the engine's
    internal numbering reached the public contract.
    """
    data = client.post(
        "/v1/chart", json={"birth": BENCHMARK_CHARTS[chart_name]}
    ).json()["data"]

    # Planets are keyed by name.
    assert set(data["planets"]) >= {"SUN", "MOON", "SATURN", "RAHU", "KETU"}

    for planet_name, position in data["planets"].items():
        assert position["sign"] in SIGN_NAMES, (
            f"{chart_name}/{planet_name}: sign serialised as "
            f"{position['sign']!r} rather than a name"
        )
        assert isinstance(position["nakshatra_info"]["nakshatra"], str)
        assert isinstance(position["nakshatra_info"]["lord"], str)

    assert data["ascendant"]["sign"] in SIGN_NAMES


@pytest.mark.parametrize("chart_name", list(BENCHMARK_CHARTS))
def test_sade_sati_flags_are_consistent(client, chart_name: str):
    """The umbrella flag must equal the union of the three specific ones.

    This is the phase-1 fix, asserted across every chart rather than the two it
    was developed against.
    """
    data = client.post(
        "/v1/sade-sati",
        json={"birth": BENCHMARK_CHARTS[chart_name], "as_of": AS_OF},
    ).json()["data"]

    specifics = (
        data["is_sade_sati"],
        data["is_small_panoti"],
        data["is_ashtama_shani"],
    )
    assert data["is_active"] == any(specifics)
    # The three distances are mutually exclusive.
    assert sum(specifics) <= 1
    assert (data["current_phase"] is not None) == data["is_active"]


@pytest.mark.parametrize("chart_name", list(BENCHMARK_CHARTS))
def test_render_produces_a_real_svg(client, chart_name: str):
    """The SVG renderer is what the mobile client will draw, so it must be valid."""
    data = client.post(
        "/v1/render",
        json={"birth": BENCHMARK_CHARTS[chart_name], "format": "svg"},
    ).json()["data"]

    assert data["format"] == "svg"
    assert data["content"].lstrip().startswith("<svg")
    assert "</svg>" in data["content"]


@pytest.mark.parametrize("chart_name", list(BENCHMARK_CHARTS))
def test_all_four_dasha_systems_on_every_chart(client, chart_name: str):
    """All four systems must produce a timeline for every chart."""
    for system in ("vimsottari", "yogini", "ashtottari", "narayana"):
        response = client.post(
            "/v1/dasha",
            json={
                "birth": BENCHMARK_CHARTS[chart_name],
                "system": system,
                "as_of": AS_OF,
            },
        )
        assert response.status_code == 200, (
            f"{system} on {chart_name}: {response.text[:200]}"
        )
        assert response.json()["data"]["timeline"], f"{system} on {chart_name}: empty"
