# AllowED Session 3 — Wire Frontend to Live Supabase

## Context
AllowED is a VA certification automation platform for School Certifying Officials. The full codebase is at `~/Desktop/AllowED` (also on GitHub at chilly611/AllowED). Supabase is live with schema deployed, SDSU seeded with 739 students/enrollments, and 3 test accounts ready.

## What's already done
- **Supabase** (cwxkpsnjsxaupncqyojq.supabase.co): 13 tables, RLS, 25 institutions, 6,543 WEAMS programs, 739 SDSU enrollments, 20 HITL flags
- **Test accounts**: sco@sdsu.test (SCO), sco@calpoly.test (SCO), admin@allowed.test (superadmin) — all password AllowED2026!
- **Credentials**: ~/Desktop/AllowED/.env has SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY
- **Frontend UIs**: allowed_workstation.html (SCO dashboard), allowed_student.html (student portal), allowed_website.html (marketing site) — all vanilla HTML/CSS/JS, currently using mock data
- **Backend**: api/ folder has FastAPI with 17 routes (server.py entry point)

## Three parallel workstreams — run as subagents

### Agent 1: Wire SCO Workstation to Supabase
Read `~/Desktop/AllowED/allowed_workstation.html` and `~/Desktop/AllowED/.env`. Rewrite the workstation to connect to live Supabase:
1. Add Supabase JS CDN (`https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2`)
2. Login page: Supabase Auth signInWithPassword, store session
3. Dashboard: query enrollments table grouped by status for the logged-in user's institution_id
4. Student roster: join students + enrollments for current term, show name/chapter/status/units
5. Student drill-down: click a student → show their course_schedules with decision tree results (certifiable, modality, exclusion_reason)
6. HITL queue: query hitl_queue for institution, show flag_type/reason/priority, approve/dismiss buttons that update status
7. Keep all existing CSS/styling. Vanilla JS only, no frameworks.
8. The canonical test case is Daniel Bahena (student_id_internal = 'JR-001') at SDSU — make sure his drill-down shows ENS 331 excluded, R:6, D:6, T:12.

### Agent 2: Fix Decision Tree for All Schools + Seed Remaining
Read `~/Desktop/AllowED/decision_tree.py` and `~/Desktop/AllowED/weams_programs.py`. The `match_weams_program` function crashes with `'NoneType' object has no attribute 'split'` when processing non-SDSU students. The synthetic cohort generator assigns random WEAMS programs from each school's program list, but some program names don't match the expected format.
1. Find and fix the NoneType bug in weams_programs.py (likely a program name that doesn't split cleanly)
2. Add defensive None checks so the decision tree never crashes on bad input
3. Test with Cal Poly Humboldt programs to verify the fix
4. Delete existing Cal Poly students from Supabase (they have no enrollments): `DELETE FROM students WHERE institution_id = '11906105';`
5. Re-run: `python3 scripts/generate_synthetic_cohort.py --facility-code 11906105 --term "Fall 2026"`
6. If that works, run `--all` for all 25 schools
7. Fix `scripts/create_test_accounts.py` — change Cal Poly facility code from 11400104 to 11906105

### Agent 3: Benefits Intake PDF Upload
Read `~/Desktop/AllowED/benefits_intake.py` and `~/Desktop/AllowED/va_api_client.py`. Wire the VA Benefits Intake API (sandbox) to upload a PDF certification for at least one student (Daniel Bahena preferred).
1. Check if the VA sandbox API keys are in .env
2. Create a simple test script that generates a PDF certification doc for Daniel Bahena and submits it via the Benefits Intake API sandbox endpoint
3. If sandbox keys aren't available, create the PDF generation + upload flow with a mock mode that shows what would be submitted

## Important constraints
- HTML files must be vanilla JS (no React/Babel/Tailwind CDNs that need compilation). Supabase JS CDN is OK.
- Enrollment and T&F certification are SEPARATE tracks. Don't conflate them.
- Brand colors: dark #0F172A, blue #1E40AF, orange #F97316, green #10B981
- All changes should be committed and pushed to GitHub when done.

## After all agents finish
Run end-to-end demo: login as sco@sdsu.test → see dashboard with real stats → find Daniel Bahena → drill into course schedule → approve a HITL item → log in as admin@allowed.test → switch institutions.
