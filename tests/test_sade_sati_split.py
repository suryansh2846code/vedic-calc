"""Sade Sati must be reported separately from Small Panoti and Ashtama Shani.

Background: these three Saturn-over-Moon afflictions were previously collapsed
into one ``is_active`` boolean. They are different things of different lengths,
and reporting Small Panoti as "Sade Sati" puts us in direct contradiction with
other software and with any astrologer the user asks.

See ``docs/accuracy.md``.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from vedic_calc import calculate_chart, calculate_sade_sati
from vedic_calc.chart.sade_sati import _classify
from vedic_calc.core.constants import Planet, Sign

# A date on which Saturn is in Pisces, used by the worked examples below.
SATURN_IN_PISCES = datetime(2026, 10, 6)


class TestClassify:
    """The pure sign-distance classifier."""

    @pytest.mark.parametrize(
        "distance,expected",
        [
            (12, (True, False, False)),   # 12th from Moon  — Sade Sati rising
            (1, (True, False, False)),    # same sign       — Sade Sati peak
            (2, (True, False, False)),    # 2nd from Moon   — Sade Sati setting
            (4, (False, True, False)),    # 4th from Moon   — Small Panoti
            (8, (False, False, True)),    # 8th from Moon   — Ashtama Shani
            (3, (False, False, False)),   # unafflicted
            (7, (False, False, False)),
        ],
    )
    def test_each_distance(self, distance: int, expected: tuple[bool, bool, bool]):
        """Walk every relevant sign distance from a fixed Moon sign."""
        moon = Sign.ARIES  # == 1, so sign number == distance
        saturn_sign_num = ((int(moon) - 1 + distance - 1) % 12) + 1
        assert _classify(saturn_sign_num, moon) == expected

    def test_at_most_one_affliction_at_a_time(self):
        """The three distances are mutually exclusive, for every combination."""
        for moon in Sign:
            for saturn_num in range(1, 13):
                assert sum(_classify(saturn_num, moon)) <= 1

    def test_wraparound(self):
        """Sagittarius Moon with Saturn in Capricorn is the 2nd, not the 14th."""
        assert _classify(int(Sign.CAPRICORN), Sign.SAGITTARIUS) == (True, False, False)
        # And the 12th wraps the other way: Scorpio is 12th from Sagittarius.
        assert _classify(int(Sign.SCORPIO), Sign.SAGITTARIUS) == (True, False, False)


class TestSmallPanotiIsNotSadeSati:
    """The regression this change exists to prevent."""

    def test_delhi_1992_is_small_panoti_not_sade_sati(self):
        """Moon in Sagittarius, Saturn in Pisces — the 4th, so Small Panoti.

        This chart is why the fix was needed: the old umbrella flag reported it
        as Sade Sati, disagreeing with AstrologyAPI, which was right.
        """
        # Exactly the "Delhi 1992" chart from benchmarks/accuracy.py.
        chart = calculate_chart(
            year=1992, month=1, day=5, hour=6, minute=15,
            latitude=28.614, longitude=77.209, timezone_offset=5.5,
        )
        assert chart.planets[Planet.MOON].sign is Sign.SAGITTARIUS

        result = calculate_sade_sati(chart, SATURN_IN_PISCES)

        assert result.is_sade_sati is False, "Pisces is the 4th from Sagittarius"
        assert result.is_small_panoti is True
        assert result.is_ashtama_shani is False
        assert result.current_phase == "small_panoti"
        # The umbrella still fires, for callers that want any affliction.
        assert result.is_active is True

    def test_varanasi_1988_is_ashtama_shani(self):
        """Moon in Leo, Saturn in Pisces — the 8th, so Ashtama Shani.

        The "Varanasi 1988" chart from benchmarks/accuracy.py. AstrologyAPI
        reports Sade Sati false here, and the strict flag agrees with it while
        the umbrella does not.
        """
        chart = calculate_chart(
            year=1988, month=8, day=15, hour=5, minute=0,
            latitude=25.3176, longitude=83.0068, timezone_offset=5.5,
        )
        assert chart.planets[Planet.MOON].sign is Sign.LEO

        result = calculate_sade_sati(chart, SATURN_IN_PISCES)

        assert result.is_sade_sati is False, "Pisces is the 8th from Leo"
        assert result.is_ashtama_shani is True
        assert result.is_small_panoti is False
        assert result.current_phase == "ashtama_shani"
        assert result.is_active is True

    def test_sydney_1998_is_small_panoti(self):
        """Southern-hemisphere chart: Moon in Sagittarius, so the 4th."""
        chart = calculate_chart(
            year=1998, month=9, day=1, hour=8, minute=15,
            latitude=-33.8688, longitude=151.2093, timezone_offset=10.0,
        )
        result = calculate_sade_sati(chart, SATURN_IN_PISCES)

        assert result.is_sade_sati is False
        assert result.is_small_panoti is True


class TestUmbrellaIsTheUnion:
    """``is_active`` must equal the OR of the three specific flags."""

    @pytest.mark.parametrize(
        "year,month,day,lat,lon",
        [
            (1990, 3, 15, 19.0760, 72.8777),
            (1992, 1, 5, 28.6139, 77.2090),
            (1988, 8, 15, 25.3176, 83.0068),
            (2005, 4, 10, 26.9124, 75.7873),
        ],
    )
    def test_union_holds(self, year, month, day, lat, lon):
        chart = calculate_chart(
            year=year, month=month, day=day, hour=12,
            latitude=lat, longitude=lon, timezone_offset=5.5,
        )
        for probe in (datetime(2024, 6, 1), SATURN_IN_PISCES, datetime(2028, 1, 1)):
            r = calculate_sade_sati(chart, probe)
            assert r.is_active == (
                r.is_sade_sati or r.is_small_panoti or r.is_ashtama_shani
            )
            # And a phase is reported exactly when something is active.
            assert (r.current_phase is not None) == r.is_active


class TestDeterminism:
    """The same chart and the same date must always give the same answer."""

    def test_repeatable(self):
        chart = calculate_chart(
            year=1990, month=3, day=15, hour=10, minute=30,
            latitude=19.0760, longitude=72.8777, timezone_offset=5.5,
        )
        first = calculate_sade_sati(chart, SATURN_IN_PISCES)
        second = calculate_sade_sati(chart, SATURN_IN_PISCES)
        assert first == second
