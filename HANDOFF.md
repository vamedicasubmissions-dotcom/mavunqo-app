# MAVUNQO — Agent Handoff Log (`HANDOFF.md`)

## Latest Handoff
- **Codex independent retest (2026-11-28):** T-005 verified. In a fresh QA copy without any source databases, the complete four-module suite ran 41 tests in 4.782s and returned OK (zero failures or errors). A fresh normal seed put both demo listings in `pending` with `requests_enabled=0`. The approval updates are confined to temporary test setup. SQLite connection `ResourceWarning` messages remain a separate QA finding.
- **Agent:** Google Antigravity
- **Date & Time:** 2026-11-28 11:10 (America/Santo_Domingo)
- **Status:** T-005 implemented & verified locally — ready for Codex independent QA (`T-006`).

## T-005 Resolution — Isolated Test Fixtures (2026-11-28)
- **Modified Files:**
  - `backend/tests.py` (`TestMavunqoPhase1.setUpClass`): Enables `biz_sosua_villas` and `biz_caribe_fix` (`status='approved'`, `requests_enabled=1`) **only** inside its isolated `tempfile.TemporaryDirectory()` test database (`test_mavunqo.db`).
  - `backend/test_http.py` (`TestHttpEndpoints.setUpClass` / `tearDownClass`): Redirects `backend.server` (`DB_PATH`, `service.db_path`, `wa_service.db_path`, `wa_bot.db_path`, `security_monitor.db_path`) to an isolated `tempfile.TemporaryDirectory()` database (`test_http_mavunqo.db`), enables `biz_sosua_villas` and `biz_caribe_fix` only inside that isolated test DB, and restores original paths on teardown.
  - `backend/test_phase2_requests.py` (`TestPhase2MerchantRequests.setUpClass` / `tearDownClass`): Redirects `backend.server` and module `DB_PATH` to an isolated `tempfile.TemporaryDirectory()` database (`test_phase2_mavunqo.db`) so running tests never touches `mavunqo.db`.
- **Preserved Production / Seed Behavior:**
  - `backend/seed.py` keeps `biz_sosua_villas` and `biz_caribe_fix` hidden (`status='pending'`, `requests_enabled=0`).
  - `mavunqo.db` was **not** modified (`[('biz_caribe_fix', 'pending', 0), ('biz_sosua_villas', 'pending', 0)]`).
  - Application visibility rules were **not** weakened.
- **Exact Test Verification Result:**
  - Command: `.\py.bat -m unittest backend.tests backend.test_http backend.test_phase2_requests backend.test_whatsapp_ordering -q`
  - Result: **`Ran 41 tests in 4.667s — OK`** (41 passed, 0 failures, 0 errors).

## Codex Independent QA — 2026-11-28
- Ran the complete 41-test command in an isolated writable QA copy; no production database was used or modified.
- Result: **34 passed; 4 failures; 3 errors**.
- All seven non-passing tests are caused by `biz_sosua_villas` and/or `biz_caribe_fix` being seeded as `status='pending'` while legacy tests require those records to be active public fixtures.
- Affected coverage includes search, optional service prices, storefront lookup, contact forms, ordering lifecycle, AI concierge recommendations, and the HTTP slug endpoint.
- Required correction: keep production/demo seed listings hidden, but create approved test-only fixtures in the relevant test setup(s). Do not weaken public visibility checks in application code.
- Additional audit finding: repeated `ResourceWarning` messages show SQLite connections are not consistently closed around `backend/service.py:407`; track separately after restoring the suite.
- **QA decision:** Not approved for deployment until all 41 tests pass in isolation.

## Action Request to Google Antigravity
- **Owner authorization received:** Proceed with the test-fixture correction.
- Update the test setup so `biz_sosua_villas` and `biz_caribe_fix` are active **only inside isolated test databases**.
- Keep both listings hidden (`status='pending'`, `requests_enabled=0`) in the normal application seed and production-facing behavior.
- Do not weaken application visibility rules and do not modify `mavunqo.db`.
- Run the complete 41-test command and record the exact result and modified files here when finished.
- Return the work to Codex for independent retesting; do not deploy or push to production.

## Completed Work & Modified Files
1. **Server `POST` Fix (`backend/server.py`):**
   - Removed duplicate `import time` inside `do_POST` (line 1385) that caused `UnboundLocalError` and HTTP 500s on `POST /api/orders` and other `POST` endpoints.
2. **Test Fixture & Demo Listing Cleanup (`backend/seed.py`):**
   - Added `biz_montellano_oasis_massage` (`owner_id='user_admin'`, `requests_enabled=1`) so `backend/test_phase2_requests.py` passes.
   - Set demo listings `biz_sosua_villas` (`sosua-ocean-view-villas`) and `biz_caribe_fix` (`caribe-fix-auto`) to `status='pending'` and `requests_enabled=0` so they stay hidden from public search, storefronts, and bookings.
   - Seeded 73 verified DR outreach leads into `outreach_leads` (North Coast, Punta Cana, Santo Domingo, Santiago).
3. **Outreach & Driver Portals (`frontend/outreach.html`, `frontend/login.html`, `frontend/driver.html`):**
   - Added `In-Person Visit`, `Specialist Callback`, `📍 Near Me` GPS sorting, `▶ Play Audio Walkthrough`, B2B/SaaS pitch, and `"Already have a system"` objection handler to `frontend/outreach.html`.
   - Updated `frontend/login.html` tab label to `Business / Sales Staff / Admin` and added auto-redirect for `staff` accounts to `/outreach`.
   - Added English (`en`) language option and translations to `frontend/driver.html`.
4. **Payment Wording Cleanup (`frontend/storefront.html`, `frontend/order_status.html`):**
   - Removed `"Zero chargeback risk"` / `"0% Chargeback"` and the unexplained `Standard (80%)` badge while keeping Zelle and Wise payment instructions intact.
5. **CI Workflow (`.github/workflows/ci.yml`):**
   - Added GitHub Actions workflow running `python -m unittest backend.tests backend.test_http backend.test_phase2_requests backend.test_whatsapp_ordering -v` on `push` / `pull_request` to `main`.

## Technical Decisions & Reasoning
- Kept SQLite and zero-dependency Python stdlib intact per owner preservation rules.
- Hid demo listings via `status='pending'` and `requests_enabled=0` rather than deleting rows, preserving schema integrity.

## Known Issues & Instructions for Next Agent (Codex)
- **Test Note:** Hiding `biz_sosua_villas` (`status='pending'`) causes 4 older tests in `backend/tests.py` (`TestMavunqoPhase1`) to fail if re-run against `seed.py` because they expect `sosua-ocean-view-villas` to be `approved`. Codex should review whether to move `biz_sosua_villas` into a test-only fixture in `backend/tests.py`.
- **Do not** push to production or modify `mavunqo.db` without owner approval.
