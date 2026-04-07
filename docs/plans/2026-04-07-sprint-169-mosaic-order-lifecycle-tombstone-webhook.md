---
canonical_sprint_id: S169
display: Sprint 169
status: PLANNED (amended 2026-04-07 post-audit)
branch: s169-mosaic-order-lifecycle-tombstone-webhook
lane: single
created_date: 2026-04-07
completed_date:
deployed_at:
backend_pr:
frontend_pr:
l3_result:
execution_summary:
depends_on: S165 (merged — PRs #466, #470, #472) — this sprint replaces S165's "extra" branch handling with a proper tombstone pattern
amendment_history:
  - 2026-04-07 — v2 post-audit amendments applied (10 verified blockers: 4 CRITICAL + 6 HIGH + 15 MED/LOW). Root cause of BLOCKER 1 was an UPSERT race that would have silently un-tombstoned every cancelled order on the next hourly poll. See ## Amendment History at bottom of plan.
---

# S169 — Mosaic Order Lifecycle CDC via Webhook + Tombstone Pattern

**Goal:** Eliminate phantom-void data drift in `pos_orders` by subscribing to Mosaic's `order.cancelled` webhook, storing the order lifecycle via two separate write-paths (the poller writes `order_status` + `completed_at` from the live API; the webhook + nightly verify-script tombstone exclusively write `cancelled_at` + `cancellation_reason`), filtering every downstream revenue view on `cancelled_at IS NULL` via a single wrapper view `v_pos_orders_live`, and upgrading the S165 nightly verify script's `extra` branch to tombstone-not-delete. Preserves full audit history, closes the Apr 4 SM Marikina incident (₱2,052 phantom gross, 3 phantom rows) as the first real test of the pattern.

**Critical architectural constraint (from v2 audit):** The hourly `sync_pos_to_supabase.py` poller MUST NOT include `cancelled_at` or `cancellation_reason` keys in the dict returned by `map_order()`. PostgREST `Prefer: resolution=merge-duplicates` writes every column present in the payload via `ON CONFLICT DO UPDATE SET col=EXCLUDED.col`. Since the Mosaic list endpoint only returns completed orders, `order.get("cancelled_at")` would be `None` for every row, and including the key would cause every hourly poll to `UPDATE pos_orders SET cancelled_at = NULL` — silently un-tombstoning everything the webhook just set. This is a hard no-go and is enforced via a `MUST_NOT_CONTAIN` assertion in `verify_s169.py`. See BLOCKER 1 in the audit and Design Rationale decision #9.

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

9. **Poller writes `order_status` + `completed_at` but NOT `cancelled_at` + `cancellation_reason`** (added 2026-04-07 post-audit) — This is the single most important architectural decision in the plan. See BLOCKER 1 in `output/plan-audit/s169-mosaic-order-lifecycle/verified_blockers.md` for the full trace.
   - **The race:** `scripts/sync_pos_to_supabase.py:174-198` `supabase_upsert()` sends PostgREST header `Prefer: resolution=merge-duplicates,return=minimal` (line 187). PostgREST writes `INSERT ... ON CONFLICT (id) DO UPDATE SET col=EXCLUDED.col` for **every column present in the JSON payload**. Columns NOT in the payload are left untouched — verified PostgREST semantics, documented behavior.
   - **The failure mode (if we naively added all 4 lifecycle cols):** Since the Mosaic list endpoint hard-filters to completed orders only (doc line 56, empirically verified), `order.get("cancelled_at")` returns `None` for every row the poller sees. If `map_order` includes `cancelled_at: None` in its return dict, every hourly poll would `UPDATE pos_orders SET cancelled_at = NULL WHERE id IN (...)` — silently un-tombstoning everything the webhook just set. The webhook's idempotency guard (`WHERE cancelled_at IS NULL`) protects the webhook from itself but does NOT protect from the poller.
   - **The fix:** Split the lifecycle cols into two ownership zones:
     - **Poller-owned** (`order_status`, `completed_at`) — live fields that change during an order's normal lifecycle (PENDING → COMPLETED). Poller writes on every sync via the existing upsert. Idempotent because it writes the same value every time unless Mosaic changes it.
     - **Webhook-and-verify-owned** (`cancelled_at`, `cancellation_reason`) — state transitions that happen AFTER the order leaves the list endpoint. Only the webhook handler (`hrms/api/mosaic_webhook.py`) and the nightly verify script's `tombstone_extras()` function can write these columns. The poller never references them in any payload.
   - **Enforcement:** `verify_s169.py` asserts `MUST_NOT_CONTAIN: "cancelled_at": order.get` and `MUST_NOT_CONTAIN: "cancellation_reason": order.get` against `scripts/sync_pos_to_supabase.py`. The phase gate fails if the agent accidentally re-adds them.
   - **Why `order_status` is still safe:** When an order is cancelled, Mosaic removes it from the list endpoint entirely — so the poller never sees the row again after the transition. The webhook handler explicitly writes `order_status='CANCELLED'` alongside `cancelled_at` so the row is self-consistent. Since Mosaic won't return the row in any future list-endpoint poll, there's no reverse-race path.
   - **Cross-cutting lesson:** `Prefer: resolution=merge-duplicates` is the BEI-wide Supabase write pattern — it appears in 9 sync scripts per a 2026-04-07 grep. Any future plan that adds lifecycle columns to any synced table must apply the same split-ownership rule. Worth memorializing in `MEMORY.md`.

### Known limitations

- **`fetch_all_orders()` at `scripts/sync_pos_to_supabase.py:354`** — does not paginate through cancelled orders (Mosaic filters them out). `cancelled_at` is populated ONLY via the webhook handler or via the nightly verify script's tombstone path on direct-ID 404 confirmation.
- **Poller vs webhook column ownership (post-audit v2 constraint — HARD BLOCKER enforced by verify_s169.py):** `map_order()` MUST NOT include `cancelled_at` or `cancellation_reason` keys in its return dict. See Design Rationale decision #9 for the full trace. The poller owns `order_status` and `completed_at`; the webhook + nightly verify own `cancelled_at` and `cancellation_reason`. This split is not optional — it is load-bearing architecture.
- **Webhook replay / deduplication** — webhooks can fire multiple times for the same event. The handler MUST be idempotent (single UPDATE with `WHERE cancelled_at IS NULL` guard — only overwrites if the row hasn't already been tombstoned). This protects against double-processing AND against the rare reverse race where the verify script tombstoned first.
- **Webhook delivery guarantees** — Mosaic does not document at-least-once / at-most-once semantics. Assume at-least-once (most webhook systems are). Combined with the nightly verify safety net, occasional dropped webhooks are fully tolerated.
- **`hq.bebang.ph` availability** — if the Frappe backend is down during a cancellation event, the webhook fires and fails. Mosaic's retry behavior is undocumented. Safety net: the nightly verify script catches any missed cancellations. Secondary safety net: the Phase 9 webhook silence detector alerts if 7 consecutive days see zero tombstones AND zero nightly-verify tombstones (suggests the webhook may be silently dead).
- **`sync_progress` table unchanged** — this sprint does not touch sync_progress semantics. Hourly sync continues to function exactly as S165 left it. Phase 5 backfill uses `get_completed_store_days()` at `scripts/sync_pos_to_supabase.py:241` for resume-on-interrupt behavior.
- **Sales reports from March and earlier** — will continue to include historical phantom rows if any exist. Phase 5 backfill is deliberately bounded to the last 30 days; older data is frozen for finance purposes.
- **Phase 4 dashboard lag window** — during Phase 4 execution, `daily-pos-sync.yml` is disabled via `gh workflow disable`. The hourly `refresh-sales-dashboard-views` job does not run. Dashboard data lags behind live POS by up to ~30 minutes. Finance team MUST be notified before Phase 4 begins. Workflow is re-enabled immediately after the last view is rewritten.
- **Existing Supabase access layer is fragmented** — 4 parallel helper sets exist in `sales_dashboard.py`, `discount_abuse.py`, `marketing_giveaways.py`, and `store_order_demand_snapshot.py`. This sprint adds a 5th (`hrms/utils/supabase.py`) BUT explicitly positions it as the canonical extraction target that future sprints will migrate the other 4 to. Design-review H1 is acknowledged as a follow-up sprint, not a blocker here.

### Source references

- Mosaic API doc (BEI-ERP local, 187 lines — **this is the SSOT**): `docs/api/MOSAIC_API.md` — "Retrieve a list of *completed* orders" at **line 56**, `POST /api/v1/orders/{id}/cancel` at **line 140** (section 2.5), `order.cancelled` event at **line 182** (section 8 Webhooks events list). **Line refs corrected 2026-04-07 post-audit** (earlier plan draft cited line 171 and 396 — those were from the longer mirror, not the local file an executor reads).
- Full Mosaic API doc mirror: `F:\Dropbox\Projects\Dice-Roll-Game-Digital\docs\api\MOSAIC_API.md` (reference only; executors MUST use the BEI-ERP local copy)
- Sync script: `scripts/sync_pos_to_supabase.py` — `map_order()` at line 379, `payment_status` hardcode at line 401, `map_order_items()` at line 434, `map_order_payments()` at line 463, `fetch_all_orders()` at line 354, `fetch_orders_page()` at line 310, **`supabase_upsert()` at line 174-198 with `Prefer: resolution=merge-duplicates,return=minimal` header at line 187** (THE critical line for BLOCKER 1), call site `supabase_upsert(client, "pos_orders", order_rows, on_conflict="id")` at line 535
- **Canonical Frappe JSON-parse pattern:** `hrms/api/esignature.py:55-60` — use `frappe.request.get_data(as_text=True) + json.loads()`, NOT `frappe.request.get_json(...)` (which doesn't exist in this codebase — verified via grep, zero matches)
- **Canonical Supabase-from-Frappe pattern:** `hrms/api/sales_dashboard.py:168-199` — `_get_supabase_url`, `_get_supabase_service_key`, `_supabase_headers`, `_supabase_get` helpers using `requests` + PostgREST. This is the shape `hrms/utils/supabase.py` MUST mirror — do NOT use `psycopg2`.
- PostgREST upsert semantics: https://postgrest.org/en/stable/references/api/tables_views.html#upsert — "PostgREST only updates the columns specified in the request body"
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
| Phase 0 | Pre-flight: schema audit, phantom scan, webhook signing probe (self-induced cancel + 30min fallback), view dependency audit, canonical-pattern reads | **8** (was 6 — BLOCKER 6 adds self-induced cancel script + T0.7 reference-pattern check) |
| Phase 1 | Schema migration: `pos_orders` lifecycle columns + `sync_verification` enum + partial index | 3 |
| Phase 2 | Fix `map_order()` — stop hardcoding PAID, add `order_status` + `completed_at` ONLY (NOT `cancelled_at` / `cancellation_reason` per BLOCKER 1) | **5** (was 4 — T2.4 phase-gate verification + T2.5 local sanity) |
| Phase 3 | Build `hrms/utils/supabase.py` (PostgREST + `requests`) + `hrms/api/mosaic_webhook.py` (canonical JSON parse + try/except + HTTP 500 retry path) + T0.5-dependent auth + fault injection test + deploy | **8** (was 6 — BLOCKER 4 + BLOCKER 5 + HIGH 8 + explicit deploy gate) |
| Phase 4 | Wrapper-view pattern (`v_pos_orders_live`) + single-token substitution of 12 dependents + cron disable/enable fence + rollback runbook + `bench clear-cache` | **12** (was 10 — BLOCKER 7 + BLOCKER 2 cron fence + HIGH 9 rollback + MED bench clear) |
| Phase 5 | Backfill 30-day window (post-Phase-4, workflow re-enabled, concurrent with hourly cron — sync_progress handles it) | 5 |
| Phase 6 | Upgrade `verify_mosaic_pos_sync.py` `extra` branch to tombstone-not-delete (new `tombstone_extras` function with HIGH 8 try/except) | **8** (was 6 — HIGH 8 error handling + dry-run smoke test) |
| Phase 7 | Register webhook on all 12 Mosaic credential groups (one-time operator action) | 3 |
| Phase 8 | L3 verification — Apr 4 SM Marikina incident as first real test + live webhook test via self-induced cancel | **10** (was 8 — T8.6 downstream view smoke + T8.7 live webhook test) |
| Phase 9 | Closeout: PR, plan+registry update, explicit `git add -f`, HIGH 10 webhook silence monitor, MEMORY.md lesson | **7** (was 5 — HIGH 10 + MEMORY.md entry) |
| **Total** | | **69** |

Hard limit 15 per phase respected. Total **69 units** (was 56 pre-audit — grew by 13 to cover all 10 verified blockers from `output/plan-audit/s169-mosaic-order-lifecycle/verified_blockers.md`, zero features cut). Still well under 80-unit single-session ceiling. Largest phase is **12 units** (Phase 4 — the wrapper-view pattern + cron fence + rollback), well under the 15-unit cap.

**Audit amendment philosophy (per Sam directive 2026-04-07):** "Reducing units is not a priority, getting what I want is." This amendment adds units rather than removing them. No features cut, no corners cut — every blocker gets a full correct fix with explicit validation gates.

---

## Requirements Regression Checklist

Before writing any code, the executing agent MUST verify every item below:

### Schema migration
- [ ] Does the `pos_orders` migration add exactly these 4 columns: `cancelled_at TIMESTAMPTZ`, `cancellation_reason TEXT`, `order_status TEXT`, `completed_at TIMESTAMPTZ`?
- [ ] Are new columns **nullable** so existing ~10M rows don't fail the migration?
- [ ] Is there a partial index `idx_pos_orders_cancelled_at_not_null ON pos_orders(cancelled_at) WHERE cancelled_at IS NOT NULL` for efficient tombstone queries?
- [ ] Does the `sync_verification` CHECK constraint get a new value `extras_tombstoned` added to the allowed status list (now 7 values: ok, missing, extra, healed, unresolved, api_error, extras_tombstoned)?

### `map_order()` fix — POLLER WRITES `order_status` + `completed_at` ONLY
- [ ] Does the fix stop hardcoding `'PAID'` as a fallback? Does it read `order.get("payment_status")` and preserve the real value (explicit `None` check — NOT `or "PAID"`, NOT `or ""`)? See Files to Modify §1 for the exact replacement.
- [ ] Does the fix populate `order_status` and `completed_at` from the order object? These are poller-owned — every hourly poll writes them.
- [ ] **HARD BLOCKER — CRITICAL architecture constraint:** Does the fix OMIT `cancelled_at` and `cancellation_reason` from the return dict entirely? These keys MUST NOT appear in `map_order`'s output. See Design Rationale decision #9 for the full rationale. `verify_s169.py` enforces this via `MUST_NOT_CONTAIN: '"cancelled_at": order.get'` and `MUST_NOT_CONTAIN: '"cancellation_reason": order.get'` against `scripts/sync_pos_to_supabase.py`. If the agent re-adds them thinking "we need to initialize the columns", the phase gate FAILS and the agent MUST remove them before proceeding.
- [ ] Does `_resolve_channel()` continue to work unchanged (not accidentally regressed)?
- [ ] **HARD BLOCKER:** Is there a before/after snapshot (`tmp/s169_map_order_snapshot_before.json` + `after.json`) showing the exact diff of old vs new `map_order` output on a sample real order? Agent must produce both before modifying production sync.
- [ ] Does the after-snapshot show exactly these NEW keys: `order_status`, `completed_at`, and the fixed `payment_status` (real value, not hardcoded)? And show the ABSENCE of `cancelled_at` + `cancellation_reason`?

### Webhook endpoint
- [ ] Is the endpoint at `hrms/api/mosaic_webhook.py` with `@frappe.whitelist(allow_guest=True, methods=["POST"])`?
- [ ] Does the endpoint call `set_backend_observability_context(module="sync_verification", action="mosaic_webhook_receive", mutation_type="update")` as its first meaningful line per DM-7?
- [ ] **HARD BLOCKER (BLOCKER 4 from audit):** Does the endpoint parse the JSON body using the canonical BEI pattern `frappe.request.get_data(as_text=True) + json.loads()` per `hrms/api/esignature.py:55-60`, NOT `frappe.request.get_json(...)` (which does not exist in this codebase — verified via grep)? `verify_s169.py` enforces `MUST_CONTAIN: 'get_data(as_text=True)'` and `MUST_NOT_CONTAIN: 'frappe.request.get_json'`.
- [ ] Does the JSON parse have a try/except that returns `{"ok": false, "reason": "invalid_json"}` with HTTP 400 on `json.JSONDecodeError`? (No `silent=True` — errors must be visible.)
- [ ] Does the endpoint verify the webhook signature if Mosaic signs (Phase 0 T0.5 resolves the probe)?
- [ ] If Mosaic does NOT sign, does the endpoint confirm the event by calling `GET /api/v1/orders/{id}` on Mosaic and ONLY tombstoning if the response is HTTP 404 (confirming the order is really gone)?
- [ ] Is the UPDATE idempotent (`UPDATE pos_orders SET cancelled_at = ?, cancellation_reason = ?, order_status = 'CANCELLED' WHERE id = ? AND cancelled_at IS NULL RETURNING id`)? Note `order_status = 'CANCELLED'` is explicitly set here — the webhook owns this transition because the poller won't see the row again after cancel.
- [ ] **HARD BLOCKER (HIGH 8 from audit):** Is the Supabase UPDATE wrapped in a try/except? On Supabase failure, does it return HTTP 500 so Mosaic queues a retry (instead of marking the event as delivered and losing it)? Does it `frappe.log_error()` with the exception (feeds Sentry via the monkey-patch)?
- [ ] Does the endpoint return `{"ok": true}` within 2 seconds to avoid webhook retry storms? If round-trip confirm exceeds 5s, does it defer to `frappe.enqueue` background job?

### `hrms/utils/supabase.py` helper
- [ ] **HARD BLOCKER (BLOCKER 5 from audit):** Does the helper use **PostgREST + `requests`**, mirroring the shape of `hrms/api/sales_dashboard.py:168-199` (`_get_supabase_url`, `_get_supabase_service_key`, `_supabase_headers`, `_supabase_get`)? It MUST NOT use `psycopg2`. `verify_s169.py` enforces `MUST_NOT_CONTAIN: 'psycopg2'` in `hrms/utils/supabase.py`.
- [ ] Does the helper expose a minimal surface: `get_service_key()`, `supabase_headers(prefer=None)`, `supabase_get(path, params=None)`, `supabase_patch(path, params, body)`, `supabase_query_sql(sql, params)` (the last one hitting the Management API for DDL/complex updates that PostgREST can't express cleanly)?
- [ ] Is the helper documented as the canonical extraction target — future sprints migrate `sales_dashboard.py`, `discount_abuse.py`, `marketing_giveaways.py`, `store_order_demand_snapshot.py` to use it? (The migration itself is OUT of scope for this sprint — do NOT touch those 4 files.)

### View / MV updates — WRAPPER-VIEW PATTERN (post-audit v2 — BLOCKER 7 fix)
- [ ] **HARD BLOCKER (BLOCKER 2 from audit):** Before Phase 4 begins, has the `daily-pos-sync.yml` workflow been disabled via `GH_TOKEN="" gh workflow disable daily-pos-sync.yml --repo Bebang-Enterprise-Inc/hrms`? The hourly `refresh-sales-dashboard-views` job runs unconditionally and would fail on a DROPped MV — see `.github/workflows/daily-pos-sync.yml:125-142`. Workflow MUST stay disabled until the last view is rewritten. Dashboard data will lag ~30 min during the window — finance team notified in advance.
- [ ] **HARD BLOCKER:** Before any view is dropped, does the plan produce `tmp/s169_view_definitions_before.sql` containing the full current definitions of all 12 objects for rollback? And `tmp/s169_rollback_phase4.sql` containing exactly the SQL to restore the pre-Phase-4 state (drops new versions + replays originals)?
- [ ] **HARD BLOCKER (BLOCKER 7 from audit — wrapper-view pattern):** Does Phase 4 use the wrapper-view approach instead of parsing-and-rewriting each view's body? Specifically:
  - [ ] Step 1: `CREATE OR REPLACE VIEW v_pos_orders_live AS SELECT * FROM pos_orders WHERE cancelled_at IS NULL;` — this is the single source of truth for "live orders" going forward.
  - [ ] Step 2: For each of the 12 dependent views/MVs, do a **single-token find/replace**: change `FROM pos_orders` to `FROM v_pos_orders_live`, and `JOIN pos_orders` to `JOIN v_pos_orders_live`. NO SQL parsing. NO WHERE-clause mangling. Just regex-safe token replacement on the definition text.
  - [ ] Step 3: `CREATE OR REPLACE VIEW` for each regular view with the new body. `DROP MATERIALIZED VIEW ... CREATE MATERIALIZED VIEW ... AS` for each MV. All wrapped in transactions.
  - [ ] Step 4: Immediately after each CREATE, run a sample `COUNT(*)` query and verify it matches the expected delta (0 for non-SM-Marikina objects, -3 for objects that include SM Marikina Apr 4).
- [ ] Are the rewritten definitions committed to `output/l3/s169/view_definitions_after.sql` for audit?
- [ ] Does the sales-dashboard view refresh still work (tested by running `scripts/supabase_exec.py "select public.refresh_sales_dashboard_daily_store_metrics();"` post-deploy, AFTER the workflow is re-enabled)?
- [ ] Is a `REFRESH MATERIALIZED VIEW CONCURRENTLY` pattern preserved where the MV has a unique index (check each MV's indexes first)?
- [ ] Post-Phase-4: was `daily-pos-sync.yml` re-enabled via `gh workflow enable`? Was the first post-reenable hourly refresh verified green?
- [ ] Post-Phase-4: was `bench clear-cache` run inside the Frappe container (`frappe_backend.1.*`) to invalidate any cached Supabase responses in `hrms.api.sales_dashboard`? (Per deployment-qa MED-8 — bei-tasks doesn't read the views directly but DOES cache the proxied Frappe responses.)
- [ ] **T0.4 HARD BLOCKER reinforcement:** If the `pg_depend` audit in Phase 0 T0.4 reveals a 13th object (not in the current list of 12), the plan's `verify_s169.py` view count assertion must be updated in the SAME edit, not deferred. Scope change requires explicit plan update.

### Backfill
- [ ] Is the backfill window exactly `date_from = today - 30 days` to `date_to = yesterday PHT`?
- [ ] Does the backfill re-run `sync_store_day()` for each (store, date) tuple so the new `map_order()` output overwrites existing rows via upsert on `id`?
- [ ] Does the backfill respect the existing REQUEST_INTERVAL rate limiting?
- [ ] Does T5.2 explicitly cite `scripts/sync_pos_to_supabase.py:241 get_completed_store_days()` as the resume logic that makes the backfill restartable if interrupted?
- [ ] **Timing constraint:** Is the backfill run AFTER Phase 4 completes (workflow re-enabled) so dashboards are live while the backfill works in background? Or is the backfill run DURING the Phase 4 disable window so no hourly cron races with it? Plan must pick one — audit deployment-qa HIGH-5 flagged this ambiguity.

### Verify script upgrade
- [ ] Does the upgraded `extra` branch do all of: (a) pull full Mosaic ID list via `fetch_all_orders()`, (b) set-diff against Supabase IDs, (c) direct-ID 404 confirmation per extra ID, (d) mark `cancelled_at = NOW()` + `cancellation_reason = 'reconciled_from_mosaic_gap'` + `order_status = 'CANCELLED'` on confirmed-gone rows, (e) write `status='extras_tombstoned'` to sync_verification?
- [ ] **HARD BLOCKER (HIGH 8 from audit):** Is the Supabase UPDATE inside `tombstone_extras()` wrapped in try/except that logs via `sentry_sdk.capture_exception()` and re-raises to the caller? The caller marks the row as `unresolved` in `sync_verification` and escalates via the existing Chat alert path.
- [ ] Does it NEVER DELETE pos_orders rows? `verify_s169.py` enforces `MUST_NOT_CONTAIN: 'DELETE FROM pos_orders'`.
- [ ] Does `supabase_count()` query filter `cancelled_at=is.null` in the PostgREST params?
- [ ] Is the pre-commit guard `scripts/guards/check_chat_space_literals.py` still passing after all edits?

### Webhook registration
- [ ] Are all 12 credential groups registered with `POST /api/v1/webhooks` pointing at `https://hq.bebang.ph/api/method/hrms.api.mosaic_webhook.receive`?
- [ ] Are events exactly `["order.cancelled"]` (not subscribing to `order.created` or `order.completed` to avoid duplicating the sync)?
- [ ] Is the registration idempotent (check `GET /api/v1/webhooks` first, skip if already registered)?
- [ ] Are registration IDs recorded in `data/POS_Extraction/MOSAIC_WEBHOOK_REGISTRATIONS.csv` for future audit/unregister?

### Observability + webhook silence detection (HIGH 10 from audit)
- [ ] Is `SENTRY_DSN` in Doppler `bei-erp/dev`? (Verified 2026-04-07 — yes)
- [ ] Does the webhook endpoint emit a breadcrumb on every successful cancel update with `{order_id, location_id, cancelled_at}`?
- [ ] Is there a dashboard query / SQL view showing count of `cancelled_at IS NOT NULL` per store per day for BI consumption?
- [ ] **HIGH 10 (new check):** Does Phase 9 add a webhook silence detector? Specifically: a `SELECT COUNT(*) FROM sync_verification WHERE status = 'extras_tombstoned' AND verified_at >= NOW() - INTERVAL '7 days'` AND a `SELECT COUNT(*) FROM pos_orders WHERE cancelled_at >= NOW() - INTERVAL '7 days'` — if BOTH are zero for 7 consecutive days, the webhook may be silently dead (Mosaic silently deregistered, `hq.bebang.ph` firewalled, etc.). Alert to `spaces/AAQABiNmpBg` with "Mosaic webhook silent for 7 days — verify registration". Acceptable false-positive rate (some weeks have no cancels, e.g. Holy Week closures).

### Chat routing
- [ ] Do all notifications in this sprint's code go ONLY to `spaces/AAQABiNmpBg`?
- [ ] Does `scripts/guards/check_chat_space_literals.py` pass against all modified files?

---

## Autonomous Execution Contract

- **completion_condition:**
  - `pos_orders` has 4 new nullable columns (`cancelled_at`, `cancellation_reason`, `order_status`, `completed_at`) + partial index `idx_pos_orders_cancelled_at_not_null`
  - `sync_verification.status` allows `extras_tombstoned`
  - `map_order()` reads real `payment_status` + populates ONLY `order_status` and `completed_at` (NOT `cancelled_at` / `cancellation_reason` — critical architectural constraint per Design Rationale decision #9). Before/after snapshot diff committed to `output/l3/s169/`. `verify_s169.py` MUST_NOT_CONTAIN assertions on the forbidden keys pass.
  - `hrms/api/mosaic_webhook.py` endpoint exists with Sentry context, canonical JSON parse (`get_data(as_text=True) + json.loads()`), signature verify or round-trip confirm, idempotent UPDATE with try/except, Supabase-failure retry via HTTP 500, atomic `SET cancelled_at = ?, cancellation_reason = ?, order_status = 'CANCELLED'`
  - `hrms/utils/supabase.py` helper exists using PostgREST + `requests` (mirrors `hrms/api/sales_dashboard.py:168-199` shape). `verify_s169.py` MUST_NOT_CONTAIN `psycopg2` assertion passes.
  - `v_pos_orders_live` wrapper view exists filtering `WHERE cancelled_at IS NULL`
  - All 12 dependent views/MVs rewritten to read from `v_pos_orders_live` instead of `pos_orders` directly (verified via `pg_views` + `pg_matviews` definition re-query)
  - `daily-pos-sync.yml` workflow was disabled for the full duration of Phase 4 and re-enabled immediately after. First post-reenable hourly refresh was verified green.
  - `bench clear-cache` ran in Frappe backend container after Phase 4
  - 30-day backfill completed, resulting pos_orders rows show real `payment_status` values (not all `'PAID'`) AND populated `order_status` + `completed_at` — sample query proves it. `cancelled_at` remains NULL on all backfilled rows (correct — poller never writes it).
  - Verify script upgraded: `extra` branch tombstones via `tombstone_extras()` with try/except + set-diff + direct-ID 404 confirmation, `extras_tombstoned` status visible in `sync_verification`
  - All 12 credential groups registered with `order.cancelled` webhook, IDs logged in `data/POS_Extraction/MOSAIC_WEBHOOK_REGISTRATIONS.csv`
  - Self-induced cancel test completed (create + cancel a test order via Mosaic API, observe webhook fires, row tombstoned in Supabase within 30s) — evidence in `output/l3/s169/webhook_live_test_payload.json` + `_response.json`
  - Apr 4 SM Marikina incident tombstoned via the new pipeline (NOT manually): the verify script's next run shows `status='extras_tombstoned'` for that store-day and `supabase_count` filtered on `cancelled_at IS NULL` now equals `mosaic_total`
  - Webhook silence detector added (Phase 9 new task) — daily cron or nightly-verify extension
  - Phase 4 rollback runbook `tmp/s169_rollback_phase4.sql` exists and is commit-tracked
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

### 2. `hrms/api/mosaic_webhook.py` (NEW, ~250 lines)

**MUST_MODIFY:** `hrms/api/mosaic_webhook.py`
**MUST_CONTAIN:** `@frappe.whitelist(allow_guest=True, methods=["POST"])`
**MUST_CONTAIN:** `set_backend_observability_context(`
**MUST_CONTAIN:** `module="sync_verification"`
**MUST_CONTAIN:** `action="mosaic_webhook_receive"`
**MUST_CONTAIN:** `order.cancelled`
**MUST_CONTAIN:** `get_data(as_text=True)` — canonical Frappe JSON parse (BLOCKER 4)
**MUST_CONTAIN:** `json.JSONDecodeError` — explicit parse error handling, no silent mode (BLOCKER 4)
**MUST_CONTAIN:** `cancelled_at IS NULL` — idempotency guard in WHERE clause
**MUST_CONTAIN:** `order_status = 'CANCELLED'` — webhook owns this transition, poller never sees the row again after cancel
**MUST_CONTAIN:** `sentry_sdk.capture_exception` or `frappe.log_error` — Supabase failure path (HIGH 8)
**MUST_NOT_CONTAIN:** `frappe.request.get_json` — this API doesn't exist in BEI codebase (BLOCKER 4)
**MUST_NOT_CONTAIN:** `silent=True` — masks JSON parse errors, forbidden (BLOCKER 4)

Full skeleton (the executing agent should treat this as the target, refining only where indicated):

```python
"""Mosaic POS webhook receiver — handles order.cancelled events.

Per S169 plan: the webhook handler is the ONLY writer of `cancelled_at` and
`cancellation_reason` columns on pos_orders (along with the nightly verify
script's tombstone_extras path). The hourly poller never touches these
columns — see Design Rationale decision #9 for the full rationale.

When a cancel event arrives, this handler:
  1. Parses the JSON body using the canonical BEI pattern (get_data + json.loads)
  2. Optionally verifies the webhook signature or does a round-trip confirm
     against Mosaic's direct-ID endpoint (expects 404 on a cancelled order)
  3. Atomically updates the pos_orders row: cancelled_at + cancellation_reason
     + order_status='CANCELLED', guarded by WHERE cancelled_at IS NULL
  4. Returns HTTP 200 on success, HTTP 500 on Supabase failure (so Mosaic retries)

See docs/plans/2026-04-07-sprint-169-mosaic-order-lifecycle-tombstone-webhook.md
"""
import json
from datetime import datetime, timezone

import frappe
from frappe import _

from hrms.utils.sentry import set_backend_observability_context
from hrms.utils.supabase import supabase_query_sql  # Phase 3 T3.1 creates this


@frappe.whitelist(allow_guest=True, methods=["POST"])
def receive():
    """Handle inbound Mosaic webhooks (primarily order.cancelled).

    Returns:
        dict with `ok: bool` and either `handled: bool` + `order_id` on success
        or `reason` + optional error fields on failure.
    """
    # DM-7: observability context MUST be the first meaningful line
    set_backend_observability_context(
        module="sync_verification",
        action="mosaic_webhook_receive",
        mutation_type="update",
    )

    # BLOCKER 4 fix: use canonical BEI JSON parse pattern (see hrms/api/esignature.py:55-60)
    # DO NOT use frappe.request.get_json() — it does not exist in this codebase (zero grep matches)
    raw_body = frappe.request.get_data(as_text=True)
    try:
        payload = json.loads(raw_body) if raw_body else {}
    except json.JSONDecodeError as e:
        frappe.log_error(
            title="Mosaic webhook invalid JSON",
            message=f"body_snippet={raw_body[:200]} error={e}",
        )
        frappe.local.response.http_status_code = 400
        return {"ok": False, "reason": "invalid_json"}

    event = (payload.get("event") or "").strip()
    data = payload.get("data") or {}

    if event != "order.cancelled":
        # We only subscribe to order.cancelled. Any other event is a mis-registration.
        return {"ok": True, "handled": False, "reason": f"ignored event: {event}"}

    order_id = data.get("id")
    if not order_id:
        return {"ok": False, "reason": "missing order id"}

    # Phase 0 T0.5 determines which auth path we're in.
    # Path A (if Mosaic signs): verify HMAC signature from header
    # Path B (if Mosaic does not sign): round-trip confirm — call GET /api/v1/orders/{id}
    #                                    and only proceed if Mosaic returns HTTP 404.
    if not _authenticate_webhook(order_id, data):
        frappe.log_error(
            title="Mosaic webhook auth failed",
            message=f"order_id={order_id} event={event}",
        )
        frappe.local.response.http_status_code = 401
        return {"ok": False, "reason": "auth_failed"}

    # Prefer Mosaic's authoritative timestamp over our wall-clock fallback
    cancelled_at = data.get("cancelled_at") or datetime.now(timezone.utc).isoformat()
    reason = (data.get("cancellation_reason") or "mosaic_webhook_missing_reason")[:500]

    # HIGH 8 fix: wrap Supabase write in try/except, return 500 on failure so
    # Mosaic retries instead of silently marking the event delivered
    try:
        result = supabase_query_sql(
            """
            UPDATE pos_orders
               SET cancelled_at = %s,
                   cancellation_reason = %s,
                   order_status = 'CANCELLED'
             WHERE id = %s
               AND cancelled_at IS NULL
            RETURNING id, location_id, business_date
            """,
            (cancelled_at, reason, order_id),
        )
    except Exception as e:
        # Observability: frappe.log_error feeds Sentry via the hrms monkey-patch
        frappe.log_error(
            title="Mosaic webhook Supabase UPDATE failed",
            message=f"order_id={order_id} cancelled_at={cancelled_at} error={str(e)[:500]}",
        )
        frappe.local.response.http_status_code = 500
        return {"ok": False, "reason": "supabase_update_failed", "order_id": order_id}

    if not result:
        # Either: (a) already tombstoned by a prior webhook/verify run, or (b) order_id
        # does not exist in pos_orders (e.g. pre-sync row). Both are idempotent no-ops.
        return {
            "ok": True,
            "handled": False,
            "reason": "already_tombstoned_or_not_found",
            "order_id": order_id,
        }

    row = result[0]
    frappe.logger().info(
        f"S169 mosaic webhook: tombstoned order_id={order_id} "
        f"loc={row['location_id']} date={row['business_date']} reason={reason[:60]}"
    )
    return {"ok": True, "handled": True, "order_id": order_id}


def _authenticate_webhook(order_id: int, data: dict) -> bool:
    """Verify the webhook is really from Mosaic.

    Path A (if Mosaic signs): read the signature header, compute HMAC over the
    raw body, constant-time compare. Return True on match.

    Path B (if Mosaic does not sign): round-trip confirm. Call GET /api/v1/orders/{id}
    on Mosaic using the credential group matched by data.location_id. Return True
    if Mosaic returns HTTP 404 (confirming the order was really cancelled).

    Phase 0 T0.5 resolves which path this repo takes. The probe result is
    documented in output/l3/s169/webhook_signing_probe.md and this function
    reads the result at runtime from a Frappe bench config value.
    """
    # Implementation lands in Phase 3 T3.3 after T0.5 determines the auth model
    raise NotImplementedError("Phase 3 T3.3 — pending T0.5 probe result")
```

Key changes from the draft skeleton (per audit):
- **BLOCKER 4:** `json.loads(get_data(as_text=True))` replaces the non-existent `frappe.request.get_json(...)`. Explicit `json.JSONDecodeError` handling with HTTP 400 response.
- **HIGH 8:** try/except around Supabase call returns HTTP 500 for Mosaic retry; `frappe.log_error` feeds Sentry.
- **Architecture #9:** webhook is the ONLY writer of `cancelled_at`/`cancellation_reason`. Also sets `order_status='CANCELLED'` atomically (the poller won't see the row again after this).
- **Top-level import:** `from hrms.utils.supabase import supabase_query_sql` is at the top, NOT inline inside `receive()` (design-review M4).
- **`_authenticate_webhook` helper:** extracted so Phase 3 T3.3 has a single function to implement after T0.5.
- **Reason default:** `"mosaic_webhook_missing_reason"` makes BI queries discoverable — BI can filter `WHERE cancellation_reason LIKE 'mosaic_webhook%'` to find auto-tombstones vs manual.
- **Timestamp preference:** Mosaic's `data.cancelled_at` is preferred (authoritative); wall-clock fallback only if absent (design-review M2).

### 3. `hrms/utils/supabase.py` (NEW — canonical PostgREST + Management API helper, ~120 lines)

**MUST_MODIFY:** `hrms/utils/supabase.py`
**MUST_CONTAIN:** `import requests`
**MUST_CONTAIN:** `def get_service_key(`
**MUST_CONTAIN:** `def supabase_headers(`
**MUST_CONTAIN:** `def supabase_get(`
**MUST_CONTAIN:** `def supabase_patch(`
**MUST_CONTAIN:** `def supabase_query_sql(`
**MUST_CONTAIN:** `https://api.supabase.com/v1/projects/csnniykjrychgajfrgua/database/query` — Management API URL for SQL-based writes
**MUST_NOT_CONTAIN:** `import psycopg2` — BLOCKER 5 fix, we do NOT use psycopg2 in this codebase
**MUST_NOT_CONTAIN:** `psycopg2` (anywhere in file) — doubled check, BLOCKER 5

**Purpose and positioning (BLOCKER 5 fix):** This module is the canonical Supabase access layer for Frappe-side Python code. It mirrors the shape already used ad-hoc in `hrms/api/sales_dashboard.py:168-199` (`_get_supabase_url`, `_get_supabase_service_key`, `_supabase_headers`, `_supabase_get`), but exposes them as a single importable module so future sprints can migrate the 4 existing parallel copies (`sales_dashboard.py`, `discount_abuse.py`, `marketing_giveaways.py`, `store_order_demand_snapshot.py`) to a single source of truth. **The migration itself is OUT of scope for S169** — DO NOT touch those 4 files. Just create the new helper and wire the webhook endpoint to it.

**Why PostgREST + `requests`, not psycopg2:**
- All 4 existing BEI Supabase consumers use `requests` + PostgREST. None use psycopg2.
- PostgREST is already reachable from `hq.bebang.ph` via the Supabase project URL; no new network path or connection pooling to worry about.
- The Supabase Management API handles DDL and complex transactions that PostgREST can't express cleanly (the `supabase_query_sql` helper below wraps it).
- `psycopg2` would require direct DB connection credentials (5432) and connection pooling — extra attack surface, extra failure modes, no existing BEI precedent.

**Skeleton (the executing agent should treat this as the target):**

```python
"""Canonical Supabase access layer for Frappe-side Python code (S169).

Mirrors the shape used ad-hoc in hrms/api/sales_dashboard.py:168-199.
Future sprints migrate sales_dashboard.py, discount_abuse.py, marketing_giveaways.py,
and store_order_demand_snapshot.py to import from here.

Uses PostgREST for normal CRUD and the Supabase Management API for DDL / complex UPDATEs.
Never uses psycopg2 — by design, mirrors existing BEI patterns.
"""
import os
from typing import Any, Optional

import requests

import frappe

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://csnniykjrychgajfrgua.supabase.co")
SUPABASE_MGMT_URL = "https://api.supabase.com/v1/projects/csnniykjrychgajfrgua/database/query"


def get_service_key() -> str:
    """Return the Supabase service role key.

    Source order:
      1. Environment variable SUPABASE_SERVICE_ROLE_KEY
      2. Frappe bench config `supabase_service_role_key`
      3. Doppler fallback (local dev only)
    """
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if key:
        return key
    key = frappe.conf.get("supabase_service_role_key", "").strip()
    if key:
        return key
    # Local dev fallback via Doppler — safe because Doppler CLI requires auth
    try:
        import subprocess
        result = subprocess.run(
            ["doppler", "secrets", "get", "SUPABASE_SERVICE_ROLE_KEY",
             "--plain", "--project", "bei-erp", "--config", "dev"],
            capture_output=True, text=True, timeout=10,
            creationflags=0x08000000 if os.name == "nt" else 0,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    frappe.throw("SUPABASE_SERVICE_ROLE_KEY not available")


def get_mgmt_token() -> str:
    """Return the Supabase Management API token (for DDL / complex SQL)."""
    token = os.environ.get("SUPABASE_MGMT_TOKEN", "").strip()
    if token:
        return token
    token = frappe.conf.get("supabase_mgmt_token", "").strip()
    if token:
        return token
    frappe.throw("SUPABASE_MGMT_TOKEN not available")


def supabase_headers(prefer: Optional[str] = None) -> dict:
    """Return PostgREST headers with the service role key."""
    key = get_service_key()
    h = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    if prefer:
        h["Prefer"] = prefer
    return h


def supabase_get(path: str, params: Optional[dict] = None, timeout: int = 15) -> Any:
    """GET against PostgREST. Returns parsed JSON."""
    url = f"{SUPABASE_URL}/rest/v1/{path.lstrip('/')}"
    r = requests.get(url, headers=supabase_headers(), params=params, timeout=timeout)
    r.raise_for_status()
    return r.json()


def supabase_patch(path: str, params: dict, body: dict, timeout: int = 15) -> Any:
    """PATCH against PostgREST (for column-scoped UPDATEs on a filtered set)."""
    url = f"{SUPABASE_URL}/rest/v1/{path.lstrip('/')}"
    r = requests.patch(
        url,
        headers=supabase_headers(prefer="return=representation"),
        params=params,
        json=body,
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()


def supabase_query_sql(sql: str, params: tuple = ()) -> list[dict]:
    """Execute arbitrary SQL via the Supabase Management API.

    Use this for DDL, RETURNING clauses, or transactional UPDATEs that PostgREST can't
    express cleanly. Returns a list of row dicts.

    Note: Management API does NOT support parameterized queries in the same way psycopg2
    does — we substitute here using safe-quote inlining. For user-input data use PostgREST
    PATCH with filter params instead.
    """
    # Safe substitution for the webhook UPDATE case
    if params:
        # Very narrow use case: the webhook has fixed-shape params (str, str, int)
        # Escape single quotes and wrap strings
        safe_args = []
        for p in params:
            if isinstance(p, str):
                safe_args.append("'" + p.replace("'", "''") + "'")
            elif p is None:
                safe_args.append("NULL")
            else:
                safe_args.append(str(int(p)))  # only int types beyond str/None in our use case
        sql_filled = sql
        # naive %s replacement — OK because our only caller passes tuple of known types
        for arg in safe_args:
            sql_filled = sql_filled.replace("%s", arg, 1)
    else:
        sql_filled = sql

    r = requests.post(
        SUPABASE_MGMT_URL,
        headers={
            "Authorization": f"Bearer {get_mgmt_token()}",
            "Content-Type": "application/json",
        },
        json={"query": sql_filled},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()
```

**Known limitation of this helper:** the naive `%s` substitution in `supabase_query_sql` is ONLY safe because the S169 webhook caller passes a known-shape tuple of (cancelled_at ISO timestamp, cancellation_reason short text, order_id int). For broader use, callers MUST use `supabase_patch()` or `supabase_get()` with PostgREST filter params. Document this loudly in the docstring and add a TODO for a follow-up sprint to properly parameterize Management API calls if more consumers adopt this module.

### 4. `data/POS_Extraction/MOSAIC_WEBHOOK_REGISTRATIONS.csv` (NEW)

CSV audit trail of webhook registrations:
```
credential_group,client_id,webhook_id,url,events,registered_at
Araneta Group (3 stores),a080acf5-22e9-4c80-bfb5-14a96147dc70,<returned_id>,https://hq.bebang.ph/api/method/hrms.api.mosaic_webhook.receive,order.cancelled,2026-04-07T...
...12 rows total
```

---

## Files to Modify

### 1. `scripts/sync_pos_to_supabase.py` — `map_order()` fix (BLOCKER 1 architecture)

**MUST_MODIFY:** `scripts/sync_pos_to_supabase.py`
**MUST_CONTAIN:** `"payment_status":` with `order.get("payment_status")` AND explicit `None` fallback (see replacement below)
**MUST_CONTAIN:** `"order_status": order.get("order_status"),`
**MUST_CONTAIN:** `"completed_at": order.get("completed_at"),`
**MUST_NOT_CONTAIN:** `(order.get("payment_status") or "PAID")` — the old hardcode that caused the problem
**MUST_NOT_CONTAIN:** `"cancelled_at": order.get` — BLOCKER 1 architecture constraint: the poller does not write this column
**MUST_NOT_CONTAIN:** `"cancellation_reason": order.get` — BLOCKER 1 architecture constraint: the poller does not write this column

The fix is in `map_order()` at line 379. Current line 401:
```python
"payment_status": (order.get("payment_status") or "PAID").upper(),
```

**Correct replacement (post-audit v2):**
```python
# Poller-owned lifecycle fields (see S169 Design Rationale decision #9).
# DO NOT add cancelled_at or cancellation_reason here — the webhook and nightly
# verify script are the ONLY writers of those columns. Adding them here would
# make every hourly poll NULL out the webhook's tombstones via PostgREST
# merge-duplicates upsert semantics (verified at scripts/sync_pos_to_supabase.py:187).
_payment_status_raw = order.get("payment_status")
_payment_status = _payment_status_raw.upper() if isinstance(_payment_status_raw, str) and _payment_status_raw else None

# ... inside the map_order return dict ...
"payment_status": _payment_status,
"order_status": (order.get("order_status") or "").upper() or None,
"completed_at": order.get("completed_at"),
```

**Rationale (post-audit):**
- Don't hardcode `'PAID'` — that was the whole point. Real values include `PAID`, `PENDING`, `UNPAID`, `PARTIAL`, etc. depending on Mosaic's current lifecycle state.
- Explicit `None` fallback — if Mosaic really omits the field, the Supabase column (nullable) gets NULL, not a bogus default.
- **`cancelled_at` and `cancellation_reason` are NOT in the dict.** The poller never writes these. Enforced by `MUST_NOT_CONTAIN` assertions.
- `order_status` is uppercased and NULL-fallbacked for consistency with `payment_status`.
- `completed_at` is passed through as-is (ISO 8601 string from Mosaic).

**HARD BLOCKER (snapshot regression check):** Before editing this file, the agent MUST produce `output/l3/s169/map_order_snapshot_before.json` by running `map_order()` on a sample Mosaic order (fetched live via `fetch_all_orders` for SM Megamall 2026-04-04 LIMIT 1). After editing, produce `_after.json` with the same input. Commit both. The after-snapshot MUST:
- Include keys: `order_status`, `completed_at`, corrected `payment_status`
- EXCLUDE keys: `cancelled_at`, `cancellation_reason` (NOT present in the dict at all — not even as `None`)

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

### 3. Supabase views — wrapper-view pattern (BLOCKER 7 fix, post-audit v2)

The audit replaced the "parse and rewrite each view" approach with the **wrapper-view pattern**. This is safer (no SQL parsing), simpler (single-token find/replace per view), and leaves the existing view definitions intact except for one substitution.

**Step 1 — Create the live wrapper (single source of truth for "non-cancelled orders"):**

```sql
-- Create BEFORE disabling the workflow so the wrapper is ready when views are updated
CREATE OR REPLACE VIEW public.v_pos_orders_live AS
  SELECT * FROM public.pos_orders WHERE cancelled_at IS NULL;

COMMENT ON VIEW public.v_pos_orders_live IS
  'Canonical "live orders only" view. Filters out any row with cancelled_at set (tombstoned by Mosaic order.cancelled webhook or by verify_mosaic_pos_sync.py). All revenue reports MUST read from this view instead of pos_orders directly. See S169.';
```

**Step 2 — Disable the hourly workflow (BLOCKER 2 fence):**

```bash
# 2289454 — deploy authorization
GH_TOKEN="" gh workflow disable daily-pos-sync.yml --repo Bebang-Enterprise-Inc/hrms
```

Capture the disable confirmation in `output/l3/s169/workflow_disable_confirmation.txt`.

**Step 3 — Rewrite each of the 12 dependent views/MVs via single-token substitution.** For each object:

1. Read the current definition from `pg_views.definition` or `pg_matviews.definition`
2. Append to `tmp/s169_view_definitions_before.sql` (all 12 concatenated) — this is the rollback source
3. Apply text substitution: `FROM pos_orders` → `FROM v_pos_orders_live`, `JOIN pos_orders` → `JOIN v_pos_orders_live`. Use regex with word boundaries to avoid matching `pos_orders_items` or `pos_orders_payments`
4. Save the rewritten definition to `tmp/s169_view_definitions_after.sql`
5. Apply via transaction:
   - **Regular views:** `CREATE OR REPLACE VIEW public.<name> AS <new_def>;`
   - **Materialized views:** `BEGIN; DROP MATERIALIZED VIEW public.<name> CASCADE; CREATE MATERIALIZED VIEW public.<name> AS <new_def>; REFRESH MATERIALIZED VIEW public.<name>; COMMIT;` (CASCADE handles dependent indexes/constraints)
6. Run a sample `COUNT(*)` query pre/post and log to `output/l3/s169/view_rewrite_deltas.json`. Expected delta:
   - **0 rows** for MVs/views that don't touch SM Marikina Apr 4 (most)
   - **-3 rows** for MVs/views that aggregate Apr 4 SM Marikina orders (that's the 3 phantoms disappearing)
   - Any other delta is a RED FLAG — STOP and investigate before continuing

**The 12 objects in rewrite order** (MVs that depend on other MVs must be rewritten last — Phase 0 T0.4 `pg_depend` audit resolves this ordering and saves it to `tmp/s169_view_rewrite_order.md`):

**Materialized views (6):**
1. `public.daily_revenue`
2. `public.discount_summary`
3. `public.payment_reconciliation`
4. `public.sales_dashboard_daily_store_metrics` — the hourly-refreshed dashboard MV (was refreshed by `scripts/supabase_exec.py` before we disabled the workflow)
5. `public.store_daily_baselines` — feeds `scripts/detect_anomalies.py` — rewrite carefully, the baseline calculation must still work
6. `public.store_daily_closing`

**Regular views (6):**
7. `public.v_all_channel_daily`
8. `public.v_discount_identity_order_usage`
9. `public.v_monthly_store_summary`
10. `public.v_ops_weekly`
11. `public.v_orders` — simple pass-through; may be consumed by external tools (check Phase 0 T0.4)
12. `public.v_system_daily_totals`

**Step 4 — Build the rollback runbook:**

Concatenate `tmp/s169_view_definitions_before.sql` with a header and save as `tmp/s169_rollback_phase4.sql`:

```sql
-- S169 Phase 4 rollback — executes in reverse order of the rewrite
-- Run this if ANY view/MV post-rewrite breaks consumption
-- ETA: ~5 minutes for all 12 objects

BEGIN;
-- Drop the new wrapper-dependent versions
DROP MATERIALIZED VIEW public.store_daily_closing CASCADE;
DROP MATERIALIZED VIEW public.store_daily_baselines CASCADE;
-- ... (in reverse rewrite order)

-- Replay the originals verbatim from before the rewrite
\i tmp/s169_view_definitions_before.sql

-- Drop the wrapper (optional — it's harmless to leave it)
DROP VIEW IF EXISTS public.v_pos_orders_live;

COMMIT;
```

Commit this file to `output/l3/s169/rollback_phase4.sql` (copy of tmp) as a permanent artifact.

**Step 5 — Re-enable the workflow:**

```bash
# 2289454
GH_TOKEN="" gh workflow enable daily-pos-sync.yml --repo Bebang-Enterprise-Inc/hrms
```

**Step 6 — Verify the hourly refresh still works:**

```bash
python scripts/supabase_exec.py "select public.refresh_sales_dashboard_daily_store_metrics();"
```

Must return success within ~2 minutes. Any SQL error = rollback per `tmp/s169_rollback_phase4.sql`.

**Step 7 — Clear Frappe caches (deployment-qa MED-8):**

```bash
# 2289454
BACKEND=$(docker ps --format "{{.Names}}" | grep frappe_backend | head -1)
docker exec $BACKEND bench --site hq.bebang.ph clear-cache
```

This invalidates `hrms.api.sales_dashboard` cached responses so bei-tasks dashboards pick up the new view definitions on next request.

**HARD BLOCKER:** DO NOT proceed past Phase 4 without ALL of:
- `tmp/s169_view_definitions_before.sql` committed to git
- `tmp/s169_rollback_phase4.sql` committed to git
- `output/l3/s169/workflow_disable_confirmation.txt` + `workflow_enable_confirmation.txt`
- `output/l3/s169/view_rewrite_deltas.json` showing expected deltas per object

### 4. (merged into §3) — the wrapper-view pattern eliminates the separate "regular views" subsection
The original plan had a separate §4 for regular views. Under the wrapper-view pattern both MVs and regular views get the same 1-token substitution, so they're handled together in §3 above.

### 5. `output/l3/s169/verify_s169.py` (NEW — machine-verifiable phase gate)

Same pattern as S165's `verify_s165.py`. Fails the run if:
- Any of the `MUST_MODIFY` files lack any of the `MUST_CONTAIN` strings
- Any of the `MUST_NOT_CONTAIN` strings appear
- `git diff --name-only origin/production..HEAD` is missing any required file
- **Live Supabase check (zero-skip MED fix):** Query `pg_views.definition` / `pg_matviews.definition` for each of the 13 objects (12 originals + `v_pos_orders_live`) and assert the 12 originals contain `v_pos_orders_live` and the wrapper contains `cancelled_at IS NULL`. If the verify script runs in a context with Supabase credentials (Doppler present), it SHOULD do this. If not, it MUST log a warning and the executing agent is responsible for running the Supabase check manually.

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
    # BLOCKER 1 architecture check: poller must NOT write cancelled_at/cancellation_reason
    check_contains("scripts/sync_pos_to_supabase.py", [
        'order.get("order_status")',
        'order.get("completed_at")',
    ], forbidden=[
        '(order.get("payment_status") or "PAID")',  # the old hardcode
        '"cancelled_at": order.get',                # BLOCKER 1 — poller must not write
        '"cancellation_reason": order.get',         # BLOCKER 1 — poller must not write
    ]),
    # BLOCKER 4: canonical Frappe JSON parse pattern
    check_contains("hrms/api/mosaic_webhook.py", [
        "@frappe.whitelist(allow_guest=True",
        "set_backend_observability_context(",
        'module="sync_verification"',
        'action="mosaic_webhook_receive"',
        "order.cancelled",
        "get_data(as_text=True)",              # BLOCKER 4: canonical JSON parse
        "json.JSONDecodeError",                # BLOCKER 4: explicit error handling
        "order_status = 'CANCELLED'",          # webhook owns the state transition
        "cancelled_at IS NULL",                # idempotency guard
    ], forbidden=[
        "frappe.request.get_json",             # BLOCKER 4: this API doesn't exist
        "silent=True",                         # BLOCKER 4: don't mask parse errors
    ]),
    # BLOCKER 5: PostgREST + requests, never psycopg2
    check_contains("hrms/utils/supabase.py", [
        "import requests",
        "def supabase_headers(",
        "def supabase_query_sql(",
        "api.supabase.com/v1/projects/csnniykjrychgajfrgua/database/query",
    ], forbidden=[
        "import psycopg2",
        "psycopg2",  # doubled check — forbidden anywhere
    ]),
    # Verify script tombstone upgrade
    check_contains("scripts/verify_mosaic_pos_sync.py", [
        "cancelled_at=is.null",  # PostgREST filter syntax
        "def tombstone_extras(",
        "extras_tombstoned",
        "reconciled_from_mosaic_gap",
        "sentry_sdk.capture_exception",  # HIGH 8: tombstone error handling
    ], forbidden=[
        "DELETE FROM pos_orders",
    ]),
    # All required files on branch
    check_diff_includes("s169-mosaic-order-lifecycle-tombstone-webhook", [
        "data/supabase/migrations/2026-04-07-pos-orders-lifecycle-columns.sql",
        "scripts/sync_pos_to_supabase.py",
        "hrms/api/mosaic_webhook.py",
        "hrms/utils/supabase.py",
        "scripts/verify_mosaic_pos_sync.py",
        "scripts/s169_register_webhooks.py",
        "scripts/s169_self_induced_cancel_test.py",
        "data/POS_Extraction/MOSAIC_WEBHOOK_REGISTRATIONS.csv",
        "output/l3/s169/form_submissions.json",
        "output/l3/s169/api_mutations.json",
        "output/l3/s169/state_verification.json",
        "output/l3/s169/map_order_snapshot_before.json",
        "output/l3/s169/map_order_snapshot_after.json",
        "output/l3/s169/view_definitions_before.sql",
        "output/l3/s169/view_definitions_after.sql",
        "output/l3/s169/view_rewrite_deltas.json",
        "output/l3/s169/workflow_disable_confirmation.txt",
        "output/l3/s169/workflow_enable_confirmation.txt",
        "output/l3/s169/webhook_signing_probe.md",
        "output/l3/s169/webhook_live_test_payload.json",
        "output/l3/s169/webhook_live_test_response.json",
        "output/l3/s169/rollback_phase4.sql",
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

### Phase 0 — Pre-flight (8 units — up from 6 post-audit)

- **T0.1** — Read this plan fully. Read `scripts/sync_pos_to_supabase.py` (lines 1-100, 170-210 for `supabase_upsert`, 354-470, 499-560), `scripts/verify_mosaic_pos_sync.py` (full file), `docs/api/MOSAIC_API.md` (full file — 187 lines), `data/POS_Extraction/MOSAIC_POS_API_KEYS.csv` (all 46 rows), `hrms/api/esignature.py:55-60` (canonical JSON parse pattern), `hrms/api/sales_dashboard.py:168-199` (canonical Supabase helper shape), `output/plan-audit/s169-mosaic-order-lifecycle/verified_blockers.md` (the audit report that shaped this plan).
- **T0.2** — Create sprint branch: `git fetch origin production && git checkout -b s169-mosaic-order-lifecycle-tombstone-webhook origin/production`. Verify branch name via `git branch --show-current`.
- **T0.3** — Phantom scan: run the SQL from Ground-Truth Lock to count all phantom-void groups since 2026-01-01. Write to `tmp/s169_phantom_scan.md`. **HARD BLOCKER:** If the scan reveals >50 phantom groups (10× the single known incident), STOP and present a scope-expansion decision to Sam — a massive phantom population might indicate a different root cause than void-and-retry.
- **T0.4** — View dependency audit: `SELECT schemaname, matviewname, definition FROM pg_matviews WHERE definition ILIKE '%pos_orders%'` and same for `pg_views`. Save all 12 current definitions (regular views + MVs) to `tmp/s169_view_definitions_before.sql` AND `output/l3/s169/view_definitions_before.sql`. Also query `pg_depend` to find any view depending on another in the list, and any EXTERNAL consumer (e.g., a view in `bei-tasks/*` database or a function consuming one of these). Write rewrite order to `tmp/s169_view_rewrite_order.md`. **HARD BLOCKER:** If the audit reveals a 13th object (not in the current list of 12), or any `pg_depend` edge outside `public` schema, STOP — update the plan's hard-coded "12 objects" inventory everywhere (Phase Budget, Requirements Regression, verify_s169.py, this task list) in the same edit, then resume.
- **T0.5 (webhook signing probe) — HARD BLOCKER GATE with self-induced cancel (BLOCKER 6 fix):**
  - **Step 1 (register test webhook):** Register a test webhook pointing at `https://webhook.site/<fresh-uuid>` for ONE credential group (pick the smallest — e.g., `Dedicated` single-store group to minimize noise).
  - **Step 2 (self-induced cancel — PRIMARY test):** Write `scripts/s169_self_induced_cancel_test.py` that:
    1. Creates a real test order via `POST /api/v1/orders` with `location_id = <test store>`, a unique `bill_number` prefix (e.g., `999991` so finance can exclude), a single test product ₱1.00 gross, and a fake `ordered_at` timestamp.
    2. Immediately cancels it via `POST /api/v1/orders/{id}/cancel` with `reason = "S169 webhook signing probe test — safe to ignore"`.
    3. Waits up to 60 seconds for the webhook.site inspector to receive the event.
    4. Inspects the delivered headers and body.
    5. Cleans up: if the test order somehow persists in Supabase via hourly sync, run `scripts/s169_cleanup_test_orders.py` to tombstone the test rows.
  - **Step 3 (fallback — natural cancel):** If the self-induced cancel fails (e.g., Mosaic doesn't allow creating test orders, or the API errors), fall back to waiting for a natural cancel in prod with a **hard 30-minute time bound**. If no cancel arrives within 30 min, STOP and escalate — treat as an infrastructure blocker.
  - **Step 4 (document outcome):** Write the findings to `tmp/s169_webhook_signing_probe.md` and `output/l3/s169/webhook_signing_probe.md`. Required fields: `mosaic_signs: yes|no`, `signature_header_name: <if yes>`, `hmac_algorithm: <if yes>`, `secret_source: <if yes>`, `delivery_latency_ms: <measured>`, `sample_payload_path: <committed file>`.
  - **Step 5 (auth decision):** Based on the probe outcome:
    - If Mosaic signs → Phase 3 T3.3 implements HMAC signature verification.
    - If Mosaic does NOT sign → Phase 3 T3.3 implements the round-trip confirm fallback (call `GET /api/v1/orders/{id}` and only tombstone on HTTP 404). The probe MUST measure the round-trip latency; if >2 seconds, T3.5 MUST use `frappe.enqueue` async path.
  - **HARD BLOCKER:** This task is the whole gate for Phase 3. If the outcome is inconclusive (e.g., webhook never arrives at webhook.site AND self-induced cancel fails AND no natural cancel within 30 min), STOP and escalate to Sam. Do NOT guess the auth model.
- **T0.6** — Confirm `SENTRY_DSN` in Doppler `bei-erp/dev` (already done in S165; re-verify). Confirm `hq.bebang.ph` is publicly reachable AND resolvable from a non-BEI network (not just LAN): `curl -I https://hq.bebang.ph/api/method/ping` returns 200 or 401 (not timeout, not DNS error). If Cloudflare is in front, verify Mosaic IP ranges are allow-listed OR that the Cloudflare challenge doesn't block programmatic POSTs. Test with `curl -X POST -d '{}' https://hq.bebang.ph/api/method/hrms.api.mosaic_webhook.receive` — expected 404 (endpoint doesn't exist yet) — NOT 403 (Cloudflare challenge) or 502 (origin unreachable).
- **T0.7** — Confirm existing canonical patterns: `grep -rn "_get_supabase_service_key\|_supabase_headers" F:/Dropbox/Projects/BEI-ERP/hrms/api/sales_dashboard.py` returns lines 168-199. Read them. `grep -rn "get_data(as_text=True)" F:/Dropbox/Projects/BEI-ERP/hrms/api/esignature.py` returns lines 55-60. Read them. These are the reference shapes for `hrms/utils/supabase.py` and the webhook JSON parse respectively. If either reference file has been refactored since this plan was written, STOP and update the plan.

### Phase 1 — Schema migration (3 units)

- **T1.1** — Create `data/supabase/migrations/2026-04-07-pos-orders-lifecycle-columns.sql` with the full SQL from "Files to Create" §1.
- **T1.2** — Apply via Supabase Management API. Capture the response. Verify all 4 new columns via `information_schema.columns`. Verify the new `sync_verification` CHECK constraint via `pg_get_constraintdef`.
- **T1.3** — Verify the partial index exists: `SELECT indexname FROM pg_indexes WHERE tablename='pos_orders' AND indexname='idx_pos_orders_cancelled_at_not_null'`.

### Phase 2 — Fix `map_order()` (5 units — up from 4 post-audit)

- **T2.1** — Pre-edit snapshot: write `tmp/s169_map_order_probe.py` that imports `sync_pos_to_supabase.map_order` and runs it on a real Mosaic order JSON (fetched live via `fetch_all_orders` for SM Megamall 2026-04-04 LIMIT 1). Save output to `output/l3/s169/map_order_snapshot_before.json`. **HARD BLOCKER:** If this fails, STOP — can't verify the fix without a before baseline.
- **T2.2** — Edit `scripts/sync_pos_to_supabase.py:379-433` (`map_order` function): update the return dict per "Files to Modify" §1. Add ONLY `order_status` and `completed_at` (plus fix `payment_status`). DO NOT add `cancelled_at` or `cancellation_reason` — that is the BLOCKER 1 fix. Do NOT touch `map_order_items()` or `map_order_payments()`.
- **T2.3** — Post-edit snapshot: re-run `tmp/s169_map_order_probe.py`, save to `output/l3/s169/map_order_snapshot_after.json`. Diff before vs after:
  - **Keys that MUST appear:** `order_status`, `completed_at`
  - **Keys that MUST BE ABSENT:** `cancelled_at`, `cancellation_reason`
  - **`payment_status` value** MUST be the real value from the Mosaic response (e.g., `"PAID"`, `"PENDING"`, or `None`), not a hardcoded default
  - Any other key diff (unexpected addition or removal) = STOP and investigate
- **T2.4** — Run `python output/l3/s169/verify_s169.py` — the `scripts/sync_pos_to_supabase.py` assertions (MUST_CONTAIN `order.get("order_status")`, MUST_NOT_CONTAIN `"cancelled_at": order.get`, MUST_NOT_CONTAIN the PAID hardcode) must all pass. **HARD BLOCKER:** If any fail, fix before proceeding.
- **T2.5** — Local sanity test: run the existing sync script with `--date 2026-04-04 --store 2338` (SM Megamall — low-risk, well-understood baseline). Confirm no import errors, no runtime regressions, and the resulting Supabase row for a sample order has the new `order_status` and `completed_at` populated (via a targeted `SELECT`).

### Phase 3 — Webhook endpoint (8 units — up from 6 post-audit)

- **T3.1 (BLOCKER 5 fix)** — Create `hrms/utils/supabase.py` per "Files to Create" §3. Use PostgREST + `requests`, mirroring `hrms/api/sales_dashboard.py:168-199` shape. Expose: `get_service_key`, `get_mgmt_token`, `supabase_headers`, `supabase_get`, `supabase_patch`, `supabase_query_sql`. **HARD BLOCKER:** No `import psycopg2`. No `psycopg2` anywhere in the file. `verify_s169.py` enforces this — run it after this task and fix any FAIL.
- **T3.2 (BLOCKER 4 fix)** — Create `hrms/api/mosaic_webhook.py` per "Files to Create" §2 (full skeleton). Key constraints:
  - `set_backend_observability_context(module="sync_verification", action="mosaic_webhook_receive", mutation_type="update")` MUST be the first meaningful line after the function def.
  - JSON parse MUST use `frappe.request.get_data(as_text=True) + json.loads()` with explicit `except json.JSONDecodeError` — NOT `frappe.request.get_json(...)` which doesn't exist in this codebase.
  - Supabase call wrapped in try/except that returns HTTP 500 on failure (so Mosaic retries).
  - Atomic UPDATE sets all three: `cancelled_at`, `cancellation_reason`, `order_status='CANCELLED'`.
  - Idempotency guard `WHERE cancelled_at IS NULL`.
  - `_authenticate_webhook()` helper is stubbed with `NotImplementedError` — T3.3 fills it in.
- **T3.3 (depends on T0.5 outcome)** — Implement `_authenticate_webhook(order_id, data)`:
  - **Path A (if T0.5 probe reported Mosaic signs):** read the signature header (name from probe), compute HMAC-SHA256 (or whichever algorithm the probe identified) over the raw body using the shared secret from Doppler key `MOSAIC_WEBHOOK_SECRET`, constant-time compare via `hmac.compare_digest`. Return True on match.
  - **Path B (if T0.5 probe reported Mosaic does NOT sign):** round-trip confirm. Use the credential group matched by `data.location_id` (look up in `MOSAIC_POS_API_KEYS.csv`), `ensure_token` for OAuth, call `GET /api/v1/orders/{order_id}`, return True if HTTP 404 (confirms the order was really cancelled). Any other status (200, 500, timeout) = return False, which causes T3.2's handler to return HTTP 401 and log the event.
  - **HARD BLOCKER:** If T0.5 probe was inconclusive, STOP. Do not write a "default allow" path.
- **T3.4** — Idempotent UPDATE call via `supabase_query_sql`:
  ```sql
  UPDATE pos_orders
     SET cancelled_at = %s,
         cancellation_reason = %s,
         order_status = 'CANCELLED'
   WHERE id = %s
     AND cancelled_at IS NULL
  RETURNING id, location_id, business_date
  ```
  If `RETURNING` is empty, the row is already tombstoned or doesn't exist — return `{"ok": true, "handled": false, "reason": "already_tombstoned_or_not_found"}` (idempotent no-op, NOT an error).
- **T3.5** — Latency budget enforcement. If T0.5 measured round-trip confirm latency >2 seconds, T3.2 MUST wrap the entire handler body in `frappe.enqueue('hrms.api.mosaic_webhook._process_cancel_async', ...)` and return `{"ok": true, "queued": true, "order_id": order_id}` immediately. The async worker does the auth + UPDATE. **HARD BLOCKER:** If any sync path exceeds 5s during T3.6 testing, MUST switch to async regardless of T0.5 latency.
- **T3.6** — Local/dev sanity test: Use `/local-frappe` skill OR a dev Frappe site to POST a test payload to the endpoint. Three test cases:
  1. Valid `order.cancelled` payload with a real order ID → expect `{"ok": true, "handled": true}` (if the order exists in Supabase) or `{"ok": true, "handled": false, "reason": "already_tombstoned_or_not_found"}` (if not).
  2. Invalid JSON body → expect HTTP 400 `{"ok": false, "reason": "invalid_json"}`.
  3. `event: "order.created"` (wrong event) → expect `{"ok": true, "handled": false, "reason": "ignored event: order.created"}`.
  Save all 3 request/response pairs to `output/l3/s169/webhook_test_payload.json` + `webhook_test_response.json` as a JSON array.
- **T3.7 (HIGH 8 verify)** — Inject a fault: temporarily make `supabase_query_sql` raise an exception (e.g., `raise Exception("test fault")` at the top of the function). POST a valid payload. Verify:
  1. Response is HTTP 500
  2. Response body is `{"ok": false, "reason": "supabase_update_failed", "order_id": <id>}`
  3. `frappe.log_error` was called (check via `SELECT * FROM tabError Log WHERE title = 'Mosaic webhook Supabase UPDATE failed' ORDER BY creation DESC LIMIT 1` in bench console)
  4. Sentry breadcrumb recorded (check Sentry UI for `bei-hrms` project)
  Remove the fault, run T3.6 again to confirm the happy path still works. Save fault-injection evidence to `output/l3/s169/webhook_fault_injection.json`.
- **T3.8** — Deploy the new endpoint to production via `/deploy-frappe`. **Deploy flags required:** `skip_build=false`, `no_cache=true` (new Python file requires a full rebuild; Frappe caches discovered `@frappe.whitelist()` endpoints). This is a user-mediated deploy — agent creates PR and waits. **Phase 3 does NOT complete until the deployed endpoint is reachable at `https://hq.bebang.ph/api/method/hrms.api.mosaic_webhook.receive`**, verified via `curl -X POST https://hq.bebang.ph/api/method/hrms.api.mosaic_webhook.receive -H "Content-Type: application/json" -d '{"event":"ping"}'` returning HTTP 200 with `{"ok": true, "handled": false, ...}`.

### Phase 4 — Wrapper-view pattern (12 units — up from 10 post-audit for cron fence + rollback)

**Strategy (BLOCKER 7 fix):** Use the wrapper-view pattern from "Files to Modify" §3. Instead of parsing and rewriting each view's body, create a single `v_pos_orders_live` wrapper, then do a single-token `FROM pos_orders` → `FROM v_pos_orders_live` substitution on each of the 12 dependent objects.

- **T4.0 (BLOCKER 2 fix — cron fence open)** — Disable the hourly workflow BEFORE any view mutation: `GH_TOKEN="" gh workflow disable daily-pos-sync.yml --repo Bebang-Enterprise-Inc/hrms`. Capture stdout to `output/l3/s169/workflow_disable_confirmation.txt`. Verify via `GH_TOKEN="" gh workflow view daily-pos-sync.yml --repo Bebang-Enterprise-Inc/hrms --json state` returning `"state": "disabled_manually"`. **HARD BLOCKER:** If the disable call fails, STOP. Do not proceed.
- **T4.1 (wrapper view creation)** — Run via Supabase Management API:
  ```sql
  CREATE OR REPLACE VIEW public.v_pos_orders_live AS
    SELECT * FROM public.pos_orders WHERE cancelled_at IS NULL;
  COMMENT ON VIEW public.v_pos_orders_live IS '...';  -- per Files to Modify §3
  ```
  Verify via `SELECT COUNT(*) FROM v_pos_orders_live` returns `(SELECT COUNT(*) FROM pos_orders WHERE cancelled_at IS NULL)`.
- **T4.2 (build the substitution + rollback SQL)** — For each of the 12 objects, read its current definition from `pg_views` / `pg_matviews`. Apply regex substitution: `\bFROM\s+pos_orders\b` → `FROM v_pos_orders_live`, `\bJOIN\s+pos_orders\b` → `JOIN v_pos_orders_live`. Word boundaries protect against matching `pos_orders_items` or `pos_orders_payments`. Save rewritten definitions to `tmp/s169_view_definitions_after.sql` (concatenated, in rewrite order). Also build `tmp/s169_rollback_phase4.sql` by concatenating `tmp/s169_view_definitions_before.sql` with a rollback header. Copy both to `output/l3/s169/`.
- **T4.3 — T4.8 (regular views — CREATE OR REPLACE)** — For each of the 6 regular views (`v_all_channel_daily`, `v_discount_identity_order_usage`, `v_monthly_store_summary`, `v_ops_weekly`, `v_orders`, `v_system_daily_totals`), run `CREATE OR REPLACE VIEW public.<name> AS <rewritten_def>;`. Immediately after each, run a sample `COUNT(*)` query and log the delta to `output/l3/s169/view_rewrite_deltas.json`. Expected delta: 0 (none of these aggregate Apr 4 SM Marikina specifically). Any non-zero delta = STOP and investigate.
- **T4.9 — T4.14 (materialized views — DROP + CREATE + REFRESH)** — For each of the 6 MVs in rewrite order from T0.4, wrap in a transaction:
  ```sql
  BEGIN;
  DROP MATERIALIZED VIEW public.<name> CASCADE;
  CREATE MATERIALIZED VIEW public.<name> AS <rewritten_def>;
  REFRESH MATERIALIZED VIEW public.<name>;
  COMMIT;
  ```
  If the MV had a unique index in its original definition, recreate it. Log sample `COUNT(*)` delta to `view_rewrite_deltas.json`. Expected:
  - `daily_revenue`, `discount_summary`, `payment_reconciliation`, `store_daily_closing`, `v_all_channel_daily` → delta 0 or -3 depending on whether Apr 4 SM Marikina is in the active window
  - `sales_dashboard_daily_store_metrics` → delta -3 (aggregates last 7 days, includes Apr 4)
  - `store_daily_baselines` → delta depends on baseline window; verify against `scripts/detect_anomalies.py` expectations
  Any unexpected delta = STOP and investigate.
- **T4.15 (sales-dashboard refresh function smoke test)** — After all 12 objects rewritten, run `python scripts/supabase_exec.py "select public.refresh_sales_dashboard_daily_store_metrics();"`. Must return success within ~2 minutes. Any SQL error = rollback per `tmp/s169_rollback_phase4.sql` and STOP.
- **T4.16 (BLOCKER 2 fix — cron fence close)** — Re-enable workflow: `GH_TOKEN="" gh workflow enable daily-pos-sync.yml --repo Bebang-Enterprise-Inc/hrms`. Capture stdout to `output/l3/s169/workflow_enable_confirmation.txt`. Verify next scheduled cron run lands (wait up to 1 hour OR manually trigger via `gh workflow run` with `skip_verify=true skip_anomaly=true` to fast-test).
- **T4.17 (Frappe cache clear — deployment-qa MED-8)** — Inside the production Frappe container via SSM:
  ```bash
  # 2289454
  BACKEND=$(docker ps --format "{{.Names}}" | grep frappe_backend | head -1)
  docker exec $BACKEND bench --site hq.bebang.ph clear-cache
  ```
  This invalidates the cached `hrms.api.sales_dashboard` responses so bei-tasks dashboards pick up the new view definitions. Save confirmation to `output/l3/s169/bench_clear_cache_confirmation.txt`.
- **T4.18 (Phase 4 closeout)** — Commit `tmp/s169_view_definitions_before.sql`, `tmp/s169_view_definitions_after.sql`, `tmp/s169_rollback_phase4.sql` to `output/l3/s169/` (copies for permanent audit). Run `python output/l3/s169/verify_s169.py` — all Phase 4 assertions must pass. If any fail, do NOT proceed to Phase 5.
- **T4.2** — Save the rewritten definitions to `tmp/s169_view_definitions_after.sql` and `output/l3/s169/view_definitions_after.sql`. Manual review: does each rewrite preserve intent?
- **T4.3 — T4.8** — For each of the 6 MVs (one task each), in rewrite order from T0.4:
  - `BEGIN; DROP MATERIALIZED VIEW <name>; CREATE MATERIALIZED VIEW <name> AS <new_def>; COMMIT;`
  - `REFRESH MATERIALIZED VIEW CONCURRENTLY <name>` (if unique index exists; else plain REFRESH)
  - Run a sample count query pre/post; log delta
- **T4.9** — For each of the 6 regular views: `CREATE OR REPLACE VIEW <name> AS <new_def>;`. Sample count query pre/post.
- **T4.10** — Run the sales-dashboard refresh function: `python scripts/supabase_exec.py "select public.refresh_sales_dashboard_daily_store_metrics();"`. Must succeed without errors.

### Phase 5 — 30-day backfill (5 units)

- **T5.0 (ordering resolved per audit)** — Phase 5 backfill runs AFTER Phase 4 completes AND the workflow is re-enabled. The existing hourly cron will be running concurrently with the backfill. Per audit deployment-qa HIGH-5: the `sync_progress` table handles (loc, date) concurrency — two jobs writing the same row is safe because it's an upsert on `id`. Document this in the execution log.
- **T5.1** — Calculate the date range: `date_from = today - 30 days`, `date_to = yesterday PHT` (matches S165 HW4 rule for "no today").
- **T5.2** — Run `python scripts/sync_pos_to_supabase.py --from <date_from> --to <date_to> --parallel`. Expected runtime: ~30-60 minutes (rate-limited). Monitor for errors. The existing `scripts/sync_pos_to_supabase.py:241 get_completed_store_days()` provides resume-on-interrupt behavior — if the backfill fails mid-run, restarting re-reads completed days from `sync_progress` and skips them.
- **T5.3** — Verify the new `map_order` output populated the lifecycle columns: `SELECT COUNT(DISTINCT payment_status) FROM pos_orders WHERE business_date >= '<date_from>'` must return >1 (proves we're reading real values now, not just the hardcoded 'PAID'). Also: `SELECT COUNT(*) FROM pos_orders WHERE business_date >= '<date_from>' AND order_status IS NOT NULL` must be > 0 (proves the new poller-owned column is populated).
- **T5.4** — Verify `cancelled_at` is still NULL for all re-synced rows (the list endpoint only returns completed orders, so no cancelled_at should be set by sync — the webhook and verify safety net do that). `SELECT COUNT(*) FROM pos_orders WHERE business_date >= '<date_from>' AND cancelled_at IS NOT NULL` must be 0 immediately after backfill (webhook/verify not yet run in Phase 8). This is the BLOCKER 1 post-verification — confirms the poller never writes `cancelled_at`.
- **T5.5** — Spot-check 5 random store-days: sample `SELECT payment_status, COUNT(*) FROM pos_orders WHERE location_id=X AND business_date=Y GROUP BY payment_status`. Expect mostly `PAID` but with some variation (e.g., `PENDING` for in-flight orders that were later completed).

### Phase 6 — Verify script upgrade (8 units — up from 6 post-audit for HIGH 8 error handling)

- **T6.1** — Update `supabase_count()` in `scripts/verify_mosaic_pos_sync.py` to append `cancelled_at=is.null` to PostgREST params. Example:
  ```python
  params = {
      "location_id": f"eq.{location_id}",
      "business_date": f"eq.{business_date}",
      "select": "id",
      "cancelled_at": "is.null",  # BLOCKER 1 split-ownership — only count live rows
  }
  ```
- **T6.2** — Add new `tombstone_extras(client, cred, loc_id, ds, supabase_extra_ids, mosaic_ids)` function. Signature:
  ```python
  def tombstone_extras(
      client: httpx.Client,
      cred: dict,
      loc_id: int,
      ds: str,
      supabase_ids: set[int],
      mosaic_ids: set[int],
  ) -> tuple[list[int], list[tuple[int, str]]]:
      """Tombstone rows in Supabase that Mosaic no longer acknowledges.

      For each ID in (supabase_ids - mosaic_ids), call GET /api/v1/orders/{id}
      on Mosaic. If the lookup returns HTTP 404, the order was really cancelled —
      tombstone it via supabase_query_sql UPDATE. If the lookup returns anything
      else, leave the row alone and add it to the "unconfirmed" list.

      Returns:
          (tombstoned_ids, unconfirmed_ids_with_reason)
      """
  ```
- **T6.3** — Execute the tombstone via Supabase Management API (the script already imports from sync_pos_to_supabase, which has `_supabase_headers` — reuse or extract). For each confirmed-gone ID:
  ```sql
  UPDATE pos_orders
     SET cancelled_at = NOW(),
         cancellation_reason = 'reconciled_from_mosaic_gap',
         order_status = 'CANCELLED'
   WHERE id = %s
     AND cancelled_at IS NULL
  ```
  Batch multiple IDs via `WHERE id = ANY(%s::int[])` to reduce round-trips.
- **T6.4 (HIGH 8 fix)** — Wrap the tombstone UPDATE in try/except. On Supabase failure: `sentry_sdk.capture_exception(e)`, log to stdout with prefix `[TOMBSTONE_ERROR]`, mark the affected rows as `status='unresolved'` in `sync_verification` (NOT `extras_tombstoned`), and escalate via the existing Chat alert path. Do NOT swallow the exception silently. Do NOT proceed to mark rows as tombstoned without a successful UPDATE.
- **T6.5** — Update `_process_group` `extra` branch: call `tombstone_extras`, set row status to `extras_tombstoned` for confirmed-gone IDs + `heal_attempted = TRUE`. Post-tombstone, re-run `supabase_count()` (now filtered on `cancelled_at IS NULL`) and verify it equals `mosaic_total`. If yes, status is `extras_tombstoned`. If not, log a warning and mark the remaining delta as `unresolved`.
- **T6.6** — Ensure `DELETE FROM pos_orders` does NOT appear anywhere in the file (grep check + `verify_s169.py` MUST_NOT_CONTAIN assertion).
- **T6.7** — Run pre-commit guard: `python scripts/guards/check_chat_space_literals.py scripts/verify_mosaic_pos_sync.py`. Must pass.
- **T6.8** — Local smoke test: run the upgraded verify script with `--date 2026-04-04 --store 2317 --dry-run --no-chat` (dry-run so it doesn't actually tombstone yet — Phase 8 is the real test). Verify logs show the 3 phantom IDs are identified as extras and would be tombstoned. If dry-run flag doesn't exist, add it in this task.

### Phase 7 — Webhook registration (3 units)

- **T7.1** — Write `scripts/s169_register_webhooks.py`: iterates over unique credential groups in `MOSAIC_POS_API_KEYS.csv`, for each one calls `POST /api/v1/webhooks` with `{"url": "https://hq.bebang.ph/api/method/hrms.api.mosaic_webhook.receive", "events": ["order.cancelled"]}`. Before registering, call `GET /api/v1/webhooks` and skip if our URL is already registered. Record each registration (ID, credential group, registered_at) to `data/POS_Extraction/MOSAIC_WEBHOOK_REGISTRATIONS.csv`.
- **T7.2** — Run the registration script. Expected: 12 new rows in the CSV, 0 errors.
- **T7.3** — Verify: for a random credential group, run `GET /api/v1/webhooks` — our URL must appear in the list.

### Phase 8 — L3 verification (10 units — up from 8 post-audit for live webhook test)

- **T8.1** — **Apr 4 SM Marikina test — the primary acceptance.** Pre-run sanity SQL (capture to state_verification.json):
  - `SELECT COUNT(*) FROM pos_orders WHERE location_id=2317 AND business_date='2026-04-04'` → 311 total rows
  - `SELECT COUNT(*) FROM pos_orders WHERE location_id=2317 AND business_date='2026-04-04' AND cancelled_at IS NULL` → 311 (nothing tombstoned yet)
  - `SELECT * FROM v_pos_orders_live WHERE location_id=2317 AND business_date='2026-04-04'` → 311 (wrapper view also returns all, pre-tombstone)
- **T8.2** — Run upgraded verify script (live, no dry-run): `python scripts/verify_mosaic_pos_sync.py --date 2026-04-04 --store 2317 --no-chat`. Capture stdout to `output/l3/s169/verification_run.log`. Expected log flow: `[EXTRA]` detection → direct-ID 404 confirmation for IDs 49575307, 49575308, 49575310 → `[TOMBSTONED]` for each → final `extras_tombstoned` status written to `sync_verification`.
- **T8.3** — Post-run SQL: verify the 3 phantom rows have `cancelled_at IS NOT NULL` AND `cancellation_reason = 'reconciled_from_mosaic_gap'` AND `order_status = 'CANCELLED'`.
- **T8.4** — Post-run SQL: `SELECT COUNT(*) FROM pos_orders WHERE location_id=2317 AND business_date='2026-04-04' AND cancelled_at IS NULL` now equals 308 (matches Mosaic). `SELECT COUNT(*) FROM v_pos_orders_live WHERE location_id=2317 AND business_date='2026-04-04'` also equals 308.
- **T8.5** — Verify `sync_verification` has a new row: `SELECT * FROM sync_verification WHERE location_id=2317 AND business_date='2026-04-04' ORDER BY verified_at DESC LIMIT 1` shows `status='extras_tombstoned'`, `heal_attempted=TRUE`, `mosaic_total=308`, `supabase_total=308`.
- **T8.6** — Downstream view smoke test: query the rewritten `daily_revenue` MV for SM Marikina Apr 4 and verify the order count is now 308 (not 311). This confirms the wrapper-view substitution took effect and the sales dashboard will reflect reality.
- **T8.7 (BLOCKER 6 fix — live webhook test)** — Run the self-induced cancel test AGAINST the deployed endpoint (not webhook.site like in T0.5):
  1. Create a test order via `POST /api/v1/orders` with `bill_number = 999992`, `location_id = <smallest store>`, ₱1.00 gross.
  2. Immediately cancel via `POST /api/v1/orders/{id}/cancel` with `reason = "S169 Phase 8 live webhook test — safe to ignore"`.
  3. Within 30 seconds, query Supabase: `SELECT * FROM pos_orders WHERE id = <test_order_id>` — expected: `cancelled_at IS NOT NULL`, `cancellation_reason LIKE '%S169%'`, `order_status = 'CANCELLED'`. If the row doesn't yet exist in Supabase (the hourly sync hasn't captured it yet), query after 1 hour.
  4. Check Sentry for the `bei-hrms` project breadcrumb `action=mosaic_webhook_receive` with matching `order_id`.
  5. Save request/response pairs + Supabase state + Sentry link to `output/l3/s169/webhook_live_test_payload.json` + `webhook_live_test_response.json`. **HARD BLOCKER:** If the webhook doesn't fire within 30 seconds AND self-induced cancel test is the primary path, STOP and debug (`hq.bebang.ph` reachability, webhook registration status, Cloudflare challenge, endpoint errors in Frappe Error Log).
  6. Cleanup: tombstone the test order locally so it doesn't pollute future analysis: `UPDATE pos_orders SET cancellation_reason = cancellation_reason || ' [s169_test_cleanup]' WHERE id = <test_order_id>`. Consider the test row as audit evidence, do NOT delete.
- **T8.8** — Regression check: run the verify script for a random healthy store-day (e.g., SM Megamall 2026-04-05). Expected: status `ok`, no tombstoning, no errors.
- **T8.9** — Full 7-day sweep: `python scripts/verify_mosaic_pos_sync.py --days 7 --no-chat`. Expected: 0 `extra` rows in the latest state (Apr 4 Marikina already tombstoned in T8.2). Runtime <90s.
- **T8.10** — Run `python output/l3/s169/verify_s169.py`. All checks PASS. If any FAIL, fix before Phase 9.

### Phase 9 — Closeout + silence monitor (7 units — up from 5 post-audit for HIGH 10)

- **T9.1 (HIGH 10 fix — webhook silence detector)** — Add a silence-detection task to the nightly verify script OR as a new cron job. Implementation options (pick the simpler):
  - **Option A (extend verify script):** At the end of `verify_mosaic_pos_sync.py`'s main(), after the 7-day sweep, run a query:
    ```sql
    SELECT
      (SELECT COUNT(*) FROM sync_verification
        WHERE status = 'extras_tombstoned' AND verified_at >= NOW() - INTERVAL '7 days') AS tombstoned_count,
      (SELECT COUNT(*) FROM pos_orders
        WHERE cancelled_at >= NOW() - INTERVAL '7 days') AS cancelled_count
    ```
    If BOTH counts are 0, append to the Chat alert: `⚠️ Mosaic webhook may be silent — 7 days with zero tombstones AND zero webhook-set cancelled_at. Verify webhook registration via GET /api/v1/webhooks and hq.bebang.ph reachability.` This may fire occasional false positives (e.g., Holy Week closures with zero cancels) but is far better than silent failure.
  - **Option B (separate cron):** Write a standalone script `scripts/s169_webhook_silence_monitor.py` that runs daily, does the same query, and posts to `spaces/AAQABiNmpBg` only if the alert condition fires. Register in a new GH Actions workflow or extend `daily-pos-sync.yml`.
  - **Recommendation:** Option A — simpler, uses existing Chat path, no new cron. Choose A unless there's a reason to run it more frequently than nightly.
- **T9.2** — Update plan YAML: `status: COMPLETED`, `completed_date: <today>`, `backend_pr: <PR#>`, `execution_summary: <summary>`, `l3_result: <summary>`.
- **T9.3** — Update `docs/plans/SPRINT_REGISTRY.md` S169 row: status → COMPLETED with PR reference.
- **T9.4 (MW8)** — Explicit `git add -f`:
  ```bash
  git add -f \
    data/supabase/migrations/2026-04-07-pos-orders-lifecycle-columns.sql \
    scripts/sync_pos_to_supabase.py \
    scripts/verify_mosaic_pos_sync.py \
    scripts/s169_register_webhooks.py \
    scripts/s169_self_induced_cancel_test.py \
    scripts/s169_cleanup_test_orders.py \
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
    output/l3/s169/view_rewrite_deltas.json \
    output/l3/s169/workflow_disable_confirmation.txt \
    output/l3/s169/workflow_enable_confirmation.txt \
    output/l3/s169/bench_clear_cache_confirmation.txt \
    output/l3/s169/rollback_phase4.sql \
    output/l3/s169/webhook_signing_probe.md \
    output/l3/s169/webhook_test_payload.json \
    output/l3/s169/webhook_test_response.json \
    output/l3/s169/webhook_fault_injection.json \
    output/l3/s169/webhook_live_test_payload.json \
    output/l3/s169/webhook_live_test_response.json \
    output/l3/s169/verification_run.log \
    output/l3/s169/verify_s169.py
  ```
  Do NOT use `git add -A`.
- **T9.5** — Create PR: `GH_TOKEN="" gh pr create --repo Bebang-Enterprise-Inc/hrms --base production --head s169-mosaic-order-lifecycle-tombstone-webhook --title "S169: Mosaic Order Lifecycle CDC via Webhook + Tombstone" --body "..."`. PR body includes task-by-task checklist, the Apr 4 SM Marikina before/after evidence, the self-induced cancel test results, and a link to the audit report `verified_blockers.md`.
- **T9.6** — Write a short MEMORY.md lesson: "Supabase upsert split-ownership rule — when adding lifecycle columns to any synced table, the poller must not write columns that the webhook owns. PostgREST `Prefer: resolution=merge-duplicates` writes every column in the payload. See S169 Design Rationale decision #9." Commit in the same PR.
- **T9.7** — STOP per PR-HANDOFF rule. Post PR number to Sam and exit. No merge, no deploy.

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

- Test Python changes locally: `/local-frappe` (for the webhook endpoint — needs a local Frappe site with the updated hrms app). MANDATORY for Phase 3 T3.6 (webhook endpoint smoke test) and Phase 3 T3.7 (fault injection test) BEFORE production deploy.
- **Deploy Frappe changes: `/deploy-frappe` with `skip_build=false, no_cache=true`** — the new webhook endpoint is a fresh Python file and Frappe caches discovered `@frappe.whitelist()` endpoints. Skip-build would miss the new endpoint and the deploy would succeed but the endpoint would 404. Full rebuild is mandatory.
- E2E testing: the L3 scenarios above — no separate E2E framework needed
- Webhook live test (Phase 8 T8.7): self-induced cancel via `scripts/s169_self_induced_cancel_test.py` (primary) with 30-minute natural-cancel fallback (secondary). Per BLOCKER 6 fix — the plan never waits indefinitely for a natural event.

---

## Anti-Rewind / Concurrent-Run Protection Contract

- **Ownership matrix:** This sprint owns exclusively:
  - `data/supabase/migrations/2026-04-07-pos-orders-lifecycle-columns.sql` (NEW)
  - `scripts/sync_pos_to_supabase.py` — `map_order` function ONLY, lines 379-433. No other function in this file may be touched.
  - `scripts/verify_mosaic_pos_sync.py` — `supabase_count` + `_process_group` `extra` branch + new `tombstone_extras` function + Phase 9 silence monitor (if Option A chosen)
  - `scripts/s169_register_webhooks.py` (NEW)
  - `scripts/s169_self_induced_cancel_test.py` (NEW)
  - `scripts/s169_cleanup_test_orders.py` (NEW)
  - `hrms/api/mosaic_webhook.py` (NEW)
  - `hrms/utils/supabase.py` (NEW)
  - `data/POS_Extraction/MOSAIC_WEBHOOK_REGISTRATIONS.csv` (NEW)
  - `pos_orders` table (schema change — nullable cols + partial index)
  - `sync_verification` table (CHECK constraint change — adds `extras_tombstoned`)
  - `public.v_pos_orders_live` (NEW wrapper view)
  - The 6 MVs and 6 views listed in "Files to Modify" §3 (single-token substitution)
  - Temporary workflow disable/enable on `daily-pos-sync.yml` during Phase 4 ONLY (state returns to enabled at Phase 4 close)
- **Protected surfaces (DO NOT TOUCH):**
  - `scripts/sync_pos_to_supabase.py` — functions other than `map_order`. Especially `sync_store_day`, `fetch_all_orders`, `get_completed_store_days`, `set_sync_progress`, `supabase_upsert`. The `supabase_upsert` function at lines 174-198 is load-bearing; its PostgREST `merge-duplicates` header is the reason the BLOCKER 1 split-ownership architecture exists. Do NOT modify.
  - `sync_progress` table — schema unchanged
  - `pos_order_items` and `pos_order_payments` tables — no schema change
  - `scripts/detect_anomalies.py` — unrelated to this sprint (already fixed in S165 follow-up PR #470)
  - `.github/workflows/daily-pos-sync.yml` — NO code changes to the YAML file. Only temporary runtime state change via `gh workflow disable/enable` during Phase 4. The workflow definition must be byte-identical before and after Phase 4.
  - `hrms/api/sales_dashboard.py`, `hrms/api/discount_abuse.py`, `hrms/api/marketing_giveaways.py`, `hrms/utils/store_order_demand_snapshot.py` — these have their own ad-hoc Supabase helpers that design-review H1 flagged for consolidation. Migration is OUT of scope for S169 — DO NOT touch these files. A follow-up sprint will migrate them to import from `hrms/utils/supabase.py`.
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

### 2026-04-07 v1 — Plan created from S165 Apr 4 SM Marikina incident research
First draft. Based on research into Mosaic's list-endpoint filtering, direct-ID 404 behavior, and webhook event catalog. Empirically probed 10 filter forms on `/api/v1/orders` (all returned same `meta.total=308`) and confirmed `POST /orders/{id}/cancel` + `order.cancelled` webhook exist. PR #475 opened.

### 2026-04-07 v2 — Post-audit amendments applied (4 CRITICAL + 6 HIGH blockers fixed, zero features cut)
Audit run: `output/plan-audit/s169-mosaic-order-lifecycle/verified_blockers.md`. Six domain auditors + code verifier ran in parallel. Code verifier confirmed V1, V2, V3 against actual source files (the UPSERT race at `scripts/sync_pos_to_supabase.py:174-198`, the cron collision at `.github/workflows/daily-pos-sync.yml:125-142`, and the non-existent `frappe.request.get_json` canonical pattern).

**Per Sam directive 2026-04-07:** "Reducing units is not a priority, getting what I want is." This amendment added units (56 → 69) rather than cutting scope. Every blocker gets a full correct fix with explicit validation gates. No features removed.

**Blockers fixed in v2:**

| ID | Severity | Fix applied |
|----|----------|-------------|
| **BLOCKER 1** | CRITICAL | `map_order()` no longer writes `cancelled_at` or `cancellation_reason`. Split ownership: poller writes `order_status` + `completed_at`; webhook + verify own `cancelled_at` + `cancellation_reason`. Enforced by `verify_s169.py` MUST_NOT_CONTAIN assertions. Design Rationale decision #9 added with full trace. |
| **BLOCKER 2** | CRITICAL | Phase 4 adds `gh workflow disable daily-pos-sync.yml` fence (T4.0) + `gh workflow enable` close (T4.16). Hourly `refresh-sales-dashboard-views` job cannot race with view DROPs. |
| **BLOCKER 3** | CRITICAL | Closed by BLOCKER 1 fix (same root cause — the poller overwriting the webhook). No Phase ordering change needed. |
| **BLOCKER 4** | CRITICAL | Webhook endpoint uses canonical `frappe.request.get_data(as_text=True) + json.loads()` per `hrms/api/esignature.py:55-60`. `frappe.request.get_json` and `silent=True` explicitly forbidden in verify_s169.py. Explicit `json.JSONDecodeError` handling returns HTTP 400. |
| **BLOCKER 5** | HIGH | `hrms/utils/supabase.py` is PostgREST + `requests` ONLY, mirroring `hrms/api/sales_dashboard.py:168-199` shape. `psycopg2` import is forbidden by verify_s169.py MUST_NOT_CONTAIN. Full skeleton in Files to Create §3 with 5 helper functions (`get_service_key`, `get_mgmt_token`, `supabase_headers`, `supabase_get`, `supabase_patch`, `supabase_query_sql`). |
| **BLOCKER 6** | HIGH | Phase 0 T0.5 uses `scripts/s169_self_induced_cancel_test.py` to create + cancel a test order as the primary webhook signing probe method. Natural-cancel-wait is demoted to fallback with a hard 30-minute bound. Same self-induced method used in Phase 8 T8.7 for the live webhook test. |
| **BLOCKER 7** | HIGH | Phase 4 uses the wrapper-view pattern: one new view `v_pos_orders_live AS SELECT * FROM pos_orders WHERE cancelled_at IS NULL`, then single-token substitution on each of the 12 dependents (`FROM pos_orders` → `FROM v_pos_orders_live`). No SQL parsing, no WHERE-clause mangling. |
| **HIGH 8** | HIGH | Webhook handler + `tombstone_extras` both wrap Supabase calls in try/except. Webhook returns HTTP 500 on Supabase failure (Mosaic retries). Verify script's tombstone path uses `sentry_sdk.capture_exception` and marks the affected rows `unresolved` on Supabase failure. New Phase 3 T3.7 fault-injection test verifies the error path. |
| **HIGH 9** | HIGH | Phase 4 T4.2 builds `tmp/s169_rollback_phase4.sql` alongside the new definitions. Phase 4 T4.18 commits the rollback to `output/l3/s169/` as permanent audit. ~5 minute MTTR. |
| **HIGH 10** | HIGH | Phase 9 T9.1 adds a webhook silence detector (Option A — extend the nightly verify script): if 7 consecutive days show zero tombstones AND zero cancelled_at updates, alert to `! Blip Notifications`. |

**Demoted MED/LOW fixes also applied:**
- `cancelled_at` uses Mosaic's authoritative timestamp (not now() fallback)
- `payment_status` uses explicit `None` check (not `or ""` double-or)
- Top-level import of `supabase_query_sql` in webhook (not inline)
- Phase 5 T5.0 cites `sync_progress` resume logic explicitly
- Execution Workflow specifies `no_cache=true` flag for `/deploy-frappe`
- Phase 4 T4.17 adds `bench clear-cache` post-Phase-4 (deployment-qa MED-8)
- Mosaic API doc line refs corrected (140 + 182, not 171 + 396)
- T0.4 HARD BLOCKER upgraded to require plan update if a 13th view is found
- Verify_s169.py adds Supabase-live checks for view definitions
- Missing MUST_MODIFY assertions added for `hrms/utils/supabase.py`, registrations CSV, verify_s169.py

**Phase budget impact:** 56 → 69 units. Still under 80-unit ceiling. Max phase is 12 units (Phase 4). Zero features cut. Zero corners cut.

**Philosophy:** Get it right, not get it fast. Every amendment preserved a feature Sam asked for and added validation instead of removing complexity.
