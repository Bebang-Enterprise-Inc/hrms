# S232 Plan Audit — Deployment + QA + L3 + Test Data Seeding Compliance

**Plan:** `docs/plans/2026-05-02-sprint-232-pos-ingest-hardening-cup-counting.md`
**User question:** "will this resolve all our duplicates issues?"
**Audited by:** Deployment/QA/L3 review agent
**Date:** 2026-05-02

---

## Executive Verdict

The plan covers most duplicate-resolution paths, but contains **one CRITICAL deployment-ordering bug** that will cause Phase 1 to fail outright in production, plus **3 BLOCKER-grade L3 coverage gaps** related to the user's exact concern. It will not resolve all duplicate issues without these fixes.

**Counts: 1 CRITICAL, 3 BLOCKER, 5 MAJOR, 4 MINOR.**

---

## 1. L3 SCENARIO COVERAGE FOR DUPLICATES

### 1.1 [BLOCKER] Cup count assertion is fuzzy ("~2,941"), not the exact gate the user asked for

**Finding:** Line 462 reads:
> "Cups display shows ~2,941 (NOT 3,054 or 2,334)"

The tilde and "NOT 3,054 or 2,334" framing makes this a soft expectation rather than an assertion. The user's question explicitly anchors the gate on **2,941 = true cup drinks**. The L3 scenario must assert exact equality to 2,941 (with documented data-integrity tolerance ±N from the audit).

The scenario row also lacks a programmatic check — it's a "sam@bebang.ph manual UI step." There is no machine-verifiable "L3 verifier asserts `v_pos_cups_sold` total for Araneta 2026-04-20..2026-04-26 == 2941" anywhere.

**Required fix:** Add an automated L3 row:
```
| n/a (script) | scripts/s232_verify_cup_count.py --location 2557 --start 2026-04-20 --end 2026-04-26 | Returns exactly 2941 (audit ground truth). 3054 = old sum(qty), 2334 = old item_count. | Cup classification did not produce the audit's verified count |
```

### 1.2 [BLOCKER] No L3 scenario verifies cancellation tombstone survives a duplicate-retry pull

**Finding:** S169 ships an `order.cancelled` tombstone on `pos_orders.cancelled_at`. The plan's "Anti-Rewind" table (line 486) protects S169, but **no L3 scenario** confirms that:
1. Order `bill_number=99007` is ingested (poll run 1)
2. Order is cancelled via S169 webhook → `cancelled_at` set
3. Poll run 2 returns the SAME `bill_number` with a NEW Mosaic ID (the production drift behavior)
4. Dedup must REJECT the new ID AND preserve `cancelled_at` on the original row

This is the highest-risk failure mode: a tombstone gets silently overwritten because the dedup helper (Phase 1.4 `find_bill_number_twin`) returns the existing row, but the upsert path then UPDATEs that row with fresh fields, blanking `cancelled_at`.

**Required fix:** Add an L3 scenario `--scenario cancelled-retry` that asserts `cancelled_at` is preserved after a re-arrival of the same `bill_number`.

### 1.3 [BLOCKER] No L3 scenario for Phase 5 backfill correctness

**Finding:** Phase 5 task 5.1 marks 945 historical duplicates `is_duplicate=true`. There is no L3 scenario that verifies:
- After backfill, exactly the expected duplicate count is marked
- The KEPT row in each cluster is the earliest by `created_at` (or the one referenced by `kept_order_id`)
- No `is_duplicate=true` was applied to a non-duplicate cluster (false positives)
- Aggregate `original_gross_sales` after `WHERE is_duplicate IS NOT TRUE` filter drops by the audit's ~PHP 15K for Araneta, scaled to all stores

The user is asking "will this resolve duplicates?" — the answer for the existing 945 only comes from Phase 5 backfill working correctly. Without an L3 row, the agent will run the script, observe no errors, and call it done.

**Required fix:** Add an L3 scenario `--scenario backfill-validation` that:
1. Reads `dedup_collisions_before.csv` cluster count (e.g., 945 expected)
2. Asserts `SELECT count(*) FROM pos_orders WHERE is_duplicate=true` matches that count
3. Asserts `SELECT count(*) FROM pos_orders WHERE is_duplicate=true AND kept_order_id IS NULL` == 0
4. Spot-checks 5 random clusters: kept_order is the earliest by `created_at`

### 1.4 [MAJOR] False-positive guard exists but is weak

**Finding:** Line 457 has a "two-real-customers" scenario (different `bill_number`, same items, same gross, same second). This is good but only verifies the bill-number primary path. It does NOT test the NULL-bill fallback path. If Phase 1.4's `find_cluster_twin` (60-second window) is invoked for two real customers in a multi-terminal store with NULL bill_numbers, it WILL false-positive.

**Required fix:** Add a `--scenario null-bill-two-customers` row: 2 NULL-bill orders, identical items, identical gross, 30 seconds apart at a multi-terminal store. Both must be accepted.

### 1.5 [MAJOR] Webhook future-proofing scenario exists but does NOT cover the S189 retry-burst pattern

**Finding:** Line 458 covers `burst-retry` with same `bill_number=99005` (5 webhooks). Good for the bill-number path. But the original S189 incident (per the audit) was 18 clusters where the webhook re-fired with DIFFERENT Order IDs within tight time windows. The current scenario uses the same bill_number throughout — what about the webhook firing same-bill but with the same `id` 5 times (unique-PK collision path)? The plan's helper relies on the bill_number twin check; if the same `id` arrives twice, the existing PK upsert handles it but is the path tested?

**Required fix:** Add a `--scenario same-id-retry` row: 5 webhooks with identical `id` AND `bill_number`. Verify only 1 row in `pos_orders` and 4 in `webhook_duplicates`.

### 1.6 [MINOR] Missing aggregator-channel cross-replay

The plan replays GrabFood (channel=1) and FoodPanda (channel=2) inference, but does not test a **dedup + inference combo**: same `bill_number` arriving twice for a FoodPanda order. Does the dedup correctly route to `webhook_duplicates` AND does the inference helper still fire on the FIRST arrival? Currently untested.

---

## Summary of duplicate-resolution coverage gap

User asked: "will this resolve all our duplicates issues?" Honest answer based on the L3 table: **mostly yes** for the 945 historical and the API-poll drift case, but with these scenarios MISSING:

| Pattern | Covered? | Gap severity |
|---------|----------|--------------|
| Same bill_number, different IDs across pulls (production bug) | YES — line 455 `id-drift` | OK |
| Two real customers, different bill_numbers, same content (false-positive guard) | YES — line 457 | OK |
| Cancellation tombstone survives duplicate retry | NO | BLOCKER |
| Webhook S189-style retry burst | PARTIAL — bill_number same path only | MAJOR |
| Cup count == 2,941 (NOT 3,054 or 2,334) | SOFT — tilde, manual UI | BLOCKER |
| Backfill correctly marked the 945 dupes | NO L3 scenario | BLOCKER |
| Two real customers, NULL bill, multi-terminal | NO | MAJOR |
| Same id retry (PK collision path) | NO | MAJOR |
| Dedup + inference combo on aggregator | NO | MINOR |

---

## 2. TEST DATA SEEDING CONTRACT COMPLIANCE

### 2.1 [MINOR] Synthetic test store ID 9999 collision check IS in Phase 0 (task 0.4) — PASS

Phase 0 task 0.4 (line 311) reads:
> "Verify synthetic store ID 9999 is free. Run psql ... SELECT count(*) FROM pos_orders WHERE location_id = 9999. Expect 0."

A HARD BLOCKER restatement appears at line 302. Compliant with S225 rule.

### 2.2 [MAJOR] `/frappe-bulk-edits` is referenced as the seeding mechanism — INCORRECT for this domain

**Finding:** Line 283 specifies the `pos_orders` seeding mechanism as:
> "Seed via `/frappe-bulk-edits` SUPABASE_INSERT"

This is **wrong**. `/frappe-bulk-edits` is the BEI skill for bulk-editing Frappe DocTypes via SSM (per the skill description loaded in the system reminder). It does NOT handle Supabase tables. Supabase rows are reached via:
- direct PostgREST/SQL (the same path Phase 0.4 uses for the collision check)
- a Python script using the `supabase-py` client (the path the existing `scripts/sync_pos_to_supabase.py` and S232 backfill scripts use)

**Required fix:** Replace "/frappe-bulk-edits SUPABASE_INSERT" with explicit reference to `scripts/s232_seed_test_orders.py --location 9999 --apply`. The seeding step (line 287-289) already mentions this script — the table at line 283 should match.

### 2.3 [MAJOR] Per-scenario preconditions NOT enumerated

**Finding:** The Test Data Seeding Contract (lines 276-300) lists THREE preconditions in aggregate (pos_products, pos_orders, test webhook payloads). The L3 Workflow Scenarios table has 10 rows, each requiring DIFFERENT preconditions:
- `id-drift`: 6 poll-run payloads with same bill but drifting IDs
- `null-bill`: 3 NULL-bill aggregator orders with matching cluster keys
- `two-real-customers`: 2 distinct-bill orders with same items+gross
- `burst-retry`: 5 webhooks same bill
- `foodpanda-no-payment`: 1 FP webhook with empty payments
- `grabfood-no-payment`: 1 GF webhook with empty payments
- `mixed-cart`: 1 order with 3 line items mixing cup + topping + packaging
- 1 "normal" baseline order

The contract does not enumerate what test data each scenario needs. Per S225 rule, every L3 scenario's preconditions must be explicit so the seeder can build them.

**Required fix:** Expand the seeding contract table to one row PER scenario, listing the exact synthetic IDs and payload shapes needed. Or reference a `scripts/s232_seed_l3_scenarios.py` that builds each scenario's data and writes a manifest to `output/s232/l3/seed_manifest.json`.

### 2.4 [MINOR] Teardown ledger format defined — PARTIAL

The plan mentions:
- `output/s232/l3/teardown_ledger.json` (written during seeding) at line 295
- `output/s232/l3/teardown_complete.json` (written after teardown) at line 297

But the FORMAT/SCHEMA of `teardown_ledger.json` is not specified. What entries does it contain? `(table_name, primary_key_value, seeded_at)` tuples? The S225 rule requires explicit format so any agent (not just the seeder) can clean up.

**Required fix:** Add a code block specifying the schema:
```json
{
  "seeded_at": "2026-05-02T...",
  "entries": [
    {"table": "pos_orders", "id": <int>, "location_id": 9999, "scenario": "id-drift"},
    {"table": "pos_order_items", "id": <int>, "order_id": <int>}
  ]
}
```

### 2.5 [MINOR] Closeout teardown task EXISTS — PASS

Phase 7 task 7.3 (line 445) explicitly runs `python scripts/s232_teardown.py --apply`. Mandatory teardown line at 300 reinforces it. Compliant.

---

## 3. BACKFILL VERIFICATION

### 3.1 [BLOCKER] No L3 scenario verifies the Phase 5 backfill ran correctly

Already flagged in 1.3 above — repeated here because it's both an L3 gap AND a backfill-validation gap.

The agent will:
1. Run `python scripts/s232_backfill_dupes.py`
2. See it complete without errors
3. Move on to Phase 7

There is NO programmatic gate that confirms:
- The expected number of clusters were marked
- No false positives
- The kept row in each cluster is the correct one
- Aggregate gross_sales drops by the predicted ~PHP 15K (Araneta) and ~PHP X (all stores)

Phase 5 verifier (line 422) only checks "both verification CSVs exist + non-empty" with "±2 cluster tolerance" — that does not verify CORRECTNESS, only EXISTENCE.

**Required fix:** Add Phase 5.5 task: "Validate backfill correctness. `scripts/s232_validate_backfill.py` reads `dedup_collisions_before.csv`, queries Supabase, asserts row counts and kept_order_id assignments match. Writes `output/s232/verification/backfill_validation.json` with `{expected: 945, marked: <actual>, false_positives: 0}`. Phase 5 verifier asserts `false_positives == 0` AND `abs(marked - expected) <= 5`."

---

## 4. DEPLOYMENT ORDERING

### 4.1 [CRITICAL] Phase 1 creates the unique index BEFORE Phase 5 marks existing duplicates — Phase 1 WILL FAIL

**Finding:** This is a real, blocker-grade ordering bug.

Phase 1 task 1.1 (line 332):
> "Add unique partial index on `pos_orders`. ... `CREATE UNIQUE INDEX pos_orders_bill_number_natural_key ON pos_orders (location_id, business_date, bill_number) WHERE bill_number IS NOT NULL`"

Phase 5 task 5.1 (line 419):
> "Backfill duplicate detection. ... walks pos_orders ... applies the natural-key + timestamp-clustering rule retroactively, sets `is_duplicate=true` and `kept_order_id=<earliest_order>` on each duplicate."

The plan's own evidence (line 63) says there are **945 existing duplicate rows** in production today. PostgreSQL's `CREATE UNIQUE INDEX` will scan existing rows and **abort with an error** if any pair violates the constraint. The 945 rows DO violate `(location_id, business_date, bill_number)` uniqueness — that is exactly what makes them duplicates.

The partial `WHERE bill_number IS NOT NULL` clause does not save this — the duplicates have non-NULL bill_numbers (that's how the audit found them: by grouping on bill_number).

**Three valid orderings exist; the plan picks none of them:**

A. **Mark dupes first, then index** (recommended):
   - Move Phase 5.1 (backfill `is_duplicate=true`) to BEFORE Phase 1.1
   - Change Phase 1.1 partial-index to `WHERE bill_number IS NOT NULL AND is_duplicate IS NOT TRUE`
   - Index creation succeeds because all violators are excluded

B. **Add the column first, then mark dupes, then index**:
   - Phase 1.3 (add `is_duplicate` column) FIRST
   - Then Phase 5.1 backfill
   - Then Phase 1.1 index with `WHERE NOT is_duplicate`

C. **Index with deferred enforcement**:
   - Use `CREATE UNIQUE INDEX CONCURRENTLY` doesn't help — still fails on existing dupes
   - Would require a check constraint NOT VALID + later VALIDATE — too complex for this plan

**Required fix:** Re-order phases. The simplest correction is:
1. Phase 1.3 (add `is_duplicate` column) → run FIRST
2. Phase 5.1 (backfill `is_duplicate=true`) → run SECOND
3. Phase 1.1 (create unique partial index) → run THIRD with `WHERE bill_number IS NOT NULL AND is_duplicate IS NOT TRUE`
4. Then continue Phase 1.2-1.7, Phase 2-4, Phase 5.2-5.4

This is a real bug and the plan WILL crash at Phase 1.1 deployment without this fix. Severity: **CRITICAL**.

---

## 5. WORKTREE ISOLATION

### 5.1 [PASS] Worktree spawn + closeout exist

Phase 0.1 (line 308) spawns the worktree via `git worktree add ... origin/production` and `cd`s into it.
Phase 7.6 (line 448) removes it via `git worktree remove`.
Branch and worktree paths match the convention in `.claude/rules/worktree-isolation.md`.

### 5.2 [MINOR] No explicit "cd into worktree" reminder in mid-plan tasks

The plan does not restate "all paths between Phase 0.1 and Phase 7.6 are run from the worktree CWD." If the agent's shell loses CWD (e.g., bash session reset between tool calls — which is exactly how the agent's environment behaves per the agent's system prompt: "Agent threads always have their cwd reset between bash calls"), the agent could silently revert to the main checkout.

**Required fix:** Add a top-of-Phase note: "Every bash command from Phase 1 through Phase 7 MUST start with `cd F:/Dropbox/Projects/BEI-ERP-s232-pos-ingest-hardening-cup-counting &&` to defend against CWD reset." Or use absolute paths everywhere.

---

## 6. EVIDENCE SPLIT COMPLIANCE

### 6.1 [PASS] evidence_committed and evidence_transient lists exist and are realistic

YAML frontmatter (lines 27-46) cleanly splits:
- **Committed** (output/s232/): SUMMARY, DEFECTS, state_before/after, dedup_collisions_before/after, cups_recount, l3 form_submissions/api_mutations/state_verification/teardown_ledger/teardown_complete
- **Transient** (tmp/s232/): sweep_run logs, probe JSONs, traceback txts, playwright_trace zips, webhook_replay JSONs

`playwright_trace_*.zip` is correctly listed as transient. No committed paths look transient.

### 6.2 [MINOR] `output/s232/vendor_outreach/` and `output/s232/verification/` are written but NOT in `evidence_committed`

Phase 7.4 writes `output/s232/vendor_outreach/2026-05-02_OR_No_Request.md` (line 446).
Phase 0.5 writes `output/s232/verification/state_before.json` (line 312, in committed list — fine).
Phase 1.7 / 2.7 / 3.4 / 4.3 / 5.4 / 6.4 / 7.1 write `output/s232/verification/phase_<N>_verifier.txt` (line 533).
Phase 3.1 writes `output/s232/verification/timestamp_usage_audit.md` (line 398).
Phase 5.4's `output/s232/verification/dedup_collisions_after.csv` IS in the committed list.

But several of the above (vendor_outreach .md, phase_<N>_verifier.txt, timestamp_usage_audit.md, bei_tasks_cup_query_audit.md) are NOT explicitly enumerated in `evidence_committed`. The list is selective.

**Required fix:** Either enumerate every committed path (preferred) or use a glob like `output/s232/verification/*.{json,csv,md}` and `output/s232/vendor_outreach/**/*`. The agent's git-add discipline depends on this list being complete.

---

## 7. PR-HANDOFF

### 7.1 [PASS] PR-handoff text exists

Line 543:
> "PR-handoff: this sprint creates the PR and stops. Sam handles merge + deploy."

Compliant with the Sam-merges-PRs governance rule.

### 7.2 [MAJOR] Autonomous Execution Contract `completion_condition` includes "PR created and shared" but does NOT explicitly forbid auto-merge

Line 497:
> "all 7 phases green; all phase verifiers PASS; all L3 evidence files non-empty; teardown_complete.json shows zero seeded data remaining; plan + registry pushed; PR created and shared with Sam."

Reads as if "PR created" is an end-state, but the agent could interpret "all phases green" + Phase 7.5 closeout artifacts pushed as license to also `gh pr merge`. The block-push-to-merged-branch hook (per CLAUDE.md) catches some risk, but the explicit prohibition on auto-merge is missing.

**Required fix:** Append to `completion_condition`: "Agent does NOT run `gh pr merge`. PR is left open for Sam's review."

---

## 8. SENTRY OBSERVABILITY GATE

### 8.1 [PASS] Phase 1.6 — webhook handler

Line 339:
> "set_backend_observability_context(module='pos_ingest', action='handle_order_completed', mutation_type='create', extras={'order_id': order_id, 'bill_number': bill_number})"

Module `"pos_ingest"` and action `"handle_order_completed"` are correct per the rule. `mutation_type="create"` matches the actual operation.

### 8.2 [PASS] Phase 2.6 — sales_dashboard

Line 389:
> "Every modified `@frappe.whitelist()` endpoint in `sales_dashboard.py` calls `set_backend_observability_context(module='sales_dashboard', action='<fn>')`."

Module `"sales_dashboard"` is correct (per rule, BEI module names: warehouse, commissary, store, billing, hr, finance, etc. — `sales_dashboard` is consistent). Action is parameterized per function, which is correct.

### 8.3 [MINOR] `@frappe.whitelist()` endpoints in `discount_abuse.py` and `marketing_giveaways.py` MAY be modified in Phase 5.2 without Sentry instrumentation

Phase 5.2 (line 420) adds `WHERE is_duplicate IS NOT TRUE` filter to views consumed by `discount_abuse.py` (per line 221) and `marketing_giveaways.py` (line 222). If these endpoints' `@frappe.whitelist()` functions are touched, they need the Sentry call too. Plan does not specify.

**Required fix:** Add to Phase 5.2: "If any whitelisted endpoint in discount_abuse.py or marketing_giveaways.py is modified, add `set_backend_observability_context(module='discount_abuse'|'marketing_giveaways', action=<fn>)`."

### 8.4 [MINOR] Inference helper added in Phase 4.1 may need observability

Phase 4.1 (line 409) adds `infer_payment_type` and modifies the payment mapping in `mosaic_webhook.py`. The webhook receive endpoint is the wrapping `@frappe.whitelist()`. Phase 1.6 covers `_handle_order_completed`. But Phase 4.1's path runs through the SAME endpoint, so it inherits the existing scope. Phase 4 should explicitly note "no new observability call needed — inherits Phase 1.6 scope."

---

## 9. PHASE VERIFIERS AS GATES

### 9.1 [PASS] Phase 7.1 runs all phase verifiers in sequence

Line 443:
> "Run all phase verifiers. python scripts/s232_verify_all_phases.py runs Phase 0-6 verifiers in order. Any FAIL halts here."

This is BLOCKING (per "Any FAIL halts here") and runs BEFORE L3 (Phase 7.2 is next). Compliant.

### 9.2 [MAJOR] Per-phase verifiers are NOT explicitly described as blocking gates DURING phase execution

Line 376:
> "If verifier fails, do NOT proceed to Phase 2. Fix and re-run."

This appears once at the end of Phase 1. Phases 2-6 do not have an equivalent "do not proceed" sentence. The agent could run Phase 2 verifier, see FAIL, and continue to Phase 3 anyway.

**Required fix:** Add the same "If verifier fails, do NOT proceed to Phase N+1" sentence at the end of every phase. OR: codify in `Zero-Skip Enforcement` section that any verifier FAIL is a hard halt.

### 9.3 [MINOR] Phase 7.1 runs verifiers AGAIN even though they ran during execution

This is good (defense-in-depth) but the plan should note that Phase 7.1 is a re-run for end-state confirmation, not the first run. Otherwise the agent might skip the per-phase runs assuming Phase 7.1 will catch it.

---

## 10. CLOSEOUT REGISTRY + PLAN YAML + GIT ADD -F

### 10.1 [PASS] Phase 7.5 covers all three

Line 447:
> "Update plan YAML status: COMPLETED, completed_date: <today>, execution_summary. Update SPRINT_REGISTRY.md row to COMPLETED with PR link. Commit + push (git add -f docs/plans/...)."

All three S092 closeout requirements covered:
- plan YAML status update ✓
- registry update ✓
- `git add -f` for plan files ✓

### 10.2 [MINOR] `git add -f docs/plans/...` is shorthand — should specify both files

The shorthand `docs/plans/...` is ambiguous. Should be `docs/plans/2026-05-02-sprint-232-pos-ingest-hardening-cup-counting.md docs/plans/SPRINT_REGISTRY.md` to match the named-files-only rule from CLAUDE.md (Memory lesson "feedback_git_add_specific_files").

### 10.3 [MINOR] Status Reconciliation Contract missing PR description

Lines 511-518 list four files to update when status changes:
1. SUMMARY.md
2. DEFECTS.md
3. plan YAML status
4. SPRINT_REGISTRY.md

Missing: the PR description (the official signoff artifact per Signoff Model line 523). When status flips to COMPLETED in the YAML, the PR description should also reflect that.

---

## CONSOLIDATED FINDINGS BY SEVERITY

### CRITICAL (1)
1. **Section 4.1** — Phase 1 unique index will fail on existing 945 duplicates because they're created BEFORE Phase 5 marks `is_duplicate=true`. Reorder phases.

### BLOCKER (3)
1. **Section 1.1** — Cup count gate is "~2,941" not exact. The user's question is exactly "is this 2,941?" Add programmatic L3 assertion.
2. **Section 1.2** — No L3 scenario for cancellation tombstone surviving duplicate retry.
3. **Section 1.3 / 3.1** — No L3 scenario or programmatic gate verifies the Phase 5 backfill marked the right rows.

### MAJOR (5)
1. **Section 1.4** — False-positive guard does not test NULL-bill multi-terminal case.
2. **Section 1.5** — Webhook future-proofing scenario missing same-id retry path.
3. **Section 2.2** — TEST_DATA_SEEDING_VAGUE: `/frappe-bulk-edits` referenced for Supabase data, but that skill is Frappe-only. Use `scripts/s232_seed_test_orders.py`.
4. **Section 2.3** — Per-scenario preconditions not enumerated; aggregate-only contract insufficient for 10 distinct scenarios.
5. **Section 7.2** — Autonomous Execution Contract does not explicitly forbid `gh pr merge`.
6. **Section 9.2** — Per-phase verifier gates not consistently described as blocking across all phases.

### MINOR (4-ish)
1. **Section 1.6** — Missing dedup + inference combo on aggregator.
2. **Section 2.4** — Teardown ledger format/schema not specified.
3. **Section 5.2** — No explicit "cd into worktree" reminder for mid-plan tasks (CWD reset risk).
4. **Section 6.2** — `evidence_committed` list does not enumerate vendor_outreach, phase_<N>_verifier.txt, timestamp_usage_audit.md, bei_tasks_cup_query_audit.md.
5. **Section 8.3** — Sentry instrumentation note missing for discount_abuse / marketing_giveaways if touched in Phase 5.2.
6. **Section 8.4** — Phase 4 should explicitly note inheritance of Phase 1.6 Sentry scope.
7. **Section 9.3** — Phase 7.1 re-run intent not stated.
8. **Section 10.2** — `git add -f docs/plans/...` shorthand instead of named files.
9. **Section 10.3** — Status Reconciliation Contract missing PR description.

---

## RECOMMENDED PLAN AMENDMENTS BEFORE EXECUTION

The CRITICAL ordering bug (Section 4.1) must be fixed before the agent runs the plan, otherwise Phase 1 deployment will crash and the agent will spend cycles trying to debug a self-inflicted problem. The 3 BLOCKERs around L3 coverage must be added before the agent starts Phase 7, otherwise the user's primary question ("will this resolve all our duplicates issues?") will not be answered with the rigor the plan claims.

The MAJORs and MINORs should be batched into a Phase 0.5 plan-amendment task rather than blocking execution.
