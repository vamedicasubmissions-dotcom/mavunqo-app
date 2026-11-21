# Mavunqo — Massage & Wellness Directory & Storefront Plan (Puerto Plata)

## 1. Directory, Discovery & Facility Integrity Standard
- **Category:** `cat_wellness_massage` (*Massage & Wellness* / *Masajes y Bienestar*) under `cat_health` (*Health & Wellness* / *Salud y Bienestar*).
- **Location:** `loc_puerto_plata` (*Puerto Plata*) — flip from `upcoming` to `active` at launch.
- **Official Dispatch WhatsApp:** `+18299414894` (pending linking to WhatsApp Business account).
- **Facility Integrity Policy:** For brand trust and client comfort, Mavunqo routes wellness appointments to **client homes/villas/hotels (`mobile_visit`)** or **vetted medical clinic facilities**. Physical spa studios are **conditionally approved**—they are only showcased and unlocked for `in_shop` bookings once finished and verified for cleanliness and wellness standards.
- **Directory Card Highlights:**
  - **INFOTEP Certified** trust badge (`Certificado por INFOTEP`).
  - **Service Mode Pill:** `Mobile / Home Visits` (or `Mobile + Vetted Clinic` once a clinic room is partnered).
  - **Specialty Tags:** Helps users immediately distinguish *Spa & Aesthetics* from *Therapeutic & Physical Rehab*.

---

## 2. Storefront Service Menu Structure (Industry UX Standard)
1. **Top Split-Path Toggle (Hybrid Providers):**
   - `[ On-Site / En Local ]` vs. `[ Mobile / A Domicilio ]`
   - Mobile-only providers display only the *A Domicilio* view with a 3-bullet expectation note (therapist brings portable table, linens, oils; 10-min setup/teardown does not cut into session time).
2. **Goal-Based Service Sections (Instead of a Flat List):**
   - Group services into clear, scannable sections with duration pills (`30 min`, `60 min`, `90 min`) and transparent `DOP` pricing.
3. **3-Photo Trust Gallery + Credentials:**
   - Uniform portrait, spotless treatment room (or portable kit), exterior/logo, and verified INFOTEP certification badge.

---

## 3. Provider Profiles & Menu Grouping

### Provider A: Nelfa López García *(Therapeutic Massage & Physical Rehabilitation)*
- **Positioning:** INFOTEP-Certified Massage Therapist & Physical Therapist · **Mobile-Only (`mobile_visit`)** covering **Puerto Plata, Villa Montellano & Sosúa** · `+18495282828`
- **Dispatch & Location Policy:** Private home GPS pin for mobile dispatch/routing only; appointments take place **only at the client's home/villa/hotel or an approved medical clinic facility**.
- **Phased Equipment Rollout:** Start using existing/shared portable tables (checking how many remote tables Clara has) and schedule around availability; supply Nelfa with her own portable table once booking demand justifies it.
- **Section 1 — Therapeutic & Relaxation Massage (Mobile):**
  - Express / Targeted (30 min) · Relaxing / Swedish (60 / 90 min) · Deep Tissue / Descontracturante (60 / 90 min) · Sports / Recovery (60 min) · Lymphatic Drainage (60 min) · Couples Massage (60 min)
- **Section 2 — Physical Therapy & Rehabilitation (Mobile):**
  - Initial Assessment + First Session (60 min) · Standard Rehab / PT Session (45–60 min) · Extended Manual Therapy + Exercise (75–90 min) · Post-Op / Sports Injury Rehab (60 min)
- **Section 3 — Packages & Modalities:**
  - 5-Session Pack (10% off) · 10-Session Pack (15% off) · Modalities: Ultrasound, TENS, Hot/Cold Compresses, Cupping (*Ventosas*)
- **Pending before publish:** Exact 8-hour schedule/days, fixed prices aligned with Claribel.

---

### Provider B: Claribel Batista Ferreira — Clara Light Spa *(Full-Service Spa, Massage & Aesthetics)*
- **Positioning:** 4× INFOTEP-Certified Therapist & Aesthetician · **Mobile / Outcall (`mobile_visit`)** covering **Puerto Plata, Villa Montellano & Sosúa** · `+18299584064` · Mon–Sat, 9:00 AM – 7:00 PM
- **Location Policy:** Launch **mobile/at-home (`mobile_visit`)** (or via a vetted medical clinic). Clara Light Spa's studio (`19.787583, -70.692389`) is **conditional**—once construction/setup is finished and passes a final cleanliness inspection, `in_shop` can be enabled on Mavunqo.
- **Section 1 — Pain Relief & Recovery:**
  - Express / Targeted (30 min) · Deep Tissue / Muscle-Release (60 min) · Sports / Muscle-Release (90 min) · Sports Recovery (60 min, *On-Site only*)
- **Section 2 — Relaxation & Signature Spa:**
  - Relaxation / Swedish (60 / 90 min) · Hot Stone Massage (60 min) · 4-Hand Massage (60 min) · Couples Massage (60 min) · Lymphatic Drainage (60 min)
- **Section 3 — Aesthetics, Nails & Body Care:**
  - Basic Facial (*On-Site / Mobile*) · Pedicure & Manicure (*On-Site / Mobile*) · Hair Removal — Arms, Legs, Underarms (*Quote by area/density*)
- **Pending before publish:** Curbside WhatsApp GPS pin, fixed prices aligned with Nelfa.

---

## 4. Next Implementation Steps in Mavunqo
1. Update `frontend/storefront.html` so `cat_wellness_massage` renders **grouped service sections**, **On-Site / Mobile mode toggle**, and an **INFOTEP Certified** badge.
2. Update `frontend/index.html` directory cards to show service-mode pills (`In-Studio` / `Mobile`) and specialty tags.
3. Import both providers from `onboarding/puerto_plata_wellness/providers.json` into `mavunqo.db` (and activate `loc_puerto_plata`) once their final aligned prices, Nelfa's hours, and Claribel's GPS pin are confirmed.
