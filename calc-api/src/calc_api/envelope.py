"""The response envelope and the engine version string.

Every endpoint returns::

    {"data": ..., "meta": {"engine_version", "ayanamsa", "computed_at"}}

``meta.engine_version`` is load-bearing. Consumers include it in their cache
keys, so an engine change invalidates their cached results automatically
instead of silently serving stale numbers. **Never change engine behaviour
without bumping it.**
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

from calc_api import __version__ as _api_version

# Bump this by hand whenever a change to the engine or to this service alters
# any computed output. The git commit below disambiguates builds, but a
# deliberate marker is what consumers key their caches on.
# Revision 3: KP planet and sign fields are now rendered as names rather than
# raw integers, so the "enums are always names" guarantee holds there too.
# Revision 2: SadeSatiResult gained is_sade_sati / is_small_panoti /
# is_ashtama_shani, and DoshaResult gained convention / basis.
# Each changes response payloads, so consumer caches must invalidate.
ENGINE_REVISION = 3


@lru_cache(maxsize=1)
def engine_version() -> str:
    """Return the version string that identifies this engine build.

    Shaped as ``<api version>+fork.<revision>.<short commit>``, e.g.
    ``0.1.0+fork.1.a1b2c3d``. The commit is omitted when git is unavailable,
    which is the case in some container builds.

    Returns:
        A stable identifier for the computational behaviour of this deployment.

    Example:
        >>> engine_version().startswith("0.1.0+fork.")
        True
    """
    base = f"{_api_version}+fork.{ENGINE_REVISION}"
    commit = _git_short_sha()
    return f"{base}.{commit}" if commit else base


@lru_cache(maxsize=1)
def _git_short_sha() -> str | None:
    """Best-effort short commit SHA of the working tree.

    Returns:
        The short SHA, or None when git is not available or this is not a
        repository.
    """
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    sha = out.stdout.strip()
    return sha or None


def envelope(data: Any, ayanamsa: str) -> dict[str, Any]:
    """Wrap a computed payload in the standard response envelope.

    Args:
        data: Already-JSON-safe payload (see ``serialize.to_jsonable``).
        ayanamsa: Name of the ayanamsa used, e.g. ``"LAHIRI"``.

    Returns:
        The full response body.

    Example:
        >>> body = envelope({"ok": True}, "LAHIRI")
        >>> body["meta"]["ayanamsa"]
        'LAHIRI'
    """
    return {
        "data": data,
        "meta": {
            "engine_version": engine_version(),
            "ayanamsa": ayanamsa,
            # computed_at is metadata about the response, never an input to a
            # computation — every endpoint takes the dates it needs explicitly
            # so results stay reproducible.
            "computed_at": datetime.now(timezone.utc).isoformat(),
        },
    }
