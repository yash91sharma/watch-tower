"""The Docker build context (.dockerignore, task 15.2): no secrets and no local deps."""

import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.docker

REPO = Path(__file__).parents[3]
_DOCKER = shutil.which("docker") or "docker"


def context_files(dest: Path) -> set[str]:
    """Copy the build context to `dest` (no base image) and give its file paths."""
    subprocess.run(
        [_DOCKER, "build", "--quiet", "-f", "-", "-o", f"type=local,dest={dest}", REPO],
        input=b"FROM scratch\nCOPY . /\n",
        check=True,
        capture_output=True,
    )
    return {path.relative_to(dest).as_posix() for path in dest.rglob("*")}


def test_the_context_has_no_secrets_and_no_local_deps(tmp_path: Path) -> None:
    secret = REPO / ".env.wt_test"
    secret.write_text("WT_GITHUB_TOKEN=not-a-real-token\n")
    try:
        files = context_files(tmp_path)
    finally:
        secret.unlink()

    def has(part: str) -> bool:
        return any(part in f"/{path}/" for path in files)

    for part in ["/.env", "/.git/", "/node_modules/", "/.venv/", "/.pnpm-store/"]:
        assert not has(part), part
    for part in ["/backend/tests/", "/e2e/", "/frontend/src/test/", ".test.ts"]:
        assert not has(part), part
    assert not [path for path in files if path.endswith((".pem", ".key"))]
    for needed in [
        "backend/pyproject.toml",
        "backend/uv.lock",
        "backend/wt/main.py",
        "frontend/package.json",
        "frontend/pnpm-lock.yaml",
        "frontend/src/main.tsx",
        "frontend/public/icon.svg",
    ]:
        assert needed in files, needed
