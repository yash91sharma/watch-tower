"""GET and PUT /api/settings: the UI settings and the secret state."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from wt.api.deps import Ctx
from wt.bus import Topic
from wt.config import SECRET_FIELDS, Env, Settings, load_settings, save_settings

router = APIRouter(prefix="/settings", tags=["settings"])

SecretValue = Literal["set", "not set"]


class SecretState(BaseModel):
    """Env vars set the secrets. The UI shows only if each one is set."""

    github_token: SecretValue
    ntfy_token: SecretValue
    llm_api_key: SecretValue


class SettingsOut(BaseModel):
    values: Settings
    secrets: SecretState


def settings_out(env: Env, values: Settings) -> SettingsOut:
    secrets = {
        name: "not set" if getattr(env, name) is None else "set"
        for name in SECRET_FIELDS
    }
    return SettingsOut(values=values, secrets=SecretState.model_validate(secrets))


@router.get("")
def get_settings(ctx: Ctx) -> SettingsOut:
    return settings_out(ctx.env, load_settings(ctx.engine))


@router.put("")
def put_settings(values: Settings, ctx: Ctx) -> SettingsOut:
    """Save all settings. Workers reload them on the `settings` bus topic."""
    save_settings(ctx.engine, values)
    ctx.bus.publish(Topic.SETTINGS)
    return settings_out(ctx.env, values)
