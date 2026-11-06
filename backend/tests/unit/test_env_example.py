"""The deploy file .env.example (task 15.4): it has the env vars that an admin sets."""

from pathlib import Path

from wt.config import SECRET_FIELDS, Env

ENV_EXAMPLE = Path(__file__).parents[3] / ".env.example"
# compose.yaml sets DOCKER_HOST. The defaults of the others are correct for a deploy.
NOT_IN_FILE = {"DOCKER_HOST", "WT_DATA_DIR", "WT_GITHUB_API_URL"}


def env_name(field: str) -> str:
    alias = Env.model_fields[field].validation_alias
    return alias if isinstance(alias, str) else f"WT_{field.upper()}"


def lines() -> list[str]:
    return [line for line in ENV_EXAMPLE.read_text().splitlines() if line.strip()]


def values() -> dict[str, str]:
    pairs = [line.split("=", 1) for line in lines() if not line.startswith("#")]
    return {name: value for name, value in pairs}


def test_the_file_has_each_admin_env_var_once() -> None:
    names = [line.split("=", 1)[0] for line in lines() if not line.startswith("#")]
    expected = {env_name(field) for field in Env.model_fields} - NOT_IN_FILE

    assert sorted(names) == sorted(expected)


def test_the_secrets_are_empty() -> None:
    for field in SECRET_FIELDS:
        assert values()[env_name(field)] == ""


def test_each_env_var_has_a_comment_line() -> None:
    previous = ""
    for line in lines():
        if not line.startswith("#"):
            assert previous.startswith("#"), line
        previous = line
