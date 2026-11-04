#!/usr/bin/env bash
# One CI job (task 17.1): run it in the dev image. See .github/workflows/pr.yml.
#   ci.sh <job>
# The backend test jobs show each test kind as its own check. The "coverage" job runs all
# backend tests once more for the coverage gates (check.sh backend).
set -euo pipefail
cd /workspace

pytest_in_backend() {
  (cd backend && uv run pytest -q "$@")
}

case "${1:-}" in
  static | frontend) bash .devcontainer/check.sh "$1" ;;
  coverage) bash .devcontainer/check.sh backend ;;
  unit) pytest_in_backend tests/unit -m "not hypothesis and not docker and not e2e and not llm_eval" ;;
  property) pytest_in_backend -m hypothesis ;;
  integration) pytest_in_backend tests/integration ;;
  migration) pytest_in_backend tests/unit/db/test_migrate.py tests/unit/db/test_dumps.py ;;
  contract) pytest_in_backend tests/contract ;;
  auth)
    pytest_in_backend tests/unit/auth tests/integration/test_reset_admin.py \
      tests/integration/api/test_auth_{guard,login,logout,setup}.py
    ;;
  # Docker tests share the test containers: one at a time (-n0).
  docker) pytest_in_backend -m docker -n0 --ignore=tests/docker/test_image.py ;;
  image) pytest_in_backend -m docker -n0 tests/docker/test_image.py ;;
  # E2E: flows, then accessibility, visual and PWA checks on all browser projects.
  e2e) bash e2e/run.sh ;;
  dependencies)
    # --skip-editable: wt itself is not on PyPI.
    (cd backend && uv run pip-audit --skip-editable)
    (cd frontend && pnpm audit --audit-level high)
    (cd e2e && pnpm audit --audit-level high)
    ;;
  # Nightly jobs (.github/workflows/nightly.yml, task 17.2).
  mutation) bash .devcontainer/mutation.sh ;;
  footprint) FOOTPRINT=1 bash e2e/run.sh --project footprint ;;
  schemathesis-long) (cd backend && WT_SCHEMATHESIS_EXAMPLES=500 uv run pytest -q tests/contract) ;;
  llm-eval)
    # Ollama with a small model, on the test network (this container joins it).
    docker network create wt_test_net > /dev/null 2>&1 || true
    docker network connect wt_test_net "$(hostname)" > /dev/null 2>&1 || true
    docker rm -f wt_test_ollama > /dev/null 2>&1 || true
    docker run -d --name wt_test_ollama --label wt.enable=false --network wt_test_net \
      ollama/ollama:0.9.6 > /dev/null
    until docker exec wt_test_ollama ollama list > /dev/null 2>&1; do sleep 1; done
    docker exec wt_test_ollama ollama pull qwen2.5:3b
    (cd backend && WT_EVAL_LLM_URL=http://wt_test_ollama:11434 uv run pytest -q -n0 -m llm_eval)
    ;;
  *)
    echo "Unknown job: ${1:-} (see the case list in this script)"
    exit 2
    ;;
esac
