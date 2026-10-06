"""Service configuration, read from the environment.

Deliberately tiny. This service has no database, no provider credentials, and
no product settings — only how to bind and an optional shared secret.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Immutable service settings.

    Attributes:
        api_key: Shared secret expected in the ``X-API-Key`` header. When empty,
            authentication is disabled — intended for local development only.
        host: Bind address.
        port: Bind port.
    """

    api_key: str
    host: str
    port: int

    @property
    def auth_enabled(self) -> bool:
        """Whether requests must carry a valid ``X-API-Key`` header."""
        return bool(self.api_key)


def load_settings() -> Settings:
    """Read settings from the process environment.

    Returns:
        A frozen ``Settings`` instance.

    Example:
        >>> import os
        >>> os.environ["CALC_API_PORT"] = "9000"
        >>> load_settings().port
        9000
    """
    return Settings(
        api_key=os.environ.get("CALC_API_KEY", ""),
        host=os.environ.get("CALC_API_HOST", "127.0.0.1"),
        port=int(os.environ.get("CALC_API_PORT", "8800")),
    )


settings = load_settings()
