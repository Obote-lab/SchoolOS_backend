from rest_framework.exceptions import APIException
from rest_framework import status


class SchoolOSException(APIException):
    """Base exception for the entire platform."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "A platform error occurred."
    default_code = "schoolos_error"


class ValidationError(SchoolOSException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Invalid input."
    default_code = "validation_error"


class PermissionDenied(SchoolOSException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "You do not have permission to perform this action."
    default_code = "permission_denied"


class NotFound(SchoolOSException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "Resource not found."
    default_code = "not_found"


class ConflictError(SchoolOSException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Conflict with current state of the resource."
    default_code = "conflict"


class SchoolContextMissing(SchoolOSException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "School context is required for this operation."
    default_code = "school_context_missing"



class AuthenticationFailed(SchoolOSException):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = ""
    default_code = ""

class RateLimitExceeded(SchoolOSException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = ""
    default_code = ""
    

class BusinessRuleViolation(SchoolOSException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = ""
    default_code = ""
    