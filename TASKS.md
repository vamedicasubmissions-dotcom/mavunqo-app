# MAVUNQO — Shared Task Management (`TASKS.md`)

| ID | Task Description | Priority | Assigned | Status | Acceptance Criteria & Verification |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **T-001** | Fix `UnboundLocalError` in `backend/server.py` `do_POST` | Critical | Antigravity | **Done** | `POST /api/orders` returns `201`; verified via `unittest`. |
| **T-002** | Remove `"Zero chargeback risk"` / `"0% Chargeback"` & `Standard (80%)` badge | High | Antigravity | **Done** | Removed from `storefront.html` & `order_status.html`; Zelle/Wise instructions intact. |
| **T-003** | Hide demo listings (`biz_sosua_villas`, `biz_caribe_fix`) from public site | High | Antigravity | **Done** | Both set to `status='pending'`, `requests_enabled=0` in `seed.py` & `mavunqo.db`. |
| **T-004** | Add `en` language support to `frontend/driver.html` | Medium | Antigravity | **Done** | `🇺🇸 EN` option translates all driver UI labels and prompts. |
| **T-005** | Isolate `biz_sosua_villas` test fixture in `backend/tests.py` | High | Codex / Antigravity | **Pending** | All 41 tests pass while `seed.py` keeps demo listings hidden. |
| **T-006** | Independent QA audit of recent frontend/backend changes | High | Codex | **Pending** | Codex reviews `HANDOFF.md` changes and runs full `unittest` suite. |
| **T-007** | Fix directory UI bugs (initial cards, Concierge/footer overlap, city dropdown state, blank map tiles) | Medium | Antigravity | **Pending** | Verified on staging browser QA. |
| **T-008** | Production DB persistence (Render Persistent Disk or PostgreSQL) | Critical | Owner Approval | **Blocked (Level 3)** | Owner approves recurring cost before any migration. |
| **T-009** | Link 2 dedicated staff SIM numbers to `staff1` / `staff2` | Medium | Antigravity | **Waiting on Owner** | Owner provides the 2 WhatsApp Business numbers. |
