# AllowED — Chilly Handoff Document v1
**Date:** April 17, 2026  
**Prepared by:** Paulina + Claude audit  
**For:** Chilly (Software Architect / Project Lead)  
**Status:** Active project — backend logic complete, integration layer is next

---

## SECTION A: What You're Getting

### Project Overview
AllowED automates VA GI Bill enrollment certification for universities. Today, School Certifying Officials (SCOs) enter the same data twice: once in PeopleSoft (the university SIS) and once in the VA's Enrollment Manager — fully manual, no system-to-system connection. At SDSU alone this means ~2,100 students per semester processed 10–20 per day, causing 30–90 day delays before veterans receive benefits. AllowED is the regulatory compliance bridge between PeopleSoft and the VA Lighthouse API: it reads enrollment data, applies every SCO Handbook rule automatically, and submits certification-ready data to Enrollment Manager. Target: all students certified on Day 1 of the semester.

*Full detail: `VA_Certification_Automation_Project_Brief.md`*

### Current State Summary (Honest)

**What is genuinely working:**
- The 7-step course applicability rule engine (`decision_tree.py`) is complete, validated against the SCO Handbook, and passing 63/63 regression checks including the canonical James Roster test case.
- The EM field formatter (`em_integration.py`) correctly maps Decision Tree output to all Enrollment Manager fields.
- The enrollment change detector (`enrollment_monitor.py`) correctly classifies adds, drops, withdrawals, never-attended, program changes, and graduation events — 90/90 checks.
- The VA Lighthouse sandbox is live: Veteran Confirmation API and Benefits Intake API both have active sandbox keys, tested connections, and a real GUID from a test PDF upload (`Nick_Foster_Certification.pdf`).
- All 7 backend modules import cleanly with zero dependency errors.

**What is stubbed / not yet wired:**
- There is **no PeopleSoft connection**. All test data is hardcoded Python dicts. The real integration — querying PS tables, reading enrollment snapshots, pulling DARS data — is specified in the docs but not coded.
- `pipeline.py` has explicit `# Placeholder` comments for: student date of birth (`date(1990,1,1)`), student VA ID (uses internal student_id instead of emplid), tuition/fees from bursar (`0.0`), and rounding-out detection from degree audit.
- `app.py` is a Flask demo server — not a production API. It has no authentication, no database, and runs 6 hardcoded demo students through the real decision tree. It is useful for demos only.
- The `LighthouseClient` in `em_integration.py` has HTTP calls stubbed with a TODO comment. Benefits Intake is real (via `va_api_client.py`), but the enrollment submission API is not yet implemented.
- **Bug fixed (April 18):** `enrollment_monitor.py` `AmendmentReason` enum has been corrected — replaced 5 wrong options with the exact 8 EM dropdown strings from live screen recordings. All 8 test suites (90/90 checks) passing. See Section B for the correct enum values.

---

## SECTION B: File-by-File Breakdown

### 1. `decision_tree.py` — 1,090 lines — ✅ WORKING

**Purpose:** The regulatory heart of AllowED. For each course on a student's schedule, runs 7 sequential gates to determine if it's certifiable and at what modality (residential vs. distance).

**The 7 Steps:**
1. WEAMS program match (is student's degree VA-approved?)
2. DARS applicability (is course required for degree? + 3 SCO exception paths)
3. Audit check (audit/non-credit = never certifiable)
4. Repeat course check (previously passed without exception = not certifiable)
5. Remedial check (online/hybrid remedial = never certifiable per handbook)
6. Modality classification (1 in-person 50-min session during term → residential)
7. Rate of pursuit + training time (full/3-4/half/less-than-half)

**Key dataclasses:**
```python
StudentInput(name, student_id, program, academic_level, benefit_chapter, term, courses, facility_code)
CourseSchedule(course_id, title, units, grading_basis, in_dars, has_in_person_session, all_online, ...)
DecisionTreeOutput(course_results, residential_units, distance_units, total_certifiable_units, training_time, rate_of_pursuit, ...)
```

**Run it:** `python3 decision_tree.py` — runs all 3 built-in test suites and prints results.

**Dependencies:** `weams_programs.py` (for WEAMS matching). No external packages beyond stdlib.

**Known gaps:**
- Modality data (`has_in_person_session`, `all_online`) must be populated from PeopleSoft schedule — currently hardcoded in tests.
- DARS data (`in_dars`, `dars_rationale`) must be populated from degree audit — currently hardcoded.
- No database, no API call, no PS connection. Pure business logic.

---

### 2. `em_integration.py` — 1,030 lines — ⚠️ WORKING / API STUBBED

**Purpose:** Translates `DecisionTreeOutput` into a populated `EMEnrollment` object with all Enrollment Manager fields. Also houses the `LighthouseClient` which is the stub for actual API submission.

**Key functions:**
```python
format_for_em(dt_output, student_va_id, student_dob, facility_code, pre_set_id, term_begin, term_end, gross_tuition, aid_amount) -> EMEnrollment
validate_submission_window(enrollment) -> (bool, str)  # 180-day/120-day advance rule
```

**`LighthouseClient` modes:** `"mock"` (default, returns fake success), `"sandbox"` (would hit VA sandbox), `"production"`. HTTP calls in sandbox/production modes are **not yet implemented** — there is a TODO comment at line ~546. The mock mode is what all tests currently use.

**`EMEnrollment` key fields:**
- `resident_credit_hours`, `online_credit_hours`, `clock_hours`
- `tuition_fees` (Ch.33 = net after aid; Ch.35 = gross)
- `begin_date`, `end_date`
- `vba_remarks` (list — see correct options in `EM_Interface_Reference.md`)
- `status` (READY / DRAFT / SUBMITTED)
- `hitl_flags` (list of reasons SCO review is required before submission)

**HITL triggers (7 types):** WEAMS confidence < 95%, courses in SCO exception queue, confidence < 90%, tuition discrepancy, program not matched, post-census drop, never-attended scenario.

**Dependencies:** `decision_tree.py`, `weams_programs.py`. No external packages.

**Known gaps:** Actual HTTP submission to Lighthouse enrollment endpoint not coded. VBA Remarks auto-selection logic needs to be updated with correct field names per `EM_Interface_Reference.md`.

---

### 3. `enrollment_monitor.py` — 2,145 lines — ⚠️ WORKING / BUG IN AMENDMENT ENUM

**Purpose:** Compares two snapshots of a student's enrollment (before and after a change event) and generates the correct amendment for Enrollment Manager.

**Key classes:**
```python
EnrollmentSnapshot(student_id, term, courses, program, graduated)
EnrollmentChange(change_type, course_id, old_value, new_value, requires_amendment, ...)
AmendmentRequest(student_id, amendment_reason, effective_date, ...)
```

**Run it:** `python3 enrollment_monitor.py` — 8 test suites, 90 checks.

**✅ BUG FIXED (April 18) — AmendmentReason enum corrected.**

Previous code (WRONG — now replaced):
```python
class AmendmentReason(Enum):
    TUITION_CHANGE = "Change to Tuition and Fees"
    REDUCED_ENROLLMENT = "Pre-registered but reduced"
    NEVER_ATTENDED = "Pre-registered but never attended"
    WITHDREW_DROP_PERIOD = "Withdrew during drop period"
    GRADUATED = "Graduated/Received Diploma"
```

Correct values (from live EM screen recording, April 17, 2026 — verified by Paulina):
```python
class AmendmentReason(Enum):
    NEVER_ATTENDED            = "Pre-registered but never attended"
    UNSATISFACTORY            = "Unsatisfactory attendance, progress or conduct"
    WITHDREW_BEFORE_TERM      = "Withdraw before beginning of term"
    WITHDREW_POST_DROP_NONPUN = "Withdraw after drop period - non-punitive grades assigned"
    WITHDREW_POST_DROP_PUN    = "Withdraw after drop period - punitive grades assigned"
    WITHDREW_DROP_PERIOD      = "Withdraw during drop period"
    WITHDREW_NCD              = "Withdrawal or interruption (Non-College Degree Programs not on a term basis)"
    OTHER                     = "Other"
```

**Impact:** Any amendment submitted to EM with the old enum values will have incorrect reason codes. This must be fixed before any live submission. The downstream mapping logic in the file also needs to be updated to route PS change events to the correct new options.

**PS mapping for auto-selection:**
| Change event | Correct EM reason |
|---|---|
| Drop before term start | `Withdraw before beginning of term` |
| Drop during add/drop period | `Withdraw during drop period` |
| Drop after census, W grade (non-punitive) | `Withdraw after drop period - non-punitive grades assigned` |
| Drop after census, WF grade (punitive) | `Withdraw after drop period - punitive grades assigned` |
| Enrolled at start, 0 units at add/drop | `Pre-registered but never attended` |
| NCD/clock-hour programs | `Withdrawal or interruption (Non-College Degree Programs...)` |
| Anything else | `Other` + HITL escalation |

**Dependencies:** `decision_tree.py`. No external packages.

---

### 4. `benefits_intake.py` — 797 lines — ✅ WORKING

**Purpose:** Two responsibilities: (1) generate a professional VA certification PDF from `EMEnrollment` data using ReportLab, and (2) upload that PDF to the VA via the Benefits Intake API (2-step: POST for upload URL, PUT to upload).

**Run it:** Import and call — no standalone test runner. `python3 benefits_intake.py` imports cleanly.

**VA Benefits Intake flow:**
1. `POST /uploads` → receive `{guid, location}` (the upload URL)
2. `PUT {location}` with PDF binary + metadata JSON
3. `GET /uploads/{guid}` to poll status

**Live test result:** `Nick_Foster_Certification.pdf` (4,708 bytes) successfully uploaded to VA sandbox. GUID `9dcad747` received. Status: pending (sandbox processing expected).

**Dependencies:** `reportlab`, `va_api_client.py`, `.env` file with `VA_BENEFITS_INTAKE_SANDBOX_KEY`.

**Known gaps:** Used as the upload mechanism for certification PDFs. Not connected to the enrollment submission API (that's `LighthouseClient` in em_integration.py, which is separate).

---

### 5. `tuition_fees.py` — 788 lines — ✅ WORKING / NO PS

**Purpose:** Manages the Tuition & Fees certification track separately from the enrollment certification track. Ch.33 requires reporting T&F independently, after census, when the bursar report is available.

**Key flow:**
```
TFRecord created (PENDING_BURSAR_REPORT) 
→ Bursar report received, amounts updated (RECEIVED)
→ SCO certifies to VA (CERTIFIED_TO_VA)
→ Tuition change detected → amendment (AMENDED)
```

**Business rule coded:** Cannot certify T&F before census date. Ch.33 = net tuition (gross minus aid). Ch.35 = gross tuition (aid not deducted).

**Run it:** `python3 tuition_fees.py` — 21/21 checks pass.

**Dependencies:** None. Self-contained.

**Known gaps:** Tuition/fees amounts in `pipeline.py` are `0.0` placeholders. Real values must come from PeopleSoft `SSR_VB_TUI_WRK_FED` (net) and `TUITION_CALC_TBL` (gross) after census.

---

### 6. `va_api_client.py` — 415 lines — ✅ WORKING (sandbox)

**Purpose:** Live VA Lighthouse API client. Two APIs: Veteran Confirmation (confirm veteran status by SSN) and Benefits Intake (upload certification PDFs). Reads credentials from `.env`.

**`.env` file (present, both keys set):**
```
VA_VET_CONFIRM_SANDBOX_KEY = [32 chars, active]
VA_BENEFITS_INTAKE_SANDBOX_KEY = [32 chars, active]
```

**Run it:** `python3 va_api_client.py` — runs sandbox connection test. Requires `.env` to be present.

**Rate limits:** 60 requests/minute (enforced in code with token bucket).

**Dependencies:** `python-dotenv`, `.env` file. No other internal dependencies.

**Known gaps:** No production keys. Veteran Confirmation API requires real SSNs for confirmed status — Paulina should check developer email for sandbox test SSNs. No enrollment submission API yet (VA has not yet released it through Lighthouse).

---

### 7. `rounding_out.py` — 1,008 lines — ✅ WORKING / NO PS

**Purpose:** Implements the 5-step final-term verification algorithm per 38 CFR §21.4273(d) and the REMOTE Act (PL 117-76). Detects if a student is in their final term, checks that rounding-out courses meet all criteria, and generates the SCO certification statement.

**5 steps:**
1. Check `ACAD_PROG.EXPECTED_GRAD_DT` matches current term
2. Get remaining required units from DARS
3. Sum applicable units from Decision Tree
4. If applicable < full-time AND remaining − applicable = 0 → eligible
5. Verify REMOTE Act compliance (no repeats, approved program)

**Run it:** `python3 rounding_out.py` — 4 scenarios, all pass.

**Dependencies:** `decision_tree.py`. No external packages.

**Known gaps:** DARS integration is simulated — remaining units and course requirements are hardcoded in tests. Real integration requires querying the DARS API or PeopleSoft `SAA_RPT_RQST`.

---

### 8. `pipeline.py` — 1,025 lines — ⚠️ STUBBED

**Purpose:** Orchestration layer that wires all 7 modules together into a single student certification flow. `CertificationPipeline.process_student()` runs decision tree → EM format → T&F record → rounding-out check.

**Public methods:**
```python
CertificationPipeline(facility_code)
  .process_student(student_input) -> PipelineResult
  .process_batch(students) -> BatchResult
  .process_amendment(student_id, old_snapshot, new_snapshot) -> AmendmentResult
  .process_tf_certification(student_id, term) -> TFResult
  .check_rounding_out(student_input) -> RoundingOutResult
```

**Run it:** `python3 pipeline.py` — 6/6 integration tests pass (all using mock data).

**Explicit placeholders in code (Chilly must fix for live use):**

| Location | Placeholder | What it needs |
|----------|-------------|---------------|
| `pipeline.py:225` | `student_va_id=student_input.student_id` | Real emplid from PeopleSoft `SCC_PERDATA_QVW` |
| `pipeline.py:226` | `student_dob=date(1990, 1, 1)` | Real DOB from PeopleSoft student record |
| `pipeline.py:262` | `tuition=0.0, fees=0.0` | Real amounts from `SSR_VB_TUI_WRK_FED` (net) post-census |
| `pipeline.py:273` | Rounding-out detection comment | Real DARS integration — check `ACAD_PROG.EXPECTED_GRAD_DT` |

**Dependencies:** All other Python modules.

---

### 9. `app.py` — 787 lines — ⚠️ DEMO ONLY

**Purpose:** Flask REST API serving the SCO dashboard frontend (`allowed_workstation.html`). Creates 6 demo students at startup, runs them through the real `decision_tree.py`, and serves JSON responses.

**Routes:**
```
GET  /                              → serves dashboard HTML
GET  /api/dashboard                 → summary counts
GET  /api/students                  → list all students with status
GET  /api/students/<id>             → student detail with full DT output
POST /api/students/<id>/approve     → SCO approves flagged enrollment
POST /api/students/<id>/certify-all → certify all clean students
GET  /api/amendments                → pending amendments
POST /api/amendments/<id>/approve   → SCO approves amendment
GET  /api/audit-log                 → audit trail
```

**Demo students (run through real decision tree):**
- Daniel Bahena — Ch.33, B.A. Journalism (James Roster case)
- Maria Garcia — Ch.35, B.S. Computer Science
- James Chen — Ch.33, M.C.P. City Planning (grad student)
- Sarah Kim — Ch.33, B.A. Psychology
- Robert Torres — Ch.31, B.S. Civil Engineering
- Lisa Nguyen — Ch.33, M.A. Comparative World Literature

**⚠️ What this is NOT:**
- No authentication or authorization
- No database — data is regenerated on every server start
- No PeopleSoft connection — demo students are hardcoded
- Runs on port 5000, debug=True — development mode only

**To run:** `cd "VA Project" && pip install flask && python3 app.py`

**Dependencies:** `flask`, all other Python modules.

---

### 10. `weams_programs.py` — 1,204 lines — ✅ WORKING (2 schools hardcoded)

**Purpose:** WEAMS-approved program lists for SDSU and CSUN, plus a 3-tier matching engine (exact → structured → fuzzy) that maps PeopleSoft ACAD_PLAN descriptions to VA-approved program names.

**Current state:** 853 programs hardcoded as Python lists (SDSU: 531, CSUN: 322). `INSTITUTION_REGISTRY` maps facility codes to program lists.

**`weams_all_schools.json` now exists** (April 17, 2026) with 6,543 programs across 25 universities. `weams_programs.py` does NOT yet load from this file — it should be refactored to load dynamically by facility code. Adding a new school currently requires editing the Python file directly.

**Matching engine:**
```python
match_weams_program(program_name, facility_code) -> (matched_name, confidence, tier)
# confidence: 0.0–1.0. Tier: "exact" / "structured" / "fuzzy"
# HITL triggered when confidence < 0.95
```

**Dependencies:** `difflib` (stdlib). No external packages.

---

## SECTION C: Regression Tests

### Primary Test Case — James Roster / Daniel Bahena (B.A. Journalism, Ch.33, Fall 2024)

**Input:** 5 courses — MIS 401 (hybrid), MIS 460 (in-person), MIS 585 (online), MUSIC 151 (online), ENS 331 (in-person, not in DARS)

**Expected output (per validated SCO decision tree):**

| Course | Certifiable | Modality | Reason if excluded |
|--------|-------------|----------|--------------------|
| ENS 331 | ❌ NO | — | Not required for degree per DARS |
| MIS 401 | ✅ YES | RESIDENTIAL | Has in-person session |
| MIS 460 | ✅ YES | RESIDENTIAL | In-person |
| MIS 585 | ✅ YES | DISTANCE | All online |
| MUSIC 151 | ✅ YES | DISTANCE | All online |

**Summary:** R:6, D:6, T:12, Full-Time UG, RoP 100%, MHA eligible

**Actual output (April 17, 2026 run):** 19/19 checks PASS. ✅ Exact match.

**How to run:**
```bash
cd "VA Project"
python3 -c "
from decision_tree import james_roster_test, print_results
print_results(james_roster_test())
"
```

### Secondary Test Cases

| Test | File | What it covers | Status |
|------|------|----------------|--------|
| Kitchen Sink | `decision_tree.py` | All 7 gates: audit, repeat, remedial-online, SCO exception queue, pre-term modality, Ch.35 MHA | ✅ 30/30 PASS |
| Grad Thesis | `decision_tree.py` | Master's student, Thesis 799A full-time override, Ch.33 MHA | ✅ 14/14 PASS |
| 8 amendment scenarios | `enrollment_monitor.py` | Drop before add/drop, post-census drop, never attended, program change, graduation | ✅ 90/90 PASS |
| T&F dual cert | `tuition_fees.py` | Ch.33 T&F cycle, census gate, amendment on change | ✅ 21/21 PASS |
| Rounding out | `rounding_out.py` | Final term eligible/ineligible, already full-time edge case | ✅ 4/4 PASS |
| Pipeline integration | `pipeline.py` | End-to-end orchestration (mock data) | ✅ 6/6 PASS |

**No "Christopher Davis" or F2 graduate secondary test in code.** Only graduate coverage is the "Grad Thesis" test (James Chen, M.C.P.) in `decision_tree.py` and `enrollment_monitor.py`.

### How Chilly Runs All Tests
```bash
cd "/path/to/VA Project"
python3 decision_tree.py      # 63 checks
python3 em_integration.py     # 22 checks (mock API)
python3 enrollment_monitor.py # 90 checks
python3 tuition_fees.py       # 21 checks
python3 rounding_out.py       # 4 checks
python3 pipeline.py           # 6 checks
# Total: 206 checks. All should pass.
```

---

## SECTION D: Open Technical Questions for Chilly

### 1. PeopleSoft Data Access — METHOD NOT DECIDED ⚠️
The specs describe 12 PS tables to query. How the connector reads them is unresolved:
- **Option A:** Direct DB connection (Oracle JDBC/cx_Oracle) — fastest, requires DBA approval from Cyndie Winrow
- **Option B:** PeopleSoft Query API or Application Engine — cleaner, but slower and requires PS config changes
- **Option C:** PeopleSoft Integration Broker (REST/SOAP) — enterprise approach, complex setup
- **Paulina's contact:** Jen Christensen (deployed the M&V Module) is the technical ally for this conversation. Cyndie Winrow controls access — get Frazee's approval first.

**Key tables needed:** `STDNT_ENRL`, `SSR_VB_DATA`, `SSR_VB_TUI_WRK_FED`, `SCC_PERDATA_QVW`, `ACAD_PROG`, `ACAD_PLAN`, `SSR_VB_INSTR_MAP`, `SAA_RPT_RQST`

### 2. VA Enrollment API — NOT YET AVAILABLE
The VA Lighthouse does not yet have an enrollment submission API. Current approach is Benefits Intake (PDF upload). Decision: keep using Benefits Intake for now, or wait for VA to release enrollment API and queue submissions?

### 3. Student Identifier: emplid vs SSN ⚠️
- VA Student ID in Enrollment Manager = **emplid** (confirmed April 17 from live EM session)
- SSN is stored in PeopleSoft `SCC_PERDATA_QVW` but NOT accessible in EM
- `pipeline.py` currently passes `student_input.student_id` as VA Student ID — this needs to be the emplid pulled from PS
- Transfer students (previously attended another school): look up by name + DOB in EM

### 4. Tuition/Fees Timing
- Net tuition (Ch.33) is calculated by PS AFTER census date via `SSR_VB_TUI_WRK_FED`
- Some schools do this manually depending on financial aid award structure
- Question: does SDSU's PS always have net tuition populated after census, or is there a manual step?
- Bursar data feed: scheduled query (daily/weekly) or event-driven on census date?

### 5. Authentication / Auth Model for the Connector Service
- `app.py` currently has zero auth
- For production: what auth model? SDSU SSO? API key per institution? OAuth?
- SCO workstation (`allowed_workstation.html`) needs to know who is approving HITL queue items — audit trail requires SCO identity

### 6. Deployment Target
- Where does this run? SDSU servers? AWS GovCloud? Azure Government?
- FedRAMP authorization required for any cloud service storing student VA data (6–18 month process)
- Pilot approach: run on-premise at SDSU (shadow mode) to avoid FedRAMP during pilot

### 7. Half-Time Threshold — Graduate Programs
- Hardcoded in `decision_tree.py`: Master's full-time = 9+ units, Doctoral = 6+
- Question: configurable per school or always the VA handbook minimum?
- SDSU confirmed: follows VA handbook minimum. Other schools may differ.

### 8. Mamie Miller's Exact Query Logic
- Her business logic is captured in `Mamie_Miller_Process_Transcript_Annotated.md`
- Her exact SQL queries are NOT captured — SDSU privacy policy may prevent access
- The software uses `STDNT_ENRL.LAST_UPD_DT_STMP` as a workaround (event-driven, better than her checkpoint approach)
- Risk: if Mamie retires before her specific edge-case rules are captured, some nuance may be lost

### 9. DARS Integration
- DARS (Degree Audit Report System) is the authoritative source for course applicability
- `SAA_RPT_RQST` is the PS table for programmatically requesting degree audits
- No DARS API is currently coded — all DARS data in tests is hardcoded
- Question: can PeopleSoft `SAA_RPT_RQST` be queried programmatically, or does this require a separate DARS system call?

---

## SECTION E: Recommended Build Order for Chilly

### Phase 1 — SDSU Pilot MVP (Months 1–3)

**Goal:** Run one semester cohort through AllowED in shadow mode alongside Paulina's manual process. Prove correctness before any live submission.

Priority order:
1. **~~Fix the AmendmentReason enum~~** ✅ Done (April 18) — enum replaced, routing logic updated, 90/90 checks passing
2. **PeopleSoft read connector** — build the PS query layer: connect to SDSU PS Oracle DB (or Integration Broker), pull `STDNT_ENRL` snapshots, `SSR_VB_DATA`, `ACAD_PROG`/`ACAD_PLAN`, `SSR_VB_TUI_WRK_FED`. This is the biggest unknown.
3. **Fix pipeline.py placeholders** — wire real emplid, DOB, tuition from PS queries (replaces the four `# Placeholder` lines)
4. **Implement DARS lookup** — either PS `SAA_RPT_RQST` query or DARS REST API if SDSU exposes one
5. **Authentication for app.py** — at minimum, HTTP basic auth or SDSU SSO for the SCO workstation
6. **Shadow mode end-to-end** — run pipeline against live PS data but DO NOT submit to EM; compare AllowED output against Paulina's manual certifications

**Success metric:** AllowED produces correct output for 95%+ of students that Paulina manually certifies. SCO approves HITL queue items. Zero incorrect certifications submitted.

### Phase 2 — Live Submission at SDSU (Months 4–6)

**Goal:** Replace Paulina's manual EM entries with AllowED submissions.

1. **Implement Lighthouse enrollment submission** — either Benefits Intake (PDF per student) or the forthcoming VA enrollment API
2. **Update VBA Remarks auto-selection** in `em_integration.py` with all 11 correct options from `EM_Interface_Reference.md`
3. **Wire `weams_programs.py` to load from `weams_all_schools.json`** — dynamic loading instead of hardcoded lists
4. **Production deployment** — determine server target, set up process supervision, configure .env for production keys
5. **Enrollment monitoring scheduler** — `enrollment_monitor.py` needs a scheduler (cron or event hook) to continuously compare PS snapshots

### Phase 3 — CSU System Scale (Months 7–12)

**Goal:** Expand beyond SDSU to other CSU campuses.

1. **Multi-institution config** — institution registry keyed by facility code (25 schools already in `weams_all_schools.json`)
2. **Per-institution WEAMS crosswalk** — load dynamically by facility code
3. **Per-institution PS connection** — each CSU campus has its own PS instance
4. **T&F bursar feed** — integrate with each campus's bursar process (varies by school)
5. **Admin multi-school dashboard** — `allowed_admin.html` already has placeholder metrics; wire to real data
6. **FedRAMP planning** — if running on cloud, begin authorization process here

---

## SECTION F: Files Chilly Should Read in Order

Read these five documents in this order. Estimated time: 45 minutes.

1. **`VA_Certification_Automation_Project_Brief.md`** — Start here. The full problem statement, all system requirements (R1–R8), regulatory foundation (38 CFR), key contacts, and go-to-market context. Read the whole thing. 15 min.

2. **`Course_Applicability_Decision_Tree_v02.docx`** — The SCO Handbook rules translated into a decision tree. Contains the James Roster canonical test case with all course-level decisions explained. This document is what `decision_tree.py` implements. 10 min.

3. **`EM_Interface_Reference.md`** — Live screen recording analysis of VA Enrollment Manager. Every field name, every dropdown option (VBA Remarks and Amendment Reasons — the correct ones), every business rule visible in the UI. Read this before touching `em_integration.py` or `enrollment_monitor.py`. 5 min.

4. **`Technical_Integration_Spec_v1.docx`** — The PeopleSoft schema (12 tables with column-level detail), Lighthouse API architecture, enrollment monitoring SQL approach, net tuition pipeline, WEAMS crosswalk design, and HITL trigger spec. This is what Chilly needs to build the PS connector. 10 min.

5. **`Rounding_Out_Verification_Spec_v1.docx`** — The 5-step final-term algorithm with decision matrix, edge cases, and EM submission details. Relevant once Phase 1 is stable. 5 min.

**Supplementary (read when relevant):**
- `PS_to_EM_Data_Dictionary_v1.xlsx` — 6-sheet field mapping reference; use when building PS connector
- `Mamie_Miller_Process_Transcript_Annotated.md` — Business logic for enrollment change detection; 11 key findings
- `EM_Field_Mapping_F4_v1.docx` — Detailed EM field mapping for dual certification workflows

---

## SECTION G: Problems Flagged Honestly

### ✅ Bug 1 — AmendmentReason Enum (enrollment_monitor.py) — FIXED April 18
The enum had 5 wrong option strings. Replaced with the exact 8 EM dropdown strings from live screen recordings. Routing logic (`_map_change_to_reason`) also updated: added `WITHDREW_BEFORE_TERM` for pre-term drops, split post-deadline withdrawals into `WITHDREW_POST_DROP_NONPUN` (default) vs `WITHDREW_POST_DROP_PUN`, mapped graduation and program change to `OTHER` (graduation uses EM checkbox, not reason dropdown). All 8 test suites (90/90 checks) green.

### 🟡 Warning 2 — pipeline.py Is Not Wired to Real Data
**Severity: Medium.** The pipeline passes all 6 integration tests, but every test uses fabricated input. The four placeholder comments (DOB, emplid, tuition, rounding-out) mean that `pipeline.py` cannot process a real PS student record without being updated first. The tests prove the orchestration logic is correct; they do not prove the data layer works.

### 🟡 Warning 3 — app.py Has No Auth and Is Debug Mode
**Severity: Medium for demo, High for production.** Running `python3 app.py` starts a Flask development server on port 5000 with `debug=True` and no authentication. Fine for showing to Frazee. Not deployable. Before any external-facing demo, add at minimum a static API key header check.

### 🟡 Warning 4 — LighthouseClient HTTP Calls Are Not Implemented
**Severity: Medium.** `em_integration.py` contains a `LighthouseClient` class with `submit_enrollment()` and `submit_amendment()` methods. In non-mock mode, these methods have a TODO comment and return fabricated responses. The Benefits Intake PDF upload IS real (in `va_api_client.py`), but the enrollment API submission is not. Chilly needs to decide: implement Benefits Intake submission per student, or wait for VA to release a proper enrollment API.

### 🟢 Note 5 — weams_programs.py Should Load Dynamically
**Severity: Low.** Currently 853 programs are hardcoded Python lists. `weams_all_schools.json` now has 6,543 programs across 25 universities. Adding a new school requires editing the Python source. This should be refactored to load from JSON — probably a 2-hour task.

### 🟢 Note 6 — No DARS Integration Exists
**Severity: Low for pilot, High for production.** Every test that touches DARS data (course applicability, remaining units, rounding-out eligibility) uses hardcoded values. The spec describes using `SAA_RPT_RQST` to programmatically request degree audits from PeopleSoft, but this is not coded. For the shadow-mode pilot, Paulina can manually verify DARS results alongside the system. For production, this must be solved.

---

*Handoff document prepared April 17, 2026. Code audited against live file system — all test results are from actual runs, not estimated.*
