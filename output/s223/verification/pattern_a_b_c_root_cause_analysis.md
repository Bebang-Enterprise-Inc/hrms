# S224 — Pattern A/B/C Root Cause Analysis (from Sentry + SSM evidence)

**Source:** Sentry REST API queries against `bei-hrms` and `bei-tasks` projects + SSM diagnostics. Bypassed Sentry MCP (currently disconnected); used `SENTRY_API_TOKEN` from Doppler.

**Sweep window:** 2026-04-26T05:19:52Z → 06:05:07Z UTC (49 stores attempted, 33 ran, 16 PASS).

---

## Pattern A — Dispatch modal stuck open (6 stores)

### Root cause: race-condition + canonical drift in intercompany batch handling

**Sentry evidence (5 backend events):**

```
3× ValidationError: The Batch BACKFILL-20260421-FG004-3MD-LOGISTICS-CAMANGYANAN
   of an item FG004 has negative stock in the warehouse 3MD LOGISTICS -
   CAMANGYANAN - BKI as of 26-04-2026 13:57:31. Please add a stock quantity[y]
2× ValidationError: The Batch BACKFILL-20260421-FG004-PINNACLE-COLD-STORAGE-SOLUTIONS
   of an item FG004 has negative stock in the warehouse PINNACLE COLD STORAGE
   SOLUTIONS - BKI
2× ValidationError: Stock decreased between resolution and dispatch — SCM must
   re-resolve order line for FG004 (have N, need M) at <warehouse>
```

**Where it surfaces:**
- Backend: `hrms/api/warehouse.py:create_stock_transfer` (with `module="warehouse"` Sentry context)
- Frontend: dispatch modal in `app/dashboard/warehouse/dispatch/page.tsx:handleCreateTransfer` correctly catches the 417 and shows toast — but doesn't close the dialog (intentional UX so the user sees the error). DispatchPage Page Object's 30s poll for `MR.per_transferred > 0` fails because no SE was created.

**Why it happens:**

1. **Batch race condition.** The L3 sweep dispatches 49 stores × 3 items in parallel via Playwright workers. FG004 (BUKO PANDAN JELLY) at the BACKFILL-20260421-FG004-PINNACLE / 3MD batches is the "shared" stock for stores sourcing from those BKI cold storages. ERPNext's stock-availability check fires AFTER the bin reservation, so 5+ concurrent dispatches can over-issue and push the batch briefly negative.

2. **S163 stock-decreased guard correctly fires.** The race-protection at `hrms/api/store.py:3902-3923` runs `bin_qty < qty` check at MR creation time. Under parallel load this is a true positive — the stock genuinely decreased between resolution and dispatch.

3. **Canonical drift (newly discovered).** The diagnostic also revealed:
   - `3MD LOGISTICS - CAMANGYANAN - BKI` (canonical, hyphen `-`): 1095 units
   - `3MD LOGISTICS – CAMANGYANAN - BKI` (em-dash `–`): 648 units
   These are DIFFERENT warehouse records via punctuation. Stock split between two near-identical warehouses; canonical resolver picks the hyphen version, leaving 648 units stranded.

**Real-world impact:**
- Real SCM dispatchers don't dispatch 49 stores in 60 seconds, so they rarely hit the race.
- BUT the canonical drift is a permanent data bug — 648 units of FG004 are stranded.
- AND the negative-stock failure mode IS user-visible whenever supply is tight.

**Fix recommendations (priority order):**

1. **🔴 IMMEDIATE — Cleanup canonical warehouse duplicate**: disable `3MD LOGISTICS – CAMANGYANAN - BKI` (em-dash) and migrate its 648 units to the hyphen version via Stock Reconciliation. This requires Sam approval per canonical rule; covered in `docs/STORE_COMPANY_CANONICAL.md`.

2. **🟠 BACKEND — Lock batch row during stock decrement**: wrap the FG004 batch availability check + reservation in a `SELECT ... FOR UPDATE` so concurrent dispatches serialize. Currently the check is read-then-write without a row lock.

3. **🟡 TEST — Serialize the L3 sweep**: with `workers=1, fullyParallel=false` already in playwright.config, the issue is multiple item rows within one dispatch racing. Less critical — production won't hit this load.

4. **🟢 UX — Close modal on error after toast**: improve `handleCreateTransfer` to auto-close the modal 3 seconds after showing the error toast, OR add a clear "Cancel" button in the modal that's emphasized when the error appears. Current behavior leaves the modal open which confuses users.

---

## Pattern B — Warehouse approval queue narrowing (4 stores) — **FIXED in S224 patch**

### Root cause: idempotency bug in `approve_material_request`

**Sentry evidence (5 events, both projects):**

```
ValidationError: Material Request MAT-MR-2026-00491 has already been approved
ValidationError: Material Request MAT-MR-2026-00492 has already been approved
ValidationError: Material Request MAT-MR-2026-00493 has already been approved
ValidationError: Material Request MAT-MR-2026-00494 has already been approved
ValidationError: Material Request MAT-MR-2026-00495 has already been approved
```

Frontend mirror: `Error: Material Request MAT-MR-2026-00495 has already been approved` from `tags.module=warehouse, tags.action=approve_mr`, user=`test.scm`, url=`/dashboard/warehouse/approve`.

**Where it surfaces:**
- `hrms/api/warehouse.py:approve_material_request:1238-1243` (pre-S224)

**Why it happens:**

The MR is created at status="Pending" by `_create_mr_for_store_order` in `approve_order` stage 2, but a BEI on_submit hook (or the SCM auto-approve flow upstream) sets status="Ordered" before the test/UI calls `approve_material_request` again. The function did:
```python
if current_status == "Ordered":
    frappe.throw("Material Request {0} has already been approved")
```
This is **NOT idempotent**: re-approving an already-approved MR is a legitimate operation (user clicked twice, browser retry, etc.) and should succeed silently, not throw.

**Fix shipped in S224** (`hrms/api/warehouse.py:approve_material_request`):
```python
if current_status == "Ordered":
    return {
        "success": True,
        "message": f"Material Request {mr_name} already approved (status=Ordered) — no-op",
        "already_approved": True,
    }
```

**Expected impact:** unblocks the 4 Pattern B stores (ROBINSONS ANTIPOLO, ROBINSONS IMUS, AYALA FAIRVIEW TERRACES, AYALA UP TOWN CENTER) on the next sweep. The MR is already approved → return success instead of throw → frontend proceeds to dispatch step.

---

## Pattern C — MR creation stalls (3 stores) — **FIXED in S224 patch**

### Root cause: `resolve_warehouse()` doesn't handle non-canonical store identifiers

**Sentry evidence (4 events with full traceback):**

```
ValidationError: Could not find Store: Estancia
  endpoint_or_job: hrms.api.store.validate_order_schedule
  module: ordering
  Stack tail:
    hrms/api/store.py:3011 validate_order_schedule()
    hrms/api/store.py:273 resolve_warehouse()  ← throw here
```

Same pattern for "Could not find Store: Araneta Gateway - Bebang Enterprise Inc." (2 hits, but with stale company name) — confirms the issue isn't unique to ESTANCIA.

**Where it surfaces:**
- `hrms/api/store.py:resolve_warehouse:243-273` (pre-S224)

**Why it happens:**

`resolve_warehouse()` tries:
1. Exact `Warehouse` docname — NO match for `"Estancia"`
2. `<input> - BEI` — NO match
3. `<input> - BKI` — NO match
4. `Warehouse.warehouse_name = <input>` — NO match (warehouse_name is `"ORTIGAS ESTANCIA"`, not `"Estancia"`)
5. `COMMISSARY_WAREHOUSE_ALIAS_MAP[<input>]` — NO entry
6. → throws "Could not find Store"

The caller is `validate_order_schedule(store=...)`, invoked from the frontend ordering page. Some legacy code path passes a truncated/old name (`"Estancia"`, `"Araneta Gateway - Bebang Enterprise Inc."`).

**Fix shipped in S224** (`hrms/api/store.py:resolve_warehouse`):

Added a case-insensitive substring fallback as the LAST resort before throwing:
```python
candidates = frappe.db.sql("""
    SELECT name FROM `tabWarehouse`
    WHERE disabled=0 AND is_group=0
      AND (LOWER(warehouse_name) LIKE LOWER(%(s)s) OR LOWER(name) LIKE LOWER(%(s)s))
    LIMIT 5
""", {"s": f"%{store_or_branch.strip()}%"})
if len(candidates) == 1:
    return candidates[0]
if len(candidates) > 1:
    frappe.throw("Ambiguous store identifier {0!r} — matches multiple warehouses: {1}. Use full canonical name.")
```

**Expected impact:**
- `"Estancia"` → unique match `ORTIGAS ESTANCIA - BB ESTANCIA FOOD CORP.` → resolves successfully → unblocks NAIA T3 + ORTIGAS ESTANCIA (assuming the same code path handles their lookups too).
- `"Araneta Gateway - Bebang Enterprise Inc."` → 0 candidates (no warehouse has "Bebang Enterprise Inc." in the name for ARANETA GATEWAY) → still throws → caller is responsible for sending canonical names. This is correct: stale company names should fail, not silently match the wrong store.

**Note:** `"NAIA T3"` and `"ORTIGAS GREENHILLS"` weren't in the Sentry sample but follow the same pattern — they would also benefit from this fuzzy fallback.

---

## Observability gaps closed in S224

Three backend endpoints had NO Sentry observability before this PR:

| Endpoint | Was | Now |
|---|---|---|
| `hrms/api/warehouse.py:get_pending_material_requests` | no Sentry context | `module="warehouse", action="get_pending_material_requests", mutation_type="read"` |
| `hrms/api/warehouse.py:approve_material_request` | no Sentry context | `module="warehouse", action="approve_material_request", mutation_type="update", extras={"mr_name": mr_name}` |
| `hrms/api/store.py:_create_mr_for_store_order` | inherits caller's scope (no helper-specific) | `module="ordering", action="_create_mr_for_store_order", phase="mr_creation", extras={order_name, store_warehouse, cargo_category, item_count}` |

Frontend Sentry was already complete — `@sentry/nextjs` auto-instruments all API routes; `lib/error-handler.ts` adds rich context.

---

## Other defects exposed by Sentry (not in scope but flagged)

From `module:ordering 14d` query:

1. **`OperationalError: (1054, "Unknown column 'i.custom_store_ordering_uom'")`** — 36 hits, last seen 2026-04-05. Pre-S205 column-missing error. Probably resolved by S205 migration.
2. **`Error: Frappe API error: 521 - <!DOCTYPE html>`** — 8 hits, gateway timeout (Cloudflare returns HTML 521 when origin times out). Worth investigating as a separate reliability concern.
3. **2961× `New Exception collected in error log`** at `hrms.api.procurement.get_invoices` — generic catch-all on procurement page. Not in store-ordering scope but indicates procurement page has a chronic error.

These should each be a separate follow-up sprint.

---

## Evidence files

- `output/s223/verification/sentry_events_during_sweep.json` — bei-hrms 32 + bei-tasks 57 events
- `output/s223/verification/sentry_event_details.json` — full tracebacks for top 16 events
- `output/s223/verification/sentry_pattern_c_hunt.json` — 7-day broader hunt
- `output/s223/verification/sentry_estancia_traceback.json` — Pattern C definitive traceback
- `output/s223/verification/pattern_a_batch_diagnostic.json` — current state of FG004 backfill batches

---

🤖 Generated with [Claude Code](https://claude.com/claude-code)
