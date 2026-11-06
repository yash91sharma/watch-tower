"""Tests for the env vars in wt.config."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from wt.config import Env

ENV_NAMES = [
    "DOCKER_HOST",
    "WT_DATA_DIR",
    "WT_TRUSTED_PROXIES",
    "WT_LOG_LEVEL",
    "WT_GITHUB_API_URL",
    "WT_GITHUB_TOKEN",
    "WT_NTFY_TOKEN",
    "WT_LLM_API_KEY",
    "WT_GITHUB_TOKEN_FILE",
    "WT_NTFY_TOKEN_FILE",
    "WT_LLM_API_KEY_FILE",
]
SECRETS = [
    ("WT_GITHUB_TOKEN", "github_token"),
    ("WT_NTFY_TOKEN", "ntfy_token"),
    ("WT_LLM_API_KEY", "llm_api_key"),
]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


def test_defaults() -> None:
    env = Env()

    assert env.docker_host is None
    assert env.data_dir == Path("/data")
    assert env.log_level == "INFO"
    assert env.github_api_url == "https://api.github.com"
    assert env.github_token is None
    assert env.ntfy_token is None
    assert env.llm_api_key is None


def test_values_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCKER_HOST", "tcp://socket-proxy:2375")
    monkeypatch.setenv("WT_DATA_DIR", "/srv/wt")
    monkeypatch.setenv("WT_LOG_LEVEL", "debug")
    monkeypatch.setenv("WT_GITHUB_API_URL", "http://fake-github:8080/")

    env = Env()

    assert env.docker_host == "tcp://socket-proxy:2375"
    assert env.data_dir == Path("/srv/wt")
    assert env.log_level == "DEBUG"
    assert env.github_api_url == "http://fake-github:8080"


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("WT_LOG_LEVEL", "LOUD"),
        ("WT_GITHUB_API_URL", "ftp://example.com"),
    ],
)
def test_bad_values_fail(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(ValidationError):
        Env()


def test_empty_values_use_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WT_GITHUB_TOKEN", "")

    env = Env()

    assert env.github_token is None


def test_an_old_trusted_proxies_value_is_ignored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # WT does not read X-Forwarded-* headers. An old .env can still have this var.
    monkeypatch.setenv("WT_TRUSTED_PROXIES", "172.18.0.0/16")

    env = Env()

    assert "trusted_proxies" not in Env.model_fields
    assert not hasattr(env, "trusted_proxies")


@pytest.mark.parametrize(("env_name", "field"), SECRETS)
def test_secret_from_env(
    monkeypatch: pytest.MonkeyPatch, env_name: str, field: str
) -> None:
    monkeypatch.setenv(env_name, "s3cret-value")

    secret = getattr(Env(), field)

    assert secret.get_secret_value() == "s3cret-value"


@pytest.mark.parametrize(("env_name", "field"), SECRETS)
def test_secret_from_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, env_name: str, field: str
) -> None:
    secret_file = tmp_path / "secret"
    secret_file.write_text("s3cret-value\n")
    monkeypatch.setenv(f"{env_name}_FILE", str(secret_file))

    secret = getattr(Env(), field)

    assert secret.get_secret_value() == "s3cret-value"


@pytest.mark.parametrize(("env_name", "field"), SECRETS)
def test_secret_and_file_both_set_fail(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, env_name: str, field: str
) -> None:
    secret_file = tmp_path / "secret"
    secret_file.write_text("from-file")
    monkeypatch.setenv(env_name, "from-env")
    monkeypatch.setenv(f"{env_name}_FILE", str(secret_file))

    with pytest.raises(ValueError, match=f"{env_name}_FILE"):
        Env()


def test_secret_file_that_does_not_exist_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("WT_GITHUB_TOKEN_FILE", str(tmp_path / "missing"))

    with pytest.raises(ValueError, match="WT_GITHUB_TOKEN_FILE"):
        Env()


def test_no_secret_value_in_repr_or_str(monkeypatch: pytest.MonkeyPatch) -> None:
    for env_name, _ in SECRETS:
        monkeypatch.setenv(env_name, f"s3cret-{env_name}")

    env = Env()

    for text in (repr(env), str(env)):
        assert "s3cret" not in text


def test_secret_file_source_reads_no_single_field() -> None:
    # pydantic-settings calls __call__ for all values; get_field_value gives nothing.
    from wt.config import _SecretFiles  # pyright: ignore[reportPrivateUsage]

    source = _SecretFiles(Env)
    field = Env.model_fields["github_token"]

    assert source.get_field_value(field, "github_token") == (
        None,
        "github_token",
        False,
    )
