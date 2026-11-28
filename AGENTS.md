# MAVUNQO — Multi-Agent Governance & Instructions (`AGENTS.md`)

## 1. Project Overview & Business Objectives
- **Platform:** MAVUNQO (`mavunqo.com`) — a hyper-local business directory, WhatsApp-first ordering & booking platform, and managed delivery/dispatch system for the Dominican Republic (starting in Sosúa, Cabarete, Puerto Plata, and Montellano).
- **Business Model:** Zero monthly SaaS fees for local merchants; monetization via transaction/commission fees (e.g., 15% on MAVUNQO-sourced orders/bookings), delivery splits, and B2B supply-chain referrals.

## 2. Current Architecture & Technology Stack
- **Backend:** Zero-dependency Python standard library (`sqlite3`, `http.server`, `hashlib`, `hmac`, `smtplib`, `imaplib`) in `backend/` (`server.py`, `service.py`, `db.py`, `seed.py`, `auth.py`, `security_monitor.py`, `payment_monitor.py`).
- **Frontend:** Static HTML/CSS/Vanilla JS + PWA (`manifest.json`, `sw.js`, `notifications.js`, `pwa_nav.js`) in `frontend/` (`index.html`, `storefront.html`, `order_status.html`, `register.html`, `login.html`, `outreach.html`, `driver.html`, `dispatcher.html`, `admin.html`).
- **Database:** Local SQLite (`mavunqo.db`).
- **Hosting & CI:** Render (`render.yaml`, currently `plan: free` with ephemeral local disk) + GitHub Actions (`.github/workflows/ci.yml`).

## 3. Development Standards & Security Requirements
- Preserve existing working functionality; make narrowly scoped, incremental changes.
- Never commit secrets, passwords, API keys, `.db` files with customer data, or credentials.
- All authenticated endpoints must enforce role-based access (`admin`, `owner`, `staff`, `driver`).
- Never publicly cache `/api/*`, `/admin`, `/dispatcher`, `/outreach`, or financial/order-status endpoints.
- All changes must be verified against isolated test databases (`unittest`), never production data.

## 4. Agent Roles & Responsibilities
- **Google Antigravity (Primary Developer):**
  - Implements approved features, bug fixes, and isolated repairs.
  - Documents all modified files, decisions, and test results in `HANDOFF.md` and `TASKS.md`.
- **OpenAI Codex (Independent Auditor & QA):**
  - Independently reviews code changes, runs automated tests, audits security/data integrity, and flags regressions or risks.
  - Does not rubber-stamp Antigravity's work; failed reviews are returned for correction.

## 5. Human Approval Requirements (Level 3)
Explicit owner approval is required before:
- Production deployments (`push_to_github.bat` / Render deploy).
- Database schema migrations, PostgreSQL migration, or Render Persistent Disk upgrades.
- Changes to payment, commission, financial logic, or authentication/RBAC rules.
- Any recurring expense or external paid service activation.

## 6. Conflict Prevention & Git / Rollback Rules
- Both agents must read `AGENTS.md`, `HANDOFF.md`, `TASKS.md`, and `REPORT.md` before starting any task.
- Never edit the same file simultaneously; claim tasks in `TASKS.md` before editing.
- Maintain verified SQLite backups (`sqlite3.Connection.backup()`) before schema/seed changes and use isolated Git branches for non-trivial work.
- Escalate unresolved disagreements to the project owner.
