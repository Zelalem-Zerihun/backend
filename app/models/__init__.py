"""
SQLAlchemy ORM models package.

Import all models here so that:
1. Alembic's ``target_metadata`` discovers every table via ``Base.metadata``.
2. Other modules can do ``from app.models import User, Module, ...``.
"""

from app.models.user import User, Subscription  # noqa: F401
from app.models.curriculum import (  # noqa: F401
    Module,
    Topic,
    TopicContent,
    TopicAttachment,
)
from app.models.progress import UserProgress  # noqa: F401
from app.models.ai import AIRateLimit  # noqa: F401

__all__ = [
    "User",
    "Subscription",
    "Module",
    "Topic",
    "TopicContent",
    "TopicAttachment",
    "UserProgress",
    "AIRateLimit",
]
