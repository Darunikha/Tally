"""Date helpers. All calendar logic uses Asia/Kolkata.

Transaction dates are calendar dates from bank statements (already IST). They are stored as
naive datetimes at midnight representing that IST calendar day, so no UTC shift can move a
transaction into a different day or month.
"""
import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

IST = ZoneInfo("Asia/Kolkata")

_FORMATS = [
    "%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d-%m-%y", "%d.%m.%Y", "%d.%m.%y",
    "%d-%b-%Y", "%d-%b-%y", "%d %b %Y", "%d %b %y", "%d/%b/%Y", "%d/%b/%y",
    "%d-%B-%Y", "%d %B %Y", "%Y-%m-%d", "%Y/%m/%d", "%b %d, %Y", "%d %b, %Y",
]


def now_ist() -> datetime:
    return datetime.now(IST)


def today_ist() -> date:
    return now_ist().date()


def utcnow() -> datetime:
    return datetime.utcnow()


def parse_date(value) -> datetime | None:
    """Parse a statement date (day-first, Indian convention). Returns naive midnight datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return datetime(value.year, value.month, value.day)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    if isinstance(value, pd.Timestamp):
        return None if pd.isna(value) else datetime(value.year, value.month, value.day)
    s = str(value).strip()
    if not s or s.lower() in {"nan", "nat", "none", "-"}:
        return None
    # Drop time portion like "17/10/2025 19:45" or "2025-10-17T19:45:00"
    s = re.split(r"[ T](?=\d{1,2}:\d{2})", s)[0].strip()
    for fmt in _FORMATS:
        try:
            d = datetime.strptime(s, fmt)
            return datetime(d.year, d.month, d.day)
        except ValueError:
            continue
    try:
        d = pd.to_datetime(s, dayfirst=True, errors="raise")
        return datetime(d.year, d.month, d.day)
    except (ValueError, TypeError, OverflowError):
        return None


def to_day(d: date | datetime | str) -> datetime:
    if isinstance(d, str):
        d = date.fromisoformat(d[:10])
    return datetime(d.year, d.month, d.day)


def month_start(d: date | datetime) -> datetime:
    return datetime(d.year, d.month, 1)


def add_months(d: datetime, months: int) -> datetime:
    m = d.month - 1 + months
    return datetime(d.year + m // 12, m % 12 + 1, 1)


def month_end(d: date | datetime) -> datetime:
    """Last day of month (inclusive, midnight)."""
    return add_months(month_start(d), 1) - timedelta(days=1)


def week_start(d: datetime) -> datetime:
    d = to_day(d)
    return d - timedelta(days=d.weekday())
