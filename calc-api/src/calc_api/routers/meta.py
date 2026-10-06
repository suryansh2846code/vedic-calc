"""Health and version endpoints.

``/v1/version`` is not decoration: consumers put ``engine_version`` into their
cache keys so that an engine change invalidates their cached charts instead of
silently serving stale numbers.
"""

from __future__ import annotations

from typing import Any

import swisseph as swe
from fastapi import APIRouter
from vedic_calc.core.constants import Ayanamsa

from calc_api.envelope import engine_version
from calc_api.models import AYANAMSA_BY_NAME

router = APIRouter(tags=["meta"])


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    """Liveness probe.

    Returns:
        ``{"status": "ok"}`` if the process is serving.
    """
    return {"status": "ok"}


@router.get("/v1/version")
async def version() -> dict[str, Any]:
    """Report what this deployment will compute with.

    Returns:
        Engine version, Swiss Ephemeris version, the default ayanamsa, and the
        full list of supported ayanamsas.

    Example:
        >>> # GET /v1/version
        >>> # {"engine_version": "0.1.0+fork.1.a1b2c3d",
        >>> #  "ephemeris": "swisseph 2.10.03", ...}
    """
    return {
        "engine_version": engine_version(),
        "ephemeris": f"swisseph {swe.version}",
        "ayanamsa_default": Ayanamsa.LAHIRI.name,
        "ayanamsas_supported": sorted(AYANAMSA_BY_NAME),
    }
