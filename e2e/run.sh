#!/usr/bin/env bash
# Run the E2E tests (task 16.5). Run it in wt_dev: bash e2e/run.sh [playwright args]
# It starts the stack from zero (new WT data), builds the runner and runs it as
# wt_test_playwright on the e2e network with the host Docker socket. Then it copies the
# report and the results to e2e/ (Git ignores them).
# Footprint test (task 16.22, run by hand): FOOTPRINT=1 bash e2e/run.sh --project footprint
set -euo pipefail
cd "$(dirname "$0")"

FOOTPRINT="${FOOTPRINT:-}"
profile=()
if [ -n "$FOOTPRINT" ]; then profile=(--profile footprint); fi

# down with the profile: it also removes the footprint containers of an old run.
docker compose -f compose.test.yaml --profile footprint down --volumes --remove-orphans
docker compose -f compose.test.yaml "${profile[@]}" up -d --build --wait
docker build -q -f playwright.Dockerfile -t wt_test/playwright . > /dev/null
docker rm -f wt_test_playwright > /dev/null 2>&1 || true

status=0
docker run --name wt_test_playwright --label wt.enable=false --network wt_test_e2e_e2e \
  -e FOOTPRINT="$FOOTPRINT" -v /var/run/docker.sock:/var/run/docker.sock wt_test/playwright "$@" || status=$?

rm -rf playwright-report test-results
docker cp wt_test_playwright:/e2e/playwright-report playwright-report > /dev/null 2>&1 || true
docker cp wt_test_playwright:/e2e/test-results test-results > /dev/null 2>&1 || true
# Screenshot baselines (new ones after --update-snapshots). Git keeps them.
docker cp wt_test_playwright:/e2e/specs/checks/visual.spec.ts-snapshots specs/checks/ > /dev/null 2>&1 || true
exit "$status"
