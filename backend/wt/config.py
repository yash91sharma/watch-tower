"""WT config.

`Env` holds the env vars: deploy values and secrets. Each secret also reads
`<NAME>_FILE` (Docker secrets). The UI settings are stored in the DB (task 5.1).
"""

import ipaddress
import os
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    NoDecode,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]

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
        if not value.startswith(("http://", "https://")):
            raise ValueError("The URL must start with http:// or https://")
        return value.rstrip("/")

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
