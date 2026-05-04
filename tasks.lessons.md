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
