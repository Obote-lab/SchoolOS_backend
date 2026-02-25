import jwt
import logging
import uuid
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from .models import CustomUser, AuditLog

logger = logging.getLogger(__name__)


def generate_password_reset_token(user: CustomUser) -> str:
    """
    Generate secure JWT for password reset (no plaintext password ever sent)
    """
    payload = {
        "user_id": str(user.id),
        "email": user.email or user.recovery_email,
        "exp": int((timezone.now() + timezone.timedelta(hours=24)).timestamp()),
        "type": "password_reset",
        "aud": "schoolOS",
        "iss": "schoolOS.accounts",
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def decode_password_reset_token(token: str) -> CustomUser | None:
    """
    Decode and validate password reset token
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
            return None

        user_id = payload.get("user_id")
        return CustomUser.objects.get(id=user_id)

    except (jwt.ExpiredSignatureError, jwt.InvalidAudienceError,
            jwt.InvalidIssuerError, jwt.DecodeError, CustomUser.DoesNotExist) as e:
        logger.warning(f"Invalid/expired password reset token: {str(e)}")
        return None


def send_welcome_email(user: CustomUser) -> bool:
    """
    Send welcome email WITHOUT plaintext password.
    Instructs user to reset password on first login.
    """
    recipient = user.email or user.recovery_email
    if not recipient:
        logger.warning(f"No email available for user {user.login_id} - welcome email skipped")
        return False

    subject = "Welcome to SchoolOS - Your Account is Ready"
    context = {
        "user": user,
        "full_name": user.get_full_name(),
        "school": user.school.school_name if user.school else "the system",
        "login_id": user.login_id,
        "login_url": settings.FRONTEND_URL.rstrip("/") + "/login",
        "reset_url": settings.FRONTEND_URL.rstrip("/") + "/reset-password",
        "support_email": settings.DEFAULT_FROM_EMAIL,
    }

    html_message = render_to_string("accounts/emails/welcome.html", context)
    plain_message = render_to_string("accounts/emails/welcome.txt", context)

    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info(f"Welcome email (no temp password) sent to {user.login_id} ({recipient})")

        # Audit
        AuditLog.objects.create(
            user=None,  # system-sent
            action_type="NOTIFY",
            model_name="CustomUser",
            record_id=user.id,
            new_value="Welcome email sent (force password reset on first login)",
            reason="Account creation notification",
            school=user.school,
            timestamp=timezone.now()
        )
        return True

    except Exception as e:
        logger.error(f"Failed to send welcome email to {user.login_id}: {str(e)}")
        return False


def send_password_reset_email(user: CustomUser, request=None) -> bool:
    """
    Send password reset link (improved logging)
    """
    recipient = user.email or user.recovery_email
    if not recipient:
        logger.warning(f"No email for password reset - user {user.login_id}")
        return False

    token = generate_password_reset_token(user)
    reset_url = f"{settings.FRONTEND_URL.rstrip('/')}/reset-password/{token}"

    subject = "SchoolOS Password Reset Request"
    context = {
        "user": user,
        "reset_url": reset_url,
        "expires_hours": 24,
        "support_email": settings.DEFAULT_FROM_EMAIL,
    }

    html = render_to_string("accounts/emails/password_reset.html", context)
    plain = render_to_string("accounts/emails/password_reset.txt", context)

    try:
        send_mail(
            subject=subject,
            message=plain,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            html_message=html,
            fail_silently=False,
        )

        # Audit with more context
        AuditLog.objects.create(
            user=user,
            action_type="REQUEST_RESET",
            model_name="CustomUser",
            record_id=user.id,
            reason="Password reset requested",
            school=user.school,
            user_ip=request.META.get('REMOTE_ADDR') if request else None,
            timestamp=timezone.now()
        )

        logger.info(f"Password reset email sent to {user.login_id}")
        return True

    except Exception as e:
        logger.error(f"Password reset email failed for {user.login_id}: {e}")
        return False