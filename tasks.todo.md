# AllowED — Session 3 Todo

## Completed (May 3)
- [x] Recover project files from iCloud → ~/Desktop/AllowED
- [x] Push to GitHub (chilly611/AllowED)
- [x] Deploy schema to Supabase (13 tables, RLS, triggers)
- [x] Seed institutions (25), WEAMS programs (6,543), terms (25)
- [x] Generate SDSU synthetic cohort (739 students, 739 enrollments, 20 HITL flags)
- [x] Create test SCO accounts (sco@sdsu.test, sco@calpoly.test, admin@allowed.test)

## Next Session — Wire Frontend to Supabase
- [ ] Add Supabase JS client to allowed_workstation.html (CDN OK for real browsers)
- [ ] Build login page with Supabase Auth (email/password)
- [ ] Dashboard: pull enrollment stats from Supabase (counts by status, chapter breakdown)
- [ ] Student list: query enrollments + students tables, show in roster view
- [ ] Student drill-down: show James Roster (Daniel Bahena) course schedule, decision tree output
- [ ] HITL queue: pull from hitl_queue table, approve/dismiss actions
- [ ] Institution switcher (superadmin only): switch institution_id context

## Next Session — Bug Fixes
- [ ] Fix decision tree WEAMS matching for non-SDSU schools (NoneType split error)
- [ ] Run generate_synthetic_cohort.py --all for remaining 24 schools
- [ ] Fix create_test_accounts.py Cal Poly facility code (11400104 → 11906105)

## Next Session — Benefits Intake
- [ ] Wire Benefits Intake API PDF upload for at least one student
- [ ] End-to-end demo: login → dashboard → drill-down → HITL → switch institution → amendment

## Lessons
- iCloud + git = bad. Keep repo local, use GitHub as source of truth.
- Python date objects aren't JSON serializable for Supabase — use ISO strings.
- NUMERIC(3,2) only holds up to 9.99 — weams_confidence needed NUMERIC(5,2).
- iCloud `cp -R` skips offloaded subfolders — copy them individually.
