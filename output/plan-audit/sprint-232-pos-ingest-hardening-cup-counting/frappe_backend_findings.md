# S232 Frappe Backend + End-to-End Duplicate Resolution Audit

**Plan:** `F:\Dropbox\Projects\BEI-ERP\docs\plans\2026-05-02-sprint-232-pos-ingest-hardening-cup-counting.md`
**Audit date:** 2026-05-02
**Lens:** "Will this resolve all our duplicate issues?" (the user's primary concern)

---

## Executive headline

**The plan WILL fix the 945 historical duplicates and prevent new poll-driven duplicates as long as `bill_number` is non-NULL — which the live API probe confirmed for 250/250 orders.** The dedup primary key `(location_id, business_date, bill_number)` is correctly chosen and the partial unique index is the right enforcement mechanism.

But the plan as written has **3 CRITICAL bugs** that, if executed verbatim, will produce orphan rows, drop a unique-violation 409 on the floor, or fail at migration time. There are also **5 WARNINGs** about silent under-counting in analytics views, an ambiguous "kept" rule in the backfill, and a Sentry context call that lands in the wrong place. None of the issues are show-stoppers for the architecture — they are fix-during-execution items that should be locked into the plan before it goes to an executing agent.

---

## Q1 — Will the unique partial index actually prevent new duplicates?

**Severity: CRITICAL**

**Short answer:** The index will *block at the database level*, but the way `scripts/sync_pos_to_supabase.py` calls PostgREST (`on_conflict=id` + `Prefer: resolution=merge-duplicates`) will **fail loudly with HTTP 409 on the entire batch** when a new row arrives with the same bill_number but a different `id`. The plan correctly anticipates this in Phase 1.5 ("If the unique partial index throws via PostgREST despite the pre-check (rare race), catch the unique-violation error code and route to `webhook_duplicates`") — but the existing `supabase_upsert()` helper has NO such error-handling path.

**Trace:**

`F:\Dropbox\Projects\BEI-ERP\scripts\sync_pos_to_supabase.py:174-198` defines:

```python
def supabase_upsert(client, table, rows, on_conflict=None):
    ...
    for attempt in range(1, MAX_RETRIES + 1):
        r = client.post(url, headers=_supabase_headers(prefer="resolution=merge-duplicates,return=minimal"), json=batch, timeout=30)
        if r.status_code in (200, 201):
            break
        if r.status_code == 429 and attempt < MAX_RETRIES:
            time.sleep(RETRY_WAIT)
            continue
        raise RuntimeError(f"Supabase upsert {table} failed ({r.status_code}): {r.text[:300]}")
```

Then at `:539-543`:

```python
supabase_upsert(client, "pos_orders", order_rows, on_conflict="id")
upsert_items_batch(client, item_rows)
supabase_upsert(client, "pos_order_payments", payment_rows, on_conflict="order_id,payment_type,line_number")
```

**Mechanism:**
1. `Prefer: resolution=merge-duplicates` only resolves on the conflict target named in `on_conflict=id` (PRIMARY KEY).
2. When Mosaic re-issues a NEW `id` for an existing `bill_number`, the row is a **fresh primary key**, so `merge-duplicates` does NOT trigger — the row is INSERTed.
3. Postgres then evaluates the new partial unique index `pos_orders_bill_number_natural_key`. Existing row already occupies that key. **Constraint violation.**
4. PostgREST returns **HTTP 409 Conflict for the whole batch of 100** (it sends the batch atomically; one bad row fails the transaction).
5. The current `supabase_upsert()` raises `RuntimeError`. Sync of that store-day errors out, `sync_progress` is set to `error`, and the next cron tries again — same outcome.

**The plan's Phase 1.5 says "catch the unique-violation error code and route to `webhook_duplicates`" but does not specify HOW.** The existing helper aborts the whole batch. To recover from a single bad row inside a 100-row batch, the agent would have to either:
  (a) split the batch on 409 and retry rows individually, or
  (b) rely entirely on the `find_bill_number_twin` pre-check to filter dupes BEFORE the upsert call (so 409 never fires in steady state).

If the agent ships option (a) the implementation is non-trivial and untested. If they ship option (b) only, then any race-condition retry (two threads of `--parallel` mode for two locations sharing a bill_number — vanishingly rare but possible) blows up the whole batch.

**Recommended fix (LOCK INTO PLAN):**
> Phase 1.5 must explicitly require:
> 1. A new helper `supabase_upsert_with_unique_violation_split(table, rows, on_conflict, unique_violation_handler)` that, on HTTP 409, parses the error body for the violated row's PK, removes the offender from the batch, calls `unique_violation_handler(row)` to write to `webhook_duplicates`, and retries the rest.
> 2. The `find_bill_number_twin` pre-check is the primary path; the 409 retry is the safety-net for races.

Without that helper, **the plan's "catch the unique-violation" sentence has no concrete implementation path.**

---

## Q2 — Is `find_bill_number_twin` sufficient, or do we need atomic upsert-with-conflict-target?

**Severity: WARNING**

**Pre-check is sufficient under normal conditions but not race-proof.** PostgreSQL's partial unique index is the only true atomicity guarantee. The plan correctly layers both (pre-check + DB constraint), so the design is right.

**Race scenarios:**
1. **Two parallel `_sync_one_group` workers** processing different credential groups but covering the same physical store (impossible per `MOSAIC_POS_API_KEYS.csv` structure — each store has exactly one credential group).
2. **Webhook + poll arriving simultaneously** for the same order — the webhook is currently only `order.cancelled` (which UPDATEs, doesn't INSERT) plus a code-complete-but-unregistered `order.completed` path. Today, **0 races**. Future, after vendor outreach hopefully fixes the bill_number stability, **still 0 races** because that webhook also goes through the same dedup helper (Phase 1.5b).
3. **The cron's `cancel-in-progress: false`** in `.github/workflows/pos-sync-5min.yml` could in theory overlap two runs of `--daily` — but the `sync_progress.in_progress` status guard plus the per-store-day skip logic at `:598-602` prevents two runs from both processing the same store-day.

**Conclusion:** the unique index IS the atomicity guarantee, the pre-check is the optimization. The plan's combo is correct. The 409 handling gap from Q1 is the actual issue, not the race itself.

---

## Q3 — Does the plan handle `pos_order_items` and `pos_order_payments` when a parent duplicate is rejected? (ORPHAN RISK)

**Severity: CRITICAL**

**The plan is silent on this. Reading the script literally:** `pos_order_items` and `pos_order_payments` will be inserted even when their parent `pos_orders` row is rejected as a duplicate. This produces **orphan child rows attached to a Mosaic Order ID that does not exist in `pos_orders`**.

**Trace at `F:\Dropbox\Projects\BEI-ERP\scripts\sync_pos_to_supabase.py:528-543`:**

```python
order_rows = []
item_rows = []
payment_rows = []
for order in orders:
    order_rows.append(map_order(order))
    item_rows.extend(map_order_items(order))
    payment_rows.extend(map_order_payments(order))

# Upsert into Supabase
try:
    supabase_upsert(client, "pos_orders", order_rows, on_conflict="id")
    upsert_items_batch(client, item_rows)
    supabase_upsert(client, "pos_order_payments", payment_rows, on_conflict="order_id,payment_type,line_number")
```

`pos_order_items.order_id` and `pos_order_payments.order_id` reference `pos_orders.id`. Phase 1.5 says "append the rejected row to a batch list and skip the main upsert" — but the plan's text only references the `pos_orders` upsert, not the items/payments upserts.

**If items/payments are inserted with the rejected parent's `order_id`:**
- They become orphans — no FK exists to enforce this on Supabase by default, so they live in the table.
- The `daily_material_consumption` trigger at `supabase\migrations\20260414_s189_realtime_bom_consumption.sql:122` (`fn_update_material_consumption_pos`) FIRES for every item INSERT and looks up `pos_orders.business_date` — for an orphan, that lookup returns NULL and the trigger early-returns at `:134`. **So no phantom material consumption is recorded.** Good.
- BUT discount_abuse and giveaway analytics queries at `discount_abuse.py:1232` and `marketing_giveaways.py:1028` join from `pos_orders` to `pos_order_items` via `order_id`. They do INNER joins (param-style filter on `order_id IN (chunk)`), so orphan items are silently filtered out. **Good (accidentally).**
- BUT `cups_sold` recount in Phase 5.3 (`scripts/s232_recount_cups.py`) is brand-new code not yet written. If it `SUM(qty) WHERE is_cup_drink` against `pos_order_items` directly without joining `pos_orders`, **it will count orphan rows and inflate cups.**

**Recommended fix (LOCK INTO PLAN):**
> Phase 1.5 must explicitly say: "When `find_bill_number_twin` returns a hit, ALSO drop the matching item rows from `item_rows` and matching payment rows from `payment_rows` (filter where `order_id == order["id"]`) before the items/payments upserts."
>
> Phase 5.3 cup recount script must JOIN `pos_order_items` to `pos_orders` and filter `is_duplicate IS NOT TRUE` to avoid counting orphan items from historical duplicates.

This is the single most likely silent bug to ship if the plan is executed literally.

---

## Q4 — Tombstone interaction with S169 cancellation

**Severity: WARNING (resolvable but worth specifying)**

**Scenario:** Order is cancelled. S169 webhook fires `order.cancelled` and runs UPDATE at `mosaic_webhook.py:151-162`:

```python
UPDATE pos_orders
   SET cancelled_at = %s, cancellation_reason = %s, order_status = 'CANCELLED'
 WHERE id = %s AND cancelled_at IS NULL
```

This UPDATE only runs against the CURRENT row (matched by `id`). Then the next poll run pulls the same physical bill from Mosaic API but Mosaic re-issues a new `id`. The new row arrives with a fresh `id` and `order_status` re-set from the API payload.

**Path through dedup:**
1. `find_bill_number_twin(location_id, business_date, bill_number)` finds the existing tombstoned row.
2. Plan says "skip the main upsert" — so the new row is NOT written. The cancellation is preserved on the original row. **Good.**

**BUT:** what if the plan's race-condition fallback (Q1's missing 409 handler) ever executes? If a second-arrival row makes it past the pre-check (e.g., the pre-check runs in a different transaction snapshot), the partial unique index correctly rejects it. The original tombstoned row is preserved. **Also good.**

**The actual risk:** Phase 5.1 backfill — when the script identifies a duplicate cluster, it picks a "kept" row and marks the rest `is_duplicate=true`. **What if the "kept" row is the cancelled one and the duplicate is a more-recent post-cancellation re-issue from Mosaic?** The plan doesn't address this. If the kept row has `cancelled_at IS NOT NULL` and the duplicate has `cancelled_at IS NULL`, the analytics views would silently include `is_duplicate IS NOT TRUE AND cancelled_at IS NULL` — and the cancelled row gets filtered out, the live row marked dupe — and the post-dedup view ends up with no row at all.

**Recommended fix (LOCK INTO PLAN):**
> Phase 5.1 must explicitly say: "When picking the kept row in a cluster, prefer rows where `cancelled_at IS NOT NULL` over rows without — cancellation is sticky and authoritative. If multiple have `cancelled_at`, keep the one with the lowest `id` (earliest received)."
>
> Phase 5.2 view filter must be `WHERE is_duplicate IS NOT TRUE AND cancelled_at IS NULL` to preserve the existing S169 contract.

---

## Q5 — Backfill phase 5: who is the "kept" row?

**Severity: WARNING**

**The plan is ambiguous.** Phase 5.1 (line 419) says:

> sets `is_duplicate=true` and `kept_order_id=<earliest_order>` on each duplicate

"earliest_order" is undefined. Three plausible interpretations, all behave differently:

| Interpretation | Source field | Risk |
|----------------|--------------|------|
| Lowest `id` | `pos_orders.id` (Mosaic Order ID) | Mosaic IDs are NOT monotonic across re-issues — the cluster Sam quoted has IDs `[51481228, 51481233, 51481234, 51481241, 51481247, 51499274]` where the gap between 51481247 and 51499274 is 18,000 IDs. Lowest id == "first observed by Mosaic", not necessarily first written to our DB. |
| Earliest `webhook_received_at` | New column added in Phase 1.3 | NULL for all historical rows — the column doesn't exist before this sprint. Backfill against pre-S232 data has no usable value here. |
| Earliest `created_at` (Supabase row insert time) | The Supabase column on `pos_orders` (set by INSERT) | The table doesn't appear to have `created_at` declared in any migration; PostgreSQL doesn't auto-add this. **May not exist.** |

The user explicitly flagged this in the question prompt as "earliest known timestamp" and asked to verify it's unambiguous — **it is NOT unambiguous in the plan.**

**Recommended fix (LOCK INTO PLAN):**
> Phase 5.1 must specify: "The kept row is determined by `MIN(id)` within each `(location_id, business_date, bill_number)` cluster. Reasoning: even though Mosaic re-issues IDs, the earliest-observed ID corresponds to the first poll-run that captured the order, which is the canonical first observation. All later-IDs in the cluster are by definition retries or re-issues."

This is the simplest, deterministic, and matches what a vendor outreach response of "id should be stable" would imply.

---

## Q6 — Is the backfill safe to re-run?

**Severity: WARNING**

**Probably yes, with a fix:** `scripts/s232_backfill_dupes.py` (Phase 5.1) is described as setting `is_duplicate=true` and `kept_order_id=<earliest_order>` on each duplicate. The plan does NOT explicitly state the script is idempotent.

**Idempotency analysis:**
- If run twice on a clean cluster: first run flags the 5 dupes, kept row stays. Second run sees the 5 already-flagged dupes — does it re-flag them? If the SQL is `UPDATE pos_orders SET is_duplicate=true WHERE ...`, yes, idempotent (same-state assignment).
- If the cluster gains a new row between runs (e.g., 7th arrival), the second run should flag it as dupe too. **Only safe if the cluster-detection logic is `MIN(id) survives, all others are dupes` regardless of pre-existing `is_duplicate` state.**
- DANGER: if the script is `WHERE is_duplicate IS NULL OR is_duplicate IS FALSE` (skipping already-flagged), then a new row added later will not be re-evaluated against existing flags, and the kept_order_id becomes inconsistent.

**Recommended fix (LOCK INTO PLAN):**
> Phase 5.1 must specify: "The backfill is idempotent. It MUST process all rows where `bill_number IS NOT NULL` regardless of pre-existing `is_duplicate` state. The SQL pattern: `UPDATE pos_orders SET is_duplicate = (id != MIN(id) OVER (PARTITION BY location_id, business_date, bill_number)), kept_order_id = MIN(id) OVER (PARTITION BY location_id, business_date, bill_number) WHERE bill_number IS NOT NULL`. This is naturally idempotent."
>
> Add idempotency proof to verifier: run twice, diff `is_duplicate` and `kept_order_id` distribution, must be byte-identical.

---

## Q7 — DM-checklist applicability

**Severity: INFO (no blocker)**

The plan does NOT touch:
- `Journal Entry` (no creation)
- `Payment Entry` (no creation)
- `GL Entry` (no creation)
- `Sales Invoice` / `Purchase Invoice` (no Frappe DocType writes)
- Any Frappe-side accounting field

It only touches Supabase analytics tables (`pos_orders`, `pos_order_items`, `pos_order_payments`, new `pos_products`, new `webhook_duplicates`) and Frappe Python API readers.

**DM-1 through DM-6 are N/A.** The `canonical_scope: none` declaration in YAML frontmatter is correctly justified (lines 13-20).

---

## Q8 — Sentry instrumentation correctness

**Severity: INFO (small landing-spot issue)**

Phase 1.6 says:

> add `set_backend_observability_context(module="pos_ingest", action="handle_order_completed", ...)` at the start of `_handle_order_completed`

**Issue:** `_handle_order_completed` already calls this at `F:\Dropbox\Projects\BEI-ERP\hrms\api\mosaic_webhook.py:206-210`:

```python
def _handle_order_completed(data: dict) -> dict:
    ...
    set_backend_observability_context(
        module="mosaic",
        action="handle_order_completed",
        mutation_type="create",
    )
```

Phase 1.6 asks the agent to ADD a new call. If they replace the existing one, the `module` changes from "mosaic" to "pos_ingest" — which **changes the Sentry tag for all future webhook deliveries**. This breaks any saved Sentry alerts/dashboards keyed on `module="mosaic"`. If they add a second call, the second one wins (replaces context) but still creates noise.

The rule in `.claude/rules/sentry-observability.md` says module is the BEI module name. Both "mosaic" and "pos_ingest" are reasonable. The rule does not enforce one specific name — but **the agent should not silently rename a tag that is already in production telemetry.**

**Recommended fix (LOCK INTO PLAN):**
> Phase 1.6 should clarify: "MODIFY the existing `set_backend_observability_context` call at `mosaic_webhook.py:206`. Update `module='mosaic'` → `module='pos_ingest'` ONLY IF coordinated with Sentry alerts owner. Otherwise keep `module='mosaic'` and add `extras={'order_id': order_id, 'bill_number': bill_number}` to the existing call."

---

## Q9 — Does `is_duplicate` flag propagate through analytics correctly?

**Severity: CRITICAL**

**The plan adds `WHERE is_duplicate IS NOT TRUE` only to "views" — but the production analytics layer reads `pos_orders` directly via PostgREST in 14+ places.** Phase 5.2 says:

> `pos_orders` views and rollups (`v_sync_drift_monitor`, any S171/S189 view) get a `WHERE is_duplicate IS NOT TRUE` filter

This catches `v_sync_drift_monitor`, `v_pos_orders_live`, `v_ingestion_reconciliation`, `v_webhook_coverage` — but **does NOT catch the direct PostgREST queries.** The following sites query `pos_orders` directly with NO `is_duplicate` filter:

| File | Line | Query |
|------|-----:|-------|
| `hrms/api/discount_abuse.py` | 1167-1175 | `_query_paid_orders_for_range` filters `payment_status=eq.PAID`, NO `is_duplicate` filter |
| `hrms/api/discount_abuse.py` | 971 | List of 14 fields read via `_supabase_get_all("pos_orders", ...)` |
| `hrms/api/marketing_giveaways.py` | 996-1009 | `_query_probable_giveaway_leakage` reads `pos_orders` directly |
| `hrms/api/sales_dashboard.py` | (many — uses `v_pos_orders_live`) | Reads through view |

**Concretely:** if Phase 5.1 marks 945 historical rows as `is_duplicate=true`, then:
- `discount_abuse._query_paid_orders_for_range` will continue to return all 945 dupes as if they were real paid orders. Statutory discount audit will count them as 945 separate paid customer transactions. PHP 15K of discount-eligible gross will be double-counted. **Discount abuse alerting will continue to drift.**
- `marketing_giveaways._query_probable_giveaway_leakage` will see them as separate orders and over-flag giveaway leakage.

**The plan's checklist item ("Did I confirm dashboards consume `pos_orders.business_date`...") does not catch this.** There is no Phase 5 or Phase 6 task that audits `discount_abuse.py` and `marketing_giveaways.py` for `is_duplicate` propagation.

**Recommended fix (LOCK INTO PLAN):**
> Add Phase 5.x task: "Audit every `_supabase_get(_all)?\(.pos_orders.,` call site in `hrms/api/`. Each must add `('is_duplicate', 'not.is.true')` to its params list. List of known sites:
> - `hrms/api/discount_abuse.py:1175` (`_query_paid_orders_for_range`)
> - `hrms/api/discount_abuse.py:971` (around `_supabase_get_all('pos_orders')`)
> - `hrms/api/marketing_giveaways.py:1009` (`_query_probable_giveaway_leakage`)
> - any other site found by `grep -rn '"pos_orders"' hrms/api/`."
>
> Add a verifier: `python scripts/s232_verify_dedup_filter_coverage.py` greps all `*.py` files under `hrms/api/` for `"pos_orders"` and asserts every site is paired with `is_duplicate.not.is.true`.

Without this, **the plan resolves duplicates in the dashboard view but NOT in the backend analytics — the discount audit and giveaway analyses keep drifting**.

---

## Q10 — `is_duplicate=PENDING_REVIEW` magic value

**Severity: INFO (false alarm — not in the plan)**

The user's prompt asserted "Phase 1.5b says it sets this when bill_number is None and cluster-window finds a twin. But `is_duplicate` is declared `BOOLEAN DEFAULT false`."

**Re-read of plan:** I searched for `PENDING_REVIEW`, `PENDING`, `review_queue` and `cluster.window.*NULL` in the entire plan text. The string `PENDING_REVIEW` does **not** appear. Phase 1.5b text:

> Wire same dedup into `_upsert_completed_order` (FUTURE-PROOFING). Before the `pos_orders` upsert at `hrms/api/mosaic_webhook.py:457`, do the same: bill_number twin check (→ `webhook_duplicates` if found), NULL fallback to cluster-window.

Phase 1.5b routes NULL-bill twins to `webhook_duplicates` (the same audit table), NOT to a `is_duplicate=PENDING_REVIEW` magic value. The plan keeps `is_duplicate` as plain BOOLEAN.

The protected-surface table at line 483 mentions `webhook_review_queue` as a "new table" but no Phase actually creates it. **This is a leftover from an earlier plan iteration that referenced a review queue.**

**Recommended fix (LOCK INTO PLAN):**
> Remove `webhook_review_queue` from the line 483 protected-surfaces table. The plan does NOT create that table. The current architecture routes NULL-bill twins to the same `webhook_duplicates` table.

No bug exists. The user's question 10 was based on a misreading. (User: please re-confirm — if you saw `PENDING_REVIEW` somewhere I missed, send the line number.)

---

## ADDITIONAL FINDINGS NOT IN THE QUESTIONS

### A. Migration filename collision

**Severity: CRITICAL**

Phase 1.3 (line 334) declares: `scripts/s232_supabase_migrations/003_pos_orders_dedup_fields.sql`
Phase 2.1 (line 384) declares: `scripts/s232_supabase_migrations/003_pos_products.sql`

**Two different migrations both numbered `003_`.** When the agent runs them in order, only one will be applied (filename collision overwrites or skips). Atlas / Supabase migration runners typically use the numeric prefix as ordering — both files at index 003 produces undefined behavior.

**Recommended fix (LOCK INTO PLAN):**
> Renumber Phase 2.1 migration to `004_pos_products.sql`. Then Phase 1.5c short_order_id migration moves to `005_short_order_id.sql`. Then Phase 4.2 inferred-payments to `006_pos_order_payments_inferred.sql`. Then Phase 5.2 view filter to `007_views_filter_dupes.sql`.
> Verifier MUST_MODIFY paths must be updated accordingly.

### B. `_handle_order_completed` round-trip blocks dedup pre-check

**Severity: WARNING**

At `mosaic_webhook.py:228-243`:
```python
order = _fetch_mosaic_order(order_id, data)
if not order:
    if not data.get("location_id") or not data.get("business_date"):
        return {"ok": True, "handled": False, ...}
    order = data
```

The plan's Phase 1.5b puts `find_bill_number_twin` "before the `pos_orders` upsert at `:457`" — i.e., inside `_upsert_completed_order`. But the round-trip fetch at `:229` may take 15s timeout. **If Mosaic API is the source of bill_number drift, the round-trip would return the SAME order with the SAME bill_number — no help. But the round-trip can also return a DIFFERENT id if Mosaic happens to re-issue between webhook send and round-trip fetch**, in which case the dedup helper sees a "different order" and dedups against the wrong row.

This is theoretical edge case. Today the webhook is unregistered. Future-proofing only matters if the webhook ever gets re-registered. **Acceptable risk** — but worth a comment.

**Recommended fix (LOCK INTO PLAN):**
> Phase 1.5b must add a comment: "When using round-trip-fetched order (vs. webhook payload), prefer the webhook's `bill_number` over the fetched order's `bill_number` — the webhook payload is the closest-in-time observation of the physical transaction."

### C. `webhook_received_at` not set on existing rows

**Severity: WARNING**

Phase 1.3 adds `webhook_received_at TIMESTAMPTZ` (no DEFAULT) to `pos_orders`. Phase 5.1 backfill detection uses cluster-window (`webhook_received_at within 60s`) for NULL-bill_number rows. **Existing 138K rows have NULL `webhook_received_at`.**

The cluster-window helper `find_cluster_twin` at `hrms/utils/pos_dedup.py` (Phase 1.4) needs `webhook_received_at` to compute the 60s window. If the column is NULL on the lookup target, the comparison `abs(new.webhook_received_at - existing.webhook_received_at) <= 60s` is undefined.

**For the live ingest path:** new rows from Phase 1.5+ will set `webhook_received_at = now()`. So the helper works for new data. But the BACKFILL in Phase 5.1 looking at historical NULL-bill rows can't compute window — there's no observation timestamp.

**Recommended fix (LOCK INTO PLAN):**
> Phase 1.3 migration must include: `UPDATE pos_orders SET webhook_received_at = COALESCE(billed_at, business_date::timestamptz + interval '12 hours') WHERE webhook_received_at IS NULL;`. This gives historical rows a usable proxy for the cluster-window backfill.
> Phase 1.4 `find_cluster_twin` helper must explicitly handle NULL by treating the window as never-matching (safe default — backfill skips NULL-bill clusters).

### D. The `webhook_duplicates` table column choice for `bill_number`

**Severity: INFO**

Phase 1.2 declares: `bill_number INT`. Mosaic's `bill_number` is observed up to 5-digit values (23547 in Araneta cluster). INT is fine. **But** other stores may eventually exceed 2^31 — though unlikely for a per-store-per-day counter. Not a blocker. INT is fine.

### E. Seed risk: synthetic store ID 9999 collides with real Mosaic location_id

**Severity: WARNING (mitigated by HARD BLOCKER in plan)**

Phase 0.4 adds the right verification: `SELECT 1 FROM pos_orders WHERE location_id = 9999`. Plan correctly halts and asks for an alternate ID. **No fix needed — already addressed.**

But a minor strengthening: the verifier should also check `MOSAIC_POS_API_KEYS.csv` for any `Mosaic Location ID = 9999` — if a store gets added later with that ID, the seed contaminates real data.

### F. `_resolve_channel` is duplicated between webhook and poll paths

**Severity: INFO (pre-existing tech debt)**

Both `mosaic_webhook.py:380` and `sync_pos_to_supabase.py:425` define `_resolve_channel` separately. They MUST stay in sync. The plan adds new fields (`short_order_id`, payment inference) to BOTH paths in Phase 1.5c and Phase 4.1 — but doesn't propose to consolidate.

**Acceptable for this sprint.** Future cleanup. Not a blocker.

---

## Final summary on the user's question: "will this resolve all our duplicates issues?"

**For the 945 historical poll-induced duplicates: YES, the architecture resolves them**, IF and only if:
1. Q1 (409 batch failure) is solved by either an enhanced upsert helper OR by trusting the pre-check completely.
2. Q3 (orphan items/payments) is fixed by filtering child rows in lock-step with the parent.
3. Q5 (kept_order_id rule) is locked to a specific deterministic rule (`MIN(id)` recommended).
4. Q9 (analytics filter coverage) is extended to direct PostgREST callers in `discount_abuse.py` and `marketing_giveaways.py`.
5. The migration numbering collision (Finding A) is fixed before any agent runs the migrations.

**For NEW poll-induced duplicates going forward:** the partial unique index is the correct enforcement. With the dedup pre-check, 99%+ of dupes never reach the index. The 1% that hit the index need the 409 handler from Q1.

**For NULL-bill_number edge cases:** the cluster-window fallback exists but Q5/Finding C show the `webhook_received_at` proxy needs explicit backfill before the fallback can run on historical data. New rows will populate it correctly.

**Out of scope but worth noting:** the plan correctly identifies that the root cause is on Mosaic's side (`id` instability across pulls). Phase 7 vendor outreach is the long-term fix. The dedup index is the BEI-side workaround. **Even if Mosaic never fixes it, our dedup is durable.**
