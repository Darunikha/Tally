"""Uploaded files are untrusted input: validate name, extension, size and content signature."""
import hashlib
import os
import re

from app.core.config import get_settings
from app.core.errors import AppError

_EXCEL_TYPES = {
    "application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/x-msexcel", "application/zip", "application/x-zip-compressed", "text/html", "text/plain",
    "text/csv", "application/octet-stream", "",
}
ALLOWED = {
    "csv": {"text/csv", "application/vnd.ms-excel", "text/plain", "application/csv", "application/octet-stream", ""},
    "pdf": {"application/pdf", "application/octet-stream", ""},
    "xlsx": _EXCEL_TYPES,
    "xls": _EXCEL_TYPES,
}

ZIP_MAGIC = b"PK\x03\x04"
OLE_MAGIC = b"\xd0\xcf\x11\xe0"
PDF_MAGIC = b"%PDF"
UTF16_BOMS = (b"\xff\xfe", b"\xfe\xff")


def sanitize_filename(name: str | None) -> str:
    base = os.path.basename((name or "statement").replace("\\", "/"))
    base = re.sub(r"[^\w.\- ()]", "_", base).strip(" .") or "statement"
    return base[:150]


def detect_file_type(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED:
        raise AppError("Only CSV, PDF and Excel (.xls, .xlsx) statements are supported.", 415, "unsupported_file_type")
    return ext


def _is_text(head: bytes) -> bool:
    return b"\x00" not in head or head.startswith(UTF16_BOMS)


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

    head = content[:8192]
    if ftype == "pdf":
        if not content[:1024].lstrip().startswith(b"%PDF-"):
            raise AppError("The file is not a valid PDF.", 400, "invalid_file")
    elif ftype == "xlsx":
        # OLE is accepted: a password-protected .xlsx is an OLE container (the reader explains that case)
        if not content.startswith((ZIP_MAGIC, OLE_MAGIC)):
            raise AppError("The file is not a valid .xlsx workbook.", 400, "invalid_file")
    elif ftype == "xls":
        # real BIFF .xls (OLE), an .xlsx renamed to .xls (zip), or the HTML / delimited-text "xls" banks export
        if not (content.startswith((OLE_MAGIC, ZIP_MAGIC)) or (_is_text(head) and not head.startswith(PDF_MAGIC))):
            raise AppError("The file is not a valid .xls spreadsheet.", 400, "invalid_file")
    else:
        if not _is_text(head):
            raise AppError("The file does not look like a text CSV.", 400, "invalid_file")
        if head.startswith((ZIP_MAGIC, PDF_MAGIC, OLE_MAGIC)):
            raise AppError("The file content does not match the .csv extension (Excel/PDF detected).", 400, "invalid_file")
    return safe, ftype, hashlib.sha256(content).hexdigest()
