# AllowED — Lessons Learned

## Session 2 (May 3, 2026)

### iCloud + git = data loss risk
iCloud Drive offloads files to the cloud silently. `cp -R` skips offloaded subfolders without error. Always verify copied files exist. Keep git repos on local disk, not in iCloud-synced folders.

### Python date objects break Supabase inserts
`date(2026, 8, 24)` is not JSON serializable. Always use ISO strings (`"2026-08-24"`) when inserting dates via supabase-py.

### Check column precision before inserting
NUMERIC(3,2) can only hold -9.99 to 9.99. A 95.0 confidence score overflows. Always verify column precision matches expected data range.

### Terminal vs SQL Editor
Users will paste SQL into Terminal if you don't clearly label where to run commands. Always prefix instructions with "In Terminal:" or "In Supabase SQL Editor:".

### Verify file copy completeness
After copying from iCloud, glob for expected files (*.py, *.sql, etc.) and diff against source. Don't assume cp succeeded for all subdirectories.

## Session 3 (May 4, 2026)

### Graduate training time thresholds are NOT proportional to undergrad
Don't just scale undergraduate brackets down. The VA has specific thresholds per academic level. Always verify against the SCO Handbook and Paulina's domain knowledge before coding.

**Correct thresholds (credit hours, standard term):**

Undergraduate: 12+ = full-time, 9-11 = 3/4, 6-8 = 1/2, 4-5 = <1/2, 1-3 = 1/4 or less

Master's: 9+ = full-time, 6-8 = 3/4, 4-5 = 1/2, <4 = <1/2

Doctoral: 6+ = full-time (also 799A/897/899 = full-time regardless of units)

**The mistake:** Code had Master's as 7+ = 3/4, 5+ = 1/2 (wrong). Correct is 6+ = 3/4, 4+ = 1/2. A Master's student with 6 units is 3/4 time, not half-time.

### Always check the project markdown files before guessing
The project instructions (`Paulina_Claude_Project_Instructions.md`) contain verified Q&A from Paulina with authoritative answers on VA rules. Check there first before assuming or asking the user to re-explain something already documented.
