#!/usr/bin/env bash
# Runs all static checks and tests. Run it in wt_dev. The pre-commit hook calls it.
set -euo pipefail
cd /workspace

echo "== backend"
(
  cd backend
  uv run ruff format --check
  uv run ruff check
  uv run pyright
  uv run pytest -q
)

echo "== frontend"
(cd frontend && pnpm test)
