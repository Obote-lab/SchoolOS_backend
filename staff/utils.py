from django.core.exceptions import ValidationError
from django.utils import timezone

from core.choices.staff import StaffTypeChoices


def generate_staff_id(school, staff_type: str | None = None) -> str:
    """
    Generate a unique staff ID in the format:

        SCHOOLCODE-PREFIX-NNNN

    Examples:
        NBS-TCH-0001
        SCH-KE-ABC-PRN-0005
    """
    if not school:
        raise ValueError("School is required to generate a staff ID")

    # Prefer system_school_code, then school_code, then name fallback
    school_code = (
        getattr(school, "system_school_code", None)
        or getattr(school, "school_code", None)
        or (school.school_name[:5].upper() if school.school_name else "SCH")
    )
    school_code = str(school_code)[:8].upper().replace(" ", "")

    # Map staff_type → short prefix
    prefix_map = {
        StaffTypeChoices.TEACHER: "TCH",
        StaffTypeChoices.PRINCIPAL: "PRN",
        StaffTypeChoices.DEPUTY: "DEP",
        StaffTypeChoices.HOD: "HOD",
        StaffTypeChoices.ADMIN: "ADM",
        StaffTypeChoices.MATRON: "MTN",
        StaffTypeChoices.SECURITY: "SEC",
        StaffTypeChoices.DRIVER: "DRV",
        StaffTypeChoices.COOK: "COK",
        StaffTypeChoices.NURSE: "NRS",
        StaffTypeChoices.LIBRARIAN: "LIB",
        StaffTypeChoices.LAB_TECH: "LAB",
        StaffTypeChoices.OTHER: "STF",
    }

    prefix = prefix_map.get(staff_type, "STF")
    base = f"{school_code}-{prefix}-"

    last_staff = (
        school.staff_members.filter(staff_id__startswith=base)
        .order_by("-staff_id")
        .first()
    )

    seq = 1
    if last_staff:
        try:
            seq = int(last_staff.staff_id.split("-")[-1]) + 1
        except (ValueError, IndexError):
            seq = 1

    return f"{base}{seq:04d}"


def validate_id_number(id_number: str | None) -> str:
    """
    Validate a Kenyan national ID number.
    Must be exactly 8 digits.
    """
    if not id_number:
        return ""

    cleaned = str(id_number).strip()
    if not cleaned.isdigit() or len(cleaned) != 8:
        raise ValidationError(
            "National ID number must be exactly 8 digits (e.g. 12345678)."
        )

    return cleaned