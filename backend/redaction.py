# Privacy, Redaction and Masking Utility for Mavunqo WhatsApp Platform
import re
import hashlib
import hmac
import os
import json

SECRET_KEY = os.environ.get("MAVUNQO_SECRET_KEY", "mavunqo_dev_secret_key_sosua_2026")

# Comprehensive Phone Number Regex (E.164, Dominican Republic 809/829/849, US, Intl)
PHONE_REGEX = re.compile(
    r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}|\+?[1-9]\d{9,14}'
)

def hash_phone(phone: str) -> str:
    """Produces a secure irreversible HMAC hash of a phone number for deduplication & indexing."""
    clean = re.sub(r'[^\d+]', '', phone or '')
    return hmac.new(SECRET_KEY.encode('utf-8'), clean.encode('utf-8'), hashlib.sha256).hexdigest()

def hash_phone_number(phone: str) -> str:
    """Alias for hash_phone."""
    return hash_phone(phone)

def generate_customer_alias(phone: str, location_name: str = "Sosúa") -> str:
    """Generates an opaque, human-friendly masked alias (e.g., 'Guest #C82A (Sosúa)')."""
    h = hash_phone(phone)
    code = h[:4].upper()
    return f"Guest #{code} ({location_name})"

def mask_phone_for_display(phone: str) -> str:
    """Masks phone number showing only last 2 digits, or completely redacts."""
    clean = re.sub(r'[^\d+]', '', phone or '')
    if len(clean) >= 4:
        return f"+***-***-**{clean[-2:]}"
    return "+***-***-****"

def mask_phone_number(phone: str) -> str:
    """Alias for mask_phone_for_display."""
    return mask_phone_for_display(phone)

def redact_text(text: str) -> str:
    """Redacts any phone numbers or sensitive identifiers from text, logs, prompts, or error traces."""
    if not text:
        return ""
    return PHONE_REGEX.sub("[REDACTED_PHONE]", str(text))

def redact_dict(data: dict) -> dict:
    """Recursively redacts phone numbers from dictionary values and known phone keys."""
    if not isinstance(data, dict):
        return data
    redacted = {}
    for k, v in data.items():
        if k in ("customer_phone", "phone", "sender_phone", "raw_phone", "whatsapp_number"):
            redacted[k] = "[REDACTED_PHONE]"
        elif isinstance(v, str):
            redacted[k] = redact_text(v)
        elif isinstance(v, dict):
            redacted[k] = redact_dict(v)
        elif isinstance(v, list):
            redacted[k] = [redact_dict(i) if isinstance(i, dict) else (redact_text(i) if isinstance(i, str) else i) for i in v]
        else:
            redacted[k] = v
    return redacted
