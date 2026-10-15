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
- `topic_contents`: id, topic_id (FK, unique), html_content, notebooklm_url, notebooklm_raw_notes, updated_at
- `topic_attachments`: id, topic_id (FK), title, file_type ('pdf'|'pptx'), drive_link, order_index
- `user_progress`: id, user_id (FK), topic_id (FK), is_completed, completed_at, last_visited_at. (Unique on `user_id` + `topic_id`)
- `ai_rate_limits`: id, user_id (FK), query_date, query_count. (Unique on `user_id` + `query_date`)
- `payment_transactions`: id, user_id (FK), plan_type, payment_method, transaction_reference (unique), amount, receipt_url, status, rejection_reason, verified_by, verified_at, created_at, updated_at

## 5. Development Roadmap
- Step 1: Project setup, configuration (`pydantic-settings`), async DB engine & session.
- Step 2: SQLAlchemy 2.0 models and Alembic setup.
- Step 3: Pydantic v2 schemas.
- Step 4: JWT Auth + Single session validation.
- Step 5: Modules and Topics router with paywall dependency.
- Step 6: User progress router.
- Step 7: Gemini AI study assistant router with rate limiter.






# Module Briefing: Admin Content Management System (CMS) & Analytics Engine

## Role & Instructions
You are acting as an elite Backend Architect and Senior Systems Engineer. We are now specifying and implementing the **Admin CMS** and **Platform Analytics Engine** for our FastAPI accounting e-learning SaaS.

### CRITICAL INSTRUCTION:
DO NOT generate all the code at once. Review this specification, acknowledge your understanding of the architecture, database queries, and business logic, and confirm you are ready. We will implement this module strictly step by step across the 4 milestones defined below.

---

## 1. Domain Overview & Requirements

The Admin subsystem serves two critical operational goals:
1. **Content Ingestion & CMS (Frictionless Uploading)**:
   - Provide administrative endpoints to create modules, topics, and manage publishing states.
   - Support direct file upload (`multipart/form-data`) for large, pre-styled `.html` files (e.g., `Ethiopian_Financial_Law_Dashboard.html`), reading the raw HTML stream and persisting it directly into `topic_contents.html_content`.
   - Manage external metadata: NotebookLM URLs, raw NotebookLM notes for AI context, video stream URLs, and audio URLs.
   - Support file attachments (PDFs, PPTXs, XLSX spreadsheets) associated with specific topics.

2. **Platform Analytics & Telemetry (SQL-Aggregated)**:
   - Calculate business and academic metrics using efficient database-level aggregations (`func.count`, `func.sum`, `func.avg`, `group_by`).
   - Deliver clear dashboards for:
     - **Business KPIs**: Total users, active subscribers, conversion rate, total revenue.
     - **Engagement Metrics**: Completion rates per topic, most/least popular topics, drop-off points.
     - **AI Cost & Quota Monitoring**: Total daily queries, high-frequency users, token consumption estimates.
     - **Payment Audit**: Pending transaction queue, payment method breakdown (CBE vs. Telebirr).

---

## 2. API Endpoints Specification

### A. Admin CMS (`/api/v1/admin/cms`)
*All endpoints require `require_admin` dependency.*

1. **Modules Management**:
   - `POST /modules` — Create module (`title`, `slug`, `description`, `order_index`).
   - `PATCH /modules/{module_id}` — Update metadata or reorder.
   - `DELETE /modules/{module_id}` — Cascade delete (with safety confirmation).

2. **Topics Management**:
   - `POST /modules/{module_id}/topics` — Create topic metadata (`title`, `slug`, `order_index`, `is_free_preview`, `estimated_read_time`).
   - `PATCH /topics/{topic_id}` — Edit topic metadata, toggle `is_free_preview`, or toggle `is_published`.
   - `DELETE /topics/{topic_id}` — Delete topic and associated contents.

3. **Content & HTML Ingestion**:
   - `POST /topics/{topic_id}/content` (Multipart Form):
     - `html_file`: `UploadFile` (reads UTF-8 HTML string into `topic_contents.html_content`).
     - `notebooklm_url`: Optional[str]
     - `notebooklm_raw_notes`: Optional[str]
     - `video_url`: Optional[str]
     - `audio_url`: Optional[str]
   - `GET /topics/{topic_id}/content` — Preview current content payload.

4. **Attachments Management**:
   - `POST /topics/{topic_id}/attachments` (Multipart Form):
     - `file`: `UploadFile` (validates mime types: PDF, PPTX, XLSX).
     - `title`: str (e.g., "Cost Accounting Slide Deck - Lesson 1").
     - Stores the file to storage (local disk/S3) and creates `topic_attachments` record with calculated byte size.
   - `DELETE /attachments/{attachment_id}` — Remove attachment file and database record.

---

### B. Admin Analytics (`/api/v1/admin/analytics`)
*All endpoints require `require_admin` dependency.*

1. **`GET /overview`** (High-Level KPIs):
   - `total_students`: `COUNT(users.id)` where `role = 'student'`.
   - `active_subscriptions`: `COUNT(subscriptions.id)` where `status = 'active'` AND `expires_at > now()`.
   - `free_tier_students`: `total_students - active_subscriptions`.
   - `subscription_conversion_rate`: Percentage of registered students who are paid subscribers.
   - `pending_verifications`: `COUNT(payment_transactions.id)` with `status = 'pending_verification'`.
   - `total_verified_revenue`: `SUM(payment_transactions.amount)` where `status = 'completed'`.

2. **`GET /learning-engagement`**:
   - `most_completed_topics`: Top 5 topics with highest `is_completed = true` in `user_progress`.
   - `most_visited_topics`: Top 5 topics ordered by recent `last_visited_at` activity.
   - `completion_funnel`: Percentage of students completing each topic within a given module (identifies where students get stuck).

3. **`GET /ai-utilization`**:
   - `total_queries_today`: `SUM(query_count)` from `ai_rate_limits` for `CURRENT_DATE`.
   - `active_ai_users_today`: `COUNT(DISTINCT user_id)` querying the AI today.
   - `top_ai_users`: Top 10 users with highest query counts (abuse/power-user detection).

4. **`GET /finance-summary`**:
   - Transaction breakdown by payment method (e.g., CBE vs. Telebirr count and total amount).
   - Recent 20 transactions log with status, student email, and timestamp.

---

## 3. Step-by-Step Implementation Roadmap

When instructed, we will execute in this order:

- **Milestone 1**: Pydantic v2 schemas for all CMS inputs/outputs and Analytics response models.
- **Milestone 2**: File storage handler utility for saving uploaded attachments and validating `.html` files.
- **Milestone 3**: Admin CMS router implementation with transaction safety and role verification.
- **Milestone 4**: Admin Analytics service and router with optimized async SQLAlchemy aggregation queries.

---

### Your Immediate Response:
1. Confirm that you have reviewed the entire specification.
2. Explicitly outline how you will structure the SQL aggregation queries for the `/analytics/overview` endpoint to ensure they run efficiently in async SQLAlchemy 2.0 without loading entire tables into memory.
3. State that you are ready to begin **Milestone 1**.













# Module Specification: Manual/Automated Transaction Verification Payment System

## Core Business Flow
We are NOT using direct checkout gateways (like Stripe Checkout). Instead, we are using a **Transaction Reference Verification Workflow**:
1. Student views subscription plans and payment instructions (e.g., CBE Account, Telebirr Merchant/Account Number).
2. Student transfers funds externally and copies the **Transaction ID / Reference Number** provided by the bank or payment app.
3. Student submits the transaction reference on our website (`POST /api/v1/payments/submit-reference`), along with the plan selected and an optional screenshot of the receipt.
4. The system creates a `payment_transactions` record with status `pending_verification`.
5. An external verification service (or an admin) verifies the transaction reference and calls our secure verification endpoint (`POST /api/v1/payments/verify-reference`).
6. Upon successful verification, the transaction status updates to `completed`, and the user's `subscriptions` record is automatically activated or extended.

---

## 1. Database Model Updates (SQLAlchemy 2.0)

### `payment_transactions` Table:
- `id`: Mapped[UUID], PK, default uuid4
- `user_id`: Mapped[UUID], ForeignKey("users.id", ondelete="CASCADE"), nullable=False
- `plan_type`: Mapped[str], String(50), nullable=False ('monthly', 'semester', 'annual')
- `payment_method`: Mapped[str], String(50), nullable=False (e.g., 'telebirr', 'cbe', 'bank_transfer')
- `transaction_reference`: Mapped[str], String(255), unique=True, index=True, nullable=False (Crucial: prevents duplicate submission of the same transaction)
- `amount`: Mapped[Decimal], Numeric(10, 2), nullable=False
- `receipt_url`: Mapped[Optional[str]], String(1000), nullable=True
- `status`: Mapped[str], String(50), default="pending_verification", nullable=False ('pending_verification', 'completed', 'rejected')
- `rejection_reason`: Mapped[Optional[str]], Text, nullable=True
- `verified_by`: Mapped[Optional[str]], String(100), nullable=True
- `verified_at`: Mapped[Optional[datetime]], DateTime(timezone=True), nullable=True
- `created_at`: Mapped[datetime], DateTime(timezone=True), server_default=func.now()
- `updated_at`: Mapped[datetime], DateTime(timezone=True), server_default=func.now(), onupdate=func.now()

---

## 2. API Endpoints Specification

### A. Student Payment Submissions (`/api/v1/payments`)

1. **`POST /api/v1/payments/submit-reference`**
   - **Access:** Authenticated (Student)
   - **Body (multipart/form-data or JSON):**
     - `plan_type`: str ('monthly' | 'semester' | 'annual')
     - `payment_method`: str ('cbe' | 'telebirr' | ...)
     - `transaction_reference`: str (e.g., "TXN987654321")
     - `receipt_file`: Optional[UploadFile]
   - **Validation:** Check if `transaction_reference` already exists in `payment_transactions`. If it exists, raise `400 Bad Request` ("This transaction reference has already been submitted").
   - **Outcome:** Stores record as `status='pending_verification'`. Returns confirmation message and status.

2. **`GET /api/v1/payments/my-status`**
   - **Access:** Authenticated (Student)
   - **Outcome:** Returns the user's latest transaction status (whether pending, completed, or rejected with reasons) and current subscription expiration.

---

### B. Verification Endpoint (Automated Verifier / Internal Service)

3. **`POST /api/v1/payments/verify-reference`**
   - **Access:** Protected by a secure internal `X-Verifier-Key` header (defined in `.env`).
   - **Request Body:**
     ```json
     {
       "transaction_reference": "TXN987654321",
       "status": "completed", // or "rejected"
       "rejection_reason": null,
       "verifier_note": "Automated bank statement reconciliation"
     }
     ```
   - **Execution Logic (Atomic Transaction):**
     1. Locate the pending record in `payment_transactions` by `transaction_reference`. If not found, return `404 Not Found`.
     2. If already marked `completed`, return `200 OK` (idempotent).
     3. If `status == "completed"`:
        - Set `transaction.status = "completed"`.
        - Set `transaction.verified_by = "auto_verifier"`.
        - Set `transaction.verified_at = now()`.
        - Calculate subscription duration based on `plan_type` (30 days, 120 days, or 365 days).
        - Upsert the user's `subscriptions` record (`starts_at = now()`, `expires_at = now() + duration`).
     4. If `status == "rejected"`:
        - Set `transaction.status = "rejected"`.
        - Set `transaction.rejection_reason = body.rejection_reason`.

---

### C. Admin Fallback & Verification Panel (`/api/v1/admin/payments`)

4. **`GET /api/v1/admin/payments/pending`**
   - **Access:** Admin only
   - **Outcome:** Returns a paginated list of all pending transactions with student name, email, transaction reference, amount, and receipt image URL.

5. **`POST /api/v1/admin/payments/{transaction_id}/review`**
   - **Access:** Admin only
   - **Body:** `{ "action": "approve" | "reject", "rejection_reason": "Optional string" }`
   - **Outcome:** Performs the same activation logic as the automated verifier, tagging `verified_by = admin_user.email`.

---

## 3. Important Implementation Notes
- Use database transactions (`session.begin()`) when updating payment status and creating/extending subscriptions to ensure atomicity.
- Ensure `transaction_reference` lookups are case-insensitive or sanitized (trimmed of whitespaces) to prevent user typing mismatches.