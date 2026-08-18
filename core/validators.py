import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def validate_kenyan_phone(value: str):
    """
    Accepts formats:
    - +2547XXXXXXXX
    - 2547XXXXXXXX
    - 07XXXXXXXX
    - 7XXXXXXXX
    """
    pattern = r"^(\+?254|0)?[17]\d{8}$"
    if not re.match(pattern, value):
        raise ValidationError(
            _("Enter a valid Kenyan phone number (e.g. +254712345678 or 0712345678).")
        )


def validate_national_id(value: str):
    if not value.isdigit() or len(value) not in (7, 8):
        raise ValidationError(_("National ID must be 7 or 8 digits."))