"""Password hash with Argon2id. Params: OWASP minimum (19 MiB, 2 iterations, 1 lane)."""

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError

MIN_LENGTH = 12

_hasher = PasswordHasher(
    time_cost=2, memory_cost=19 * 1024, parallelism=1, type=Type.ID
)


class PasswordTooShortError(ValueError):
    def __init__(self) -> None:
        super().__init__(f"The password must have {MIN_LENGTH} or more characters")


def hash_password(password: str) -> str:
    """Give the Argon2id hash. The hash has the salt and the params."""
    if len(password) < MIN_LENGTH:
        raise PasswordTooShortError
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """True if `password` matches the hash."""
    try:
        return _hasher.verify(password_hash, password)
    except VerificationError, InvalidHashError:
        return False
