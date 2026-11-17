"""Uploaded files are untrusted input: validate name, extension, size and content signature."""
import hashlib
import os
import re

from app.core.config import get_settings
from app.core.errors import AppError

ALLOWED = {"csv": {"text/csv", "application/vnd.ms-excel", "text/plain", "application/csv", "application/octet-stream", ""},
           "pdf": {"application/pdf", "application/octet-stream", ""}}


def sanitize_filename(name: str | None) -> str:
    base = os.path.basename((name or "statement").replace("\\", "/"))
    base = re.sub(r"[^\w.\- ()]", "_", base).strip(" .") or "statement"
    return base[:150]


def detect_file_type(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED:
        raise AppError("Only CSV and PDF statements are supported.", 415, "unsupported_file_type")
    return ext


def validate_upload(filename: str, content_type: str | None, content: bytes) -> tuple[str, str, str]:
    """Return (safe_filename, file_type, sha256). Raises AppError on invalid input."""
    s = get_settings()
    safe = sanitize_filename(filename)
    ftype = detect_file_type(safe)
    if content_type and content_type.split(";")[0].strip().lower() not in ALLOWED[ftype]:
        raise AppError(f"Unexpected content type for a .{ftype} file.", 415, "unsupported_file_type")
    if not content:
        raise AppError("The uploaded file is empty.", 400, "empty_file")
    if len(content) > s.max_upload_bytes:
        raise AppError(f"File is larger than {s.max_upload_mb} MB.", 413, "file_too_large")
    if ftype == "pdf":
        if not content[:1024].lstrip().startswith(b"%PDF-"):
            raise AppError("The file is not a valid PDF.", 400, "invalid_file")
    else:
        head = content[:8192]
        if b"\x00" in head and not head.startswith((b"\xff\xfe", b"\xfe\xff")):
            raise AppError("The file does not look like a text CSV.", 400, "invalid_file")
        if head.startswith((b"PK\x03\x04", b"%PDF", b"\xd0\xcf\x11\xe0")):
            raise AppError("The file content does not match the .csv extension (Excel/PDF detected).", 400, "invalid_file")
    return safe, ftype, hashlib.sha256(content).hexdigest()
