"""
Date & time utilities for SchoolOS.

Focused on Kenyan academic calendar realities:
- Academic years (e.g. 2025, 2025/2026)
- Three-term system
- Term boundaries
- Age calculation from date of birth
- Human-friendly formatting
- Timezone-aware helpers (Africa/Nairobi)
"""

from __future__ import annotations
from datetime import date, datetime, timedelta
from typing import Optional, Tuple, Union
from django.utils import timezone
from django.conf import settings


# Basic helpers
def today() -> date:
    """Return today's date in the project timezone (Africa/Nairobi)."""
    return timezone.localdate()


def now() -> datetime:
    """Return current datetime in the project timezone."""
    return timezone.localtime()


def make_aware(dt: datetime) -> datetime:
    """Make a naive datetime timezone-aware using the project timezone."""
    if timezone.is_aware(dt):
        return dt
    return timezone.make_aware(dt, timezone.get_current_timezone())


def to_date(value: Union[str, date, datetime, None]) -> Optional[date]:
    """
    Convert various inputs into a date object.
    Accepts: date, datetime, 'YYYY-MM-DD', 'DD/MM/YYYY', 'DD-MM-YYYY'
    """
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()

    value = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {value}")



# Age calculation (very common in schools)
def calculate_age(born: Union[date, str], on_date: Optional[date] = None) -> int:
    """
    Calculate age in full years.
    Useful for admission age checks, student profiles, etc.
    """
    if isinstance(born, str):
        born = to_date(born)
    if on_date is None:
        on_date = today()

    age = on_date.year - born.year
    if (on_date.month, on_date.day) < (born.month, born.day):
        age -= 1
    return age


def age_as_of(born: Union[date, str], on_date: Optional[date] = None) -> str:
    """
    Human readable age, e.g. "12 years 3 months"
    """
    if isinstance(born, str):
        born = to_date(born)
    if on_date is None:
        on_date = today()

    years = calculate_age(born, on_date)
    months = on_date.month - born.month
    if on_date.day < born.day:
        months -= 1
    if months < 0:
        months += 12

    parts = []
    if years > 0:
        parts.append(f"{years} year{'s' if years != 1 else ''}")
    if months > 0:
        parts.append(f"{months} month{'s' if months != 1 else ''}")
    if not parts:
        return "Less than 1 month"
    return " ".join(parts)



# Academic year helpers
def current_academic_year(as_of: Optional[date] = None) -> str:
    """
    Simple heuristic for Kenyan schools.
    Most schools run Jan–Nov/Dec.
    Returns string like "2025" or "2025/2026" depending on preference.
    """
    if as_of is None:
        as_of = today()

    # Simple version – calendar year
    return str(as_of.year)

    # Alternative (uncomment if you prefer 2025/2026 style):
    # if as_of.month >= 1:  # adjust based on your school calendar
    #     return f"{as_of.year}/{as_of.year + 1}"
    # return f"{as_of.year - 1}/{as_of.year}"


def academic_year_range(year: Union[int, str]) -> Tuple[date, date]:
    """
    Rough academic year boundaries.
    You will later override this with real data from configuration.AcademicYear.
    """
    year = int(str(year)[:4])
    start = date(year, 1, 1)
    end = date(year, 12, 31)
    return start, end


# Term helpers (Kenyan 3-term system)
def guess_current_term(as_of: Optional[date] = None) -> int:
    """
    Very rough term estimation.
    Real system should use the Term model from configuration/academics.
    """
    if as_of is None:
        as_of = today()

    month = as_of.month
    if 1 <= month <= 4:
        return 1
    if 5 <= month <= 8:
        return 2
    return 3



# Formatting helpers
def format_date(d: Union[date, datetime, str, None], fmt: str = "%d %b %Y") -> str:
    """
    Common display format used across the platform.
    Example: 27 Jul 2026
    """
    if d is None:
        return ""
    if isinstance(d, str):
        d = to_date(d)
    if isinstance(d, datetime):
        d = d.date()
    return d.strftime(fmt)


def format_datetime(dt: Union[datetime, str, None], fmt: str = "%d %b %Y %H:%M") -> str:
    if dt is None:
        return ""
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt)
    if timezone.is_naive(dt):
        dt = make_aware(dt)
    return timezone.localtime(dt).strftime(fmt)


def format_date_range(start: date, end: date) -> str:
    """Nice range display: 12 Jan – 15 Mar 2026"""
    if start.year == end.year:
        if start.month == end.month:
            return f"{start.day} – {end.day} {start.strftime('%b %Y')}"
        return f"{start.strftime('%d %b')} – {end.strftime('%d %b %Y')}"
    return f"{start.strftime('%d %b %Y')} – {end.strftime('%d %b %Y')}"


# Working days / school days helpers
def add_working_days(start: date, days: int) -> date:
    """
    Add business days (Mon–Fri). 
    Does not yet know Kenyan public holidays – that will come from configuration.
    """
    current = start
    added = 0
    while added < days:
        current += timedelta(days=1)
        if current.weekday() < 5:  # 0=Mon ... 4=Fri
            added += 1
    return current


def is_weekend(d: date) -> bool:
    return d.weekday() >= 5