"""Logging setup. Never log transaction descriptions, amounts, UPI IDs or account numbers."""
import logging
import re

_VPA = re.compile(r"[A-Za-z0-9.\-_]{2,}@[A-Za-z]{2,}")
_LONG_DIGITS = re.compile(r"\d{6,}")


class RedactingFilter(logging.Filter):
    """Defence-in-depth: mask VPAs and long digit runs (account/ref numbers) if they slip into a log."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _LONG_DIGITS.sub("[redacted]", _VPA.sub("[vpa]", record.msg))
        return True


def setup_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    handler.addFilter(RedactingFilter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
