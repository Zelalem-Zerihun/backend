"""
Authentication endpoints – register, login, current user, and logout.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.api.deps import CurrentUser
from app.schemas.auth import TokenResponse, UserCreate, UserLogin, UserRead
from app.services.auth import login_user, register_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ── POST /register ───────────────────────────────────────────────────────
@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new student account",
)
async def register(
    payload: UserCreate,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> TokenResponse:
    """
    Register a new user with **email**, **password**, and **full_name**.

    Returns a JWT access token and the newly created user profile.
    """
    return await register_user(payload, session)


# ── POST /login ──────────────────────────────────────────────────────────
@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and receive a JWT",
)
async def login(
    payload: UserLogin,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> TokenResponse:
    """
    Authenticate with **email** and **password**.

    A new ``session_id`` is generated, invalidating any previously issued
    token (single-active-session enforcement).
    """
    return await login_user(payload, session)


# ── GET /me ──────────────────────────────────────────────────────────────
@router.get(
    "/me",
    response_model=UserRead,
    summary="Get the authenticated user's profile",
)
async def me(current_user: CurrentUser) -> UserRead:
    """
    Return the profile of the currently authenticated user.

    Requires a valid, non-revoked bearer token.
    """
    return UserRead.model_validate(current_user)


# ── POST /logout ─────────────────────────────────────────────────────────
@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Invalidate the current session",
)
async def logout(
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> dict[str, str]:
    """
    Clear the user's ``current_session_id``, effectively revoking every
    outstanding JWT for this account.
    """
    current_user.current_session_id = None
    await session.flush()
    return {"detail": "Successfully logged out."}
