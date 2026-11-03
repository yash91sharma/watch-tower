#!/usr/bin/env bash
# Runs all static checks and tests. Run it in wt_dev. The pre-commit hook calls it.
# Any failed check stops the script with a non-zero exit code.
set -euo pipefail
cd /workspace

echo "== backend"
(
  cd backend
  uv run ruff format --check
  uv run ruff check
  uv run pyright
  # Coverage gate: see [tool.coverage] in pyproject.toml.
  uv run pytest -q --cov --cov-report=term
  # Rule modules: 100% of lines and branches.
  for module in health versions notify; do
    echo "-- 100% gate: wt/$module"
    uv run coverage report --include="wt/$module/*" --fail-under=100
  done
)

echo "== frontend"
(
  cd frontend
  pnpm typecheck
  pnpm lint
  # Coverage gate: see test.coverage in vite.config.ts.
  pnpm test --coverage
)
