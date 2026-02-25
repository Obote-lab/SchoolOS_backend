import re
from django.core.exceptions import ValidationError
from django.utils import timezone


def generate_staff_id(school, staff_type=None):
    """
    Generate unique staff ID in format: SCHOOLCODE-PREFIX-NNNN
    Example: NAI-TCH-0001, NAI-PRN-0005
    """
    school_code = (school.school_code or school.system_school_code[:3]).upper()

    prefix_map = {
        "teacher": "TCH",
        "principal": "PRN",
        "deputy_principal": "DEP",
        "hod": "HOD",
        "admin": "ADM",
        "support": "SUP",
    }
    prefix = prefix_map.get(staff_type or "support", "STF")

    last_staff = school.staff_members.filter(
        staff_id__startswith=f"{school_code}-{prefix}-"
    ).order_by("-staff_id").first()

    seq = 1
    if last_staff:
        try:
            seq = int(last_staff.staff_id.split("-")[-1]) + 1
        except (ValueError, IndexError):
            seq = 1

    return f"{school_code}-{prefix}-{seq:04d}"


def validate_id_number(id_number: str | None) -> str:
    """
    Validate Kenyan national ID number (must be exactly 8 digits).
    Returns cleaned string or empty string if None.
    Raises ValidationError on invalid format.
    """
    if not id_number:
        return ""

    cleaned = str(id_number).strip()
    if not cleaned.isdigit() or len(cleaned) != 8:
        raise ValidationError("National ID number must be exactly 8 digits")

    return cleaned