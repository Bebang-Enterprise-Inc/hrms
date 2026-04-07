---
canonical_sprint_id: S169
display: Sprint 169
status: PLANNED
branch: s169-mosaic-order-lifecycle-tombstone-webhook
lane: single
created_date: 2026-04-07
completed_date:
deployed_at:
backend_pr:
frontend_pr:
l3_result:
execution_summary:
depends_on: S165 (merged) — this sprint replaces S165's "extra" branch handling with a proper tombstone pattern
---

# S169 — Mosaic Order Lifecycle CDC via Webhook + Tombstone Pattern

**Goal:** Eliminate phantom-void data drift in `pos_orders` by subscribing to Mosaic's `order.cancelled` webhook, storing the order lifecycle (`cancelled_at`, `cancellation_reason`, `order_status`, `completed_at`) that Mosaic already provides but we currently discard, filtering every downstream revenue view on `cancelled_at IS NULL`, and upgrading the S165 nightly verify script's `extra` branch to tombstone-not-delete. Preserves full audit history, closes the Apr 4 SM Marikina incident (₱2,052 phantom gross, 3 phantom rows) as the first real test of the pattern.

**Origin:** S165's nightly verification correctly flagged a real data drift on 2026-04-07 at 00:47 PHT: `SM Marikina 2026-04-04: Mosaic=308, Supabase=311, status=extra`. Diagnosis showed Supabase had 4 rows for `bill_number=43701` (Mosaic IDs 49575307, 49575308, 49575310, 49575311) — all PAID, all ₱684, all timestamped 06:35:13 — while Mosaic only has one of them (49575311) via the list endpoint, and the other 3 return clean HTTP 404 on direct-ID lookup. The cashier rang up the bill, voided, retried, voided, retried, voided, finally succeeded on the 4th attempt (receipt 33469) — all in 31 seconds. Our sync captured all 4 as PAID during an early window, then Mosaic's backend removed the voided records from the list API, leaving Supabase with 3 stranded phantom rows.

**Root cause:** The `sync_pos_to_supabase.py` sync is upsert-only — it never deletes rows that disappear from Mosaic — AND `map_order()` at line 401 hardcodes `payment_status` to `'PAID'` if the field is missing from the response, losing all state lineage. Meanwhile, Mosaic's API already returns `cancelled_at`, `cancellation_reason`, `order_status`, and `completed_at` on every order, AND supports an `order.cancelled` webhook — we just never wired either up.

---

## Design Rationale (For Cold-Start Agents)

### Why this exists

The S165 Apr 4 SM Marikina incident is one instance across **1,665 store-days of historical data since 2026-03-01** (45 stores × ~37 days). A full scan confirmed this is the only phantom-void group in that window. Financial impact: ₱2,052 overstated gross / ₱1,710 overstated net / 3 phantom order rows.

But the lack of lifecycle tracking is systemic:
- Every row in `pos_orders` has `payment_status = 'PAID'` because `map_order()` defaults to `'PAID'` when the field is absent. We haven't been reading the real Mosaic `payment_status` field at all.
- `cancelled_at`, `cancellation_reason`, `order_status`, `completed_at` exist on every Mosaic order response but are silently discarded by `map_order()`.
- No webhook subscription exists for `order.cancelled`, even though Mosaic's `POST /api/v1/webhooks` endpoint is already working and registration is straightforward.

So the next phantom-void event in any store — even a small one — will silently overstate that store's revenue until the nightly verify script catches it, AND the verify script currently has no self-heal path for `extra` status. The incident-counter will grow over time.

### Why this architecture

**Empirically tested alternatives and why they were rejected:**

1. **"Include cancelled orders" filter on the list endpoint** — **REJECTED, doesn't exist.** Probed 10 different parameter forms (`filter[include_cancelled]=true`, `filter[status]=all`, `filter[state]=cancelled`, `filter[cancelled]=true`, etc.) on 2026-04-07. All 10 returned the same `meta.total=308`. Mosaic's doc explicitly says "Retrieve a list of *completed* orders" — the filter is hard-coded server-side. No undocumented bypass exists.

2. **Direct-ID lookup for cancelled orders** — **REJECTED, returns 404.** Direct `GET /api/v1/orders/{id}` on IDs 49575307/308/310 returns clean HTTP 404 (my earlier 500s were transient). Once cancelled, Mosaic surfaces the order nowhere in REST.

3. **DELETE-on-poll (my initial wrong recommendation)** — **REJECTED.** Gives the poller delete authority (expands blast radius), loses audit history, 24h latency, contradicts how every serious CDC pipeline (Stripe, Salesforce, Shopify, Square, Toast, Clover) handles source deletions. Tombstones-not-deletes is the industry standard.

4. **Full-refresh MERGE window (nightly rebuild last 7 days from scratch)** — **REJECTED.** Expensive (10K+ orders/day × 7 days × 45 stores × 12 credential groups = crosses Mosaic's rate limits every night), obliterates any downstream Supabase-side annotations, and still needs a "deleted" marker for reports to exclude the removed rows.

5. **Webhook subscription for `order.cancelled` + tombstone pattern** — **CHOSEN.** Mosaic already emits `order.cancelled` (confirmed in `docs/api/MOSAIC_API.md` line 396). Our `map_order` already has the schema to read `cancelled_at` from the live API — we just aren't doing it. Webhooks are near-real-time (seconds) vs polling's 24h. Zero delete authority anywhere in the pipeline. Full audit history preserved. SCD Type 2 equivalent for POS orders.

### Key trade-off decisions

1. **Tombstone via column (`cancelled_at`) vs separate `pos_orders_tombstones` table** — Chose **column** because (a) every revenue query already joins on `pos_orders`, adding a column is a one-line `WHERE cancelled_at IS NULL` filter per view, (b) a separate table would require LEFT JOIN EXCLUDE on every query, which is error-prone and slower, (c) matches Mosaic's own schema where `cancelled_at` lives on the order record.

2. **Webhook as primary + verify script as safety net vs webhook only** — Chose **both**. Webhooks are near-real-time but can be missed (network blip, our endpoint down, Mosaic misfire). The S165 verify script stays in place as a nightly reconciler; its `extra` branch is upgraded to tombstone the difference rather than delete. Belt-and-suspenders.

3. **`cancellation_reason` as free text vs enum** — Chose **text** because (a) Mosaic returns free text (we confirmed the schema), (b) we want to preserve the cashier's reason verbatim for audit, (c) BI queries can `GROUP BY` on common prefixes.

4. **Backfill window: 7 days vs 30 days vs "from go-live" (2025-06-27)** — Chose **30 days**. 7 days misses the SM Marikina case (Apr 4, 3 days back at time of planning but could drift). Full go-live backfill is wasteful — older data is already closed and reconciled against P&L reports. 30 days covers the current quarter close window and all in-flight reconciliations without crossing Mosaic's rate-limit budget during off-hours.

5. **Mosaic webhook registration: 12 credential groups or 1 umbrella** — Chose **12 separate registrations** because each credential group authenticates independently. One POST per group pointing at the same endpoint URL. Our webhook handler uses the credential's signature (if Mosaic signs) or the order's `location_id` to identify which group sent the event.

6. **Webhook endpoint hosted where** — Chose **Frappe backend at `hrms/api/mosaic_webhook.py`** because (a) `hq.bebang.ph` is already exposed publicly with TLS, (b) Frappe's `@frappe.whitelist(allow_guest=True)` handles unauthenticated webhooks, (c) it has direct Supabase PG credentials via bench config, (d) no new infrastructure. Rejected alternatives: bei-tasks Vercel serverless (unnecessary cold starts), a new Cloud Function (needs deployment pipeline), blip-sentinel EC2 (unrelated concern).

7. **Authentication of inbound webhook** — Chose **HMAC signature verification if Mosaic supports it, else IP allowlist + payload-ID-lookup validation**. Need to confirm during Phase 0 probe whether Mosaic signs webhooks. If not signed, the handler must do a `GET /api/v1/orders/{id}` round-trip to Mosaic to confirm the order exists before trusting the event — which defeats the near-real-time benefit but is safer. Phase 0 T0.5 resolves this.

8. **Retroactive payment_status fix for existing rows** — Chose **leave existing rows alone**. The hardcoded `'PAID'` default is baked into the 10M+ historical rows. Retroactively resyncing every row to get the real field would cross Mosaic's rate limits and gain little (reporting is already using PAID-filtered queries because that's all we had). Instead: fix `map_order()` going forward, and the Phase 5 backfill for the last 30 days gets the real values via a fresh resync of those rows only.

### Known limitations

- **`fetch_all_orders()` at `scripts/sync_pos_to_supabase.py:354`** — does not paginate through cancelled orders (Mosaic filters them out). Only `cancelled_at` populated via webhook or via direct-ID lookup on known IDs.
- **Webhook replay / deduplication** — webhooks can fire multiple times for the same event. The handler MUST be idempotent (upsert on `id`, only updates `cancelled_at` if currently NULL to avoid overwriting later manual reconciliation annotations).
- **Webhook delivery guarantees** — Mosaic does not document at-least-once / at-most-once semantics. Assume at-least-once (most webhook systems are). Combined with the nightly verify safety net, occasional dropped webhooks are fully tolerated.
- **`hq.bebang.ph` availability** — if the Frappe backend is down during a cancellation event, the webhook fires and fails. Mosaic's retry behavior is undocumented. Safety net: the nightly verify script catches any missed cancellations.
- **`sync_progress` table unchanged** — this sprint does not touch sync_progress semantics. Hourly sync continues to function exactly as S165 left it.
- **Sales reports from March and earlier** — will continue to include historical phantom rows if any exist. Phase 5 backfill is deliberately bounded to the last 30 days; older data is frozen for finance purposes.

### Source references

- Mosaic API doc: `docs/api/MOSAIC_API.md:56` ("Retrieve a list of *completed* orders"), line 171 (`POST /orders/{id}/cancel`), line 396 (`order.cancelled` event)
- Full Mosaic API doc: `F:\Dropbox\Projects\Dice-Roll-Game-Digital\docs\api\MOSAIC_API.md`
- Sync script: `scripts/sync_pos_to_supabase.py` — `map_order()` at line 379, `payment_status` hardcode at line 401, `map_order_items()` at line 434, `map_order_payments()` at line 463, `fetch_all_orders()` at line 354, `fetch_orders_page()` at line 310
- Verify script (S165): `scripts/verify_mosaic_pos_sync.py` — `_process_group()` `extra` branch, `supabase_count()` at the HW1/MW5 block
- Credential CSV: `data/POS_Extraction/MOSAIC_POS_API_KEYS.csv` (46 rows, 45 stores, 12 credential groups)
- Existing webhook registrations (demo/test, not ours): 3 registered pointing at `requestcatcher.com` URLs — confirmed via live `GET /api/v1/webhooks` probe on 2026-04-07
- S165 plan (predecessor): `docs/plans/2026-04-06-sprint-165-mosaic-sync-verification.md`
- S165 closeout PR: #466, #470, #472
- `sync_verification` table schema: `data/supabase/migrations/2026-04-06-create-sync-verification.sql` (6 status values: `ok`, `missing`, `extra`, `healed`, `unresolved`, `api_error` — this sprint adds `extras_tombstoned`)
- Chat Blip notifications space: `spaces/AAQABiNmpBg` (per Sam directive 2026-04-07 — NO notifications anywhere else)
- Pre-commit guard (S165 fix): `scripts/guards/check_chat_space_literals.py`
- pos_orders schema: 23 columns, indexes on `(location_id, business_date)`, `(channel)`, `(service_channel_id)`, `(payment_status)` — verified via `information_schema.columns` on 2026-04-07
- pos_orders downstream views (6 MVs + 6 views — ALL must be updated in Phase 4):
  - `public.daily_revenue` (MV)
  - `public.discount_summary` (MV)
  - `public.payment_reconciliation` (MV)
  - `public.sales_dashboard_daily_store_metrics` (MV) — the hourly-refreshed dashboard MV
  - `public.store_daily_baselines` (MV) — feeds anomaly detection
  - `public.store_daily_closing` (MV)
  - `public.v_all_channel_daily` (view)
  - `public.v_discount_identity_order_usage` (view)
  - `public.v_monthly_store_summary` (view)
  - `public.v_ops_weekly` (view)
  - `public.v_orders` (view)
  - `public.v_system_daily_totals` (view)
- Apr 4 SM Marikina incident evidence:
  - Alert: `spaces/AAQABiNmpBg` message `2026-04-07T02:47:12.338399Z` — "🔴 Sync Verification... SM Marikina 2026-04-04: Mosaic=308, Supabase=311, status=extra"
  - Phantom IDs: 49575307, 49575308, 49575310 (all PAID, ₱684 gross, billed_at 2026-04-04 06:35:13+00, paid_at 2026-04-04 06:35:44+00)
  - Canonical order: 49575311 (bill 43701, receipt 33469, PAID, ₱684) — the final successful attempt

---

## Ground-Truth Lock

- **evidence_sources:**
  - `scripts/sync_pos_to_supabase.py` → proves reusable helpers + current broken `map_order`
  - `scripts/verify_mosaic_pos_sync.py` → proves current `extra` branch signature
  - `docs/api/MOSAIC_API.md` → proves Mosaic order schema + webhook events
  - `data/POS_Extraction/MOSAIC_POS_API_KEYS.csv` → proves 45 stores × 12 credential groups
  - Supabase `information_schema.columns` query → proves current `pos_orders` has 23 columns (no `cancelled_at`)
  - `pg_matviews` + `pg_views` query → proves 12 downstream objects reference `pos_orders`
- **count_method:**
  - metric: `phantom-void incidents per store-day` and `overstated gross per incident`
  - basis: `(location_id, business_date, bill_number, original_gross_sales, billed_at) GROUP BY HAVING COUNT(*) > 1 in pos_orders`
  - method: direct SQL query (see S165 incident diagnosis in `tmp/s165_phantom_scan.md` — to be created in Phase 0 T0.3)
- **authoritative_sections:** "Files to Create", "Files to Modify", "L3 Workflow Scenarios", "Phases & Tasks", "Verification" are authoritative for execution. Amendment history is traceability only.
- **normalization_required:** Any amendment that changes counts, file paths, DocType/column names, or view lists must update all authoritative sections in the same edit.
- **unresolved_value_policy:** Any uncertain value becomes `[UNVERIFIED — requires resolution]`; no best-guess in operator-facing output.

---

## Phase Budget Contract

| Phase | Description | Units |
|-------|-------------|-------|
| Phase 0 | Pre-flight: schema audit, phantom scan, webhook sign probe, view dependency audit, view filter strategy decision | 6 |
| Phase 1 | Schema migration: `pos_orders` columns + `sync_verification` enum + indexes | 3 |
| Phase 2 | Fix `map_order()` — stop hardcoding PAID, read all lifecycle fields | 4 |
| Phase 3 | Build `hrms/api/mosaic_webhook.py` endpoint + Sentry observability | 6 |
| Phase 4 | Update all 6 MVs + 6 views to filter `WHERE cancelled_at IS NULL` | 10 |
| Phase 5 | Backfill 30-day window via re-sync (fresh values for `payment_status` + all lifecycle fields) | 5 |
| Phase 6 | Upgrade `verify_mosaic_pos_sync.py` `extra` branch to tombstone-not-delete; new `extras_tombstoned` status | 6 |
| Phase 7 | Register webhook on all 12 Mosaic credential groups (one-time operator action) | 3 |
| Phase 8 | L3 verification — Apr 4 SM Marikina incident as first real test | 8 |
| Phase 9 | Closeout: PR, plan+registry update, final Chat announcement | 5 |
| **Total** | | **56** |

Hard limit 15 per phase respected. Total **56** units — well under 80-unit single-session ceiling. No phase exceeds 10 units.

---

## Requirements Regression Checklist

Before writing any code, the executing agent MUST verify every item below:

### Schema migration
- [ ] Does the `pos_orders` migration add exactly these 4 columns: `cancelled_at TIMESTAMPTZ`, `cancellation_reason TEXT`, `order_status TEXT`, `completed_at TIMESTAMPTZ`?
- [ ] Are new columns **nullable** so existing ~10M rows don't fail the migration?
- [ ] Is there a partial index `idx_pos_orders_cancelled_at_not_null ON pos_orders(cancelled_at) WHERE cancelled_at IS NOT NULL` for efficient tombstone queries?
- [ ] Does the `sync_verification` CHECK constraint get a new value `extras_tombstoned` added to the allowed status list (now 7 values: ok, missing, extra, healed, unresolved, api_error, extras_tombstoned)?

### `map_order()` fix
- [ ] Does the fix stop hardcoding `'PAID'` as a fallback? Does it read `order.get("payment_status")` and preserve the real value (raising or logging if absent, NOT defaulting to PAID)?
- [ ] Does the fix populate `cancelled_at`, `cancellation_reason`, `order_status`, `completed_at` from the order object?
- [ ] Does `_resolve_channel()` continue to work unchanged (not accidentally regressed)?
- [ ] **HARD BLOCKER:** Is there a test (or a `tmp/s169_map_order_snapshot_before.json` + `after.json`) showing the exact diff of old vs new `map_order` output on a sample real order? Agent must produce both before modifying production sync.

### Webhook endpoint
- [ ] Is the endpoint at `hrms/api/mosaic_webhook.py` with `@frappe.whitelist(allow_guest=True, methods=["POST"])`?
- [ ] Does the endpoint call `set_backend_observability_context(module="sync_verification", action="mosaic_webhook", mutation_type="update")` as its first meaningful line per DM-7?
- [ ] Does the endpoint verify the webhook signature if Mosaic signs (Phase 0 T0.5 resolves the probe)?
- [ ] If Mosaic does NOT sign, does the endpoint confirm the event by calling `GET /api/v1/orders/{id}` on Mosaic before trusting the payload?
- [ ] Is the UPDATE idempotent (`UPDATE pos_orders SET cancelled_at = ... WHERE id = ? AND cancelled_at IS NULL`)?
- [ ] Does the endpoint log to Sentry on any mutation failure?
- [ ] Does the endpoint return `{"ok": true}` within 2 seconds to avoid webhook retry storms?

### View / MV updates
- [ ] Are ALL 6 MVs updated with `WHERE cancelled_at IS NULL` OR updated to not-reference cancelled rows via equivalent filter?
- [ ] Are ALL 6 regular views updated the same way?
- [ ] Are MVs **dropped and recreated** (CREATE MATERIALIZED VIEW … AS …), since ALTER isn't supported?
- [ ] Is a `REFRESH MATERIALIZED VIEW CONCURRENTLY` pattern preserved so the hourly dashboard refresh doesn't block reads?
- [ ] Does the sales-dashboard view refresh still work (tested by running `scripts/supabase_exec.py "select public.refresh_sales_dashboard_daily_store_metrics();"` post-deploy)?
- [ ] **HARD BLOCKER:** Before any view is dropped, does the plan produce `tmp/s169_view_definitions_before.sql` containing the full current definitions of all 12 objects for rollback? If not, STOP.

### Backfill
- [ ] Is the backfill window exactly `date_from = today - 30 days` to `date_to = yesterday PHT`?
- [ ] Does the backfill re-run `sync_store_day()` for each (store, date) tuple so the new `map_order()` output overwrites existing rows via upsert on `id`?
- [ ] Does the backfill respect the existing REQUEST_INTERVAL rate limiting?

### Verify script upgrade
- [ ] Does the upgraded `extra` branch do all of: (a) pull full Mosaic ID list via `fetch_all_orders()`, (b) set-diff against Supabase IDs, (c) direct-ID 404 confirmation per extra ID, (d) mark `cancelled_at = NOW()` + `cancellation_reason = 'reconciled_from_mosaic_gap'` on confirmed-gone rows, (e) write `status='extras_tombstoned'` to sync_verification?
- [ ] Does it NEVER DELETE pos_orders rows?
- [ ] Does `supabase_count()` query become `SELECT COUNT(*) ... WHERE cancelled_at IS NULL`?
- [ ] Is the pre-commit guard `scripts/guards/check_chat_space_literals.py` still passing after all edits?

### Webhook registration
- [ ] Are all 12 credential groups registered with `POST /api/v1/webhooks` pointing at `https://hq.bebang.ph/api/method/hrms.api.mosaic_webhook.receive`?
- [ ] Are events exactly `["order.cancelled"]` (not subscribing to `order.created` or `order.completed` to avoid duplicating the sync)?
- [ ] Is the registration idempotent (check `GET /api/v1/webhooks` first, skip if already registered)?
- [ ] Are registration IDs recorded in `data/POS_Extraction/MOSAIC_WEBHOOK_REGISTRATIONS.csv` for future audit/unregister?

### Observability
- [ ] Is `SENTRY_DSN` in Doppler `bei-erp/dev`? (Verified 2026-04-07 — yes)
- [ ] Does the webhook endpoint emit a breadcrumb on every successful cancel update with `{order_id, location_id, cancelled_at}`?
- [ ] Is there a dashboard query / SQL view showing count of `cancelled_at IS NOT NULL` per store per day for BI consumption?

### Chat routing
- [ ] Do all notifications in this sprint's code go ONLY to `spaces/AAQABiNmpBg`?
- [ ] Does `scripts/guards/check_chat_space_literals.py` pass against all modified files?

---

## Autonomous Execution Contract

- **completion_condition:**
  - `pos_orders` has 4 new nullable columns + partial index
  - `sync_verification.status` allows `extras_tombstoned`
  - `map_order()` reads real `payment_status` + all 4 lifecycle fields, before/after snapshot diff committed to `output/l3/s169/`
  - `hrms/api/mosaic_webhook.py` endpoint exists with Sentry context, signature verify (or round-trip confirm), idempotent UPDATE
  - All 6 MVs + 6 views filter `WHERE cancelled_at IS NULL` (verified via `pg_views` + `pg_matviews` definition re-query)
  - 30-day backfill completed, resulting pos_orders rows show real `payment_status` values (not all `'PAID'`) — sample query proves it
  - Verify script upgraded: `extra` branch tombstones, `extras_tombstoned` status visible in `sync_verification`
  - All 12 credential groups registered with `order.cancelled` webhook, IDs logged in `data/POS_Extraction/MOSAIC_WEBHOOK_REGISTRATIONS.csv`
  - Apr 4 SM Marikina incident tombstoned via the new pipeline (NOT manually): the verify script's next run shows `status='extras_tombstoned'` for that store-day and `supabase_count` filtered on `cancelled_at IS NULL` now equals `mosaic_total`
  - L3 evidence files present in `output/l3/s169/` AND committed via `git add -f`
  - PR created, plan YAML updated to `COMPLETED`, registry row updated, both pushed to production
- **stop_only_for:**
  - Mosaic API returns unexpected schema (e.g., `cancelled_at` field renamed or missing from the live response)
  - Mosaic's webhook registration endpoint returns a new error (e.g., rate limit on registration)
  - **Phase 0 T0.5 webhook signature probe determines Mosaic does NOT sign webhooks AND does not document a secret-header mechanism** — the plan has a fallback (round-trip confirm) but we must explicitly confirm the fallback works before proceeding
  - Supabase migration SQL rejected by Management API
  - A view's rewritten definition produces different row counts on a sample query (would indicate a SQL logic regression beyond just the cancelled filter)
  - `hq.bebang.ph` is not publicly reachable by Mosaic (firewall, Cloudflare challenge, etc.) — Phase 7 validates this with a test webhook
  - Destructive approval needed (should never happen in this plan)
- **continue_without_pause_through:** audit → execute → PR creation → L3 → closeout
- **blocker_policy:**
  - programmatic → fix and continue
  - Mosaic API error → retry 3x with backoff, then skip with audit log and continue
  - Mosaic webhook registration rate limit → backoff 60s, retry up to 3 times, then skip and continue
  - View rewrite produces incorrect counts → STOP and present fix options
  - `hq.bebang.ph` unreachable from public → STOP and present options (might need Cloudflare allowlist for Mosaic IPs)
- **signoff_authority:** single-owner (Sam)
- **canonical_closeout_artifacts:**
  - `output/l3/s169/form_submissions.json` — CLI invocations + arguments
  - `output/l3/s169/api_mutations.json` — Mosaic webhook registrations + sync_verification writes
  - `output/l3/s169/state_verification.json` — before/after SQL counts for Apr 4 SM Marikina
  - `output/l3/s169/map_order_snapshot_before.json` + `map_order_snapshot_after.json` — prove the payment_status + lifecycle fix works
  - `output/l3/s169/view_definitions_before.sql` + `view_definitions_after.sql` — prove view rewrites
  - `output/l3/s169/webhook_test_payload.json` + `webhook_test_response.json` — prove the endpoint works
  - `output/l3/s169/verify_s169.py` — machine-verifiable phase gate
  - `data/POS_Extraction/MOSAIC_WEBHOOK_REGISTRATIONS.csv` — registered webhook IDs per credential group
  - `docs/plans/2026-04-07-sprint-169-mosaic-order-lifecycle-tombstone-webhook.md` (status → COMPLETED)
  - `docs/plans/SPRINT_REGISTRY.md` (S169 row → COMPLETED with PR reference)

---

## Sentry Observability Instrumentation

Per `.claude/rules/sentry-observability.md` (DM-7):

- **Backend rule (`@frappe.whitelist()` endpoints in `hrms/api/*.py`)**: **APPLICABLE**. The new `hrms/api/mosaic_webhook.py` endpoint MUST call `set_backend_observability_context(module="sync_verification", action="mosaic_webhook_receive", mutation_type="update")` as its first meaningful line.
- **Frontend rule (`bei-tasks/app/api/*/route.ts`)**: NOT applicable. No frontend routes touched.
- **Script-level Sentry**: `scripts/verify_mosaic_pos_sync.py` already has `sentry_sdk.init()` with tags `module=sync_verification, action=verify_mosaic_pos_sync` (from S165). The upgraded `extra` branch inherits this instrumentation.
- **Fail-fast on missing DSN**: the webhook endpoint must `frappe.throw` during init if `SENTRY_DSN` is missing (following the S165 CB5 pattern).

---

## Files to Create

### 1. `data/supabase/migrations/2026-04-07-pos-orders-lifecycle-columns.sql` (NEW)

**MUST_MODIFY:** `data/supabase/migrations/2026-04-07-pos-orders-lifecycle-columns.sql`
**MUST_CONTAIN:** `ALTER TABLE pos_orders ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMPTZ`
**MUST_CONTAIN:** `ADD COLUMN IF NOT EXISTS cancellation_reason TEXT`
**MUST_CONTAIN:** `ADD COLUMN IF NOT EXISTS order_status TEXT`
**MUST_CONTAIN:** `ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ`
**MUST_CONTAIN:** `CREATE INDEX IF NOT EXISTS idx_pos_orders_cancelled_at_not_null`
**MUST_CONTAIN:** `WHERE cancelled_at IS NOT NULL`
**MUST_CONTAIN:** `ALTER TABLE sync_verification DROP CONSTRAINT`
**MUST_CONTAIN:** `extras_tombstoned`

```sql
-- S169 phase 1: lifecycle columns on pos_orders + new sync_verification status
BEGIN;

ALTER TABLE pos_orders
  ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS cancellation_reason TEXT,
  ADD COLUMN IF NOT EXISTS order_status TEXT,
  ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_pos_orders_cancelled_at_not_null
  ON pos_orders(location_id, business_date)
  WHERE cancelled_at IS NOT NULL;

COMMENT ON COLUMN pos_orders.cancelled_at IS
  'Set when Mosaic emits order.cancelled webhook, or when verify_mosaic_pos_sync.py tombstones an extra row. NULL = live order. See S169.';

-- Add extras_tombstoned to the sync_verification CHECK constraint
ALTER TABLE sync_verification DROP CONSTRAINT sync_verification_status_check;
ALTER TABLE sync_verification ADD CONSTRAINT sync_verification_status_check
  CHECK (status IN ('ok', 'missing', 'extra', 'healed', 'unresolved', 'api_error', 'extras_tombstoned'));

COMMIT;
```

### 2. `hrms/api/mosaic_webhook.py` (NEW, ~200 lines)

**MUST_MODIFY:** `hrms/api/mosaic_webhook.py`
**MUST_CONTAIN:** `@frappe.whitelist(allow_guest=True, methods=["POST"])`
**MUST_CONTAIN:** `set_backend_observability_context(`
**MUST_CONTAIN:** `module="sync_verification"`
**MUST_CONTAIN:** `action="mosaic_webhook_receive"`
**MUST_CONTAIN:** `order.cancelled`
**MUST_CONTAIN:** `UPDATE pos_orders SET cancelled_at`
**MUST_CONTAIN:** `WHERE id = ` (parameterized, via frappe.db.sql)
**MUST_CONTAIN:** `cancelled_at IS NULL` (idempotency guard in WHERE clause)

Skeleton (full implementation during execution):

```python
"""Mosaic POS webhook receiver — handles order.cancelled events.

See docs/plans/2026-04-07-sprint-169-mosaic-order-lifecycle-tombstone-webhook.md
"""
import json
from datetime import datetime, timezone

import frappe
from frappe import _

from hrms.utils.sentry import set_backend_observability_context


@frappe.whitelist(allow_guest=True, methods=["POST"])
def receive():
    """Handle inbound Mosaic webhooks (primarily order.cancelled)."""
    set_backend_observability_context(
        module="sync_verification",
        action="mosaic_webhook_receive",
        mutation_type="update",
    )

    payload = frappe.request.get_json(force=True, silent=True) or {}
    event = (payload.get("event") or "").strip()
    data = payload.get("data") or {}

    if event != "order.cancelled":
        # We only subscribe to order.cancelled. Any other event is a mis-registration.
        return {"ok": True, "handled": False, "reason": f"ignored event: {event}"}

    order_id = data.get("id")
    if not order_id:
        return {"ok": False, "reason": "missing order id"}

    # T0.5 decision: if Mosaic signs, verify sig here. Else round-trip confirm.
    # ... (Phase 0 probe determines which path)

    cancelled_at = data.get("cancelled_at") or datetime.now(timezone.utc).isoformat()
    reason = (data.get("cancellation_reason") or "mosaic_webhook")[:500]

    # Connect to Supabase directly (Frappe site does not own pos_orders).
    # Uses the sync service role key from doppler / bench config.
    from hrms.utils.supabase import get_supabase_client  # TODO create this helper in Phase 3

    sb = get_supabase_client()
    # Idempotent: only update if not already tombstoned
    result = sb.execute("""
        UPDATE pos_orders
           SET cancelled_at = %s,
               cancellation_reason = %s
         WHERE id = %s
           AND cancelled_at IS NULL
        RETURNING id, location_id, business_date
    """, (cancelled_at, reason, order_id))

    if not result:
        return {"ok": True, "handled": False, "reason": "already tombstoned or not found", "order_id": order_id}

    row = result[0]
    frappe.logger().info(f"S169 mosaic webhook: tombstoned {order_id} (loc={row['location_id']} date={row['business_date']})")
    return {"ok": True, "handled": True, "order_id": order_id}
```

### 3. `hrms/utils/supabase.py` (NEW — thin Supabase client helper)

Simple wrapper around `psycopg2` or `requests` (PostgREST) that reads the Supabase service role key from bench config and exposes an `execute(sql, params)` method. ~50 lines.

### 4. `data/POS_Extraction/MOSAIC_WEBHOOK_REGISTRATIONS.csv` (NEW)

CSV audit trail of webhook registrations:
```
credential_group,client_id,webhook_id,url,events,registered_at
Araneta Group (3 stores),a080acf5-22e9-4c80-bfb5-14a96147dc70,<returned_id>,https://hq.bebang.ph/api/method/hrms.api.mosaic_webhook.receive,order.cancelled,2026-04-07T...
...12 rows total
```

---

## Files to Modify

### 1. `scripts/sync_pos_to_supabase.py`

**MUST_MODIFY:** `scripts/sync_pos_to_supabase.py`
**MUST_CONTAIN:** `"payment_status": order.get("payment_status"),` (no `.upper()`, no `or 'PAID'` default)
**MUST_CONTAIN:** `"cancelled_at": order.get("cancelled_at"),`
**MUST_CONTAIN:** `"cancellation_reason": order.get("cancellation_reason"),`
**MUST_CONTAIN:** `"order_status": order.get("order_status"),`
**MUST_CONTAIN:** `"completed_at": order.get("completed_at"),`

The fix is in `map_order()` at line 379. Current line 401:
```python
"payment_status": (order.get("payment_status") or "PAID").upper(),
```

Must become:
```python
"payment_status": (order.get("payment_status") or "").upper() or None,
"cancelled_at": order.get("cancelled_at"),
"cancellation_reason": order.get("cancellation_reason"),
"order_status": order.get("order_status"),
"completed_at": order.get("completed_at"),
```

Rationale: (a) don't hardcode PAID (defeat of the whole point), (b) uppercase the real value for consistency, (c) fall through to NULL if genuinely absent (Supabase column is nullable).

**HARD BLOCKER:** Before editing this file, the agent MUST produce `output/l3/s169/map_order_snapshot_before.json` by running `map_order()` on a sample Mosaic order and saving the output. After editing, produce `_after.json` with the same input. Commit both. This is a zero-skip regression check.

### 2. `scripts/verify_mosaic_pos_sync.py`

**MUST_MODIFY:** `scripts/verify_mosaic_pos_sync.py`
**MUST_CONTAIN:** `cancelled_at IS NULL` (in the `supabase_count` SELECT)
**MUST_CONTAIN:** `def tombstone_extras(` (new function)
**MUST_CONTAIN:** `extras_tombstoned`
**MUST_CONTAIN:** `reconciled_from_mosaic_gap`
**MUST_NOT_CONTAIN:** `DELETE FROM pos_orders`

Changes:
1. `supabase_count()` appends `&cancelled_at=is.null` to the PostgREST params
2. `_process_group` `extra` branch calls new `tombstone_extras(client, cred, loc_id, ds, supabase_ids, mosaic_ids)` which:
   - Computes `extras = supabase_ids - mosaic_ids`
   - For each extra ID, does a direct `GET /api/v1/orders/{id}` lookup
   - Confirms 404 (truly gone)
   - Updates `pos_orders SET cancelled_at = NOW(), cancellation_reason = 'reconciled_from_mosaic_gap' WHERE id = ?`
   - Returns the tombstoned count
3. Row status becomes `extras_tombstoned` with `heal_attempted = TRUE`
4. Post-tombstone, re-run `supabase_count()` (now filtered on `cancelled_at IS NULL`) and expect it to equal `mosaic_total`

### 3. Six materialized views (DROP and CREATE in one transaction per MV)

For each MV in `daily_revenue`, `discount_summary`, `payment_reconciliation`, `sales_dashboard_daily_store_metrics`, `store_daily_baselines`, `store_daily_closing`:

1. Save current definition to `tmp/s169_view_definitions_before.sql` (all 6 concatenated)
2. Parse the current `FROM pos_orders` or `JOIN pos_orders` clauses
3. Rewrite with `WHERE cancelled_at IS NULL` added (or appended to existing WHERE via `AND`)
4. In ONE transaction per MV: `BEGIN; DROP MATERIALIZED VIEW; CREATE MATERIALIZED VIEW; COMMIT;`
5. `REFRESH MATERIALIZED VIEW CONCURRENTLY` if the MV has a unique index (check first); else just `REFRESH MATERIALIZED VIEW`
6. Run a sample count query pre/post to verify row delta is within expected range (delta should be 0 for non-SM-Marikina MVs, -3 for ones that include SM Marikina Apr 4)

**Reference data-flow map** (execution agent MUST read to understand dependencies):
- `sales_dashboard_daily_store_metrics` is refreshed by `scripts/supabase_exec.py "select public.refresh_sales_dashboard_daily_store_metrics();"` hourly per S165 (daily-pos-sync.yml line ~148)
- `store_daily_baselines` feeds `scripts/detect_anomalies.py` — its baseline calculation must still work after the filter is added
- `v_orders` is a simple pass-through view; may or may not be used by external consumers — check `pg_depend` during Phase 0 T0.4

**HARD BLOCKER:** DO NOT proceed past Phase 4 without `tmp/s169_view_definitions_before.sql` present in git for rollback.

### 4. Six regular views (same pattern, simpler — just CREATE OR REPLACE)

For each view in `v_all_channel_daily`, `v_discount_identity_order_usage`, `v_monthly_store_summary`, `v_ops_weekly`, `v_orders`, `v_system_daily_totals`:

1. Save definition to `tmp/s169_view_definitions_before.sql`
2. `CREATE OR REPLACE VIEW <name> AS <rewritten query with cancelled_at IS NULL filter>;`
3. Verify with sample count query

### 5. `output/l3/s169/verify_s169.py` (NEW — machine-verifiable phase gate)

Same pattern as S165's `verify_s165.py`. Fails the run if:
- Any of the `MUST_MODIFY` files lack any of the `MUST_CONTAIN` strings
- Any of the `MUST_NOT_CONTAIN` strings appear
- `git diff --name-only origin/production..HEAD` is missing any required file
- The 6 MV definitions in Supabase do not contain `cancelled_at IS NULL`
- The 6 view definitions in Supabase do not contain `cancelled_at IS NULL`

---

## L3 Workflow Scenarios

**Note:** This sprint's "UI" is the nightly verify script, the webhook endpoint, and the SQL views. L3 scenarios test end-to-end on production data, with the Apr 4 SM Marikina incident as the primary test case.

| User | Action | Expected Outcome | Failure Means |
|------|--------|-------------------|---------------|
| Builder | Pre-Phase 2: run `map_order()` on a real Mosaic order JSON fixture, save output to `output/l3/s169/map_order_snapshot_before.json` | JSON file created, shows current output with `payment_status='PAID'` hardcoded | Sync script import broken |
| Builder | Post-Phase 2: re-run same `map_order()` on same fixture, save to `_after.json` | JSON file shows `payment_status` = real value from fixture, plus `cancelled_at`, `order_status`, `completed_at`, `cancellation_reason` keys populated | Fix didn't actually read new fields |
| Builder | Apply Phase 1 migration via Supabase Mgmt API | `SELECT column_name FROM information_schema.columns WHERE table_name='pos_orders' AND column_name IN ('cancelled_at','cancellation_reason','order_status','completed_at')` returns 4 rows | Migration failed |
| Builder | Query `sync_verification` CHECK constraint: `SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname='sync_verification_status_check'` | Output includes `'extras_tombstoned'` | Enum update failed |
| Builder | Deploy webhook endpoint `hrms/api/mosaic_webhook.py` (via Frappe skip_build=false redeploy) | `curl -X POST https://hq.bebang.ph/api/method/hrms.api.mosaic_webhook.receive -H "Content-Type: application/json" -d '{"event":"order.cancelled","data":{"id":99999999}}'` returns `{"ok":true,"handled":false,"reason":"already tombstoned or not found"}` within 2 seconds | Endpoint not deployed or signature verify blocks test |
| Builder | Register webhook on ALL 12 credential groups via `POST /api/v1/webhooks` with events=["order.cancelled"] | `data/POS_Extraction/MOSAIC_WEBHOOK_REGISTRATIONS.csv` has 12 rows. Verify with `GET /api/v1/webhooks` per group — each returns our URL in its list | Registration rate-limited or auth mismatch |
| Builder | Phase 4 view rewrites: for each of the 12 objects, check `pg_views.definition` / `pg_matviews.definition` LIKE '%cancelled_at IS NULL%' | All 12 definitions contain the filter | View rewrite broken |
| Builder | Phase 4 sanity: run `REFRESH MATERIALIZED VIEW sales_dashboard_daily_store_metrics` then check hourly dashboard loads | No SQL errors, dashboard shows non-zero values | View rewrite broke the MV query |
| Builder | Phase 5 backfill: `python scripts/sync_pos_to_supabase.py --from 2026-03-08 --to 2026-04-06 --parallel` | Completes without errors. Post-backfill sample: `SELECT COUNT(DISTINCT payment_status) FROM pos_orders WHERE business_date >= '2026-03-08'` returns >1 (not just 'PAID') | Backfill didn't pick up the new `map_order` |
| Builder | **Apr 4 SM Marikina test — the money shot.** Pre-run sanity: `SELECT COUNT(*) FROM pos_orders WHERE location_id=2317 AND business_date='2026-04-04' AND cancelled_at IS NULL` | Returns 311 (still showing phantoms as live) | Column not populated |
| Builder | Run upgraded verify script: `python scripts/verify_mosaic_pos_sync.py --date 2026-04-04 --store 2317 --no-chat` | Logs show `[EXTRA] SM Marikina (2317) ... delta=3` then `[TOMBSTONED] SM Marikina ... 3 phantoms` then final status `extras_tombstoned` | Tombstone path broken |
| Builder | Post-run SQL: `SELECT id, cancelled_at, cancellation_reason FROM pos_orders WHERE id IN (49575307, 49575308, 49575310)` | All 3 rows have `cancelled_at = <recent ts>`, `cancellation_reason = 'reconciled_from_mosaic_gap'` | UPDATE didn't fire |
| Builder | Post-run SQL: `SELECT COUNT(*) FROM pos_orders WHERE location_id=2317 AND business_date='2026-04-04' AND cancelled_at IS NULL` | Returns 308 (matches Mosaic) | Filter on cancelled_at broken in downstream queries |
| Builder | Post-run SQL: `SELECT * FROM sync_verification WHERE location_id=2317 AND business_date='2026-04-04' ORDER BY verified_at DESC LIMIT 1` | Latest row shows `status='extras_tombstoned'`, `heal_attempted=TRUE`, `mosaic_total=308`, `supabase_total=308` | sync_verification write broken |
| Builder | **Webhook live test** (manual cancel for test): create a test order in Mosaic staging (if available) and cancel it. Observe webhook fires. | Sentry breadcrumb shows `module=sync_verification, action=mosaic_webhook_receive`, Supabase row for test order has `cancelled_at` populated within 30s | Mosaic not reaching our endpoint (DNS, firewall, signature, etc.) |
| Builder | Run next-night verify full sweep: `python scripts/verify_mosaic_pos_sync.py --days 7 --no-chat` | Zero `extra` rows in the latest state (all previously-extra rows are now tombstoned and filtered out of `supabase_count`). Full run < 90s. | Tombstoned rows still counted as extras |
| Builder | Final gate: `python output/l3/s169/verify_s169.py` | All PASS | Some MUST_CONTAIN / MUST_NOT_CONTAIN / branch-diff check failed |

**L3 Evidence Files Required (committed via `git add -f` before closeout):**
- `output/l3/s169/form_submissions.json` — CLI invocations + arguments
- `output/l3/s169/api_mutations.json` — Mosaic webhook registrations + sync_verification writes + tombstone UPDATEs
- `output/l3/s169/state_verification.json` — before/after SQL counts for Apr 4 SM Marikina AND a random sample store for regression
- `output/l3/s169/map_order_snapshot_before.json` + `map_order_snapshot_after.json`
- `output/l3/s169/view_definitions_before.sql` + `view_definitions_after.sql`
- `output/l3/s169/webhook_test_payload.json` + `webhook_test_response.json`
- `output/l3/s169/verification_run.log` — full stdout of the 7-day run
- `output/l3/s169/verify_s169.py`

---

## Zero-Skip Enforcement

Every task in this plan MUST be implemented. The agent is FORBIDDEN from:

- Skipping a task silently
- Marking partial work as "done"
- Replacing a task with a simpler version without user approval
- Saying "deferred to next sprint"
- Combining tasks and dropping features in the merge
- Implementing the webhook endpoint without the round-trip confirm fallback if Mosaic doesn't sign
- Rewriting fewer than all 12 views
- Skipping the Apr 4 SM Marikina test (it's the whole reason the sprint exists)

**Verification script** (agent MUST write and run this after each phase, fix any FAIL before proceeding):

`output/l3/s169/verify_s169.py`:

```python
#!/usr/bin/env python3
"""S169 machine-verifiable phase gate. Runs from filesystem, not self-report."""
import subprocess, sys, pathlib
REPO = pathlib.Path(__file__).resolve().parents[3]

def check_contains(path, needles, forbidden=()):
    p = REPO / path
    if not p.exists():
        return f"FAIL: {path} does not exist"
    text = p.read_text(encoding='utf-8')
    missing = [n for n in needles if n not in text]
    bad = [n for n in forbidden if n in text]
    if missing:
        return f"FAIL: {path} missing: {missing}"
    if bad:
        return f"FAIL: {path} contains forbidden: {bad}"
    return f"PASS: {path}"

def check_diff_includes(branch, files):
    out = subprocess.run(["git", "diff", "--name-only", f"origin/production..{branch}"],
                         capture_output=True, text=True, cwd=REPO)
    diff = out.stdout.split()
    missing = [f for f in files if f not in diff]
    return f"FAIL: branch diff missing: {missing}" if missing else f"PASS: branch diff includes all required files"

results = [
    check_contains("data/supabase/migrations/2026-04-07-pos-orders-lifecycle-columns.sql", [
        "ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMPTZ",
        "ADD COLUMN IF NOT EXISTS cancellation_reason TEXT",
        "ADD COLUMN IF NOT EXISTS order_status TEXT",
        "ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ",
        "idx_pos_orders_cancelled_at_not_null",
        "extras_tombstoned",
    ]),
    check_contains("scripts/sync_pos_to_supabase.py", [
        'order.get("cancelled_at")',
        'order.get("cancellation_reason")',
        'order.get("order_status")',
        'order.get("completed_at")',
    ], forbidden=[
        '(order.get("payment_status") or "PAID")',  # the old hardcode
    ]),
    check_contains("hrms/api/mosaic_webhook.py", [
        "@frappe.whitelist(allow_guest=True",
        "set_backend_observability_context(",
        'module="sync_verification"',
        'action="mosaic_webhook_receive"',
        "order.cancelled",
        "cancelled_at IS NULL",
    ]),
    check_contains("scripts/verify_mosaic_pos_sync.py", [
        "cancelled_at=is.null",  # PostgREST filter syntax
        "def tombstone_extras(",
        "extras_tombstoned",
        "reconciled_from_mosaic_gap",
    ], forbidden=[
        "DELETE FROM pos_orders",
    ]),
    check_diff_includes("s169-mosaic-order-lifecycle-tombstone-webhook", [
        "data/supabase/migrations/2026-04-07-pos-orders-lifecycle-columns.sql",
        "scripts/sync_pos_to_supabase.py",
        "hrms/api/mosaic_webhook.py",
        "hrms/utils/supabase.py",
        "scripts/verify_mosaic_pos_sync.py",
        "data/POS_Extraction/MOSAIC_WEBHOOK_REGISTRATIONS.csv",
        "output/l3/s169/form_submissions.json",
        "output/l3/s169/api_mutations.json",
        "output/l3/s169/state_verification.json",
        "output/l3/s169/map_order_snapshot_before.json",
        "output/l3/s169/map_order_snapshot_after.json",
        "output/l3/s169/view_definitions_before.sql",
        "output/l3/s169/view_definitions_after.sql",
        "output/l3/s169/verify_s169.py",
    ]),
]

for r in results:
    print(r)
if any(r.startswith("FAIL") for r in results):
    sys.exit(1)
print("\nAll S169 verification checks passed.")
```

The agent MUST run this script after each phase and fix any FAIL before proceeding.

---

## Phases & Tasks

### Phase 0 — Pre-flight (6 units)

- **T0.1** — Read this plan fully. Read `scripts/sync_pos_to_supabase.py` (lines 1-100, 354-470), `scripts/verify_mosaic_pos_sync.py` (full file), `docs/api/MOSAIC_API.md` (full file), `data/POS_Extraction/MOSAIC_POS_API_KEYS.csv` (all 46 rows).
- **T0.2** — Create sprint branch: `git fetch origin production && git checkout -b s169-mosaic-order-lifecycle-tombstone-webhook origin/production`. Verify branch name via `git branch --show-current`.
- **T0.3** — Phantom scan: run the SQL from Ground-Truth Lock to count all phantom-void groups since 2026-01-01. Write to `tmp/s169_phantom_scan.md`. **HARD BLOCKER:** If the scan reveals >50 phantom groups (10× the single known incident), STOP and present a scope-expansion decision to Sam — a massive phantom population might indicate a different root cause than void-and-retry.
- **T0.4** — View dependency audit: run `SELECT definition FROM pg_views WHERE ...` and `pg_matviews` for all 12 objects, save full current definitions to `tmp/s169_view_definitions_before.sql` AND `output/l3/s169/view_definitions_before.sql`. Also run `pg_depend` to find any other objects depending on these views. **HARD BLOCKER:** If a view depends on another view in the list, determine the correct rewrite order and document in `tmp/s169_view_rewrite_order.md`.
- **T0.5 (webhook signing probe) — HARD BLOCKER GATE.** Register a test webhook pointing at a public inspector (e.g., `https://webhook.site/<uuid>`) and trigger a cancel on a test order (if staging is available) OR wait for a natural cancel in prod. Inspect headers. Document whether Mosaic signs webhooks and how (header name, HMAC algorithm, secret source). Write to `tmp/s169_webhook_signing_probe.md` and `output/l3/s169/webhook_signing_probe.md`. **If Mosaic does NOT sign**, the webhook endpoint MUST use the round-trip confirm fallback (Phase 3 T3.3).
- **T0.6** — Confirm `SENTRY_DSN` in Doppler `bei-erp/dev` (already done in S165; re-verify). Confirm `hq.bebang.ph` is publicly reachable: `curl -I https://hq.bebang.ph/api/method/ping` returns 200 or 401 (not timeout).

### Phase 1 — Schema migration (3 units)

- **T1.1** — Create `data/supabase/migrations/2026-04-07-pos-orders-lifecycle-columns.sql` with the full SQL from "Files to Create" §1.
- **T1.2** — Apply via Supabase Management API. Capture the response. Verify all 4 new columns via `information_schema.columns`. Verify the new `sync_verification` CHECK constraint via `pg_get_constraintdef`.
- **T1.3** — Verify the partial index exists: `SELECT indexname FROM pg_indexes WHERE tablename='pos_orders' AND indexname='idx_pos_orders_cancelled_at_not_null'`.

### Phase 2 — Fix `map_order()` (4 units)

- **T2.1** — Pre-edit snapshot: write `tmp/s169_map_order_probe.py` that imports `sync_pos_to_supabase.map_order` and runs it on a real Mosaic order JSON (fetched live via `fetch_all_orders` for SM Megamall 2026-04-04 LIMIT 1). Save output to `output/l3/s169/map_order_snapshot_before.json`. **HARD BLOCKER:** If this fails, STOP — can't verify the fix without a before baseline.
- **T2.2** — Edit `scripts/sync_pos_to_supabase.py:379-433` (`map_order` function): update the return dict per "Files to Modify" §1. Do NOT touch `map_order_items()` or `map_order_payments()`.
- **T2.3** — Post-edit snapshot: re-run `tmp/s169_map_order_probe.py`, save to `output/l3/s169/map_order_snapshot_after.json`. Diff before vs after — `cancelled_at`, `cancellation_reason`, `order_status`, `completed_at` keys must now appear, and `payment_status` should be the real value (or NULL, not 'PAID' by default).
- **T2.4** — Run existing sync script with `--date 2026-04-04 --store 2338 --dry-run` (if a dry-run flag exists; else a single real store-day) to confirm no import errors or runtime regressions from the fix.

### Phase 3 — Webhook endpoint (6 units)

- **T3.1** — Create `hrms/utils/supabase.py` — thin Postgres client (~50 lines) exposing `get_supabase_client()` with `execute(sql, params)` method. Reads credentials from Doppler via `_get_secret()` helper pattern.
- **T3.2** — Create `hrms/api/mosaic_webhook.py` skeleton (full body from "Files to Create" §2). Include the Sentry context call (`set_backend_observability_context`) as the first meaningful line — HARD BLOCKER per DM-7.
- **T3.3 (depends on T0.5 outcome)** — Implement auth:
  - If Mosaic signs: verify HMAC signature using the documented header name + algorithm
  - If Mosaic does NOT sign: round-trip confirm — on receiving a cancel event, call `GET /api/v1/orders/{id}` and ONLY tombstone if the response is 404 (confirming the order is really gone). Use the credential group matched by `data.location_id` to pick the right token.
- **T3.4** — Idempotent UPDATE: `UPDATE pos_orders SET cancelled_at = %s, cancellation_reason = %s WHERE id = %s AND cancelled_at IS NULL RETURNING id, location_id, business_date`. If `RETURNING` returns nothing, it's already tombstoned or the row doesn't exist — return `{"ok": true, "handled": false, "reason": "already tombstoned or not found"}`.
- **T3.5** — Return `{"ok": true}` within 2 seconds. If the round-trip confirm path is slow, make it async (Frappe background job) and return immediately. **HARD BLOCKER:** If the round-trip path takes >5 seconds, Mosaic will retry — we need async.
- **T3.6** — Add a unit-ish test: POST a fake payload to the endpoint via `curl` locally (or against dev Frappe), confirm the response is well-formed. Save to `output/l3/s169/webhook_test_payload.json` + `webhook_test_response.json`.

### Phase 4 — View / MV updates (10 units)

- **T4.1** — Read `tmp/s169_view_definitions_before.sql` (from T0.4). Parse each definition. For each one, write the rewritten definition with `WHERE cancelled_at IS NULL` added appropriately (either as a new WHERE clause or AND'd into an existing one).
- **T4.2** — Save the rewritten definitions to `tmp/s169_view_definitions_after.sql` and `output/l3/s169/view_definitions_after.sql`. Manual review: does each rewrite preserve intent?
- **T4.3 — T4.8** — For each of the 6 MVs (one task each), in rewrite order from T0.4:
  - `BEGIN; DROP MATERIALIZED VIEW <name>; CREATE MATERIALIZED VIEW <name> AS <new_def>; COMMIT;`
  - `REFRESH MATERIALIZED VIEW CONCURRENTLY <name>` (if unique index exists; else plain REFRESH)
  - Run a sample count query pre/post; log delta
- **T4.9** — For each of the 6 regular views: `CREATE OR REPLACE VIEW <name> AS <new_def>;`. Sample count query pre/post.
- **T4.10** — Run the sales-dashboard refresh function: `python scripts/supabase_exec.py "select public.refresh_sales_dashboard_daily_store_metrics();"`. Must succeed without errors.

### Phase 5 — 30-day backfill (5 units)

- **T5.1** — Calculate the date range: `date_from = today - 30 days`, `date_to = yesterday PHT`.
- **T5.2** — Run `python scripts/sync_pos_to_supabase.py --from <date_from> --to <date_to> --parallel`. Expected runtime: ~30-60 minutes (rate-limited). Monitor for errors.
- **T5.3** — Verify the new `map_order` output populated the columns: `SELECT COUNT(DISTINCT payment_status) FROM pos_orders WHERE business_date >= '<date_from>'` must return >1 (proves we're reading real values now, not just the hardcoded 'PAID').
- **T5.4** — Verify `cancelled_at` is still NULL for all re-synced rows (the list endpoint only returns completed orders, so no cancelled_at should be set by sync — the webhook and verify safety net do that).
- **T5.5** — Spot-check 5 random store-days: sample `SELECT payment_status, COUNT(*) FROM pos_orders WHERE location_id=X AND business_date=Y GROUP BY payment_status`. Expect mostly `PAID` but with some variation (e.g., `PENDING` for in-flight orders that were later completed).

### Phase 6 — Verify script upgrade (6 units)

- **T6.1** — Update `supabase_count()` in `scripts/verify_mosaic_pos_sync.py` to append `cancelled_at=is.null` to PostgREST params. Example:
  ```python
  params = {
      "location_id": f"eq.{location_id}",
      "business_date": f"eq.{business_date}",
      "select": "id",
      "cancelled_at": "is.null",
  }
  ```
- **T6.2** — Add new `tombstone_extras(client, cred, loc_id, ds, supabase_extra_ids)` function. Per extra ID: direct `GET /api/v1/orders/{id}` → if 404, add to tombstone batch. Return list of confirmed-gone IDs.
- **T6.3** — Execute the tombstone: single parameterized UPDATE with `id = ANY(%s)` to update all confirmed-gone IDs in one round-trip.
- **T6.4** — Update `_process_group` `extra` branch: call `tombstone_extras`, set row status to `extras_tombstoned`, `heal_attempted = TRUE`. Post-tombstone, re-run `supabase_count()` (now filtered) and verify it equals `mosaic_total`. If yes, status is `extras_tombstoned`. If not, status is `unresolved`.
- **T6.5** — Ensure `DELETE FROM pos_orders` does NOT appear anywhere in the file (grep check).
- **T6.6** — Run pre-commit guard: `python scripts/guards/check_chat_space_literals.py scripts/verify_mosaic_pos_sync.py`. Must pass.

### Phase 7 — Webhook registration (3 units)

- **T7.1** — Write `scripts/s169_register_webhooks.py`: iterates over unique credential groups in `MOSAIC_POS_API_KEYS.csv`, for each one calls `POST /api/v1/webhooks` with `{"url": "https://hq.bebang.ph/api/method/hrms.api.mosaic_webhook.receive", "events": ["order.cancelled"]}`. Before registering, call `GET /api/v1/webhooks` and skip if our URL is already registered. Record each registration (ID, credential group, registered_at) to `data/POS_Extraction/MOSAIC_WEBHOOK_REGISTRATIONS.csv`.
- **T7.2** — Run the registration script. Expected: 12 new rows in the CSV, 0 errors.
- **T7.3** — Verify: for a random credential group, run `GET /api/v1/webhooks` — our URL must appear in the list.

### Phase 8 — L3 verification (8 units)

- **T8.1** — **Apr 4 SM Marikina test — the primary acceptance.** Pre-run sanity SQL (capture to state_verification.json): `SELECT COUNT(*) FROM pos_orders WHERE location_id=2317 AND business_date='2026-04-04'` (should be 311 total rows), AND `... AND cancelled_at IS NULL` (should be 311 — nothing tombstoned yet).
- **T8.2** — Run upgraded verify script: `python scripts/verify_mosaic_pos_sync.py --date 2026-04-04 --store 2317 --no-chat`. Capture stdout to `output/l3/s169/verification_run.log`. Expected: log shows `[EXTRA]` then `[TOMBSTONED]` for the 3 phantom IDs.
- **T8.3** — Post-run SQL: verify the 3 phantom rows have `cancelled_at IS NOT NULL` and `cancellation_reason = 'reconciled_from_mosaic_gap'`.
- **T8.4** — Post-run SQL: `SELECT COUNT(*) WHERE location_id=2317 AND business_date='2026-04-04' AND cancelled_at IS NULL` now equals 308 (matches Mosaic).
- **T8.5** — Verify `sync_verification` has a new row: `SELECT * FROM sync_verification WHERE location_id=2317 AND business_date='2026-04-04' ORDER BY verified_at DESC LIMIT 1` shows `status='extras_tombstoned'`.
- **T8.6** — Regression check: run the verify script for a random healthy store-day (e.g., SM Megamall 2026-04-05). Expected: status `ok`, no tombstoning, no errors.
- **T8.7** — Full 7-day sweep: `python scripts/verify_mosaic_pos_sync.py --days 7 --no-chat`. Expected: 0 `extra` rows in the latest state. Runtime <90s.
- **T8.8** — Run `python output/l3/s169/verify_s169.py`. All checks PASS.

### Phase 9 — Closeout (5 units)

- **T9.1** — Update plan YAML: `status: COMPLETED`, `completed_date: <today>`, `backend_pr: <PR#>`, `execution_summary: <summary>`, `l3_result: <summary>`.
- **T9.2** — Update `docs/plans/SPRINT_REGISTRY.md` S169 row: status → COMPLETED with PR reference.
- **T9.3 (MW8)** — Explicit `git add -f`:
  ```bash
  git add -f \
    data/supabase/migrations/2026-04-07-pos-orders-lifecycle-columns.sql \
    scripts/sync_pos_to_supabase.py \
    scripts/verify_mosaic_pos_sync.py \
    hrms/api/mosaic_webhook.py \
    hrms/utils/supabase.py \
    data/POS_Extraction/MOSAIC_WEBHOOK_REGISTRATIONS.csv \
    docs/plans/2026-04-07-sprint-169-mosaic-order-lifecycle-tombstone-webhook.md \
    docs/plans/SPRINT_REGISTRY.md \
    output/l3/s169/form_submissions.json \
    output/l3/s169/api_mutations.json \
    output/l3/s169/state_verification.json \
    output/l3/s169/map_order_snapshot_before.json \
    output/l3/s169/map_order_snapshot_after.json \
    output/l3/s169/view_definitions_before.sql \
    output/l3/s169/view_definitions_after.sql \
    output/l3/s169/webhook_test_payload.json \
    output/l3/s169/webhook_test_response.json \
    output/l3/s169/verification_run.log \
    output/l3/s169/verify_s169.py \
    output/l3/s169/webhook_signing_probe.md
  ```
  Do NOT use `git add -A`.
- **T9.4** — Create PR: `GH_TOKEN="" gh pr create --repo Bebang-Enterprise-Inc/hrms --base production --head s169-mosaic-order-lifecycle-tombstone-webhook --title "S169: Mosaic Order Lifecycle CDC via Webhook + Tombstone" --body "..."`. PR body includes task-by-task checklist and the Apr 4 SM Marikina before/after evidence.
- **T9.5** — STOP per PR-HANDOFF rule. Post PR number to Sam and exit. No merge, no deploy.

---

## Execution Workflow

- Test Python changes locally: `/local-frappe` (for the webhook endpoint — needs a local Frappe site with the updated hrms app)
- Deploy changes: `/deploy-frappe` (full build required for the new webhook endpoint — NOT skip_build)
- E2E testing: the L3 scenarios above — no separate E2E framework needed
- Webhook live test: trigger a test cancel in Mosaic staging (if available) or wait for a natural production cancel

---

## Anti-Rewind / Concurrent-Run Protection Contract

- **Ownership matrix:** This sprint owns exclusively:
  - `data/supabase/migrations/2026-04-07-pos-orders-lifecycle-columns.sql` (NEW)
  - `scripts/sync_pos_to_supabase.py` — `map_order` function only, lines 379-433
  - `scripts/verify_mosaic_pos_sync.py` — `supabase_count` + `_process_group` `extra` branch + new `tombstone_extras` function
  - `hrms/api/mosaic_webhook.py` (NEW)
  - `hrms/utils/supabase.py` (NEW)
  - `data/POS_Extraction/MOSAIC_WEBHOOK_REGISTRATIONS.csv` (NEW)
  - `pos_orders` table (schema change)
  - `sync_verification` table (CHECK constraint change)
  - The 6 MVs and 6 views listed in "Files to Modify" §3-4
- **Protected surfaces (DO NOT TOUCH):**
  - `scripts/sync_pos_to_supabase.py` — functions other than `map_order`, especially `sync_store_day`, `fetch_all_orders`, `get_completed_store_days`, `set_sync_progress`
  - `sync_progress` table — schema unchanged
  - `pos_order_items` and `pos_order_payments` tables — no schema change
  - `scripts/detect_anomalies.py` — unrelated to this sprint (already fixed in S165 follow-up)
  - `.github/workflows/daily-pos-sync.yml` — unchanged (already handles the upgraded verify script via the `verify-sync` job)
- **Remote truth baseline:**
  - repo: `Bebang-Enterprise-Inc/hrms`
  - release_branch: `production`
  - release_head_sha: to be captured at Phase 0 start
- **Freshness gate:** Before creating the PR, `git fetch origin production && git rebase origin/production`. If conflicts in `scripts/verify_mosaic_pos_sync.py` (because S165 just landed), resolve by preserving S165 (it's the base) and adding the new tombstone logic on top.

---

## Status Reconciliation Contract

When any of the following change, update all authoritative surfaces in the same commit:
1. Phase task status
2. L3 evidence file presence
3. PR number
4. Plan YAML `status` field
5. `docs/plans/SPRINT_REGISTRY.md` S169 row

---

## Signoff Model

- **Mode:** single-owner
- **Approver of record:** Sam (CEO)
- **Signoff artifact:** PR review + merge by Sam

---

## Out of Scope (Explicitly NOT in This Plan)

- **Subscribing to `order.created` or `order.completed` webhooks** — duplicating the sync would cause double-writes. The hourly sync is the canonical path for creating/updating rows; webhooks are only for cancel events.
- **Retroactive backfill of `payment_status` for orders older than 30 days** — too expensive, insufficient business value (those months are already closed).
- **Refactoring `map_order` to a class-based mapper or pydantic model** — scope creep; keep the function-based structure for minimal diff.
- **Adding a frontend dashboard for `cancelled_at` analytics** — a separate future sprint could add "voided order rate per cashier" reports.
- **Migrating away from upsert-based sync entirely** — out of scope; the incremental pattern stays.
- **Handling `order.updated` or partial-refund events** — Mosaic doesn't document these events; if they exist, a future sprint.
- **HMAC signing for our OUTBOUND webhook registration calls** — Mosaic's registration endpoint is OAuth-authed; no HMAC needed for us to register.

---

## Amendment History

(none yet — plan created 2026-04-07 from S165 Apr 4 SM Marikina incident research)
