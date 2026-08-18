import logging
import uuid
from datetime import timedelta
import jwt
from django.conf import settings
from django.utils import timezone
from .models import CustomUser

logger = logging.getLogger(__name__)


def generate_password_reset_token(user: CustomUser) -> str:
    """
    Generate a secure JWT for password reset.
    Token expires in 24 hours.
    """
    expires_at = timezone.now() + timedelta(hours=24)

    payload = {
        "user_id": str(user.id),
        "email": user.email or user.recovery_email,
        "exp": expires_at,
        "type": "password_reset",
        "aud": "schoolOS",
        "iss": "schoolOS.accounts",
        "jti": str(uuid.uuid4()),
    }

    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def validate_password_reset_token(token: str) -> CustomUser | None:
    """
    Decode and validate a password reset token.
    Returns the user if valid, otherwise None.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=["HS256"],
            audience="schoolOS",
            issuer="schoolOS.accounts",
        )

        if payload.get("type") != "password_reset":
            logger.warning("Invalid token type used for password reset")
            return None

        return CustomUser.objects.get(id=payload["user_id"])

    except jwt.ExpiredSignatureError:
        logger.warning("Password reset token expired")
    except (jwt.InvalidAudienceError, jwt.InvalidIssuerError, jwt.DecodeError):
        logger.warning("Invalid password reset token")
    except CustomUser.DoesNotExist:
        logger.warning("User not found for password reset token")
    except Exception:
        logger.exception("Unexpected error decoding password reset token")

    return None


def generate_account_activation_token(user: CustomUser) -> str:
    """
    Generate a secure JWT for first-time account activation.
    Token expires in 48 hours.
    """
    expires_at = timezone.now() + timedelta(hours=48)

    payload = {
        "user_id": str(user.id),
        "email": user.email or user.recovery_email,
        "exp": expires_at,
        "type": "account_activation",
        "aud": "schoolOS",
        "iss": "schoolOS.accounts",
        "jti": str(uuid.uuid4()),
    }

    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def validate_account_activation_token(token: str) -> CustomUser | None:
    """
    Validate an account activation token.
    Returns the associated user if valid, otherwise None.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=["HS256"],
            audience="schoolOS",
            issuer="schoolOS.accounts",
        )

        if payload.get("type") != "account_activation":
            logger.warning("Invalid token type used for account activation")
            return None

        return CustomUser.objects.get(id=payload["user_id"])

    except jwt.ExpiredSignatureError:
        logger.warning("Account activation token has expired")
    except (jwt.InvalidAudienceError, jwt.InvalidIssuerError, jwt.DecodeError):
        logger.warning("Invalid account activation token")
    except CustomUser.DoesNotExist:
        logger.warning("User not found for account activation token")
    except Exception:
        logger.exception("Unexpected error validating account activation token")

    return None