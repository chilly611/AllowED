# VA Enrollment Certification Automation — Full Project Brief

**Project:** Automating the school certification process between higher education institutions and the VA to verify and certify student enrollment for GI Bill benefits release.

**Team:** Chilly (lead / software architect), Paulina (domain expert / SDSU Veterans Center staff, School Certifying Official)

**Date:** March 28, 2026 (updated March 31, 2026)

---

## 1. Problem Statement

School Certifying Officials (SCOs) at universities manually certify student enrollment for GI Bill benefits. At SDSU, the largest military-connected school in California, the current process allows a maximum of 10–20 student certifications per day at peak times. There are approximately 800 GI Bill students per semester who need certification.

This creates delays of 30–90+ days. Students have reported waiting months for certifications to process. The SCO must manually pull up each student's schedule and degree program, certify once in PeopleSoft (Military and Veterans Module), then certify again in the VA's Enrollment Manager — a redundant double-entry process.

**The goal:** Certify all 800 students on day one of the semester. No more 10 at a time. Everyone gets certified the day classes start so their benefits process immediately.

---

## 2. Current Workflow (As Described by Paulina)

### The Double-Certification Problem

1. The SCO pulls up a student's schedule and degree program manually
2. The SCO certifies the student in **PeopleSoft's Military and Veterans Module** (distance and residential units are entered here)
3. The SCO then turns around and certifies the **same student again** in the VA's **Enrollment Manager**
4. This is fully manual — the two systems don't talk to each other

### The Enrollment Change Problem

- Students don't always self-report enrollment changes (e.g., dropping from 12 units to 6)
- Per 38 CFR regulations, what matters for dual certification is **enrollment changes at or below half-time enrollment**
- If a student drops to 3/4 time, they still get paid — that's fine
- But dropping to half-time or below triggers a required update to the VA
- Currently the Bursar's office is supposed to run daily reports on changes, but only one person (Mamie Miller) does this, and she's about to retire
- The software needs to automatically detect enrollment changes from PeopleSoft and update Enrollment Manager accordingly

### Mamie Miller's Enrollment Change Process (Captured March 31, 2026)

Mamie Miller in the Bursar's office runs PeopleSoft queries manually at three checkpoints:
1. **Before add/drop period** — baseline enrollment snapshot
2. **At census** — compare against baseline to catch changes
3. **After census** — final comparison to catch post-census changes

She detects enrollment changes by comparing query results across these checkpoints. **This is NOT real-time** — queries run weekly or biweekly. If she doesn't run them, changes are missed entirely. There is no automated alerting.

**This is a critical automation opportunity.** The software should monitor enrollment changes continuously, replacing this manual query-and-compare process. Full details of her specific PeopleSoft queries and comparison logic still need to be captured before she retires.

### Key Systems in Play

| System | Owner | Role |
|--------|-------|------|
| **PeopleSoft Campus Solutions** | SDSU IT (Cyndie Winrow, AVP ERP Systems) | Student Information System — stores enrollment, schedule, degree data |
| **PeopleSoft Military & Veterans Module** | Recently deployed at SDSU (last CSU to get it) | Where SCO does first certification — distance/residential units |
| **VA Enrollment Manager** | U.S. Department of Veterans Affairs | Where SCO does second certification — submits to VA for benefits processing |
| **Bursar's Office / PeopleSoft** | SDSU Finance | Tuition and fee data — needed for accurate certification |
| **DARS (Degree Audit Report)** | PeopleSoft | Authoritative source for course applicability. Expected graduation date is the only source for final-term identification. |

### The PeopleSoft Military & Veterans Module

- Paulina worked with **Jen Christensen** to develop and deploy this module at SDSU
- SDSU was the **last CSU campus** to get this module — every other CSU already has it
- This means every CSU campus has the same PeopleSoft module, making system-wide integration feasible
- The module already contains the certification data (distance/residential units, degree, enrollment status)
- **This is the key integration point** — the software connects the M&V Module to Enrollment Manager

---

## 3. Software Requirements

### Core Requirement: Automated Pipeline

**PeopleSoft Military & Veterans Module → [Our Software] → VA Enrollment Manager**

The SCO already enters data once in PeopleSoft. The software eliminates the second manual entry by automatically pushing that certification to Enrollment Manager.

### Specific Functional Requirements

#### R1: Bulk Semester Certification
- On semester start, certify all eligible students (up to 800+) in a single batch
- Pull enrollment data, schedule, and degree program from PeopleSoft M&V Module
- Apply 7-step Course Applicability Decision Tree (see `Course_Applicability_Decision_Tree_v02.docx`)
- Generate and submit certifications to VA Enrollment Manager
- Target: same-day processing for all students on first day of classes

#### R2: Enrollment Change Monitoring
- Continuously monitor PeopleSoft for enrollment changes (replaces Mamie Miller's manual query process)
- **Critical trigger:** Student drops to or below half-time enrollment
- Automatically update Enrollment Manager when changes occur
- Must detect: unit drops, course withdrawals, program changes, credit-to-audit changes
- Must catch changes between add/drop, census, and post-census — not just at checkpoint dates

#### R3: Dual Certification Data Sync
- Per 38 CFR, must accurately report: tuition, fees, supplies, enrollment dates, and program information
- Pull tuition and fee data from Bursar's office (PeopleSoft financial module)
- Automatically scrub, validate, and update data
- Generate alerts when data changes that affect certification

#### R4: Integration Approach
- **Read from:** PeopleSoft Military & Veterans Module (enrollment, units, degree)
- **Read from:** PeopleSoft Bursar/Financial module (tuition, fees)
- **Read from:** DARS / Degree Audit (course applicability, expected graduation date)
- **Write to:** VA Enrollment Manager (certifications, updates)
- Paulina's preference: a lightweight connector ("like a clawbot") that sits between systems rather than replacing Enrollment Manager

#### R5: Student Self-Service Trigger
- Students can self-certify to trigger the process through my.SDSU
- But the system cannot rely solely on student self-reporting (students forget to report drops)
- PeopleSoft enrollment data is the authoritative source, not student input

#### R6: Alerts and Notifications
- Alert SCO when enrollment changes affect certification
- Alert when tuition/fee changes require certification updates
- Alert when data discrepancies are detected between systems
- Alerts go to the company (Veterans Center), not solely to an individual SCO

#### R7: Rounding-Out Verification (New — March 31, 2026)
- Cross-reference DARS expected graduation date + remaining required units to determine if student is in final term
- Flag rounding-out requests for SCO validation
- Verify that the student is below full-time without the rounding-out course
- Verify course meets REMOTE Act criteria (PL 117-76)
- **Currently no way to verify rounding-out claims** — this is a compliance gap the software fills

#### R8: Course Applicability Rule Engine (New — March 31, 2026)
- Implement the 7-step decision tree from `Course_Applicability_Decision_Tree_v02.docx`
- Step 1: WEAMS program match (requires crosswalk table to be built)
- Step 2: DARS degree applicability check + 3 SCO exception workflows
- Step 3: Audit check
- Step 4: Repeat course check
- Step 5: Remedial check (**online/hybrid remedial = NEVER certifiable, per handbook**)
- Step 6: Modality classification (hybrid threshold: one 50-min session during term)
- Step 7: Rate of pursuit / training time calculation (configurable for grad programs)

---

## 4. Regulatory Foundation

### 38 CFR Part 21 — Key Finding

The regulation specifies the **data content** that must be reported (tuition, fees, supplies, enrollment dates, program information) but does **NOT mandate that a human submit the certification**. This is the legal basis for automation.

### SCO Handbook Rev 7.4 (June 26, 2025)

The SCO Handbook is the regulatory authority for all certification rules. A copy has been uploaded and verified against the Decision Tree v0.2. Key rules now cite exact handbook language and statutory authority (CFR/USC sections). SDSU follows the VA handbook minimum for all rules — no higher internal standards.

### Key Handbook Rules Verified (March 31, 2026)

| Rule | Handbook Language | Authority |
|------|-------------------|-----------|
| Course applicability | "Only courses that satisfy requirements outlined by the curriculum guide or graduation evaluation form can be certified for VA purposes." | SCO Handbook, Course Applicability |
| Hybrid = residential | "Hybrid training must have at least one session that meets the definition of a standard class session (i.e. one 50-minute class) but does not have to meet weekly." | 38 U.S.C. 3313(c)(1)(B)(iii) |
| Pre-term ≠ residential | "A course has an in-residence meet-up before the term begins. During the actual term all training is conducted online." = distance | Handbook Example 5 |
| Remedial online = never | "Remedial and deficiency courses offered in an online or hybrid format cannot be approved for VA benefits and cannot be certified to VA under any chapter." | SCO Handbook, Remedial section |
| Practicum = residential | "Practical training courses are considered to be resident training." | 38 CFR 21.4275 |
| Rounding out | Final term only, once per program, REMOTE Act (PL 117-76) criteria apply | SCO Handbook + REMOTE Act |
| Course substitutions | "If the college allows substitutions for program requirements, VA will allow course substitutions if the school approves them and they are documented in the student's file." | SCO Handbook, Course Substitutions |

### Data Requirements per 38 CFR

- Tuition and fees (accurate, from Bursar's office)
- Supplies
- Enrollment dates
- Program information (degree, major)
- Enrollment status (full-time, 3/4, half-time, less than half-time)
- Credit hours (distance vs. residential — already tracked in M&V Module)

### Compliance Standards

- VA's own accuracy benchmark: 97%+
- Automated system should match or exceed this
- Full audit trail required for every certification action
- Built-in fraud detection for anomalous patterns

---

## 5. Technical Architecture (Proposed)

### Integration Points

```
┌─────────────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│   PeopleSoft SIS    │     │   Our Software   │     │  VA Enrollment Mgr  │
│                     │     │                  │     │                     │
│ ● M&V Module ───────┼────►│ ● Data Extraction│     │                     │
│   (certifications)  │     │ ● Rule Engine    │────►│ ● Certification     │
│                     │     │   (7-step tree)  │     │   Submission        │
│ ● Bursar/Finance ───┼────►│ ● Validation     │     │                     │
│   (tuition, fees)   │     │ ● Audit Logging  │     │                     │
│                     │     │ ● Fraud Detection│     │                     │
│ ● DARS ─────────────┼────►│ ● Change Monitor │────►│ ● Updates           │
│   (degree audit)    │     │ ● Rounding-Out   │     │                     │
│                     │     │   Verification   │     │                     │
│ ● Enrollment ───────┼────►│ ● Alerts (R6)    │     │                     │
│   (schedule/units)  │     │                  │     │                     │
└─────────────────────┘     └──────────────────┘     └─────────────────────┘
```

### VA Systems for Integration

- **Enrollment Manager** — Primary submission target (replaced VA-ONCE in March 2023)
- **VA Lighthouse API** (developer.va.gov) — Open API platform for third-party integration
- **Education Benefits API** — Available through VA Developer Portal

### PeopleSoft Integration

- All 23 CSU campuses run PeopleSoft Campus Solutions
- All have the Military & Veterans Module (SDSU was last to deploy)
- Single integration pattern covers the entire CSU system
- Read-only access initially — no writes to PeopleSoft

---

## 6. Key People and Contacts

### Project Team

| Person | Role | Contact |
|--------|------|---------|
| Chilly | Project lead, software architecture | chillyd@gmail.com |
| Paulina | Domain expert, SCO, SDSU Veterans Center | paulina0101@gmail.com |

### SDSU Stakeholders

| Person | Role | Notes |
|--------|------|-------|
| **James Frazee** | VP for IT & CIO, SDSU | Primary approval target. Led CSU-wide AI Summit. Pro-AI, pro-innovation. Named top-5 educational tech leader. |
| **Cyndie Winrow** | AVP, ERP Systems, SDSU | Controls PeopleSoft. 26+ year tenure. Historically cautious about new software. Must be brought along carefully — get Frazee's support first, then approach her. |
| **Jen Christensen** | PeopleSoft M&V Module developer | Paulina's existing contact. Worked together to deploy the M&V Module at SDSU. Potential technical ally. |
| **Mamie Miller** | Bursar's Office | Runs enrollment change PeopleSoft queries manually at add/drop, census, and post-census checkpoints. About to retire — her process and specific queries must be captured before she leaves. |

### CSU System

| Person | Role | Notes |
|--------|------|-------|
| **Mildred Garcia** | Chancellor, CSU System | First Latina to lead a 4-year public system. Committed $16.9M to AI initiative. Paulina's background as Latina educator is a networking asset. |

### VA / Federal

| Person | Role | Notes |
|--------|------|-------|
| **Doug Collins** | Secretary, U.S. Dept. of Veterans Affairs | Air Force Reserve Colonel. Pro-AI. VA already automating 65% of claims. $7.3B IT budget. |

---

## 7. Go-to-Market Strategy (Summary)

Three parallel pitch tracks, each reinforcing the others:

### Track 1: SDSU Pilot
- 90-day zero-cost pilot at SDSU Veterans Center
- Read-only PeopleSoft integration, shadow mode alongside manual process
- Pitch to James Frazee emphasizing AI innovation, equity for veterans, and CSU leadership positioning
- Use Paulina as internal champion
- Success metric: certify a semester cohort faster and more accurately than manual process

### Track 2: CSU Chancellor's Office
- Position for inclusion in Chancellor Garcia's $16.9M AI initiative
- Leverage that all 23 CSU campuses run PeopleSoft with the M&V Module — one integration covers the system
- Paulina connects with Garcia's office through equity/veteran student advocacy
- Frazee sits on CSU AI Workforce Acceleration Board and can advocate internally

### Track 3: VA National
- Register on VA Lighthouse API (free, immediate)
- Apply for SBIR Phase I ($50K–$300K, 40–60% first-timer success rate)
- Build working Lighthouse API integration using pilot data from SDSU
- Pursue congressional introduction once pilot results are in
- Frame as extending VA's 65% claims automation to education certification

### Procurement Vehicles
- **SBIR Phase I** — First federal credibility milestone (awaiting Congressional reauthorization)
- **VA Lighthouse API** — Free developer access, build integration now
- **Other Transaction Authority (OTA)** — Fast-track prototype contracts (70–120 days)
- **FedRAMP** — Required eventually for cloud services handling government data (6–18 months)

---

## 8. Integrated Timeline

| Timeframe | Track 1: SDSU | Track 2: CSU | Track 3: VA |
|-----------|--------------|-------------|-------------|
| **Months 1–2** | Meet with Frazee. Get Paulina's endorsement. Build prototype. | Research CSU AI initiative application. Draft proposal. | Register on Lighthouse API. Begin SBIR application. |
| **Months 3–5** | 90-day pilot begins. Shadow mode alongside manual process. | Submit CSU AI initiative proposal. Connect Paulina with Chancellor's office. | Build Lighthouse integration. Submit SBIR Phase I. |
| **Months 6–8** | Pilot results published. Decision on continued use. | Present results to CSU AI Workforce Board. | SBIR decision. Demo integration to VA OIT. |
| **Months 9–12** | Production at SDSU. Build case study. | Three-campus pilot (SDSU + 2). System-wide evaluation. | Use pilot data for Phase II or OTA. Congressional intro. |

---

## 9. Paulina's Audio Notes — Full Transcriptions

### Recording 1 (Original) — The Vision
> Goal: Currently an SCO at the biggest military-connected school in California certifies a maximum of 10–20 students at peak times. Want the software to certify all 800 kids at semester start so there is no delay. The day classes start, their application is processed that same day. No more waiting 30, 60, 90+ days. Everything automated — all 800 kids that request it, certified at once.

### Recording 2 — Dual Certification and Enrollment Changes
> For dual certifications, 38 CFR specifies data that must be reported: tuition, fees, supplies, enrollment dates, program info. One pathway is student self-certification, but students don't always report changes (e.g., dropping from 12 to 6 units). If a student drops to 3/4 time they still get paid. What matters is enrollment changes at or below half-time. The system needs enrollment change data from PeopleSoft, not just student triggers.

### Recording 3 — The PeopleSoft M&V Module Connection
> Paulina worked with Jen Christensen to deliver the Military and Veterans Module — the final addition to PeopleSoft at SDSU. The SCO already certifies in PeopleSoft through this module (distance and residential units). That data is already being entered. The software needs to connect the M&V Module to Enrollment Manager — that's the key connection point.

### Recording 4 — Double Entry Problem and Integration Vision
> Paulina worked with Jen Christensen to develop the Veterans module, which was the last piece of PeopleSoft. Every other CSU already has it. The SCO certifies once in PeopleSoft, then certifies again in Enrollment Manager. It's still manual because they have to pull up the student's schedule and degree. If they're already doing it once, the software just connects it to Enrollment Manager and the VA.

### Recording 5 — Bursar Integration and Change Monitoring
> For dual certifications, report tuition and fees accurately. Software must alert when changes occur. This requires info from the Bursar's office — Mamie Miller runs reports but is about to retire. PeopleSoft and Bursar's office need to communicate. Software needs to automatically scrub data, update it, and push changes to Enrollment Manager. Paulina prefers a lightweight add-on ("like a clawbot") rather than replacing Enrollment Manager, as the VA won't change EM for everyone. A lightweight connector would make them more inclined to adopt.

---

## 10. Open Questions and Next Steps (Updated March 31, 2026)

### Resolved
1. ~~Half-time threshold logic~~ — **RESOLVED:** UG: 12+ = full-time, 9-11 = 3/4, 6-8 = 1/2. Grad: Master's 9+, Doctoral 6+, Thesis/Dissertation = full-time regardless. See Decision Tree v0.2 Step 7.
2. ~~Bursar data feed~~ — **PARTIALLY RESOLVED:** Mamie Miller runs PeopleSoft queries manually at add/drop, census, and post-census. Compares results to catch changes. Weekly/biweekly. Full query details still needed.

### Still Open
3. **PeopleSoft API access:** What APIs or data export methods does the M&V Module support? Need to confirm with Jen Christensen or Cyndie Winrow.
4. **Enrollment Manager API:** Does EM have an API for programmatic submission, or does it require browser automation? Check VA Lighthouse API coverage.
5. **Mamie Miller's specific PeopleSoft queries:** We know she runs queries at three checkpoints — but need the actual query names/parameters and what she compares. **URGENT before she retires.**
6. **F2: Advisor approval form details:** What does the form look like? Where does it live (scanned, digital, physical)? Blocks exception queue implementation.
7. **F4: Ch33 dual certification EM walkthrough:** Paulina is sending this April 1, 2026. Blocks EM submission module.
8. **Jen Christensen relationship:** Paulina's existing working relationship with the M&V Module developer is a significant asset. Schedule follow-up.
9. **FedRAMP planning:** When should the FedRAMP authorization process begin?

---

*This document is the single source of truth for the VA Enrollment Certification Automation project. It combines software requirements (from Paulina's audio notes), go-to-market strategy (from market research), stakeholder intelligence, and technical architecture into one reference. Use it as project context in Claude or any other AI tool to maintain continuity across sessions.*
