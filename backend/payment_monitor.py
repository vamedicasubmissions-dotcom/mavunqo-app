"""
MAVUNQO Payment Email Alert & Bank Inbox Monitor
- Sends outbound alert emails (with optional customer screenshot attachment) to a single monitored inbox
  whenever a Zelle or Bank Transfer order is placed.
- Checks the monitored inbox via IMAP for real bank deposit notifications (Zelle / Banreservas / Popular / BHD)
  so dispatch can verify the payment actually arrived.
"""

import email
import email.utils
import imaplib
import os
import re
import smtplib
from email.message import EmailMessage
from email.header import decode_header


def get_smtp_config():
    return {
        "host": os.environ.get("MAVUNQO_SMTP_HOST", "smtp.gmail.com"),
        "port": int(os.environ.get("MAVUNQO_SMTP_PORT", "587")),
        "user": os.environ.get("MAVUNQO_SMTP_USER", "").strip(),
        "password": os.environ.get("MAVUNQO_SMTP_PASS", "").strip(),
        "alert_email": os.environ.get("MAVUNQO_PAYMENT_ALERT_EMAIL", "").strip(),
    }


def get_imap_config():
    return {
        "host": os.environ.get("MAVUNQO_IMAP_HOST", "imap.gmail.com"),
        "port": int(os.environ.get("MAVUNQO_IMAP_PORT", "993")),
        "user": os.environ.get("MAVUNQO_IMAP_USER", os.environ.get("MAVUNQO_SMTP_USER", "")).strip(),
        "password": os.environ.get("MAVUNQO_IMAP_PASS", os.environ.get("MAVUNQO_SMTP_PASS", "")).strip(),
    }


def send_payment_alert_email(order_info: dict, proof_file_path: str = None) -> dict:
    """
    Sends an email notification to the configured monitoring inbox for Zelle / Bank Transfer orders.
    Attaches the customer's payment screenshot if available.
    """
    cfg = get_smtp_config()
    if not cfg["user"] or not cfg["password"] or not cfg["alert_email"]:
        return {"sent": False, "reason": "SMTP or MAVUNQO_PAYMENT_ALERT_EMAIL not configured"}

    order_num = order_info.get("order_number", "MVQ-UNKNOWN")
    method = (order_info.get("payment_method") or "zelle").upper()
    total_dop = float(order_info.get("total") or 0.0)
    total_usd = round(total_dop / 60.0, 2)
    cust_name = order_info.get("customer_name", "Customer")
    cust_phone = order_info.get("customer_phone", "")
    biz_name = order_info.get("business_name", "Merchant")

    msg = EmailMessage()
    msg["Subject"] = f"[MAVUNQO PAYMENT] {method} - {order_num} - ${total_usd:.2f} USD / RD$ {total_dop:.2f}"
    msg["From"] = cfg["user"]
    msg["To"] = cfg["alert_email"]

    body = (
        f"MAVUNQO Payment Verification Alert\n"
        f"==================================\n"
        f"Order Number: {order_num}\n"
        f"Payment Method: {method}\n"
        f"Expected USD (Zelle): ${total_usd:.2f} USD\n"
        f"Expected DOP (Transfer): RD$ {total_dop:.2f} DOP\n"
        f"Business: {biz_name}\n"
        f"Customer: {cust_name} ({cust_phone})\n"
        f"Proof Attached: {'Yes' if proof_file_path and os.path.exists(proof_file_path) else 'No'}\n\n"
        f"Match this alert against your bank's deposit notification email in this inbox, "
        f"then click Verify Payment in /dispatcher.\n"
    )
    msg.set_content(body)

    if proof_file_path and os.path.exists(proof_file_path):
        try:
            with open(proof_file_path, "rb") as f:
                img_bytes = f.read()
            ext = os.path.splitext(proof_file_path)[1].lower().lstrip(".") or "jpeg"
            if ext == "jpg":
                ext = "jpeg"
            msg.add_attachment(
                img_bytes,
                maintype="image",
                subtype=ext,
                filename=os.path.basename(proof_file_path),
            )
        except Exception as e:
            print(f"[PaymentMonitor] Could not attach proof image: {e}")

    try:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=10) as server:
            server.starttls()
            server.login(cfg["user"], cfg["password"])
            server.send_message(msg)
        return {"sent": True, "to": cfg["alert_email"]}
    except Exception as e:
        print(f"[PaymentMonitor] SMTP send failed: {e}")
        return {"sent": False, "reason": str(e)}


def _decode_header_str(raw_val: str) -> str:
    if not raw_val:
        return ""
    parts = decode_header(raw_val)
    out = []
    for chunk, enc in parts:
        if isinstance(chunk, bytes):
            out.append(chunk.decode(enc or "utf-8", errors="replace"))
        else:
            out.append(str(chunk))
    return "".join(out)


TRUSTED_BANK_SENDER_DOMAINS = (
    "zellepay.com",
    "wise.com",
    "transferwise.com",
    "banreservas.com",
    "popularenlinea.com",
    "bhd.com.do",
    "bancosantacruz.com.do",
    "chase.com",
    "bankofamerica.com",
    "wellsfargo.com",
    "citi.com",
    "capitalone.com",
)


def _is_trusted_bank_sender(sender_header: str) -> bool:
    _, addr = email.utils.parseaddr(sender_header or "")
    addr = (addr or "").strip().lower()
    if "@" not in addr:
        return False
    domain = addr.split("@", 1)[1]
    extra = os.environ.get("MAVUNQO_TRUSTED_BANK_DOMAINS", "")
    extra_domains = tuple(d.strip().lower() for d in extra.split(",") if d.strip())
    allowed = TRUSTED_BANK_SENDER_DOMAINS + extra_domains
    return any(domain == d or domain.endswith("." + d) for d in allowed)


def check_inbox_for_bank_deposits(limit: int = 20) -> dict:
    """
    Scans the recent emails in the monitored inbox for bank deposit notifications
    (Zelle, Banreservas, Banco Popular, BHD) and extracts received amounts.
    """
    cfg = get_imap_config()
    if not cfg["user"] or not cfg["password"]:
        return {
            "configured": False,
            "deposits": [],
            "message": "Set MAVUNQO_IMAP_USER and MAVUNQO_IMAP_PASS environment variables to enable live bank email scanning.",
        }

    deposits = []
    try:
        mail = imaplib.IMAP4_SSL(cfg["host"], cfg["port"])
        mail.login(cfg["user"], cfg["password"])
        mail.select("INBOX")
        status, msg_ids = mail.search(None, "ALL")
        if status != "OK" or not msg_ids or not msg_ids[0]:
            mail.logout()
            return {"configured": True, "deposits": []}

        ids = msg_ids[0].split()[-limit:]
        for eid in reversed(ids):
            st, msg_data = mail.fetch(eid, "(RFC822)")
            if st != "OK" or not msg_data:
                continue
            raw_email = msg_data[0][1]
            parsed = email.message_from_bytes(raw_email)
            subject = _decode_header_str(parsed.get("Subject", ""))
            sender = _decode_header_str(parsed.get("From", ""))
            date_str = parsed.get("Date", "")

            # Skip our own outbound MAVUNQO alerts
            if "[MAVUNQO PAYMENT]" in subject:
                continue

            # Reject spoofed/untrusted senders outside known bank & payment domains
            if not _is_trusted_bank_sender(sender):
                continue

            combined = f"{subject} {sender}".lower()
            is_bank_alert = any(
                kw in combined
                for kw in ("zelle", "wise", "transferwise", "banreservas", "popular", "bhd", "santa cruz", "transferencia", "deposit", "received", "recibiste")
            )
            if not is_bank_alert:
                continue

            body_text = ""
            if parsed.is_multipart():
                for part in parsed.walk():
                    if part.get_content_type() == "text/plain":
                        payload = part.get_payload(decode=True)
                        if payload:
                            body_text += payload.decode(errors="replace")
            else:
                payload = parsed.get_payload(decode=True)
                if payload:
                    body_text = payload.decode(errors="replace")

            full_text = f"{subject}\n{body_text}"
            usd_matches = re.findall(r"\$\s*([0-9]+(?:\.[0-9]{2})?)", full_text)
            dop_matches = re.findall(r"RD\$\s*([0-9,]+(?:\.[0-9]{2})?)", full_text, re.IGNORECASE)

            deposits.append({
                "from": sender,
                "subject": subject,
                "date": date_str,
                "usd_amounts": [float(x) for x in usd_matches],
                "dop_amounts": [float(x.replace(",", "")) for x in dop_matches],
            })

        mail.logout()
        return {"configured": True, "deposits": deposits}
    except Exception as e:
        return {"configured": True, "deposits": [], "error": str(e)}


def enqueue_merchant_alert(db_path: str, alert_info: dict) -> str:
    """Persists a merchant alert in notification_queue before delivery."""
    import json
    import uuid
    from .db import get_connection

    nid = f"ntf_{uuid.uuid4().hex[:12]}"
    with get_connection(db_path) as conn:
        conn.execute(
            """INSERT INTO notification_queue
               (id, kind, ref_number, business_id, business_name, merchant_email, summary, payload_json, status, attempts)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', 0)""",
            (
                nid,
                alert_info.get("kind", "ORDER"),
                alert_info.get("ref_number", ""),
                alert_info.get("business_id"),
                alert_info.get("business_name", "Merchant"),
                alert_info.get("merchant_email"),
                alert_info.get("summary", ""),
                json.dumps(alert_info),
            ),
        )
        conn.commit()
    return nid


def _attempt_alert_delivery(alert_info: dict) -> dict:
    import json
    import urllib.request

    results = {"email_sent": False, "webhook_sent": False, "error": None}
    webhook_url = os.environ.get("MAVUNQO_MERCHANT_WEBHOOK_URL", "").strip()
    if webhook_url:
        try:
            req = urllib.request.Request(
                webhook_url,
                data=json.dumps(alert_info).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5):
                results["webhook_sent"] = True
        except Exception as e:
            results["webhook_error"] = str(e)
            results["error"] = str(e)

    cfg = get_smtp_config()
    to_email = (alert_info.get("merchant_email") or cfg["alert_email"] or "").strip()
    if cfg["user"] and cfg["password"] and to_email:
        try:
            kind = alert_info.get("kind", "ORDER").upper()
            ref_num = alert_info.get("ref_number", "")
            biz_name = alert_info.get("business_name", "Merchant")
            summary = alert_info.get("summary", "")
            msg = EmailMessage()
            msg["Subject"] = f"[MAVUNQO {kind}] {ref_num} - {biz_name}"
            msg["From"] = cfg["user"]
            msg["To"] = to_email
            msg.set_content(
                f"New {kind} on MAVUNQO\n"
                f"Business: {biz_name}\n"
                f"Reference: {ref_num}\n"
                f"Details: {summary}\n\n"
                f"Open your MAVUNQO Merchant Dashboard to accept or manage this request."
            )
            with smtplib.SMTP(cfg["host"], cfg["port"], timeout=12) as server:
                server.starttls()
                server.login(cfg["user"], cfg["password"])
                server.send_message(msg)
            results["email_sent"] = True
        except Exception as e:
            results["email_error"] = str(e)
            results["error"] = str(e)
    return results


def deliver_queued_notification(db_path: str, notification_id: str, alert_info: dict) -> dict:
    from .db import get_connection

    res = _attempt_alert_delivery(alert_info)
    delivered = bool(res["email_sent"] or res["webhook_sent"])
    with get_connection(db_path) as conn:
        if delivered:
            conn.execute(
                """UPDATE notification_queue
                   SET status = 'sent', attempts = attempts + 1, last_error = NULL, sent_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (notification_id,),
            )
        else:
            err = res.get("error") or "No active SMTP or webhook transport configured"
            conn.execute(
                """UPDATE notification_queue
                   SET status = 'failed', attempts = attempts + 1, last_error = ?
                   WHERE id = ?""",
                (err, notification_id),
            )
        conn.commit()
    res["notification_id"] = notification_id
    res["status"] = "sent" if delivered else "failed"
    return res


def process_pending_notifications(db_path: str, limit: int = 20) -> dict:
    """Retries pending or previously failed notifications after a restart or transient outage."""
    import json
    from .db import get_connection

    processed = 0
    sent = 0
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """SELECT id, payload_json, kind, ref_number, business_id, business_name, merchant_email, summary
               FROM notification_queue
               WHERE status IN ('pending', 'failed') AND attempts < 5
               ORDER BY created_at ASC LIMIT ?""",
            (int(limit),),
        ).fetchall()

    for r in rows:
        processed += 1
        try:
            payload = json.loads(r["payload_json"]) if r["payload_json"] else {}
        except Exception:
            payload = {
                "kind": r["kind"],
                "ref_number": r["ref_number"],
                "business_id": r["business_id"],
                "business_name": r["business_name"],
                "merchant_email": r["merchant_email"],
                "summary": r["summary"],
            }
        out = deliver_queued_notification(db_path, r["id"], payload)
        if out["status"] == "sent":
            sent += 1
    return {"processed": processed, "sent": sent}


def send_merchant_new_order_alert(alert_info: dict, db_path: str = None) -> dict:
    """
    Sends a non-blocking locked-phone alert (email + optional webhook) to the merchant,
    backed by notification_queue when db_path is provided.
    """
    if db_path:
        nid = enqueue_merchant_alert(db_path, alert_info)
        return deliver_queued_notification(db_path, nid, alert_info)
    return _attempt_alert_delivery(alert_info)
