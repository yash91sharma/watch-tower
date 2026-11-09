"""Auth routes: state, first setup, login and logout. No session is needed for them."""

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from wt.api.deps import Ctx, SessionCookie, clear_cookie, set_cookie
from wt.auth import sessions, totp
from wt.auth.admin import create_admin, load_admin, use_totp_step
from wt.auth.password import MIN_LENGTH, hash_password, verify_password
from wt.context import AppContext
from wt.db import has_admin

router = APIRouter(prefix="/auth", tags=["auth"])


class AuthState(BaseModel):
    setup_required: bool
    logged_in: bool


class SetupBeginIn(BaseModel):
    token: str = Field(max_length=200)


class SetupBeginOut(BaseModel):
    totp_secret: str
    otpauth_uri: str
    # An SVG document. Show it in an <img> with a data: URL, not as HTML.
    qr_svg: str


class SetupFinishIn(BaseModel):
    token: str = Field(max_length=200)
    password: str = Field(min_length=MIN_LENGTH, max_length=1024)
    totp_code: str = Field(max_length=16)


def check_limit(ctx: AppContext) -> None:
    """While the login limit blocks: 429 with Retry-After."""
    retry_after = ctx.login_limit.retry_after()
    if retry_after is not None:
        raise HTTPException(
            429,
            "Too many failed attempts. Try again later.",
            headers={"Retry-After": str(retry_after)},
        )


def check_setup_token(ctx: AppContext, token: str) -> None:
    """Stop if the admin exists (409) or the token is wrong (403, counts as a failure)."""
    check_limit(ctx)
    if has_admin(ctx.engine):
        raise HTTPException(409, "The admin is already set up")
    if not ctx.setup_token.check(token):
        ctx.login_limit.failure()
        raise HTTPException(403, "The setup token is not correct")


@router.get("/state")
def state(ctx: Ctx, wt_session: SessionCookie = None) -> AuthState:
    logged_in = wt_session is not None and sessions.touch_session(
        ctx.engine, wt_session
    )
    return AuthState(setup_required=not has_admin(ctx.engine), logged_in=logged_in)


@router.post("/setup/begin")
def setup_begin(body: SetupBeginIn, ctx: Ctx) -> SetupBeginOut:
    """Make a new TOTP secret for the setup. WT keeps it in memory until setup finish."""
    check_setup_token(ctx, body.token)
    secret = totp.new_secret()
    ctx.setup_token.pending_secret = secret
    uri = totp.provisioning_uri(secret)
    return SetupBeginOut(totp_secret=secret, otpauth_uri=uri, qr_svg=totp.qr_svg(uri))


@router.post("/setup/finish")
def setup_finish(body: SetupFinishIn, ctx: Ctx, response: Response) -> AuthState:
    """Save the admin, end the setup token and log in."""
    check_setup_token(ctx, body.token)
    secret = ctx.setup_token.pending_secret
    if secret is None:
        raise HTTPException(400, "Start the setup first")
    step = totp.verify(secret, body.totp_code, last_step=None)
    if step is None:
        ctx.login_limit.failure()
        raise HTTPException(400, "The TOTP code is not correct")

    if not create_admin(ctx.engine, hash_password(body.password), secret, step):
        raise HTTPException(409, "The admin is already set up")
    ctx.setup_token.use()
    ctx.login_limit.success()
    set_cookie(response, sessions.create_session(ctx.engine))
    return AuthState(setup_required=False, logged_in=True)


class LoginIn(BaseModel):
    password: str = Field(max_length=1024)
    totp_code: str = Field(max_length=16)


LOGIN_FAILED = "The password or the TOTP code is not correct"


@router.post("/login")
def login(body: LoginIn, ctx: Ctx, response: Response) -> AuthState:
    """Log in with the password and a TOTP code. All failures give the same message."""
    check_limit(ctx)
    admin = load_admin(ctx.engine)
    if admin is None:
        raise HTTPException(409, "Set up the admin first")

    # Check both, so that the time does not show which one failed.
    password_ok = verify_password(admin.password_hash, body.password)
    step = totp.verify(admin.totp_secret, body.totp_code, admin.last_totp_step)
    if not password_ok or step is None or not use_totp_step(ctx.engine, step):
        ctx.login_limit.failure()
        raise HTTPException(401, LOGIN_FAILED)

    ctx.login_limit.success()
    set_cookie(response, sessions.create_session(ctx.engine))
    return AuthState(setup_required=False, logged_in=True)


@router.post("/logout", status_code=204)
def logout(ctx: Ctx, response: Response, wt_session: SessionCookie = None) -> None:
    """Delete the session and the cookie."""
    if wt_session is not None:
        sessions.delete_session(ctx.engine, wt_session)
    clear_cookie(response)
