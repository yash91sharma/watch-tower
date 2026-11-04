#!/usr/bin/env bash
# Mutation test (task 16.23, nightly): mutmut on wt/versions, wt/health and wt/notify (see
# [tool.mutmut] in backend/pyproject.toml). Run it in wt_dev. It fails if the score is < 80%.
# A timeout counts as killed. See the survived mutants with: uv run mutmut results
set -euo pipefail
cd /workspace/backend

rm -rf mutants
uv run mutmut run
uv run mutmut export-cicd-stats
uv run python - <<'EOF'
import json
import sys

stats = json.load(open("mutants/mutmut-cicd-stats.json"))
score = (stats["killed"] + stats["timeout"]) / stats["total"]
print(f"Mutation score: {score:.1%} ({stats['survived']} survived of {stats['total']})")
sys.exit(0 if score >= 0.8 else 1)
EOF
