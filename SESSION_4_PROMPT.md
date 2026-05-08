# AllowED Session 4 — Polish for TechCrunch + End-to-End Demo

## Context
AllowED is a VA certification automation platform. The codebase is at `~/Desktop/AllowED` and on GitHub at chilly611/AllowED. The platform is functional end-to-end: 25 schools seeded (10,929 students), SCO Workstation connected to live Supabase, Benefits Intake PDF generation working in mock mode.

## What's done
- Supabase live: 25 institutions, 10,929 students, 10,928 enrollments, 270 HITL flags
- SCO Workstation: login, dashboard, student roster, drill-down, HITL queue, superadmin institution switcher — all wired to live data
- Benefits Intake: PDF generation for Daniel Bahena (mock mode, needs VA sandbox keys for live)
- Test accounts: sco@sdsu.test, sco@calpoly.test, admin@allowed.test (all AllowED2026!)
- Credentials in ~/Desktop/AllowED/.env

## Session 4 priorities

### 1. QA the workstation thoroughly
- Log in as sco@sdsu.test — test every view, click every button
- Log in as admin@allowed.test — test institution switcher across multiple schools
- Check Daniel Bahena drill-down: ENS 331 excluded, R:6, D:6, T:12
- Verify grad students show correct training time (6 units = 3/4 for Master's)
- Check HITL approve/dismiss actually updates the database
- Note any UI bugs, broken queries, missing data, or confusing UX

### 2. Add amendment flow to workstation
The workstation needs an amendment workflow for when a student's enrollment changes mid-term (drops a class, withdraws, etc.). The amendments table exists in Supabase with 8 valid amendment reasons. Build:
- Amendment creation form (select student, select reason from the 8 valid reasons, enter effective date)
- Amendment review queue (pending amendments that need SCO approval)
- Approve/reject actions that update the amendment status
- When approved, recalculate the student's enrollment (units, training time)

### 3. Add batch certification workflow
SCOs don't certify one student at a time — they certify in batches. Build:
- Batch selection: checkboxes on the student roster to select multiple students
- "Certify Selected" button that moves all selected enrollments from pending → submitted
- Batch summary showing what's being certified before confirmation
- Update enrollment status and submitted_at timestamp

### 4. Visual polish for demo
- Make sure the workstation looks professional enough for TechCrunch
- Clean up any rough edges in the UI
- Add loading states so data fetches don't show blank screens
- Brand consistency: dark #0F172A, blue #1E40AF, orange #F97316, green #10B981

### 5. Wire student portal (if time)
Connect allowed_student.html to Supabase so students can see their own certification status. Lower priority than the SCO workstation polish.

## Constraints
- Vanilla HTML/CSS/JS only (Supabase JS CDN is the only external dependency)
- Enrollment and T&F certification are SEPARATE tracks — don't conflate
- Graduate training time: Master's 9+ full, 6-8 = 3/4, 4-5 = 1/2. Doctoral 6+ full.
- Check Paulina_Claude_Project_Instructions.md before coding any VA rules
- All changes committed and pushed to GitHub when done
