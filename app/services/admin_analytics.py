"""
Admin Analytics service – SQL-aggregated business and learning metrics.

All public functions accept an ``AsyncSession`` and return a fully-populated
Pydantic response model.  **No Python-level aggregation is used** — every
count, sum, and average is computed inside the database via scalar subqueries
or aggregating ``SELECT`` statements, so the engine never loads entire tables
into memory.

Query Design
~~~~~~~~~~~~
* Scalar subqueries are used for the ``/overview`` KPIs so the entire
  response is produced in **one** round-trip.
* ``GROUP BY`` + ``ORDER BY`` + ``LIMIT`` window queries are used for
  per-topic engagement rankings (avoids Python sorting of large result sets).
* Date filtering on ``ai_rate_limits`` uses ``func.current_date()`` so the
  database applies the filter at query time (no Python datetime conversion
  needed).
* All queries are read-only; no session mutations occur here.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai import AIRateLimit
from app.models.curriculum import Module, Topic
from app.models.payment import PaymentTransaction
from app.models.progress import UserProgress
from app.models.user import Subscription, User
from app.schemas.admin_analytics import (
    AIUtilizationAnalytics,
    CompletionFunnelItem,
    FinanceSummaryAnalytics,
    LearningEngagementAnalytics,
    OverviewAnalytics,
    PaymentMethodBreakdown,
    RecentTransaction,
    TopAIUser,
    TopicEngagement,
)


# ═══════════════════════════════════════════════════════════════════════════
# 1. OVERVIEW KPIs
# ═══════════════════════════════════════════════════════════════════════════


async def get_overview(session: AsyncSession) -> OverviewAnalytics:
    """
    Compute all high-level business KPIs in a single database round-trip
    using correlated scalar subqueries.

    Aggregations
    ~~~~~~~~~~~~
    * ``total_students``        – COUNT(users) WHERE role = 'student'
    * ``active_subscriptions``  – COUNT(subscriptions) WHERE status = 'active'
                                  AND expires_at > now()
    * ``pending_verifications`` – COUNT(payment_transactions) WHERE status =
                                  'pending_verification'
    * ``total_verified_revenue``– SUM(amount) WHERE status = 'completed'

    Derived
    ~~~~~~~
    * ``free_tier_students``           = total_students − active_subscriptions
    * ``subscription_conversion_rate`` = active_subscriptions / total_students × 100
    """
    now = datetime.now(timezone.utc)

    # ── Scalar subqueries ──────────────────────────────────────────────
    total_students_sq = (
        select(func.count(User.id))
        .where(User.role == "student")
        .scalar_subquery()
    )

    active_subs_sq = (
        select(func.count(Subscription.id))
        .where(
            Subscription.status == "active",
            Subscription.expires_at > now,
        )
        .scalar_subquery()
    )

    pending_sq = (
        select(func.count(PaymentTransaction.id))
        .where(PaymentTransaction.status == "pending_verification")
        .scalar_subquery()
    )

    revenue_sq = (
        select(func.coalesce(func.sum(PaymentTransaction.amount), 0))
        .where(PaymentTransaction.status == "completed")
        .scalar_subquery()
    )

    # ── Single SELECT that evaluates all four subqueries in one pass ──
    stmt = select(
        total_students_sq.label("total_students"),
        active_subs_sq.label("active_subscriptions"),
        pending_sq.label("pending_verifications"),
        revenue_sq.label("total_verified_revenue"),
    )

    row = (await session.execute(stmt)).one()

    total_students: int = row.total_students or 0
    active_subscriptions: int = row.active_subscriptions or 0
    free_tier_students: int = max(total_students - active_subscriptions, 0)

    if total_students > 0:
        conversion_rate = round(active_subscriptions / total_students * 100, 2)
    else:
        conversion_rate = 0.0

    return OverviewAnalytics(
        total_students=total_students,
        active_subscriptions=active_subscriptions,
        free_tier_students=free_tier_students,
        subscription_conversion_rate=conversion_rate,
        pending_verifications=row.pending_verifications or 0,
        total_verified_revenue=Decimal(str(row.total_verified_revenue or 0)),
    )


# ═══════════════════════════════════════════════════════════════════════════
# 2. LEARNING ENGAGEMENT
# ═══════════════════════════════════════════════════════════════════════════


async def get_learning_engagement(
    session: AsyncSession,
    module_id_for_funnel: str | None = None,
) -> LearningEngagementAnalytics:
    """
    Compute topic engagement metrics.

    Most-completed topics
    ~~~~~~~~~~~~~~~~~~~~~
    JOIN ``user_progress`` → ``topics`` → ``modules``, filter
    ``is_completed = TRUE``, GROUP BY topic, ORDER BY count DESC, LIMIT 5.

    Most-visited topics
    ~~~~~~~~~~~~~~~~~~~
    Same join pattern but counts all progress rows (any visit), ordered
    by the count of visits DESC, LIMIT 5.

    Completion funnel
    ~~~~~~~~~~~~~~~~~
    For a given module (``module_id_for_funnel``), compute per-topic:
    * ``total_students_started`` – COUNT DISTINCT users who have any
      progress row in this module.
    * ``students_completed``     – COUNT DISTINCT users with
      ``is_completed = TRUE`` for this specific topic.
    * ``completion_percent``     – derived in Python (avoids a subquery
      in the SELECT list for clarity).

    If ``module_id_for_funnel`` is ``None``, the funnel defaults to the
    first published module by ``order_index``.

    Parameters
    ----------
    session
        Active async DB session.
    module_id_for_funnel
        Optional UUID string of the module to compute the completion funnel
        for.  Defaults to the first published module.
    """
    # ── Most-completed topics (top 5) ─────────────────────────────────
    most_completed_stmt = (
        select(
            Topic.id.label("topic_id"),
            Topic.title.label("topic_title"),
            Module.title.label("module_title"),
            func.count(UserProgress.id).label("count"),
        )
        .join(UserProgress, UserProgress.topic_id == Topic.id)
        .join(Module, Module.id == Topic.module_id)
        .where(UserProgress.is_completed.is_(True))
        .group_by(Topic.id, Topic.title, Module.title)
        .order_by(func.count(UserProgress.id).desc())
        .limit(5)
    )
    most_completed_rows = (await session.execute(most_completed_stmt)).all()
    most_completed = [
        TopicEngagement(
            topic_id=row.topic_id,
            topic_title=row.topic_title,
            module_title=row.module_title,
            count=row.count,
        )
        for row in most_completed_rows
    ]

    # ── Most-visited topics (top 5 by total visit count) ──────────────
    most_visited_stmt = (
        select(
            Topic.id.label("topic_id"),
            Topic.title.label("topic_title"),
            Module.title.label("module_title"),
            func.count(UserProgress.id).label("count"),
        )
        .join(UserProgress, UserProgress.topic_id == Topic.id)
        .join(Module, Module.id == Topic.module_id)
        .group_by(Topic.id, Topic.title, Module.title)
        .order_by(func.count(UserProgress.id).desc())
        .limit(5)
    )
    most_visited_rows = (await session.execute(most_visited_stmt)).all()
    most_visited = [
        TopicEngagement(
            topic_id=row.topic_id,
            topic_title=row.topic_title,
            module_title=row.module_title,
            count=row.count,
        )
        for row in most_visited_rows
    ]

    # ── Completion funnel for a module ────────────────────────────────
    funnel: list[CompletionFunnelItem] = []

    # Resolve the target module
    if module_id_for_funnel:
        from uuid import UUID
        module_uuid = UUID(module_id_for_funnel)
        module = await session.get(Module, module_uuid)
    else:
        first_module_stmt = (
            select(Module)
            .where(Module.is_published.is_(True))
            .order_by(Module.order_index)
            .limit(1)
        )
        module = (await session.execute(first_module_stmt)).scalar_one_or_none()

    if module is not None:
        # Count distinct users who have ANY progress row in this module
        # (i.e., users who have started at least one topic in the module)
        started_sq = (
            select(func.count(func.distinct(UserProgress.user_id)))
            .join(Topic, Topic.id == UserProgress.topic_id)
            .where(Topic.module_id == module.id)
            .scalar_subquery()
        )

        funnel_stmt = (
            select(
                Topic.id.label("topic_id"),
                Topic.title.label("topic_title"),
                Topic.order_index.label("order_index"),
                func.count(
                    case((UserProgress.is_completed.is_(True), UserProgress.user_id))
                ).label("students_completed"),
                started_sq.label("total_students_started"),
            )
            .outerjoin(UserProgress, UserProgress.topic_id == Topic.id)
            .where(Topic.module_id == module.id)
            .group_by(Topic.id, Topic.title, Topic.order_index)
            .order_by(Topic.order_index)
        )
        funnel_rows = (await session.execute(funnel_stmt)).all()

        for row in funnel_rows:
            total_started: int = row.total_students_started or 0
            completed: int = row.students_completed or 0
            pct = round(completed / total_started * 100, 2) if total_started > 0 else 0.0
            funnel.append(
                CompletionFunnelItem(
                    topic_id=row.topic_id,
                    topic_title=row.topic_title,
                    order_index=row.order_index,
                    total_students_started=total_started,
                    students_completed=completed,
                    completion_percent=pct,
                )
            )

    return LearningEngagementAnalytics(
        most_completed_topics=most_completed,
        most_visited_topics=most_visited,
        completion_funnel=funnel,
    )


# ═══════════════════════════════════════════════════════════════════════════
# 3. AI UTILIZATION
# ═══════════════════════════════════════════════════════════════════════════


async def get_ai_utilization(session: AsyncSession) -> AIUtilizationAnalytics:
    """
    Compute AI usage metrics for today using ``func.current_date()``.

    ``total_queries_today``   – SUM(query_count) WHERE query_date = CURRENT_DATE
    ``active_ai_users_today`` – COUNT(DISTINCT user_id) for today
    ``top_ai_users``          – Top 10 users by total queries today, joined
                                with ``users`` to retrieve email and name
    """
    # ── Totals (single query) ─────────────────────────────────────────
    totals_stmt = select(
        func.coalesce(func.sum(AIRateLimit.query_count), 0).label("total_queries"),
        func.count(func.distinct(AIRateLimit.user_id)).label("active_users"),
    ).where(AIRateLimit.query_date == func.current_date())

    totals_row = (await session.execute(totals_stmt)).one()

    # ── Top 10 AI users today ─────────────────────────────────────────
    top_users_stmt = (
        select(
            User.id.label("user_id"),
            User.email.label("email"),
            User.full_name.label("full_name"),
            func.sum(AIRateLimit.query_count).label("total_queries"),
        )
        .join(User, User.id == AIRateLimit.user_id)
        .where(AIRateLimit.query_date == func.current_date())
        .group_by(User.id, User.email, User.full_name)
        .order_by(func.sum(AIRateLimit.query_count).desc())
        .limit(10)
    )
    top_user_rows = (await session.execute(top_users_stmt)).all()
    top_users = [
        TopAIUser(
            user_id=row.user_id,
            email=row.email,
            full_name=row.full_name,
            total_queries=row.total_queries,
        )
        for row in top_user_rows
    ]

    return AIUtilizationAnalytics(
        total_queries_today=totals_row.total_queries or 0,
        active_ai_users_today=totals_row.active_users or 0,
        top_ai_users=top_users,
    )


# ═══════════════════════════════════════════════════════════════════════════
# 4. FINANCE SUMMARY
# ═══════════════════════════════════════════════════════════════════════════


async def get_finance_summary(session: AsyncSession) -> FinanceSummaryAnalytics:
    """
    Compute payment method breakdown and return the 20 most recent transactions.

    Payment method breakdown
    ~~~~~~~~~~~~~~~~~~~~~~~~
    GROUP BY ``payment_method``, COUNT transactions, SUM amount — filtered
    to ``status = 'completed'`` so revenue figures are verified-only.

    Recent transactions
    ~~~~~~~~~~~~~~~~~~~
    JOIN ``payment_transactions`` → ``users`` for email + name.
    ORDER BY ``created_at DESC``, LIMIT 20.  No status filter — admins
    need visibility into all states (pending, completed, rejected).
    """
    # ── Breakdown by payment method ───────────────────────────────────
    breakdown_stmt = (
        select(
            PaymentTransaction.payment_method.label("payment_method"),
            func.count(PaymentTransaction.id).label("transaction_count"),
            func.coalesce(func.sum(PaymentTransaction.amount), 0).label("total_amount"),
        )
        .where(PaymentTransaction.status == "completed")
        .group_by(PaymentTransaction.payment_method)
        .order_by(func.count(PaymentTransaction.id).desc())
    )
    breakdown_rows = (await session.execute(breakdown_stmt)).all()
    breakdown = [
        PaymentMethodBreakdown(
            payment_method=row.payment_method,
            transaction_count=row.transaction_count,
            total_amount=Decimal(str(row.total_amount)),
        )
        for row in breakdown_rows
    ]

    # ── Recent 20 transactions (all statuses) ─────────────────────────
    recent_stmt = (
        select(
            PaymentTransaction.id.label("transaction_id"),
            User.email.label("student_email"),
            User.full_name.label("student_name"),
            PaymentTransaction.plan_type.label("plan_type"),
            PaymentTransaction.payment_method.label("payment_method"),
            PaymentTransaction.amount.label("amount"),
            PaymentTransaction.transaction_reference.label("transaction_reference"),
            PaymentTransaction.status.label("status"),
            PaymentTransaction.created_at.label("created_at"),
        )
        .join(User, User.id == PaymentTransaction.user_id)
        .order_by(PaymentTransaction.created_at.desc())
        .limit(20)
    )
    recent_rows = (await session.execute(recent_stmt)).all()
    recent = [
        RecentTransaction(
            transaction_id=row.transaction_id,
            student_email=row.student_email,
            student_name=row.student_name,
            plan_type=row.plan_type,
            payment_method=row.payment_method,
            amount=Decimal(str(row.amount)),
            transaction_reference=row.transaction_reference,
            status=row.status,
            created_at=row.created_at,
        )
        for row in recent_rows
    ]

    return FinanceSummaryAnalytics(
        payment_method_breakdown=breakdown,
        recent_transactions=recent,
    )
