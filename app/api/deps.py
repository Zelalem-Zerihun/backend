"""
Shared FastAPI dependencies (auth guards, paywall checks, etc.).

``get_current_user`` is the critical dependency – it validates the JWT
**and** enforces single-active-session by comparing the token's
``sid`` claim against the user's ``current_session_id`` in the database.

``require_topic_access`` enforces the freemium paywall: free-preview
topics are accessible to all authenticated users, while premium topics
require an active, non-expired subscription.
"""

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.core.security import decode_access_token
from app.models.user import Subscription, User

# ── Bearer scheme (auto-populates Swagger "Authorize" button) ────────────
_bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials, Depends(_bearer_scheme)
    ],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> User:
    """
    Validate the bearer token and return the authenticated ``User``.

    Steps
    -----
    1. Decode & verify the JWT signature + expiration.
    2. Extract ``sub`` (user_id) and ``sid`` (session_id) claims.
    3. Load the user from the database.
    4. **Single-session check** – reject the token if ``sid`` no longer
       matches ``User.current_session_id`` (meaning the user logged in
       from another device / browser, invalidating this session).

    Raises
    ------
    HTTPException 401
        On any validation failure.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # 1. Decode token
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise credentials_exception

    # 2. Extract claims
    user_id_str: str | None = payload.get("sub")
    session_id_str: str | None = payload.get("sid")
    if user_id_str is None or session_id_str is None:
        raise credentials_exception

    try:
        user_id = uuid.UUID(user_id_str)
        session_id = uuid.UUID(session_id_str)
    except ValueError:
        raise credentials_exception

    # 3. Load user
    user = await session.get(User, user_id)
    if user is None:
        raise credentials_exception

    # 4. Single-active-session enforcement
    if user.current_session_id != session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has been invalidated. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


# ── Convenience type alias ───────────────────────────────────────────────
CurrentUser = Annotated[User, Depends(get_current_user)]


# ── Role-based access control ───────────────────────────────────────────
def require_role(*allowed_roles: str):
    """
    Factory that returns a dependency restricting access to the given roles.

    Usage::

        @router.get("/admin-only", dependencies=[Depends(require_role("admin"))])
        async def admin_endpoint(): ...
    """

    async def _check_role(user: CurrentUser) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource.",
            )
        return user

    return _check_role


# ── Paywall (subscription) guard ─────────────────────────────────────────


async def require_topic_access(
    topic_id: uuid.UUID,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> None:
    """
    Enforce the freemium paywall for a given topic.

    Resolution order
    ~~~~~~~~~~~~~~~~
    1. Load the topic – 404 if missing / unpublished.
    2. If ``topic.is_free_preview`` is ``True``, access is granted
       immediately (no subscription required).
    3. Otherwise, query the ``subscriptions`` table for an active,
       non-expired record for this user.
    4. If no qualifying subscription exists, raise HTTP 403 with the
       standardised ``PaywallResponse`` body.

    This dependency is designed to be added to topic-content endpoints
    that serve premium material.
    """
    from app.services.curriculum import get_topic  # avoid circular import

    topic = await get_topic(topic_id, session)

    # Free-preview topics are always accessible
    if topic.is_free_preview:
        return

    # Check for an active, non-expired subscription
    now = datetime.now(timezone.utc)
    stmt = select(Subscription).where(
        Subscription.user_id == current_user.id,
        Subscription.status == "active",
        Subscription.expires_at > now,
    )
    result = await session.execute(stmt)
    subscription = result.scalar_one_or_none()

    if subscription is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active subscription required to access this content.",
            headers={"X-Upgrade-URL": "/pricing"},
        )


# ── Admin guard ─────────────────────────────────────────────────────────
async def require_admin(user: CurrentUser) -> User:
    """
    Dependency that allows only users with ``role='admin'``.

    Raises
    ------
    HTTPException 403
        If the authenticated user is not an admin.
    """
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )
    return user


# Convenience annotated alias — use in router signatures for clean DI.
AdminUser = Annotated[User, Depends(require_admin)]
