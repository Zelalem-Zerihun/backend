"""
File storage utilities for the Admin CMS.

Provides one core capability:

1. **HTML ingestion** – read an uploaded ``.html`` file, validate it,
   and return the raw HTML string for database persistence.

Design Notes
~~~~~~~~~~~~
* Topic attachments (PDF, PPTX) are referenced via Google Drive links.
  No attachment files are stored on the server.
* The HTML file itself is stored directly in the ``topic_contents``
  database table — **not** on disk.
"""

import re

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings


# ═══════════════════════════════════════════════════════════════════════════
# 1. HTML FILE INGESTION
# ═══════════════════════════════════════════════════════════════════════════


async def read_html_upload(file: UploadFile) -> str:
    """
    Read and validate an uploaded HTML file, returning its content
    as a UTF-8 string.

    The HTML is stored directly in ``topic_contents.html_content``
    (not on disk) — this function only validates and reads it.

    Validations
    ~~~~~~~~~~~
    * File must have a ``.html`` or ``.htm`` extension.
    * Content-type must be ``text/html`` (if the client provides it).
    * File size must not exceed ``MAX_HTML_FILE_SIZE_MB``.
    * Content must decode as valid UTF-8.
    * Content must contain at least one HTML tag (minimal sanity check).

    Parameters
    ----------
    file
        The ``UploadFile`` from a multipart form submission.

    Returns
    -------
    str
        The raw HTML content as a string.

    Raises
    ------
    HTTPException 400
        On any validation failure.
    """
    # ── Extension check ──────────────────────────────────────────────
    filename = file.filename or ""
    if not filename.lower().endswith((".html", ".htm")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid file extension: '{filename}'. "
                "Only .html and .htm files are accepted."
            ),
        )

    # ── Content-type check (lenient — some clients omit it) ──────────
    if file.content_type and file.content_type not in (
        "text/html",
        "application/octet-stream",  # some upload tools default to this
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid content type: '{file.content_type}'. "
                "Expected 'text/html'."
            ),
        )

    # ── Read and size check ──────────────────────────────────────────
    raw_bytes = await file.read()
    if len(raw_bytes) > settings.max_html_file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"HTML file too large ({len(raw_bytes):,} bytes). "
                f"Maximum allowed: {settings.MAX_HTML_FILE_SIZE_MB} MB."
            ),
        )

    if len(raw_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded HTML file is empty.",
        )

    # ── UTF-8 decode ─────────────────────────────────────────────────
    try:
        html_content = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="HTML file is not valid UTF-8.",
        )

    # ── Minimal HTML sanity check ────────────────────────────────────
    if not re.search(r"<[a-zA-Z][^>]*>", html_content):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File does not appear to contain valid HTML markup.",
        )

    return html_content
