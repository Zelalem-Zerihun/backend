# Project Context: Accounting E-Learning SaaS (Backend)

## 1. Role & Behavior
- You are an expert Backend Architect & Principal Python Engineer.
- Work **step-by-step**. Do not jump ahead or write unrequested boilerplate.
- Wait for explicit user confirmation before moving to the next implementation phase.
- Always write type-safe, production-ready code with docstrings and error handling.

## 2. Tech Stack & Tooling Standards
- **Framework**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL (UUID primary keys)
- **ORM**: SQLAlchemy 2.0 (AsyncSession, `Mapped[]`, and `mapped_column()`)
- **Schemas**: Pydantic v2 (`ConfigDict(from_attributes=True)`)
- **Linting & Formatting**: Ruff (`ruff check --fix`, `ruff format`)
- **Static Type Checking**: Mypy (strict typing)
- **Migrations**: Alembic

## 3. Core Architectural Rules (Strict Invariants)
1. **Payload Separation**:
   - Never return `html_content` or raw notes when listing modules or topics (e.g. for curriculum/sidebar navigation).
   - Only serve `html_content` and attachments through the dedicated `GET /api/v1/topics/{id}/content` endpoint.
2. **Single Active Session (Anti-Account-Sharing)**:
   - On login, generate a new UUID `session_id`, persist it in `users.current_session_id`, and embed it in the JWT claims.
   - The `get_current_user` auth dependency must reject any JWT where `token.session_id != user.current_session_id` with HTTP 401.
3. **Paywall Protection**:
   - `require_topic_access` dependency checks if `topic.is_free_preview == True`.
   - If `False`, verify the user has an active, non-expired record in `subscriptions`. If not, return HTTP 403 Forbidden.
4. **AI Rate Limiting**:
   - The Gemini AI study assistant endpoint must query the `ai_rate_limits` table and enforce a daily cap (default: 50 requests/day per user), returning HTTP 429 when exceeded.

## 4. Database Schema Summary
- `users`: id, email, password_hash, full_name, role, current_session_id, created_at
- `subscriptions`: id, user_id (FK), plan_type, status, starts_at, expires_at
- `modules`: id, title, slug (unique), description, order_index, is_published, created_at
- `topics`: id, module_id (FK), title, slug, order_index, is_free_preview, estimated_read_time, is_published. (Unique on `module_id` + `slug`)
- `topic_contents`: id, topic_id (FK, unique), html_content, notebooklm_url, notebooklm_raw_notes, video_url, audio_url, updated_at
- `topic_attachments`: id, topic_id (FK), title, file_type, file_url, file_size_bytes, order_index
- `user_progress`: id, user_id (FK), topic_id (FK), is_completed, completed_at, last_visited_at. (Unique on `user_id` + `topic_id`)
- `ai_rate_limits`: id, user_id (FK), query_date, query_count. (Unique on `user_id` + `query_date`)

## 5. Development Roadmap
- Step 1: Project setup, configuration (`pydantic-settings`), async DB engine & session.
- Step 2: SQLAlchemy 2.0 models and Alembic setup.
- Step 3: Pydantic v2 schemas.
- Step 4: JWT Auth + Single session validation.
- Step 5: Modules and Topics router with paywall dependency.
- Step 6: User progress router.
- Step 7: Gemini AI study assistant router with rate limiter.