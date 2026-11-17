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
