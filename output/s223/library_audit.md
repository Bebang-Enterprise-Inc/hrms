# S223 Library Audit (Phase 0 Task 9-11)

**Captured:** 2026-04-25 PHT (Phase 0 boot)
**Branch:** `s223-fix-l3-store-chain-product-bugs`
**Worktrees:**
- hrms: `F:/Dropbox/Projects/BEI-ERP-s223-fix-l3-store-chain-product-bugs` (HEAD `dd664302b`)
- bei-tasks: `F:/Dropbox/Projects/bei-tasks-s223-fix-l3-store-chain-product-bugs` (HEAD `f2d10e22`)

---

## Page Object REST-fallback inventory (read-only audit)

| Page Object | Has REST fallback today? | Used for | S223 action |
|---|---|---|---|
| `OrderApprovalPage` | YES — S221, lines 86-117 (`getReadbackCtx().post('/api/method/hrms.api.store.approve_order')`) | First approval (test.area) | **Phase 6 revert** |
| `DispatchPage` | YES — S222, lines 174-190 (`queryDocs('Stock Entry Detail')` for material_request) | Warehouse dispatch (test.scm) | **Phase 6 revert** |
| `WarehouseApprovalPage` | NO (file does not exist; flow handled inline by `usePendingMRs` + `approveMR` from `hooks/use-warehouse.ts`) | Second approval (test.scm) | Confirm via Phase 1 trace whether a Page Object is needed |
| `ReceivingPage` | (TBD — verified Phase 1) | Store receiving (test.receiver) | n/a unless surfaced in trace |
| `StoreOrderingPage` | (TBD — verified Phase 1) | Store order submit (test.area) | n/a unless surfaced in trace |

**Legitimate post-click readback usages (must be retained, marked with `// VERIFICATION-POST-UI:`):**
- `OrderApprovalPage:39` — pre-click bypass (S221 — to be REMOVED)
- Other Page Objects use `readDoc`/`getReadbackCtx`/`queryDocs` after click for state verification — confirmed during Phase 6.

---

## data-testid coverage (current state)

Verified via `grep -c "data-testid"` on the affected pages:

| Page | Testid count | Notes |
|---|---|---|
| `app/dashboard/warehouse/dispatch/page.tsx` | 1 | Pattern A surface — needs more for inner modal |
| `app/dashboard/warehouse/approve/page.tsx` | 0 | Pattern B surface — needs full instrumentation |
| `app/dashboard/store-ops/order-approvals/page.tsx` | 3 | DEFECT-11 surface — partially covered |

**Gap closure plan:** S223 phases 2B/3B/4 add testids as needed via the registry namespace below.

---

## Test ID Registry — S223 reservations

The current TEST_IDS registry lives at:
```
bei-tasks/tests/e2e/support/selectors.ts
```

The plan asked to create `tests/e2e/test-ids.ts` if absent OR extend the existing registry. Since `selectors.ts` is the established SSOT, S223 additions go there.

**S223 reserved namespaces:**
- `s223-dispatch-create-transfer-modal-submit` — inner Create Transfer button in dispatch dialog
- `s223-dispatch-modal-status-toast` — success indicator shown after SE creation
- `s223-approve-mr-row-${mrName}` — per-MR row testid in warehouse approve list
- `s223-order-approval-date-picker` — date filter on order-approvals page (DEFECT-11)
- `s223-order-approval-show-all-toggle` — possible "show beyond today" toggle (DEFECT-11 fix proposal)

Phase 2B/3B/4 verification gates check that any newly-added `data-testid` matches one of these reservations.

---

## Pre-loaded findings fact-freshness check (Phase 0 task 11)

| Pre-loaded fact | Verified? | Evidence |
|---|---|---|
| Pattern A endpoint = `hrms.api.warehouse.create_stock_transfer` | ✅ | `hrms/api/warehouse.py:1431 def create_stock_transfer(` |
| Pattern B + DEFECT-11 narrowing at `order-approvals/page.tsx:548` | ✅ (form: `useState(todayStr())`, not `selectedDate=todayStr()`) | `app/dashboard/store-ops/order-approvals/page.tsx:548 const [selectedDate, setSelectedDate] = useState(todayStr());` |
| Pattern B target page (`approve/page.tsx`) — same `todayStr()` pattern? | ❌ **NOT same root cause** | `grep todayStr app/dashboard/warehouse/approve/page.tsx` → 0 hits. Pattern B narrowing is at a different layer (likely `usePendingMRs` SWR cache or backend `get_pending_material_requests`). Phase 3A must investigate. |
| Pattern C Sentry context = `module="ordering"` | ✅ | `hrms/api/store.py:3065 module="ordering"` (in submit_order); also lines 2554, 3003, 2230 |
| ORTIGAS HQ TIN row in registry = `688-721-280-00000` | ✅ (file row 38 = file line 77) | `hrms/data_seed/company_register_2026-04-14.csv` line 77, id "38": `BEIFRANCHISE FOOD OPC,...,688-721-280-00000` |
| ORTIGAS branch TIN row = `688-721-280-00001` | ✅ (file row 49 = file line 50) | `hrms/data_seed/ENTITY_TIN_RDO_2026-02-27.csv` line 50, id "49": `Ortigas Greenhills,688-721-280-00001` |

**Path correction:** Plan referenced `data/ENTITY_TIN_RDO_2026-02-27.csv` but actual path is `hrms/data_seed/ENTITY_TIN_RDO_2026-02-27.csv`. Content matches.

**Important update for Phase 3A:** Pattern B (warehouse/approve/page.tsx) does NOT share `todayStr()` root cause with DEFECT-11. The two must be investigated separately. The order-approvals narrowing IS the pre-loaded `useState(todayStr())` filter. Pattern B will require trace evidence to identify its root cause.

---

## Vitest setup status

`bei-tasks/package.json` — vitest is in `devDependencies` but has no `"test"` script. Plan Phase 2B task 7 requires adding `"test": "vitest"` if a component test is needed.

---

## Trace zip availability

`C:/Users/Sam/AppData/Local/Temp/bei-pw-artifacts/` is empty (only `.last-run.json`). Playwright cleanup has wiped the S222 trace zips. **Phase 1 will need to regenerate traces** by running single-store playwright executions against each cluster representative.
