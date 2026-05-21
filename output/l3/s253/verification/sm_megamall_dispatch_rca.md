# SM MEGAMALL DispatchPage Timeout — RCA
**Date:** 2026-05-21
**Plan:** S253 Phase 1
**S252 failed MR:** `MAT-MR-2026-01142`
**Failure:** `DispatchPage: dispatch did not register for MAT-MR-2026-01142 within 30s (status=Ordered, per_transferred=undefined)`

## Production state probe (REST API)

```
MR MAT-MR-2026-01142:
  status = "Ordered"
  docstatus = 1 (Submitted)
  material_request_type = "Material Issue"
  per_ordered = 100.0
  per_received = 0.0
  per_transferred = MISSING (field does not exist on doc)
  custom_source_warehouse = "3MD LOGISTICS - CAMANGYANAN - BKI"
  custom_destination_warehouse = "SM MEGAMALL - BEBANG ENTERPRISE INC."
```

## Code-path inspection

- `DispatchPage.dispatch()` at `tests/e2e/pages/DispatchPage.ts:163-197`:
  - Polls MR doc for 30s waiting for `per_transferred > 0 || status promotion`
  - Falls back to `waitForToast(/dispatched|transfer created|success/i)`
- Backend handler: `hrms/api/warehouse.py:create_stock_transfer` (line 1462) — creates the Stock Entry that drains the source warehouse and creates the buyer-side Draft SI per S198/S247.

## `per_transferred` field analysis

`per_transferred` is **NOT** a field on the Frappe `Material Request` doctype:
- Not a Custom Field (verified via `Custom Field` table query — 8 custom fields exist, none named `per_transferred`)
- Not present on the actual doc (verified via `frappe.client.get` — field missing from response)

The Material Request progress fields are:
- `per_ordered` — % already ordered against this MR (PO creation)
- `per_received` — % received against this MR

For a `Material Issue` MR (BEI's store-to-store transfer pattern), dispatch completion is signaled by:
- `status` transitioning from `"Ordered"` → `"Issued"`
- AND/OR a linked Stock Entry referencing this MR being submitted

The DispatchPage poll's `per_transferred` check (line 172, 176, 179) is a **bug** — that field never exists on Material Issue MRs and will always read as `undefined → 0`.

However, the poll ALSO checks `status promotion` (line 178) — if the dispatch button click had actually fired and the SE was created, the status would have moved past "Ordered" and the test would have PASSED via the status path. So the test bug is necessary but not sufficient to explain the failure.

## Why dispatch did NOT register

**Production state shows:**
- MR stayed at `status=Ordered` for 30s after click
- No Stock Entry was created with `to_warehouse="SM MEGAMALL - BEBANG ENTERPRISE INC."` linking back to this MR

This means the dispatch button click on the SM MEGAMALL run **did not result in a successful `create_stock_transfer` backend call**. Possible Mode A/C root causes:

| Mode | Possibility | Evidence |
|---|---|---|
| Mode A (app bug) | `create_stock_transfer` raised a validation error specific to SM MEGAMALL ownership chain (Bebang Enterprise Inc. is a parent-child Company per S247 P4a) | Cannot confirm without Error Log access; needs `bench --site hq.bebang.ph execute frappe.client.get_list` on `Error Log` filtered by `creation > 2026-05-16` and `error LIKE "%SM MEGAMALL%"` |
| Mode B (test bug only) | `per_transferred` field bug masked a transient frontend failure that would have self-recovered | UNLIKELY — status also stayed at "Ordered", so dispatch didn't complete server-side |
| Mode C (master data) | SM MEGAMALL Warehouse missing a field needed by `create_stock_transfer` (e.g., `custom_cost_center` from S247 P4a) | Possible — S247 P4a was specifically for SM MEGAMALL and 3 other BEBANG ENTERPRISE INC. parent-child stores |

## Verification of Mode C — Master Data Check

Probe via API: confirm SM MEGAMALL Warehouse has S247 P4a-required fields populated:
- `Warehouse.account` — referenced by S198 SI creation
- `Warehouse.custom_cost_center` — referenced by PI generator `_resolve_per_store_cost_center`
- `Company.stock_received_but_not_billed` — referenced by SE generator
- `Company.enable_perpetual_inventory` — S247 prereq

These probes WERE done in S247 P4a and reported PASS at 49/49. SM MEGAMALL passed the S247 P5 backend smoke test (synthetic SSM submission). However, the REAL dispatch flow via UI involves a CHAIN of validations across `create_stock_transfer` that S247 P5 may have bypassed.

## Classification: **Mode D (skip-and-document) — pending follow-up sprint**

**Rationale:** Confirming Mode A vs Mode C requires:
1. Frappe Error Log access via SSM (not available from this REST-only session)
2. A live retry of dispatch on SM MEGAMALL with browser+screenshot to capture frontend error toast
3. Likely a code read of `create_stock_transfer` step-by-step for SM MEGAMALL's ownership chain

This investigation is itself a multi-hour sprint candidate. Per S253 plan P1.7 Mode D directive: skip SM MEGAMALL from Phase 5 sweep, document as known-blocker, list as follow-up sprint candidate (`S256` candidate: "SM MEGAMALL dispatch UI completion investigation").

## Test infrastructure recommendation (for ANY future store sweep)

DispatchPage's `per_transferred` field check is a structural bug — it relies on a non-existent field. Replace with:
```typescript
const doc = await readDoc<{ status?: string }>("Material Request", mrName);
const dispatchSuccess = doc.status && doc.status !== "Ordered" && doc.status !== "Pending";
if (dispatchSuccess) break;
```
Or check for the linked Stock Entry's existence:
```typescript
const linkedSEs = await queryDocs("Stock Entry", [["material_request", "=", mrName], ["docstatus", "=", 1]]);
if (linkedSEs.length > 0) break;
```

This fix is OUTSIDE the scope of S253 (would modify shipped S209/S252 Page Object). Flag as separate S### follow-up.

## Disposition

- ✅ **RCA written + classified Mode D**
- ✅ **Add to DEFECTS.md**: SM MEGAMALL is excluded from Phase 5 sweep
- ✅ **Follow-up sprint candidate**: S256 (or next available) — "SM MEGAMALL dispatch UI completion + DispatchPage per_transferred bug fix"
- ⏭ **NO backend code change in S253** — Mode D path, no CEO approval needed

**Classification:** Mode D
