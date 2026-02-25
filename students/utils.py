import re
from datetime import date
from django.core.exceptions import ValidationError
from django.utils import timezone


def validate_age(date_of_birth, min_age=3, max_age=25):
    """Validate student age range (used in Student.clean())"""
    if not date_of_birth:
        return

    today = timezone.now().date()
    age = today.year - date_of_birth.year - (
        (today.month, today.day) < (date_of_birth.month, date_of_birth.day)
    )

    if age < min_age:
        raise ValidationError(f"Student must be at least {min_age} years old.")
    if age > max_age:
        raise ValidationError(f"Student cannot be older than {max_age} years.")


def validate_phone_number(phone: str) -> str:
    """Normalize and validate Kenyan phone number"""
    if not phone:
        return ""

    phone = str(phone).strip().replace(" ", "").replace("-", "")

    patterns = [
        r"^\+2547\d{8}$",
        r"^2547\d{8}$",
        r"^07\d{8}$",
        r"^7\d{8}$",
    ]

    for pattern in patterns:
        if re.match(pattern, phone):
            if phone.startswith("0"):
                return "+254" + phone[1:]
            if phone.startswith("254"):
                return "+" + phone
            if phone.startswith("7") and len(phone) == 9:
                return "+254" + phone
            if phone.startswith("+254"):
                return phone
    raise ValidationError("Invalid Kenyan phone number format.")


def generate_admission_number(school):
    """Generate unique admission number: SCHOOLCODE/YEAR/SEQ"""
    year = timezone.now().year
    prefix = f"{school.school_code or school.system_school_code[:6].upper()}/{year}/"

    last = school.students.filter(
        admission_number__startswith=prefix
    ).order_by('-admission_number').first()

    if last:
        try:
            seq = int(last.admission_number.split('/')[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    else:
        seq = 1

    return f"{prefix}{seq:04d}"