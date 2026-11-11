# MAVUNQO — Phase 1 Product Requirements & Antigravity Build Plan

**Document status:** Approved Phase 1 product decisions; implementation not yet verified  
**Working brand:** Mavunqo  
**Candidate domain:** `mavunqo.com` — user-reported registrar listing; purchase, ownership, renewal price and trademark clearance must be confirmed  
**Launch market:** Sosúa, Dominican Republic  
**Expansion priority:** Cabarete → Puerto Plata  
**Purpose:** The public entry point to a future AI-powered local business marketplace and centrally managed business automation ecosystem.

## 1. Product vision

Mavunqo starts as a bilingual, mobile-first searchable directory of local businesses and services. Customers find a business, explore its profile and service menu, and contact it directly. Businesses receive a **free basic directory listing** and, if they need one, a **free basic Mavunqo-hosted storefront**. Businesses with existing sites can keep those sites and link them from Mavunqo.

This directory is **the market entry point**, not the end product. The platform must be structured so businesses can later opt into shared automation capabilities such as AI customer assistance, service requests, estimates, scheduling, orders, notifications and payments, without re-registering or rebuilding their listing. **Do not implement Phase 2 automation in Phase 1.**

## 2. Launch and rollout

1. **Sosúa:** Launch pilot, onboard and validate businesses and customer journeys.
2. **Cabarete:** Activate when the Sosúa pilot meets agreed product and operational readiness criteria.
3. **Puerto Plata:** Expand after the Cabarete rollout is stable.
4. Keep locations as configurable data, not hard-coded business logic; additional cities should be addable later.
5. Businesses may specify a physical location and/or multiple service areas. Do not publicly promote an unlaunched city as an active Mavunqo launch market.

## 3. Confirmed Phase 1 decisions

| Topic | Requirement |
|---|---|
| Listing approval | **Admin approves every public business listing** before publication. |
| Public discovery | Search by **service, category, location, and business name**. |
| Search cards | Show business name, services, location/service areas, photos, contact and website when provided. |
| Customer identity | Public browsing and discovery require **no customer account or login**. |
| Business ownership | Authenticated business owners may manage **only their own** listings. |
| Significant edits | Admin must approve significant edits before they become public. |
| Basic plan | **Free** basic listing and **free** basic hosted storefront for businesses that need a website. |
| Existing websites | Businesses may link to and continue using their existing website. No forced migration. |
| Service prices | Optional; each business chooses whether to display them. |
| Contacts | WhatsApp, telephone, external website (if any), and a contact form. |
| Customer reviews | **Not included** in Phase 1; reserve verified reviews for a later phase. |
| Languages | English and Spanish, with a **visible manual language switch**. |
| RNC/tax ID | **Optional** in Phase 1; missing RNC must not block submission or automatically block approval. |
| Banking information | **Optional / deferred**; no bank account details are required for free listings. |
| Geographic priority | Sosúa first, then Cabarete, then Puerto Plata. |

## 4. Customer-facing experience

### 4.1 Directory home
- Prominent search input: “What are you looking for?” / “¿Qué estás buscando?”
- Browse categories and supported locations.
- Results support keyword, category and area filters, including combined filters.
- Clearly indicate whether a company serves an area versus has a physical location there.
- Responsive, accessible mobile-first design with useful loading, empty and error states.
- SEO-friendly public pages and understandable URLs.

### 4.2 Search results
- Business name, logo/cover photo, brief service description, category, city/service area.
- WhatsApp and telephone action where configured.
- Link to its Mavunqo business profile, with optional external website link.
- No fabricated rating, review count, opening hours, service prices or availability.
- Track aggregate searches and zero-result terms; minimize collection of personal information.

### 4.3 Business profiles and service menus
- Brand name, approved business description, photo gallery, operating hours if supplied, address or service areas, services, optional prices and contact methods.
- Clear CTA for WhatsApp, call, contact form, and existing website.
- If the business needs a website, publish a **hosted storefront** at a path such as `mavunqo.com/b/{slug}`. This is part of the free basic plan.
- If a business already has a website, keep its Mavunqo profile and link to the existing site. Do not scrape or republish proprietary website content without permission.
- Storefront pages use business-specific identity and content but share a centrally maintained technical platform.
- Set reasonable free-tier storage and image limits and make them administratively configurable.

### 4.4 Contact form
- Collect only necessary information (e.g. name, preferred contact and message), clearly disclose who receives it, and require consent where appropriate.
- Protect from spam and abuse; limit uploads or avoid them in the first version.
- Deliver messages reliably to the business or its authorized inbox; provide a clear success/failure state without exposing private contact data.
- Do not claim a booking, quote or transaction has been completed just because a contact form was submitted.

## 5. Business registration and verification

### 5.1 Required application fields
- Public/trading business name, main service category, description of offered services.
- Business owner's or authorized representative's private name and verified contact channel.
- Contact number/WhatsApp and physical location or service area.
- Ownership acknowledgement, accurate-information agreement and relevant terms/privacy acknowledgement.

### 5.2 Optional fields
- Website URL, photos/logo, hours, service prices, other contact methods.
- **RNC** or relevant tax identity for verification. If absent, allow application and manual review.
- **Bank information: not needed for Phase 1 onboarding.** If a future financial module needs payout data, obtain it at that time through an appropriately vetted payment provider and enhanced verification.

### 5.3 Onboarding workflow
1. Business submits a registration form (status `pending`).
2. Admin checks duplicate listings, legitimacy, contact/authorization and available RNC information as appropriate.
3. Admin approves, rejects with rationale, or requests corrections.
4. Approved listing is published; rejected/pending listings remain private.
5. Owner can propose edits; designated sensitive fields (ownership, payout details when enabled, legal identity, primary website/domain) require manual approval.
6. Record who approved changes, when, and what changed.

**Privacy:** Do not publish owners’ private identity fields, RNC verification records, bank data or administration notes. Public information must be deliberately selected and reviewed.

## 6. Admin and owner dashboards

### Platform Admin
- View pending/approved/rejected/suspended applications.
- Review and approve listings and sensitive changes; resolve duplicates; manage categories and cities.
- View business profiles, moderation notes and change history.
- Monitor searches, result views, contact CTA clicks, and zero-result queries in aggregate.
- Manage free-plan limits, feature flags, abuse reports and business status.

### Business owner
- Securely log in; claim/manage only authorized businesses.
- Edit profile, photos, service menu, price visibility, contact methods and existing site link.
- Preview before publishing; see pending approval status for sensitive changes.
- View basic aggregate profile activity where compliant and available.
- Future modules should be shown as *coming later* or hidden—not as usable Phase 1 features.

## 7. Future-ready central automation architecture (not Phase 1 functionality)

Mavunqo must be designed for a shared, **multi-tenant** automation layer, with opt-in features activated separately per business. Examples of later modules:

- AI bilingual customer concierge and business assistant.
- Customer intake and service requests.
- Appointment scheduling and availability.
- Preliminary estimates and approval workflows.
- Restaurant ordering, delivery and driver notifications.
- Payments, settlement and provider-verified payouts.
- Authorized integrations with existing business websites and systems.

Future automation requires business authorization, strict tenant isolation, human approval for binding commitments and high-risk actions, audit logs and compliance reviews. **Do not build these modules yet.**

## 8. Suggested architecture

Choose a coherent implementation based on the existing repository; **inspect existing code before adding a new stack**. A reasonable greenfield baseline:

- **Web:** Next.js + TypeScript + Tailwind CSS.
- **Database:** PostgreSQL with migrations and tenant-aware access controls.
- **Auth:** Well-supported managed authentication for business owners and platform admin users; customer browsing is public.
- **Media:** Object storage with safe file types, size limits and image processing.
- **Search:** Indexed database search with services/categories/location filters; add specialized search infrastructure only when needed.
- **Languages:** EN/ES message catalogs; persist user language preference when appropriate, with visible switcher.
- **Hosting:** Managed HTTPS web deployment, production/staging separation, backups and observability.

Maintain separate responsibilities for directory/search, storefront presentation, business management, approvals and future automation services. Avoid duplicated apps per tenant; enforce per-business authorization on every protected operation.

## 9. Proposed data model

- `businesses`: id, legal name (private where appropriate), trading name, slug, description, status, category refs, location/service area refs, website and public-contact settings.
- `business_owners` / `business_memberships`: user id, business id, role, status.
- `categories` and `business_categories`.
- `services`: business id, name, description, optional price/currency, display-price flag, sort order.
- `locations` and `business_service_areas`.
- `media_assets`: business id, file metadata, approved public visibility.
- `contact_requests`: business id, limited lead fields, delivery/status metadata, retention policy.
- `listing_submissions` / `change_requests`: requested changes, review status, reviewer and timestamps.
- `verification_records`: optional RNC and verification outcomes; private, access restricted.
- `audit_events`: actor, action, tenant id, timestamp, metadata.
- `feature_entitlements`: per-business future module flags, initially free-directory/storefront only.
- `search_events`: privacy-conscious aggregate analytics for queries and outcomes.

Treat this as a conceptual schema; refine during implementation with indexes, constraints, retention/deletion policies and field-level access rules.

## 10. Security, privacy and operational safeguards

- Authenticate and authorize every admin/owner operation; never trust a business ID passed from the browser.
- Prevent cross-business access in APIs, database queries, files and reports; test against tenant isolation failures.
- MFA for platform administrators; appropriate credential/session protections for business owners.
- Rate-limit registration, login, search and contact endpoints; anti-bot protections where needed.
- Validate uploaded images and URLs; block malicious file formats and unsafe redirects.
- Secure secrets, HTTPS, audit trails, backups and restoration testing.
- Collect the minimum personal information needed; define consent, retention and deletion policies.
- RNC is optional. Avoid collecting raw bank account numbers until payout functionality requires it; then use a vetted payment provider/tokenized setup when supported.
- English/Spanish privacy notices and public terms should match actual operations.
- Apply local legal/regulatory review before handling payments or claiming a business is legally verified.

## 11. Suggested implementation milestones

### Milestone 0 — Repo and specification audit
- Inspect current Antigravity project, existing code, environments, tests and design patterns.
- Identify implemented versus missing Phase 1 requirements; do not assume completion.
- Produce a concise build plan and list of risks before large code changes.

### Milestone 1 — Core data and access control
- Create migrations, authenticated owner/admin roles, business tenancy and audit framework.
- Implement categories and locations with Sosúa launch state.

### Milestone 2 — Applications and approvals
- Business application form, optional RNC, pending workflow, admin review and notification.
- Enforce no publication before admin approves.

### Milestone 3 — Directory and search
- Home, categories, keyword/service/location/company search, filters and search-result cards.
- Empty states and mobile-first bilingual interface.

### Milestone 4 — Profiles and free storefronts
- Business details, menus with optional prices, photos, contacts, existing website links and hosted pages.
- Owner content editing and approvals of sensitive changes.

### Milestone 5 — Validation and pilot
- Seed two realistic demo businesses: one with an existing site and one using a free Mavunqo storefront.
- Run security, tenancy, accessibility, mobile, EN/ES, analytics and end-to-end tests.
- Pilot with Sosúa businesses; fix observed friction before expansion.

## 12. Phase 1 acceptance criteria

- [ ] Visitors can search and browse without creating an account.
- [ ] Search supports service, category, location and business name, alone or combined.
- [ ] Search listings show only truthful, approved public information.
- [ ] Sosúa is the first active launch area, with configurable future expansion to Cabarete and Puerto Plata.
- [ ] A business with an existing website can register, be approved and link to that site.
- [ ] A business without a website can receive a free Mavunqo-hosted profile/storefront.
- [ ] Owners can edit only their own businesses; sensitive changes require admin approval.
- [ ] RNC and banking information are **not required** to submit a Phase 1 application.
- [ ] Service prices can be shown or hidden independently per business/service.
- [ ] WhatsApp, phone, website and contact form work as configured.
- [ ] EN/ES translations and visible language switch work on mobile and desktop.
- [ ] No customer review functionality or misleading review widgets are launched.
- [ ] No unapproved listings become public; audit logs record approvals.
- [ ] Cross-tenant data access tests fail safely; admin access is protected.
- [ ] Search, profile and contact metrics are tracked in a privacy-conscious way.
- [ ] No future AI, payment, booking, ordering or delivery functions are falsely presented as operational.

## 13. Out of scope for Phase 1

Payment processing, payouts, paid subscriptions, full CRM automation, AI agents, estimates, appointment scheduling, inventory, delivery, drivers, marketplace checkout, customer reviews, customer accounts and automatic third-party website scraping.

## 14. Instructions to paste into Antigravity

> Read `MAVUNQO_PHASE1_REQUIREMENTS.md` as the approved Phase 1 product specification. Inspect this repository before making changes. First produce a concise gap analysis mapping existing code to requirements and an implementation plan. Then build only the missing Phase 1 features in milestone order, keeping Sosúa as the initial live market and Cabarete/Puerto Plata configurable for future rollout. Preserve the free listing and free basic storefront model, optional RNC and bank information, bilingual UI, business isolation, owner-managed profiles, and admin approval gates. Do not add Phase 2 marketplace or AI automation functionality yet. Implement and run tests, document configuration and manual steps, and never claim production readiness without evidence.

---

**Brand note:** Until the user confirms buying the domain and completes appropriate trademark due diligence, use “Mavunqo” as a *working project name*, not as a claim of registered trademark or owned domain.
