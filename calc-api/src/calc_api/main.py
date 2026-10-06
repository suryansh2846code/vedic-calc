"""FastAPI application for calc-api.

Run locally::

    uv sync --extra dev
    uv run uvicorn calc_api.main:app --reload --port 8800

Then open http://127.0.0.1:8800/docs

Note what is deliberately absent: there is no CORS middleware opening this to
browsers, no user model, and no persistence. This service is reached by one
server-side consumer over a private network, not by end users. See
``../README.md`` for why that restraint is a licence matter and not only an
architectural preference.
"""

from __future__ import annotations

from typing import Any

from fastapi import Depends, FastAPI, Request, status
from fastapi.responses import JSONResponse

from calc_api import __version__
from calc_api.deps import require_api_key
from calc_api.routers import matching, meta, natal, special, systems, timing

app = FastAPI(
    title="calc-api",
    version=__version__,
    description=(
        "Thin stateless HTTP service over the vedic_calc engine. "
        "AGPL-3.0-or-later. Source: "
        "https://github.com/suryansh2846code/vedic-calc"
    ),
)

# Health and version are unauthenticated so that load balancers and deploy
# tooling can probe them. Everything that computes requires the shared secret.
app.include_router(meta.router)
for computational_router in (
    natal.router,
    timing.router,
    matching.router,
    systems.router,
    special.router,
):
    app.include_router(computational_router, dependencies=[Depends(require_api_key)])


@app.exception_handler(ValueError)
async def value_error_handler(_request: Request, exc: ValueError) -> JSONResponse:
    """Turn engine and validation ``ValueError``s into structured 400s.

    The engine raises ``ValueError`` for inputs it cannot interpret — an unknown
    ayanamsa name, an impossible date. Those are the caller's mistake, so they
    get a 400 with the message rather than a 500.

    Args:
        _request: Unused.
        exc: The raised error.

    Returns:
        A 400 JSON response in the standard error shape.
    """
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error": {"code": "invalid_input", "message": str(exc), "field": None}},
    )


@app.get("/")
async def root() -> dict[str, Any]:
    """Point callers at the docs and at the source, as AGPL section 13 requires.

    Returns:
        Service identity, the docs path, and the source URL.
    """
    return {
        "service": "calc-api",
        "version": __version__,
        "licence": "AGPL-3.0-or-later",
        "source": "https://github.com/suryansh2846code/vedic-calc",
        "docs": "/docs",
    }
