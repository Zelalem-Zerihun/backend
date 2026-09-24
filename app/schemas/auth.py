"""
Authentication & user-related request / response schemas.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ── Requests ─────────────────────────────────────────────────────────────


class UserCreate(BaseModel):
    """Registration payload."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)


class UserLogin(BaseModel):
    """Login payload."""

    email: EmailStr
    password: str


# ── Responses ────────────────────────────────────────────────────────────


class UserRead(BaseModel):
    """
    Public user profile (returned after registration, login, and
    ``GET /me``).  Never exposes ``password_hash``.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    role: str
    created_at: datetime


class TokenResponse(BaseModel):
    """JWT bearer token returned on successful login."""

    access_token: str
    token_type: str = "bearer"
    user: UserRead


# ── Subscription Responses ───────────────────────────────────────────────


class SubscriptionRead(BaseModel):
    """Subscription details surfaced to the authenticated user."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    plan_type: str
    status: str
    starts_at: datetime
    expires_at: datetime
