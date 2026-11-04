"""The release workflow (task 17.1): a v* tag builds the arm64 image, pushes to Docker Hub."""

import re
from pathlib import Path

REPO = Path(__file__).parents[3]
WORKFLOW = REPO / ".github" / "workflows" / "release.yml"
IMAGE = "docker.io/yash91sharma/watch-tower"


def text() -> str:
    return WORKFLOW.read_text()


def test_a_version_tag_starts_it() -> None:
    assert 'tags: ["v*"]' in text()


def test_it_builds_only_arm64_on_an_arm_runner() -> None:
    assert "runs-on: ubuntu-24.04-arm" in text()
    assert re.findall(r"platforms: (.+)", text()) == ["linux/arm64"]


def test_it_pushes_the_version_and_latest_to_docker_hub() -> None:
    assert f"{IMAGE}:${{{{ steps.version.outputs.version }}}}" in text()
    assert f"{IMAGE}:latest" in text()
    assert "push: true" in text()
    assert "ghcr.io" not in text()


def test_the_docker_hub_token_comes_from_a_secret() -> None:
    assert "password: ${{ secrets.DOCKERHUB_TOKEN }}" in text()
    assert re.findall(r"password: (.+)", text()) == ["${{ secrets.DOCKERHUB_TOKEN }}"]


def test_each_action_is_pinned_by_commit_sha() -> None:
    uses = re.findall(r"uses: (\S+)", text())

    assert uses
    for action in uses:
        assert re.fullmatch(r"[\w.-]+/[\w./-]+@[0-9a-f]{40}", action), action


def test_compose_runs_the_docker_hub_image() -> None:
    assert f"image: {IMAGE}:latest" in (REPO / "compose.yaml").read_text()
