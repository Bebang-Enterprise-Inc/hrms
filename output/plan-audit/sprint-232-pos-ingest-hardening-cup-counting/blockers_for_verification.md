# S232 Plan Audit — Consolidated Blockers (For Verification)

**Audit run:** 2026-05-02
**Plan:** `docs/plans/2026-05-02-sprint-232-pos-ingest-hardening-cup-counting.md`
**Domain agents:** 5 (deployment-qa, frappe-backend, system-arch, cold-start+zero-skip, frontend+design+team)
**User question:** "will this resolve all our duplicate issues?"

**Verdict (pre-fact-check):** NO. The plan's architecture is fundamentally sound (unique partial index on `(location_id, business_date, bill_number)` IS the right answer), but **13 distinct blockers** and **10 high-priority issues** must be fixed before the plan can ship without leaving residual duplicate inflation in production analytics.

---

## CLUSTER A — Dedup itself broken (sprint cannot ship as written)

### BLOCKER A1 — Phase 1 unique index will FAIL because 945 existing duplicates violate it

**Claim:** Phase 1 task 1.1 creates `CREATE UNIQUE INDEX pos_orders_bill_number_natural_key ... WHERE bill_number IS NOT NULL` BEFORE Phase 5 marks the existing 945 duplicates as `is_duplicate=true`. The CREATE INDEX statement will throw `ERROR 23505: duplicate key value violates unique constraint`. Phase 1 cannot complete.

**Evidence:**
- Plan task 1.1 (line ~245 of plan)
- Plan Phase 5 task 5.1 (backfill comes AFTER Phase 1)
- Live Supabase probe `.claude/rlm_state/pos_audit/probe_supabase_dupes.py` confirmed 945 dupe rows exist today
- Confirmed by 2 agents: deployment_qa_findings.md §4.1 [CRITICAL]; system_arch_findings.md BLOCKER 4

**Source agent:** deployment-qa + system-arch (independent confirmation)
**Fix:** Reorder phases — backfill (mark `is_duplicate=true`) MUST run BEFORE the unique index is created. Either move Phase 5.1 into Phase 1 as task 1.0a, OR change the index `WHERE` clause to also exclude `is_duplicate=true` rows.

### BLOCKER A2 — PostgREST `on_conflict=id` upsert will throw 409 on bill_number-unique-index violation, and `supabase_upsert` doesn't handle 409

**Claim:** The poll script's `supabase_upsert(client, "pos_orders", order_rows, on_conflict="id")` at `scripts/sync_pos_to_supabase.py:539` will throw HTTP 409 (unique violation) when a new row's `bill_number` collides with an existing row's `bill_number` (different `id`). The `supabase_upsert` helper raises on non-2xx and re-tries up to MAX_RETRIES — meaning the entire batch fails repeatedly until the duplicate is removed.

**Evidence:**
- `scripts/sync_pos_to_supabase.py` `supabase_upsert` definition (frappe_backend_findings.md Q1)
- The plan does NOT specify what `on_conflict` clause to use after the new index ships

**Source agent:** frappe-backend Q1 [CRITICAL]; system-arch MEDIUM 3
**Fix:** The plan must specify either: (a) catch the 409 status code in the upsert helper and route the rejected rows to `webhook_duplicates`, OR (b) change `on_conflict` to use the natural key index, OR (c) split the batch on first conflict and continue. Choose one; document it.

### BLOCKER A3 — Webhook handler `_upsert_completed_order` bypasses the dedup helper

**Claim:** Phase 1 task 1.5b says "wire same dedup into `_upsert_completed_order`" but the actual implementation in `hrms/api/mosaic_webhook.py:457-490` uses a direct REST insert path. The plan's MUST_CONTAIN assertions don't cover the actual code path that runs in production.

**Evidence:**
- `hrms/api/mosaic_webhook.py:457-490` — direct REST insert, doesn't go through poll-script's `supabase_upsert` helper
- Plan task 1.5b assumes the helper-call pattern works the same in both paths

**Source agent:** system_arch_findings.md BLOCKER 1
**Fix:** Add a task that explicitly modifies the webhook's REST insert path to call `find_bill_number_twin` BEFORE the POST to `/rest/v1/pos_orders`.

### BLOCKER A4 — Migration filename numbering collision (003_ and 005_ each reused)

**Claim:** Across phases the plan declares migrations:
- Phase 1.3 → `003_pos_orders_dedup_fields.sql`
- Phase 2.1 → `003_pos_products.sql` (collides)
- Phase 4.2 → `005_pos_order_payments_inferred.sql`
- Phase 5.2 → `005_views_filter_dupes.sql` (collides)

Some migration runners apply files in alphabetical order; collisions silently corrupt migration state.

**Evidence:** Confirmed by 3 agents: cold_start_findings.md §3, frappe_backend_findings.md Additional Finding A, frontend_design_team_findings.md Finding 14

**Source agent:** cold-start + frappe-backend + frontend (triple confirmation, very high confidence)
**Fix:** Renumber all migrations in monotonic order:
- 001 → bill_number unique index (Phase 1.1)
- 002 → webhook_duplicates table (Phase 1.2)
- 003 → pos_orders dedup fields (Phase 1.3)
- 004 → short_order_id column (Phase 1.5c)
- 005 → pos_products table (Phase 2.1)
- 006 → pos_order_payments inferred column (Phase 4.2)
- 007 → views_filter_dupes (Phase 5.2)

### BLOCKER A5 — Phase 2.2 SQL uses wrong column name (`item_name` vs actual `product_name`)

**Claim:** Phase 2.2 task 2.2 says: "SELECT DISTINCT product_id, item_name, AVG(price) FROM pos_order_items". But the actual `pos_order_items` schema uses `name` (or `product_name`), not `item_name`. The seed script will throw `ERROR: column "item_name" does not exist`.

**Evidence:**
- `scripts/sync_pos_to_supabase.py` `map_order_items()` writes `name`, not `item_name`
- Cold-start agent verified column names in actual schema

**Source agent:** cold_start_findings.md BLOCKER 2
**Fix:** Change Phase 2.2 SQL to use the correct column name. Cross-check by reading `scripts/sync_pos_to_supabase.py:438-456` (`map_order_items`) and matching the field mapping.

---

## CLUSTER B — Analytics drift persists even after dedup ships (Sales Dashboard overage NOT resolved)

### BLOCKER B1 — `discount_abuse.py:1175` and `marketing_giveaways.py:1009` query `pos_orders` directly via PostgREST, NOT through views

**Claim:** Phase 5.2 only filters Supabase VIEWS (`v_sync_drift_monitor`, etc.) with `WHERE is_duplicate IS NOT TRUE`. But `discount_abuse.py:1175` and `marketing_giveaways.py:1009` use `_supabase_get_all("pos_orders", params)` — they read the BASE TABLE directly. These queries will silently double-count duplicate-flagged rows.

**Evidence:**
- `hrms/api/discount_abuse.py:1175`: `return _supabase_get_all("pos_orders", params)`
- `hrms/api/marketing_giveaways.py:1009-1015`: similar direct query
- Plan Phase 5.2 only mentions views

**Source agent:** frappe_backend_findings.md Q9 [CRITICAL]
**Fix:** Add an explicit task to either (a) modify these direct queries to add `is_duplicate=is.false` filter, OR (b) replace the direct queries with view-backed equivalents.

### BLOCKER B2 — At least 10 other Supabase analytics views read non-filtered `pos_orders`

**Claim:** Phase 5.2 mentions only `v_sync_drift_monitor`, but a comprehensive search would identify ~10 other views (S171/S189-era) that also read `pos_orders` and need the same filter.

**Evidence:** system_arch_findings.md BLOCKER 5 — agent identified at least 10 candidate views
**Source agent:** system-arch BLOCKER 5
**Fix:** Phase 5.2 must produce an exhaustive view audit (`output/s232/verification/views_using_pos_orders.md`) BEFORE writing migration 005, and the migration must cover EVERY view that reads `pos_orders` without already filtering on `is_duplicate`.

### BLOCKER B3 — `pos_orders_raw` table is uncovered

**Claim:** The poll script writes BOTH to `pos_orders_raw` (raw dump, on_conflict=id at line 495) AND `pos_orders` (cleaned). The plan only addresses `pos_orders`. `pos_orders_raw` will continue accumulating duplicates indefinitely with no cleanup path.

**Evidence:** system_arch_findings.md BLOCKER 2; `scripts/sync_pos_to_supabase.py:495-498`

**Source agent:** system-arch BLOCKER 2
**Fix:** Decide explicitly: (a) add the same dedup logic + unique index to `pos_orders_raw`, OR (b) document that `pos_orders_raw` is intentionally raw (no dedup, kept for forensics) and ensure no analytics consume it. The plan currently ignores it.

### BLOCKER B4 — `pos_order_items` orphan rows accumulate (6× line items per duplicate cluster)

**Claim:** When 6 duplicate parent rows land in `pos_orders`, they each insert their own line items into `pos_order_items` (unique on `(order_id, product_id, line_number)`). Even if the plan rejects 5 of 6 parents going forward, the 6× items already in the database remain. Cup count + revenue queries will still see all 6× items unless the items are also tombstoned.

**Evidence:**
- `scripts/sync_pos_to_supabase.py:541` — `pos_order_items` upsert; PK doesn't reference `pos_orders.is_duplicate`
- Confirmed by 2 agents: frappe_backend Q3 [CRITICAL], system_arch BLOCKER 3

**Source agent:** frappe-backend + system-arch (double confirmation)
**Fix:** Phase 5 must include a task that DELETEs (or marks `is_duplicate=true` on) all `pos_order_items` rows where `order_id IN (SELECT id FROM pos_orders WHERE is_duplicate=true)`. Same for `pos_order_payments`.

---

## CLUSTER C — Verification gaps (no proof the fix worked)

### BLOCKER C1 — Phases 2-6 lack verifier code templates

**Claim:** Only Phase 1 includes a full Python verifier script template (line ~270 of plan). Phases 2-6 say "Phase N verifier" without showing the script. Per S154 Machine-Verifiable Phase Gate Audit Rule, prose phase checklists have a 100% lie rate. Without code templates, Phase 2-6 verifiers can be `print("PASS")` and the agent moves on.

**Evidence:** zero_skip_findings.md §10 — only Phase 1 has the template

**Source agent:** zero-skip BLOCKER
**Fix:** Either (a) add full Python verifier templates for Phases 2-6 inline, OR (b) write a single `scripts/s232_verify_phase_N.py` template the agent extends per-phase, with mandatory `subprocess.check_output(["git","diff","--name-only"])` + `MUST_CONTAIN` assertion patterns.

### BLOCKER C2 — L3 does not programmatically assert cup count = 2,941

**Claim:** L3 scenario "mixed-cart" verifies the per-order cup count is 1, but no scenario asserts the AGGREGATE recount equals 2,941 (the true cup count from the audit) for the historical 7-day window. The user explicitly asked for this number.

**Evidence:** deployment_qa_findings.md §1.1 [BLOCKER]

**Source agent:** deployment-qa
**Fix:** Add an L3 scenario "verify-cup-recount-2941" that runs the recount script on the audit's 7-day window at Araneta Gateway and asserts `total_cups == 2941`. Make it FAIL the sprint if the assertion drifts.

### BLOCKER C3 — No L3 scenario for cancellation tombstone interaction with duplicate retry

**Claim:** The user's audit shows S169 tombstone path is active (12 webhook registrations). If a cancelled order is later re-fired with a new `id` but same `bill_number`, does the tombstone survive the dedup logic? The plan adds NO L3 scenario for this.

**Evidence:** deployment_qa_findings.md §1.2 [BLOCKER]

**Source agent:** deployment-qa
**Fix:** Add L3 scenario: insert a `pos_orders` row with `cancelled_at` set, then replay a webhook/poll with the same `(location_id, business_date, bill_number)` and a new `id`. Assert: the cancellation timestamp is preserved, the new payload goes to `webhook_duplicates`, and analytics correctly show the order as cancelled.

### BLOCKER C4 — No L3 scenario verifies Phase 5 backfill correctness

**Claim:** Phase 5 mutates 945 rows in production. There is NO L3 scenario that verifies the backfill ran correctly. The plan's verifier checks file existence, not row counts.

**Evidence:** deployment_qa_findings.md §3.1 [BLOCKER]

**Source agent:** deployment-qa
**Fix:** Add an L3 task that runs `SELECT COUNT(*) FROM pos_orders WHERE is_duplicate=true GROUP BY business_date` BEFORE and AFTER backfill, and asserts the delta matches the expected dupe count from `output/s232/verification/dedup_collisions_before.csv`.

---

## HIGH-PRIORITY (not blockers, but should be fixed before execution)

| # | Issue | Source | Quick fix |
|--:|-------|--------|-----------|
| H1 | Phase 1 budget understated: declared 12, sums to 15 (after adding 1.5b and 1.5c) | frontend Finding 9 | Update Phase 1 budget line to 15; total becomes 61 (still under 80) |
| H2 | Anti-rewind misstates S197 cron cadence as 5-min when actual is `*/10` | frontend Finding 12 | Update protected-surface table to say "10-min poll cadence (S197 actual cron `*/10 2-16 * * *`)" |
| H3 | Anti-rewind references `webhook_review_queue` as a new surface, but no phase creates it | frontend Finding 15 | Remove the row OR add the table to Phase 1 if intended |
| H4 | `webhook_duplicates` should be renamed `pos_duplicates` (99.95% poll-source) | frontend F7 + system-arch HIGH 3 | Rename in all migration SQL + plan body |
| H5 | Multi-terminal `bill_number` scope unconfirmed; could over-deduplicate at multi-terminal stores | system-arch HIGH 1 | Add Phase 7.4a task: query Mosaic at SM Megamall (multi-terminal) for any bill_number collision across orders. Pause the unique index ship if collision found. |
| H6 | Race condition across 12 parallel cred workers writing to pos_orders | system-arch HIGH 2 | Document that the unique index handles cross-worker races atomically (already true once index is in place); add an integration test |
| H7 | Backfill kept-row tie-breaker rule ambiguous ("earliest known timestamp") | frappe-backend Q5 | Specify: `kept_order_id = MIN(id)` per natural-key tuple, deterministic across re-runs |
| H8 | `webhook_received_at` NULL on 138K historical poll rows; cluster-window fallback can't function for them | frappe-backend C | Backfill `webhook_received_at = paid_at` (or equivalent) during Phase 5 for historical rows |
| H9 | Phase 6.3 metric-change badge target file is "TBD per audit" | frontend Finding 2 | Phase 6.1 audit must produce an exact file path; Phase 6.3 task gets a hard MUST_MODIFY |
| H10 | `/frappe-bulk-edits` is the wrong mechanism for Supabase data | deployment 2.2 | Replace `/frappe-bulk-edits` references with direct SQL via `psql` / management API; or document that `/frappe-bulk-edits` only applies to the (small) Frappe-side test data |

---

## MEDIUM / LOW (informational; do not block execution)

- L3 doesn't include Phase 3 timestamp-test scenario (frontend F17 — MED)
- `infer_payment_type` placement: pos_dedup.py vs pos_inference.py (frontend F6 — MED)
- Empty/error/loading states for cup tile (frontend F4 — MED)
- DM-3 EWT/VAT note (LOW)
- Status reconciliation contract minor gaps (LOW)
- Pre-existing tech debt: `_resolve_channel` duplicated between webhook + poll paths (frappe-backend F — INFO)
- Synthetic store ID 9999 already mitigated by Phase 0.4 HARD BLOCKER (frappe-backend E — WARN, mitigated)

---

## Cross-agent confirmation matrix

| Blocker | Deployment | Frappe Backend | System Arch | Cold-Start | Frontend |
|---------|:----------:|:--------------:|:-----------:|:----------:|:--------:|
| A1 (index ordering) | ✅ CRITICAL | — | ✅ BLOCKER | — | — |
| A2 (PostgREST 409) | — | ✅ CRITICAL | ✅ MEDIUM | — | — |
| A3 (webhook bypass) | — | — | ✅ BLOCKER | — | — |
| A4 (filename collision) | — | ✅ CRITICAL | — | ✅ BLOCKER | ✅ BLOCKER |
| A5 (item_name col) | — | — | — | ✅ BLOCKER | — |
| B1 (direct queries) | — | ✅ CRITICAL | — | — | — |
| B2 (10 views) | — | — | ✅ BLOCKER | — | — |
| B3 (pos_orders_raw) | — | — | ✅ BLOCKER | — | — |
| B4 (item orphans) | — | ✅ CRITICAL | ✅ BLOCKER | — | — |
| C1 (verifier templates) | — | — | — | ✅ BLOCKER | — |
| C2 (cup count assert) | ✅ BLOCKER | — | — | — | — |
| C3 (cancel + retry) | ✅ BLOCKER | — | — | — | — |
| C4 (backfill L3) | ✅ BLOCKER | — | — | — | — |

The 4 dual/triple-confirmed blockers (A1, A2, A4, B4) are the highest-confidence items.

## Final answer to user's question

**"Will this resolve all our duplicate issues?"** Without the 13 fixes above: NO. With them: YES, with one caveat — H5 (multi-terminal `bill_number` scope) must be confirmed at SM Megamall before the unique index ships, otherwise dedup may over-match at multi-terminal stores.
