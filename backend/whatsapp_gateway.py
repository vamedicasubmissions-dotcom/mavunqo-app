import hmac
import hashlib
import time
import json
import re
import uuid
from typing import Dict, Any, Optional, Tuple, List
from backend.db import get_connection
from backend.redaction import hash_phone_number, mask_phone_number, generate_customer_alias, redact_text

DEFAULT_APP_SECRET = "mavunqo_wa_webhook_secret_2026"

def verify_webhook_signature(payload_bytes: bytes, signature_header: str, secret: str = DEFAULT_APP_SECRET) -> bool:
    """
    Verify X-Hub-Signature-256 header from WhatsApp Business Platform (Meta).
    Header format: 'sha256=abcdef...'
    """
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    received_hash = signature_header.split("sha256=")[1].strip()
    expected_hash = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(received_hash, expected_hash)

def record_and_check_idempotency(db_path: str, event_id: str, message_id: str, event_type: str, raw_payload: str) -> bool:
    """
    Check if event has already been processed. If yes, returns False (replay detected).
    If new, records event and returns True.
    """
    conn = get_connection(db_path)
    try:
        # Check duplicate
        row = conn.execute(
            "SELECT id, status FROM whatsapp_webhook_events WHERE event_id = ? OR (message_id = ? AND message_id IS NOT NULL)",
            (event_id, message_id)
        ).fetchone()
        if row:
            return False  # Already seen

        rec_id = f"wwe_{uuid.uuid4().hex[:12]}"
        phone_hash = hashlib.sha256(raw_payload.encode('utf-8')).hexdigest()[:16]
        conn.execute(
            """
            INSERT INTO whatsapp_webhook_events (id, event_id, message_id, phone_hash, payload_json, status)
            VALUES (?, ?, ?, ?, ?, 'processed')
            """,
            (rec_id, event_id, message_id, phone_hash, raw_payload)
        )
        conn.commit()
        return True
    finally:
        conn.close()

def get_customer_consent(db_path: str, customer_phone: str) -> Dict[str, Any]:
    """Retrieve consent status for a customer phone."""
    phone_hash = hash_phone_number(customer_phone)
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT transactional_consent, marketing_consent, opted_out, opted_out_at, updated_at FROM customer_consents WHERE phone_hash = ?",
            (phone_hash,)
        ).fetchone()
        if not row:
            return {
                "phone_hash": phone_hash,
                "transactional_consent": 0,
                "marketing_consent": 0,
                "opt_out_at": None,
                "exists": False
            }
        return {
            "phone_hash": phone_hash,
            "transactional_consent": row["transactional_consent"],
            "marketing_consent": row["marketing_consent"],
            "opt_out_at": row["opted_out_at"],
            "exists": True
        }
    finally:
        conn.close()

def update_customer_consent(db_path: str, customer_phone: str, transactional: bool, marketing: bool, source: str = "whatsapp_opt_in") -> None:
    """Update or record customer consent separated by transactional and marketing channels."""
    phone_hash = hash_phone_number(customer_phone)
    conn = get_connection(db_path)
    try:
        opted_out = 0 if transactional else 1
        conn.execute(
            """
            INSERT INTO customer_consents (phone_hash, transactional_consent, marketing_consent, opted_out, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(phone_hash) DO UPDATE SET
                transactional_consent = excluded.transactional_consent,
                marketing_consent = excluded.marketing_consent,
                opted_out = excluded.opted_out,
                updated_at = CURRENT_TIMESTAMP
            """,
            (phone_hash, 1 if transactional else 0, 1 if marketing else 0, opted_out)
        )
        conn.commit()
    finally:
        conn.close()

def process_inbound_opt_keywords(db_path: str, customer_phone: str, message_text: str) -> Optional[str]:
    """
    Handle WhatsApp compliance keywords: STOP, UNSUBSCRIBE, BAJA, ALTA, START.
    Returns response string if handled, or None if regular conversational message.
    """
    clean_text = message_text.strip().upper()
    if clean_text in ["STOP", "UNSUBSCRIBE", "CANCEL", "BAJA", "DETENER"]:
        update_customer_consent(db_path, customer_phone, transactional=False, marketing=False, source="whatsapp_opt_out_keyword")
        return "Has sido dado de baja de los mensajes de MAVUNQO. No recibirás más notificaciones. Escribe START o ALTA en cualquier momento para volver a activarlos."
    elif clean_text in ["START", "ALTA", "YES", "SI"]:
        update_customer_consent(db_path, customer_phone, transactional=True, marketing=False, source="whatsapp_opt_in_keyword")
        return "¡Gracias! Has reactivado las notificaciones transaccionales para tus pedidos en MAVUNQO."
    return None
