#!/usr/bin/env bash
# Runs all static checks and tests. Run it in wt_dev. The pre-commit hook calls it.
# Any failed check stops the script with a non-zero exit code.
set -euo pipefail
cd /workspace

echo "== backend"
(
  cd backend
  # The E2E fakes (Python) use the backend tools and config.
  uv run ruff format --check . ../e2e/fakes
  uv run ruff check . ../e2e/fakes
  uv run pyright
  # Coverage gate: see [tool.coverage] in pyproject.toml.
  uv run pytest -q --cov --cov-report=term
  # All modules: 100% of lines and branches. Not the real Docker client: the Docker
  # tests (-m docker) test it.
  echo "-- 100% gate: wt/ (not wt/docker/client.py)"
  uv run coverage report --omit="wt/docker/client.py" --fail-under=100
)

echo "== API types"
# The committed schema and TS types must match the backend. Fix: pnpm gen:api
tmp=$(mktemp -d)
(cd backend && uv run wt openapi 2>/dev/null > "$tmp/openapi.json")
(cd frontend && pnpm exec openapi-typescript "$tmp/openapi.json" -o "$tmp/schema.d.ts" > /dev/null)
if ! diff -q frontend/src/api/openapi.json "$tmp/openapi.json" > /dev/null \
  || ! diff -q frontend/src/api/schema.d.ts "$tmp/schema.d.ts" > /dev/null; then
  echo "The API types are old. Run in frontend/: pnpm gen:api"
  exit 1
fi
echo "API types are up to date"

echo "== frontend"
(
  cd frontend
  pnpm typecheck
  pnpm lint
  # Coverage gate: see test.coverage in vite.config.ts.
  pnpm test --coverage
)
