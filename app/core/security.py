"""
Password hashing and JWT token utilities.

This module wraps **bcrypt** for password hashing and **python-jose**
for JWT creation / verification.  It is intentionally free of database
or request dependencies so it can be imported by both the auth service
and the ``get_current_user`` dependency.

.. note::

   We use ``bcrypt`` directly (not via ``passlib``) because passlib is
   incompatible with bcrypt ≥ 4.1.  The direct API is simpler anyway.
"""

import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

# ── Password Hashing ────────────────────────────────────────────────────


def hash_password(plain: str) -> str:
    """Return a bcrypt hash of *plain*."""
    return bcrypt.hashpw(
        plain.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Return ``True`` if *plain* matches the bcrypt *hashed* value."""
    return bcrypt.checkpw(
        plain.encode("utf-8"), hashed.encode("utf-8")
    )


# ── JWT Tokens ───────────────────────────────────────────────────────────


def create_access_token(
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    role: str,
    expires_delta: timedelta | None = None,
) -> str:
    """
    Build a signed JWT containing the user's identity and session claim.

    The ``session_id`` is the single-session anchor: on every login a new
    UUID is generated and stored on the ``User`` row.  The
    ``get_current_user`` dependency rejects tokens whose ``sid`` no longer
    matches the value in the database.

    Payload claims
    ~~~~~~~~~~~~~~
    * ``sub``  – user UUID (string)
    * ``sid``  – session UUID (string)
    * ``role`` – user role (``student`` | ``instructor`` | ``admin``)
    * ``exp``  – expiration timestamp
    * ``iat``  – issued-at timestamp
    """
    now = datetime.now(timezone.utc)
    expire = now + (
        expires_delta
        or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    payload = {
        "sub": str(user_id),
        "sid": str(session_id),
        "role": role,
        "exp": expire,
        "iat": now,
    }
    return jwt.encode(
        payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )


def decode_access_token(token: str) -> dict | None:
    """
    Decode and verify *token*.

    Returns the payload dict on success, or ``None`` if the token is
    invalid / expired / tampered with.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError:
        return None
