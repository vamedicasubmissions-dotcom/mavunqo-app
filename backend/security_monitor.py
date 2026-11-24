"""
Mavunqo Automated Cybersecurity & Threat Monitor
- Sliding-window rate limiting per IP & sensitive endpoint (/api/auth/login, /api/driver/verify-pin, /api/concierge)
- Heuristic payload & anomaly inspection (SQLi, XSS, path traversal, brute-force spikes)
- Logs security alerts into audit_events for /api/admin/security-alerts
"""
import os
import re
import shutil
import time
import uuid
from collections import defaultdict
from typing import Dict, Tuple, Optional, List
from backend.db import get_connection

ADMIN_ALERT_PHONE = os.environ.get("MAVUNQO_ADMIN_ALERT_PHONE", "+18093487472")
ADMIN_ALERT_EMAIL = os.environ.get("MAVUNQO_ADMIN_ALERT_EMAIL", "admin@mavunqo.com")


class SecurityMonitor:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._started_at = time.time()
        self._hits: Dict[str, list] = defaultdict(list)
        self._req_log: list = []
        self._threat_patterns = [
            ("sqli_probe", re.compile(r"(\bunion\b\s+\bselect\b|\bdrop\b\s+\btable\b|'\s*or\s*'1'\s*=\s*'1|--\s*$)", re.IGNORECASE)),
            ("xss_probe", re.compile(r"(<\s*script\b|onerror\s*=|onload\s*=|javascript:)", re.IGNORECASE)),
            ("path_traversal", re.compile(r"(\.\./|\.\.\\|/etc/passwd|win\.ini)", re.IGNORECASE)),
        ]

    def check_rate_limit(self, ip: str, path: str, max_hits: int = 20, window_sec: int = 60) -> Tuple[bool, Optional[str]]:
        now = time.time()
        key = f"{ip}:{path}"
        recent = [t for t in self._hits[key] if now - t < window_sec]
        recent.append(now)
        self._hits[key] = recent
        if len(recent) > max_hits:
            self.log_security_event(ip, "rate_limit_blocked", path, f"Exceeded {max_hits} req/{window_sec}s")
            return False, "Too many requests. Please wait a moment and try again."
        return True, None

    def inspect_payload(self, ip: str, path: str, payload_text: str) -> Tuple[bool, Optional[str]]:
        if not payload_text:
            return True, None
        for threat_type, pattern in self._threat_patterns:
            if pattern.search(payload_text):
                self.log_security_event(ip, f"security_threat_{threat_type}", path, payload_text[:120])
                return False, "Request blocked by Mavunqo Security Monitor."
        return True, None

    def record_request(self, status_code: int, duration_ms: float = 0.0):
        now = time.time()
        self._req_log = [r for r in self._req_log if now - r[0] < 60]
        self._req_log.append((now, int(status_code), float(duration_ms)))

    def get_server_health(self) -> Dict[str, object]:
        now = time.time()
        recent = [r for r in self._req_log if now - r[0] < 60]
        self._req_log = recent
        rpm = len(recent)
        durations = [r[2] for r in recent if r[2] > 0]
        avg_ms = round(sum(durations) / len(durations), 1) if durations else 0.0
        peak_ms = round(max(durations), 1) if durations else 0.0
        errors_5xx = sum(1 for r in recent if r[1] >= 500)

        memory_pct = None
        if os.path.isfile("/proc/meminfo"):
            try:
                info = {}
                with open("/proc/meminfo", "r", encoding="utf-8") as f:
                    for line in f:
                        parts = line.split()
                        if len(parts) >= 2:
                            info[parts[0].rstrip(":")] = int(parts[1])
                total = info.get("MemTotal", 0)
                avail = info.get("MemAvailable", info.get("MemFree", 0))
                if total > 0:
                    memory_pct = round(((total - avail) / total) * 100.0, 1)
            except Exception:
                memory_pct = None

        load_1m = None
        if os.path.isfile("/proc/loadavg"):
            try:
                with open("/proc/loadavg", "r", encoding="utf-8") as f:
                    load_1m = float(f.read().split()[0])
            except Exception:
                load_1m = None

        db_size_mb = round(os.path.getsize(self.db_path) / (1024 * 1024), 2) if os.path.isfile(self.db_path) else 0.0
        try:
            disk_free_mb = round(shutil.disk_usage(os.path.dirname(self.db_path) or ".").free / (1024 * 1024), 1)
        except Exception:
            disk_free_mb = None

        status = "ok"
        label = "Healthy — Current Plan OK"
        if (memory_pct is not None and memory_pct >= 85) or avg_ms >= 1000 or errors_5xx >= 3:
            status = "upgrade"
            label = "Upgrade Recommended — High Load or Errors"
        elif (memory_pct is not None and memory_pct >= 75) or avg_ms >= 500 or rpm >= 120:
            status = "watch"
            label = "Watch — Traffic or Latency Rising"

        return {
            "status": status,
            "label": label,
            "rpm": rpm,
            "avg_ms": avg_ms,
            "peak_ms": peak_ms,
            "errors_5xx": errors_5xx,
            "memory_pct": memory_pct,
            "load_1m": load_1m,
            "db_size_mb": db_size_mb,
            "disk_free_mb": disk_free_mb,
            "uptime_min": round((now - self._started_at) / 60.0, 1),
        }

    def get_alert_config(self) -> Dict[str, object]:
        return {
            "admin_alert_phone": ADMIN_ALERT_PHONE,
            "admin_alert_email": ADMIN_ALERT_EMAIL,
            "smtp_configured": bool(os.environ.get("MAVUNQO_SMTP_USER") and os.environ.get("MAVUNQO_SMTP_PASS")),
        }

    def get_recent_security_events(self, limit: int = 25) -> List[Dict]:
        try:
            with get_connection(self.db_path) as conn:
                rows = conn.execute(
                    """SELECT id, actor_id, action, target_type, target_id, details_json, created_at
                       FROM audit_events
                       WHERE target_type = 'security'
                       ORDER BY created_at DESC LIMIT ?""",
                    (limit,),
                ).fetchall()
                return [dict(r) for r in rows]
        except Exception:
            return []

    def _send_email_alert_if_configured(self, action: str, actor_ip: str, target_id: str, detail: str):
        smtp_user = os.environ.get("MAVUNQO_SMTP_USER", "")
        smtp_pass = os.environ.get("MAVUNQO_SMTP_PASS", "")
        if not smtp_user or not smtp_pass or not ADMIN_ALERT_EMAIL:
            return
        try:
            import smtplib
            from email.message import EmailMessage
            smtp_host = os.environ.get("MAVUNQO_SMTP_HOST", "smtp.gmail.com")
            smtp_port = int(os.environ.get("MAVUNQO_SMTP_PORT", "587"))
            msg = EmailMessage()
            msg["Subject"] = f"[Mavunqo Security Alert] {action} on {target_id}"
            msg["From"] = smtp_user
            msg["To"] = ADMIN_ALERT_EMAIL
            msg.set_content(
                f"Mavunqo Security Monitor detected an event:\n"
                f"Action: {action}\nIP: {actor_ip}\nPath: {target_id}\nDetail: {detail}\n"
                f"Admin Alert Line: {ADMIN_ALERT_PHONE}\n"
            )
            with smtplib.SMTP(smtp_host, smtp_port, timeout=5) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)
        except Exception:
            pass

    def log_security_event(self, actor_ip: str, action: str, target_id: str, detail: str = ""):
        try:
            with get_connection(self.db_path) as conn:
                conn.execute(
                    """INSERT INTO audit_events (id, actor_id, action, target_type, target_id, details_json)
                       VALUES (?, ?, ?, 'security', ?, ?)""",
                    (f"sec_{uuid.uuid4().hex[:12]}", actor_ip or "unknown", action, target_id, detail)
                )
                conn.commit()
        except Exception:
            pass
        if action.startswith("security_threat_") or action == "rate_limit_blocked":
            self._send_email_alert_if_configured(action, actor_ip or "unknown", target_id, detail)
