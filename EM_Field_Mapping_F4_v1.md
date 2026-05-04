# Enrollment Manager Field Mapping
## F4: Dual Certification Walkthrough Analysis

**Source:** VA Enrollment Manager 102 Training Module (NCD & IHL SCOs)  
**Version:** 1.1 | April 16, 2026  
**Prepared for:** Chilly (Software Architect)  
**Domain Expert:** Paulina (SCO, SDSU Veterans Center)

---

**STATUS v1.1:** 4 of 6 questions fully validated. F4-2 (VBA Remarks dropdown) and F4-4 (Amendment Reason dropdown) require a screenshot from Paulina — both are dropdown lists best captured visually. All other fields are implementation-ready.

---

## 1. Executive Summary

This document maps every field in VA Enrollment Manager (EM) to its data source in PeopleSoft and defines how the automation software will populate each one. Based on the EM 102 Training Module for IHL and NCD programs.

Four core EM workflows:
1. Create a Pre-set enrollment
2. Edit a Pre-set enrollment
3. Add and submit a new enrollment certification
4. Amend an existing enrollment certification

> **KEY FINDING:** EM has separate fields for Resident Credits, Online Credits, Clock Hours, and Remedial/Deficiency Credits. This maps directly to the modality classification output from Decision Tree Step 6. The software must split PeopleSoft course-level data into these four EM buckets.

---

## 2. EM Navigation Structure

| Tab | Purpose | Automation Relevance |
|-----|---------|---------------------|
| **Enrollment** | Dashboard, Your Actions queue, VA Education Liaison info | Landing page. Your Actions shows pending certifications. Software monitors for status tracking. |
| **Students** | Student search, student profiles, enrollment history | Primary workspace. Student search + Add enrollment is the core certification path. |
| **Schools** | Pre-set enrollment management | One-time semester setup. Software creates pre-set enrollments at start of each term. |
| **Reports** | Reporting and analytics | Post-submission verification and audit trail. |

---

## 3. Pre-set Enrollment Fields

Pre-set enrollments define the enrollment period (semester dates) reused across all student certifications for that term. Must be created **before** any student certifications can be submitted.

| EM Field | Req? | Format | PeopleSoft Source | Automation Notes |
|----------|------|--------|-------------------|-----------------|
| **Name** | No | Text | Generated: e.g., "Fall 2026" | Auto-generate from PS term code |
| **School** | Yes | Dropdown | Facility Code from WEAMS (11910105 for SDSU) | Map PS Institution to WEAMS facility code |
| **Begin date** | Yes | MM/DD/YYYY | PS Term Begin Date (Academic Calendar) | Pull from PS ACAD_CAREER term table |
| **End date** | Yes | MM/DD/YYYY | PS Term End Date (last day of finals) | Pull from PS ACAD_CAREER term table |
| **Vacation periods** | No | Date ranges | PS Academic Calendar | SDSU standard semesters — typically not needed |
| **Active checkbox** | No | Boolean | N/A | Set to Active when creating. Deactivate after term ends. |

> ✅ **F4-6 VALIDATED (April 16, 2026):** SDSU uses pre-set enrollments. Created from semester start through last day of finals. Software must auto-create pre-sets from PeopleSoft academic calendar before bulk certification runs.

> ⚠️ **IMPORTANT:** Pre-set enrollments cannot be edited once active. To correct: (1) deactivate old pre-set, (2) create new one with correct dates, (3) manually amend all certifications submitted under old pre-set. Validate all dates BEFORE creating.

---

## 4. Student Search and Profile

### 4.1 Student Search

| Search Field | Req? | Format | PeopleSoft Source | Automation Notes |
|-------------|------|--------|-------------------|-----------------|
| **First name** | No* | Text | PS PERSONAL_DATA.FIRST_NAME | Minimum: first 2 letters of last name OR Student ID |
| **Last name** | No* | Text | PS PERSONAL_DATA.LAST_NAME | *At least partial last name or Student ID required |
| **Student ID** | No* | Text | PS EMPLID | See F4-1 answer below |

> ✅ **F4-1 VALIDATED (April 16, 2026):** The VA Student ID used in EM is the student's **EMPLID** from PeopleSoft. Stored on the student's profile (enrollment verification page).
>
> **IMPORTANT EXCEPTION:** If a student previously attended another school, they may already exist in EM under that school's records. In that case, look them up by **name + date of birth** in EM rather than by EMPLID.
>
> SSN is NOT used in EM — not granted on the platform.
>
> **Software implementation:** Primary lookup = EMPLID. Fallback = first name + last name + DOB. If no EMPLID match, trigger name/DOB lookup and flag for SCO review before certifying.

### 4.2 Student Profile

| Profile Element | Content | Automation Relevance |
|----------------|---------|---------------------|
| **Current Benefit** | Active benefit type (e.g., Chapter 33) | Verify matches PS M&V benefit chapter before certifying |
| **Pending Benefit** | Benefit awaiting activation | If pending, flag for SCO review |
| **Benefits remaining** | Months/days of entitlement remaining | Alert SCO if near exhaustion |
| **Contact information** | Email, phone, address | Read-only |
| **Enrollment list** | Facility code, date range, status, credit hours | Check for existing enrollment before creating new — prevents duplicates |
| **Enrollment details** | Resident Credits, Online Credits, Tuition & Fees | Post-submission verification |

---

## 5. New Enrollment Certification Fields

### 5.1 Enrollment Information

| EM Field | Req? | Format | PeopleSoft Source | Automation Notes |
|----------|------|--------|-------------------|-----------------|
| **Academic institution** | Yes | Dropdown | PS INSTITUTION + WEAMS crosswalk | Map SDSU to Facility Code 11910105 |
| **Benefit type** | Auto | Read-only | PS M&V Module: VA_BENEFIT_TYPE | Auto-populated. Verify Ch.33 vs Ch.35 vs Ch.31 |
| **Objective type** | Auto | Read-only | PS ACAD_PROG: degree type | Auto-populated |
| **Program name** | Auto | Read-only | PS ACAD_PLAN + WEAMS crosswalk | Must match approved WEAMS program |
| **Begin date** | Yes | MM/DD/YYYY | PS term begin date | Ch.33: max 180 days advance. Non-Ch.33: max 120 days |
| **End date** | Yes | MM/DD/YYYY | PS term end date (last day of finals) | Use pre-set enrollment dates |

### 5.2 Credits and Tuition

> ⚠️ **CRITICAL:** These fields represent the output of Decision Tree Steps 6 and 7. Each course's credits must be classified and summed into the correct bucket.

| EM Field | Req? | Format | PeopleSoft Source | Automation Notes |
|----------|------|--------|-------------------|-----------------|
| **Resident credits** | No* | Number | Sum of RESIDENTIAL credits from Decision Tree Step 6 | Face-to-face + hybrid + practicum. *At least one credit field required |
| **Online credits** | No* | Number | Sum of DISTANCE credits from Decision Tree Step 6 | Fully online courses only |
| **Clock hours** | No* | Number | N/A | **NEVER USED AT SDSU** — IHL programs = credit hours only. Always 0. |
| **Remedial/Deficiency credits** | No* | Number | Decision Tree Step 5 output | Residential remedial only. Online/hybrid remedial = never certifiable |
| **Tuition & Fees amount** | Yes | Currency | PS Student Financials (post-census) | Ch.33: NET tuition after aid. Non-Ch.33: TOTAL gross tuition |

> ✅ **F4-3 VALIDATED (April 16, 2026):** For Ch33 net tuition — PeopleSoft calculates net tuition after financial aid awards AFTER CENSUS. Pull tuition from PeopleSoft Student Financials after census date has passed. If census has not yet run, flag as unverified and hold certification or save as draft for SCO review.
>
> ✅ **F4-5 VALIDATED (April 16, 2026):** SDSU is IHL. All programs use CREDIT HOURS. Clock Hours field = 0 always. Software can hardcode Clock Hours = 0 and skip that field entirely for all SDSU certifications.

### 5.3 Remarks

| EM Field | Format | Automation Notes |
|----------|--------|-----------------|
| **VBA Remarks** | Dropdown (standard options) | Auto-select when conditions detected. **⏳ F4-2 SCREENSHOT NEEDED — see Section 9** |
| **Custom Remark** | Free text | ⚠️ WARNING: Delays processing and payment. NEVER auto-submit. Always save as draft for SCO review. |

### 5.4 Notes

Notes are stored on the student's profile and **NOT submitted** with the enrollment. Visible to other SCOs at the same school. Use for audit trail entries (e.g., "Certified via automation - verified against DARS 04/16/2026"). **No PII allowed (FOIA applies).**

### 5.5 Submission

Certification statement: *"By submitting this record, I certify that the previous statements are true and correct to the best of my knowledge and belief."*

| Button | Action | Software Behavior |
|--------|--------|------------------|
| **Ok, Add enrollment** | Submits to VA | Primary action after all validation passes |
| **Save as draft** | Saves without submitting | Use for SCO review cases: custom remarks, unverified tuition, edge cases |
| **Discard edits** | Cancels all data | Use when validation fails |

---

## 6. Amendment Workflow

### 6.1 Amendment-Specific Checkboxes

| Checkbox | When to Use | Software Trigger |
|----------|-------------|-----------------|
| **Graduation/End of Term** | Student completed term or graduated | DARS shows degree conferred OR term end date reached |
| **Termination** | Student withdrew, dismissed, no longer eligible | Student drops ALL courses. When checked, all credit/tuition values become read-only. |

> ⚠️ **CRITICAL:** When Termination is checked, all pre-existing credit and tuition values become **read-only**. Software must capture termination effective date and reason only — do not attempt to modify credit values.

### 6.2 Amendment Information

| EM Field | Req? | Format | PeopleSoft Source | Automation Notes |
|----------|------|--------|-------------------|-----------------|
| **Amendment Reason** | Yes | Dropdown | Derived from PS enrollment change event type | **⏳ F4-4 SCREENSHOT NEEDED — see Section 9** |
| **Amendment effective date** | Yes | MM/DD/YYYY | PS STDNT_ENRL: effective date of change | Date the change occurred, NOT date amendment is submitted |

### 6.3 Amendment Submission

| Button | Software Behavior |
|--------|------------------|
| **Submit amendment** | Primary action for R2 enrollment changes. Shows "AMENDMENT - SUBMITTED" after. |
| **Save as draft** | Use for terminations, complex changes, near half-time threshold, pending F4-4 screenshot |
| **Discard edits** | Use if change was reversed (student re-adds dropped course before census) |

> ⚠️ **WRONG FACILITY RULE:** Cannot amend the facility on an existing certification. Must terminate and recertify under correct facility. Software must detect facility mismatches BEFORE submission.

---

## 7. End-to-End Data Flow

### 7.1 PeopleSoft → Decision Tree

| PeopleSoft Data | Decision Tree Step | Output |
|----------------|-------------------|--------|
| ACAD_PLAN + WEAMS program list | Step 1: WEAMS Program Match | PASS/FAIL per program |
| DARS audit (course-by-course) | Step 2: DARS Applicability | APPLICABLE / NOT APPLICABLE / PENDING |
| PS enrollment history (prior terms) | Step 3: Audit Check | Flag audit courses |
| PS enrollment history (same course) | Step 4: Repeat Check | Flag repeats |
| PS course attributes (remedial flag) | Step 5: Remedial Check | Remedial + modality. Online remedial = EXCLUDED |
| PS class schedule (meeting patterns, location) | Step 6: Modality Classification | RESIDENTIAL / DISTANCE per course |
| Sum of R + D credits from Step 6 | Step 7: Rate of Pursuit | Full-time / 3/4 / Half-time / Less than half |

### 7.2 Decision Tree → EM Fields

| Decision Tree Output | EM Field | Example (Nick Foster) |
|---------------------|----------|-----------------------|
| Sum of RESIDENTIAL credits | Resident credits | 6 (MIS 401 + MIS 460) |
| Sum of DISTANCE credits | Online credits | 6 (MIS 585 + MUSIC 151) |
| Remedial + RESIDENTIAL credits | Remedial/Deficiency credits | 0 (no remedial) |
| R + D total | (Determines benefit level) | 12 total = Full-time |
| Excluded courses | NOT entered in EM | ENS 331 — not in DARS |
| PS Student Financials (post-census, net for Ch.33) | Tuition & Fees | Net tuition after waivers |

---

## 8. EM Business Rules for Software

### 8.1 Submission Timing
- **Ch.33:** Cannot submit more than 180 days before term start
- **Non-Ch.33:** Cannot submit more than 120 days before term start
- Software must calculate submission windows and queue bulk certifications accordingly

### 8.2 Tuition Reporting
- **Ch.33:** NET tuition (after scholarships, waivers, aid) — pulled from PeopleSoft AFTER CENSUS
- **Non-Ch.33:** TOTAL gross tuition charged
- **Clock hours:** Always 0 for SDSU (IHL, credit hours only)

### 8.3 Pre-set Enrollment Rules
- One per term: semester start through last day of finals
- Cannot be edited once active
- Validate all dates before creating

### 8.4 Remarks Rules
- Standard VBA Remarks: no processing delay — use whenever standard option matches
- Custom Remarks: delay processing and payment — NEVER auto-submit, always draft for SCO review

### 8.5 Notes vs. Remarks
- **Notes:** Internal only, not submitted to VA, no PII, good for audit trail
- **Remarks:** Submitted to VA, affect processing, use standard options when possible

---

## 9. Open Items — Screenshots Needed from Paulina

| # | What's Needed | Why It Matters |
|---|--------------|----------------|
| **F4-2** | Screenshot of the VBA Remarks dropdown in EM | Complete list needed to build auto-remark logic. Software needs to know all standard options to map conditions automatically. Until received: default to no remark unless "Dual Degree Program" detected. |
| **F4-4** | Screenshot of the Amendment Reason dropdown in EM | Complete list needed to map PeopleSoft enrollment change events to correct EM amendment reason. Until received: save amendments as draft, require SCO manual selection of reason. |

---

## 10. Implementation Priority for Chilly

**Phase 1 — Core Certification (MVP):**
- Enrollment Information fields (academic institution, dates, program)
- Credits and Tuition fields (resident credits, online credits, tuition)
- Clock hours = 0 always for SDSU
- Pre-set enrollment creation from PS academic calendar
- Student lookup: EMPLID primary, name+DOB fallback
- Tuition: pull post-census, flag as unverified if census not yet run
- Submit enrollment ("Ok, Add enrollment" action)

**Phase 2 — Amendment Engine:**
- Detect enrollment changes from PeopleSoft (R2)
- Map changes to Amendment Reason dropdown (pending F4-4 screenshot — save as draft until received)
- Recalculate credits and tuition for amended enrollment
- Handle Termination checkbox (read-only field logic)

**Phase 3 — Edge Cases and Intelligence:**
- Graduation/End of Term detection and amendment
- Auto-remarks (pending F4-2 screenshot)
- Draft mode for SCO review (custom remarks, edge cases)
- Audit trail via Notes field

---

*This document should be read alongside the Course Applicability Decision Tree VALIDATED v0.2, which defines the rule logic that feeds the EM fields mapped above.*
