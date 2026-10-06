# calc-api — AGPL-3.0-or-later
#
# BUILD FROM THE REPOSITORY ROOT, not from this directory:
#
#     docker build -f calc-api/Dockerfile -t calc-api .
#
# The engine in ../src is a path dependency of this service, so both must be
# inside the build context. All COPY paths below are therefore relative to the
# repo root.
#
# Note what is *absent*: no Swiss Ephemeris data files. The engine resolves
# positions through swisseph's built-in Moshier analytic ephemeris (verified —
# calc_ut returns an iflag with SEFLG_MOSEPH set), compiled into the pyswisseph
# wheel. That keeps the image small and makes container results byte-identical
# to a local run: no 100MB+ .se1 downloads, and no risk of the container and a
# dev machine disagreeing because only one of them found a data file.

# ─── build ───────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS build

# pyswisseph builds from source on some platforms, so a compiler must exist at
# build time. Deliberately absent from the runtime stage.
RUN apt-get update && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.9.7 /uv /usr/local/bin/uv

ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /build

# Manifests first, so the dependency layer caches independently of source edits.
# The engine's own manifest is needed because calc-api resolves it by path.
COPY pyproject.toml ./
COPY calc-api/pyproject.toml calc-api/uv.lock ./calc-api/

# Sources. The engine must be importable at the path its manifest declares,
# which is why it lands at /build/src rather than somewhere tidier.
COPY src ./src
COPY README.md LICENSE NOTICE ./
COPY calc-api/src ./calc-api/src
COPY calc-api/README.md ./calc-api/

WORKDIR /build/calc-api
# --no-editable so the runtime stage needs no source tree, only /opt/venv.
RUN uv sync --frozen --no-dev --no-editable

# ─── runtime ─────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# AGPL section 13: anyone interacting with this service over a network must be
# offered its source. The running service advertises this at GET /.
LABEL org.opencontainers.image.licenses="AGPL-3.0-or-later" \
      org.opencontainers.image.source="https://github.com/suryansh2846code/vedic-calc" \
      org.opencontainers.image.title="calc-api" \
      org.opencontainers.image.description="Stateless HTTP service over the vedic_calc engine"

# This service holds no state, but it does parse untrusted JSON, so it should
# not run as root.
RUN useradd --create-home --uid 10001 calc

COPY --from=build /opt/venv /opt/venv
# NOTICE travels with the image so the licence terms ship with the binary.
COPY --from=build /build/NOTICE /build/LICENSE /usr/share/calc-api/

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER calc
EXPOSE 8800

# /healthz does not touch the engine, so it answers even while workers are busy.
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8800/healthz',timeout=2).status==200 else 1)"

# Workers, not threads: the engine is CPU-bound C code, so concurrency has to
# come from processes. Two suits a shared-cpu-1x instance; raise it with the
# instance size.
CMD ["uvicorn", "calc_api.main:app", "--host", "0.0.0.0", "--port", "8800", "--workers", "2"]
