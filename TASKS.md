# MAVUNQO — Shared Task Management (`TASKS.md`)

| ID | Task Description | Priority | Assigned | Status | Acceptance Criteria & Verification |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **T-001** | Fix `UnboundLocalError` in `backend/server.py` `do_POST` | Critical | Antigravity | **Done** | `POST /api/orders` returns `201`; verified via `unittest`. |
| **T-002** | Remove `"Zero chargeback risk"` / `"0% Chargeback"` & `Standard (80%)` badge | High | Antigravity | **Done** | Removed from `storefront.html` & `order_status.html`; Zelle/Wise instructions intact. |
| **T-003** | Hide demo listings (`biz_sosua_villas`, `biz_caribe_fix`) from public site | High | Antigravity | **Done** | Both set to `status='pending'`, `requests_enabled=0` in `seed.py` & `mavunqo.db`. |
| **T-004** | Add `en` language support to `frontend/driver.html` | Medium | Antigravity | **Done** | `🇺🇸 EN` option translates all driver UI labels and prompts. |
| **T-005** | Isolate hidden demo-business test fixtures in backend tests | High | Antigravity | **Ready for Codex QA** | `backend/tests.py`, `backend/test_http.py`, and `backend/test_phase2_requests.py` now use isolated temp DBs and activate `biz_sosua_villas` & `biz_caribe_fix` only in test setup (`Ran 41 tests in 4.667s — OK`). |
| **T-006** | Independent QA audit of recent frontend/backend changes | High | Codex | **Ready for Retest** | Antigravity completed T-005; Codex to rerun all 41 tests and verify `seed.py` keeps demo listings hidden. |
| **T-007** | Fix directory UI bugs (initial cards, Concierge/footer overlap, city dropdown state, blank map tiles) | Medium | Antigravity | **Pending** | Verified on staging browser QA. |
| **T-008** | Production DB persistence (Render Persistent Disk or PostgreSQL) | Critical | Owner Approval | **Blocked (Level 3)** | Owner approves recurring cost before any migration. |
| **T-009** | Link 2 dedicated staff SIM numbers to `staff1` / `staff2` | Medium | Antigravity | **Waiting on Owner** | Owner provides the 2 WhatsApp Business numbers. |
**Codex QA update (2026-11-28):** T-005 independently verified. All 41 tests passed in 4.782s in an isolated QA copy, and both demo listings remained pending with requests disabled in a fresh normal seed.
