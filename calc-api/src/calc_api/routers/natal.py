"""Natal endpoints — the birth chart and what derives from it alone.

None of these read the clock: a natal chart is fixed at birth, so every result
here is cacheable forever by the consumer.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from vedic_calc import (
    analyze_houses,
    calculate_ashtakavarga,
    calculate_aspects,
    calculate_chart,
    calculate_divisional_chart,
    calculate_planet_states,
    calculate_shadbala,
    detect_doshas,
    detect_yogas,
)

from calc_api.envelope import envelope
from calc_api.models import ChartOnlyRequest, DivisionalRequest
from calc_api.serialize import to_jsonable

router = APIRouter(prefix="/v1", tags=["natal"])


@router.post("/chart")
async def chart(req: ChartOnlyRequest) -> dict[str, Any]:
    """Compute a natal (D-1 Rasi) chart.

    Returns planetary longitudes, signs, degrees within sign, nakshatras and
    padas, house occupancy, and the ascendant.

    Args:
        req: Birth moment, place, and ayanamsa.

    Returns:
        The standard envelope with the chart as ``data``.
    """
    b = req.birth
    result = calculate_chart(
        year=b.year, month=b.month, day=b.day,
        hour=b.hour, minute=b.minute, second=b.second,
        latitude=b.latitude, longitude=b.longitude,
        timezone_offset=b.timezone_offset,
        ayanamsa=b.ayanamsa_enum(),
    )
    return envelope(to_jsonable(result), b.ayanamsa.upper())


@router.post("/divisional")
async def divisional(req: DivisionalRequest) -> dict[str, Any]:
    """Compute one divisional chart (varga).

    Vargas subdivide each 30-degree sign into N parts and re-map them onto the
    zodiac, each one used to examine a different area of life — D-9 Navamsa for
    marriage and dharma, D-10 Dashamsa for career, D-7 for children.

    Args:
        req: Birth data plus the D-number (1-60).

    Returns:
        The standard envelope with the divisional chart as ``data``.
    """
    b = req.birth
    natal = _natal(req.birth)
    result = calculate_divisional_chart(natal, req.division)
    return envelope(to_jsonable(result), b.ayanamsa.upper())


@router.post("/yogas-doshas")
async def yogas_doshas(req: ChartOnlyRequest) -> dict[str, Any]:
    """Detect classical yogas and doshas in a natal chart.

    A *yoga* is a named planetary combination held to produce a specific
    effect; a *dosha* is an affliction. Both come with severity where the
    engine scores it, and doshas carry traditional remedies.

    Args:
        req: Birth data.

    Returns:
        Envelope with ``{"yogas": [...], "doshas": [...]}``.
    """
    natal = _natal(req.birth)
    return envelope(
        {
            "yogas": to_jsonable(detect_yogas(natal)),
            "doshas": to_jsonable(detect_doshas(natal)),
        },
        req.birth.ayanamsa.upper(),
    )


@router.post("/strength")
async def strength(req: ChartOnlyRequest) -> dict[str, Any]:
    """Compute planetary strength two ways.

    *Shadbala* is the six-fold strength measure, reported in rupas.
    *Ashtakavarga* is the eight-source benefic point system, which scores every
    sign from each planet's perspective.

    Args:
        req: Birth data.

    Returns:
        Envelope with ``{"shadbala": {...}, "ashtakavarga": {...}}``.
    """
    natal = _natal(req.birth)
    return envelope(
        {
            "shadbala": to_jsonable(calculate_shadbala(natal)),
            "ashtakavarga": to_jsonable(calculate_ashtakavarga(natal)),
        },
        req.birth.ayanamsa.upper(),
    )


@router.post("/houses")
async def houses(req: ChartOnlyRequest) -> dict[str, Any]:
    """Analyse each of the twelve houses.

    Per house: its lord, its occupants, the aspects it receives, and an overall
    strength assessment.

    Args:
        req: Birth data.

    Returns:
        Envelope with the per-house analysis.
    """
    natal = _natal(req.birth)
    return envelope(to_jsonable(analyze_houses(natal)), req.birth.ayanamsa.upper())


@router.post("/aspects")
async def aspects(req: ChartOnlyRequest) -> dict[str, Any]:
    """Compute Vedic aspects (drishti).

    Unlike Western aspects these are whole-sign and asymmetric: every planet
    aspects the 7th from itself, and Mars, Jupiter and Saturn have additional
    special aspects (Mars the 4th and 8th, Jupiter the 5th and 9th, Saturn the
    3rd and 10th).

    Args:
        req: Birth data.

    Returns:
        Envelope with the aspect list.
    """
    natal = _natal(req.birth)
    return envelope(to_jsonable(calculate_aspects(natal)), req.birth.ayanamsa.upper())


@router.post("/states")
async def states(req: ChartOnlyRequest) -> dict[str, Any]:
    """Compute planetary states — dignity, combustion, retrogression.

    Args:
        req: Birth data.

    Returns:
        Envelope with per-planet state.
    """
    natal = _natal(req.birth)
    return envelope(
        to_jsonable(calculate_planet_states(natal)), req.birth.ayanamsa.upper()
    )


def _natal(birth) -> Any:
    """Build the engine's ``BirthChart`` from a request's birth block.

    Most engine functions take a chart rather than raw parameters, and this
    service is stateless, so every request that needs one re-derives it. The
    consumer caches the *response*, which is why that is cheap in practice.

    Args:
        birth: A ``BirthData`` instance.

    Returns:
        A ``vedic_calc`` ``BirthChart``.
    """
    return calculate_chart(
        year=birth.year, month=birth.month, day=birth.day,
        hour=birth.hour, minute=birth.minute, second=birth.second,
        latitude=birth.latitude, longitude=birth.longitude,
        timezone_offset=birth.timezone_offset,
        ayanamsa=birth.ayanamsa_enum(),
    )
