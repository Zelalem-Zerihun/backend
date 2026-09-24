"""
Authentication service – register and login business logic.

All database mutations and credential verification live here so that
route handlers stay thin and testable.
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.auth import TokenResponse, UserCreate, UserLogin, UserRead


async def register_user(
    payload: UserCreate,
    session: AsyncSession,
) -> TokenResponse:
    """
    Create a new user and return a JWT.

    Raises
    ------
    HTTPException 409
        If the email is already registered.
    """
    # ── Check for duplicate email ────────────────────────────────────
    stmt = select(User).where(User.email == payload.email)
    result = await session.execute(stmt)
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        )

    # ── Create user ──────────────────────────────────────────────────
    session_id = uuid.uuid4()
    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role="student",
        current_session_id=session_id,
    )
    session.add(user)
    await session.flush()  # populate user.id and defaults

    # ── Issue token ──────────────────────────────────────────────────
    token = create_access_token(
        user_id=user.id,
        session_id=session_id,
        role=user.role,
    )

    return TokenResponse(
        access_token=token,
        user=UserRead.model_validate(user),
    )


async def login_user(
    payload: UserLogin,
    session: AsyncSession,
) -> TokenResponse:
    """
    Authenticate an existing user and return a new JWT.

    A fresh ``session_id`` is generated on every login.  This invalidates
    any token issued to a previous session (single-active-session).

    Raises
    ------
    HTTPException 401
        If the email does not exist or the password is wrong.
    """
    # ── Look up user ─────────────────────────────────────────────────
    stmt = select(User).where(User.email == payload.email)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    # ── Rotate session (single-active-session enforcement) ───────────
    new_session_id = uuid.uuid4()
    user.current_session_id = new_session_id
    await session.flush()

    # ── Issue token ──────────────────────────────────────────────────
    token = create_access_token(
        user_id=user.id,
        session_id=new_session_id,
        role=user.role,
    )

    return TokenResponse(
        access_token=token,
        user=UserRead.model_validate(user),
    )
