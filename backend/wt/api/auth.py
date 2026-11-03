"""Auth routes: state, first setup, login and logout. No session is needed for them."""

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select, update

from wt.api.deps import Ctx, SessionCookie
from wt.auth import sessions, totp
from wt.auth.password import MIN_LENGTH, hash_password, verify_password
from wt.context import AppContext
from wt.db.models import ADMIN_ID, Admin

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


def has_admin(ctx: AppContext) -> bool:
    with Session(ctx.engine) as session:
        return session.exec(select(Admin)).first() is not None


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
    if has_admin(ctx):
        raise HTTPException(409, "The admin is already set up")
    if not ctx.setup_token.check(token):
        ctx.login_limit.failure()
        raise HTTPException(403, "The setup token is not correct")


@router.get("/state")
def state(ctx: Ctx, wt_session: SessionCookie = None) -> AuthState:
    logged_in = wt_session is not None and sessions.touch_session(
        ctx.engine, wt_session
    )
    return AuthState(setup_required=not has_admin(ctx), logged_in=logged_in)


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

    admin = Admin(
        id=ADMIN_ID,
        password_hash=hash_password(body.password),
        totp_secret=secret,
        last_totp_step=step,
    )
    try:
        with Session(ctx.engine) as session:
            session.add(admin)
            session.commit()
    except IntegrityError:
        raise HTTPException(409, "The admin is already set up") from None
    ctx.setup_token.use()
    ctx.login_limit.success()
    sessions.set_cookie(response, sessions.create_session(ctx.engine))
    return AuthState(setup_required=False, logged_in=True)


class LoginIn(BaseModel):
    password: str = Field(max_length=1024)
    totp_code: str = Field(max_length=16)


LOGIN_FAILED = "The password or the TOTP code is not correct"


@router.post("/login")
def login(body: LoginIn, ctx: Ctx, response: Response) -> AuthState:
    """Log in with the password and a TOTP code. All failures give the same message."""
    check_limit(ctx)
    with Session(ctx.engine) as session:
        admin = session.get(Admin, ADMIN_ID)
    if admin is None:
        raise HTTPException(409, "Set up the admin first")

    # Check both, so that the time does not show which one failed.
    password_ok = verify_password(admin.password_hash, body.password)
    step = totp.verify(admin.totp_secret, body.totp_code, admin.last_totp_step)
    if not password_ok or step is None or not _use_step(ctx, step):
        ctx.login_limit.failure()
        raise HTTPException(401, LOGIN_FAILED)

    ctx.login_limit.success()
    sessions.set_cookie(response, sessions.create_session(ctx.engine))
    return AuthState(setup_required=False, logged_in=True)


def _use_step(ctx: AppContext, step: int) -> bool:
    """Save the TOTP step. False if a parallel login used this step or a newer one."""
    statement = (
        update(Admin)
        .where(col(Admin.id) == ADMIN_ID, col(Admin.last_totp_step) < step)
        .values(last_totp_step=step)
    )
    with Session(ctx.engine) as session:
        result = session.exec(statement)
        session.commit()
    return result.rowcount == 1


@router.post("/logout", status_code=204)
def logout(ctx: Ctx, response: Response, wt_session: SessionCookie = None) -> None:
    """Delete the session and the cookie."""
    if wt_session is not None:
        sessions.delete_session(ctx.engine, wt_session)
    sessions.clear_cookie(response)
