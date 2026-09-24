"""
User progress tracking schemas.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


# ── Requests ─────────────────────────────────────────────────────────────


class ProgressUpdate(BaseModel):
    """
    Payload for marking a topic as completed or recording a visit.

    ``is_completed`` is optional — if omitted, only ``last_visited_at``
    is refreshed (useful for "I opened this topic" analytics).
    """

    topic_id: uuid.UUID
    is_completed: bool | None = None


# ── Responses ────────────────────────────────────────────────────────────


class ProgressRead(BaseModel):
    """Single topic progress record for the authenticated user."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    topic_id: uuid.UUID
    is_completed: bool
    completed_at: datetime | None = None
    last_visited_at: datetime


class ModuleProgressSummary(BaseModel):
    """
    Aggregated progress for a single module.

    Returned as part of the curriculum tree so the frontend can
    render per-module completion bars.
    """

    module_id: uuid.UUID
    module_title: str
    total_topics: int
    completed_topics: int
    completion_percent: float
