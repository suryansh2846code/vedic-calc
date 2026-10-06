"""Request models.

Two design rules are enforced here rather than left to each endpoint:

**1. No implicit "now".** Several engine functions default a date parameter to
the current clock (``calculate_sade_sati(target_date=None)``,
``get_current_dasha(date=None)``). That is convenient in a library and wrong in
a cacheable API: the same request would produce different answers on different
days, breaking both the consumer's cache and our own tests. So every date this
service needs is a **required** field.

**2. The caller owns the timezone offset.** ``timezone_offset`` is a plain
number and we trust it. Resolving it correctly from place and date — including
historical rules such as India's UTC+6:30 during 1942-45 — needs a tz database
and belongs to the consumer, which has one.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from vedic_calc.core.constants import Ayanamsa, Nakshatra, Sign

# Ayanamsa is exposed by name rather than by the engine's numeric value, which
# is a Swiss Ephemeris sidereal-mode id and an implementation detail.
# Astrologers genuinely disagree about which to use, so this must be a visible
# parameter rather than a buried default.
AYANAMSA_BY_NAME: dict[str, Ayanamsa] = {a.name: a for a in Ayanamsa}


def _ayanamsa_field() -> Any:
    """Build a fresh ayanamsa field descriptor.

    A factory rather than one shared module-level ``Field(...)``: reusing a
    single ``FieldInfo`` across several models makes them share mutable state,
    which is a subtle source of cross-model bugs in Pydantic v2.

    Returns:
        A ``Field`` descriptor defaulting to Lahiri.
    """
    return Field(
        default="LAHIRI",
        description="One of: " + ", ".join(AYANAMSA_BY_NAME),
    )


class _Base(BaseModel):
    """Shared config: reject unknown fields so typos fail loudly."""

    model_config = ConfigDict(extra="forbid")


class BirthData(_Base):
    """A birth moment and place — the input to almost every calculation.

    Attributes:
        year, month, day: Calendar date of birth in *local* time at the place
            of birth.
        hour, minute, second: Local clock time of birth.
        latitude: Degrees north, negative for south.
        longitude: Degrees east, negative for west.
        timezone_offset: Hours ahead of UTC at the birth moment, e.g. 5.5 for
            IST. Resolved by the caller — see the module docstring.
        ayanamsa: Sidereal zodiac offset to use, by name.

    Example:
        >>> BirthData(year=1990, month=3, day=15, hour=10, minute=30,
        ...           latitude=19.076, longitude=72.8777,
        ...           timezone_offset=5.5).hour
        10
    """

    year: int = Field(ge=-3000, le=3000)
    month: int = Field(ge=1, le=12)
    day: int = Field(ge=1, le=31)
    hour: int = Field(default=0, ge=0, le=23)
    minute: int = Field(default=0, ge=0, le=59)
    second: int = Field(default=0, ge=0, le=59)
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    timezone_offset: float = Field(ge=-12.0, le=14.0)
    ayanamsa: str = _ayanamsa_field()

    def ayanamsa_enum(self) -> Ayanamsa:
        """Resolve the ``ayanamsa`` name to the engine enum.

        Returns:
            The matching ``Ayanamsa`` member.

        Raises:
            ValueError: If the name is not a known ayanamsa.
        """
        try:
            return AYANAMSA_BY_NAME[self.ayanamsa.upper()]
        except KeyError as exc:
            raise ValueError(
                f"unknown ayanamsa {self.ayanamsa!r}; expected one of "
                f"{', '.join(AYANAMSA_BY_NAME)}"
            ) from exc


class DateTimePlace(_Base):
    """A dated moment at a place, for calculations that are not natal.

    Used by panchanga, muhurta, transits and prashna — anything asking "what is
    the sky doing at this time and place" rather than "what was it doing when
    this person was born".
    """

    year: int = Field(ge=-3000, le=3000)
    month: int = Field(ge=1, le=12)
    day: int = Field(ge=1, le=31)
    hour: int = Field(default=0, ge=0, le=23)
    minute: int = Field(default=0, ge=0, le=59)
    second: int = Field(default=0, ge=0, le=59)
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    timezone_offset: float = Field(ge=-12.0, le=14.0)
    ayanamsa: str = _ayanamsa_field()

    def ayanamsa_enum(self) -> Ayanamsa:
        """Resolve the ``ayanamsa`` name to the engine enum."""
        try:
            return AYANAMSA_BY_NAME[self.ayanamsa.upper()]
        except KeyError as exc:
            raise ValueError(
                f"unknown ayanamsa {self.ayanamsa!r}; expected one of "
                f"{', '.join(AYANAMSA_BY_NAME)}"
            ) from exc


class DivisionalRequest(_Base):
    """A varga (divisional chart) request.

    ``division`` is the D-number: 9 for Navamsa, 10 for Dashamsa, and so on.
    """

    birth: BirthData
    division: int = Field(ge=1, le=60, description="D-number, e.g. 9 for Navamsa")


class DashaRequest(_Base):
    """A dasha timeline request.

    ``system`` selects which of the four implemented systems to compute.
    ``as_of`` is **required**: it is the date the "current period" is reported
    for, and leaving it implicit would make the response uncacheable.
    """

    birth: BirthData
    system: str = Field(
        default="vimsottari",
        description="One of: vimsottari, yogini, ashtottari, narayana",
    )
    levels: int = Field(default=2, ge=1, le=4, description="Nesting depth")
    as_of: datetime = Field(description="Date to report the current period for")


class TransitRequest(_Base):
    """Transit positions on a given date, optionally against a natal chart."""

    moment: DateTimePlace
    birth: BirthData | None = Field(
        default=None,
        description="When given, transits are reported relative to this chart",
    )


class SadeSatiRequest(_Base):
    """Sade Sati status for a chart on a specific date.

    ``as_of`` is required for the determinism reason in the module docstring —
    the engine would otherwise read the clock.
    """

    birth: BirthData
    as_of: datetime = Field(description="Date to evaluate Saturn's transit for")


class ChandrashtamaRequest(_Base):
    """Chandrashtama days in a window.

    Chandrashtama is the period when the transiting Moon occupies the 8th sign
    from the natal Moon — traditionally an inauspicious two to three days each
    month.
    """

    birth: BirthData
    start: datetime
    end: datetime


class CompatibilityRequest(_Base):
    """Ashtakoot (North Indian, 36-point) matching from nakshatra and sign.

    Takes nakshatra and sign names directly rather than two birth charts,
    because that is what the classical 8-kuta method actually needs — and
    because many users know their nakshatra without knowing their birth time.
    """

    person1_nakshatra: str = Field(description="e.g. ROHINI")
    person1_sign: str = Field(description="e.g. TAURUS")
    person2_nakshatra: str = Field(description="e.g. HASTA")
    person2_sign: str = Field(description="e.g. VIRGO")

    def resolve(self) -> tuple[Nakshatra, Sign, Nakshatra, Sign]:
        """Resolve the four names to engine enums.

        Returns:
            ``(p1_nakshatra, p1_sign, p2_nakshatra, p2_sign)``.

        Raises:
            ValueError: If any name is not recognised.
        """
        return (
            _enum_by_name(Nakshatra, self.person1_nakshatra, "nakshatra"),
            _enum_by_name(Sign, self.person1_sign, "sign"),
            _enum_by_name(Nakshatra, self.person2_nakshatra, "nakshatra"),
            _enum_by_name(Sign, self.person2_sign, "sign"),
        )


class PoruthamRequest(_Base):
    """Porutham (South Indian, 10-factor) matching from two birth charts."""

    person1: BirthData
    person2: BirthData


class MuhurtaWindowRequest(_Base):
    """A search for auspicious windows for an activity.

    This is the constraint solver, not the daily table: it scans the range and
    returns the best-scoring windows.
    """

    activity: str = Field(description="e.g. marriage, travel, housewarming")
    start: datetime
    end: datetime
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    timezone_offset: float = Field(ge=-12.0, le=14.0)
    natal_moon_nakshatra: int = Field(default=0, ge=0, le=27)
    natal_moon_sign: int = Field(default=0, ge=0, le=12)
    max_results: int = Field(default=5, ge=1, le=50)
    ayanamsa: str = _ayanamsa_field()

    def ayanamsa_enum(self) -> Ayanamsa:
        """Resolve the ``ayanamsa`` name to the engine enum."""
        try:
            return AYANAMSA_BY_NAME[self.ayanamsa.upper()]
        except KeyError as exc:
            raise ValueError(f"unknown ayanamsa {self.ayanamsa!r}") from exc


class VarshaphalRequest(_Base):
    """A solar-return (annual) chart for one year of life."""

    birth: BirthData
    year: int = Field(ge=-3000, le=3000, description="Solar return year")


class NumerologyRequest(_Base):
    """Chaldean numerology from a name and birth date."""

    name: str = Field(min_length=1, max_length=200)
    year: int = Field(ge=-3000, le=3000)
    month: int = Field(ge=1, le=12)
    day: int = Field(ge=1, le=31)


class PrashnaRequest(DateTimePlace):
    """A horary question: the moment it was asked, plus the house it concerns.

    Prashna judgement is relative to a *query house* — the house that owns the
    subject of the question. The classical mapping: 2nd money, 4th home and
    property, 5th children, 6th illness and enemies, 7th marriage and
    partnership, 10th career, 11th gains. Without it there is nothing to judge,
    which is why the engine requires it.
    """

    query_house: int = Field(
        ge=1, le=12, description="House the question concerns, e.g. 10 for career"
    )


class DateOnly(_Base):
    """A bare calendar date, for calculations that need nothing else."""

    year: int = Field(ge=-3000, le=3000)
    month: int = Field(ge=1, le=12)
    day: int = Field(ge=1, le=31)


class RenderRequest(_Base):
    """A request to draw the chart.

    ``style`` is a tradition, not a theme: South Indian fixes the signs in place
    and moves the houses; North Indian fixes the houses and moves the signs.
    """

    birth: BirthData
    format: Literal["svg", "ascii"] = Field(default="svg")
    style: Literal["south", "north"] = Field(default="south")
    place_name: str = Field(
        default="", max_length=100, description="Optional label drawn on the SVG"
    )


class ChartOnlyRequest(_Base):
    """For endpoints that need nothing but a natal chart."""

    birth: BirthData


def _enum_by_name(enum_cls: type, raw: str, label: str):
    """Look up an engine enum member by case-insensitive name.

    Args:
        enum_cls: The enum class, e.g. ``Sign``.
        raw: The incoming name, e.g. ``"taurus"``.
        label: Human label used in the error message.

    Returns:
        The matching enum member.

    Raises:
        ValueError: If no member matches.

    Example:
        >>> from vedic_calc.core.constants import Sign
        >>> _enum_by_name(Sign, "taurus", "sign").name
        'TAURUS'
    """
    try:
        return enum_cls[raw.strip().upper()]
    except KeyError as exc:
        valid = ", ".join(m.name for m in enum_cls)
        raise ValueError(f"unknown {label} {raw!r}; expected one of {valid}") from exc
