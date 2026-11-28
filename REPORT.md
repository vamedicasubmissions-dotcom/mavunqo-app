# MAVUNQO — Project Owner Report (`REPORT.md`)

## 1. Overall Project Status
- **Application:** Core directory, storefronts, WhatsApp ordering, `/outreach` portal, `/driver`, `/dispatcher`, and `/admin` are operational locally.
- **Live Site (`https://mavunqo.com`):** Up (HTTP 200). Latest local changes (chargeback wording removal, demo listing hiding, driver `EN` support, 73 leads) are **pending owner push** via `push_to_github.bat`.

## 2. Completed & Verified Features
- **Backend API & Ordering:** `POST /api/orders` HTTP 500 fixed; 41-test suite passed (`Ran 41 tests in 2.790s — OK`) prior to hiding `biz_sosua_villas` in `seed.py`.
- **Sales Outreach (`/outreach`):** 73 verified DR leads seeded, `📍 Near Me` GPS sorting, `▶ Play Audio Walkthrough`, `🤝 In-Person Visit`, `📞 Specialist Callback`, B2B/SaaS pitch, and staff auto-redirect on `/login`.
- **Driver App (`/frontend/driver.html`):** English (`EN`), Spanish (`ES`), and French (`FR`) support; 4-digit PIN verification.
- **Checkout & Order Status:** Zelle and Wise instructions preserved; chargeback and `Standard (80%)` wording removed.

## 3. Incomplete Features & Known Bugs
- **4 Phase 1 Tests (`backend/tests.py`):** Expect `sosua-ocean-view-villas` to be `approved`; need test-only fixture isolation (`T-005`).
- **Live UI Bugs (from browser QA):**
  - Landing page `/` shows no business cards until a category or search is clicked.
  - `AI Concierge` floating button overlaps `Admin Portal` footer link.
  - City dropdown can stay visually on `Cabarete` after returning Home.
  - Embedded Leaflet map tiles render blank in checkout modal.

## 4. Security & Financial / Infrastructure Risks
- **Critical — Ephemeral Storage on Render Free Plan:** `render.yaml` uses `plan: free` with local SQLite (`mavunqo.db`). Redeploys or restarts on Render will wipe local SQLite data until a **Render Persistent Disk** or **PostgreSQL** is added.
- **No Edge WAF yet:** Cloudflare DNS/WAF/rate-limiting not yet configured.

## 5. Recommended Next Steps & Owner Decisions
1. **Approve `T-005`:** Let Antigravity/Codex isolate `biz_sosua_villas` as a test-only fixture so all 41 tests pass with demo listings hidden.
2. **Approve Production Persistence (`T-008`):** Choose Render Persistent Disk or Render PostgreSQL.
3. **Deploy:** Run `push_to_github.bat` after `T-005` passes CI.
4. **Staff SIMs (`T-009`):** Share the 2 dedicated SIM numbers when ready.
