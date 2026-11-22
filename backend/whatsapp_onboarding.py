"""
Anonymous WhatsApp Merchant Onboarding & Storefront Update Pipeline.
Parses incoming WhatsApp messages (hours, GPS pins, service/price updates, photos)
without exposing brand/company identity in outbound replies until further notice.
"""
import json
import re
import uuid
from typing import Dict, Any, Optional, List
from backend.db import get_connection


class WhatsAppMerchantIntake:
    """Handles anonymous WhatsApp-based onboarding and storefront updates."""

    def __init__(self, db_path: str, brand_anonymous: bool = True):
        self.db_path = db_path
        self.brand_anonymous = brand_anonymous

    def parse_message(self, message_text: str) -> Dict[str, Any]:
        """Extracts structured storefront fields from free-form Spanish/English WhatsApp text."""
        text = (message_text or "").strip()
        parsed: Dict[str, Any] = {
            "gps_pin": None,
            "hours": None,
            "service_updates": [],
            "notes": text,
        }

        # 1. Decimal GPS coordinates e.g. 19.787583, -70.692389
        dec_match = re.search(r'(-?\d{1,2}\.\d{4,})\s*,\s*(-?\d{1,3}\.\d{4,})', text)
        if dec_match:
            parsed["gps_pin"] = {
                "lat": float(dec_match.group(1)),
                "lng": float(dec_match.group(2)),
            }

        # 2. Hours e.g. "8:00 AM - 4:00 PM" or "9AM a 7PM"
        hr_match = re.search(
            r'(\d{1,2}(?::\d{2})?\s*(?:am|pm)?\s*(?:-|to|a|at)\s*\d{1,2}(?::\d{2})?\s*(?:am|pm))',
            text,
            re.IGNORECASE,
        )
        if hr_match:
            parsed["hours"] = hr_match.group(1).strip()

        # 3. Service + Price lines e.g. "Masaje Relajante 60 min: 3000 DOP"
        for line in text.splitlines():
            srv_match = re.match(
                r'^\s*[-*]?\s*(.+?)\s*[:\-]\s*(?:RD\$|DOP|\$)?\s*(\d{3,6})(?:\s*(?:DOP|RD\$))?\s*$',
                line,
                re.IGNORECASE,
            )
            if srv_match:
                parsed["service_updates"].append({
                    "name": srv_match.group(1).strip(),
                    "price_dop": float(srv_match.group(2)),
                })

        return parsed

    def ingest_message(self, sender_phone: str, message_text: str, media_urls: Optional[List[str]] = None) -> Dict[str, Any]:
        """Logs an incoming WhatsApp merchant update and returns a neutral, brand-anonymous reply."""
        parsed = self.parse_message(message_text)
        if media_urls:
            parsed["media_urls"] = media_urls

        clean_phone = re.sub(r'\D', '', sender_phone or "")
        intake_id = f"intk_{uuid.uuid4().hex[:12]}"
        business_id = None

        with get_connection(self.db_path) as conn:
            if clean_phone:
                row = conn.execute(
                    "SELECT id FROM businesses WHERE REPLACE(REPLACE(REPLACE(phone, '+', ''), '-', ''), ' ', '') LIKE ? LIMIT 1",
                    (f"%{clean_phone[-10:]}",)
                ).fetchone()
                if row:
                    business_id = row["id"]

            conn.execute("""
                INSERT INTO merchant_intake_logs (id, sender_phone, business_id, raw_message, parsed_json, brand_anonymous, status)
                VALUES (?, ?, ?, ?, ?, ?, 'pending_review')
            """, (
                intake_id,
                sender_phone,
                business_id,
                message_text,
                json.dumps(parsed),
                1 if self.brand_anonymous else 0
            ))
            conn.commit()

        # Strictly neutral, zero-brand reply when brand_anonymous=True
        reply_es = "Recibido, muchas gracias. Ya anotamos tu información y la estaremos actualizando."
        if parsed["service_updates"] or parsed["hours"] or parsed["gps_pin"]:
            reply_es = "Recibido, muchas gracias. Ya registramos los detalles enviados para actualizar tu perfil."

        return {
            "intake_id": intake_id,
            "business_id": business_id,
            "parsed": parsed,
            "brand_anonymous": self.brand_anonymous,
            "reply_es": reply_es
        }
