"""Text helpers shared by extract, checks and prove."""

import re
from datetime import date

from dateutil import parser as dateparser

MONEY_RE = re.compile(r"(Rs\.?|₹|INR)\s*[\d,]+(\.\d+)?")


def normalise(s: str) -> str:
    """Lower-case, one currency spelling ("rs"), single spaces, no edge punctuation."""
    s = s.lower().replace("₹", " rs ")
    s = re.sub(r"\binr\b", "rs", s)
    s = re.sub(r"\brs\.", "rs ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip(" .,:;-")


def parse_date(s) -> date | None:
    if not s:
        return None
    s = str(s).strip()
    iso = bool(re.match(r"^\d{4}[-/.]\d{1,2}[-/.]\d{1,2}", s))
    try:
        return dateparser.parse(s, dayfirst=not iso, yearfirst=iso).date()
    except (ValueError, OverflowError):
        return None


def parse_money(v) -> float | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    cleaned = re.sub(r"(?i)rs\.?|₹|inr|,|\s", "", str(v))
    try:
        return float(cleaned)
    except ValueError:
        return None


def months_between(a: date, b: date) -> int:
    return (b.year - a.year) * 12 + b.month - a.month - (1 if b.day < a.day else 0)
