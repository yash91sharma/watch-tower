"""Test data builders. Give only the values that the test is about."""

from collections.abc import Mapping

from wt.docker.client import ContainerInfo
from wt.docker.parse import ENABLE_LABEL, PROJECT_LABEL, SOURCE_LABEL


def make_info(
    name: str = "web",
    image: str = "nginx:1",
    *,
    docker_id: str | None = None,
    labels: Mapping[str, str] | None = None,
    project: str | None = None,
    source: str | None = None,
    excluded: bool = False,
    state: str = "running",
    health: str = "none",
    tty: bool = False,
) -> ContainerInfo:
    """A container from Docker inspect. The default id is "id-<name>".

    `project`, `source` and `excluded` add the Compose project, release source and
    `wt.enable=false` labels to `labels`.
    """
    all_labels = dict(labels or {})
    if project is not None:
        all_labels[PROJECT_LABEL] = project
    if source is not None:
        all_labels[SOURCE_LABEL] = source
    if excluded:
        all_labels[ENABLE_LABEL] = "false"
    return ContainerInfo(
        docker_id or f"id-{name}", name, image, all_labels, state, health, tty
    )
