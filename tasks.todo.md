# AllowED — Production Build Plan
**Date:** April 18, 2026  
**Prepared by:** Claude (for Chilly's approval)  
**Status:** SESSION 1 COMPLETE — all 6 streams built, 206 tests pass, migration pending apply

---

## Pre-flight Check (DONE)

- [x] Read `Chilly_Handoff_v1.md` — ground truth confirmed
- [x] Read `VA_Certification_Automation_Project_Brief.md` — R1-R8 requirements understood
- [x] Read `EM_Interface_Reference.md` — all 12 VBA Remarks, 8 Amendment Reasons mapped
- [x] Verify `.env` — all 3 Supabase keys present (URL, anon, service_role), both VA sandbox keys present
- [x] Run all tests — **206/206 checks pass** (decision_tree: 63, em_integration: 22, enrollment_monitor: 90, tuition_fees: 21, rounding_out: 4, pipeline: 6)
- [x] Inspect `weams_all_schools.json` — 25 universities, each with facility_code + program list (SDSU: 538, total: 6,543)

---

## Work Streams (Parallel Where Possible)

### Stream 1: Database Schema & Migrations
**Depends on:** Nothing (can start immediately)  
**Blocks:** Streams 2, 3, 4, 5

- [ ] **1.1 Design multi-tenant schema** — Normalized tables with FK constraints, check constraints, indexes. All keyed on `institution_id` (facility code). Tables: `institutions`, `weams_programs`, `sco_users`, `students`, `terms`, `enrollments`, `course_schedules`, `enrollment_snapshots`, `amendments`, `tuition_fees_records`, `hitl_queue`, `audit_log`, `certifications_submitted`.
- [ ] **1.2 Write first migration SQL** — Single migration file in `/supabase/migrations/` that creates schema from scratch. Every table gets RLS enabled + policy in the same migration. SCO users scoped by `institution_id`. Service role unrestricted.
- [ ] **1.3 Apply migration via Supabase CLI** — Install CLI, link to project, run `supabase db push` or `supabase migration up`. Verify tables exist in dashboard.
- [ ] **1.4 Write `scripts/seed.py`** — Loads `weams_all_schools.json` into `weams_programs` table for all 25 universities. Uses `supabase-py` with service_role key. Idempotent (safe to re-run).
- [ ] **1.5 Verify** — Query each table from Python. Confirm RLS blocks cross-institution reads with anon key. Confirm service_role can read all.

### Stream 2: PeopleSoft Adapter Interface
**Depends on:** Stream 1 (needs schema for MockAdapter)  
**Blocks:** Stream 4 (API needs adapter)

- [ ] **2.1 Define `PeopleSoftAdapter` abstract class** — ABC with methods: `get_student(student_id)`, `get_enrollment_snapshot(student_id, term)`, `get_dars_audit(student_id)`, `get_tuition_net(student_id, term)`, `get_tuition_gross(student_id, term)`, `list_students_for_term(term)`, `get_course_schedule(student_id, term)`, `get_program_info(student_id)`, `get_expected_graduation(student_id)`, `get_student_dob(student_id)`, `get_student_emplid(student_id)`, `get_enrollment_changes(since_timestamp)`. Signatures match the 12 PS tables in the Technical Integration Spec.
- [ ] **2.2 Implement `MockPeopleSoftAdapter`** — Reads from Supabase synthetic data tables. Uses `supabase-py` with service_role key. Returns same dataclass shapes as the abstract methods define.
- [ ] **2.3 Implement `OraclePeopleSoftAdapter` skeleton** — Every method has a clear TODO: "Wire to cx_Oracle query against PS table X, columns Y, Z". No fake data — raises `NotImplementedError` with a helpful message. This is Jen Christensen's handoff point.
- [ ] **2.4 Rewire `pipeline.py`** — Remove the 4 placeholder comments (DOB, emplid, tuition, rounding-out). Pipeline takes an adapter instance and calls adapter methods for all data. Existing 6 integration tests still pass (using MockAdapter with in-memory data for backward compat).
- [ ] **2.5 Verify** — Run `python3 pipeline.py` — 6/6 still pass. Run `python3 decision_tree.py` — 63/63 still pass. Zero regressions.

### Stream 3: Synthetic Data Generator
**Depends on:** Stream 1 (needs tables to insert into)  
**Blocks:** Stream 5 (frontend needs data to display)

- [ ] **3.1 Build `scripts/generate_synthetic_cohort.py`** — For a given `institution_id` and term, creates 200-800 students with:
  - Chapter distribution: 85% Ch.33 / 10% Ch.35 / 5% Ch.31 (Chilly: ask Paulina if SDSU's real ratio differs)
  - Programs drawn from that institution's actual WEAMS crosswalk in `weams_programs` table
  - Course schedules that exercise every decision tree branch: hybrid, all-online, audit, repeat, remedial, thesis override, practicum, excess electives
  - ~5-10% HITL escalation rate
  - James Roster canonical case always reproducible byte-for-byte at SDSU
- [ ] **3.2 Run generator for all 25 schools** — Batch script that loops through `weams_all_schools.json` facility codes. Should produce ~5,000-15,000 total synthetic students.
- [ ] **3.3 Verify** — Query student counts per institution. Confirm SDSU has ~500 students. Confirm decision tree produces expected distribution of outcomes. Confirm James Roster case matches 19/19 regression checks.

### Stream 4: Backend API (FastAPI)
**Depends on:** Streams 1, 2 (needs DB + adapter)  
**Blocks:** Stream 5 (frontend needs API endpoints)

- [ ] **4.1 Scaffold FastAPI app** — Replace `app.py` demo Flask. Keep `app.py` as-is (rename to `app_demo.py` for reference). New entry point: `api/main.py` or `server.py`. Auto-generated OpenAPI/Swagger at `/docs`.
- [ ] **4.2 Supabase Auth integration** — Email/password sign-up/sign-in. SCO users stored in `sco_users` table linked to Supabase Auth user ID. JWT carries `institution_id` claim.
- [ ] **4.3 Auth middleware** — Every API route validates JWT. Extracts `institution_id`. Passes to adapter/queries so all data is institution-scoped. Superadmin role bypasses institution filter.
- [ ] **4.4 Core routes** — Match existing `app.py` routes but backed by real DB:
  - `GET /api/dashboard` — summary counts for logged-in SCO's institution
  - `GET /api/students` — list students for institution + term
  - `GET /api/students/{id}` — detail with full DT output
  - `POST /api/students/{id}/approve` — HITL approval, writes audit log
  - `POST /api/students/certify-batch` — batch cert, writes audit log
  - `GET /api/amendments` — pending amendments for institution
  - `POST /api/amendments/{id}/approve` — approve amendment
  - `GET /api/audit-log` — audit trail for institution
  - `GET /api/hitl-queue` — HITL items for institution
  - `GET /api/tf-records` — T&F certification records
- [ ] **4.5 Admin routes** —
  - `POST /api/admin/institutions` — add institution
  - `POST /api/admin/institutions/{id}/weams` — upload WEAMS crosswalk (CSV/JSON)
  - `POST /api/admin/sco-users` — create SCO account
  - `GET /api/admin/metrics` — cross-institution metrics
  - `POST /api/admin/generate-cohort` — trigger synthetic data generation for an institution
- [ ] **4.6 Rate limiting, logging, error handling** — Structured JSON logging. No stack traces in error responses. Rate limit per IP/user. CORS configured for frontend origins.
- [ ] **4.7 Verify** — Swagger UI loads. `curl` tests against each endpoint with valid/invalid JWTs. Cross-institution isolation proven (SDSU JWT can't read Cal Poly data).

### Stream 5: Frontend Rewire
**Depends on:** Stream 4 (needs API endpoints)

- [ ] **5.1 `allowed_workstation.html` — Login + API integration** — Add login screen (Supabase Auth JS via CDN). On auth, store JWT. All fetch() calls hit real API with Authorization header. Dashboard, student list, student detail, HITL approval, audit log — all backed by live data.
  - **NOTE (CDN tension):** Stack rules say "@supabase/supabase-js via CDN script tag". Lesson 18 says Cowork preview can't load CDN scripts. Resolution: CDN is fine for real browser demos (Frazee meeting). For Cowork preview testing, we may need a minimal inline auth fallback. Flag for Chilly.
- [ ] **5.2 `allowed_admin.html` — Full admin panel** — Superadmin login. Add institution form. WEAMS upload (file input → parse → POST to API). Create SCO accounts. Cross-institution metrics dashboard.
- [ ] **5.3 Multi-institution proof** — Log in as SDSU SCO → see SDSU data. Log out. Log in as Cal Poly SCO → see completely different cohort. Zero data leakage.
- [ ] **5.4 Verify** — Walk through every step of the demo script (Step 5 in handoff). Every click works, every data point is real (from Supabase), every action writes to audit log.

### Stream 6: Bug Fixes, Integration, Infrastructure
**Depends on:** Partially independent, partially needs Streams 1-4

- [ ] **6.1 Confirm AmendmentReason enum fix** — Re-run `python3 enrollment_monitor.py`, confirm 90/90 with 8 correct dropdown strings. (Already verified in pre-flight — this is documentation.)
- [ ] **6.2 Wire Benefits Intake into pipeline** — The `benefits_intake.py` → `va_api_client.py` path is real. Connect it so `pipeline.py` triggers a real PDF upload to VA sandbox for submitted certifications. Show working on at least one synthetic student.
- [ ] **6.3 LighthouseClient honesty** — Enrollment submission stub stays a stub. Add clear docstring: "VA has not released enrollment submission API. Benefits Intake PDF upload is the current path." No faking.
- [ ] **6.4 Refactor `weams_programs.py`** — Load from `weams_programs` Supabase table instead of hardcoded Python lists. Keep 3-tier matching engine. `match_weams_program()` queries DB by facility code. Backward-compatible: if DB unavailable, fall back to `weams_all_schools.json`.
- [ ] **6.5 `.env.example`** — Checked into repo with placeholder values. Real `.env` in `.gitignore`.
- [ ] **6.6 `docker-compose.yml`** — FastAPI + Python deps. Connects to Supabase cloud. `docker compose up` starts the whole stack.
- [ ] **6.7 `README.md`** — What this is, how to run, how to add a school, how to regenerate synthetic data, how PS adapter swap works.
- [ ] **6.8 Final regression** — All 206 original tests still pass. New tests for adapter, API, auth. Demo script runs cleanly end-to-end.

---

## Dependency Graph

```
Stream 1 (DB Schema)
    ├──→ Stream 2 (PS Adapter) ──→ Stream 4 (API) ──→ Stream 5 (Frontend)
    └──→ Stream 3 (Synthetic Data) ──────────────────→ Stream 5 (Frontend)

Stream 6 (Bug Fixes / Infra) — partially parallel with everything
```

**Parallel execution plan:**
- **Session 1:** Stream 1 (full) + Stream 6.1, 6.3, 6.5 (independent pieces)
- **Session 2:** Stream 2 + Stream 3 (both depend on Stream 1, independent of each other)
- **Session 3:** Stream 4 (API — depends on 1+2)
- **Session 4:** Stream 5 + Stream 6.2, 6.4, 6.6, 6.7 (frontend + remaining infra)
- **Session 5:** Stream 6.8 (final regression) + demo script walkthrough

---

## Honest Time Estimate

**5-8 Cowork sessions** to complete all streams, depending on:
- Whether Supabase CLI cooperates in the sandbox (may need workarounds)
- Complexity of synthetic data that genuinely exercises every DT branch
- How much frontend rework is needed once hitting real API (shape mismatches)

**Highest risk:** Stream 4 (FastAPI + auth). Most code, most integration points, most places for bugs. Budget 2 sessions.

**Lowest risk:** Stream 1 (schema). Well-defined, write SQL, apply, verify. 1 session.

---

## Questions for Chilly Before Starting

1. **Chapter distribution for synthetic data** — Default 85/10/5 (Ch.33/Ch.35/Ch.31) per the handoff. Should we ask Paulina for SDSU's actual ratio?

2. **FastAPI vs Flask** — Handoff says "FastAPI preferred" and I agree (better typing, auto-docs, async, Pydantic validation). Any reason to keep Flask?

3. **CDN tension** — Stack rules say use `@supabase/supabase-js` via CDN for frontend auth. But Lesson 18 says Cowork preview can't load CDN scripts. For the Frazee demo (real browser), CDN is fine. For Cowork testing, I'll build a minimal inline fallback. Sound right?

4. **Supabase CLI in sandbox** — This Cowork environment may not have the Supabase CLI pre-installed. I can install it via npm, or apply migrations directly via the Supabase Management API / SQL editor through `supabase-py`. Which approach do you prefer?

5. **Git repo** — The VA Project folder doesn't appear to be a git repo yet. Should I initialize one? The migration workflow and `.gitignore` assume git.

6. **`app.py` disposition** — Rename to `app_demo.py` and keep as reference, or delete? I lean toward keeping it — it's useful as a quick standalone demo that doesn't need Supabase.
