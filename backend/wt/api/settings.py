"""GET and PUT /api/settings: the UI settings and the secret state."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from wt.api.deps import Ctx
from wt.bus import Topic
from wt.config import Env, Settings, load_settings, save_settings
from wt.context import AppContext

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


def secret_state(env: Env) -> SecretState:
    def state(value: object) -> SecretValue:
        return "not set" if value is None else "set"

    return SecretState(
        github_token=state(env.github_token),
        ntfy_token=state(env.ntfy_token),
        llm_api_key=state(env.llm_api_key),
    )


def settings_out(ctx: AppContext, values: Settings) -> SettingsOut:
    return SettingsOut(values=values, secrets=secret_state(ctx.env))


@router.get("")
def get_settings(ctx: Ctx) -> SettingsOut:
    return settings_out(ctx, load_settings(ctx.engine))


@router.put("")
def put_settings(values: Settings, ctx: Ctx) -> SettingsOut:
    """Save all settings. Workers reload them on the `settings` bus topic."""
    save_settings(ctx.engine, values)
    ctx.bus.publish(Topic.SETTINGS)
    return settings_out(ctx, values)
