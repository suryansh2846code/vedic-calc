"""calc-api — a thin, stateless HTTP service over the ``vedic_calc`` engine.

This package exists for one reason: so that applications can use the engine
*without linking against it*, communicating over a documented network protocol
instead. See ``../NOTICE`` and ``../README.md`` for why that distinction
matters.

It is deliberately generic. No authentication logic beyond a shared secret, no
authorisation, no billing, no business rules, no prompts, no interpretation —
it exposes the engine's public functions and nothing else.
"""

__version__ = "0.1.0"
