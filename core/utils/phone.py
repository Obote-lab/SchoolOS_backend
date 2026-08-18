"""
Phone number utilities for SchoolOS.

Primary focus: Kenya (+254)
Designed to be easily extended for other African countries.
"""

from __future__ import annotations

import re
from typing import Optional


# Country configurations
COUNTRY_CONFIG = {
    "KE": {
        "country_code": "254",
        "international_prefix": "+254",
        # Mobile prefixes after removing leading 0 or country code
        "mobile_prefixes": ("7", "1"),          # 07xx / 01xx
        "valid_local_lengths": (9,),            # 7xxxxxxxx or 1xxxxxxxx (9 digits)
        "example": "+254712345678",
    },
    # Future examples (uncomment / expand when needed)
    # "UG": {
    #     "country_code": "256",
    #     "international_prefix": "+256",
    #     "mobile_prefixes": ("7",),
    #     "valid_local_lengths": (9,),
    #     "example": "+256712345678",
    # },
    # "TZ": {
    #     "country_code": "255",
    #     "international_prefix": "+255",
    #     "mobile_prefixes": ("6", "7"),
    #     "valid_local_lengths": (9,),
    #     "example": "+255712345678",
    # },
}


DEFAULT_COUNTRY = "KE"

# Helpers
def _clean_phone(phone: str) -> str:
    """Remove spaces, dashes, brackets and other common separators."""
    if not phone:
        return ""
    phone = str(phone).strip()
    phone = re.sub(r"[\s\-\(\)\.]", "", phone)
    return phone


def _is_valid_kenyan_local(local_number: str) -> bool:
    """
    Validate the local part of a Kenyan number (after country code / leading 0).
    Accepts:
        7xxxxxxxx   (Safaricom, Airtel, etc.)
        1xxxxxxxx   (mainly Equitel / some others)
    """
    if len(local_number) != 9:
        return False
    return local_number[0] in ("7", "1") and local_number.isdigit()


# Main public functions
def normalize_phone(phone: str, country: str = DEFAULT_COUNTRY) -> Optional[str]:
    """
    Normalize a phone number to E.164 format.

    Currently fully supports Kenya (+254).
    Returns None if the number is clearly invalid.

    Supported Kenyan input formats:
        +254712345678
        254712345678
        0712345678
        0112345678          ← 01x numbers
        712345678
        112345678
        +254 712 345 678
        07-12-345-678
        etc.
    """
    if not phone:
        return None

    phone = _clean_phone(phone)
    country = country.upper()

    if country not in COUNTRY_CONFIG:
        # Unknown country – return cleaned version as-is (or raise)
        return phone if phone.startswith("+") else f"+{phone}"

    config = COUNTRY_CONFIG[country]
    country_code = config["country_code"]
    intl_prefix = config["international_prefix"]


    # Kenya-specific logic (most common case)
    if country == "KE":
        # Already in E.164
        if phone.startswith("+254"):
            local = phone[4:]
            if _is_valid_kenyan_local(local):
                return phone
            return None

        # Starts with 254 (without +)
        if phone.startswith("254"):
            local = phone[3:]
            if _is_valid_kenyan_local(local):
                return f"+{phone}"
            return None

        # Starts with 0 (local format: 07xxxxxxxx or 01xxxxxxxx)
        if phone.startswith("0"):
            local = phone[1:]
            if _is_valid_kenyan_local(local):
                return f"+254{local}"
            return None

        # Starts with 7 or 1 (missing leading 0)
        if phone.startswith(("7", "1")) and len(phone) == 9:
            if _is_valid_kenyan_local(phone):
                return f"+254{phone}"
            return None

        # Anything else is invalid for Kenya
        return None

    # Generic fallback for other countries (future)
    if phone.startswith(intl_prefix):
        return phone
    if phone.startswith(country_code):
        return f"+{phone}"
    if phone.startswith("0"):
        return f"{intl_prefix}{phone[1:]}"

    return f"{intl_prefix}{phone}"


def normalize_kenyan_phone(phone: str) -> Optional[str]:
    """
    Convenience wrapper – always forces Kenya.
    Preferred function to use inside Kenyan school logic.
    """
    return normalize_phone(phone, country="KE")


def is_valid_kenyan_phone(phone: str) -> bool:
    """Quick validation helper."""
    normalized = normalize_kenyan_phone(phone)
    return normalized is not None


def format_phone_for_display(phone: str, country: str = DEFAULT_COUNTRY) -> str:
    """
    Nice display format for UI.
    Kenya example: +254 712 345 678
    """
    normalized = normalize_phone(phone, country)
    if not normalized:
        return phone or ""

    if country == "KE" and normalized.startswith("+254"):
        local = normalized[4:]
        return f"+254 {local[:3]} {local[3:6]} {local[6:]}"

    return normalized


# Django validator (for model fields)
def validate_kenyan_phone(value: str):
    """
    Django model / form validator.
    Usage:
        phone = models.CharField(..., validators=[validate_kenyan_phone])
    """
    from django.core.exceptions import ValidationError

    if not value:
        return

    if not is_valid_kenyan_phone(value):
        raise ValidationError(
            "Enter a valid Kenyan phone number. "
            "Examples: +254712345678, 0712345678, 0112345678"
        )