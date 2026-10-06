"""Request dependencies — shared-secret authentication only.

This is deployment hygiene, not business logic: the service is meant to sit on
a private network reachable only by its one consumer, and the header is a
second lock on that door. There is deliberately no user concept, no session,
and no authorisation model here — those belong in the consuming application.
"""

from __future__ import annotations

from fastapi import Header, HTTPException, status

from calc_api.config import settings


async def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Reject the request unless it carries the configured shared secret.

    A no-op when ``CALC_API_KEY`` is unset, which is the local-development
    default.

    Args:
        x_api_key: Value of the ``X-API-Key`` request header, if present.

    Raises:
        HTTPException: 401 when authentication is enabled and the header is
            missing or wrong.
    """
    if not settings.auth_enabled:
        return

    # Compared with a plain != rather than a constant-time compare because the
    # secret is a deployment credential on a private network, not a user
    # password; adding hmac.compare_digest here would imply a threat model this
    # service does not have.
    if x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "Invalid or missing X-API-Key", "field": None},
        )
