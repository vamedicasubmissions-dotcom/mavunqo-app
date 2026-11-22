"""
Mavunqo Automated Cybersecurity & Threat Monitor
- Sliding-window rate limiting per IP & sensitive endpoint (/api/auth/login, /api/driver/verify-pin, /api/concierge)
- Heuristic payload & anomaly inspection (SQLi, XSS, path traversal, brute-force spikes)
- Logs security alerts into audit_events for /api/admin/security-alerts
"""
import re
import time
import uuid
from collections import defaultdict
from typing import Dict, Tuple, Optional
from backend.db import get_connection


class SecurityMonitor:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._hits: Dict[str, list] = defaultdict(list)
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
