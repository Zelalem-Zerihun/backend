"""
Admin Analytics response schemas.

These schemas define the response models for the four analytics
endpoints under ``/api/v1/admin/analytics``:

1. ``GET /overview``            → ``OverviewAnalytics``
2. ``GET /learning-engagement`` → ``LearningEngagementAnalytics``
3. ``GET /ai-utilization``      → ``AIUtilizationAnalytics``
4. ``GET /finance-summary``     → ``FinanceSummaryAnalytics``

All analytics endpoints are read-only (no request bodies) and return
pre-aggregated data computed via SQL-level aggregations.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════════════════
# 1. OVERVIEW KPIs
# ═══════════════════════════════════════════════════════════════════════════


class OverviewAnalytics(BaseModel):
    """
    High-level business KPIs for the admin dashboard.

    All values are computed server-side via ``COUNT`` / ``SUM``
    scalar subqueries — no full-table scans.
    """

    total_students: int = Field(
        description="Count of users with role='student'."
    )
    active_subscriptions: int = Field(
        description="Subscriptions that are active and not yet expired."
    )
    free_tier_students: int = Field(
        description="Students without an active paid subscription."
    )
    subscription_conversion_rate: float = Field(
        description="Percentage of students who are paid subscribers (0–100)."
    )
    pending_verifications: int = Field(
        description="Payment transactions awaiting admin/auto verification."
    )
    total_verified_revenue: Decimal = Field(
        description="Sum of amount for all completed payment transactions."
    )


# ═══════════════════════════════════════════════════════════════════════════
# 2. LEARNING ENGAGEMENT
# ═══════════════════════════════════════════════════════════════════════════


class TopicEngagement(BaseModel):
    """A single topic with its engagement count."""

    topic_id: uuid.UUID
    topic_title: str
    module_title: str
    count: int = Field(
        description=(
            "Completion count (for most-completed) or "
            "visit count (for most-visited)."
        )
    )


class CompletionFunnelItem(BaseModel):
    """
    One step in the per-module completion funnel.

    Shows what percentage of students who started a module
    completed each successive topic — useful for identifying
    drop-off points.
    """

    topic_id: uuid.UUID
    topic_title: str
    order_index: int
    total_students_started: int = Field(
        description="Number of students who have any progress in this module."
    )
    students_completed: int = Field(
        description="Number of students who completed this specific topic."
    )
    completion_percent: float = Field(
        description="students_completed / total_students_started × 100."
    )


class LearningEngagementAnalytics(BaseModel):
    """
    Engagement metrics for the admin learning analytics dashboard.

    Identifies the most/least popular topics and pinpoints where
    students get stuck within a module's topic sequence.
    """

    most_completed_topics: list[TopicEngagement] = Field(
        description="Top 5 topics by completion count."
    )
    most_visited_topics: list[TopicEngagement] = Field(
        description="Top 5 topics by recent visit activity."
    )
    completion_funnel: list[CompletionFunnelItem] = Field(
        description=(
            "Per-topic completion rates for a given module, "
            "ordered by topic order_index."
        )
    )


# ═══════════════════════════════════════════════════════════════════════════
# 3. AI UTILIZATION
# ═══════════════════════════════════════════════════════════════════════════


class TopAIUser(BaseModel):
    """A single user in the top-AI-users leaderboard."""

    user_id: uuid.UUID
    email: str
    full_name: str
    total_queries: int = Field(
        description="Total AI queries by this user today."
    )


class AIUtilizationAnalytics(BaseModel):
    """
    AI cost and usage monitoring metrics.

    Helps detect abuse (excessive usage) and plan API budget.
    """

    total_queries_today: int = Field(
        description="Sum of all AI queries across all users today."
    )
    active_ai_users_today: int = Field(
        description="Distinct users who queried the AI today."
    )
    top_ai_users: list[TopAIUser] = Field(
        description="Top 10 users by query count today."
    )


# ═══════════════════════════════════════════════════════════════════════════
# 4. FINANCE SUMMARY
# ═══════════════════════════════════════════════════════════════════════════


class PaymentMethodBreakdown(BaseModel):
    """Aggregated transaction stats for a single payment method."""

    payment_method: str = Field(description="e.g. 'cbe', 'telebirr'.")
    transaction_count: int
    total_amount: Decimal


class RecentTransaction(BaseModel):
    """A single entry in the recent transactions log."""

    transaction_id: uuid.UUID
    student_email: str
    student_name: str
    plan_type: str
    payment_method: str
    amount: Decimal
    transaction_reference: str
    status: str
    created_at: datetime


class FinanceSummaryAnalytics(BaseModel):
    """
    Financial analytics: payment method breakdown and recent
    transaction activity log.
    """

    payment_method_breakdown: list[PaymentMethodBreakdown] = Field(
        description="Transaction count and total amount per payment method."
    )
    recent_transactions: list[RecentTransaction] = Field(
        description="Most recent 20 transactions with full details."
    )
