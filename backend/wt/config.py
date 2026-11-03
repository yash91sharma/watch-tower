"""WT config.

`Env` holds the env vars: deploy values and secrets. Each secret also reads
`<NAME>_FILE` (Docker secrets). `configure_logging` sets up the log output.
`Settings` holds the UI settings. They are stored as rows in the `setting` table.
"""

import ipaddress
import logging
import os
import sys
import time
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    SecretStr,
    StringConstraints,
    field_validator,
)
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    NoDecode,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)
from sqlalchemy import Engine
from sqlmodel import Session, select

from wt.db.models import Setting

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]


def http_url(value: str) -> str:
    """Check that the URL is http or https. Remove a trailing slash."""
    if not value.startswith(("http://", "https://")):
        raise ValueError("The URL must start with http:// or https://")
    return value.rstrip("/")


# Secret fields. Each one reads WT_<NAME> or WT_<NAME>_FILE.
SECRET_FIELDS = ("github_token", "ntfy_token", "llm_api_key")


class Env(BaseSettings):
    """Env vars. Read once at start."""

    model_config = SettingsConfigDict(
        env_prefix="WT_", env_ignore_empty=True, frozen=True
    )

    docker_host: str | None = Field(default=None, validation_alias="DOCKER_HOST")
    data_dir: Path = Path("/data")
    # IPs or networks (CIDR) of the reverse proxies. WT reads X-Forwarded-* only from them.
    trusted_proxies: Annotated[list[str], NoDecode] = []
    log_level: LogLevel = "INFO"
    github_api_url: str = "https://api.github.com"

    github_token: SecretStr | None = None
    ntfy_token: SecretStr | None = None
    llm_api_key: SecretStr | None = None

    @field_validator("trusted_proxies", mode="before")
    @classmethod
    def _split_proxies(cls, value: object) -> object:
        """Read a comma-separated list. Each item must be an IP address or a network."""
        if not isinstance(value, str):
            return value
        items = [item.strip() for item in value.split(",") if item.strip()]
        for item in items:
            ipaddress.ip_network(item, strict=False)
        return items

    @field_validator("log_level", mode="before")
    @classmethod
    def _upper_log_level(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @field_validator("github_api_url")
    @classmethod
    def _check_url(cls, value: str) -> str:
        return http_url(value)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Read init values, env vars and secret files. No .env file."""
        return (init_settings, env_settings, _SecretFiles(settings_cls))


class _SecretFiles(PydanticBaseSettingsSource):
    """Reads each secret from the file in `WT_<NAME>_FILE`."""

    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> tuple[Any, str, bool]:
        # Not used: __call__ reads all values.
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for field in SECRET_FIELDS:
            name = f"WT_{field.upper()}"
            path = os.environ.get(f"{name}_FILE")
            if not path:
                continue
            if os.environ.get(name):
                raise ValueError(f"Set {name} or {name}_FILE, not both")
            try:
                values[field] = Path(path).read_text().strip()
            except OSError as error:
                raise ValueError(f"Cannot read {name}_FILE: {error.strerror}") from None
        return values


class _OneLineFormatter(logging.Formatter):
    """Writes each record on one line. Escapes the newlines in messages and tracebacks."""

    def format(self, record: logging.LogRecord) -> str:
        return super().format(record).replace("\n", "\\n")


def configure_logging(level: LogLevel) -> None:
    """Send all logs to stdout, one line per record: UTC time, level, module, message."""
    formatter = _OneLineFormatter(
        "%(asctime)s.%(msecs)03dZ %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    formatter.converter = time.gmtime
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    logging.basicConfig(level=level, handlers=[handler], force=True)


def _empty_to_none(value: object) -> object:
    """A form sends an empty text for a value that is not set."""
    if isinstance(value, str) and not value.strip():
        return None
    return value


EmptyIsNone = BeforeValidator(_empty_to_none)
HttpUrl = Annotated[str, AfterValidator(http_url)]
# The topic goes in the URL path. ntfy allows these characters.
NtfyTopic = Annotated[str, StringConstraints(pattern=r"^[-_A-Za-z0-9]{1,64}$")]
ModelName = Annotated[str, StringConstraints(max_length=200)]


class Settings(BaseModel):
    """UI settings. The admin changes them in the UI. Secrets are env vars (`Env`)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    check_interval_hours: int = Field(default=24, ge=1)
    # Restart loop: N or more restarts in M minutes.
    restart_count: int = Field(default=3, ge=2)
    restart_window_minutes: int = Field(default=10, ge=1)
    ntfy_url: Annotated[HttpUrl | None, EmptyIsNone] = None
    ntfy_topic: Annotated[NtfyTopic | None, EmptyIsNone] = None
    llm_url: Annotated[HttpUrl | None, EmptyIsNone] = None
    llm_model: Annotated[ModelName | None, EmptyIsNone] = None
    # The URL of WT. Notifications link to it.
    public_url: Annotated[HttpUrl | None, EmptyIsNone] = None


def load_settings(engine: Engine) -> Settings:
    """Read the settings. A setting with no row has its default."""
    with Session(engine) as session:
        rows = session.exec(select(Setting)).all()
    values = {row.key: row.value for row in rows if row.key in Settings.model_fields}
    return Settings.model_validate(values)


def save_settings(engine: Engine, settings: Settings) -> None:
    """Save all settings, one row per setting."""
    with Session(engine) as session:
        for key, value in settings.model_dump().items():
            session.merge(Setting(key=key, value=value))
        session.commit()
