# S232 Cold-Start Self-Containment Audit (S091 / S154)

Plan path: `F:\Dropbox\Projects\BEI-ERP\docs\plans\2026-05-02-sprint-232-pos-ingest-hardening-cup-counting.md`

A cold-start agent reading ONLY this plan must execute every task without guessing. This file lists each gap I found.

Severity legend:
- **BLOCKER** — agent cannot proceed without asking Sam.
- **HIGH** — agent will likely guess wrong and ship a defect.
- **MEDIUM** — recoverable through one extra read.
- **NIT** — small ambiguity, agent will recover.

## Summary of blockers

| # | Severity | Gap |
|--:|----------|-----|
| 1 | **BLOCKER** | Migration file numbering COLLISION — two `003_*.sql` files and two `005_*.sql` files declared. Cold-start agent will overwrite or invent ordering. |
| 2 | **BLOCKER** | Phase 1.5b MUST_MODIFY for `hrms/api/mosaic_webhook.py` requires `bill_number is not None` AND `bill_number is None` — the verifier in line 363 only checks `find_bill_number_twin` and `find_cluster_twin`. The MUST_CONTAIN literal forms in Phase 1.5b are not echoed by the Phase 1 verifier (`scripts/s232_verify_phase1.py`). Cold-start agent may write the dedup using a `match/case` or different conditional and pass the verifier with a missing branch. |
| 3 | **HIGH** | Phase 2.5 says "Add a SQL view `v_pos_cups_sold`" but does NOT say which SQL file the view lives in. No `MUST_MODIFY: scripts/s232_supabase_migrations/...sql` for the view. Cold-start agent cannot tell whether to put it in 003_pos_products.sql, a new file, or in `_supabase_migrations/006_*.sql`. |
| 4 | **HIGH** | The plan repeatedly cites `pos_cups_sold` as already-existing column in line 99 of `hrms/api/sales_dashboard.py` AND introduces `v_pos_cups_sold` as a new view. The `pos_cups_sold` already-existing field comes from a Supabase view (referenced at line 1482: "view's pos_cups_sold already includes all channels") — but the plan never names that pre-existing view nor explains how `v_pos_cups_sold` will replace or coexist with it. Cold-start agent will likely create a duplicate view. |
| 5 | **HIGH** | Phase 6.2/6.3 list `MUST_MODIFY: bei-tasks dashboard component (TBD per audit)` — **NO concrete file path**. Real bei-tasks consumers exist at `app/dashboard/analytics/sales/page.tsx`, `app/dashboard/analytics/sales/store-detail-dialog.tsx`, `app/dashboard/analytics/sales/stores/page.tsx` (8 grep hits in 4 files). Cold-start agent will guess. |
| 6 | **MEDIUM** | Phase 1.5 / 1.5b cite line numbers (`:539`, `:457`) for the upsert hooks. The cited lines are correct as of `production` HEAD today, but the plan does not warn the agent to use a regex anchor (`supabase_upsert(client, "pos_orders"`) since adjacent edits in S232 itself will shift line numbers within the same execution. |
| 7 | **MEDIUM** | Doppler key references missing. `SUPABASE_URL` is hardcoded (default in `scripts/sync_pos_to_supabase.py:38`); `SUPABASE_SERVICE_ROLE_KEY` is fetched via Doppler in `_get_secret`. Plan does not enumerate WHICH Doppler key the migration runner / new dedup helper should use. Audit item #4 in the prompt asks for explicit Doppler key naming — none in the plan. |
| 8 | **MEDIUM** | `scripts/s232_verify_phase1.py` template (lines 343-374) does NOT include the migration files for Task 1.5c (`004_short_order_id.sql`) or Task 1.3 (`003_pos_orders_dedup_fields.sql` is listed, but `webhook_received_at` MUST_CONTAIN is not asserted). Verifier is incomplete vs the task table it audits. |
| 9 | **MEDIUM** | Task 5.2 says "`pos_orders` views and rollups (`v_sync_drift_monitor`, any S171/S189 view)" — uses "any" which is a cold-start ambiguity. The plan should enumerate exactly which views need the `is_duplicate IS NOT TRUE` filter. The S171 protection rule in line 488 says "may add a JOIN/filter, must NOT change its semantics" which conflicts with adding a `WHERE` clause that changes row count. |
| 10 | **MEDIUM** | Phase 0.4 Supabase probe says `psql ... -c "SELECT count(*) FROM pos_orders WHERE location_id = 9999"` — but the plan does NOT specify how to get the psql connection string or what user it should run as. Existing scripts use PostgREST (`SUPABASE_URL/rest/v1/...`) not psql. |
| 11 | **NIT** | Phase 0.5 says "current schema of `pos_orders`" but doesn't say how to capture it (`information_schema.columns` query? `pg_dump --schema-only`? Supabase API?). |
| 12 | **NIT** | The `kept_order_id` literal in MUST_CONTAIN (line 333, 419) appears in different contexts — once as a column definition in DDL, once as Python assignment. Verifier just greps for the bare string so it works, but a stricter checker would flag the ambiguity. |

## Detail by audit item from prompt

### 1. Supabase queries — table/column specificity

| Plan reference | Verdict |
|---|---|
| Phase 1.1 — full DDL provided. | OK |
| Phase 1.2 — full column list provided for `webhook_duplicates`. | OK |
| Phase 1.3 — column types provided. | OK |
| Phase 1.5 — references upsert at `:539` and `webhook_duplicates` table; no SELECT/INSERT SQL spelled out, but task is "wire dedup helper" so the helper file (1.4) defines query shape. | OK |
| Phase 2.1 — full DDL for `pos_products`. | OK |
| Phase 2.2 — `SELECT DISTINCT product_id, item_name, AVG(price) FROM pos_order_items` — but `pos_order_items` actually has column `product_name` (not `item_name`) per `_map_order_items` at `hrms/api/mosaic_webhook.py:441`. **Column name mismatch.** | **HIGH** |
| Phase 2.5 — `SUM(qty) WHERE is_cup_drink = true via JOIN to pos_products` — does NOT specify the JOIN ON clause. `pos_order_items` has `product_id` (line 440), `pos_products` has `product_id PK` (line 384). Implied but not stated. | MEDIUM |
| Phase 3.1 — grep target file list. No SQL. | OK |
| Phase 4.2 — column add. | OK |
| Phase 5.1 — natural-key + timestamp clustering rule references the helper from 1.4. | OK |
| Phase 5.2 — "any S171/S189 view" — **vague**. | **MEDIUM** (item 9 above) |

**Net Supabase verdict:** mostly self-contained, but Phase 2.2's `item_name` vs `product_name` is a HIGH defect. The agent will write a SQL that fails at runtime.

### 2. File paths cited — verification spot-check (12 files)

| Cited path / line | Real state | Verdict |
|---|---|---|
| `hrms/api/mosaic_webhook.py:62` (`receive`) | line 62: `def receive():` decorator at 62 (`@frappe.whitelist`), `def` at 63. **Off by 1.** Function header IS at line 62-63 area. | OK |
| `hrms/api/mosaic_webhook.py:192` (`_handle_order_completed`) | line 192: `def _handle_order_completed(data: dict) -> dict:` ✓ | OK |
| `hrms/api/mosaic_webhook.py:397` (`_map_order_row`) | line 397: `def _map_order_row(order: dict) -> dict:` ✓ | OK |
| `hrms/api/mosaic_webhook.py:431` (`_map_order_items`) | line 431: `def _map_order_items(order: dict) -> list[dict]:` ✓ | OK |
| `hrms/api/mosaic_webhook.py:457` (`_upsert_completed_order`) | line 457: `def _upsert_completed_order(order: dict) -> None:` ✓ | OK |
| `hrms/api/mosaic_webhook.py:405-406` ("already extracts bill_number, receipt_number") | lines 405-406: `"bill_number": order.get("bill_number"), "receipt_number": order.get("receipt_number"),` ✓ | OK |
| `scripts/sync_pos_to_supabase.py:495` (orders upsert) | line 495: actually `supabase_upsert(client, "pos_orders_raw", rows, on_conflict="order_id")` — this is the **raw orders** upsert, not the `pos_orders` upsert. | **HIGH** |
| `scripts/sync_pos_to_supabase.py:539` (orders upsert) | line 539: `supabase_upsert(client, "pos_orders", order_rows, on_conflict="id")` ✓ — this IS the right line | OK |
| `scripts/sync_pos_to_supabase.py:541` (items upsert) | line 541: `upsert_items_batch(client, item_rows)` ✓ | OK |
| `scripts/sync_pos_to_supabase.py:386-387` ("extracts bill_number, receipt_number") | lines 386-387: `"bill_number": order.get("bill_number"), "receipt_number": order.get("receipt_number"),` ✓ | OK |
| `hrms/api/discount_abuse.py:1167` | line 1167: `"select","id,location_id,business_date,bill_number,receipt_number,billed_at,paid_at,..."`  ✓ (reads `bill_number`/`receipt_number`) | OK |
| `hrms/api/discount_abuse.py:1254-1255` | lines 1254-1255: `"bill_number": str(order.get("bill_number") or ""),` ✓ | OK |
| `hrms/api/discount_abuse.py:2213, 2462, 2531` ("reads `pos_original_gross_sales`") | line 2213: `"pos_original_gross_sales": 0.0,` ✓; 2462: `"pos_original_gross_sales": _to_number(daily_row.get("pos_original_gross")),` ✓; 2531: `"pos_original_gross_sales",` ✓ | OK |
| `hrms/api/sales_dashboard.py` (cup query) | `cups_sold` referenced 20 times (lines 99-3642). The `pos_cups_sold` field comes from an external Supabase view referenced in line 1482 docstring. Plan never names that source view. | **HIGH** (item 4 above) |
| `data/POS_Extraction/MOSAIC_WEBHOOK_REGISTRATIONS.csv` | exists, columns: `credential_group,client_id,webhook_id,url,events,registered_at`; all 5 sampled rows are `order.cancelled` ✓ | OK |
| `.claude/rlm_state/pos_audit/*.csv` (webhook_duplicates.csv, webhook_items_parsed.csv, etc) | all referenced files exist | OK |
| `docs/audits/2026-05-02_pos_vs_analytics_forensic_audit.md` | exists | OK |

**Two file-pointer defects:**
- **HIGH:** `scripts/sync_pos_to_supabase.py:495` is described as "orders upsert" in the cold-start reading list (line 185 of plan) but is actually the `pos_orders_raw` upsert. Cold-start agent will hook the wrong line.
- **HIGH:** `pos_cups_sold` field origin (an upstream Supabase view) is never named in the plan.

### 3. New file naming-collision check

| New path | Already exists? | Verdict |
|---|---|---|
| `scripts/s232_supabase_migrations/001_bill_number_unique_index.sql` | NO | OK |
| `scripts/s232_supabase_migrations/002_webhook_duplicates.sql` | NO | OK |
| `scripts/s232_supabase_migrations/003_pos_orders_dedup_fields.sql` | NO | **NUMBER COLLISION with 003_pos_products.sql** below |
| `scripts/s232_supabase_migrations/003_pos_products.sql` | NO | **NUMBER COLLISION with 003_pos_orders_dedup_fields.sql above** |
| `scripts/s232_supabase_migrations/004_short_order_id.sql` | NO | OK |
| `scripts/s232_supabase_migrations/005_pos_order_payments_inferred.sql` | NO | **NUMBER COLLISION with 005_views_filter_dupes.sql** |
| `scripts/s232_supabase_migrations/005_views_filter_dupes.sql` | NO | **NUMBER COLLISION with 005_pos_order_payments_inferred.sql** |
| `hrms/utils/pos_dedup.py` | NO | OK |
| `scripts/s232_seed_pos_products.py` | NO | OK |
| `scripts/s232_apply_product_classification.py` | NO | OK |
| `scripts/s232_backfill_dupes.py` | NO | OK |
| `scripts/s232_recount_cups.py` | NO | OK |
| `scripts/s232_count_dupes.py` | NO | OK |
| `scripts/s232_replay_webhook.py` | NO | OK |
| `scripts/s232_replay_poll.py` | NO | OK |
| `scripts/s232_seed_test_orders.py` | NO | OK |
| `scripts/s232_teardown.py` | NO | OK |
| `scripts/s232_verify_phase{0..6}.py` | NO | OK |
| `scripts/s232_verify_all_phases.py` | NO | OK |
| `data/POS_Extraction/POS_PRODUCT_CLASSIFICATION.csv` | NO | OK |
| `tests/api/test_mosaic_webhook_timestamps.py` | NO (`tests/api/` may not exist either — verify pre-execute) | NIT |

**BLOCKER:** Migration sequence numbers `003` and `005` are each used twice. A cold-start agent applying these in order will not know which goes first; if applied in alphabetical order, the `pos_products` migration runs before its analytics view dependency is in place. Sam needs to fix the sequence to:
- 003_pos_orders_dedup_fields.sql
- 004_pos_products.sql
- 005_short_order_id.sql
- 006_pos_order_payments_inferred.sql
- 007_views_filter_dupes.sql

(or similar — the point is uniqueness.)

### 4. External APIs / credentials

The plan references:
- `SUPABASE_URL` — hardcoded in `scripts/sync_pos_to_supabase.py:38` (default), env-var override allowed.
- `SUPABASE_SERVICE_ROLE_KEY` — fetched via Doppler at line 755 (`SUPABASE_KEY = _get_secret("SUPABASE_SERVICE_ROLE_KEY")`).
- Mosaic OAuth — uses `data/POS_Extraction/MOSAIC_POS_API_KEYS.csv` (existing pattern in `_find_credential` at `hrms/api/mosaic_webhook.py:495`).

**Plan does NOT explicitly tell a cold-start agent which Doppler project to use.** From `.claude/CLAUDE.md` we know it's `bei-erp` dev, but the plan should state this. The agent will probably get it right by reading `sync_pos_to_supabase.py` but it's an unnecessary jump.

**Verdict: MEDIUM gap (item 7).**

### 5. Already-done vs pending

The plan correctly states this is a fresh sprint with `status: PLANNED` (line 6) and `completed_date: null` (line 7). No phase says "FINISHED". OK.

### 6. Branch state

- Local: `git rev-parse --abbrev-ref HEAD` returns `production` (clean default branch).
- `git branch -a --list '*s232*'` returns NOTHING — branch does not exist locally.
- `git ls-remote --heads origin s232-pos-ingest-hardening-cup-counting` returns NOTHING — branch does not exist on origin yet.

**Verdict: OK.** Phase 0.1 will create the branch off `origin/production` cleanly. No prior work to inherit.

## Total cold-start blockers: **2 BLOCKERs, 5 HIGHs**

The 2 BLOCKERs (migration file numbering collision; Phase 2.2 column-name mismatch `item_name` vs `product_name`) prevent autonomous execution; the 5 HIGHs will likely produce a working-but-wrong sprint result if not resolved before execution.
