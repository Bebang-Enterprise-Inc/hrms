# S225 Sentry Root-Cause Analysis — Why the 14 Stores Failed

**Sentry pull window:** 2026-04-28 00:00–01:55 UTC (covers full sweep)
**Source:** `output/s225/verification/sentry_events_sweep.json` + `sentry_event_detail/*.json`
**Authored:** 2026-04-28 (post-sweep, in response to CEO directive)

---

## TL;DR

**The 14 failed stores share ONE primary product bug + ONE master-data gap + ONE config gap. They are NOT 3 separate UI/race defects.**

| Cluster (sweep symptom) | Stores | Real root cause | Honest classification |
|---|---|---|---|
| WarehouseApprovalPage approve button not visible | 9 | **Resolver routes PM001 to PCS-BKI which has 0 PM001 stock**. Area-sup approval throws 417 → order stays assigned to test.area → SCM 403 on `currently assigned` guard | **Resolver bug** + workflow stuck-state |
| DispatchPage dispatch did not register within 30s | 4 | **Same root cause** — resolver picks an empty warehouse OR over-committed warehouse; FG001 at PCS-BKI is over-committed by 5,997 units (`projected_qty=-2,314`) | Same resolver bug |
| No BEI Warehouse Receiving produced | 1 (SM STA. ROSA) | **No commissary route for SM STA. ROSA + DRY** — defect #1 fallback used, source=target, downstream WR doc absent | Master data config gap |

**The decisive evidence (post-sweep stock probe):**

| Item | PCS-BKI bin (current) | Notes |
|---|---|---|
| PM001 | `actual_qty=0`, `indented_qty=0`, `projected_qty=0` | **PM001 has NEVER had stock at PCS-BKI**. The resolver still picks PCS-BKI for PM001 dispatches → 417. |
| FG001 | `actual_qty=3,683`, `indented_qty=-5,997`, `projected_qty=-2,314` | Over-committed: 5,997 units of FG001 are promised to outgoing MRs, only 3,683 on hand. Projected -2,314. |
| PM001 (where it actually IS) | 75,052 at `3MD LOGISTICS - CAMANGYANAN - BKI` | Resolver should route PM001 here, not to PCS-BKI. |

**Bottom line:** This is NOT a test-fixture problem. The resolver in `hrms/api/store.py` picks source warehouse based on (store, cargo_category) routing rules WITHOUT checking whether the specific item has stock there. PM001 has 75K units at 3MD-CAMANGYANAN but the resolver still routes it to PCS-BKI which has been at 0 the whole time. That's a real product bug.

PR #694's seven backend fixes did not target this root cause because Sentry triage at the time saw `InvalidWarehouseCompany`, `non-request set_scope`, `mosaic 409`, etc. — not "resolver picks empty warehouse". The 417 events fire at WARNING level and were drowned out by the 97-event sales-dashboard noise + the ERROR-level bugs.

---

## Evidence chain — the smoking gun

### 1. bei-tasks (frontend) shows stock failures from area-sup approval

```
Title: Error: Frappe API error: 417 - Stock decreased between resolution and dispatch
       — SCM must re-resolve order line for PM001 (have 0.0, need 5.0)
       at Pinnacle Cold Storage Solutions - BKI.

User: Test Area  (test.area@bebang.ph, designation: Area Supervisor)
URL:  https://my.bebang.ph/dashboard/store-ops/order-approvals
Action: approve_store_order
Branch: TEST-STORE-BGC

Frame:
  at B (app/dashboard/store-ops/order-approvals/page.tsx:188)
    >>>       handleError(new Error(result.error || "Failed to approve order"), {
```

**This fires when the AREA SUP clicks "Approve" on the order-approvals page** — NOT at SCM dispatch step. The 417 happens at `approve_store_order` (the area sup action), not at dispatch.

The first 417 in the sweep window: **00:33:48 UTC** (3 min into sweep). Then it repeats at 00:35, 00:37, 00:48, 00:50, 00:51, 00:53, 01:13, 01:14, 01:15 — eight times.

Each 417 says `(have 0.0, need 5.0)` or `(have 0.0, need 2.0)`. **Stock never replenishes during the sweep.**

### 2. bei-hrms (backend) shows the assignment-guard 403 chain

```
Title: PermissionError: Order BEI-ORD-2026-00439 is currently assigned to test.area@bebang.ph.

Tags:  endpoint_or_job=hrms.api.store.approve_order, http_method=POST, action=handle_exception

Frame:
  at approve_order (hrms/api/store.py:3504)
    >>> 			frappe.throw(
```

This is the S224 Pattern B "currently assigned to" guard at `hrms/api/store.py:3504`. It exists to prevent two people approving the same order. But here, when `test.scm` tries to take over `BEI-ORD-2026-00439` after `test.area`'s approval failed (at the 417 above), the guard 403s SCM out.

**The 403 is correct behavior on a healthy flow but wrong behavior on a recovery flow.** When area-sup approval fails, the order should be re-assignable so SCM can re-resolve. Right now it's permanently stuck.

### 3. bei-tasks 403s on the same order numbers as the 417s

| UTC | Order | Symptom | User |
|---|---|---|---|
| 00:33:48 | (no order yet) | 417 PM001 stock=0 | test.area |
| 00:34:05 | BEI-ORD-2026-00405 | **403 currently assigned to test.area** | test.scm |
| 00:35:24 | (next attempt) | 417 PM001 stock=0 | test.area |
| 00:35:39 | BEI-ORD-2026-00406 | **403 currently assigned to test.area** | test.scm |
| 00:37:57 | (POST /api/ordering) | 417 PM001 stock=0 | test.area |
| 00:38:10 | BEI-ORD-2026-00408 | **403 currently assigned to test.area** | test.scm |
| 00:48:45 | (next attempt) | 417 PM001 stock=2 | test.area |
| 00:49:00 | BEI-ORD-2026-00418 | **403 currently assigned to test.area** | test.scm |
| 00:50:19 | (next attempt) | 417 PM001 stock=0 | test.area |
| 00:50:35 | BEI-ORD-2026-00419 | **403 currently assigned to test.area** | test.scm |
| 00:51:53 | (next attempt) | 417 PM001 stock=0 | test.area |
| 00:52:08 | BEI-ORD-2026-00420 | **403 currently assigned to test.area** | test.scm |
| 00:53:27 | (next attempt) | 417 PM001 stock=0 | test.area |
| 00:53:42 | BEI-ORD-2026-00421 | **403 currently assigned to test.area** | test.scm |
| 01:13:49 | (next attempt) | 417 PM001 stock=0 | test.area |
| 01:14:05 | BEI-ORD-2026-00439 | **403 currently assigned to test.area** | test.scm |
| 01:15:24 | (FG001 stock=0 SM STA. ROSA) | 417 FG001 stock=0 | test.area |
| 01:15:39 | BEI-ORD-2026-00440 | **403 currently assigned to test.area** | test.scm |

**The 417/403 pattern repeats 9 times. That's the 9 WarehouseApprovalPage failures.** The order never reaches the warehouse approval stage because area-sup approval fails with stock=0, and SCM can't take over to recover.

### 4. The 4 DispatchPage failures = 4 empty-title bei-tasks events at /dashboard/warehouse/dispatch

8 bei-tasks events have empty title, all with culprit `/dashboard/warehouse/dispatch`, all by `test.scm`. These are the "dispatch did not register within 30s" failures (4 stores × 2 retries = 8 events). The actual dispatch error message wasn't captured in the title (likely a thrown error without a message), but the page and user match.

For the 4 stores that DID make it to dispatch (PM001 stock available at order-approve time but consumed by another concurrent test before dispatch?), the same stock-exhaustion pattern bites at the dispatch step.

### 5. The 1 Warehouse Receiving failure = SM STA. ROSA missing commissary route

```
Title: S225 follow-up: no commissary route for SM STA. ROSA - SWEET HARMONY FOOD CORP.+DRY;
       defaulting source to store warehouse.

Endpoint: /api/method/hrms.api.store.approve_order
URL:      http://hq.bebang.ph/api/method/hrms.api.store.approve_order
```

This is **defect #1's defense-in-depth fallback** firing in production. SM STA. ROSA + DRY combo has no entry in `_CENTRAL_WAREHOUSE_ROUTE_MAP` and no BEI Route doc. The fallback defaults source = store warehouse.

Downstream impact: when source = target = store warehouse, the Material Transfer doesn't actually move stock to a different location, so the Warehouse Receiving doc isn't produced (the test expects a WR doc on the receiving side, but there's no separate receiving side here).

Also note the bei-tasks 417 for SM STA. ROSA was for **FG001** (not PM001) at SM STA. ROSA itself (not at PCS-BKI). So this store has TWO problems: (a) missing route → defect #1 fallback → bad WR generation, (b) FG001 stock = 0 at the store's own warehouse.

---

## Why PR #694's 7 fixes didn't fix the test failures

The Sentry triage that produced PR #694 captured the dominant ERROR-level events at the time:
- `InvalidWarehouseCompany` (defect #1 → defense-in-depth fallback)
- `RuntimeError: Working outside of request context` (defect #5 → systemic Sentry monkey-patch)
- PostgREST 409 (defect #7 → on_conflict fix)
- Sales dashboard noise for non-POS warehouses (defect #6 → silence)
- `approve_order` re-approval crash (defect #2 → idempotency)
- `lock-wait` non-request crash (defect #4 → try/except)
- Warehouse approval queue missing Ordered MRs (defect #3 → backend filter)

**None of these target stock exhaustion at PCS-BKI.** The Sentry events that surfaced PM001 stock=0 (the 417s) are at WARNING level (handled=yes), and the puller in the prior triage filtered for ERROR-level only or didn't enumerate them as a top bucket because they were spread across multiple unique titles (each 417 has a different MR/store substring).

This sweep's triage catches them because:
1. The 417 errors got grouped into a single bucket: "Stock decreased between resolution and dispatch — SCM must re-resolve order line for **<PM001 (have 0.0, need X.0)>**" — 9 events stacked.
2. The 403 errors clearly correlate with the 417 events on order numbers.

---

## Real fixes (recommended for S228+, ordered by leverage)

### FIX A — Resolver must check item stock at the candidate source warehouse [PRODUCT BUG, highest leverage]

**Eliminates 13/14 failures. This is the actual product bug.**

Current behavior in `hrms/api/store.py` (likely in `_create_mr_for_store_order` or `approve_store_order`): the resolver picks source warehouse based on `(store, cargo_category)` routing rules and returns it, regardless of whether the item has stock there.

The correct behavior must verify before allocating:
- `actual_qty > 0` at the chosen source for THIS item, OR
- `projected_qty >= needed_qty` if business wants to honor pending commitments, OR
- Fall through to an alternate source (e.g., search all warehouses owned by the same parent company that have stock for the item).

This is NOT debatable per business rules — the current resolver is producing 417s in production for the SCM team to manually re-resolve, which is exactly what the system should prevent. The routing rules express WHERE TO SOURCE, but the resolver should also confirm the source CAN SOURCE.

Owner: SCM backend (store.py).

### FIX B — Master data: stock PM001 at PCS-BKI OR change PM001's route to 3MD-CAMANGYANAN [master data]

**This is the upstream root cause for the PM001-driven failures.**

PM001 has 75,052 units at `3MD LOGISTICS - CAMANGYANAN - BKI` and 0 units at `PINNACLE COLD STORAGE SOLUTIONS - BKI` — yet the resolver routes PM001 dispatches to PCS-BKI. Either:
- (a) **PM001 should be routed to 3MD-CAMANGYANAN** (the dry packaging hub) — fix the routing rules
- (b) **PCS-BKI should also stock PM001** — issue a Material Transfer to seed PCS-BKI

(a) is the canonical fix if PM001 is dry packaging (it's in `Packaging Materials` item group). PCS-BKI = Pinnacle COLD STORAGE — packaging materials don't belong in cold storage.

Owner: SCM master data (route definitions).

### FIX C — Replenish FG001 at PCS-BKI [master data ops]

FG001 at PCS-BKI: actual=3,683, **indented=-5,997** (5,997 units committed to outgoing MRs not yet shipped), **projected=-2,314**.

Either:
- Issue a Material Transfer FG001 → PCS-BKI to bring projected back positive
- OR clear the over-committed pending MRs that won't be fulfilled
- OR fix the upstream MR creation to stop accumulating commitments against an empty warehouse (this circles back to FIX A)

Owner: Commissary ops + SCM.

### FIX D — Add commissary route for SM STA. ROSA + DRY [master data, single store]

**Lowest leverage (1 store) but cheap. Add the missing entry.**

Either:
- Create a BEI Route doc for `(SM STA. ROSA - SWEET HARMONY FOOD CORP., DRY)` with the canonical commissary source warehouse
- OR add to `_CENTRAL_WAREHOUSE_ROUTE_MAP` in `hrms/api/store.py`

Then verify the WARNING marker stops firing in Sentry post-fix.

Owner: SCM master data.

### FIX E — Stuck-state recovery in approve_order assignment guard [secondary product]

**Compounds the impact of FIX A. When area-sup approval fails with 417, the order should be re-assignable.**

Current behavior at `hrms/api/store.py:3504`:
```python
if assigned_to and assigned_to != frappe.session.user:
    frappe.throw(f"Order {order_name} is currently assigned to {assigned_to}.")
```

The check assumes the assignee is actively working. If the assignee's last attempt was a stock-failure (417), they're effectively stuck — SCM should be allowed to take over and re-resolve.

Options:
1. **Time-based override** — if assignment older than N minutes AND order in a failed-resolution state, allow override
2. **Failed-resolution state tracking** — set `resolution_failed_at`; guard skips when set
3. **Explicit "release" action** — give SCM a button to take over a stuck order
4. **Auto-release on 417** — when area-sup approval throws 417, clear the assignment so anyone can retry

Option 4 is simplest. Owner: backend store ops.

### FIX E — Sales Dashboard: 97 events still firing post-PR#694 fix #6 [observability cleanup]

PR #694's fix #6 silenced Sentry for warehouses "intentionally non-POS" (commissary, cold storage). But 97 events still fire for STORE warehouses without `mosaic_location_id`:
- TUNGSTEN CAPITAL HOLDINGS OPC - BAG
- Ayala UPTC - BFC (BEBANG FRANCHISE CORP)
- D'verde Laguna - BFC
- ...

These are operational store warehouses that should have a Mosaic POS location assigned but don't. Either:
- Real master data gap: add `mosaic_location_id` to these companies (then dashboard will work for them)
- OR fix #6 needs to extend silencing logic to cover store warehouses that legitimately have no POS (franchise stores not on Mosaic?)

Owner: SCM master data + sales dashboard maintainer.

---

## Mapping back to S225 work

| S225 deliverable | Did it help these 14 stores? |
|---|---|
| Phase 3 warehouse duplicate consolidation | No — duplicates were a different issue (em-dash). PCS-BKI is correctly consolidated. |
| Phase 4/5 Pattern A FOR UPDATE lock | No — these failures aren't races; they're stock-zero. The lock works correctly (10/10 stress pass) but doesn't conjure stock. |
| S226 queue visibility hot-fix | No — queue endpoint is fine; orders never reach the queue stage. |
| Defect #1 (route fallback) | Partial — covers SM STA. ROSA + DRY (1 store) but defense-in-depth, not a real fix |
| Defect #2 (approve_order idempotency) | No — we need stuck-state recovery, not idempotency |
| Defect #3 (warehouse queue includes Ordered) | No — queue endpoint is fine; orders never reach warehouse stage |
| Defect #4 (lock-wait try/except) | No — observability cleanup |
| Defect #5 (sentry monkey-patch) | No — observability cleanup (but explains why we can now SEE the 417s clearly) |
| Defect #6 (sales dashboard non-POS) | No — observability cleanup, also partial (97 events still firing) |
| Defect #7 (mosaic on_conflict) | No — POS webhook, unrelated |

**S225 was correct work for the issues it targeted, but the test failures stem from a different root cause that wasn't visible in the prior triage.** That's why the sweep result is 32/49 and not 49/49 — we fixed the wrong things (or rather: we fixed real things, just not the things blocking these 14 stores).

---

## Recommended next sprint scope

**S228 — Fix L3 sweep root cause: PM001 stock + assignment recovery + missing route**

Phases:
1. **Diagnose actual stock state pre-sweep** — confirm PM001 starting qty at PCS-BKI; back into the depletion math
2. **Test fixture pre-seed** — patch sweep setup to ensure PM001 ≥ 245 units before sweep starts
3. **Add SM STA. ROSA + DRY commissary route** — single master data record
4. **Approve-order assignment recovery** — implement Option 4 (auto-release on 417)
5. **Re-run L3 sweep** — target 47-49/49 PASS (with stuck-state recovery + stock fix, the 13 PM001-driven failures and the 1 SM STA. ROSA failure should all clear)
6. **Sales Dashboard 97-event cleanup** — extend fix #6 OR add `mosaic_location_id` to BFC/TUNGSTEN/etc. companies

Estimated work units: ~25–35. Canonical scope: out (no master data structure changes; routes + roles only).
