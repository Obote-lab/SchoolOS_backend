from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db import transaction

def validate_age(date_of_birth, min_age: int = 3, max_age: int = 25):
    """
    Validate that a student's age is within the allowed range.
    """
    if not date_of_birth:
        return

    today = timezone.now().date()
    age = (
        today.year
        - date_of_birth.year
        - ((today.month, today.day) < (date_of_birth.month, date_of_birth.day))
    )

    if age < min_age:
        raise ValidationError(f"Student must be at least {min_age} years old.")
    if age > max_age:
        raise ValidationError(f"Student cannot be older than {max_age} years.")


def generate_admission_number(school) -> str:
    """
    Generate a unique admission number in the format:

        SCHOOLCODE/YEAR/SEQ

    Example:
        NBS/2026/0001
        SCH-KE-ABC123/2026/0042
    """
    if not school:
        raise ValueError("School is required to generate an admission number")

    year = timezone.now().year
    school_code = (
        getattr(school, "system_school_code", None)
        or getattr(school, "school_code", None)
        or (school.school_name[:6].upper() if school.school_name else "SCH")
    )
    prefix = f"{school_code}/{year}/"

    with transaction.atomic():
        last = (
            school.students.select_for_update()
            .filter(admission_number__startswith=prefix)
            .order_by("-admission_number")
            .first()
        )
        if last:
            try:
                seq = int(last.admission_number.split("/")[-1]) + 1
            except (ValueError, IndexError):
                seq = 1
        else:
            seq = 1
        return f"{prefix}{seq:04d}"