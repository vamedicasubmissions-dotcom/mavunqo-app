"""
Authentication, Password Hashing & Session Management for Mavunqo.
Standard library only: hmac, hashlib, secrets, time, base64, os.
"""
import os
import hashlib
import hmac
import secrets
import time
import json
import base64

SECRET_KEY = os.environ.get("MAVUNQO_SECRET_KEY", "mavunqo_dev_secret_key_sosua_2026")

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100_000)
    return f"{salt}:{key.hex()}"

def verify_password(stored_password: str, provided_password: str) -> bool:
    try:
        salt, key_hex = stored_password.split(":")
        new_key = hashlib.pbkdf2_hmac('sha256', provided_password.encode('utf-8'), salt.encode('utf-8'), 100_000)
        return hmac.compare_digest(new_key.hex(), key_hex)
    except Exception:
        return False

def generate_token(user_id: str, email: str, role: str, expires_in_seconds: int = 86400 * 7) -> str:
    payload = {
        "uid": user_id,
        "email": email,
        "role": role,
        "exp": int(time.time()) + expires_in_seconds,
        "nonce": secrets.token_hex(8)
    }
    payload_bytes = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    b64_payload = base64.urlsafe_b64encode(payload_bytes).decode('utf-8').rstrip('=')
    sig = hmac.new(SECRET_KEY.encode('utf-8'), b64_payload.encode('utf-8'), hashlib.sha256).hexdigest()
    return f"{b64_payload}.{sig}"

def verify_token(token: str) -> dict | None:
    if not token or "." not in token:
        return None
    try:
        b64_payload, sig = token.split(".", 1)
        expected_sig = hmac.new(SECRET_KEY.encode('utf-8'), b64_payload.encode('utf-8'), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None
        # restore padding
        rem = len(b64_payload) % 4
        if rem > 0:
            b64_payload += '=' * (4 - rem)
        payload = json.loads(base64.urlsafe_b64decode(b64_payload.encode('utf-8')).decode('utf-8'))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None
