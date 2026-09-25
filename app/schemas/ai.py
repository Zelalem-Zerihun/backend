"""
AI Study Assistant (Gemini) request / response schemas.
"""

import uuid

from pydantic import BaseModel, Field


# ── Requests ─────────────────────────────────────────────────────────────


class AIQueryRequest(BaseModel):
    """
    User question submitted to the Gemini-powered study assistant.

    ``topic_id`` grounds the AI's context to the relevant topic's
    ``notebooklm_raw_notes`` so answers stay on-curriculum.
    """

    topic_id: uuid.UUID
    question: str = Field(min_length=3, max_length=2000)


# ── Responses ────────────────────────────────────────────────────────────


class AIQueryResponse(BaseModel):
    """Response from the Gemini study assistant."""

    answer: str
    topic_id: uuid.UUID
    queries_used_today: int
    daily_limit: int


class AIQuotaResponse(BaseModel):
    """Current AI query quota status for the authenticated user."""

    queries_used_today: int
    daily_limit: int
    remaining: int
