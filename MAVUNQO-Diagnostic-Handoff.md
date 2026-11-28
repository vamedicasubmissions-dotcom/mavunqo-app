# MAVUNQO diagnostic handoff

The four suites configured in GitHub Actions ran under Python 3.13 on Windows against an isolated copy with fresh test data. Of 41 tests, 38 passed. The three unsuccessful Phase 2 checks cover bilingual search, merchant privacy and counteroffers, and map-pin validation. Each expects the Montellano Oasis Massage listing.

## Diagnosis

The listing insert in backend/seed.py around line 1422 omits owner_id. The businesses schema in backend/db.py around line 92 declares owner_id NOT NULL and references users(id). SQLite INSERT OR IGNORE skips a row that violates the NOT NULL constraint. The search test then fails its assertion and the two business lookups return None before reaching the behavior those tests intend to exercise.

## Recommended next work

Give the test listing a valid seeded owner or create the listing explicitly in the test fixture if it belongs only in tests. Preserve the existing ownership constraint. Verify that the expected listing exists after fresh setup and rerun the complete CI command.

    python -m unittest backend.tests backend.test_http backend.test_phase2_requests backend.test_whatsapp_ordering -v

The initial run also reported unclosed SQLite connections. The checked-in Render configuration seeds SQLite at build time and declares no persistent disk. Review connection cleanup and verify database persistence across redeploys before relying on live orders. Live configuration and behavior were outside this review.

The project source and original databases were left untouched by testing.
