import hmac
import hashlib
import time
import secrets
import os
from typing import Dict, Any, Optional, Tuple
from urllib.parse import urlencode, parse_qs, urlparse

SECRET_KEY = os.environ.get("MAVUNQO_SECRET_KEY", "mavunqo_tamper_resistant_secret_2026_sosua")
TOKEN_VALIDITY_SECONDS = 1800  # 30 minutes

# Configurable standard commission rate (can be overridden via environment variable)
# Default is 0.15 (15%) across all acquisition channels during initial launch
STANDARD_COMMISSION_RATE = float(os.environ.get("MAVUNQO_LAUNCH_COMMISSION_RATE", "0.15"))
STANDARD_RULE_VERSION = os.environ.get("MAVUNQO_FEE_RULE_VERSION", "v1_tiered_2026")

CATEGORY_COMMISSION_RATES = {
    "cat_grocery": 0.05,        # 5% Supermarkets & Groceries
    "cat_dining": 0.09,         # 9% Restaurants & Food
    "cat_fashion": 0.10,        # 10% Clothing & Boutiques
    "cat_tourism": 0.10,        # 10% Hotels & Lodging
    "cat_auto": 0.12,           # 12% Auto Repair
    "cat_health": 0.12,         # 12% Massage & Spas
    "mavunqo_general": 0.12     # 12% Standard Platform Rate
}

def generate_attribution_signature(business_id: str, campaign: str, secret: str = SECRET_KEY) -> str:
    """Generate an HMAC-SHA256 signature for merchant attribution link."""
    msg = f"{business_id}:{campaign}"
    return hmac.new(secret.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).hexdigest()

def verify_attribution_signature(business_id: str, campaign: str, signature: str, secret: str = SECRET_KEY) -> bool:
    """Verify attribution HMAC signature. Returns True if valid, False if tampered."""
    if not business_id or not signature:
        return False
    expected = generate_attribution_signature(business_id, campaign or "", secret)
    return hmac.compare_digest(expected, signature)

def build_merchant_qr_link(base_url: str, business_id: str, campaign: str = "counter_qr", secret: str = SECRET_KEY) -> str:
    """Build a tamper-resistant merchant-acquired WhatsApp entry link."""
    sig = generate_attribution_signature(business_id, campaign, secret)
    params = {
        "m_biz": business_id,
        "m_camp": campaign,
        "m_sig": sig
    }
    return f"{base_url.rstrip('/')}/order/wa?{urlencode(params)}"

def compute_order_fee(source_type: str, subtotal: float, category_id: Optional[str] = None) -> Tuple[float, float, float, str]:
    """
    Compute order fee based on official tier rates:
    - 5% Supermarkets & Groceries
    - 9% Restaurants & Food
    - 12% Mavunqo Standard Platform Rate
    - Returns: (commission_rate, commission_amount, merchant_payout, rule_version)
    """
    if category_id and category_id in CATEGORY_COMMISSION_RATES:
        rate = CATEGORY_COMMISSION_RATES[category_id]
    else:
        rate = STANDARD_COMMISSION_RATE
    rule_version = STANDARD_RULE_VERSION
    commission_amount = round(subtotal * rate, 2)
    merchant_payout = round(subtotal - commission_amount, 2)
    return rate, commission_amount, merchant_payout, rule_version

def create_secure_order_token(order_id: str, business_id: str, expires_in: int = TOKEN_VALIDITY_SECONDS) -> Dict[str, Any]:
    """
    Generate an opaque, single-use, cryptographically random token for checkout/order confirmation.
    Contains no raw phone numbers or predictable sequential IDs.
    """
    raw_token = "mvt_" + secrets.token_urlsafe(32)
    now = int(time.time())
    expires_at = now + expires_in
    return {
        "token": raw_token,
        "order_id": order_id,
        "business_id": business_id,
        "expires_at": expires_at,
        "created_at": now,
        "status": "active"
    }
