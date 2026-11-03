"""TOTP (RFC 6238): 30 s step, 6 digits, a window of one step before and after now.

pyotp `verify` gives only a bool. WT needs the matched step to stop a replay, so
`verify` checks each step in the window itself.
"""

import hmac
from datetime import timedelta

import pyotp

from wt import clock

ISSUER = "Watch Tower"
STEP = timedelta(seconds=30)
DIGITS = 6


def new_secret() -> str:
    """A new random base32 secret (160 bits)."""
    return pyotp.random_base32()


def provisioning_uri(secret: str, name: str = "admin") -> str:
    """The otpauth:// URI for an authenticator app (QR code)."""
    totp = pyotp.TOTP(secret)
    # pyotp has no type for its **kwargs.
    return totp.provisioning_uri(name=name, issuer_name=ISSUER)  # pyright: ignore[reportUnknownMemberType]


def verify(secret: str, code: str, last_step: int | None) -> int | None:
    """Give the step of the code, or None if it fails.

    A step that is the same as or older than `last_step` fails (replay).
    """
    code = code.replace(" ", "")
    if len(code) != DIGITS or not (code.isascii() and code.isdigit()):
        return None
    totp = pyotp.TOTP(secret)
    now_step = int(clock.now().timestamp()) // int(STEP.total_seconds())
    for step in (now_step - 1, now_step, now_step + 1):
        if last_step is not None and step <= last_step:
            continue
        expected = totp.at(step * int(STEP.total_seconds()))
        if hmac.compare_digest(expected, code):
            return step
    return None
