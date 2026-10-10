"""
File storage utilities for the Admin CMS.

Provides three core capabilities:

1. **HTML ingestion** – read an uploaded ``.html`` file, validate it,
   and return the raw HTML string for database persistence.
2. **Attachment upload** – save a validated file (PDF / PPTX / XLSX)
   to the local ``uploads/attachments/`` directory and return its
   public URL + byte size.
3. **Attachment deletion** – remove a previously uploaded file from
   disk given its public URL.

File Layout::

    uploads/
    └── attachments/
        └── {topic_id}/
            └── {uuid}_{sanitized_filename}

Design Notes
~~~~~~~~~~~~
* Filenames are prefixed with a short UUID to guarantee uniqueness
  without complex collision handling.
* The storage interface is intentionally synchronous for disk I/O
  (uses ``aiofiles`` for non-blocking writes in the async context).
* Swapping to S3/GCS later only requires replacing the three public
  functions; no caller code changes needed.
"""

import re
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings

# ── Mime-type → file_type mapping (for topic_attachments.file_type) ──────
_MIME_TO_FILE_TYPE: dict[str, str] = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
}

# ── Directory setup ─────────────────────────────────────────────────────
_UPLOAD_ROOT = Path(settings.UPLOAD_DIR)
_ATTACHMENTS_DIR = _UPLOAD_ROOT / "attachments"


def _ensure_dirs(topic_id: uuid.UUID) -> Path:
    """Create the per-topic attachment directory if it doesn't exist."""
    topic_dir = _ATTACHMENTS_DIR / str(topic_id)
    topic_dir.mkdir(parents=True, exist_ok=True)
    return topic_dir


def _sanitize_filename(name: str) -> str:
    """
    Strip path separators, collapse whitespace, and remove special
    characters from a filename to prevent path-traversal attacks
    and filesystem issues.
    """
    # Take only the basename (strip any directory components)
    name = Path(name).name
    # Replace whitespace with underscores
    name = re.sub(r"\s+", "_", name)
    # Remove anything that isn't alphanumeric, dot, hyphen, or underscore
    name = re.sub(r"[^\w.\-]", "", name)
    return name or "unnamed"


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


# ═══════════════════════════════════════════════════════════════════════════
# 2. ATTACHMENT UPLOAD
# ═══════════════════════════════════════════════════════════════════════════


class AttachmentResult:
    """Return value from ``save_attachment`` with file metadata."""

    __slots__ = ("file_url", "file_type", "file_size_bytes")

    def __init__(
        self, file_url: str, file_type: str, file_size_bytes: int
    ) -> None:
        self.file_url = file_url
        self.file_type = file_type
        self.file_size_bytes = file_size_bytes


async def save_attachment(
    file: UploadFile,
    topic_id: uuid.UUID,
) -> AttachmentResult:
    """
    Validate, save an uploaded attachment to disk, and return metadata.

    Validations
    ~~~~~~~~~~~
    * MIME type must be in the allowed set (PDF, PPTX, XLSX).
    * File size must not exceed ``MAX_ATTACHMENT_FILE_SIZE_MB``.

    File Naming
    ~~~~~~~~~~~
    Files are saved as ``{short_uuid}_{sanitized_original_name}`` inside
    ``uploads/attachments/{topic_id}/`` to guarantee uniqueness.

    Parameters
    ----------
    file
        The ``UploadFile`` from a multipart form submission.
    topic_id
        The topic this attachment belongs to (used for directory structure).

    Returns
    -------
    AttachmentResult
        Contains ``file_url``, ``file_type``, and ``file_size_bytes``.

    Raises
    ------
    HTTPException 400
        On validation failure (bad MIME type or file too large).
    """
    # ── MIME type validation ─────────────────────────────────────────
    content_type = file.content_type or ""
    if content_type not in settings.allowed_attachment_mimes:
        allowed = ", ".join(
            _MIME_TO_FILE_TYPE.get(m, m)
            for m in sorted(settings.allowed_attachment_mimes)
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported file type: '{content_type}'. "
                f"Allowed types: {allowed}."
            ),
        )

    file_type = _MIME_TO_FILE_TYPE.get(content_type, "unknown")

    # ── Read and size check ──────────────────────────────────────────
    raw_bytes = await file.read()
    file_size = len(raw_bytes)

    if file_size > settings.max_attachment_file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"File too large ({file_size:,} bytes). "
                f"Maximum allowed: {settings.MAX_ATTACHMENT_FILE_SIZE_MB} MB."
            ),
        )

    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    # ── Build unique filename and save ───────────────────────────────
    topic_dir = _ensure_dirs(topic_id)
    original_name = _sanitize_filename(file.filename or f"file.{file_type}")
    short_id = uuid.uuid4().hex[:8]
    safe_name = f"{short_id}_{original_name}"
    file_path = topic_dir / safe_name

    file_path.write_bytes(raw_bytes)

    # ── Build public URL ─────────────────────────────────────────────
    # URL: /static/uploads/attachments/{topic_id}/{filename}
    relative_path = file_path.relative_to(_UPLOAD_ROOT)
    file_url = f"{settings.UPLOAD_URL_PREFIX}/{relative_path.as_posix()}"

    return AttachmentResult(
        file_url=file_url,
        file_type=file_type,
        file_size_bytes=file_size,
    )


# ═══════════════════════════════════════════════════════════════════════════
# 3. ATTACHMENT DELETION
# ═══════════════════════════════════════════════════════════════════════════


def delete_attachment(file_url: str) -> bool:
    """
    Delete a previously uploaded attachment from disk.

    Parameters
    ----------
    file_url
        The public URL stored in ``topic_attachments.file_url``,
        e.g. ``/static/uploads/attachments/{topic_id}/{filename}``.

    Returns
    -------
    bool
        ``True`` if the file was found and deleted, ``False`` if the
        file was already missing (idempotent — not an error).
    """
    # Strip the URL prefix to get the relative path within uploads/
    prefix = settings.UPLOAD_URL_PREFIX
    if not file_url.startswith(prefix):
        return False

    relative = file_url[len(prefix) :].lstrip("/")
    file_path = _UPLOAD_ROOT / relative

    # Security: ensure the resolved path is still within UPLOAD_DIR
    try:
        file_path.resolve().relative_to(_UPLOAD_ROOT.resolve())
    except ValueError:
        # Path traversal attempt
        return False

    if file_path.is_file():
        file_path.unlink()
        # Clean up empty topic directory
        parent = file_path.parent
        if parent != _ATTACHMENTS_DIR and not any(parent.iterdir()):
            parent.rmdir()
        return True

    return False
