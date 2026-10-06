"""Timing endpoints — anything that depends on a date.

Every endpoint here takes its date **explicitly**. Several engine functions
would default to the current clock; accepting that would make responses
uncacheable and tests irreproducible. See ``calc_api.models``.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from vedic_calc import (
    calculate_ashtottari_dasha,
    calculate_chandrashtama,
    calculate_dasha,
    calculate_muhurta,
    calculate_narayana_dasha,
    calculate_panchanga,
    calculate_sade_sati,
    calculate_transit_chart,
    calculate_varshaphal,
    calculate_yogini_dasha,
    find_muhurta_windows,
    get_current_dasha,
    get_festivals,
)

from calc_api.envelope import envelope
from calc_api.models import (
    ChandrashtamaRequest,
    DashaRequest,
    DateTimePlace,
    MuhurtaWindowRequest,
    SadeSatiRequest,
    TransitRequest,
    VarshaphalRequest,
)
from calc_api.routers.natal import _natal
from calc_api.serialize import to_jsonable

router = APIRouter(prefix="/v1", tags=["timing"])

# The four dasha systems the engine implements. Each divides a life into
# planetary periods, but they use different period lengths and starting rules,
# so they genuinely disagree — which is why the caller picks one.
DASHA_SYSTEMS = {
    "vimsottari": calculate_dasha,
    "yogini": calculate_yogini_dasha,
    "ashtottari": calculate_ashtottari_dasha,
    "narayana": calculate_narayana_dasha,
}


@router.post("/dasha")
async def dasha(req: DashaRequest) -> dict[str, Any]:
    """Compute a dasha timeline and the period current as of a given date.

    A *dasha* is a planetary period: the chart is divided into spans ruled by
    successive planets, and the ruling planet colours that stretch of life.
    Vimsottari (120-year cycle, keyed to the natal Moon's nakshatra) is the
    standard; the other three are used alongside it.

    Args:
        req: Birth data, system name, nesting depth, and the ``as_of`` date the
            current period is reported for.

    Returns:
        Envelope with ``{"system", "timeline", "current"}``.

    Raises:
        HTTPException: 400 if the system name is unknown.
    """
    system = req.system.strip().lower()
    if system not in DASHA_SYSTEMS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "unknown_dasha_system",
                "message": f"expected one of {', '.join(DASHA_SYSTEMS)}",
                "field": "system",
            },
        )

    natal = _natal(req.birth)
    compute = DASHA_SYSTEMS[system]

    # Only Vimsottari takes a `levels` depth; the others have a fixed shape.
    timeline = compute(natal, req.levels) if system == "vimsottari" else compute(natal)

    return envelope(
        {
            "system": system,
            "timeline": to_jsonable(timeline),
            # get_current_dasha is Vimsottari-specific in the engine, so it is
            # reported only for that system rather than silently returning
            # Vimsottari periods under another system's name.
            "current": to_jsonable(get_current_dasha(natal, req.as_of))
            if system == "vimsottari"
            else None,
        },
        req.birth.ayanamsa.upper(),
    )


@router.post("/transits")
async def transits(req: TransitRequest) -> dict[str, Any]:
    """Compute planetary positions on a date, optionally against a natal chart.

    This is the input to the consumer's proactive-insight layer: comparing
    transiting positions to natal ones is what identifies dated events.

    Args:
        req: The moment and place, and optionally the natal chart to overlay.

    Returns:
        Envelope with the transit chart, and the natal chart when one was given.
    """
    m = req.moment
    transit = calculate_transit_chart(
        year=m.year, month=m.month, day=m.day,
        hour=m.hour, minute=m.minute, second=m.second,
        latitude=m.latitude, longitude=m.longitude,
        timezone_offset=m.timezone_offset,
        ayanamsa=m.ayanamsa_enum(),
    )
    payload: dict[str, Any] = {"transit": to_jsonable(transit)}
    if req.birth is not None:
        payload["natal"] = to_jsonable(_natal(req.birth))
    return envelope(payload, m.ayanamsa.upper())


@router.post("/panchanga")
async def panchanga(req: DateTimePlace) -> dict[str, Any]:
    """Compute the daily Vedic calendar for a date and place.

    The *panchanga* ("five limbs") is tithi (lunar day), nakshatra, yoga,
    karana and vara (weekday), plus sunrise and sunset. Festivals falling on
    the date are included.

    Args:
        req: Date, place, and ayanamsa.

    Returns:
        Envelope with ``{"panchanga", "festivals"}``.
    """
    result = calculate_panchanga(
        year=req.year, month=req.month, day=req.day,
        latitude=req.latitude, longitude=req.longitude,
        timezone_offset=req.timezone_offset,
        ayanamsa=req.ayanamsa_enum(),
        hour=req.hour, minute=req.minute,
    )
    return envelope(
        {
            "panchanga": to_jsonable(result),
            "festivals": to_jsonable(get_festivals(req.year, req.month, req.day)),
        },
        req.ayanamsa.upper(),
    )


@router.post("/muhurta")
async def muhurta(req: DateTimePlace) -> dict[str, Any]:
    """Compute the day's auspicious and inauspicious time divisions.

    Rahu Kalam and Yamaganda are to be avoided; Abhijit is the most auspicious
    window of the day; Choghadiya divides day and night into eight segments
    each with a quality.

    Args:
        req: Date and place.

    Returns:
        Envelope with the day's muhurta table.
    """
    result = calculate_muhurta(
        year=req.year, month=req.month, day=req.day,
        latitude=req.latitude, longitude=req.longitude,
        timezone_offset=req.timezone_offset,
    )
    return envelope(to_jsonable(result), req.ayanamsa.upper())


@router.post("/muhurta/search")
async def muhurta_search(req: MuhurtaWindowRequest) -> dict[str, Any]:
    """Search a date range for auspicious windows for an activity.

    The constraint solver, as opposed to ``/muhurta``'s daily table: it scans
    the range, scores candidate windows against the activity's traditional
    requirements, and returns the best.

    Args:
        req: Activity, range, place, optional natal Moon, and result count.

    Returns:
        Envelope with the ranked windows.
    """
    result = find_muhurta_windows(
        activity=req.activity,
        start_date=req.start,
        end_date=req.end,
        latitude=req.latitude,
        longitude=req.longitude,
        timezone_offset=req.timezone_offset,
        natal_moon_nakshatra=req.natal_moon_nakshatra,
        natal_moon_sign=req.natal_moon_sign,
        max_results=req.max_results,
        ayanamsa=req.ayanamsa_enum(),
    )
    return envelope(to_jsonable(result), req.ayanamsa.upper())


@router.post("/sade-sati")
async def sade_sati(req: SadeSatiRequest) -> dict[str, Any]:
    """Report Saturn's transit relative to the natal Moon on a given date.

    The three Saturn-over-Moon afflictions are reported as **separate flags**,
    because they are distinct and of different lengths:

    * ``is_sade_sati`` — Saturn in the 12th, 1st or 2nd from the natal Moon.
      Roughly 7.5 years. This is what "Sade Sati" means.
    * ``is_small_panoti`` — Saturn in the 4th (Kantaka Shani). ~2.5 years.
    * ``is_ashtama_shani`` — Saturn in the 8th. ~2.5 years.
    * ``is_active`` — the umbrella: true if any of the three applies.

    Present the specific flags, not the umbrella. Telling a user they are in
    Sade Sati when Saturn is in their 4th will be contradicted by every other
    app they check. Reference APIs differ here too: AstrologyAPI reports the
    strict reading, Prokerala the umbrella.

    Args:
        req: Birth data and the date to evaluate.

    Returns:
        Envelope with the Sade Sati assessment.
    """
    natal = _natal(req.birth)
    result = calculate_sade_sati(natal, req.as_of, req.birth.ayanamsa_enum())
    return envelope(to_jsonable(result), req.birth.ayanamsa.upper())


@router.post("/chandrashtama")
async def chandrashtama(req: ChandrashtamaRequest) -> dict[str, Any]:
    """Find Chandrashtama days in a window.

    Chandrashtama is when the transiting Moon occupies the 8th sign from the
    natal Moon — two to three days each month, traditionally avoided for new
    undertakings.

    Args:
        req: Birth data and the date range.

    Returns:
        Envelope with the dated occurrences.
    """
    natal = _natal(req.birth)
    moon_sign = natal.planets[_moon_key(natal)].sign
    result = calculate_chandrashtama(
        natal_moon_sign=moon_sign,
        start_date=req.start,
        end_date=req.end,
        latitude=req.birth.latitude,
        longitude=req.birth.longitude,
        timezone_offset=req.birth.timezone_offset,
        ayanamsa=req.birth.ayanamsa_enum(),
    )
    return envelope(to_jsonable(result), req.birth.ayanamsa.upper())


@router.post("/varshaphal")
async def varshaphal(req: VarshaphalRequest) -> dict[str, Any]:
    """Compute the solar-return (annual) chart for one year of life.

    Cast for the moment the Sun returns to its exact natal longitude, this is
    the Tajika system's year-ahead reading, including the Muntha and the year's
    annual yogas.

    Args:
        req: Birth data and the solar-return year.

    Returns:
        Envelope with the annual chart.
    """
    natal = _natal(req.birth)
    result = calculate_varshaphal(natal, req.year)
    return envelope(to_jsonable(result), req.birth.ayanamsa.upper())


def _moon_key(natal: Any) -> Any:
    """Return the ``Planet.MOON`` key for a chart's planet mapping.

    Imported lazily so this module's import list stays about endpoints rather
    than enums.

    Args:
        natal: A ``BirthChart``.

    Returns:
        The ``Planet.MOON`` enum member.
    """
    from vedic_calc.core.constants import Planet

    return Planet.MOON
