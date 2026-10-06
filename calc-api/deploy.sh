#!/usr/bin/env bash
# Deploy calc-api to Fly.io.
#
# Run from the REPOSITORY ROOT (not from calc-api/), because the engine in
# ./src is a path dependency and must be inside the build context:
#
#     ./calc-api/deploy.sh
#
# First time only:
#     fly auth login
#     fly launch --no-deploy -c calc-api/fly.toml   # pick a unique app name
#     fly secrets set CALC_API_KEY="$(openssl rand -hex 32)" -c calc-api/fly.toml

set -euo pipefail

if [[ ! -f pyproject.toml || ! -d calc-api ]]; then
  echo "error: run from the repository root, not from calc-api/" >&2
  echo "  ./calc-api/deploy.sh" >&2
  exit 1
fi

if ! command -v fly >/dev/null 2>&1; then
  echo "error: flyctl not installed." >&2
  echo "  brew install flyctl    # or: curl -L https://fly.io/install.sh | sh" >&2
  exit 1
fi

# Never ship a build the tests reject — this service's whole value is being
# correct, and a deploy is the worst place to discover it is not.
echo "==> Running the test suite before deploying"
( cd calc-api && uv run pytest -q )

echo "==> Deploying"
fly deploy -c calc-api/fly.toml

APP="$(awk -F'"' '/^app *=/ {print $2; exit}' calc-api/fly.toml)"
echo "==> Verifying the live deployment"
./calc-api/verify_deployment.sh "https://${APP}.fly.dev"
