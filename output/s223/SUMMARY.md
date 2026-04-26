# S223 Sprint Summary — Partial execution (code-verified fixes shipped, live-verification work deferred)

**Sprint:** S223 — Fix all remaining L3 store-chain failures via real product fixes (no API bypass)
**Branch (hrms):** `s223-fix-l3-store-chain-product-bugs`
**Branch (bei-tasks):** `s223-fix-l3-store-chain-product-bugs`
**Status:** READY FOR REVIEW — partial execution with explicit handoff for live-verification work
**Executor:** Claude Code agent (Opus 4.7, 1M context)

---

## What shipped (code-verified, ready to merge)

### 1. DEFECT-11 (order-approvals queue narrowing) — FIXED

**Root cause:** `bei-tasks/app/dashboard/store-ops/order-approvals/page.tsx:548` had `selectedDate = useState(todayStr())` defaulting the queue filter to PHT today. Backend `hrms.api.ordering.get_order_review_queue` matched with `WHERE so.order_date = %(date)s` strict equality. Orders submitted with an `order_date` ≠ today disappeared from the queue.

**Fix:**
- Backend `hrms/api/ordering.py:get_order_review_queue` — empty/None date now bypasses the date filter via `(%(date)s IS NULL OR so.order_date = %(date)s)`. Added `set_backend_observability_context(module="ordering", action="get_order_review_queue", mutation_type="read")`.
- Frontend `bei-tasks/app/dashboard/store-ops/order-approvals/page.tsx` — `selectedDate` now defaults to `""` (show all dates). Header description shows "(all dates)" when no filter is set. New "All dates" clear-button appears when a date is picked. Added `data-testid="s223-order-approval-date-picker"` and `data-testid="s223-order-approval-clear-date"`.

**Expected impact:** the ~5 stores S221's REST fallback was masking will now pass via the real UI path. Test users can navigate to `/dashboard/store-ops/order-approvals` and see all their pending orders regardless of date.

### 2. ORTIGAS GREENHILLS TIN — FIXED

**Decision:** Sam directive 2026-04-25 — apply HQ TIN `688-721-280-00000` (BEIFRANCHISE FOOD OPC headquarters).

**Applied via:** `scripts/s223_ortigas_apply_tin.py` (SSM probe to production).

**Result:**
- `Customer.tax_id` for `ORTIGAS GREENHILLS - BEIFRANCHISE FOOD OPC` was empty before; now `688-721-280-00000`.
- Canonical postcheck: **0 violations** (was 1 — `BILLING_CUST_TIN_EMPTY` resolved).
- Prior submitted Sales Invoices for this Customer: **0**. **No BIR §237 retroactive review needed.**
- Policy memo: `output/s223/verification/ortigas_tin_policy.md`.
- Before/after snapshots: `output/s223/verification/ortigas_customer_{before,after}.json`.

### 3. S221 + S222 Test Fallbacks — REVERTED

Per CEO directive 2026-04-25 ("no shortcuts"):

- `bei-tasks/tests/e2e/pages/OrderApprovalPage.ts` — removed S221 REST `approve_order` fallback (lines 86-117). Kept the gate-only readback as a `VERIFICATION-POST-UI`-equivalent (workflow gate, not shortcut). On invisible-order, the method now throws clearly rather than bypassing the UI via REST.
- `bei-tasks/tests/e2e/pages/DispatchPage.ts` — removed S222 `Stock Entry Detail` queryDocs fallback (lines 174-190). The Pattern A modal-stuck bug is real product code; fixing it in tests is the wrong layer.

**Discipline grep gate (passing):**
```
rg 'page\.request\.(post|put|delete|patch)|fetch\(.*api/method' tests/e2e/pages/  # 0 hits
rg 'getReadbackCtx\(\)\.post\(|queryDocs\([^)]*Stock Entry Detail|hrms\.api\.store\.approve_order' tests/e2e/pages/  # 0 hits
```

---

## What was investigated but NOT shipped (deferred to live verification)

The plan's CEO directive REQUIRES manual real-browser reproduction before shipping any Pattern A/B/C fix. This agent session does not have live browser access. Investigation produced documented findings, but actual fixes for these patterns must be done in a session with live `my.bebang.ph` access.

### Pattern A — Dispatch modal stuck open (6 stores)

**Stores:** AYALA SOLENAD, AYALA VERMOSA, CTTM TOMAS MORATO, SM GRAND CENTRAL, SM BICUTAN, SM MARIKINA — all sourced from PINNACLE COLD STORAGE - BKI or 3MD LOGISTICS - CAMANGYANAN - BKI (intercompany Material Issue path).

**Investigation done:**
- Wrote `scripts/s223_pattern_a_probe.py` SSM probe targeting AYALA SOLENAD vs ARANETA GATEWAY (control).
- Probe output: `output/s223/verification/pattern_a_probe_results.json`.
- Probe revealed approval flow architecture: `approve_order` is two-stage; `_create_mr_for_store_order` only fires after both stages complete.
- Probe limitation: my probe called `approve_order` only ONCE (test.area), not the second stage as test.scm. So it didn't actually trigger MR creation today and instead found stale MRs from yesterday's runs (docname reuse).

**Code-analysis hypothesis (requires live verification):**
The dispatch modal in `bei-tasks/app/dashboard/warehouse/dispatch/page.tsx:74-99` keeps the dialog mounted when `result.success === false`. If `hrms/api/warehouse.py:create_stock_transfer` raises `frappe.ValidationError` for these intercompany stores (e.g., insufficient stock at PINNACLE/3MD, intercompany contract resolution miss, SCM permission gate, or `_resolve_warehouse_name` failure), the `route.ts` catch block returns `{success: false, error: "..."}` with proper status, the toast shows, but the modal stays open. The S222 fallback queries `Stock Entry Detail` for child rows linked to the MR — but if `create_stock_transfer` errored before SE.insert, no SE exists, so the fallback finds nothing.

**Live verification needed:**
1. As `test.scm@bebang.ph`, manually navigate `/dashboard/warehouse/dispatch` for AYALA SOLENAD's MR.
2. Open Chrome DevTools (Network + Console), preserve log.
3. Click inner "Create Transfer" button.
4. Capture HAR + console + Sentry events.
5. Confirm the actual error message from `create_stock_transfer`. Then fix the underlying validation/data issue.

### Pattern B — Warehouse approval queue narrowing (4 stores)

**Stores:** SM STA. ROSA, ROBINSONS IMUS, SM SOUTHMALL, ROBINSONS ANTIPOLO.

**Investigation done:**
- Read `bei-tasks/app/dashboard/warehouse/approve/page.tsx` — confirmed 0 references to `todayStr()` or any client-side date narrowing.
- Read `hooks/use-warehouse.ts:usePendingMRs` — uses SWR fetch of `/api/warehouse?action=pending_mrs`, no date narrowing.
- Read `hrms/api/warehouse.py:get_pending_material_requests:1088-1108` — filters `status IN ['Pending', 'Partially Ordered']` AND `docstatus=1` AND `material_request_type IN ['Material Transfer', 'Material Issue']`. No date filter.

**Code-analysis hypothesis (requires live verification):**
Pattern B is a different mechanism than DEFECT-11. Most likely: a stale-cache or revalidation issue with SWR (`revalidateOnFocus: false`) where new MRs aren't picked up after the area-supervisor approval transitions them to "Pending Warehouse" status. Could also be: an MR-naming / GROUP_CONCAT issue in some upstream contract resolver.

**Live verification needed:**
1. Submit fresh order for SM STA. ROSA via `test.area`, complete first approval.
2. As `test.scm@bebang.ph`, navigate `/dashboard/warehouse/approve` and observe whether the MR appears.
3. If not, trigger SWR revalidation (refresh button) and observe.
4. Compare HAR output of `/api/warehouse?action=pending_mrs` against backend SQL result to identify whether narrowing is at hook layer or backend layer.

### Pattern C — MR never created (NAIA T3, ORTIGAS ESTANCIA)

**Investigation done:**
- Confirmed `hrms/api/store.py:_create_mr_for_store_order:3817` is the canonical MR-creation function.
- It uses `resolve_store_buyer_entity(warehouse_docname=store_warehouse)` and `resolve_warehouse_company(source_warehouse)` — both canonical resolvers (frozen since S196).
- For NAIA T3 and ORTIGAS ESTANCIA, the order succeeds but MR never appears — suggests the function is silently no-oping OR raising and the error is being swallowed.

**HARD STOP:** Plan rule mandates that if root cause is in canonical resolvers, STOP and ask Sam. Investigation paused at the resolver boundary — Phase 4 cannot proceed without confirming the resolver isn't the issue.

**Live verification needed:**
1. As `test.area@bebang.ph`, submit order for NAIA T3 via `/dashboard/store-ops/ordering`.
2. As `test.scm@bebang.ph`, complete second-stage approval via `/dashboard/store-ops/order-approvals` (Warehouse Manager role at stage 2).
3. Capture: does `submit_order` succeed? Does `_create_mr_for_store_order` get called? Does it fail silently? Check Sentry + Frappe Error Log.
4. Inspect `frappe.get_doc("Warehouse", "NAIA T3 - <ENTITY>")` — verify canonical structure.
5. If the resolver is the issue, surface to Sam for explicit approval before modifying.

---

## Files changed

### bei-tasks (frontend)
- `app/dashboard/store-ops/order-approvals/page.tsx` — DEFECT-11 fix (date default + clear button + testids + header copy)
- `tests/e2e/pages/OrderApprovalPage.ts` — S221 REST fallback REMOVED; gate-only readback retained
- `tests/e2e/pages/DispatchPage.ts` — S222 SE-existence fallback REMOVED; canonical poll only

### hrms (backend)
- `hrms/api/ordering.py` — `get_order_review_queue` accepts empty date as no filter; added Sentry observability context
- `scripts/s223_ortigas_apply_tin.py` — NEW (Phase 5 TIN apply)
- `scripts/s223_pattern_a_probe.py` — NEW (Phase 2A probe — investigation artifact)
- `scripts/s223_diag_mr_state.py` — NEW (MR state diagnostic — investigation artifact)
- `output/s223/SUMMARY.md` — this file
- `output/s223/DEFECT_REGISTER.md` — full investigation register
- `output/s223/library_audit.md` — Phase 0 library audit
- `output/s223/RUN_STATUS.json` — checkpoint state
- `output/s223/verify_phase1.py` — Phase 1 verification gate
- `output/s223/verification/baseline.json` — origin SHA baseline
- `output/s223/verification/canonical_preflight.txt` — pre-state canonical (1 violation)
- `output/s223/verification/canonical_postcheck_phase5.txt` — post-state canonical (0 violations)
- `output/s223/verification/ortigas_tin_policy.md` — TIN decision memo
- `output/s223/verification/ortigas_customer_{before,after}.json` — Customer record snapshots
- `output/s223/verification/ortigas_si_history.json` — empty SI history (no BIR §237 review needed)
- `output/s223/verification/pattern_a_probe_results.json` — Pattern A SSM probe output
- `output/s223/verification/mr_state_diag.json` — MR state diagnostic output

---

## Sweep verification status

**Phase 7A (sweep with fallbacks present):** SKIPPED — fallbacks were reverted in this same sprint per the CEO directive. The plan's sequencing assumed multi-session execution where Phase 7A could happen with fallbacks still in place; that didn't work in a single agent session.

**Phase 7B (UI-only sweep):** DEFERRED to Sam — invoke `/l3-v2-bei-erp` against the merged code or the branch directly. Expected outcomes:
- DEFECT-11 stores (5+): should now PASS via the real UI (date filter no longer narrowing).
- ORTIGAS GREENHILLS: should now PASS the SI step (TIN populated; canonical violation resolved).
- Pattern A (6 stores), Pattern B (4 stores), Pattern C (2 stores): still expected to fail until live-verification investigation produces the underlying fix.
- Best-case projection: ~36/49 + ~6 from DEFECT-11 + 1 from ORTIGAS = ~43/49 PASS.
- Worst-case: 30+/49 if removing S221 fallback exposes additional flake.

**Sam decision required:** merge this PR to ship the verifiable wins, then run sweep + investigate Pattern A/B/C with live access.

---

## Phase status

| Phase | Title | Status | Notes |
|---|---|---|---|
| 0 | Boot, worktrees, canonical preflight, library audit, testid registry | DONE | Preflight: 1 expected violation (ORTIGAS TIN). Library audit + testid reservations written. |
| 1 | Investigation: DEFECT_REGISTER for 13 stores | DONE | All 13 + DEFECT-11 cluster registered with hypothesized fix files. |
| 2A | Pattern A — Dispatch modal root cause | INVESTIGATED (not verified) | SSM probe ran; documented in DEFECT_REGISTER. Live browser verification deferred. |
| 2B | Pattern A — Fix + per-store verify | DEFERRED | Cannot ship without live verification per CEO directive. |
| 3A | Pattern B + DEFECT-11 — Hypothesis confirmation | DONE | DEFECT-11 hypothesis confirmed via grep. Pattern B confirmed as DIFFERENT root cause (not `todayStr()`). |
| 3B | Pattern B + DEFECT-11 — Fix + verify | PARTIAL | DEFECT-11 fix shipped; Pattern B fix DEFERRED. |
| 4 | Pattern C — MR creation fix + regression check | DEFERRED | Investigation paused at canonical resolver boundary per HARD STOP. |
| 5 | ORTIGAS GREENHILLS TIN apply + BIR §237 review | DONE | HQ TIN applied; canonical postcheck = 0 violations; 0 prior SIs (no BIR review needed). |
| 6 | Remove S221 + S222 test fallbacks | DONE | Both reverted; discipline grep gate passes. |
| 7A | Verification sweep WITH fallbacks present | SKIPPED | Fallbacks already reverted in same session. |
| 7B | UI-only verification sweep (final) | DEFERRED to Sam | Run `/l3-v2-bei-erp` against merged code. |
| 8 | Closeout: registry, PRs, evidence commit, worktree removal | IN PROGRESS | This file is the closeout artifact. |

---

## Recommended next steps

1. **Sam reviews this SUMMARY and the diff.**
2. **Merge hrms PR FIRST** — backend ordering.py change + ORTIGAS TIN data.
3. **Wait for hrms deploy + L1 smoke confirmation.**
4. **Merge bei-tasks PR** — frontend DEFECT-11 fix + S221/S222 fallback reverts.
5. **Run `/l3-v2-bei-erp` sweep** to validate DEFECT-11 + ORTIGAS unblocking.
6. **Open follow-up sprint(s) for Pattern A, B, C** — these need live-browser investigation by an agent with `my.bebang.ph` access OR by Sam directly.

---

## Co-execution credit

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
