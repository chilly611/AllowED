# Project Instructions for Claude

**IMPORTANT: Read this entire file before asking Paulina ANY questions. Every question asked and answered in this project is documented below. Do NOT re-ask resolved questions.**

## Who I Am
I'm Paulina, a School Certifying Official (SCO) at San Diego State University's Joan and Art Barron Military and Veterans Center. I'm the domain expert AND the builder on this project — I know the VA certification workflow inside and out because I do it every day, and I'm building the software with Claude's help. I worked with Jen Christensen to deploy the PeopleSoft Military and Veterans Module at SDSU (the last CSU campus to get it).

## What We're Building
Software that automates the VA enrollment certification process. Right now I certify students manually — once in PeopleSoft's M&V Module, then again in VA Enrollment Manager. That's double entry for every student. At peak times I can only do 10-20 students per day, but we have ~2000 GI Bill students per semester Ch35, Ch33 and CH31. Students wait 30-90+ days for benefits.

The software is the **regulatory compliance bridge** ("clawbot") — it takes raw enrollment data from PeopleSoft, applies every SCO Handbook rule automatically (course applicability, modality classification, rate of pursuit, WEAMS matching, enrollment change logic), and outputs certification-ready data formatted for VA Enrollment Manager via the Lighthouse API.

Goal: all 800+ students requesting certification processed on day one of the semester.

## Project Status (as of April 10, 2026)

**PHASES 1 & 2 COMPLETE. PHASE 3 (MONITORING + DASHBOARD + FRONTEND) STARTING.**

Paulina is building the software herself with Claude as her coding partner. All original questions (Q1-Q10), all follow-up questions (F1-F4, F4-1 through F4-6), and F2 (advisor approval form) are RESOLVED. The PeopleSoft schema is documented. The Lighthouse API integration is designed AND tested against live VA sandbox. The enrollment monitoring approach is finalized. The rounding-out algorithm is specified.

**Claude's role has expanded:** Claude is now both the project assistant AND the hands-on coding partner. Paulina provides domain expertise, requirements, and testing. Claude writes the code, explains technical decisions in plain language, and builds incrementally so Paulina can verify each piece against her real-world workflow.

### What's Been Built (Working Code)

| File | What It Does | Status |
|------|-------------|--------|
| `decision_tree.py` | 7-step per-course rule engine — WEAMS match, DARS check, audit/repeat/remedial gates, modality classification, rate of pursuit | ✅ 63/63 regression checks |
| `weams_programs.py` | 853 real WEAMS programs (SDSU: 531, CSUN: 322) with 3-tier matching engine. Multi-institution via facility code. | ✅ Scraped from VA website |
| `em_integration.py` | Decision Tree → EM field formatting, HITL escalation (7 triggers), Ch.33 net vs Ch.35 gross tuition | ✅ 31/31 regression checks |
| `va_api_client.py` | Live VA Lighthouse sandbox client — Veteran Confirmation API with rate limiter | ✅ Tested against sandbox |
| `benefits_intake.py` | PDF generation (ReportLab) + Benefits Intake 2-step upload (POST → PUT) | ✅ GUID received from VA |
| `.env` | Sandbox API keys (Veteran Confirmation + Benefits Intake) | ✅ Active |
| `Nick_Foster_Certification.pdf` | Generated test certification PDF (4,708 bytes) | ✅ Uploaded to VA sandbox |

### Spec Deliverables (all in the VA Project folder)

| File | What It Contains | Audience |
|------|-----------------|----------|
| `Course_Applicability_Decision_Tree_v02.docx` | 7-step per-course decision tree, SCO-validated, handbook-verified, James Roster test case, all Q&A pairs | Paulina + Chilly |
| `EM_Field_Mapping_F4_v1.docx` | Every Enrollment Manager field mapped to PeopleSoft data source, amendment workflow, business rules | Chilly |
| `Technical_Integration_Spec_v1.docx` | Complete technical spec: PS schema (12 tables), Lighthouse API, enrollment monitoring SQL, net tuition pipeline, WEAMS crosswalk, rounding-out algorithm, HITL triggers, dashboard UX, 4 implementation phases | Chilly |
| `PS_to_EM_Data_Dictionary_v1.xlsx` | Excel data dictionary (6 sheets): PS tables, EM field mappings, amendment reasons, net tuition pipeline, F4 answers, Decision Tree-to-EM mapping | Chilly |
| `Rounding_Out_Verification_Spec_v1.docx` | R7 specification: 5-step verification algorithm, decision matrix, edge cases, EM submission details, audit trail | Chilly |
| `F2_Graduate_Student_Worksheet_Sample.pdf` | Sample advisor approval form (Gabriela Elliott, Master of City Planning). Physical signed document. | Reference |
| `Mamie_Miller_Process_Transcript_Annotated.md` | Annotated transcript of Mamie Miller's meeting — full business logic for enrollment verification, third-party contract coding, VBS status workflow, financial aid timing, campus exclusions. 11 key findings + summary table. | Chilly + Reference |
| `tasks.todo.md` | Task tracker with completed and remaining items | Project management |
| `tasks.lessons.md` | 11 lessons learned from the project so far | Process improvement |

## Key Technical Context
- SDSU uses PeopleSoft Campus Solutions 9.2 with the Military & Veterans Module
- All 23 CSU campuses have this same module — one integration covers them all
- VA uses Enrollment Manager (replaced VA-ONCE in March 2023)
- VA Lighthouse API (developer.va.gov) provides third-party integration. Rate limit: 60 req/min. Benefits Intake API for document submission. Enrollment API forthcoming.
- 38 CFR Part 21 specifies required data but does NOT mandate human submission — automation is legally permissible
- The software uses agentic AI design patterns: Planning (bulk cert decomposition), Reflection (secondary verification agent), Human-in-the-Loop (SCO escalation for edge cases)
- SCO Handbook Rev 7.4 (June 26, 2025) is the regulatory authority. PDF at `/mnt/uploads/www.knowva.ebenefits.va.gov.pdf` (26.2MB). Use `pdftotext` to extract.
- DARS (Degree Audit Report) is the authoritative source for course applicability, with three exceptions (rounding out, advisor approval, course substitution)
- PeopleSoft Common Attribute Framework (CAF) stores veteran data in SSR_VB namespace tables
- **SDSU follows the VA handbook minimum for all rules** — no higher internal standards

## PeopleSoft Key Tables

| Table | Purpose |
|-------|---------|
| SSR_VB_DATA | Veterans Benefit Summary: benefit type, Yellow Ribbon eligibility |
| SSR_VB_ATTACH | Benefit attachments: Certificates of Eligibility, advisor forms (Graduate Student Worksheets) |
| SSR_VB_FED_AUD | Federal benefit audit trail |
| SSR_VB_STA_AUD | State benefit audit trail |
| SSR_VB_TUI_WRK_FED | Net tuition calculation for Ch.33 (after aid/waivers). THIS is where net tuition comes from. |
| SSR_VB_TUI_WRK_STA | State benefit tuition calculations (e.g., CalVet waiver) |
| SSR_VB_TF_SETUP | Net Tuition and Fees Setup — maps aid item types for net tuition calculation |
| SSR_VB_INSTR_MAP | Instruction mode mapping (Residential vs Distance Learning) |
| SCC_PERDATA_QVW | Student PII including SSN — maps to VA Student ID in Enrollment Manager |
| ACAD_PROG | Academic program, matriculation status, expected graduation date |
| ACAD_PLAN | Major/plan descriptions — maps to WEAMS via dynamic crosswalk |
| STDNT_ENRL | Enrollment records with LAST_UPD_DT_STMP and LAST_DROP_DT_STMP for change monitoring |
| TUITION_CALC_TBL | Gross tuition assessment for the term |
| SAA_RPT_RQST | DARS report request engine — how to programmatically run degree audits |

Full schema details in `PS_to_EM_Data_Dictionary_v1.xlsx` and `Technical_Integration_Spec_v1.docx`.

---

## ALL RESOLVED QUESTIONS (Do NOT re-ask these)

### Original Validation Questions (Q1-Q10) — Resolved March 31, 2026

| # | Question | Answer |
|---|----------|--------|
| Q1 | Is DARS always authoritative for course applicability? | DARS is primary. 3 exceptions: (1) rounding out in final term per REMOTE Act, (2) advisor approval via signed Graduate Student Worksheet, (3) course substitution with school documentation. |
| Q2 | Does a WEAMS-to-PeopleSoft crosswalk exist? | No. SCO reads program name from top of degree evaluation. Crosswalk must be built. Strategy: VA OData v2 endpoints + fuzzy matching against ACAD_PLAN descriptions. |
| Q3 | Confirm James Roster test case: R:6, D:6, T:12? | Confirmed. ENS 331 (3 units) excluded — not required for B.A. Journalism per DARS. This is the canonical regression test. |
| Q4 | Are hybrid courses classified as residential? | SDSU follows VA handbook minimum: one 50-minute in-person session during the term = residential. Does NOT have to meet weekly. Pre-term sessions do NOT qualify. |
| Q5 | What is graduate full-time? | Master's: 9+ units. Doctoral: 6+ units. Thesis 799A / Research 897 / Dissertation 899 = full-time regardless of units enrolled. |
| Q6 | How fast does DARS update for program changes? | Fast, except impacted majors — those need prerequisites + formal acceptance first. |
| Q7 | Are minor courses certifiable? | Yes, if the minor is declared AND reflected in DARS. Covered under the main program in WEAMS. |
| Q8 | Thesis/practicum/independent study? | Certifiable if required by degree. Practicum = always classified as residential per 38 CFR 21.4275. 799A/897/899 trigger full-time status. |
| Q9 | Do chapter differences affect course applicability? | No. Course applicability rules are chapter-agnostic. (But SUBMISSION rules like tuition calculation DO vary by chapter.) |
| Q10 | What EM fields are needed for dual certification? | Enter Resident (R) and Distance (D) units separately. Pre-conditions: student profile exists, degree unchanged. Ch.33 dual cert: enter zero for the second program. |

### Follow-Up Questions (F1-F4) — Resolved March 31 - April 2, 2026

| # | Question | Answer | Date Resolved |
|---|----------|--------|---------------|
| F1 | What is the hybrid residential threshold at SDSU? | SDSU follows VA handbook minimum: one 50-minute session during the term. No higher internal standard. | March 31 |
| F2 | What does the advisor approval form look like? | SDSU "Graduate Student Worksheet" (form v. 5/2021). Physical signed document listing student name, RedID, degree, all required courses with units, advisor signature. Scanned and stored in SSR_VB_ATTACH. See `F2_Graduate_Student_Worksheet_Sample.pdf`. | April 2 |
| F3 | How is a student's final term detected? | No PeopleSoft flag exists. Only source: expected graduation date in DARS (ACAD_PROG.EXPECTED_GRAD_DT). Student must also notify Veterans Center. Software automates verification via 5-step algorithm in `Rounding_Out_Verification_Spec_v1.docx`. | March 31 |
| F4 | How does the EM dual certification workflow work? | Full EM 102 training module analyzed (47 video frames). All EM fields mapped. See `EM_Field_Mapping_F4_v1.docx`. 4 EM workflows: create pre-set enrollment, add enrollment, edit pre-set, amend enrollment. | April 1 |

### F4 Sub-Questions (F4-1 through F4-6) — ALL Resolved April 2–17, 2026

| # | Question | Answer |
|---|----------|--------|
| F4-1 | What identifier maps PeopleSoft students to EM? | **VA Student ID = emplid (NOT SSN).** SSN is NOT accessible on the EM platform. PeopleSoft stores SSN on the student profile (enrollment verification page) but EM uses emplid as the VA Student ID. If a student previously attended another school, look them up by name and birthday in EM. *(Corrected April 17, 2026 — original answer was wrong.)* |
| F4-2 | Which EM dropdown options appear in the VBA Remarks field? | **RESOLVED from screen recording (April 17, 2026).** 12 options: (1) Clock Hours for this student are approved to be taken online. (2) Compliance Survey (3) Correcting previously terminated enrollment. Notice of Change in Student Status(s) to follow. (4) Dual Degree Program (5) Incarcerated Student (6) Practical Training Course(s) taken. (7) Remedial training course(s) taken. Required for VABE students only. (8) SA: Non-accredited Training (9) Student is using GI-SD Tuition Assistance Top-Up. Reported T&F is the remaining out of pocket expenses. (10) Tuition and Fees is in foreign currency (11) Tuition has not changed. Flat rate is charged for 12 or more credits. Plus "+ Add Custom Remark" for free text. Multi-select. Full reference: `EM_Interface_Reference.md`. |
| F4-3 | Does PeopleSoft calculate net tuition or is it manual? | PeopleSoft calculates net tuition **after census**. Some schools do it manually depending on how financial aid awards are structured. Software should pull from SSR_VB_TUI_WRK_FED after census date. Ch.33 = net tuition; Ch.35 = gross tuition. |
| F4-4 | What Amendment Reasons are available in EM? | **RESOLVED from screen recording (April 17, 2026).** 8 options: (1) Pre-registered but never attended (2) Unsatisfactory attendance, progress or conduct (3) Withdraw before beginning of term (4) Withdraw after drop period - non-punitive grades assigned (5) Withdraw after drop period - punitive grades assigned (6) Withdraw during drop period (7) Withdrawal or interruption (Non-College Degree Programs not on a term basis) (8) Other. Amendment also requires effective date (MM/DD/YYYY) and optional checkboxes: "Graduation/End of Term or Course" and "Termination". Full reference + PS mapping: `EM_Interface_Reference.md`. |
| F4-5 | Does SDSU use clock hours? | **IHL programs use credit hours — not clock hours.** Clock hours do not apply at SDSU for standard degree programs. |
| F4-6 | Does Paulina use pre-set enrollments in EM? | **Yes.** Pre-sets are created and saved in EM based on semester start date and end of finals. Software should auto-create pre-set enrollments at start of each term using these date boundaries. |

---

## Mamie Miller Process (RESOLVED April 2, 2026)

Mamie runs PeopleSoft queries manually at three checkpoints: before add/drop, at census, and after census. She compares query results to detect enrollment changes. This is NOT real-time — queries run weekly or biweekly. If she doesn't run them, changes are missed entirely.

**Her queries are custom-built by SDSU IT** from existing SQLs. She tells IT what she needs and they build the query. SDSU privacy policy may prevent us from accessing the actual query code.

**WORKAROUND (RESOLVED):** We don't need her custom queries. The software builds its own queries against the standard PeopleSoft `STDNT_ENRL` table using `LAST_UPD_DT_STMP` and `LAST_DROP_DT_STMP` fields. This is core PeopleSoft — exists at every CSU campus. Our approach is better: continuous event-driven monitoring vs. periodic manual snapshots.

**Business logic CAPTURED (April 7, 2026):** Full annotated transcript of Mamie's process. See `Mamie_Miller_Process_Transcript_Annotated.md`. Key findings:
- She only processes **Ch.33 students** who have **submitted a certification request** AND been **reviewed by the MVP team**
- VBS status values matter: "In Review" (default, unreliable), "Pending" (being looked at), "Reported" (sent to VA)
- She must code students BEFORE financial aid runs (early January for Spring)
- Students MUST request certification per VA law — rolled-over students without requests must NOT be coded
- She writes "verified + date + entitlement days" on VBS as audit trail
- She handles 4,000+ accounts total, needs clean one-step queries with no manual filtering
- Exclude IBC (Imperial Valley Campus) — they have their own SCOs. Include Main Campus + Global Campus only.

## F2: Advisor Approval Form (RESOLVED April 2, 2026)

The form is the **SDSU Graduate Student Worksheet** (form version 5/2021). Physical, signed document. See sample: `F2_Graduate_Student_Worksheet_Sample.pdf`.

**Form fields:** Date, Student Name, RedID, Degree/Major, total units required, complete course list (course number + title + units), prerequisite/deficiency units, advisor signature + printed name + title, contact number.

**Software logic:** When a course fails DARS applicability (Decision Tree Step 2), check SSR_VB_ATTACH for a scanned Graduate Student Worksheet. If the worksheet lists the course, certify it. If no worksheet exists, flag for SCO exception queue.

## Rounding Out / Final Term Detection (RESOLVED, Full Spec Delivered)

No PeopleSoft flag for final term. Software uses 5-step verification algorithm:
1. Check ACAD_PROG.EXPECTED_GRAD_DT matches current term
2. Call DARS for remaining units required
3. Sum applicable units from Decision Tree
4. If (Applicable < Full-Time) AND (Remaining - Applicable == 0), eligible for rounding out
5. Verify PL 117-76 compliance (no repeats, approved program)

Full spec: `Rounding_Out_Verification_Spec_v1.docx`

---

## WEAMS Program Data — 25 Universities (Updated April 17, 2026)

**Source:** VA GI Bill Comparison Tool API (`api.va.gov/v0/gi/institution_programs/search`)  
**File:** `weams_all_schools.json` — 6,543 programs across 25 universities  
**To add a school to AllowED:** add facility code to `INSTITUTION_REGISTRY` in `weams_programs.py`

| School | Facility Code | Programs |
|--------|--------------|----------|
| Arizona State University (Tempe — use this, NOT 11400109 DC campus) | **11905103** | 1,215 |
| San Diego State University | **11910105** | 538 |
| National University | **31939105** | 501 |
| San Jose State University | **11106005** | 354 |
| CSU San Bernardino | **11913105** | 373 |
| CSU Long Beach | **11924105** | 323 |
| CSU Northridge | **11918105** | 322 |
| CSU Fullerton | **11509205** | 319 |
| CSU Fresno | **11919105** | 284 |
| CSU Dominguez Hills | **11923105** | 265 |
| CSU Los Angeles | **11801905** | 252 |
| San Francisco State University | **11904105** | 249 |
| CSU Sacramento | **11802105** | 223 |
| CSU Stanislaus | **11927105** | 178 |
| Cal Poly Pomona | **11802605** | 171 |
| CSU San Marcos | **11801005** | 154 |
| Cal Poly Humboldt | **11906105** | 137 |
| Cal Poly San Luis Obispo | **11925105** | 123 |
| CSU Chico | **11903105** | 117 |
| CSU East Bay | **11911105** | 125 |
| CSU Bakersfield | **11915105** | 103 |
| CSU Channel Islands | **11929105** | 83 |
| Sonoma State University | **11909105** | 81 |
| CSU Monterey Bay | **11107005** | 44 |
| Cal Maritime Academy | **11700005** | 9 |

**⚠️ ASU note:** Facility code 11400109 = Washington DC campus (1 program). Always use 11905103 for ASU Tempe main campus.

---

## Prioritized Work Queue (Updated April 17, 2026)

### Build Phase 1 — Rule Engine ✅ COMPLETE
1. ~~Build the Decision Tree as working code~~ — `decision_tree.py`, 63/63 regression checks. (April 9)
2. ~~WEAMS dynamic crosswalk~~ — `weams_programs.py`, 853 real programs (SDSU + CSUN), 3-tier matching. (April 10)
3. ~~James Roster end-to-end regression test~~ — 19/19, plus Kitchen Sink (30/30) and Grad Thesis (14/14). (April 9)

### Build Phase 2 — EM Integration ✅ COMPLETE
4. ~~Lighthouse API sandbox~~ — Both APIs registered, sandbox keys active, Benefits Intake upload tested. (April 9)
5. ~~EM field population~~ — `em_integration.py`, HITL escalation, Ch.33/35 tuition rules, 31/31 checks. (April 9)
6. ~~Multi-campus scalability proof~~ — CSUN (11918105) added. Cross-institution isolation verified. (April 10)

### Build Phase 3 — Monitoring, Dashboard & Frontend 🔨 CURRENT
7. **Enrollment change monitoring** — STDNT_ENRL polling logic (replaces Mamie's manual process). Event-driven detection of adds, drops, withdrawals, program changes.
8. **Amendment engine** — Auto-generate EM amendments from enrollment changes. 5 amendment reason types mapped.
9. **SCO dashboard prototype** — Exception-first web frontend: HITL queue, audit trail, status tracking, batch cert actions. This is the demo piece — shows people how it all works.
10. **Rounding-out module** — 5-step final-term verification algorithm (from spec).

### Phase 4 — Polish & Pitch
11. **Frazee pitch deck** — For SDSU CIO approval. Now has a working prototype behind it.
12. **Decision Tree v0.3 document** — Update the Word doc with all build-phase findings.

## How to Help Me
- **I am the builder now.** Claude writes the code. I test it against my real-world workflow. We build incrementally — one piece at a time, verify it works, then move to the next.
- Explain every technical decision in plain language. If I don't understand it, simplify.
- I know the certification workflow better than anyone. Trust my descriptions and build from them.
- When I describe a problem, help me turn it into working code — not just a requirement doc.
- **Always verify rules against the actual SCO Handbook text** — the VA audits by the book. Use `pdftotext` on the handbook PDF, never rely on summaries.
- **Do NOT re-ask questions that are already answered above.** Read this entire file first.
- For pitch or communication materials, keep the tone professional but human
- Reference the project files listed above for full context

## Key People
- **Paulina** — SCO, domain expert, AND builder (with Claude as coding partner)
- **James Frazee** — SDSU CIO, primary approval target, pro-AI
- **Cyndie Winrow** — SDSU AVP for ERP Systems, controls PeopleSoft, cautious about new software
- **Jen Christensen** — Built the PeopleSoft M&V Module with Paulina, potential technical ally
- **Mamie Miller** — Bursar's office, handles Ch.33 third-party contract coding. Business logic fully captured (April 7, 2026). Retiring soon.
- **Mildred Garcia** — CSU Chancellor, committed $16.9M to AI initiative
- **Doug Collins** — VA Secretary, pro-AI, 65% of VA claims already automated
