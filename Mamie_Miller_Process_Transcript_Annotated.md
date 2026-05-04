# Mamie Miller ("Mimi") Process Capture — Annotated Transcript
**Source:** Team meeting with Mamie Miller, Jen Christensen, Paulina, and staff
**Date:** Approximately November 2024 (pre-Spring 2025 registration)
**Extracted:** April 7, 2026

---

## Context

This transcript captures a working meeting where Mamie Miller (Bursar's office, handles third-party contract coding for VA students), Jen Christensen (PeopleSoft M&V Module builder), and Paulina discuss the enrollment verification and coding workflow. Key business logic for the R2 (enrollment change monitoring) module is documented here.

---

## Key Process Findings

### 1. Mamie's Query and What She Pulls

Mamie runs a query that pulls student data after the MVP (Military & Veterans Program) team updates student records. The query pulls from whatever the MVP team updates on the Veterans Benefit Summary (VBS) page.

> "The query that I ran, and this really only affects chapter 33 students. I'm not sure if you have access to that query, Jen, and if you can look at it and see where that query is actually pulling information from, because once the MVP team updates the student on their side... when I run my query, that's where the information is pulled from."

**Software implication:** The query reads from SSR_VB_DATA (VBS page). The software must ensure the VBS data is accurate before Mamie's equivalent process runs.

### 2. Service Indicators vs. Attributes (Batch Processing)

Paulina proposed using PeopleSoft **service indicators** instead of attributes for tracking verification status, because service indicators can be added and removed in batch — attributes cannot.

> "The reason why I was saying a service indicator is because I can add and remove those in batch. I can't do that with the attributes."

**Workflow concept:** When a student submits a certification request via self-service, a service indicator flags them as "not verified." The MVP team works through the list. Once verified, the service indicator is released.

**Software implication:** The automation could use service indicators as a status flag mechanism. Batch operations are critical for processing 800+ students.

### 3. Students MUST Request Certification (VA Law)

> "Does a student need to submit a request in order to receive benefits? Or will they receive benefits regardless?"
> "VA law, they have to request to be certified."

**Software implication:** The certification workflow begins with a student self-service request. The software should only process students who have actively submitted a certification request for the current term. This is a legal requirement, not optional.

### 4. The Rollover Problem

Students from a prior term can be "rolled over" — their attributes carry forward. But this creates problems:

> "If we do a rollover and that attribute gets updated and I run my query, I don't know that they haven't requested their certification and then I update their account."

Risks: Students may have exhausted entitlement, switched benefit chapters (33 to 35), or not actually want benefits this term. If Mamie codes them for third-party contracts based on rolled-over data, the Bursar picks up the tab incorrectly.

> "Fall 22 and Spring 23 there was a similar rollover done by SD Carry. And so then the Bursar's office picked up third party contracts on all those folks and a lot of them had exhausted entitlement or weren't using 33 — they were using 35."

**Software implication:** The software must distinguish between "rolled over" students and students who actively requested certification for the current term. Only process students with active requests.

### 5. Mamie's Exact Query Requirements

Mamie is explicit about what she needs from the query:

> "I am one person that I deal with, not just military accounts, but many other accounts I handle — I don't even know how many, it's got to be over 4,000 student accounts. I don't have the time to sit there and filter out data. When we create the query for me, I need to be able to just run the query and know that these students are the correct students I need to code. I really don't have that time."

The query she needs must show:
- **Chapter 33 students only** (third-party contracts only apply to Ch.33)
- **Who submitted a certification request** (active request for the current term)
- **Who have been reviewed by the MVP team** (verified eligible)

> "You're really going to need a query to show the chapter 33 students that have submitted a certification request and who have been reviewed by the MVP team."

**Software implication:** The automation replaces this query entirely. The software identifies Ch.33 students with active requests, runs the Decision Tree, and outputs a clean list of students ready for coding — no filtering needed.

### 6. Status Values That Matter

The VBS page has status values. Key ones for the workflow:

- **In Review** — Default status. Does NOT mean someone has looked at them. Cannot be trusted as "verified."
- **Pending** — Someone has started looking at the student. More reliable than In Review.
- **Reported** — Certification has been reported to the VA.

> "'In Review' is like the default. So that doesn't necessarily mean that you've looked at them... the students that are in review could have been looked at or could have not been looked at."

Mamie wants to see only **Reported** and **Pending** students — not In Review.

**Software implication:** The automation should update VBS status as it processes. When Decision Tree completes, move from "In Review" to "Pending." When submitted to EM, move to "Reported."

### 7. Mamie's Verification Notes

Mamie wants to write verification notes on VBS:

> "Can I write 'verified' and then have that be part of her query for pending and reported? On VBS... I can say verified on this day and then let you know the entitlement days. I want to protect the Bursar's as much as possible because that whole issue we had — it's going to be on us if it happens again."

**Software implication:** The automation should write a note on VBS (via SSR_VB_DATA comments or notes field) with: verification date, entitlement days remaining, and who/what verified it. This creates the audit trail Mamie needs.

### 8. Financial Aid Interaction (Critical Timing)

Mamie must code students BEFORE financial aid runs in early January:

> "As long as I can code these students before we run financial aid at the beginning of January... the ones that are supposed to be coded are coded and the ones that are not supposed to be coded are not coded. So their financial aid pays their tuition and fees and they don't get it refunded to them."

If a student is incorrectly NOT coded: their financial aid pays tuition, then when VA benefits come through, the financial aid gets refunded to the student in pocket. They spend it, then can't pay their bill.

If coded correctly: VA third-party contract covers tuition, financial aid stays for other expenses.

**Software implication:** The bulk certification (R1) must complete BEFORE the financial aid disbursement deadline. For Spring terms, this means all Ch.33 students must be coded by early January. The software must have a hard deadline awareness.

### 9. The Certification Request Self-Service Page

Students access a self-service page in PeopleSoft to request certification. Access requires:
- A specific security role (dynamically assigned based on criteria)
- Being term-activated (eligible to enroll for the term)

The checklist item prompts students to go to this page and submit their request. The request is what triggers the certification workflow.

**Software implication:** The software monitors for new certification requests via the self-service submission data. This is the trigger event for the entire pipeline.

### 10. IBC (Imperial Valley Campus) Exclusion

> "We don't certify any IBC students — only main campus and Global Campus. They have their own SCOs."

**Software implication:** Filter queries by campus. Exclude IBC (Imperial Valley Campus). Include Main Campus and Global Campus only.

### 11. Tuition and Benefits Calculation Example

The team discusses a real student case showing how benefits calculations work:
- Part-time certification = no housing allowance, but partial tuition coverage
- Full-time certification = housing allowance ($4,000/month) plus tuition coverage
- Students with only 2 months and 23 days of entitlement need strategic certification across terms
- Ch.35 vs Ch.33 benefits are tracked separately

**Software implication:** The software should calculate optimal certification strategy when entitlement is running low and present options to SCO. This is an edge case for the HITL (Human-in-the-Loop) trigger.

---

## Summary of What the Software Replaces

| Manual Process | Automated Equivalent |
|---------------|---------------------|
| Mamie runs custom query for Ch.33 students | Software monitors STDNT_ENRL + SSR_VB_DATA continuously |
| MVP team manually verifies each student | Decision Tree auto-verifies; exceptions go to SCO queue |
| Mamie filters for "requested + verified" | Software only processes students with active certification requests |
| Mamie codes students one at a time | Bulk coding via automated third-party contract creation |
| Mamie writes "verified" notes manually | Software writes audit trail automatically |
| Mamie must finish before financial aid runs | Software completes bulk cert on Day 1, well before FA deadline |
| Manual status tracking (In Review → Pending → Reported) | Software updates VBS status automatically as pipeline progresses |
