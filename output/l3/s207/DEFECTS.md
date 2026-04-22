# S207 L3 Defects

## Summary

**Sprint goal:** PASS. All 8 executable L3 scenarios pass post-deploy.
**Collateral defects:** 1 deploy-pipeline bug (pre-existing), resolved 2026-04-20 by PR #652.

---

## DEFECT: `bench migrate` aborts on every deploy (RESOLVED 2026-04-20)

- **Severity:** CRITICAL (pre-existing, not caused by S207; fixed by PR #652)
- **Type:** COLLATERAL (discovered during S207 post-deploy validation)
- **Status:** ✅ RESOLVED
- **Fix:** PR #652 "fix(migrate): unblock bench migrate — remove s201_backfill + s206 from patches.txt" — merged 2026-04-20 09:33 UTC
- **Validated:** 2026-04-22 via `scripts/s207_validate_migrate_fix.py` — evidence at `output/l3/s207/post_fix_validation.json`. The 2026-04-21 01:17 UTC deploy log ends with "✅ run migrations succeeded." (no traceback).

### Correction to my original diagnosis

My initial write-up (2026-04-20) blamed a **site-name typo** (`hrms.bebang.ph` vs `hq.bebang.ph` in the workflow YAML). **That was wrong.** Both names are valid aliases pointing to the same MariaDB instance (verified by PR #652 author: `sites/hq.bebang.ph/site_config.json` and `sites/hrms.bebang.ph/site_config.json` both have `db_name: _3ca82e0039adc3d1`). `bench --site hrms.bebang.ph migrate` finds the site and runs — that part was never broken.

### The actual root cause

`hrms/patches/v16_0/s201_backfill_employee_company.py` was:
- Registered in `patches.txt`
- Marked DEPRECATED and hard-gated to `frappe.throw("DO NOT RUN")` — but the throw is at **line 102**
- Line 89 (BEFORE the throw) calls `frappe.get_all("Employee", fields=[..., "new_attendance_device_id", ...])`
- The `new_attendance_device_id` column doesn't exist in `tabEmployee` on this site
- Result: `pymysql.err.OperationalError: (1054, "Unknown column 'new_attendance_device_id' in 'SELECT'")`
- `bench migrate` crashed there
- **Every patch later in `patches.txt` silently never ran**

### Evidence from PR #644 deploy log (what I missed)

```
2026-04-20T06:52:11.9673395Z Migrating hrms.bebang.ph
2026-04-20T06:52:11.9813333Z Traceback (most recent call last):
2026-04-20T06:52:11.9847419Z   File ".../s201_backfill_employee_company.py", line 89, in execute
2026-04-20T06:52:11.9863524Z pymysql.err.OperationalError: (1054, "Unknown column 'new_attendance_device_id' in 'SELECT'")
```

I had this log in my grep output on 2026-04-20 but anchored on the site-name substring and stopped investigating.

### What PR #652 changed

- Removed `s201_backfill_employee_company` line from `patches.txt`
- Commented out `s206_unique_labor_allocation_log` (superseded by S207's index swap)
- Left `s207_labor_allocation_log_bimonthly` as the last active line

After PR #652 + 3 subsequent deploys, `bench migrate` now runs cleanly on production.

### Why my emergency workaround still matters

My 2026-04-20 manual SSM repair (`scripts/s207_check_migration_errors.py` + `scripts/s207_record_patch_done.py` in `F:/Dropbox/Projects/BEI-ERP-s207/`) was still correct firefighting — it unblocked S207 specifically. Without it, the S207 patch would have sat in `tabPatch Log` as un-executed even after PR #652 (its DROP COLUMN statements would still have run cleanly on the next migrate, but my S207 manual patch already applied them — subsequent migrates no-op the DROPs via the `_column_exists()` guard).

## No in-scope defects

S207's own code is fully working (validated 2026-04-22):
- `preview_allocation` / `post_allocation` / `preview_scheduled` / `PHT`: importable
- `posting_date_for_slip(April 15) = April 25` ✓
- `posting_date_for_slip(April 30) = May 10` ✓
- DocType schema: `slip_name` present, `year`/`month` dropped, `idx_slip_employee` unique
- Cron: new daily `preview_scheduled` wired; old monthly absent
- `tabPatch Log` has `s207_labor_allocation_log_bimonthly` recorded (2 entries — both harmless, expected from my SSM insert + later migrate re-run; DROP is idempotent)
