import base64
import re
from datetime import datetime


def normalize_phone(phone: str) -> str:
    """
    Convert any Kenyan phone format to 2547XXXXXXXX
    Accepts: 07..., 7..., +2547..., 2547...
    """
    if not phone:
        raise ValueError("Phone number is required")

    # Remove spaces, dashes, plus
    phone = re.sub(r"[\s\-\+]", "", phone)

    if phone.startswith("0"):
        phone = "254" + phone[1:]
    elif phone.startswith("7") and len(phone) == 9:
        phone = "254" + phone
    elif phone.startswith("254") and len(phone) == 12:
        pass
    else:
        raise ValueError(f"Invalid Kenyan phone number: {phone}")

    if not re.match(r"^2547\d{8}$", phone):
        raise ValueError(f"Phone must be in format 2547XXXXXXXX, got: {phone}")

    return phone


def generate_timestamp() -> str:
    """Safaricom requires YYYYMMDDHHmmss"""
    return datetime.now().strftime("%Y%m%d%H%M%S")


def generate_password(shortcode: str, passkey: str, timestamp: str) -> str:
    """
    Password = Base64(Shortcode + Passkey + Timestamp)
    """
    data = f"{shortcode}{passkey}{timestamp}"
    return base64.b64encode(data.encode("utf-8")).decode("utf-8")