"""Supporting calculations and chart rendering.

These are the smaller pieces the product needs around the main systems: the
Avakhada table that compatibility matching reads from, the Panchadha Maitri
relationship grid, Sahams, Upagrahas, special lagnas, and the two chart
renderers.

Grouped under ``/v1/special/`` rather than scattered, because none of them is a
system in its own right — they are details of a Parashari reading.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from vedic_calc import (
    calculate_avakhada,
    calculate_chalit_chart,
    calculate_combustion,
    calculate_functional_nature,
    calculate_planet_relationships,
    calculate_sahams,
    calculate_special_lagnas,
    calculate_sudarshana_chakra,
    calculate_upagrahas,
    get_disha_shool,
    render_north_indian,
    render_south_indian,
    render_svg,
)
from vedic_calc.core.constants import Planet

from calc_api.envelope import envelope
from calc_api.models import ChartOnlyRequest, DateOnly, RenderRequest
from calc_api.routers.natal import _natal
from calc_api.serialize import to_jsonable

router = APIRouter(prefix="/v1", tags=["special"])


@router.post("/special/relationships")
async def relationships(req: ChartOnlyRequest) -> dict[str, Any]:
    """Panchadha Maitri — the five-fold planetary friendship grid.

    Combines each pair's *natural* relationship (fixed by classical rule) with
    their *temporal* relationship (based on how many signs apart they are in
    this chart) to give a compound verdict from great friend to great enemy.

    Args:
        req: Birth data.

    Returns:
        Envelope with the relationship grid.
    """
    natal = _natal(req.birth)
    return envelope(
        to_jsonable(calculate_planet_relationships(natal)), req.birth.ayanamsa.upper()
    )


@router.post("/special/avakhada")
async def avakhada(req: ChartOnlyRequest) -> dict[str, Any]:
    """The Avakhada table — the classification compatibility matching reads from.

    Derived from the natal Moon's nakshatra, pada and sign: Varna (temperament),
    Vashya (dominance class), Yoni (animal symbol), Gana (temperament group),
    Nadi (constitutional channel) and Tatva (element). These are the inputs the
    eight-kuta method scores.

    Args:
        req: Birth data. The Moon's position is taken from the computed chart,
            so the caller does not have to extract it first.

    Returns:
        Envelope with the Avakhada classification.
    """
    natal = _natal(req.birth)
    moon = natal.planets[Planet.MOON]
    result = calculate_avakhada(
        nakshatra=moon.nakshatra_info.nakshatra,
        pada=moon.nakshatra_info.pada,
        sign=moon.sign,
    )
    return envelope(to_jsonable(result), req.birth.ayanamsa.upper())


@router.post("/special/sahams")
async def sahams(req: ChartOnlyRequest) -> dict[str, Any]:
    """The 21 Sahams — Tajika "sensitive points" derived from planetary arcs.

    Each Saham marks a point held to signify one matter: Punya (merit), Vidya
    (learning), Yasas (fame), and so on. Computed by adding and subtracting
    planetary longitudes per classical formula.

    Args:
        req: Birth data.

    Returns:
        Envelope with all Saham positions.
    """
    natal = _natal(req.birth)
    return envelope(to_jsonable(calculate_sahams(natal)), req.birth.ayanamsa.upper())


@router.post("/special/upagrahas")
async def upagrahas(req: ChartOnlyRequest) -> dict[str, Any]:
    """The Upagrahas — five shadowy sub-planets with no physical body.

    Dhuma, Vyatipata, Parivesha, Chapa and Upaketu are computed as fixed offsets
    from the Sun's longitude. They are treated as malefic points.

    Args:
        req: Birth data.

    Returns:
        Envelope with Upagraha positions.
    """
    natal = _natal(req.birth)
    return envelope(to_jsonable(calculate_upagrahas(natal)), req.birth.ayanamsa.upper())


@router.post("/special/lagnas")
async def special_lagnas(req: ChartOnlyRequest) -> dict[str, Any]:
    """Special ascendants used alongside the birth ascendant.

    Hora Lagna (wealth), Ghati Lagna (power), Bhava Lagna and Sree Lagna
    (prosperity) each advance at a different rate from sunrise and are read for
    the matter they govern.

    Args:
        req: Birth data.

    Returns:
        Envelope with each special lagna.
    """
    natal = _natal(req.birth)
    return envelope(
        to_jsonable(calculate_special_lagnas(natal)), req.birth.ayanamsa.upper()
    )


@router.post("/special/functional")
async def functional(req: ChartOnlyRequest) -> dict[str, Any]:
    """Functional benefic / malefic nature for this specific ascendant.

    A planet's *natural* nature is fixed — Jupiter benefic, Saturn malefic — but
    its *functional* nature depends on which houses it rules from the given
    ascendant. A planet ruling both a trine and an angle becomes a Yogakaraka,
    the most helpful placement in the chart. This is why the same planet is
    good for one person and difficult for another.

    Args:
        req: Birth data.

    Returns:
        Envelope with per-planet functional nature.
    """
    natal = _natal(req.birth)
    return envelope(
        to_jsonable(calculate_functional_nature(natal)), req.birth.ayanamsa.upper()
    )


@router.post("/special/chalit")
async def chalit(req: ChartOnlyRequest) -> dict[str, Any]:
    """The Chalit (Bhava Chalit) chart — planets placed by house cusp.

    The Rasi chart places planets by sign; Chalit places them by unequal house
    division, so a planet can sit in a different house in each. Where the two
    disagree, practitioners read both.

    Args:
        req: Birth data.

    Returns:
        Envelope with the Chalit chart.
    """
    natal = _natal(req.birth)
    return envelope(to_jsonable(calculate_chalit_chart(natal)), req.birth.ayanamsa.upper())


@router.post("/special/sudarshana")
async def sudarshana(req: ChartOnlyRequest) -> dict[str, Any]:
    """The Sudarshana Chakra — three charts read as one.

    Houses are counted from the ascendant, from the Moon and from the Sun
    simultaneously. A matter supported in all three is held to be strong.

    Args:
        req: Birth data.

    Returns:
        Envelope with the three-fold wheel.
    """
    natal = _natal(req.birth)
    return envelope(
        to_jsonable(calculate_sudarshana_chakra(natal)), req.birth.ayanamsa.upper()
    )


@router.post("/special/combustion")
async def combustion(req: ChartOnlyRequest) -> dict[str, Any]:
    """Combustion (Astangata) — planets too close to the Sun to act.

    A planet within a tradition-specific orb of the Sun is "burnt" and loses
    much of its power to deliver results, even when otherwise well placed.

    Args:
        req: Birth data.

    Returns:
        Envelope with per-planet combustion status.
    """
    natal = _natal(req.birth)
    return envelope(to_jsonable(calculate_combustion(natal)), req.birth.ayanamsa.upper())


@router.post("/disha-shool")
async def disha_shool(req: DateOnly) -> dict[str, Any]:
    """The inauspicious travel direction for a weekday.

    Each weekday has one direction traditionally avoided for starting a
    journey. Depends only on the date, not on place or chart.

    Args:
        req: The date.

    Returns:
        Envelope with the direction to avoid.
    """
    return envelope(
        to_jsonable(get_disha_shool(req.year, req.month, req.day)), "N/A"
    )


@router.post("/render")
async def render(req: RenderRequest) -> dict[str, Any]:
    """Render the chart as a diagram.

    Three formats. ``svg`` is what a mobile client would show; the two ASCII
    renderers are for terminals and debugging.

    The North and South Indian layouts are genuinely different conventions, not
    styling: South Indian fixes the signs in place and moves the houses, North
    Indian fixes the houses and moves the signs. Practitioners read the one they
    trained on.

    Args:
        req: Birth data, the format, and the layout style.

    Returns:
        Envelope with ``{"format", "style", "content"}``.
    """
    natal = _natal(req.birth)
    if req.format == "svg":
        content = render_svg(natal, style=req.style, city_name=req.place_name)
    elif req.style == "north":
        content = render_north_indian(natal)
    else:
        content = render_south_indian(natal)

    return envelope(
        {"format": req.format, "style": req.style, "content": content},
        req.birth.ayanamsa.upper(),
    )
