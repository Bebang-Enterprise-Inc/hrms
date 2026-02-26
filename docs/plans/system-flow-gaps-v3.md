# System Flow and Gaps V3 (Expanded)

**Date:** 2026-02-26  
**Status:** Active execution plan (expanded from V2)  
**Base plan:** `docs/plans/2026-02-23-full-system-flow-gaps-v2.md`  
**Testing truth sources:**  
- `docs/testing/scenarios/index.yaml`  
- `docs/testing/L3_V2_METHOD.md`  
- `docs/plans/2026-02-23-l3-v2-hardening-and-bug-tracker.md`  
- `docs/testing/ROUTE_REGISTRY.md`
- `docs/plans/system-flow-gaps-v3-full-route-map.md` (exhaustive route map)

---

## 1) Why V3 Exists

V2 mapped major gaps and fixed core runtime blockers.  
V3 expands that into a strict, no-shortcut execution contract:

1. Map full system flow with required roles, seed records, and expected Frappe end state.
2. Expand scenario bank for L1/L2/L3 from that flow map.
3. Enforce "real user in browser + backend/Frappe verification" before declaring pass.
4. Keep coverage and execution status separate (green run does not mean full coverage).

---

## 2) Current Truth Snapshot (as of 2026-02-26)

### 2.1 Run Health

- L1: `PASS=18, WARN=36, FAIL=0`  
  Source: `output/l1/runs/l1_run_20260225_114617_024421.json`
- L2: `PASS=57, FAIL=0`  
  Source: `output/l2/runs/l2_run_20260225_114718_554264.json`
- L3-v2 modules: `10 PASS / 0 FAIL`  
  Source: `output/l3/runs/l3_v2_run_20260225_121602_104741.json`

### 2.2 Coverage Reality

`docs/testing/scenarios/index.yaml` now marks:
- `dispatch-warehouse-commissary`: **ready**
- `hire-to-onboard`: **ready**
- Domain prefix requirements for `commissary`, `recruitment`, `onboarding`, `employee_clearance`: **defined**

Conclusion: cross-module flow catalog coverage is closed in manifest state.

### 2.3 Exhaustive Mapping Reality

From `docs/plans/system-flow-gaps-v3-full-route-map.md`:
- Total mapped routes/pages/features: **169**
- Route-registry bound: **169**
- Not yet bound in route registry: **0**
- Domain classification coverage: **100%** (0 unknown rows)
- Unique app-route parity vs `docs/MY_BEBANG_PH_COMPLETE_REFERENCE.md`: **165/165 matched** (0 missing, 0 extra)

Conclusion: full route-level mapping and route-registry binding are now synchronized.

---

## 3) Non-Negotiable Test Standard (V3)

A scenario is only PASS when all of the following are true:

1. Real browser user actions completed (click/type/upload/submit).
2. UI shows success state (toast, status, route transition, or record visibility).
3. API response is valid for that action.
4. Frappe persisted record is verified (doctype/name/critical fields/status chain).
5. Evidence is saved (run JSON + report + artifacts + verification output).

No shortcuts:
- No API-only substitution for L3 flow steps.
- No "PASS by assumption" when data is not found in Frappe.
- No skipping of negative/guard-path scenarios once registered.

---

## 4) Domain Coverage Matrix (Flow-to-Test Mapping)

| Domain | Route/API Presence | L1 | L2 | L3 Module | L3 Flow | Coverage State |
|---|---|---|---|---|---|---|
| procurement | Yes | Yes | Partial by role | finance/billing | procure-to-pay | Partial |
| billing | Yes | Yes | Yes | billing/finance | procure-to-pay | Ready |
| inventory | Yes | Yes | Yes | store-ops/scm/stock-counting | dispatch-warehouse-commissary | Ready |
| dispatch | Yes | Yes | Partial | scm | dispatch-warehouse-commissary | Ready |
| warehouse | Yes | Yes | Partial | scm | dispatch-warehouse-commissary | Ready |
| commissary | Yes | Partial | Partial | scm (indirect) | dispatch-warehouse-commissary | Ready |
| recruitment | Yes | Partial | Partial | hr (indirect) | hire-to-onboard | Ready |
| onboarding | Yes | Partial | Partial | hr (indirect) | hire-to-onboard | Ready |
| payroll | Yes | Yes | Yes | hr | n/a | Ready (module-level) |
| employee_clearance | Yes | Partial | Partial | hr (indirect) | hire-to-onboard | Ready |

## 4.1 Domain Route Counts (Full Map)

| Domain | Route Count |
|---|---|
| analytics | 3 |
| billing_finance | 11 |
| commissary | 11 |
| communication | 4 |
| dispatch_receiving | 4 |
| employee_clearance | 2 |
| expense_pcf | 9 |
| home_profile | 3 |
| hr_management | 30 |
| inventory | 9 |
| onboarding | 4 |
| procurement | 29 |
| recruitment | 2 |
| store_ops_maintenance | 14 |
| supervisor_tools | 7 |
| tasks_projects | 12 |
| warehouse | 15 |

---

## 5) Expanded System Flow Contracts

## 5.1 SF-01: Store Operations to Billing Readiness

**Goal:** Daily store operations produce valid billing-ready records.

**Primary roles/accounts**
- `test.crew1@bebang.ph` (store execution)
- `test.supervisor@bebang.ph` (review/approval)
- Finance/HQ reviewer (billing validation)

**Required seed records**
- Active store assignment for crew and supervisor
- Open operating day/date
- POS payload fixtures and deposit fixture

**User journey (real-user path)**
1. Opening report submit
2. Mid-shift check submit
3. Closing report submit
4. POS upload submit
5. Bank deposit submit
6. Supervisor reviews where required

**Expected Frappe end state**
- Submitted docs exist with linked store/date/user
- No orphan or duplicate daily docs for same store/date
- Billing extraction sees eligible records

**Current state**
- Stable in L1/L2/L3 module runs
- Keep in regression bank for no-store and loading-loop defenses

---

## 5.2 SF-02: Procure-to-Pay

**Goal:** PR/PO/GR/Invoice/Payment and accounting postings form a consistent chain.

**Primary roles/accounts**
- Procurement/HQ user (currently no dedicated test account)
- Finance approver
- AP/Accounting reviewer

**Required seed records**
- Supplier with tax setup
- Items/UOM/warehouse mapping
- Open period and account mappings (AP, EWT)

**User journey (real-user path)**
1. Create/approve procurement documents
2. Receive goods and invoice
3. Create payment request and post accounting outputs
4. Validate billing/ledger effects

**Expected Frappe end state**
- Linked document chain from order to payment
- Correct AP account usage and posting integrity
- No invalid party assignments in JE path

**Current state**
- Core blockers from V2 were fixed
- Still needs dedicated role-account path for complete browser-real coverage

---

## 5.3 SF-03: Dispatch-Warehouse-Commissary

**Goal:** Warehouse + commissary + dispatch flow works end-to-end with stock integrity.

**Primary roles/accounts**
- `test.warehouse@bebang.ph`
- `test.commissary@bebang.ph`
- `test.supervisor@bebang.ph` / `test.staff@bebang.ph` for receiving side

**Required seed records**
- Ready-to-dispatch transfer/order records
- Vehicle master and route assignments
- Store/warehouse stock positions that support movement assertions

**User journey (real-user path)**
1. Prepare dispatch plan/trip
2. Preview stops and validate route data
3. Dispatch and confirm delivery
4. Receive and reconcile on destination side

**Expected Frappe end state**
- Trip/dispatch documents complete with stop history
- Stock movement posted correctly source-to-destination
- Delivery/receiving records linked to trip references

**Current state**
- Flow is marked **ready** in scenario catalog with dedicated `DWC-*` scenarios
- Prefix/domain mapping is now explicit in `index.yaml`

---

## 5.4 SF-04: Hire-to-Onboard-to-Clearance

**Goal:** Candidate-to-employee lifecycle works without manual breakpoints.

**Primary roles/accounts**
- `test.hr@bebang.ph`
- `test.supervisor@bebang.ph` (hiring manager)
- `test.staff@bebang.ph` (for downstream clearance interactions)

**Required seed records**
- Manpower request/job opening
- Candidate profile and stage pipeline seed
- Onboarding template/checklist definitions
- Clearance template rules

**User journey (real-user path)**
1. Candidate progress through recruitment pipeline
2. Offer and onboarding steps submitted/approved
3. Employee creation path completes
4. Clearance workflow triggers and completes separation path where applicable

**Expected Frappe end state**
- Candidate stages move correctly
- Onboarding status lifecycle reaches terminal state
- Employee record created and linked
- Clearance status transitions complete once and notifications are non-duplicative

**Current state**
- Flow is marked **ready** in scenario catalog with dedicated `HTO-*` scenarios
- Recruitment/onboarding/clearance lifecycle checkpoints are now captured

---

## 6) Scenario Bank Expansion Plan (L1/L2/L3)

## 6.1 L1 Expansion (API Contract Depth)

Add domain-complete checks for:
- commissary endpoints
- recruitment/onboarding/clearance endpoints
- procurement/accounting role-dependent endpoints

Deliverables:
1. Endpoint inventory per domain with payload hints
2. Positive + permission-aware negative checks
3. WARN policy table (what is acceptable vs defect)

---

## 6.2 L2 Expansion (Page/Render Guard Depth)

Add route coverage and assertions for:
- flow-critical pages in dispatch/warehouse/commissary
- recruitment/onboarding/clearance route set
- procurement/accounting pages via testable role path

Deliverables:
1. Route-to-role map with render expectations
2. Console/network error denylist per route
3. Skeleton/loading watchdog assertions

---

## 6.3 L3 Expansion (Flow Scenarios)

Target additions:
1. `flow-dispatch-warehouse`: ready baseline completed
2. `flow-hire-onboard`: ready baseline completed
3. Strengthen `flow-procure-pay` with negative/accounting assertions

Required updates:
- `docs/testing/scenarios/index.yaml`
  - keep prefix requirements aligned with `DWC`/`HTO` flow IDs
  - update flow statuses only after passing evidence-backed runs
- Add/expand flow scenario files in `docs/testing/scenarios/flows/`
- Append discovered defects to regression banks

---

## 7) Data and Account Prerequisites (Blockers to Clear First)

1. Procurement/accounting browser-test account path is incomplete.
2. Cross-flow seed/reset pipeline is not fully standardized.
3. Some flows depend on role chains that must be deterministic before parallel reruns.

Required V3 action:
- Define one stable seed/reset script set for cross-module flows before mass reruns.

---

## 8) V3 Execution Waves

## Wave 0: Preconditions and Guardrails
- Normalize test accounts, roles, and store assignments
- Freeze seed dataset contracts for all cross-module flows
- Confirm route registry and scenario catalog alignment

**Exit gate:** No missing account/seed blocker for target flows.

## Wave 1: System-Flow Mapping Completion
- Finalize SF-01..SF-04 contracts in this plan
- Map every required domain to flow scenarios and test levels

**Exit gate:** No "unknown owner/unknown seed/unknown end state" rows.

## Wave 2: Scenario Authoring
- Author missing L1/L2/L3 flow scenarios
- Add prefixes/domain mappings for currently empty domains

**Exit gate:** `dispatch-warehouse-commissary` and `hire-to-onboard` no longer partial/gap in draft catalog.

## Wave 3: Execute and Verify (No Shortcut Loop)
- Run L1 all, L2 all, L3 all + flow commands
- Verify each scenario against Frappe end state
- Log defects and retest after fixes

**Exit gate:** All V3 flow scenarios PASS with persisted-state evidence.

## Wave 4: Stabilize and Promote
- Promote new scenarios into regression bank
- Publish final run reports and coverage table
- Set recurring gate for each deployment

**Exit gate:** V3 marked GO for full-flow reliability.

---

## 9) V3 Tracker

| Item | Owner | Status | Evidence |
|---|---|---|---|
| Flow contracts SF-01..SF-04 finalized | QA/Engineering | COMPLETE | this file |
| Full route-level map (all known pages/routes/features) created | QA/Engineering | COMPLETE | `docs/plans/system-flow-gaps-v3-full-route-map.md` |
| Domain prefix gaps filled in `index.yaml` | QA | COMPLETE | `docs/testing/scenarios/index.yaml` |
| Dispatch-Warehouse-Commissary flow upgraded to ready | QA + Ops | COMPLETE | `docs/testing/scenarios/flows/dispatch-warehouse-commissary.md` |
| Hire-To-Onboard flow upgraded to ready | QA + HR | COMPLETE | `docs/testing/scenarios/flows/hire-to-onboard.md` |
| Procurement browser-real account path enabled | Engineering | TODO | pending account + RBAC record |
| L1/L2/L3 full rerun with new flow bank | QA | TODO | pending run IDs |

---

## 10) GO/NO-GO Rules (V3)

**NO-GO if any of these are true:**
1. Any V3 target flow remains `partial` or `gap`.
2. Any L3 scenario lacks persisted-state verification in Frappe.
3. Any critical route can pass only by bypassing real user actions.
4. Account/seed prerequisites are manually patched during run (non-reproducible).

**GO only when all of these are true:**
1. L1/L2/L3 all green on latest build.
2. `flow-procure-pay`, `flow-dispatch-warehouse`, and `flow-hire-onboard` are all ready and passing.
3. Regression bank updated for all defects found during V3 execution.

---

## 11) Immediate Next Actions

1. Run `scripts/testing/l3_manifest_check.py` and capture run artifact proving flow-manifest integrity.
2. Execute targeted L1/L2/L3 runs for newly bound route sections and attach run IDs.
3. Resolve remaining `(not mapped)` role rows in route registry via explicit test-account mapping.
4. Keep full-route-map and route-registry in lockstep through CI truth checks.
