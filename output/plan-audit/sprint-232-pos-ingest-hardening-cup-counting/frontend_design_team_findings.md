# S232 Plan Audit — Frontend / Design / Team Orchestration Findings

Plan: `F:\Dropbox\Projects\BEI-ERP\docs\plans\2026-05-02-sprint-232-pos-ingest-hardening-cup-counting.md`
Auditor focus: Frontend correctness, design principles, team orchestration, operational completeness.
Audit date: 2026-05-02.

Severity legend: **BLOCKER** — must fix before execute. **HIGH** — fix before execute. **MEDIUM** — should fix. **LOW** — cosmetic / nice-to-have.

---

## Phase 6 — Frontend Audit

### Finding 1 — Phase 6.1 audit grep: zero direct Supabase queries; ALL routes go through HRMS API. (LOW — informational)

I ran the grep the plan defers to Phase 6.1:

```
grep -rn "cups_sold|item_count|cups" F:/Dropbox/Projects/bei-tasks/{app,lib,components} --include "*.{ts,tsx}"
```

Findings:
- 35 hits across `app/dashboard/analytics/sales/**`, `app/dashboard/analytics/product/page.tsx`, `app/dashboard/scm/route-planner/page.tsx`, `app/dashboard/warehouse/inventory/page.tsx`, `lib/sales-dashboard.ts`, `lib/api/sales-dashboard.ts`, `components/company-master/warehouse-section.tsx`, `app/api/picking/route.ts`.
- The `app/dashboard/analytics/sales/**` consumers all read `summary.cups_sold` / `day.cups_sold` / `store.cups_sold` from a typed response object. The fetch path is `lib/api/sales-dashboard.ts` → `/api/analytics/sales/overview` → `app/api/analytics/sales/[endpoint]/route.ts` (line 12-22), which proxies to `hrms.api.sales_dashboard.get_sales_dashboard_*`. All cup numbers originate in the HRMS backend.
- The `item_count` hits are unrelated domains (warehouse inventory, route planner, warehouse-section, picking) — they are SCM/warehouse counts, not POS cup counts. None of them touch `pos_orders` / `pos_order_items` in Supabase.
- The `lib/sales-dashboard.ts` hits (lines 82, 163, 206, 262) are **TypeScript type declarations only** — they declare `cups_sold: number` on the `SalesDashboardSummary` interface; no SQL.

**Conclusion:** Phase 6.2 is correctly determinable as N/A. No direct Supabase queries in bei-tasks read cup data — the rewire happens entirely in `hrms/api/sales_dashboard.py`. Phase 6.2 should be marked N/A in the PR description, leaving Phase 6.3 (badge) as the only frontend task.

The plan's Phase 6.2 fallback ("N/A with explanation in PR description") is correctly worded. No action required other than confirming this audit result is captured at execute time.

### Finding 2 — Phase 6.3 metric-change badge target file is identifiable and should be hard-coded into MUST_MODIFY. (HIGH)

The plan says "TBD per audit". The target IS identifiable today; locking it in removes ambiguity for the executing agent.

The Cups Sold tile lives at:
- `F:\Dropbox\Projects\bei-tasks\app\dashboard\analytics\sales\page.tsx` line 600 — primary Sales Dashboard hero card
- `F:\Dropbox\Projects\bei-tasks\app\dashboard\analytics\sales\store-detail-dialog.tsx` line 217 — store detail dialog tile
- `F:\Dropbox\Projects\bei-tasks\app\dashboard\analytics\sales\stores\[locationId]\page.tsx` line 307 — per-store page tile
- `F:\Dropbox\Projects\bei-tasks\app\dashboard\analytics\sales\stores\store-leaderboard-mobile.tsx` line 141 — leaderboard mobile cup stat

There are **four** Cups Sold display surfaces. The plan implies one; that misrepresents scope. Either:
- (a) Apply the tooltip to ALL four surfaces (recommended — consistent UX, prevents stale-methodology messaging on any one surface), or
- (b) Apply only to the main Sales Dashboard hero tile and accept inconsistency.

**Recommended fix:** Update Phase 6.3 to enumerate all four files explicitly in MUST_MODIFY:
```
bei-tasks/app/dashboard/analytics/sales/page.tsx (hero tile, line ~600)
bei-tasks/app/dashboard/analytics/sales/store-detail-dialog.tsx (line ~217)
bei-tasks/app/dashboard/analytics/sales/stores/[locationId]/page.tsx (line ~307)
bei-tasks/app/dashboard/analytics/sales/stores/store-leaderboard-mobile.tsx (line ~141)
```

Suggested implementation: a single shared `<CupsSoldTooltip>` component imported into each KpiTile invocation, NOT four ad-hoc tooltip snippets. This is the standard React composition pattern.

### Finding 3 — RBAC / Navigation impact: zero changes needed. (LOW — confirmed)

Plan does not declare RBAC changes. Verified:
- No new routes added (`page.tsx` count unchanged).
- No new roles in `bei-tasks/lib/roles.ts` (cups view is part of Sales Dashboard which already has analytics personas).
- Backend `hrms.api.sales_dashboard.*` whitelist endpoints are reused (existing access guarding via `BEI Sales Dashboard Store Access` DocType).

Confirmed — zero RBAC changes needed. No finding.

### Finding 4 — Empty / error / loading states for cup count are NOT addressed. (MEDIUM)

The plan does not specify behavior when:
- Supabase is unreachable (timeout) — does the cup tile show "—", show "0", show stale-cache value?
- The `pos_products` JOIN returns zero matched products (e.g., classification table un-seeded for a new product) — does cups_sold drop silently to 0 with no warning?
- The `v_pos_cups_sold` view query takes >5s — what's the degraded state?

The existing `app/dashboard/analytics/sales/page.tsx:584-591` has a `freshness.data_quality_warnings[]` mechanism and a hard-coded `FoodPanda cups are validated only through ${fpCupsMax}` warning. The plan rewires the metric methodology but does NOT add a corresponding warning for "cups counted under new methodology". When the cup number drops by ~3.7% (audit's 113 line items / 3,054 prior count = 3.7% Araneta sample), users will report the dashboard as "broken" until they discover the methodology change.

**Recommended fix:** Add a Phase 6.3b task: "Append a `cups_methodology_v2_active: true` flag on `SalesDashboardFreshness` and surface a one-time `data_quality_warnings` entry: 'Cup count methodology updated 2026-05-02 — addons/packaging now excluded. Historical comparison may show ~3-4% reduction.'" The existing warning-rendering machinery handles display.

This is also the only honest answer to "what about historical mid-window comparisons?" — without a warning, a user looking at a 30-day window straddling 2026-05-02 will see the methodology change as a vertical drop in their daily series and mistake it for a sales decline.

---

## Design Review

### Finding 5 — `hrms/utils/pos_dedup.py` module structure is clean. (LOW — confirmed)

The two functions both have a single responsibility:
- `find_bill_number_twin(...)` — natural-key lookup, primary path.
- `find_cluster_twin(...)` — fallback for NULL-bill_number rows, with a 60-second time-window heuristic and SHA256 of items.

Both share the "find an existing twin row in `pos_orders` and return its id (or None)" abstraction. The `sha256` of items signature is properly scoped to ONLY the cluster-twin path (it has no purpose in the bill-number path). This is correct cohesion.

The module has a clean single responsibility ("Given identifying fields of a candidate POS order, find an existing duplicate in pos_orders or return None"). Both functions could share a small private `_lookup` helper but that is a micro-optimization, not a design issue.

**Confirmed clean** — no action needed.

### Finding 6 — `infer_payment_type` placement (Phase 4.1) — recommend co-locating in `pos_dedup.py` is WRONG; recommend a new `pos_inference.py` instead. (MEDIUM)

Phase 4.1 places `infer_payment_type(service_channel_id) -> Optional[str]` inline in `hrms/api/mosaic_webhook.py`. That works for the webhook path but Phase 4 also implies the poll path needs it (otherwise GrabFood/FoodPanda orders ingested via poll with NULL `payment_methods` array still get NULL payment rows — which is exactly the 1.8-2.4% gap noted in the live-probe table at the top of the plan).

Three placement options:
1. Inline in `mosaic_webhook.py` only — leaves the poll path uncovered. **Wrong.**
2. Co-located in `pos_dedup.py` — that module is about deduplication; payment inference is a separate concern. **Wrong (single-responsibility violation).**
3. New file `hrms/utils/pos_inference.py` — a sibling to `pos_dedup.py` for inference rules. Both `mosaic_webhook.py` and `sync_pos_to_supabase.py` import it. **Recommended.**

The plan does not say where `infer_payment_type` lives across both ingestion paths. Phase 4.1's MUST_MODIFY only lists `hrms/api/mosaic_webhook.py` — meaning the poll path is silently missing the fix. This is a real gap, because the plan correctly states (around line 76-80) that 98% of FP/GF poll-source orders have payment_methods populated, but 1.8-2.4% don't, and they need the same inference for the safety-net 2% gap.

**Recommended fix:**
- Create `hrms/utils/pos_inference.py` with `infer_payment_type(service_channel_id)` and any future inference rules (e.g., `infer_channel(service_type_id, service_channel_id)` — already inlined as `_resolve_channel` in both ingester modules; consolidating would be tidier).
- Update Phase 4.1 MUST_MODIFY to include both `hrms/api/mosaic_webhook.py` AND `scripts/sync_pos_to_supabase.py`, and add `hrms/utils/pos_inference.py` to MUST_MODIFY.
- Update Phase 4.3 verifier to replay BOTH paths (current spec only replays webhook).

### Finding 7 — `webhook_duplicates` table naming is a maintainability anti-pattern. (HIGH)

The plan acknowledges the issue (line 86, 333):
> "(table name kept for continuity even though the source is poll)"

This is exactly wrong. The plan now ships a table whose name actively misleads any future engineer reading the schema. 99.95% of rows in that table will be poll-source duplicates, not webhook-source. Six months from now an engineer will grep `webhook_duplicates`, not find the poll script, and waste hours.

There is no "continuity" cost — the table doesn't exist yet. Renaming is free now; expensive later.

**Recommended fix:** Rename to `pos_duplicates`. Update:
- Phase 1.2: `scripts/s232_supabase_migrations/002_webhook_duplicates.sql` → `002_pos_duplicates.sql`; CREATE TABLE name → `pos_duplicates`.
- Phase 1.5, 1.5b, 1.7 verifier MUST_CONTAIN: `webhook_duplicates` → `pos_duplicates`.
- Anti-Rewind table line 483: `webhook_duplicates` → `pos_duplicates`.
- Source Audit line 167: working CSV name `webhook_duplicates.csv` is fine to keep (artifact from a different epoch).

Also kill the never-implemented `webhook_review_queue` reference at line 483 (see Finding 14).

### Finding 8 — `is_duplicate BOOLEAN` is consistent — the audit query premise is incorrect. (LOW — premise correction)

The audit query asks about a "Phase 1.5b mention of `is_duplicate=PENDING_REVIEW`". I grep-confirmed there is NO `PENDING_REVIEW` string anywhere in the plan. The `is_duplicate` field is consistently typed `BOOLEAN DEFAULT false` (Phase 1.3, line 334) and only set as `true` in the backfill (Phase 5.1, line 419), never to a string. No type clash exists.

The fallback / human-review path is implemented via the separate `webhook_duplicates` table (renamed to `pos_duplicates` per Finding 7), not via a string state on `is_duplicate`. This is the correct design.

**No fix needed.** The audit premise was wrong; documented here so the reviewer doesn't re-flag it.

---

## Team Orchestration

### Finding 9 — Phase 1 budget arithmetic error: declared 12, sums to 15. (HIGH)

Phase 1 budget table (line 247) declares 12 units. Summing the actual task units in the body (line 332-340):
- 1.1=1, 1.2=1, 1.3=1, 1.4=3, 1.5=3, 1.5b=2, 1.5c=1, 1.6=1, 1.7=2 = **15 units**

15 units IS the hard cap (line 254). Phase 1 hits the cap, not the preferred 12 split threshold.

Other phases sum correctly:
- Phase 0: 1+0+0+1+1 = 3 ✓
- Phase 2: 1+3+2+1+3+1+1 = 12 ✓
- Phase 3: 1+1+2+1 = 5 ✓
- Phase 4: 2+1+1 = 4 ✓
- Phase 5: 3+2+2+1 = 8 ✓
- Phase 6: 1+3+1+1 = 6 ✓
- Phase 7: 1+3+1+1+1+1 = 8 ✓

Real total: 3 + 15 + 12 + 5 + 4 + 8 + 6 + 8 = **61** (plan declares 58).

Implications:
- Phase 1 is not the 12-unit phase the budget claims — it's a 15-unit phase at the cap. Any unforeseen complexity (PostgREST race conditions, Supabase migration ordering, the CSV-driven seed flow) pushes it over.
- The plan's own splitting rule (line 527) says "If Phase 6 is needed AND any of Phases 1, 2, 5 expand beyond budget during execution: split into S232a/S232b". Phase 1 is *already* at the cap on paper; very limited slack.

**Recommended fix:** Either (a) update the budget table to show Phase 1 at 15 units and total at 61, or (b) consolidate 1.5b's webhook future-proofing into 1.5 (drops 2 units; brings Phase 1 to 13). Option (a) is more honest. The total still fits the 80-unit ceiling.

### Finding 10 — Cross-phase dependencies are NOT formally declared in the plan. (MEDIUM)

The plan's prose mentions dependencies casually ("Phase 5 depends on Phase 1 schema changes", "Phase 6 depends on Phase 2 cup classification") but there is no formal dependency block, no "depends_on" YAML, and no explicit ordering rule.

Implicit dependencies (verified by reading task content):
- Phase 1.4 (`pos_dedup.py` helper) → Phase 1.5 + 1.5b + 1.5c (consumers)
- Phase 1.1, 1.2, 1.3 (migrations) → Phase 5.1 (backfill needs `is_duplicate` column AND `webhook_duplicates` table)
- Phase 2.1 (`pos_products` table) → Phase 2.2 (seed) → Phase 2.3 (override CSV) → Phase 2.4 (apply overrides) → Phase 2.5 (rewire query) → Phase 5.3 (recount)
- Phase 4.2 (`inferred` column) → Phase 4.1 (writes the column) — wait, this is REVERSED from the order in the plan. Phase 4.1 cannot write `inferred=true` to `pos_order_payments` until Phase 4.2's column exists.
- Phase 6.1 (audit) → Phase 6.2 (update queries) — Phase 6.2 is conditional on 6.1's findings.
- Phase 7.1 (verifier sweep) is the gate to all earlier phases.

The Phase 4.1 / 4.2 ordering issue is a real defect: the migration must run BEFORE the code that writes the new column. The plan lists 4.1 before 4.2 in the table, suggesting 4.1 ships first. Either swap (run 4.2 first) or note explicitly that 4.2 must be applied to Supabase before the 4.1 code is deployed.

**Recommended fix:** Add a `## Phase Dependency Graph` section after the budget table:
```
0 → 1 (worktree must exist)
1.1, 1.2, 1.3 → 1.4 (helper consumes the schema)
1.4 → 1.5, 1.5b (consumers of helper)
1.5c migration → 1.5c code edits (column must exist before writes)
4.2 → 4.1 (column must exist before writes)
2.1 → 2.2 → 2.3 → 2.4 → 2.5 (linear)
1.* (schema) → 5.1 (backfill)
2.* (classification) → 5.3 (recount)
2.5 → 6.* (frontend depends on backend rewire)
0..6 → 7 (closeout)
```
Then re-order 4.1 and 4.2 to put migration first, OR mark 4.1 explicitly as "deploy 4.2 first".

### Finding 11 — Autonomous execution contract: all required fields present. (LOW — confirmed)

Verified at lines 495-509:
- ✓ `completion_condition` — line 497
- ✓ `stop_only_for` — lines 498-502
- ✓ `signoff_authority: single-owner` — line 508
- ✓ `canonical_closeout_artifacts` — line 509 (references `evidence_committed`)
- ✓ `continue_without_pause_through` — line 503
- ✓ `blocker_policy` — lines 504-507

Also verified `evidence_committed` (lines 27-39) and `evidence_transient` (lines 41-46) are declared per the worktree-isolation rule. **Confirmed compliant.**

### Finding 12 — Anti-rewind protection: two factual errors regarding S197 cron cadence and S227 sales_dashboard surface. (HIGH)

**Error 12a — S197 poll cadence.** Plan claims "S197 5-min poll cadence" three times (line 189, 230, 489). Verified the actual workflow file at `F:\Dropbox\Projects\BEI-ERP\.github\workflows\pos-sync-5min.yml`:
```
schedule:
  - cron: "*/10 2-16 * * *"  # every 10 minutes, 10 AM-midnight PHT
```
The cron is `*/10`, not `*/5`. The filename `pos-sync-5min.yml` is misleading (legacy from when it WAS 5min, presumably). The plan's intro section correctly states "API poll every 10 minutes" (line 57), so the plan is internally inconsistent.

This matters because the protected-surfaces section claims to "preserve" the 5-min cadence — an executing agent following that instruction literally might "fix" the 10-min cron back to 5-min thinking the file drifted. That would 2x the API call volume to Mosaic, possibly triggering rate-limit blocks.

**Recommended fix:** Update all three occurrences:
- Line 189: `runs *\/10 2-16 * * * UTC` (already says */5; correct to */10).
- Line 230: `S189 webhook + S197 5-min poll cadence` → `S189 webhook + S197 10-min poll cadence`.
- Line 489: `S197 5-min poll cadence` → `S197 10-min poll cadence`.

**Error 12b — S227 sales_dashboard.py surface.** Plan claims "S227 store-partner response shaping in `sales_dashboard.py`" as a protected surface (line 230, 491). I grep-confirmed: there is currently **no** `Store Partner`, `partner`, `deepcopy`, or response-stripping code in `hrms/api/sales_dashboard.py`. The string `S227` does not appear in the file.

Possible explanations: (a) S227 is BUILD_COMPLETE_AWAITING_L3_AND_REVIEW per the registry — the PR exists but has not been merged to `production`, so the surface is on a branch, not in `production`; (b) S227 was merged but the response-shaping went to a different file (e.g., `hrms/api/sales_dashboard_partner.py` or similar; not found); (c) the plan is referencing aspirational state.

The S232 plan branches off `origin/production` (line 308). If S227 is unmerged, S232's anti-rewind list is protecting a surface that isn't there yet. If S227 lands first, S232's edits to `sales_dashboard.py` (Phase 2.5 cup-rewire) need to coordinate with whatever response-stripping S227 adds. The plan does NOT define this coordination.

**Recommended fix:** Either:
1. Confirm S227 has merged to production before S232 starts, document the merge SHA in the plan's Remote Truth Baseline (line 493), and update Phase 2.5 to be aware of the deepcopy / response-stripping surface, OR
2. Drop the "S227 store-partner response shaping" line from the anti-rewind table since it's not in production — replace with "future S227 merge will need to coordinate with S232's cup-rewire in `sales_dashboard.py`".

### Finding 13 — Other anti-rewind surfaces: S169, S171, S189, S200 verified clean. (LOW — confirmed)

- **S169 cancellation tombstone**: verified at `hrms/api/mosaic_webhook.py:147-158` — sets `cancelled_at = %s, ... AND cancelled_at IS NULL` guard. Phase 2.5 cup-rewire and Phase 1.4-1.5 dedup helper do not touch this code path. ✓
- **S171 v_sync_drift_monitor**: view lives in Supabase, not in source. Phase 5.2 explicitly adds `WHERE is_duplicate IS NOT TRUE` filter — but the plan correctly notes (line 487) that S232 may add a JOIN/filter without changing semantics. The `is_duplicate IS NOT TRUE` semantic is additive (excludes a new dimension); does not change the drift query's primary computation. ✓
- **S189 webhook URL**: `https://hq.bebang.ph/api/method/hrms.api.mosaic_webhook.receive` (line 190) — verified as the existing receiver. Phase 1.5b adds dedup BEFORE the upsert call but does not change the URL. ✓
- **S200 store auto-discovery TTL cache**: 30s TTL claim (line 230) — `hrms/api/sales_dashboard.py:59` shows `SALES_DASHBOARD_CACHE_TTL = 300` (5 min, not 30s). The 30s figure may be a different cache. Phase 2.5 cup-rewire does NOT touch caching — the rewire is at the SQL level. ✓ (note 30s vs 300s discrepancy is a documentation nit, not a regression risk).

**Confirmed: S169, S171, S189, S200 are not regressed by S232's planned phases.**

---

## Operational Completeness

### Finding 14 — Migration filename collisions: numbers 003 and 005 are both reused. (BLOCKER)

The plan distributes Supabase migrations across `scripts/s232_supabase_migrations/`:

| Migration | Phase | Filename declared in MUST_MODIFY |
|----------:|------:|----------------------------------|
| 001 | 1.1 | `001_bill_number_unique_index.sql` |
| 002 | 1.2 | `002_webhook_duplicates.sql` |
| 003 | 1.3 | `003_pos_orders_dedup_fields.sql` |
| **003** | **2.1** | **`003_pos_products.sql`** ← COLLISION |
| 004 | 1.5c | `004_short_order_id.sql` |
| 005 | 4.2 | `005_pos_order_payments_inferred.sql` |
| **005** | **5.2** | **`005_views_filter_dupes.sql`** ← COLLISION |

Two migrations cannot share a number. Migration tooling typically applies them in lexical order; whichever runs first will silently shadow the second (Supabase's schema-migrations table will record only one). The Phase 1 verifier (line 354) lists `003_pos_orders_dedup_fields.sql` only — the verifier would PASS even though Phase 2.1's `003_pos_products.sql` was never created (filename was reused, content overwritten).

This is the type of issue that will silently corrupt state during execute and emerge as a confusing error in Phase 5 backfill.

**Recommended fix:** Renumber to a strict linear sequence:
```
001_bill_number_unique_index.sql        (Phase 1.1)
002_webhook_duplicates.sql → 002_pos_duplicates.sql (Phase 1.2; also rename per Finding 7)
003_pos_orders_dedup_fields.sql         (Phase 1.3)
004_short_order_id.sql                  (Phase 1.5c)
005_pos_products.sql                    (Phase 2.1, was 003)
006_pos_order_payments_inferred.sql     (Phase 4.2, was 005)
007_views_filter_dupes.sql              (Phase 5.2, was 005)
```

Then update Phase 1.7 verifier `required_files` and all MUST_MODIFY references.

### Finding 15 — Anti-rewind table claims `webhook_review_queue` as a new surface that no phase actually creates. (MEDIUM)

Line 483:
> | `webhook_duplicates`, `webhook_review_queue` (new tables) | S232 | New surfaces. |

`webhook_review_queue` does not appear in any phase task. The plan's earlier rationale (line 175) says the cluster-window rule "routes edge cases (timestamps far apart) to a human review queue", but the actual revised dedup approach (lines 153-157) eliminates the review queue:

> "This keeps the sprint scope intact but makes Phase 1 simpler and eliminates the review queue (kept as a safety net for the NULL `bill_number` fallback path only)."

The plan correctly removed the queue from the implementation, but the anti-rewind table still lists it. Either:
- (a) The queue IS being kept for the NULL-fallback path — then Phase 1 needs an explicit task to create the table, OR
- (b) The queue is gone — then drop the line from the anti-rewind table.

Reading the actual fallback path (Finding 5's `find_cluster_twin` returns the existing twin's ID, which goes to `webhook_duplicates`, not a separate review queue), I conclude (b) — the queue was eliminated.

**Recommended fix:** Remove `webhook_review_queue` from line 483. The sprint creates `pos_duplicates` (renamed) and `pos_products` only.

### Finding 16 — DM-3 EWT/VAT gate: not applicable but should be explicitly noted. (LOW)

Per `.claude/rules/frappe-development.md`, Plan Audit Gate DM-3 says any feature creating Payment Entry / Journal Entry must address EWT and VAT. S232 does NOT create PE or JE — it operates entirely on Supabase analytics tables (`pos_orders`, `pos_order_items`, `pos_order_payments`, new `pos_products`, new `pos_duplicates`). The `inferred` payment_type rows are analytics-only — they do NOT generate Frappe GL entries.

The plan's `canonical_scope: none` rationale (lines 13-20) explicitly disclaims SI/PO/MR/SE/JE/PE/GL touches, which covers DM-3 by exclusion.

**No DM-3 violation.** Worth noting in the closeout that the Frappe Deadly Mistakes checklist was reviewed and found N/A.

### Finding 17 — L3 scenario coverage: covers all phases except Phase 3 timestamp test. (MEDIUM)

L3 Workflow Scenarios table (lines 452-463) has 11 scenarios. Mapping to phases:
- Phase 1 (dedup): scenarios 1, 2, 3, 4, 5 (normal, id-drift, null-bill, two-real-customers, burst-retry) ✓
- Phase 2 (cup classification): scenario 8 (mixed-cart) ✓
- Phase 3 (timestamp PHT): **NOT TESTED IN L3** — Phase 3.3 has a unit test but no L3 scenario. The plan delegates to a Python unit test (line 400), which is fine for the timezone math but doesn't verify the dashboard end-to-end.
- Phase 4 (FoodPanda/GrabFood inference): scenarios 6, 7 ✓
- Phase 5 (backfill): scenario 10 (sam@bebang.ph dashboard check) ✓
- Phase 6 (badge): scenario 11 (tooltip) ✓

A Phase 3 L3 scenario is missing. Recommended addition:
> | n/a (script) | Replay a webhook with `billed_at = 2026-04-19T18:30:00Z` (which is 2026-04-20T02:30:00+08:00 PHT, crosses date boundary) | `pos_orders.business_date = 2026-04-20`; Sales Dashboard for 2026-04-20 includes this transaction; for 2026-04-19 excludes it | UTC bleeding into PHT-day-bucketing |

Without this scenario, Phase 3 unit-test passes do not prove the dashboard date-bucketing is correct end-to-end.

### Finding 18 — Status reconciliation contract is incomplete. (LOW)

Lines 511-518 (Status Reconciliation Contract) lists 4 places to update on status change:
1. `output/s232/SUMMARY.md`
2. `output/s232/DEFECTS.md`
3. plan YAML status line
4. `docs/plans/SPRINT_REGISTRY.md` row

Missing: the GitHub PR description and PR title (per merge protocol). The Phase 7.5 closeout also writes `execution_summary` in YAML — that's fine, but the contract should mention the PR description must mirror SUMMARY.md.

Cosmetic; won't break execution but reduces auditability post-merge.

---

## Summary

**Verdict:** The plan is largely sound — backend dedup strategy is correct (bill_number natural key + cluster-window fallback), cup classification approach is durable (flag, not heuristic), and Phase 6 frontend lane is correctly conditional on the audit finding (which I confirmed is N/A for direct queries; only badge needed). However, there are real defects that should be fixed before execute.

### Blocker count: 1
- Finding 14 — Migration filename collisions (003 reused, 005 reused) will silently corrupt state during execution.

### High count: 4
- Finding 2 — Phase 6.3 badge target should enumerate all 4 surfaces, not "TBD".
- Finding 7 — `webhook_duplicates` → `pos_duplicates` rename to avoid future engineer confusion.
- Finding 9 — Phase 1 budget arithmetic: declared 12, sums to 15 (at cap, no slack).
- Finding 12 — Anti-rewind: S197 cadence is 10-min not 5-min (3 places); S227 protected surface not yet in production.

### Medium count: 4
- Finding 4 — Empty / error / loading states for cup tile not addressed.
- Finding 6 — `infer_payment_type` placement: needs `hrms/utils/pos_inference.py`, plus poll-path coverage in MUST_MODIFY.
- Finding 10 — Cross-phase dependencies not formally declared; Phase 4.1/4.2 ordering reversed.
- Finding 15 — `webhook_review_queue` listed in anti-rewind but never created.
- Finding 17 — L3 missing a Phase 3 timestamp end-to-end scenario.

### Low / informational count: 5
- Findings 1, 3, 5, 8, 11, 13, 16, 18 — confirmed correct or premise-only.

### Premise corrections returned to caller
- Audit task #8 asserted a `is_duplicate=PENDING_REVIEW` string mismatch — that string does not appear in the plan; the field is consistently `BOOLEAN`. Documented in Finding 8.
