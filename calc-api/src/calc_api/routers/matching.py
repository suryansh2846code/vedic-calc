"""Compatibility endpoints — matching two people.

Two traditions, and they are not interchangeable: North India uses Ashtakoot
(eight kutas, 36 points) and South India uses Porutham (ten factors). A
consumer serving both regions should expose both rather than picking one.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from vedic_calc import (
    calculate_compatibility,
    calculate_papasamyam,
    calculate_porutham,
)

from calc_api.envelope import envelope
from calc_api.models import CompatibilityRequest, PoruthamRequest
from calc_api.routers.natal import _natal
from calc_api.serialize import to_jsonable

router = APIRouter(prefix="/v1", tags=["matching"])


@router.post("/compatibility")
async def compatibility(req: CompatibilityRequest) -> dict[str, Any]:
    """Ashtakoot Milan — North Indian 36-point matching.

    Scores eight kutas (Varna, Vashya, Tara, Yoni, Graha Maitri, Gana, Bhakoot,
    Nadi) from each person's Moon nakshatra and sign. Takes names rather than
    full birth data because that is all the classical method needs — useful,
    since many users know their nakshatra but not their birth time.

    Args:
        req: Both people's nakshatra and sign names.

    Returns:
        Envelope with per-kuta scores, the total out of 36, and a verdict.

    Raises:
        HTTPException: 400 if a nakshatra or sign name is unrecognised.
    """
    try:
        p1_nak, p1_sign, p2_nak, p2_sign = req.resolve()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "unknown_enum", "message": str(exc), "field": None},
        ) from exc

    result = calculate_compatibility(
        person1_nakshatra=p1_nak,
        person1_sign=p1_sign,
        person2_nakshatra=p2_nak,
        person2_sign=p2_sign,
    )
    # Ashtakoot works from nakshatra and sign alone, so no ayanamsa was applied
    # to reach this result — reporting one would be misleading.
    return envelope(to_jsonable(result), "N/A")


@router.post("/porutham")
async def porutham(req: PoruthamRequest) -> dict[str, Any]:
    """Porutham — South Indian ten-factor matching, from two birth charts.

    Also returns Papasamyam, the comparison of malefic affliction between the
    two charts, which South Indian practice weighs alongside the ten poruthams.

    Args:
        req: Both people's birth data.

    Returns:
        Envelope with ``{"porutham", "papasamyam"}``.
    """
    chart1 = _natal(req.person1)
    chart2 = _natal(req.person2)
    return envelope(
        {
            "porutham": to_jsonable(calculate_porutham(chart1, chart2)),
            "papasamyam": to_jsonable(calculate_papasamyam(chart1, chart2)),
        },
        req.person1.ayanamsa.upper(),
    )
