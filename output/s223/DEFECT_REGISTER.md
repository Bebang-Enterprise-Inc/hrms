# S223 DEFECT_REGISTER (Phase 1 output)

**Source of trace evidence:** `output/l3/s222/TRIAGE_REPORT.md` (committed to `origin/production` at SHA `5e8305ea6`)  
**Trace zips on disk:** wiped by Playwright cleanup; `C:/Users/Sam/AppData/Local/Temp/bei-pw-artifacts/` is empty. Phase 2A/3A/4 will produce fresh trace evidence via real-browser manual reproduction.  
**Investigation method:** S222's trace-first analysis is canonical for this registry. Trace zip identifiers preserved as historical references; cluster reps (AYALA SOLENAD, SM STA. ROSA, NAIA T3) get fresh trace generation in Phase 2A/3A/4.

---

## The 13 failing stores — one row per store

| # | Store | Pattern | Failure layer | Element | Network call (per S222 trace) | Fix lands in (file) | Hypothesized cause |
|---|---|---|---|---|---|---|---|
| 1 | AYALA SOLENAD | A | dispatch modal | inner "Create Transfer" button (ref=e29 in trace) | POST `/api/method/hrms.api.warehouse.create_stock_transfer` either fails silently OR returns success:false; modal stays OPEN | `bei-tasks/app/dashboard/warehouse/dispatch/page.tsx` (handleCreateTransfer + dialog) AND/OR `hrms/api/warehouse.py:create_stock_transfer` | Intercompany Material Issue path validation fails for these source warehouses; error not surfaced or swallowed by route.ts default `success ?? true` shape (Phase 2A confirms via fresh trace) |
| 2 | AYALA VERMOSA ★ | A | dispatch modal | inner "Create Transfer" button | same as AYALA SOLENAD | same | same — NEW regression from S221 (was PASS) |
| 3 | CTTM TOMAS MORATO | A | dispatch modal | inner "Create Transfer" button | same | same | same |
| 4 | SM GRAND CENTRAL | A | dispatch modal | inner "Create Transfer" button | same | same | same |
| 5 | SM BICUTAN | A | dispatch modal | inner "Create Transfer" button | same | same | same |
| 6 | SM MARIKINA | A | dispatch modal | inner "Create Transfer" button | same | same | same |
| 7 | SM STA. ROSA | B | warehouse approval queue | MR row never appears in approval list; Page Object `clickApprove(mrName)` times out | GET `/api/warehouse?action=pending_mrs` returns the MR but UI doesn't render it (per S222 trace: "page only rendering an old MR (MAT-MR-2026-00120 for SM Tanza from a prior sweep day)") | `bei-tasks/app/dashboard/warehouse/approve/page.tsx` AND/OR `bei-tasks/hooks/use-warehouse.ts:usePendingMRs` AND/OR `hrms/api/warehouse.py:get_pending_material_requests` | Client-side narrowing in render OR backend filter scope; same CLASS as DEFECT-11 but NOT same `todayStr()` line — `approve/page.tsx` has 0 `todayStr()` references |
| 8 | ROBINSONS IMUS ★ | B | warehouse approval queue | same as SM STA. ROSA | same | same | same — NEW regression from S221 |
| 9 | SM SOUTHMALL ★ | B | warehouse approval queue | same | same | same | same — NEW regression from S221 |
| 10 | ROBINSONS ANTIPOLO | B | warehouse approval queue | same | same | same | same |
| 11 | NAIA T3 | C | order → MR transition | ledger has only `order-create`, no `mr-create`; Store Order detail shows "Delivery: 2026-04-25" | POST to `submit_order` succeeds but `_create_material_request` not invoked OR no-ops silently | `hrms/api/store.py:submit_order` (and helper `_create_material_request`) | Hardcoded skip-list, missing canonical row, or Material-Issue MR type guard not matching these 2 stores |
| 12 | ORTIGAS ESTANCIA | C | order → MR transition | same as NAIA T3 | same | same | same |
| 13 | ORTIGAS GREENHILLS | C / Allowed Skip | order → MR (skip-guard lapsed in S222) | "allowEmptyTin: True" fixture should have skipped before submit; instead reached submission and got stuck | n/a | Phase 5 applies HQ TIN `688-721-280-00000`; spec skip-guard reviewed if needed | empty `Customer.tax_id` for ORTIGAS GREENHILLS billing Customer (BILLING_CUST_TIN_EMPTY canonical violation — only one) |

★ = NEW regression in S222 (was PASS in S221).

---

## DEFECT-11 (Order Approval narrowing) — currently masked by S221 REST fallback

DEFECT-11 will surface ONCE Phase 6 reverts the S221 fallback. The narrowing affects ~5 stores per S221 closeout (festival mall alabang etc.). Pre-loaded hypothesis (from S223 audit, verified): `bei-tasks/app/dashboard/store-ops/order-approvals/page.tsx:548 const [selectedDate, setSelectedDate] = useState(todayStr());` defaults to PHT-today, narrowing the queue to "orders for today only".

| Store cluster | Pattern | Failure layer | Element | Fix lands in | Hypothesized cause |
|---|---|---|---|---|---|
| FESTIVAL MALL ALABANG (S221 canonical example) + ~4 more — count refined in Phase 3A trace | DEFECT-11 | order approval queue rendering | order row absent from `/dashboard/store-ops/order-approvals` for orders with `delivery_date != today` | `bei-tasks/app/dashboard/store-ops/order-approvals/page.tsx:548` | `useState(todayStr())` initial value of `selectedDate` filters out non-today delivery orders client-side |

---

## Phase 2A SSM Probe Findings (2026-04-25 PHT)

**Probe artifacts:**
- `output/s223/verification/pattern_a_probe_results.json` — full probe output
- `output/s223/verification/mr_state_diag.json` — MR state inspection
- `scripts/s223_pattern_a_probe.py` — probe script
- `scripts/s223_diag_mr_state.py` — diagnostic script

**Key code-level findings:**

1. **Approval flow architecture:** `approve_order` is a TWO-STAGE flow:
   - Stage 1 (test.area): transitions to "Pending Warehouse Manager", returns success, **MR NOT created yet**.
   - Stage 2 (test.scm via `approve_order` with Warehouse Manager role): transitions to "Fully Approved", AND calls `_create_mr_for_store_order` which submits the MR (docstatus=1).
   - `approve_material_request` (warehouse approval queue button): operates on the EXISTING submitted MR — only sets `status="Ordered"` and `per_ordered=100`. Does NOT submit (already submitted) and does NOT cancel.

2. **Status transition gates the queue surfaces:**
   - `get_pending_material_requests` filters `status IN ['Pending', 'Partially Ordered']` AND `docstatus=1`. After MR creation (status=Pending) → MR shows in `/dashboard/warehouse/approve` queue.
   - After `approve_material_request` sets status="Ordered" → MR drops OUT of pending queue, into `get_ready_for_dispatch` queue.

3. **Probe limitation:** the probe called `approve_order` only ONCE (as test.area). Stage 2 was attempted via `approve_material_request` instead of a second `approve_order` as test.scm. This means the probe found stale MRs from previous days' runs (matching `custom_store_order` due to docname sequence reuse after cleanup) rather than fresh MRs from today's run. The `mr_lookup_post_scm` returned None because stale MRs were already at docstatus=2 (cancelled). **No fresh `create_stock_transfer` attempt was made by the probe.**

4. **Stale MR data evidence (likely unrelated to current sprint):**
   - MAT-MR-2026-00437 has `custom_destination_warehouse = AYALA FAIRVIEW TERRACES - BEBANG FT INC.` despite `custom_store_order = BEI-ORD-2026-00400` (current order is for AYALA SOLENAD). This is from yesterday's run; the MR docname reuse is artifactual.

**What this means for Phase 2A's CEO-mandated manual reproduction:**
- The probe confirmed the approval flow architecture matches the plan's understanding.
- The actual `create_stock_transfer` failure mode for Pattern A's 6 stores remains unverified in this session — would require either (a) a refined probe that does both approval stages OR (b) live browser repro per the plan's CEO directive.

**Likely Pattern A root cause (code-analysis hypothesis, requires live verification):**
The dispatch modal stays OPEN because `result.success === false` keeps the dialog mounted (per `bei-tasks/app/dashboard/warehouse/dispatch/page.tsx:74-99`):
```tsx
if (result.success) { closeTransferDialog(true); ... return; }
handleError(result.error || "...", {...});  // toast shown, dialog stays open
```

If the backend `create_stock_transfer` raises a `frappe.ValidationError` (e.g., insufficient stock at PINNACLE/3MD source warehouses, intercompany contract resolution miss, or SCM permission gate), the route.ts catch block at line 850-870 returns `{success: false, error: "..."}` with proper status code. The frontend shows the error toast but keeps the dialog open. The DispatchPage Page Object's 30s poll for `MR.per_transferred > 0` or SE existence times out (no SE created → no signal). Test fails.

**Pattern A fix design (Phase 2B):** improve error visibility + add a data-testid the test can read to detect the error state. Closing the modal on error would HIDE the error from real users (anti-pattern per "Correct Over Fast" rule). The right fix is to surface the error CLEARLY in-modal and provide a testable error indicator.

---

## Pattern A Investigation Summary (Phase 2A will produce fresh trace)

**What is broken (in product terms):** clicking the inner "Create Transfer" button inside the warehouse dispatch dialog does NOT result in a Stock Entry being created for these 6 stores. The dialog stays open. No Stock Entry exists. No success toast. Either no error toast OR an error toast that the test doesn't see.

**Who hits it:** `test.scm@bebang.ph` user when dispatching warehouse requests for AYALA SOLENAD, AYALA VERMOSA, CTTM TOMAS MORATO, SM GRAND CENTRAL, SM BICUTAN, SM MARIKINA — all stores sourced from PINNACLE COLD STORAGE SOLUTIONS - BKI or 3MD LOGISTICS - CAMANGYANAN - BKI (intercompany Material Issue path).

**What real users see:** same broken UI. Real SCM staff click "Create Transfer", see no progress, must abandon the dialog or refresh.

**Why S222 fallback didn't help (per S222 trace evidence):** the fallback queries `Stock Entry Detail` for child rows linked to the MR. But if `create_stock_transfer` errors out, no SE is created, so no SE child row exists, so the fallback finds nothing. The fallback can only help when an SE was created but its `per_transferred` field didn't bump — not when the SE was never created at all.

**Likely fix layer:** combination of frontend (handle error case in `handleCreateTransfer`, surface error to test/user, ensure dialog closes on either path) AND backend (ensure `create_stock_transfer` consistently raises on validation failure rather than returning `success: false`). Phase 2A confirms via fresh trace.

---

## Pattern B Investigation Summary (Phase 3A will produce fresh trace)

**What is broken:** `/dashboard/warehouse/approve` queue does NOT render the MR for these 4 stores. The Page Object's `clickApprove(mrName)` cannot find the row.

**Who hits it:** `test.scm@bebang.ph` user when reviewing the warehouse approval queue for SM STA. ROSA, ROBINSONS IMUS, SM SOUTHMALL, ROBINSONS ANTIPOLO.

**What real users see:** SCM team logs in, expects to see fresh store-side-approved MRs in the queue, instead sees only stale prior-day MRs.

**Why S221 fallback didn't help:** S221 fallback was a REST escape for `OrderApprovalPage` (first approval). Pattern B is at `WarehouseApprovalPage` (second approval) which has no fallback. The narrowing is purely a UI render bug: backend returns the MR but UI omits it.

**Critical Phase 0 finding:** `app/dashboard/warehouse/approve/page.tsx` does NOT contain `todayStr()` — Pattern B is NOT the same root cause as DEFECT-11. Phase 3A must determine whether the narrowing is:
- (a) inside `usePendingMRs` SWR hook (e.g., stale cache, failure to revalidate)
- (b) inside backend `hrms.api.warehouse.get_pending_material_requests` (filter scope, pagination, role gate)
- (c) inside `bei-tasks/app/dashboard/warehouse/approve/page.tsx` rendering itself

**Likely fix layer:** depends on Phase 3A finding. Most likely (b) backend filter — analogous to how S221 root-cause turned out to be backend `get_pending_orders` returning narrowed scope.

---

## Pattern C Investigation Summary (Phase 4 will produce fresh trace + probe)

**What is broken:** `submit_order` succeeds (Order docname returned, ledger has `order-create` entry) but the dual-approval chain to MR creation does not fire for NAIA T3 and ORTIGAS ESTANCIA. The order sits at "Delivery: 2026-04-25" indefinitely.

**Who hits it:** `test.area@bebang.ph` submitting orders for NAIA T3 and ORTIGAS ESTANCIA.

**What real users see:** order submitted successfully, but never appears in the warehouse queue for SCM to approve. The store team has no MR.

**Why S221/S222 didn't help:** both fallbacks were at later steps in the chain (approval, dispatch). Pattern C breaks at the order → MR transition before either fallback's surface.

**Likely fix layer:** `hrms/api/store.py:submit_order` or `_create_material_request`. Specific candidates:
- A hardcoded skip-list for franchise stores under specific parent companies
- A canonical resolver miss for these 2 stores (would be visible in `verify_canonical_structure.py` output — and the preflight only flags ORTIGAS GREENHILLS)
- A Material-Issue MR type guard that doesn't match NAIA T3 or ORTIGAS ESTANCIA's source-warehouse routing
- An exception swallowed silently by a try/except block in `_create_material_request`

**HARD STOP per plan:** if root cause is in `resolve_store_buyer_entity` or `resolve_warehouse_company`, STOP — these are canonical resolvers frozen since S196. Present finding to Sam, do NOT modify.

---

## ORTIGAS GREENHILLS — Allowed Skip with Phase 5 TIN apply

The S222 sweep found this store's "allowEmptyTin" skip-guard had lapsed somehow, causing it to attempt submission and get stuck. Phase 5 of S223 applies HQ TIN `688-721-280-00000` to the billing Customer (per Sam directive 2026-04-25), at which point the empty-TIN canonical violation is resolved and the store can proceed normally through the chain. If TIN can't be applied (Finance flagged stale), it remains the 1 allowed skip and the sprint passes at 48/49.

---

## Phase 1 verification gate (required before claiming Phase 1 complete)

```bash
# Run from worktree root
python output/s223/verify_phase1.py
```

Script lives at `output/s223/verify_phase1.py` — see next section.
