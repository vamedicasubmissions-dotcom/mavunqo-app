# Mavunqo — Phase 1 Local Business Directory & Marketplace Foundation

Mavunqo starts as a bilingual, mobile-first searchable directory of local businesses and services on the Dominican Republic North Coast (Sosúa pilot, with Cabarete and Puerto Plata staged for rollout).

## Architecture & Technology Stack
- **Backend:** Python 3.13 REST API & HTTP server (`backend/server.py`). Standard library only—zero external dependencies to install.
- **Database:** SQLite with strict foreign keys, multi-tenant isolation, audit trails, and privacy-conscious analytics (`backend/db.py`).
- **Frontend:** Responsive, accessible HTML5, CSS3, and Vanilla JavaScript with full bilingual (EN/ES) support and manual switcher (`frontend/`).

---

## Getting Started

### 1. Initialize and Seed Database
Initializes categories, locations, demo accounts, and two pilot businesses:
```powershell
.\py.bat -m backend.seed
# or: .\.venv\Scripts\python.exe -m backend.seed
```

### 2. Run Test Suite
Executes unit tests, multi-tenant isolation checks, approval gate verifications, and endpoint tests:
```powershell
.\py.bat -m backend.tests
.\py.bat -m backend.test_http
```

### 3. Start the Web Server
```powershell
.\py.bat -m backend.server
```
Visit in your browser:
- **Public Directory:** `http://localhost:8080/`
- **Business Profile / Storefront:** `http://localhost:8080/b/caribe-fix-auto` or `http://localhost:8080/b/sosua-ocean-view-villas`
- **Business Registration:** `http://localhost:8080/register`
- **Sign In:** `http://localhost:8080/login`
- **Admin Portal:** `http://localhost:8080/admin`
- **Business Owner Portal:** `http://localhost:8080/dashboard`

---

## Seed Accounts for Evaluation
- **System Admin:** `admin@mavunqo.com` / `AdminPass2026!`
- **Villa Rentals Owner (with external website):** `carlos@sosuavillas.com` / `OwnerPass2026!`
- **Auto & AC Repair Owner (free hosted storefront):** `rosa@caribefix.com` / `OwnerPass2026!`
