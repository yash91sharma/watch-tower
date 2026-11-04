"""Tests for the health state machine in wt.health.state (pure)."""

from datetime import UTC, datetime, timedelta

from wt.db.models import EventKind
from wt.docker.client import ContainerInfo, DockerEvent
from wt.health.state import HealthState

T0 = datetime(2026, 1, 1, tzinfo=UTC)
N = 3
M = timedelta(minutes=10)


def event(
    action: str,
    at: timedelta = timedelta(0),
    docker_id: str = "id-1",
    health: str | None = None,
) -> DockerEvent:
    return DockerEvent(action, docker_id, "web", T0 + at, health)


def handle(state: HealthState, item: DockerEvent) -> list[EventKind]:
    return state.handle(item, N, M)


def restart_loop(state: HealthState) -> list[EventKind]:
    changes: list[EventKind] = []
    for second in range(N):
        changes += handle(state, event("die", timedelta(seconds=second * 10)))
        changes += handle(state, event("start", timedelta(seconds=second * 10 + 1)))
    return changes


def test_unhealthy_gives_became_unhealthy_once() -> None:
    state = HealthState()

    first = handle(state, event("health_status", health="unhealthy"))
    again = handle(
        state, event("health_status", timedelta(seconds=30), health="unhealthy")
    )

    assert first == [EventKind.BECAME_UNHEALTHY]
    assert again == []


def test_healthy_after_unhealthy_gives_recovered_health() -> None:
    state = HealthState()
    handle(state, event("health_status", health="unhealthy"))

    assert handle(state, event("health_status", health="healthy")) == [
        EventKind.RECOVERED_HEALTH
    ]
    assert handle(state, event("health_status", health="healthy")) == []


def test_healthy_with_no_unhealthy_gives_no_change() -> None:
    assert handle(HealthState(), event("health_status", health="healthy")) == []


def test_n_restarts_give_restart_loop_once() -> None:
    state = HealthState()

    changes = restart_loop(state)
    more = handle(state, event("die", timedelta(minutes=1))) + handle(
        state, event("start", timedelta(minutes=1, seconds=1))
    )

    assert changes == [EventKind.RESTART_LOOP]
    assert more == []


def test_tick_gives_recovered_loop_after_m_quiet_minutes() -> None:
    state = HealthState()
    restart_loop(state)
    last_start = T0 + timedelta(seconds=(N - 1) * 10 + 1)

    assert state.tick(last_start + M - timedelta(seconds=1), M) == []
    assert state.tick(last_start + M, M) == [("web", EventKind.RECOVERED_LOOP)]
    assert state.tick(last_start + 2 * M, M) == []


def test_tick_with_no_loop_gives_nothing() -> None:
    state = HealthState()
    handle(state, event("start"))

    assert state.tick(T0 + timedelta(hours=1), M) == []


def test_destroy_with_an_old_docker_id_keeps_the_state() -> None:
    state = HealthState()
    handle(state, event("health_status", health="unhealthy"))
    handle(state, event("start", docker_id="id-new"))

    assert handle(state, event("destroy", docker_id="id-1")) == []
    assert handle(
        state, event("health_status", docker_id="id-new", health="healthy")
    ) == [EventKind.RECOVERED_HEALTH]


def test_destroy_removes_the_state_with_no_change() -> None:
    state = HealthState()
    handle(state, event("health_status", health="unhealthy"))

    assert handle(state, event("destroy")) == []
    assert handle(state, event("health_status", health="healthy")) == []


def test_destroy_of_an_unknown_container_gives_no_change() -> None:
    assert handle(HealthState(), event("destroy")) == []


def test_another_action_gives_no_change() -> None:
    assert handle(HealthState(), event("pause")) == []


def info(health: str, docker_id: str = "id-1", name: str = "web") -> ContainerInfo:
    return ContainerInfo(docker_id, name, "nginx:1", {}, "running", health, False)


def test_baseline_unhealthy_gives_no_change_then_recovered_health() -> None:
    state = HealthState()

    state.baseline([info("unhealthy")])

    assert handle(state, event("health_status", health="unhealthy")) == []
    assert handle(state, event("health_status", health="healthy")) == [
        EventKind.RECOVERED_HEALTH
    ]


def test_baseline_clears_a_missed_recovery_with_no_change() -> None:
    state = HealthState()
    handle(state, event("health_status", health="unhealthy"))

    state.baseline([info("healthy")])

    assert handle(state, event("health_status", health="healthy")) == []


def test_baseline_removes_containers_that_are_gone() -> None:
    state = HealthState()
    handle(state, event("health_status", health="unhealthy"))

    state.baseline([])

    assert handle(state, event("health_status", health="healthy")) == []


def test_baseline_keeps_a_restart_loop() -> None:
    state = HealthState()
    restart_loop(state)

    state.baseline([info("healthy")])

    assert state.tick(T0 + timedelta(hours=1), M) == [("web", EventKind.RECOVERED_LOOP)]
