"""
Gemini AI Study Assistant service – rate limiting + generation.

Business Logic
~~~~~~~~~~~~~~
1. **Rate-limit gate**: query the ``ai_rate_limits`` table for today's
   row.  If ``query_count >= settings.AI_DAILY_QUOTA``, raise HTTP 429.
2. **Context grounding**: load the topic's ``notebooklm_raw_notes``
   from ``topic_contents`` so Gemini answers are on-curriculum.
3. **Generation**: call the Gemini API with a strict system prompt.
4. **Counter increment**: upsert today's rate-limit row (+1).
"""

import uuid
from datetime import date

from google import genai
from google.genai import types
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.ai import AIRateLimit
from app.models.curriculum import Topic, TopicContent
from app.schemas.ai import AIQueryRequest, AIQueryResponse

# ── Gemini SDK client (modern google-genai package) ─────────────────────
_client = genai.Client(api_key=settings.GEMINI_API_KEY)

_SYSTEM_PROMPT = (
    "You are a helpful study assistant for an accounting e-learning platform "
    "called AccOS.  Your answers MUST be grounded in the course material "
    "provided below.  If the question is outside the scope of the material, "
    "politely state that you can only help with topics covered in the course.  "
    "Use clear, concise language suitable for university-level accounting "
    "students.  Format your answers in Markdown when appropriate."
)


async def _check_and_increment_rate_limit(
    user_id: uuid.UUID,
    session: AsyncSession,
) -> int:
    """
    Enforce the daily AI query cap for the given user.

    Returns the **new** ``query_count`` after incrementing.

    Raises
    ------
    HTTPException 429
        When the user has already exhausted today's quota.
    """
    today = date.today()

    # Look for today's rate-limit row
    stmt = select(AIRateLimit).where(
        AIRateLimit.user_id == user_id,
        AIRateLimit.query_date == today,
    )
    result = await session.execute(stmt)
    rate_row = result.scalar_one_or_none()

    if rate_row is None:
        # First query today – create the row
        rate_row = AIRateLimit(
            user_id=user_id,
            query_date=today,
            query_count=1,
        )
        session.add(rate_row)
        await session.flush()
        return 1

    # Row exists – check cap before incrementing
    if rate_row.query_count >= settings.AI_DAILY_QUOTA:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Daily AI query limit reached ({settings.AI_DAILY_QUOTA} "
                f"queries/day).  Please try again tomorrow."
            ),
            headers={"Retry-After": "86400"},
        )

    rate_row.query_count += 1
    await session.flush()
    return rate_row.query_count


async def _load_topic_context(
    topic_id: uuid.UUID,
    session: AsyncSession,
) -> str:
    """
    Load the topic's ``notebooklm_raw_notes`` as grounding context.

    Falls back to a generic message if no notes are available,
    but still allows the query to proceed (Gemini can answer
    general accounting questions within the system prompt scope).

    Raises
    ------
    HTTPException 404
        If the topic does not exist or is unpublished.
    """
    topic = await session.get(Topic, topic_id)
    if topic is None or not topic.is_published:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found.",
        )

    # Load the heavy content row
    stmt = select(TopicContent).where(TopicContent.topic_id == topic_id)
    result = await session.execute(stmt)
    content = result.scalar_one_or_none()

    if content and content.notebooklm_raw_notes:
        return (
            f"## Course Material for: {topic.title}\n\n"
            f"{content.notebooklm_raw_notes}"
        )

    return (
        f"## Topic: {topic.title}\n\n"
        "No detailed course notes are available for this topic yet.  "
        "Answer the student's question using your general accounting "
        "knowledge, but stay within the scope of an accounting curriculum."
    )


async def ask_study_assistant(
    user_id: uuid.UUID,
    payload: AIQueryRequest,
    session: AsyncSession,
) -> AIQueryResponse:
    """
    End-to-end flow: rate-limit → context load → Gemini call → response.

    Parameters
    ----------
    user_id
        Authenticated user's UUID.
    payload
        Contains ``topic_id`` and ``question``.
    session
        Active database session (will be flushed but **not** committed –
        the caller / middleware handles the commit).

    Returns
    -------
    AIQueryResponse
        The Gemini-generated answer alongside quota usage information.
    """
    # 1. Rate-limit check + increment
    queries_used = await _check_and_increment_rate_limit(user_id, session)

    # 2. Load grounding context
    context = await _load_topic_context(payload.topic_id, session)

    # 3. Call Gemini (async via client.aio)
    try:
        response = await _client.aio.models.generate_content(
            model="gemini-2.0-flash",
            contents=(
                f"### Context (course material)\n{context}\n\n"
                f"### Student Question\n{payload.question}"
            ),
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_PROMPT,
                temperature=0.4,
                max_output_tokens=2048,
            ),
        )
        answer = response.text
    except Exception as exc:
        # Roll back the rate-limit increment so the user isn't penalised
        # for an API failure they couldn't control.
        queries_used -= 1
        stmt = select(AIRateLimit).where(
            AIRateLimit.user_id == user_id,
            AIRateLimit.query_date == date.today(),
        )
        result = await session.execute(stmt)
        rate_row = result.scalar_one_or_none()
        if rate_row is not None and rate_row.query_count > 0:
            rate_row.query_count -= 1
            await session.flush()

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI service unavailable: {exc}",
        )

    return AIQueryResponse(
        answer=answer,
        topic_id=payload.topic_id,
        queries_used_today=queries_used,
        daily_limit=settings.AI_DAILY_QUOTA,
    )
