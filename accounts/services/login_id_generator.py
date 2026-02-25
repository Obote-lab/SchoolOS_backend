import random
import string


class LoginIDGenerator:
    """
    Generates short, human-readable login IDs in format:
    SCHOOLCODE-ROLE-6RANDOM
    Example: NBS-TCH-9K4P2M (Nairobi Boys - Teacher - random)

    - No county/gender/checksum (per user preference)
    - 6 random alphanumeric = ~2.1 billion possibilities per school+role → extremely low collision
    - Pure function: no DB queries, safe for bulk/offline Excel generation
    """

    @staticmethod
    def generate_random_part(length: int = 6) -> str:
        """Generate random uppercase alphanumeric part"""
        chars = string.ascii_uppercase + string.digits
        return "".join(random.choices(chars, k=length))

    @staticmethod
    def generate_login_id(school=None, user_type: str = "USR") -> str:
        """
        Pure function — no DB queries.

        Args:
            school: School instance (or None for system/regional users)
            user_type: 3-letter code (e.g., "STU", "TCH", "PRN", "PAR")

        Returns:
            str: formatted login ID (e.g. "NBS-TCH-9K4P2M")
        """
        # 1. School code prefix
        if school and school.system_school_code:
            school_code = school.system_school_code[:5].upper()  # up to 5 chars for readability
        else:
            school_code = "SYS"  # for root/regional/system users

        # 2. User type code
        user_type_code = (user_type or "USR").upper()[:3]

        # 3. Random part
        random_part = LoginIDGenerator.generate_random_part(6)

        # 4. Combine
        return f"{school_code}-{user_type_code}-{random_part}"

    @staticmethod
    def validate_format(login_id: str) -> bool:
        """Basic format validation (no checksum anymore)"""
        if not login_id:
            return False
        parts = login_id.split("-")
        if len(parts) != 3:
            return False
        school_code, role_code, random_part = parts
        return (
            len(school_code) >= 3 and school_code.isalnum() and
            len(role_code) == 3 and role_code.isalpha() and
            len(random_part) == 6 and random_part.isalnum()
        )