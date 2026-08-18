import secrets
import string
from typing import Optional, TYPE_CHECKING



if TYPE_CHECKING:
    from schools.models import School
class LoginIDGenerator:
    """
    SchoolOS Login ID Generator
    Generates short, human-friendly login IDs for authentication.
    Login IDs identify *who logs in*.
    They DO NOT represent:
        • user role
        • permissions
        • job title
        • employment status
    Those are handled separately by the RBAC system
    (Role → UserRole → PermissionMatrix).
    Identity is handled by:
        permanent_id
    Example
        Permanent ID:USR-9QF7M2K8PX
        Login ID:NBS-R8L-2PW
    This allows a user to be:
        Teacher
        Deputy Principal
        Parent
        Driver
        Board Member

    without changing the login ID.
    Login IDs should only change when absolutely necessary,
    for example:
        • school transfer
        • institutional renaming
        • username regeneration
    """

    DEFAULT_SCHOOL_CODE = "SYS"
    DEFAULT_RANDOM_LENGTH = 6

    _CHARSET = string.ascii_uppercase + string.digits

    # Random Generation
    @classmethod
    def generate_random_part(cls, length: int = DEFAULT_RANDOM_LENGTH) -> str:
        """
        Generate a cryptographically secure random string.
        Example
            R8L2PW
            K3Q8LM
            H7X9AC
        """
        return "".join(secrets.choice(cls._CHARSET) for _ in range(length))

    # School Code
    @classmethod
    def get_school_code(cls, school) -> str:
        """
        Determine the school prefix.
        Priority
        1. system_school_code
        2. short_code
        3. SYS
        Examples NBS, KSM, KCG, SYS
        """

        if school is None:
            return cls.DEFAULT_SCHOOL_CODE

        code = (
            getattr(school, "system_school_code", None)
            or getattr(school, "short_code", None)
        )

        if code:
            return str(code)[:5].upper()

        return cls.DEFAULT_SCHOOL_CODE

    # Formatting
    @staticmethod
    def format_random_part(random_part: str) -> str:
        """
        Format random characters into readable groups.

        Examples:
            R8L2PW → R8L-2PW
            K2M9XQ → K2M-9XQ
        """

        midpoint = len(random_part) // 2
        return f"{random_part[:midpoint]}-{random_part[midpoint:]}"
    
    # Login ID Generation
    @classmethod
    def generate_login_id(
        cls,
        school: Optional["School"] = None,
        random_length: int = DEFAULT_RANDOM_LENGTH,
    ) -> str:
        """
        Generate a login ID.
        Format
            SCHOOLCODE-RANDOM
        Examples
            NBS-R8L-2PW
            KSM-H7Q-9XT
            SYS-K3M-8PQ
        """

        school_code = cls.get_school_code(school)
        random_part = cls.generate_random_part(random_length)
        formatted_random = cls.format_random_part(random_part)
        return f"{school_code}-{formatted_random}"
    
    # Validation
    @classmethod
    def validate_format(cls, login_id: str) -> bool:
        """
        Validate login ID format.

        Valid   : NBS-R8L-2PW
        Invalid : NBS-TCH-R8L2PW, NBSR8L2PW, NBS/R8L/2PW
        """

        if not isinstance(login_id, str):
            return False
        parts = login_id.strip().split("-")
        if len(parts) != 3:
            return False
        school_code, first_group, second_group = parts
        random_part = first_group + second_group
        return (
            3 <= len(school_code) <= 5
            and school_code.isalnum()
            and len(random_part) == cls.DEFAULT_RANDOM_LENGTH
            and random_part.isalnum()
        )
    # Bulk Generation
    @classmethod
    def generate_many(cls,count: int,school: Optional["School"] = None,random_length: int = DEFAULT_RANDOM_LENGTH,) -> list[str]:
        """
        Generate multiple unique login IDs.
        Database uniqueness is NOT checked.
        This method only guarantees uniqueness
        within the generated batch.
        """
        generated = set()
        while len(generated) < count:
            generated.add(
                cls.generate_login_id(
                    school=school,
                    random_length=random_length,
                )
            )

        return sorted(generated)