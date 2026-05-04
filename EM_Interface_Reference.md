# VA Enrollment Manager — Complete Interface Reference
**Source:** Screen recordings from Paulina's live EM session (April 1, 2026)  
**Purpose:** Backend implementation reference for AllowED certification automation platform  
**Recordings analyzed:** 8:41 PM (22 min) + 9:07 PM (23 min) = 275 frames extracted at 10-second intervals

---

## 1. NAVIGATION STRUCTURE

**Main Tabs:**
- Dashboard
- Students
- Schools
- Reports

**Top Bar:**
- Institution selector dropdown — format: `[Facility Code] - [School Name]`  
  Example: `1190S143 - SAN DIEGO STATE UNIVERSITY`
- User indicator (e.g., `EM_SCO IHL` for IHL program SCOs)

**Breadcrumbs:**
- `Students > [Student Name]` when viewing a student profile
- `Schools > Edit Pre-set enrollment` when managing pre-sets

---

## 2. VBA REMARKS DROPDOWN — Complete Option List

**Field label:** "VBA remarks"  
**Behavior:** Multi-select. Additional custom text can be added via "+ Add Custom Remark" button.  
**Default:** "Select"

| # | Exact Option Text |
|---|-------------------|
| 1 | *(Select)* — placeholder/default |
| 2 | Clock Hours for this student are approved to be taken online. |
| 3 | Compliance Survey |
| 4 | Correcting previously terminated enrollment. Notice of Change in Student Status(s) to follow. |
| 5 | Dual Degree Program |
| 6 | Incarcerated Student |
| 7 | Practical Training Course(s) taken. |
| 8 | Remedial training course(s) taken. Required for VABE students only. |
| 9 | SA: Non-accredited Training |
| 10 | Student is using GI-SD Tuition Assistance Top-Up. Reported T&F is the remaining out of pocket expenses. |
| 11 | Tuition and Fees is in foreign currency |
| 12 | Tuition has not changed. Flat rate is charged for 12 or more credits. |

**Auto-select logic for AllowED:**
- "Dual Degree Program" → auto-select when student has 2 active ACAD_PLANs in PeopleSoft
- "Remedial training course(s) taken." → auto-select when remedial credits > 0
- "Practical Training Course(s) taken." → auto-select when practicum courses present in enrollment
- "Tuition has not changed. Flat rate is charged for 12 or more credits." → auto-select when student is ≥12 credits with flat-rate billing

---

## 3. AMENDMENT REASON DROPDOWN — Complete Option List

**Field label:** "Amendment Reason"  
**Required:** Yes  
**Default:** "Select"

| # | Exact Option Text |
|---|-------------------|
| 1 | *(Select)* — placeholder |
| 2 | Pre-registered but never attended |
| 3 | Unsatisfactory attendance, progress or conduct |
| 4 | Withdraw before beginning of term |
| 5 | Withdraw after drop period - non-punitive grades assigned |
| 6 | Withdraw after drop period - punitive grades assigned |
| 7 | Withdraw during drop period |
| 8 | Withdrawal or interruption (Non-College Degree Programs not on a term basis) |
| 9 | Other |

**Mapping to PeopleSoft enrollment change events:**

| EM Amendment Reason | PS Trigger Condition |
|---------------------|----------------------|
| Pre-registered but never attended | Student enrolled at term start but LAST_DROP_DT_STMP < add/drop deadline with no attendance record |
| Unsatisfactory attendance, progress or conduct | Academic standing flag or administrative withdrawal in STDNT_ENRL |
| Withdraw before beginning of term | Drop date before term begin date |
| Withdraw after drop period - non-punitive grades assigned | Drop after census; grade = W, WU, etc. (non-punitive) |
| Withdraw after drop period - punitive grades assigned | Drop after census; grade = WF or equivalent (punitive) |
| Withdraw during drop period | Drop between term start and census date |
| Withdrawal or interruption (Non-College Degree Programs...) | NCD/clock-hour programs only |
| Other | Anything not covered above; requires SCO review |

---

## 4. ENROLLMENT CERTIFICATION FORM — All Fields

**Form title:** "Add [LEVEL] enrollment" (e.g., "Add UNDERGRAD enrollment")

### Section 1: Enrollment Information
| Field | Type | Required | Notes |
|-------|------|----------|-------|
| Academic information | Dropdown | ✓ | Format: `[Facility Code] - [School Name]`. Drives benefit type, objective type, program name. |
| Benefit type | Read-only | — | Auto-populated from Academic information selection (e.g., "Chapter 33") |
| Objective type | Read-only | — | Auto-populated (e.g., "Bachelor of Science") |
| Program name | Read-only | — | Auto-populated (e.g., "BS BIOLOGY") |
| Enrollment name | Text | — | Links to pre-set enrollment. Use pre-set ID from Schools tab. |
| Begin date | Date (MM/DD/YYYY) | ✓ | Must match semester start |
| End date | Date (MM/DD/YYYY) | ✓ | Must match end of finals week |

### Section 2: Credits and Tuition
| Field | Type | Required | Notes |
|-------|------|----------|-------|
| Resident credits | Numeric | — | IHL residential hours (in-person/hybrid) |
| Online credits | Numeric | — | IHL distance learning hours |
| Clock hours | Numeric | — | NCD programs only; 0 for SDSU IHL |
| Remedial/Deficiency credits | Numeric | — | Only if remedial courses present |
| Tuition & Fees amount | Numeric | ✓ | Chapter 33: net tuition (from SSR_VB_TUI_WRK_FED after census). Chapter 35: gross tuition. |

### Section 3: Vacation Periods
- "+ Vacation period" button
- Only for non-standard terms (outside 15–19 week semester / 10–13 week quarter)
- All NCD clock-hour programs are considered non-standard

### Section 4: Remarks
- VBA remarks dropdown (see Section 2 above)
- "+ Add Custom Remark" button for free-text

### Section 5: Notes (optional)
- Text area, up to 1024 characters
- **Not submitted to VA** — stored in student profile only
- Warning: Do not include PII; subject to FOIA

### Submission
- "Submit enrollment" (blue button)
- "Save as draft"
- "Discard edits"
- "Return to log"
- Certification statement (red text): *"By submitting this record, I certify that the previous statements are true and correct to the best of my knowledge and belief."*

---

## 5. PRE-SET ENROLLMENT — Fields and Workflow

**Location:** Schools tab → Pre-set Enrollment table  
**Purpose:** Template that sets semester dates. All student certifications for the semester reference the pre-set by name.

### Create/Edit Pre-set Form Fields
| Field | Type | Required | Notes |
|-------|------|----------|-------|
| Name | Text | ✓ | Unique abbreviation, e.g., "2025 Fall", "Spring 26" |
| School | Dropdown | ✓ | Format: `[Facility Code] - [School Name]` |
| Begin date | Date | ✓ | Semester start date |
| End date | Date | ✓ | End of finals week |
| Active checkbox | Checkbox | — | Inactive pre-sets don't appear in enrollment dropdown |

**Buttons:** "Create Pre-set enrollment" / "Cancel"

**Auto-creation rule for AllowED:**  
Create pre-sets at start of each term using PS `ACAD_CAREER` term table dates (term start → last day of finals). Name format: `[YEAR] [TERM]` (e.g., "2026 Fall").

**Important restrictions:**
- Not available for Apprenticeship, Flight, or OJT training types
- If pre-set is inactive, it won't appear in student enrollment dropdowns

---

## 6. AMENDMENT WORKFLOW — Step by Step

1. Students tab → Find student
2. Open student profile → Enrollments tab
3. Click existing certified enrollment
4. Click "Amend" button
5. Amendment form opens with:
   - **Amendment Reason** (Required dropdown — see Section 3)
   - **Amendment effective date** (Required — MM/DD/YYYY)
   - Credits and tuition section (editable)
   - Checkboxes: "Graduation/End of Term or Course" | "Termination"
   - Remarks section
   - Notes section
   - Certification statement + "Submit amendment" button

---

## 7. STUDENT LOOKUP — How Students Are Found

**Method 1: Students tab**
- Table shows: First Name, Last Name, Status, Last edited on, Last edited by
- Click student name link to open profile

**Student Profile Tabs:**
- Enrollments
- Student Info
- Programs
- Benefits
- Notes
- History

**Student Info shows:**
- Student ID (this is the emplid / VA Student ID)
- Contact info (email, phone, mailing address)

**Method 2: Search**
- If student previously attended another school: look up by **name + date of birth** in EM
- SSN is NOT accessible in the EM interface

**Right sidebar on student profile:**
- CURRENT BENEFIT section (type, remaining entitlement, level)
- PENDING BENEFIT section
- Contact info with Edit button

---

## 8. BUSINESS RULES / VALIDATION

Rules displayed in EM UI (exact text):

1. **Advance submission window:**  
   > "Enrollments cannot be submitted more than 180 days in advance for Chapter 33 Benefit types and 120 days for non-Chapter 33 benefit types."

2. **Pre-set restrictions:**  
   > "Pre-set Enrollments are not applicable to Apprenticeship, Flight, or On-the-Job Training enrollments."

3. **PII warning:**  
   > "Please do not include a student's Personal Identification Information (PII) in a note. Data entered in VA systems is subject to the provisions of the Freedom of Information Act (FOIA)."

4. **Non-standard terms:**  
   > "Should only be included for non-standard length terms. Standard terms are: 15–19 weeks (semester) or 10–13 weeks (quarter). All NCD programs measured in clock hours are considered non-standard."

---

## 9. SUCCESS MESSAGE FORMAT

```
Success! [SCHOOL NAME] ([FACILITY CODE]) [BEGIN DATE] - [END DATE] has been added as an [enrollment/amendment].
```
Example: `Success! SAN DIEGO STATE UNIVERSITY (1190S143) 08/25/2026 - 12/15/2026 has been added as an enrollment.`

---

## 10. DASHBOARD

**"Your Actions" table columns:** First Name | Last Name | Status | Last edited on | Last edited by  
**Status values:** In Progress | SUBMITTED | DRAFT  

**Helpful Resources section:**
- School Certifying Official Handbook link
- GI Bill Comparison Tool
- Application for benefits
- General education information
- VA Education Liaison Representative (regional contact info)

---

## 11. KEY IDENTIFIERS

| Identifier | Where It Lives | Used For |
|-----------|----------------|----------|
| VA Student ID (emplid) | Student profile in EM | Linking PS student to EM record |
| Facility Code | Academic information dropdown | Identifying the certifying school |
| Pre-set Name | Schools tab | Linking enrollment to semester dates |
| ICN (Integrated Control Number) | Lighthouse APIs only | Not visible in EM UI |
| SSN | PS SCC_PERDATA_QVW only | NOT accessible in EM |

---

## 12. PAGE IDENTIFIER

- Footer shows: `EM102a` (IHL certification module)
- This is the module Paulina uses for all SDSU certifications

---

*Document generated April 17, 2026 from analysis of 275 frames across two screen recordings.*  
*Source recordings: `/mnt/uploads/Screen Recording 2026-04-01 at 8:41:07 PM.mov` and `9:07:56 PM.mov`*
