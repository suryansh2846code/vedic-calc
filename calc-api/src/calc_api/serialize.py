"""Turn engine return values into JSON-safe structures.

The engine returns a mix of shapes:

* Pydantic models (``BirthChart``, ``PanchangaInfo``, ...)
* lists of models (``list[DashaPeriod]``)
* dicts **keyed by enum** (``dict[Planet, ShadbalaResult]``)
* bare enums, datetimes, and primitives

Only the third needs real work: ``json.dumps`` cannot use an ``IntEnum`` as an
object key, and even when it coerces one it produces ``"1"`` rather than
``"SUN"`` — useless to a consumer. So enum keys become their ``.name``.
"""

from __future__ import annotations

from datetime import date, datetime, time
from enum import Enum
from typing import Any

from pydantic import BaseModel


def to_jsonable(obj: Any) -> Any:
    """Recursively convert an engine value into JSON-serialisable data.

    Args:
        obj: Any value returned by a ``vedic_calc`` function.

    Returns:
        A structure composed only of dicts, lists, strings, numbers, bools and
        None.

    Example:
        >>> from enum import IntEnum
        >>> class Planet(IntEnum):
        ...     SUN = 1
        >>> to_jsonable({Planet.SUN: 42})
        {'SUN': 42}
    """
    # Walk Pydantic models field by field rather than calling model_dump().
    #
    # This is deliberate and load-bearing. model_dump(mode="json") serialises
    # the engine's IntEnums to their *numeric* values, so a chart comes out as
    # {"0": {"sign": 12, ...}} — those numbers are Swiss Ephemeris planet ids
    # and 1-based sign indices, i.e. engine internals. Leaking them would force
    # every consumer to hardcode the engine's numbering. Recursing on the raw
    # attribute values keeps enums as enums until the branch below renders them
    # by name, so the same chart comes out as {"SUN": {"sign": "PISCES", ...}}.
    if isinstance(obj, BaseModel):
        cls = type(obj)  # on the class, not the instance: instance access is
                         # deprecated in Pydantic 2.11
        fields = list(cls.model_fields)
        fields += list(getattr(cls, "model_computed_fields", {}) or {})
        return {name: to_jsonable(getattr(obj, name)) for name in fields}

    # Enums become their symbolic name. A consumer wants "SUN", not 1 — the
    # numeric values are an engine implementation detail (Swiss Ephemeris
    # planet ids and 1-based sign indices).
    if isinstance(obj, Enum):
        return obj.name

    if isinstance(obj, dict):
        return {_key_to_str(k): to_jsonable(v) for k, v in obj.items()}

    if isinstance(obj, (list, tuple, set, frozenset)):
        return [to_jsonable(v) for v in obj]

    if isinstance(obj, (datetime, date, time)):
        return obj.isoformat()

    # Primitives and anything already JSON-safe.
    return obj


def _key_to_str(key: Any) -> str:
    """Render a dict key as a string, preferring enum names.

    Args:
        key: A dict key from an engine return value.

    Returns:
        The key as a string — ``.name`` for enums, ``str()`` otherwise.
    """
    if isinstance(key, Enum):
        return key.name
    return str(key)
