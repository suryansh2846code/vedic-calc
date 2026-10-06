#!/usr/bin/env bash
# Verify a deployed calc-api actually behaves like the local one.
#
#     ./calc-api/verify_deployment.sh https://my-calc-api.fly.dev [API_KEY]
#
# Checks four things that matter and that a plain "is it up" probe would miss:
#   1. health and version respond
#   2. the AGPL section 13 source offer is advertised
#   3. a real chart computes, with enums serialised as NAMES not numbers
#   4. the same request twice is byte-identical  (the consumer cache depends
#      on this, and a multi-worker deployment is exactly where a hidden
#      nondeterminism would first show up)

set -euo pipefail

BASE="${1:?usage: verify_deployment.sh <base-url> [api-key]}"
KEY="${2:-${CALC_API_KEY:-}}"
BASE="${BASE%/}"

# Expanded via ${AUTH[@]+...} below: under `set -u`, bash 3.2 (which macOS
# ships) treats "${empty_array[@]}" as an unbound variable and aborts.
AUTH=()
[[ -n "$KEY" ]] && AUTH=(-H "X-API-Key: ${KEY}")

pass() { printf '  \033[32mok\033[0m   %s\n' "$1"; }
fail() { printf '  \033[31mFAIL\033[0m %s\n' "$1"; exit 1; }

echo "Verifying ${BASE}"

# 1 ── health and version
curl -fsS "${BASE}/healthz" | grep -q '"ok"' || fail "/healthz"
pass "/healthz"

VERSION_JSON="$(curl -fsS "${BASE}/v1/version")" || fail "/v1/version"
ENGINE="$(printf '%s' "$VERSION_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin)["engine_version"])')"
[[ "$ENGINE" == 0.1.0+fork.* ]] || fail "unexpected engine_version: ${ENGINE}"
pass "/v1/version reports ${ENGINE}"

# 2 ── AGPL section 13: the source offer must be reachable
curl -fsS "${BASE}/" | grep -q 'github.com' || fail "GET / does not advertise source (AGPL s13)"
pass "source offer advertised (AGPL s13)"

# 3 and 4 ── a real chart, twice
BODY='{"birth":{"year":1990,"month":3,"day":15,"hour":10,"minute":30,
        "latitude":19.076,"longitude":72.878,"timezone_offset":5.5}}'

A="$(curl -fsS ${AUTH[@]+"${AUTH[@]}"} -H 'Content-Type: application/json' -d "$BODY" "${BASE}/v1/chart")" \
  || fail "/v1/chart (is CALC_API_KEY set and passed?)"
B="$(curl -fsS ${AUTH[@]+"${AUTH[@]}"} -H 'Content-Type: application/json' -d "$BODY" "${BASE}/v1/chart")"

python3 - "$A" "$B" <<'PY' || exit 1
import json, sys

a, b = json.loads(sys.argv[1]), json.loads(sys.argv[2])

moon = a["data"]["planets"]["MOON"]
# Mumbai, 15 March 1990, 10:30 IST — the reference chart. Moon in Libra, Swati.
assert moon["sign"] == "LIBRA", f'expected Moon in LIBRA, got {moon["sign"]!r}'
assert moon["nakshatra_info"]["nakshatra"] == "SWATI", moon["nakshatra_info"]
# Enums must be names. A bare integer here means the serialiser was bypassed
# and Swiss Ephemeris internals reached the public contract.
assert isinstance(moon["sign"], str), "sign serialised as a number, not a name"

# Determinism across requests — which, on a multi-worker deployment, also means
# across worker processes.
assert json.dumps(a["data"], sort_keys=True) == json.dumps(b["data"], sort_keys=True), \
    "two identical requests returned different data"
print("  \033[32mok\033[0m   /v1/chart correct (Moon in Libra, Swati) and deterministic")
PY

printf '\n\033[32mDeployment verified.\033[0m %s\n\n' "${BASE}"
