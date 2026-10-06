"""Endpoint tests.

Three things are checked, in order of importance:

1. **Agreement with the engine.** The API must return exactly what a direct
   engine call returns — a wrapper that quietly transforms values is worse than
   no wrapper.
2. **Determinism.** The same request twice must give identical ``data``. This is
   what the consumer's cache depends on.
3. **The envelope and error contract.**
"""

from __future__ import annotations

from datetime import datetime

import pytest
from vedic_calc import calculate_chart
from vedic_calc.core.constants import Ayanamsa, Planet, Sign

# Sign names, for asserting that KP does not leak 1-based sign indices.
SIGN_NAMES_KP = {s.name for s in Sign}


class TestMeta:
    """Health and version."""

    def test_healthz(self, client):
        assert client.get("/healthz").json() == {"status": "ok"}

    def test_version_reports_engine_and_ephemeris(self, client):
        body = client.get("/v1/version").json()
        assert body["engine_version"].startswith("0.1.0+fork.")
        assert "swisseph" in body["ephemeris"]
        assert body["ayanamsa_default"] == "LAHIRI"
        # All four engine ayanamsas must be offered — astrologers disagree
        # about which to use and the choice has to be visible.
        assert set(body["ayanamsas_supported"]) == {a.name for a in Ayanamsa}

    def test_root_advertises_source(self, client):
        """AGPL section 13 requires a prominent offer of source."""
        body = client.get("/").json()
        assert body["licence"] == "AGPL-3.0-or-later"
        assert body["source"].startswith("https://github.com/")


class TestChartAgreesWithEngine:
    """The wrapper must not alter what the engine computed."""

    def test_longitudes_match_direct_engine_call(self, client, birth):
        api = client.post("/v1/chart", json={"birth": birth})
        assert api.status_code == 200
        data = api.json()["data"]

        direct = calculate_chart(
            year=1990, month=3, day=15, hour=10, minute=30,
            latitude=19.0760, longitude=72.8777, timezone_offset=5.5,
            ayanamsa=Ayanamsa.LAHIRI,
        )

        # Planet keys are serialised to enum *names*, not the engine's numeric
        # Swiss Ephemeris ids, which are an implementation detail.
        for planet in Planet:
            served = data["planets"][planet.name]
            assert served["longitude"] == pytest.approx(
                direct.planets[planet].longitude, abs=1e-9
            ), f"{planet.name} longitude diverged from a direct engine call"
            assert served["sign"] == direct.planets[planet].sign.name

    def test_envelope_shape(self, client, birth):
        body = client.post("/v1/chart", json={"birth": birth}).json()
        assert set(body) == {"data", "meta"}
        assert set(body["meta"]) == {"engine_version", "ayanamsa", "computed_at"}
        assert body["meta"]["ayanamsa"] == "LAHIRI"

    def test_deterministic(self, client, birth):
        """Identical requests must give identical data, or caching is unsafe."""
        first = client.post("/v1/chart", json={"birth": birth}).json()["data"]
        second = client.post("/v1/chart", json={"birth": birth}).json()["data"]
        assert first == second

    def test_ayanamsa_changes_the_result(self, client, birth):
        """A different sidereal offset must actually move the planets."""
        lahiri = client.post("/v1/chart", json={"birth": birth}).json()["data"]
        raman = client.post(
            "/v1/chart", json={"birth": {**birth, "ayanamsa": "RAMAN"}}
        ).json()
        assert (
            raman["data"]["planets"]["SUN"]["longitude"]
            != lahiri["planets"]["SUN"]["longitude"]
        )
        assert raman["meta"]["ayanamsa"] == "RAMAN"


class TestNatalEndpoints:
    """Everything derived from the birth chart alone."""

    @pytest.mark.parametrize(
        "path",
        ["/v1/yogas-doshas", "/v1/strength", "/v1/houses", "/v1/aspects", "/v1/states"],
    )
    def test_returns_data(self, client, birth, path):
        resp = client.post(path, json={"birth": birth})
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]

    def test_divisional_navamsa(self, client, birth):
        resp = client.post("/v1/divisional", json={"birth": birth, "division": 9})
        assert resp.status_code == 200
        assert resp.json()["data"]

    def test_divisional_rejects_out_of_range(self, client, birth):
        resp = client.post("/v1/divisional", json={"birth": birth, "division": 61})
        assert resp.status_code == 422


class TestTiming:
    """Date-dependent endpoints. Every one takes its date explicitly."""

    def test_dasha_requires_as_of(self, client, birth):
        """Omitting the date must fail rather than defaulting to the clock."""
        resp = client.post("/v1/dasha", json={"birth": birth, "system": "vimsottari"})
        assert resp.status_code == 422

    @pytest.mark.parametrize(
        "system", ["vimsottari", "yogini", "ashtottari", "narayana"]
    )
    def test_all_four_dasha_systems(self, client, birth, system):
        resp = client.post(
            "/v1/dasha",
            json={"birth": birth, "system": system, "as_of": "2026-10-06T00:00:00"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()["data"]
        assert body["system"] == system
        assert body["timeline"]
        # `current` is Vimsottari-only; the others must report None rather than
        # silently returning Vimsottari periods under another system's name.
        assert (body["current"] is not None) == (system == "vimsottari")

    def test_unknown_dasha_system_is_400(self, client, birth):
        resp = client.post(
            "/v1/dasha",
            json={"birth": birth, "system": "nope", "as_of": "2026-10-06T00:00:00"},
        )
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "unknown_dasha_system"

    def test_panchanga(self, client):
        resp = client.post(
            "/v1/panchanga",
            json={
                "year": 2026, "month": 3, "day": 11,
                "latitude": 19.076, "longitude": 72.878, "timezone_offset": 5.5,
            },
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["panchanga"]

    def test_transits_with_and_without_natal(self, client, birth):
        moment = {
            "year": 2026, "month": 10, "day": 6,
            "latitude": 19.076, "longitude": 72.878, "timezone_offset": 5.5,
        }
        bare = client.post("/v1/transits", json={"moment": moment})
        assert bare.status_code == 200
        assert "natal" not in bare.json()["data"]

        overlaid = client.post("/v1/transits", json={"moment": moment, "birth": birth})
        assert overlaid.status_code == 200
        assert overlaid.json()["data"]["natal"]

    def test_sade_sati_requires_as_of(self, client, birth):
        assert client.post("/v1/sade-sati", json={"birth": birth}).status_code == 422

    def test_sade_sati(self, client, birth):
        resp = client.post(
            "/v1/sade-sati", json={"birth": birth, "as_of": "2026-10-06T00:00:00"}
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"] is not None

    def test_muhurta_day_table(self, client):
        resp = client.post(
            "/v1/muhurta",
            json={
                "year": 2026, "month": 10, "day": 6,
                "latitude": 19.076, "longitude": 72.878, "timezone_offset": 5.5,
            },
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]

    def test_varshaphal(self, client, birth):
        resp = client.post("/v1/varshaphal", json={"birth": birth, "year": 2026})
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]


class TestMatching:
    """Both traditions, because they are not interchangeable."""

    def test_ashtakoot(self, client):
        resp = client.post(
            "/v1/compatibility",
            json={
                "person1_nakshatra": "ROHINI", "person1_sign": "TAURUS",
                "person2_nakshatra": "HASTA", "person2_sign": "VIRGO",
            },
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]
        # No ayanamsa is applied by the 8-kuta method, so claiming one would
        # mislead the consumer.
        assert resp.json()["meta"]["ayanamsa"] == "N/A"

    def test_ashtakoot_accepts_lowercase(self, client):
        resp = client.post(
            "/v1/compatibility",
            json={
                "person1_nakshatra": "rohini", "person1_sign": "taurus",
                "person2_nakshatra": "hasta", "person2_sign": "virgo",
            },
        )
        assert resp.status_code == 200

    def test_ashtakoot_rejects_unknown_name(self, client):
        resp = client.post(
            "/v1/compatibility",
            json={
                "person1_nakshatra": "NOTANAKSHATRA", "person1_sign": "TAURUS",
                "person2_nakshatra": "HASTA", "person2_sign": "VIRGO",
            },
        )
        assert resp.status_code == 400
        assert "NOTANAKSHATRA" in resp.json()["detail"]["message"]

    def test_porutham(self, client, birth):
        other = {**birth, "year": 1992, "hour": 14}
        resp = client.post("/v1/porutham", json={"person1": birth, "person2": other})
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["porutham"]
        assert resp.json()["data"]["papasamyam"] is not None


class TestSystems:
    """The alternative traditions that back the consumer's personas."""

    def test_kp(self, client, birth):
        resp = client.post("/v1/kp", json={"birth": birth})
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        # KPChartResult is returned flat — it already carries everything.
        assert data["planets"] and data["cusps"]
        assert "significators" in data and "ruling_planets" in data

    def test_kp_enums_are_names_not_raw_integers(self, client, birth):
        """The engine types KP lords as plain int; the wrapper must still name them.

        Without this, a caller receives ``"sub_lord": 2`` and has no way to learn
        that means Jupiter without reproducing the engine's numbering — which is
        exactly the leak the enum-naming guarantee exists to prevent.
        """
        data = client.post("/v1/kp", json={"birth": birth}).json()["data"]
        planets = data["planets"]
        assert isinstance(planets, list), "KP returns a list, not a mapping"

        first = planets[0]
        for field in ("planet", "sign_lord", "star_lord", "sub_lord", "sub_sub_lord"):
            assert isinstance(first[field], str), (
                f"KP {field} leaked as {first[field]!r} rather than a name"
            )
        assert first["sign"] in SIGN_NAMES_KP
        assert first["planet"] == "SUN"

    def test_jaimini(self, client, birth):
        resp = client.post("/v1/jaimini", json={"birth": birth})
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["chara_karakas"]

    def test_prashna(self, client):
        resp = client.post(
            "/v1/prashna",
            json={
                "year": 2026, "month": 10, "day": 6, "hour": 14, "minute": 30,
                "latitude": 19.076, "longitude": 72.878, "timezone_offset": 5.5,
                "query_house": 10,
            },
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["verdict"] is not None

    def test_numerology(self, client):
        resp = client.post(
            "/v1/numerology",
            json={"name": "Test Name", "year": 1990, "month": 3, "day": 15},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]


class TestValidation:
    """The input contract."""

    def test_unknown_field_is_rejected(self, client, birth):
        """extra="forbid" turns a typo into a loud 422 instead of a silent default."""
        resp = client.post(
            "/v1/chart", json={"birth": {**birth, "timezoneoffset": 5.5}}
        )
        assert resp.status_code == 422

    def test_latitude_out_of_range(self, client, birth):
        resp = client.post("/v1/chart", json={"birth": {**birth, "latitude": 91.0}})
        assert resp.status_code == 422

    def test_unknown_ayanamsa_is_400(self, client, birth):
        resp = client.post("/v1/chart", json={"birth": {**birth, "ayanamsa": "BOGUS"}})
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "invalid_input"


class TestAuth:
    """Shared-secret enforcement."""

    def test_key_required_when_configured(self, monkeypatch, birth):
        """With a key configured, computational endpoints must reject anonymous calls."""
        from fastapi.testclient import TestClient

        import calc_api.config as config
        import calc_api.deps as deps

        configured = config.Settings(api_key="s3cret", host="127.0.0.1", port=8800)
        monkeypatch.setattr(deps, "settings", configured)

        from calc_api.main import app

        with TestClient(app) as c:
            assert c.post("/v1/chart", json={"birth": birth}).status_code == 401
            ok = c.post(
                "/v1/chart", json={"birth": birth}, headers={"X-API-Key": "s3cret"}
            )
            assert ok.status_code == 200
            # Probes stay open so load balancers can reach them.
            assert c.get("/healthz").status_code == 200
