# calc-api

A thin, stateless HTTP service over the `vedic_calc` engine. Birth data in,
chart JSON out.

**Licence: AGPL-3.0-or-later**, same as the engine it wraps. See `../NOTICE`.

## What this is, and what it deliberately is not

This service exists so that applications can use the engine *without linking
against it*, communicating instead over a documented network protocol.

It is therefore kept **generic and boring on purpose**:

- Stateless. No database, no sessions, no user concept.
- No authentication logic beyond a shared secret, no authorisation, no billing.
- No business rules, no prompts, no content, no interpretation.
- No secrets other than the shared API key.

It exposes the engine's public functions and nothing more — the kind of wrapper
anyone could have written. Product logic belongs in the consuming application,
not here. Adding product logic to this service would be a mistake with licence
consequences as well as architectural ones.

## Running

```bash
uv sync --extra api
uv run uvicorn calc_api.main:app --reload --port 8800
```

Then `http://127.0.0.1:8800/docs` for the OpenAPI UI.

Configuration via environment (see `.env.example`):

| Variable | Default | Meaning |
|----------|---------|---------|
| `CALC_API_KEY` | _(unset)_ | Shared secret required in `X-API-Key`. If unset, auth is disabled — local development only. |
| `CALC_API_HOST` | `127.0.0.1` | Bind address |
| `CALC_API_PORT` | `8800` | Bind port |

## Contract

Every endpoint is `POST /v1/<name>` with a JSON body and returns:

```json
{
  "data": { ... },
  "meta": {
    "engine_version": "0.1.0+fork.1",
    "ayanamsa": "lahiri",
    "computed_at": "2026-10-06T12:00:00Z"
  }
}
```

Three rules the consumer depends on:

1. **Deterministic.** Same input and same `engine_version` produce identical
   `data`. No clock reads anywhere in the computation path — endpoints whose
   semantics need a date take that date as an explicit parameter. This is what
   makes caching safe and tests reproducible.
2. **`meta.engine_version` is load-bearing.** Consumers include it in their
   cache keys so an engine change invalidates cached results automatically.
   Never change engine behaviour without bumping it.
3. **Timezone offsets are resolved by the caller.** This service takes
   `timezone_offset` as a number and trusts it. Resolving it correctly from
   place and date — including historical rules such as India's +6:30 during
   1942–45 — is the caller's responsibility, because it needs a tz database
   and this service stays dependency-light.

Errors return `{"error": {"code", "message", "field"}}`, 4xx for bad input and
5xx only for genuine faults.

### Enum values are names, not numbers

The engine's `Planet`, `Sign` and `Nakshatra` are `IntEnum`s whose values are
Swiss Ephemeris planet ids and 1-based sign indices — engine internals. Calling
Pydantic's `model_dump()` would emit those raw numbers, so a chart would arrive
as `{"0": {"sign": 12}}` and every consumer would have to hardcode the engine's
numbering.

`calc_api.serialize.to_jsonable` therefore walks models field by field and
renders enums by `.name`, so a chart arrives as
`{"SUN": {"sign": "PISCES", ...}}`. Do not replace it with `model_dump()`.

### Known engine quirks the consumer should handle

* **`ascendant.planet` reads `"SUN"`.** The engine models the ascendant with the
  same `PlanetPosition` type it uses for planets, and the `planet` field is left
  at its default. The ascendant is of course not the Sun — read `longitude`,
  `sign`, `degree_in_sign` and `nakshatra_info`, and ignore `planet`.
* **Sade Sati is over-reported.** `/v1/sade-sati` currently returns true for
  Small Panoti (Saturn in the 4th from the natal Moon) and Ashtama Shani (the
  8th) as well as Sade Sati proper (the 12th, 1st and 2nd). These are distinct
  afflictions and most other software reports them separately. Present them
  distinctly, or wait for the fix tracked in `../docs/accuracy.md`.

## Tests

```bash
cd calc-api && uv run pytest -q
```

389 tests. The bulk is a sweep of **every endpoint across all ten benchmark
charts** from `../benchmarks/accuracy.py` — chosen for spread: southern
hemisphere, negative UTC offsets, a near-midnight birth, UTC+0. Each combination
asserts a 200 with non-empty data, determinism across repeat requests, and that
no raw enum value leaked.

`test_all_charts.py::test_every_endpoint_is_covered` compares the swept paths
against the app's own route table, so a new endpoint cannot be added without
being covered.

## Deploying

Stateless, so there is nothing to migrate and scaling out is just more machines.

```bash
# from the REPOSITORY ROOT, not calc-api/ —
# the engine in ./src is a path dependency and must be in the build context

fly auth login
fly launch --no-deploy -c calc-api/fly.toml          # pick a unique app name
fly secrets set CALC_API_KEY="$(openssl rand -hex 32)" -c calc-api/fly.toml
./calc-api/deploy.sh                                  # tests, deploy, verify
```

`deploy.sh` refuses to ship a build the tests reject, then runs
`verify_deployment.sh` against the live URL. You can point that at anything:

```bash
./calc-api/verify_deployment.sh https://your-app.fly.dev "$CALC_API_KEY"
```

It checks four things a plain uptime probe would miss: the version endpoint
reports a fork build, the AGPL section 13 source offer is advertised, a known
chart computes correctly with enums as names, and two identical requests are
byte-identical — which on a multi-worker deployment also means identical
*across worker processes*.

### No ephemeris data files

The image ships none, and does not need any. Positions resolve through
swisseph's built-in Moshier analytic ephemeris, compiled into the pyswisseph
wheel — `calc_ut` returns an iflag with `SEFLG_MOSEPH` set. Accuracy is far
finer than any astrological distinction (a nakshatra pada boundary is 50
arcminutes), and the benchmark agrees with two commercial reference APIs on
1015/1015 checks, which settles it empirically.

The practical consequences: a small image, no 100MB+ download at build time,
and no risk of the container and a dev machine disagreeing because only one of
them found a data file. CI asserts the container uses the same ephemeris and
reproduces host longitudes to 0.001°.

### Deployment notes

| Concern | Choice | Why |
|---|---|---|
| Workers | 2 processes | The engine is CPU-bound C, so concurrency must come from processes, not threads. Raise with the instance size. |
| Scale to zero | enabled | Stateless and deterministic, so a cold start costs latency, never correctness. |
| Concurrency limit | soft 20 / hard 40 | Past this, latency degrades faster than throughput improves. |
| Region | `bom` (Mumbai) | Closest to the launch market. |
| Auth | `CALC_API_KEY` secret | Plus network restriction to the one consumer. `/healthz` and `/v1/version` stay open for probes. |
| User | uid 10001, non-root | No state to protect, but it parses untrusted JSON. |
