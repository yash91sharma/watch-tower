"""/api/settings: the UI settings, the secret state and the ntfy test message."""

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from wt.api.deps import Ctx
from wt.bus import Topic
from wt.config import SECRET_FIELDS, Env, Settings, load_settings, save_settings
from wt.notify.messages import ntfy_test_message
from wt.notify.ntfy import send

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


@router.post("/ntfy-test", status_code=204)
async def ntfy_test(values: Settings, ctx: Ctx) -> None:
    """Send a test message with the form values (saved or not) and the ntfy token."""
    if not values.ntfy_url or not values.ntfy_topic:
        raise HTTPException(400, "Set the ntfy URL and the ntfy topic.")
    message = ntfy_test_message(values.public_url)
    if not await send(message, values, ctx.env.ntfy_token):
        raise HTTPException(
            502,
            "ntfy did not accept the message. Check the URL, the topic and the token.",
        )
