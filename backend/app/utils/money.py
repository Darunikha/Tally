"""Amount parsing for Indian bank statements."""
import math
import re

_CLEAN = re.compile(r"[₹,\s]|INR|Rs\.?", re.IGNORECASE)


def parse_amount(value) -> float | None:
    """'1,23,456.78' -> 123456.78 ; '(500.00)' -> -500.0 ; '500.00 Dr' -> -500.0 ; '' -> None."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and math.isnan(value):
            return None
        return float(value)
    s = str(value).strip()
    if not s or s.lower() in {"nan", "none", "-", "--", "null"}:
        return None
    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative, s = True, s[1:-1]
    m = re.search(r"\b(Dr|Cr)\.?$", s, re.IGNORECASE)
    if m:
        negative = m.group(1).lower() == "dr"
        s = s[: m.start()]
    s = _CLEAN.sub("", s)
    if s.endswith("-"):
        negative, s = True, s[:-1]
    if s.startswith("-"):
        negative, s = True, s[1:]
    elif s.startswith("+"):
        s = s[1:]
    if not s:
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    return -v if negative else v


def r2(v: float | None) -> float:
    return round(float(v or 0.0), 2)
