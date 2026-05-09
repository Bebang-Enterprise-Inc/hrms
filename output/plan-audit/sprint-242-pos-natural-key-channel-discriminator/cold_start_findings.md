# Cold-Start Audit Findings
## Plan: S242 — pos_orders Natural-Key Channel Discriminator
## Date: 2026-05-08
## Plan path: F:/Dropbox/Projects/BEI-ERP/docs/plans/2026-05-08-sprint-242-pos-natural-key-channel-discriminator.md

---

## Verdict: PASS (with 2 minor warnings)

A fresh agent with zero context can execute this plan end-to-end from the document alone. Every external dependency, file path, function name, SQL block, and decision rationale is present and verifiable. The two warnings below are quality-of-life improvements, not cold-start blockers.

---

## CRITICAL Findings

**None.** Every cold-start dependency is either provided in the plan or explicitly documented as a Doppler/Supabase Mgmt API requirement.

---

## WARNING Findings

### W1: Line-range claim "lines 255-540" includes lines outside the function set the plan calls out

**Where:** `## Design Rationale → Source references` section (line 123 of plan):
> `scripts/sync_pos_to_supabase.py:255-540` (reconcile_existing_ids, _dedupe_incoming_by_natural_key, _resolve_id_collisions)

**Verified actual line numbers in `F:/Dropbox/Projects/BEI-ERP/scripts/sync_pos_to_supabase.py` (1322 total lines):**

| Function | Actual line | In claimed range 255-540? |
|---|---:|---|
| `_resolve_id_collisions` | 291 | YES |
| `_canonical_score` | 372 | YES (used by dedup) |
| `_dedupe_incoming_by_natural_key` | 389 | YES |
| `reconcile_existing_ids` | 490 | YES (body extends to ~614, partly outside the range) |
| `_resolve_channel` | 805 | NO — outside the claimed 255-540 range |

The claim is mostly accurate: 3 of 3 named functions ARE inside 255-540, but `reconcile_existing_ids`'s body runs to line 614 (returns at 614). Also, `_resolve_channel` (referenced separately on line 125 of the plan: `scripts/sync_pos_to_supabase.py:_resolve_channel`) is at line 805 — the plan correctly does NOT include a line range for that one, so this is internally consistent.

**Cold-start impact:** Low. Phase 0 task 0.1 instructs the agent to "Read `scripts/sync_pos_to_supabase.py` lines 255-540 to understand the existing reconciliation, dedup, and collision-resolution logic." If the agent reads exactly 255-540, they will see all three core functions but miss the back half of `reconcile_existing_ids` (560-614) which contains the critical `existing_by_bill: dict[str, Any]` and `bill_number: f"in.({...})"` lookup that Phase 2.2 mutates. Phase 2.2's MUST_CONTAIN regex (`existing_by_bill_channel` and `"channel": f"eq.{`) gives the agent enough to re-find that block, but it would be cleaner to either (a) widen the read window to 255-620, or (b) explicitly point at line 560 ("Step 3: look up existing live rows by natural key") in the §Phase 2 "Functions to update" table.

**Suggested fix:** Change Phase 0 task 0.1 to read `lines 255-620` (or just `lines 255-end of reconcile_existing_ids at line 614`).

---

### W2: Phase 4.1 reuse claim is not 100% safe under the new schema

**Where:** Phase 4.1 (line 410 of plan):
> Run `scripts/s232_mosaic_vs_supabase_audit.py` unchanged. The 12-store-day sample should still report 12/12 MATCH. (Migration only touches `is_duplicate` flag; raw bill counts and gross sums per channel are unchanged because canonical rows are unchanged — only previously-tombstoned siblings come back.)

**Verification of `output/s232/audit_data.json`:**
- Confirmed exists, 14,576 bytes, contains 12 store-day samples.
- SM Manila 2026-05-03 sample shows `distinct_paid_bills: 336` for both Mosaic and Supabase — matches plan's Phase 2.8 expected count of 336.
- The S232 audit's MATCH verdict (line 295 of audit script) compares `bill_ok and gross_ok and net_ok`.

**Risk:** Before the migration, S232 audited "live rows only" (filtered through `v_pos_orders_live`). After the migration, 74 previously-tombstoned rows become live. If any of those 74 happen to fall on the 12 audit-sample dates, the Supabase totals will JUMP UP — and the audit might report MISMATCH where it previously reported MATCH, even though both sides are now MORE accurate.

The plan partially anticipates this in §"Failure Response Mode C" (Mosaic API regression → escalate, do NOT roll back), but the framing assumes a Mosaic-side regression. A genuine "Supabase totals rose because we restored hidden rows" would also drop Phase 4.1 below 12/12 MATCH and trigger Phase 4.1's stop_only_for clause incorrectly.

**Mitigation already present in plan:**
- Phase 4.1 is run AFTER Phase 1 migration, so the comparison is against the post-migration Supabase state.
- Mosaic API is the source of truth — if Supabase now sums HIGHER and matches Mosaic better, that's a MATCH (the audit compares Supabase to Mosaic, not Supabase before vs after).

**Conclusion:** This is a defensive note rather than a true blocker. The audit verdict should improve, not regress, post-migration. But a fresh agent may need to read the audit script to confirm the comparator direction. **Suggested fix:** add one line to Phase 4.1: "If a store-day previously reported MATCH and now reports MISMATCH with Supabase HIGHER than Mosaic, that is a NEW MATCH path bug, not a regression — check whether the restored row is in fact present on Mosaic."

---

## Detailed Cold-Start Checklist Verification

### [PASS] Every external query has exact table/column names

- The `Population-level impact` query (lines 73-84) is the locked SQL. Names every column: `pos_orders.is_duplicate`, `bill_number`, `location_id`, `business_date`, `channel`, `payment_status`, `gross_sales`.
- Phase 1.1 migration SQL (lines 304-343) is fully locked — `BEGIN;`, `DROP INDEX IF EXISTS public.pos_orders_bill_number_natural_key`, full `CREATE UNIQUE INDEX` DDL, full restore CTE with `WITH canonical AS (...)`, full `UPDATE ... RETURNING` block, `COMMIT;`.
- Phase 1.5 spot-check SQL (line 354) has full SQL: `SELECT id, channel, is_duplicate, payment_status, gross_sales FROM pos_orders WHERE location_id=2177 AND business_date='2026-04-21' AND bill_number='39966';`.

### [PASS] Every API endpoint has URL + auth method

- Supabase Mgmt API: documented in plan §Phase 0.3 with exact verification command `doppler secrets get SUPABASE_MGMT_TOKEN --plain --project bei-erp --config dev`.
- Verified via Doppler: `SUPABASE_MGMT_TOKEN` exists in bei-erp/dev (truncated value `sbp_538c95ab61a1d7f6e3c...`).
- PostgREST URL pattern: documented via existing sync script reference (line 563: `f"{SUPABASE_URL}/rest/v1/pos_orders"`) — agent can copy that pattern.
- Auth headers come from existing `_supabase_headers()` helper (line 166-167 of sync script).

### [PASS] Every file path is complete and verified

| Plan reference | Actual location | Verified |
|---|---|---|
| `scripts/sync_pos_to_supabase.py` | `F:/Dropbox/Projects/BEI-ERP/scripts/sync_pos_to_supabase.py` | EXISTS, 53,411 bytes, 1322 lines |
| `output/s232/audit_data.json` | `F:/Dropbox/Projects/BEI-ERP/output/s232/audit_data.json` | EXISTS, 14,576 bytes |
| `output/s232/paseo_comparison_report.md` | `F:/Dropbox/Projects/BEI-ERP/output/s232/paseo_comparison_report.md` | EXISTS, 7,334 bytes — confirms Paseo 4/21 totals: POS 121,722, Supabase 121,494 |
| `output/s232/audit_report.md` | `F:/Dropbox/Projects/BEI-ERP/output/s232/audit_report.md` | EXISTS, 10,944 bytes |
| `scripts/s232_mosaic_vs_supabase_audit.py` | EXISTS, 17,740 bytes | Verified MATCH verdict logic at line 295 |
| `scripts/s232_resync_with_dedup_dance.py` | EXISTS, 8,858 bytes | OK |
| `scripts/s232_verify_after_resync.py` | EXISTS, 8,334 bytes | OK |
| `docs/plans/SPRINT_REGISTRY.md` | EXISTS, S242 row at line 336 | Confirms branch name `s242-pos-natural-key-channel-discriminator` |

Function name claims (line numbers in `scripts/sync_pos_to_supabase.py`):

| Function | Claimed | Actual |
|---|---|---|
| `reconcile_existing_ids` | in 255-540 | line 490 (in range) |
| `_dedupe_incoming_by_natural_key` | in 255-540 | line 389 (in range) |
| `_resolve_id_collisions` | in 255-540 | line 291 (in range) |
| `_resolve_channel` | (no line range claimed) | line 805 |
| `_canonical_score` | (no line range claimed) | line 372 |

Plus W1 above re: line range upper bound.

### [PASS] Every function the agent must NOT break is listed

§"Surface Inventory" (lines 156-167) explicitly enumerates:
- Touched: `_dedupe_incoming_by_natural_key`, `reconcile_existing_ids` (modified)
- Read-only: `_canonical_score`
- Untouched: `hrms/api/sales_dashboard.py`, `hrms/api/mcp.py`, `hrms/api/store.py`, `bei-tasks/app/dashboard/analytics/*`, `scripts/sync_web_to_supabase.py`, `data/POS_Extraction/MOSAIC_POS_API_KEYS.csv`.
- §"Anti-Rewind" `protected_surfaces` block (lines 181-186) re-asserts the same list.

### [PASS] No frontend route involvement

§"Surface Inventory" line 166: "`bei-tasks/app/dashboard/analytics/*` — No change. Frontend reads via Frappe API; numbers shift up because `v_pos_orders_live` returns more rows."
§"Execution Workflow" line 577: "E2E: not applicable (no UI change). Phase 4 audit replaces traditional E2E."
§"L3 Workflow Scenarios" line 437: "This sprint produces no operator-facing UI changes. L3-equivalent verification is dashboard-level, not click-level."
**Cold-start agents will not be tempted to touch the frontend.**

### [PASS] Branch state documented

§"Worktree Boot" (lines 268-283) gives exact commands:
- Branch: `s242-pos-natural-key-channel-discriminator` (matches frontmatter)
- Base: `origin/production`
- Worktree path: `F:/Dropbox/Projects/BEI-ERP-s242-pos-natural-key-channel-discriminator`
- Verified via `git branch -a`: NO existing s242 branch — fresh sprint.
- Recent commits show S232 sync hardening already merged to production: `ca7c88f08 fix(s232): dedupe Mosaic side in audit`, `e974c967e fix(s232): non-concurrent MV refresh`, `054d7aaa6 fix(s232): final dedup pass`, `dc7a36c15 fix(s232): resolve in-batch id collisions`, `0c4b4c8d1 fix(s232): dedupe in-batch natural-key`, `21c695e1a fix(s232): reconcile Mosaic ids` — confirms `depends_on: S232 sync script reconciliation patch must be live in production — confirmed`.

### [PASS] Design Rationale section answers WHY for each major decision

§"Design Rationale" (lines 94-126) covers:
- Why this exists (parallel-bill schema mismatch with Mosaic reality)
- Why extend the natural key (vs drop the partial unique index)
- Why `channel` (vs `terminal_id`, `paid_at`, append-discriminator)
- Why restore the 74 hidden rows (vs forward-only)
- Trade-off rejected: append-discriminator (BIR-relevant data integrity)
- Source references with verifiable file pointers

### [PASS] Trade-offs documented

Specifically called out and rejected with reasoning:
- `terminal_id` rejected — not in `pos_orders` (would require new column + sync wiring)
- `paid_at` rejected — unstable (Mosaic rewrites on void/refund)
- Append-discriminator (`39966-FoodPanda`) rejected — changes data semantically, propagates fake bill numbers downstream
- Drop the index entirely rejected — re-introduces same-channel over-counting that S232 dedup correctly suppresses

### [PASS] Known limitations explicit

- Supabase Mgmt API requires Doppler token: §Phase 0.3 + §Autonomous Execution Contract `stop_only_for: missing SUPABASE_MGMT_TOKEN credential`
- MV refresh non-concurrent blocks reads briefly: §Phase 3.1 `(non-concurrent — view lacks unique index per S232 finding)` — verified in `sync_pos_to_supabase.py:1093` and `1097` where `False` flag is used for these MVs.
- Migration drift tolerance: §Phase 0.5 — 5% tolerance band on locked count of 74; >5% drift triggers user-stop.

### [PASS] Source references in rationale claims point to verifiable files

All four references in §"Source references" (lines 122-125):
- `output/s232/paseo_comparison_report.md` — VERIFIED (real, contains bill 39966 data)
- `scripts/sync_pos_to_supabase.py:255-540` — VERIFIED (with W1 caveat about range upper bound)
- `v_pos_orders_live` filter `cancelled_at IS NULL AND COALESCE(is_duplicate, false) = false` — referenced as a known DB object; the plan does not include the view DDL but the filter expression is stated explicitly. Acceptable for cold-start because the migration does NOT modify the view.
- `scripts/sync_pos_to_supabase.py:_resolve_channel` — VERIFIED at line 805.

---

## Other Cold-Start Strengths Worth Noting

- **Phase 0.5 drift gate** — agent stops if Phase 0's `rows_to_restore` count differs from the locked 74 by >5%. Prevents acting on stale state.
- **Phase 1.6 anti-regression check** — same-channel tombstones MUST stay tombstoned. Tolerance band 295–320 is explicit.
- **Phase 1.4 idempotency check** — second run of migration MUST report 0 rows restored. Catches accidental re-restoration.
- **Phase 4.4 forensic pairing check** — every restored row MUST have a different-channel live sibling. Catches false-positive restorations.
- **§"Forbidden" block** (line 534) — explicitly prohibits "Marking a task done if its MUST_MODIFY file does not appear in `git diff --name-only`" and "Marking a task done if its MUST_CONTAIN string does not appear in the file via grep". Hard cold-start enforcement.
- **§"Test Data Seeding Contract"** — explicitly forbids test-row seeding; verification is against real production data only.
- **Migration SQL is locked** — agents cannot invent variations; the BEGIN/COMMIT/CTE block is the literal SQL to execute.

---

## Summary

- CRITICAL: 0
- WARNING: 2 (W1: line-range upper bound; W2: Phase 4.1 reuse semantics could mention "post-migration HIGHER MATCH is still MATCH")

**Recommendation: GO.** Both warnings are quality improvements, not blockers. A fresh agent with zero context can execute this plan from the document alone. Every dependency is either inline, verifiable on disk, or explicitly documented as a Doppler-fetched credential.
