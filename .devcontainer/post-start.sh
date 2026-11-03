#!/usr/bin/env bash
# Runs on each container start. Fixes permissions, then syncs deps from the lock files.
# The sync is fast when the lock files did not change. Run it again after a pull.
set -euo pipefail
cd /workspace

# New volumes belong to root. Give them to the dev user.
sudo chown dev:dev backend/.venv frontend/node_modules /home/dev/.cache/uv /home/dev/.local/share/pnpm

# The host socket belongs to root. Give it to the docker group.
if [ -S /var/run/docker.sock ]; then
  sudo chgrp docker /var/run/docker.sock
fi

# Use the repo hooks (pre-commit runs check.sh).
git config core.hooksPath .githooks

if [ -f backend/pyproject.toml ]; then
  (cd backend && uv sync)
fi

if [ -f frontend/package.json ]; then
  (cd frontend && pnpm install --config.confirmModulesPurge=false)
fi
