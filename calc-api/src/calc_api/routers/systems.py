"""Alternative traditions, each a self-contained analytical system.

These exist separately from ``natal`` because they are not extra detail on a
Parashari reading — they are different methods that answer differently. A
consumer that offers several astrologer personas maps each persona onto a
subset of these.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from vedic_calc import (
    calculate_arudha_padas,
    calculate_chara_karakas,
    calculate_kp_chart,
    calculate_numerology,
    cast_prashna_chart,
    detect_tajika_yogas,
    evaluate_prashna,
)

from vedic_calc.core.constants import Planet, Sign

from calc_api.envelope import envelope
from calc_api.models import ChartOnlyRequest, NumerologyRequest, PrashnaRequest
from calc_api.routers.natal import _natal
from calc_api.serialize import to_jsonable

# ─────────────────────────────────────────────────────────────────────────────
# KP integer fields that are really enums.
#
# The engine's KP types declare these as plain ``int`` with a comment saying
# "Planet enum value", rather than as ``Planet``/``Sign``. Because the values
# carry no enum type, ``to_jsonable`` cannot render them by name and they would
# reach the caller as raw Swiss Ephemeris planet ids and 1-based sign indices —
# breaking this service's documented guarantee that enums are always names.
#
# Translating here keeps that guarantee. The better long-term fix is for the
# engine to type these fields properly; that is queued as an upstream PR.
# ─────────────────────────────────────────────────────────────────────────────
KP_PLANET_FIELDS = frozenset(
    {"planet", "sign_lord", "star_lord", "sub_lord", "sub_sub_lord"}
)
KP_SIGN_FIELDS = frozenset({"sign"})


def _name_kp_enums(value: Any) -> Any:
    """Recursively rename KP integer enum fields to their symbolic names.

    Args:
        value: Already-JSON-safe KP payload from ``to_jsonable``.

    Returns:
        The same structure with planet and sign integers replaced by names.

    Example:
        >>> _name_kp_enums({"planet": 0, "sign": 12, "longitude": 330.6})
        {'planet': 'SUN', 'sign': 'PISCES', 'longitude': 330.6}
    """
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, inner in value.items():
            if key in KP_PLANET_FIELDS and isinstance(inner, int):
                out[key] = _safe_enum_name(Planet, inner)
            elif key in KP_SIGN_FIELDS and isinstance(inner, int):
                out[key] = _safe_enum_name(Sign, inner)
            else:
                out[key] = _name_kp_enums(inner)
        return out
    if isinstance(value, list):
        return [_name_kp_enums(item) for item in value]
    return value


def _safe_enum_name(enum_cls: type, raw: int) -> Any:
    """Return an enum member's name, or the original value if it is out of range.

    Falls back rather than raising: an unexpected id is a reason to return
    something a caller can see and report, not to fail the whole request.
    """
    try:
        return enum_cls(raw).name
    except ValueError:
        return raw

router = APIRouter(prefix="/v1", tags=["systems"])


@router.post("/kp")
async def kp(req: ChartOnlyRequest) -> dict[str, Any]:
    """Krishnamurti Paddhati — Placidus cusps and sublords.

    KP divides the zodiac into 249 sublord divisions and uses Placidus house
    cusps rather than whole signs. It is the most deterministic of the Indian
    systems, which is why it is the one that gives sharp yes/no answers.

    Args:
        req: Birth data.

    Returns:
        Envelope with the KP chart — planets, Placidus cusps, significators and
        ruling planets.
    """
    b = req.birth
    chart = calculate_kp_chart(
        year=b.year, month=b.month, day=b.day,
        hour=b.hour, minute=b.minute, second=b.second,
        latitude=b.latitude, longitude=b.longitude,
        timezone_offset=b.timezone_offset,
    )
    # KPChartResult already carries planets, cusps, significators and ruling
    # planets, so there is nothing to add here. The standalone
    # get_kp_significators() helper takes a BirthChart rather than a
    # KPChartResult and is for callers that have only the former.
    #
    # _name_kp_enums is required because the engine types these fields as int;
    # see the note above its definition.
    return envelope(_name_kp_enums(to_jsonable(chart)), b.ayanamsa.upper())


@router.post("/prashna")
async def prashna(req: PrashnaRequest) -> dict[str, Any]:
    """Horary astrology — cast and judge a chart for the moment of a question.

    Prashna answers a single question from the sky at the instant it was
    sincerely asked, with no reference to a birth chart. The verdict engine
    applies Tajika rules to reach a yes, no, or qualified answer.

    Args:
        req: The moment and place the question was asked, and the house it
            concerns.

    Returns:
        Envelope with ``{"chart", "tajika_yogas", "verdict"}``.
    """
    chart = cast_prashna_chart(
        year=req.year, month=req.month, day=req.day,
        hour=req.hour, minute=req.minute,
        latitude=req.latitude, longitude=req.longitude,
        timezone_offset=req.timezone_offset,
        ayanamsa=req.ayanamsa_enum(),
    )
    return envelope(
        {
            "chart": to_jsonable(chart),
            "tajika_yogas": to_jsonable(detect_tajika_yogas(chart, req.query_house)),
            "verdict": to_jsonable(evaluate_prashna(chart, req.query_house)),
        },
        req.ayanamsa.upper(),
    )


@router.post("/jaimini")
async def jaimini(req: ChartOnlyRequest) -> dict[str, Any]:
    """Jaimini system — Chara Karakas and Arudha Padas.

    The *Chara Karakas* rank the seven planets by degree to assign them roles
    (Atmakaraka is the soul's significator); *Arudha Padas* are reflected house
    positions describing how a matter appears to the world rather than how it
    is. Jaimini reads purpose and direction where Parashari reads events.

    Args:
        req: Birth data.

    Returns:
        Envelope with ``{"chara_karakas", "arudha_padas"}``.
    """
    natal = _natal(req.birth)
    return envelope(
        {
            "chara_karakas": to_jsonable(calculate_chara_karakas(natal)),
            "arudha_padas": to_jsonable(calculate_arudha_padas(natal)),
        },
        req.birth.ayanamsa.upper(),
    )


@router.post("/numerology")
async def numerology(req: NumerologyRequest) -> dict[str, Any]:
    """Chaldean numerology — psychic, destiny and name numbers.

    A separate tradition from Jyotish, included because the engine implements it
    and Indian practice often pairs the two.

    Args:
        req: Name and birth date.

    Returns:
        Envelope with the computed numbers.
    """
    result = calculate_numerology(
        name=req.name, year=req.year, month=req.month, day=req.day
    )
    return envelope(to_jsonable(result), "N/A")
