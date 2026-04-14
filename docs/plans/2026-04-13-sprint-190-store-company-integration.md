# S190 — Store-Company Integration: One Ecosystem, Zero Silos

> **Context in one line:** Rewire the entire ordering/billing/supply-chain stack to use the Company Master (Frappe Company DocType) as the single source of truth — replacing CSV lookups, warehouse name guessing, and disconnected identifier chains. When a store places an order, it flows through: Store → Company → Warehouse → Customer → Sales Invoice, all via Frappe Link fields.

**Plan version:** v1

```yaml
sprint: S190
status: DEPLOYED
planned_date: 2026-04-13
plan_file: docs/plans/2026-04-13-sprint-190-store-company-integration.md
completed_date: ""
execution_summary: "Backend PR #563 + Frontend PR #391 created. Phase 0: 54/54 warehouses have company, 4 missing Customers created. Phase 1-3: Company-first resolution, company field on BEI Store Order, BKI billing chain, API returns company. Pending L3."
backend_pr: 563
frontend_pr: 391

lanes:
  backend_lane:
    repo: Bebang-Enterprise-Inc/hrms
    branch: s190-store-company-integration
    phases: [0, 1, 2, 3, 4]
  frontend_lane:
    repo: Bebang-Enterprise-Inc/BEI-Tasks
    branch: s190-store-company-frontend
    phases: [3B]

depends_on:
  - S188 deployed (per-store company restructure — 49 stores = 49 companies)
  - S184 deployed (Company Master Data Hub)

canonical_unit_total: 65
```

---

## Design Rationale (For Cold-Start Agents)

### Why this sprint exists

S184 built the Company Master hub. S188 created per-store child companies (49 stores = 49 Frappe companies). But the store ordering system — the core revenue workflow — doesn't use any of it. Sam's directive (2026-04-13): *"Everything should be interconnected — not isolated silos."*

**Current state (broken):**
```
Store order → Warehouse name → guess company from " - BEI" suffix
                              → read CSV file for buyer entity name
                              → lookup Customer by name string match
                              → hardcode "Bebang Kitchen Inc." on Sales Invoice
```

**Target state (connected):**
```
Store order → Company (Link field on BEI Store Order)
           → Company.default_warehouse (Warehouse)
           → Company.customer_name → Customer (for BKI billing)
           → Customer.tax_id (for TIN on invoices)
           → All via Frappe Link fields, zero CSV lookups at runtime
```

### Architecture: Company-first, warehouse-derived

The ordering system currently treats warehouses as the primary identifier and derives everything else from them. This is backwards. The correct hierarchy:

```
Company (per-store, from S188)
  ├── Warehouse (Company.default_warehouse or Warehouse.company Link)
  ├── Customer (for BKI billing, created by S181 auto_provision)
  ├── Cost Center (Company.cost_center)
  ├── Bank Account (Bank Account.company Link)
  └── Employee (Employee.company)
```

**Key trade-off:** We keep `resolve_store_buyer_entity()` as a **fallback** during migration, not rip it out. The new code tries Company-based resolution first; if the Company doesn't have a customer set, it falls back to the CSV. This means zero data loss during rollout — any store not yet properly configured falls through to the existing behavior.

### What changes and what doesn't

| Component | Changes? | Details |
|---|---|---|
| `BEI Store Order` DocType | YES | Add `company` Link field (mandatory) |
| `resolve_warehouse_company()` | YES | Make `Warehouse.company` the only path — remove suffix guessing |
| `resolve_store_buyer_entity()` | YES | Try Company-based lookup first, CSV as fallback |
| `_get_store_customer()` | YES | Use Company → Customer chain instead of CSV → Customer |
| `_create_mr_for_store_order()` | YES | Read company from BEI Store Order.company, not warehouse guess |
| `build_bki_store_sale_invoice()` | YES | Read company from Stock Entry/warehouse, then Company → Customer |
| `get_user_store` API | YES | Return `company` alongside `warehouse_name` |
| Frontend `useUserStore` | YES | Add `company` field to StoreInfo |
| `submit_order()` | YES | Accept `company` param, set on BEI Store Order |
| All existing Warehouses | YES (data) | Ensure `Warehouse.company` is set correctly on all 49 store warehouses |
| S037 CSV register | NO | Kept as fallback, not removed |
| Existing orders | NO | Already-submitted orders keep warehouse-only reference |

---

## Data Sources

| Source | What it provides |
|---|---|
| Frappe `tabWarehouse` | Warehouse → Company Link (must be correct for all 49 stores) |
| Frappe `tabCustomer` | Customer records created by S181 auto_provision (buyer entities) |
| `hrms/data_seed/store_entity_mapping_2026-04-13.csv` | Fallback: store → buyer entity → customer chain |

---

## Phase Budget Contract

```yaml
phase_unit_budget:
  Phase 0 (Data: ensure all 49 warehouses have correct Company set):      8
  Phase 1 (Core: rewire resolve functions + add company to Store Order):  15
  Phase 2 (Billing: rewire BKI invoice + commissary to use Company):      12
  Phase 3 (Frontend: return company in store context + stamp on orders):   10
  Phase 3B (bei-tasks: add company to StoreInfo + pass on submit):         8
  Phase 4 (Verification + closeout):                                      12
hard_limit_per_phase: 15
total_units: 65
```

---

## Phase 0: Data Prerequisite — Warehouse.company Correctness (8u)

### Task 0.1: Audit all 49 store warehouses

```
MUST_MODIFY: Frappe production data (via SSM script)
```

Query all warehouses that belong to store companies. For each, verify `Warehouse.company` points to the correct per-store child company (not the parent group). Fix any that point to the wrong company.

**HARD BLOCKER:** Phase 1 depends on `Warehouse.company` being correct for all stores. If even one warehouse has the wrong company, the Company-based resolution will return wrong billing data.

### Task 0.2: Ensure Customer exists for every store company

Verify that every per-store child company has a matching Customer record (created by S181 `_s181_ensure_bki_customer`). If any are missing, create them.

### Task 0.3: Verify Company → Customer mapping is queryable

For each store Company, verify that `frappe.db.get_value("Customer", {"customer_name": buyer_entity_name})` returns a result. The buyer_entity_name must match exactly.

---

## Phase 1: Core — Rewire Resolution Functions (15u)

### Task 1.1: Add `company` field to BEI Store Order

```
MUST_MODIFY: hrms/hr/doctype/bei_store_order/bei_store_order.json
MUST_CONTAIN: '"fieldname": "company"'
MUST_CONTAIN: '"fieldtype": "Link"'
MUST_CONTAIN: '"options": "Company"'
```

Add a `company` Link field (mandatory for new orders, optional for existing). Insert after `store` field. Set via `submit_order()` at creation time.

### Task 1.2: Rewrite `resolve_warehouse_company()`

```
MUST_MODIFY: hrms/utils/supply_chain_contracts.py
MUST_CONTAIN: 'Warehouse.company is mandatory'
```

Remove the suffix-guessing fallback (" - BEI" / " - BKI"). The function now:
1. Reads `frappe.db.get_value("Warehouse", warehouse_name, "company")`
2. If None, logs an error and returns None (instead of guessing)
3. Never returns a guessed company from string parsing

**HARD BLOCKER:** Do NOT remove the function signature — it's called from 10+ places. Only change the internal logic.

### Task 1.3: Rewrite `resolve_store_buyer_entity()` — Company-first with CSV fallback

```
MUST_MODIFY: hrms/utils/supply_chain_contracts.py
MUST_CONTAIN: 'Company-first resolution'
MUST_CONTAIN: 'CSV fallback'
```

New resolution order:
1. Resolve warehouse → Company (via `resolve_warehouse_company`)
2. If Company found, build entity_row from Company fields:
   - `buyer_entity_name` = Company.name
   - `billing_policy` = "BKI_TO_STORE_INTERCOMPANY" (if company != BKI)
   - `store_type` = Company.store_ownership_type
   - `warehouse_docname` = warehouse parameter
3. If Company NOT found, fall through to existing CSV lookup (unchanged)
4. Return the same dict shape as before — callers don't need to change

### Task 1.4: Rewrite `_get_store_customer()`

```
MUST_MODIFY: hrms/api/store.py
MUST_CONTAIN: 'Company-first customer resolution'
```

New resolution:
1. Resolve warehouse → Company
2. Query Customer where `customer_name` matches the S037 buyer_entity_name for this company (from the store mapping CSV, or from a new Company custom field `custom_bki_customer`)
3. If found, return Customer name
4. If not found, fall back to existing CSV-based lookup

### Task 1.5: Update `submit_order()` to stamp company

```
MUST_MODIFY: hrms/api/store.py
MUST_CONTAIN: 'order.company = '
```

When creating a BEI Store Order:
1. Resolve warehouse → Company via `resolve_warehouse_company()`
2. Set `order.company = resolved_company`
3. If no company resolved, throw an error (store warehouse must have Company set)

### Task 1.6: Update `_create_mr_for_store_order()` to read company from order

```
MUST_MODIFY: hrms/api/store.py
MUST_CONTAIN: 'order.company'
```

Instead of `resolve_warehouse_company(store_warehouse)`, read `order.company` directly (set at submit time). This eliminates the runtime warehouse-to-company resolution for MR creation.

### Task 1.7: Sentry DM-7 on all modified endpoints

All modified `@frappe.whitelist()` functions must have `set_backend_observability_context()`.

---

## Phase 2: Billing — BKI Invoice Uses Company Chain (12u)

### Task 2.1: Update `_create_fee_sales_invoice_for_billing()`

```
MUST_MODIFY: hrms/api/billing.py
MUST_CONTAIN: 'resolve_warehouse_company'
```

Replace CSV-based customer lookup with:
1. Resolve warehouse → Company
2. Company → Customer (via S037 buyer entity or custom field)
3. Set `si.customer = resolved_customer`

### Task 2.2: Update `build_bki_store_sale_invoice()`

```
MUST_MODIFY: hrms/api/commissary.py
MUST_CONTAIN: 'resolve_warehouse_company'
```

Same pattern as 2.1 — Company-first, CSV fallback.

### Task 2.3: Verify TIN flows to Sales Invoice

Check if Customer.tax_id is set (from Company.tax_id). If Sales Invoice picks up Customer.tax_id automatically (Frappe standard behavior), no code change needed. If not, add explicit TIN stamping.

---

## Phase 3: API — Return Company in Store Context (10u)

### Task 3.1: Update `get_user_store` to return company

```
MUST_MODIFY: hrms/api/store.py
MUST_CONTAIN: '"company"'
```

The `get_user_store` API currently returns `{stores: [{name: warehouse_name}]}`. Add `company` field to each store object:
```python
{"name": "SM Manila - BEI-SMM", "warehouse_name": "SM Manila", "company": "Bebang Enterprise Inc. - SM Manila"}
```

### Task 3.2: Update `get_store_context` to include company

```
MUST_MODIFY: hrms/api/company_master.py
MUST_CONTAIN: 'warehouse_company'
```

The Company Master's `get_store_context` endpoint should also return the resolved company for the warehouse.

---

## Phase 3B: Frontend — Company in Store Context (8u)

### Task 3B.1: Add company to StoreInfo interface

```
MUST_MODIFY: bei-tasks/hooks/use-user-store.ts
MUST_CONTAIN: 'company: string'
```

Add `company` field to `StoreInfo` interface.

### Task 3B.2: Pass company on order submit

```
MUST_MODIFY: bei-tasks/app/dashboard/store-ops/ordering/_components/StoreOrderingPage.tsx
MUST_CONTAIN: 'company'
```

When submitting an order, pass the `company` from the selected store context alongside the warehouse name.

---

## Phase 4: Verification + Closeout (12u)

### Task 4.1: End-to-end ordering test

Create a test order from a per-store child company. Verify:
- BEI Store Order has `company` field set
- Material Request has correct `company` and `custom_target_company`
- If BKI billing triggers, Sales Invoice has correct Customer

### Task 4.2: Regression test — existing orders still work

Verify orders created before S190 (no `company` field) still process correctly through the approval flow.

### Task 4.3: Forensic audit

Run the forensic audit script to verify all 49 stores resolve correctly through the new Company-first chain.

---

## L3 Workflow Scenarios

| # | User | Action | Expected Outcome | Failure Means |
|---|------|--------|-------------------|---------------|
| 1 | test.supervisor@bebang.ph | Submit order from SM Tanza store | BEI Store Order created with company="Bebang Mega Inc. - SM Tanza" | company field not stamped |
| 2 | test.commissary@bebang.ph | Approve the order → MR created | MR.company matches source warehouse company, custom_target_company = child company | MR stamping broken |
| 3 | test.hr@bebang.ph | Call get_user_store API | Response includes company field for each store | API not returning company |
| 4 | sam@bebang.ph | Open Company Master → check BKI Billing section for child company | Shows correct buyer entity + customer | Company→Customer chain broken |
| 5 | test.supervisor@bebang.ph | Submit order from a parent company store (SM Megamall) | Order gets child company "Bebang Enterprise Inc. - SM Megamall" not parent "Bebang Enterprise Inc." | Child resolution broken |

Evidence: `output/l3/s190/state_verification.json`

---

## Requirements Regression Checklist

- [ ] **RR-1:** BEI Store Order has a `company` Link field
- [ ] **RR-2:** `resolve_warehouse_company()` never guesses from suffix — reads Warehouse.company only
- [ ] **RR-3:** `resolve_store_buyer_entity()` tries Company first, falls back to CSV
- [ ] **RR-4:** `_get_store_customer()` uses Company chain, falls back to CSV
- [ ] **RR-5:** `submit_order()` stamps `company` on the BEI Store Order
- [ ] **RR-6:** `_create_mr_for_store_order()` reads company from order, not warehouse guess
- [ ] **RR-7:** BKI Sales Invoice customer comes from Company chain
- [ ] **RR-8:** All 49 store warehouses have correct Warehouse.company set
- [ ] **RR-9:** Frontend passes company on order submit
- [ ] **RR-10:** Existing orders (no company field) still process correctly
- [ ] **RR-11:** All modified @frappe.whitelist() endpoints have Sentry DM-7
- [ ] **RR-12:** CSV register is kept as fallback — NOT deleted

---

## HARD BLOCKERS

- **HB-1:** Do NOT delete the S037 CSV register or remove `resolve_store_buyer_entity()`. It stays as fallback. The migration is additive, not destructive.
- **HB-2:** Do NOT change the `submit_order()` function signature. It must still accept `store` (warehouse name) for backward compatibility. The `company` is resolved internally.
- **HB-3:** All 49 store warehouses MUST have `Warehouse.company` set correctly before Phase 1 code deploys. Phase 0 is a hard gate.
- **HB-4:** Existing orders without `company` field must still process. The approval flow must handle `order.company is None` gracefully.

---

## Autonomous Execution Contract

```yaml
completion_condition:
  - BEI Store Order has company field
  - All 49 warehouses have correct Warehouse.company
  - resolve_warehouse_company() reads only Warehouse.company (no suffix guess)
  - resolve_store_buyer_entity() tries Company first
  - submit_order() stamps company on order
  - BKI billing uses Company→Customer chain
  - Frontend returns company in store context
  - Existing orders still process (backward compatible)
  - PRs created, SPRINT_REGISTRY updated
  - L3 handoff generated

stop_only_for:
  - Warehouse.company data is wrong on >5 stores after Phase 0
  - Existing order processing breaks during regression test
  - HB-1 through HB-4 violated

signoff_authority: single-owner (Sam Karazi)

canonical_closeout_artifacts:
  - output/l3/s190/state_verification.json
  - docs/plans/2026-04-13-sprint-190-store-company-integration.md (status → DEPLOYED)
  - docs/plans/SPRINT_REGISTRY.md (row updated)
```

---

## Agent Boot Sequence

1. Read this plan fully — every phase, every HARD BLOCKER.
2. `cd F:\Dropbox\Projects\BEI-ERP && git fetch origin production && git checkout -b s190-store-company-integration origin/production`
3. `cd F:\Dropbox\Projects\bei-tasks && git fetch origin main && git checkout -b s190-store-company-frontend origin/main`
4. Read `hrms/utils/supply_chain_contracts.py` — understand `resolve_warehouse_company()` (line 164), `resolve_store_buyer_entity()` (line 201), `stamp_material_request_contract()` (line 363)
5. Read `hrms/api/store.py` — understand `submit_order()` (line 2956), `_get_store_customer()` (line 5143), `_create_mr_for_store_order()` (line 3683)
6. Read `hrms/api/billing.py` — understand `_create_fee_sales_invoice_for_billing()` (line 525)
7. Read `hrms/api/commissary.py` — understand `build_bki_store_sale_invoice()` (line 973)
8. Read `hrms/hr/doctype/bei_store_order/bei_store_order.json` — current fields
9. Run Phase 0 SSM script to fix warehouse data, then execute Phase 1-4.

---

## Zero-Skip Enforcement

Every task MUST be implemented. The Company-first fallback pattern means we're ADDING a resolution layer, not replacing the old one. No task can be skipped because "the old way still works" — the whole point is making the new way primary.

Forbidden behaviors:
1. Leaving `resolve_warehouse_company()` with the suffix-guessing fallback
2. Not adding `company` field to BEI Store Order
3. Not stamping company on `submit_order()`
4. Deleting the CSV register (it's the fallback)
5. Breaking existing orders that don't have the company field

---

## Amendment v2 — Audit Fixes (2026-04-14)

### Fix B1: Complete 14-key entity_row for Company-first path

**CRITICAL:** `resolve_store_buyer_entity()` returns 14 keys. `buyer_entity_requires_billing_hold()` checks `buyer_entity_status` — if missing, ALL stores get billing hold=True and BKI invoicing silently stops.

Task 1.3 MUST build the Company-first entity_row with ALL 14 keys:

```python
entity_row = {
    "store_name": store_name,
    "buyer_entity_name": company_name,  # Company.name IS the buyer entity
    "buyer_entity_status": "confirmed_legal_entity",  # prevents billing hold
    "buyer_entity_source": "company_master",
    "billing_policy": "BKI_TO_STORE_INTERCOMPANY",  # default for store entities
    "billing_post_policy": "standard",
    "store_type": frappe.db.get_value("Company", company_name, "store_ownership_type") or "Company Owned",
    "store_type_status": "active",
    "store_allocation_required": "no",
    "markup_rule_mode": "standard",
    "markup_rule_source": "company_master",
    "active_fulfillment_status": "active",
    "warehouse_docname": warehouse_name,
    "evidence_primary": "company_master",
}
```

Every caller of `resolve_store_buyer_entity()` must get all 14 keys regardless of whether Company-first or CSV-fallback was used.

### Fix B2: Remove phantom `custom_bki_customer` reference

Task 1.4 must NOT reference `Company.custom_bki_customer` — the field doesn't exist.

The correct Customer resolution is already in place from S181: `_s181_ensure_bki_customer()` creates a Customer where `customer_name = buyer_entity_name`. So:

```python
customer = frappe.db.get_value("Customer", {"customer_name": company_name}, "name")
```

This works because Company.name (e.g., "Bebang Mega Inc. - SM Tanza") matches the Customer.customer_name created by S181. No custom field needed.

### Fix B3: `company` field `reqd=0` with application-layer enforcement

Task 1.1 DocType JSON:
```json
{"fieldname": "company", "fieldtype": "Link", "options": "Company", "reqd": 0, "label": "Company", "insert_after": "store"}
```

Task 1.5 application enforcement in `submit_order()`:
```python
company = resolve_warehouse_company(store)
if not company:
    frappe.throw(_("Store warehouse {0} has no Company set. Contact admin.").format(store))
order.company = company
```

Pre-S190 orders with `company=None` continue to process normally.

### Fix B4: None handling for every `resolve_warehouse_company()` callsite

| Callsite | File:Line | None Behavior |
|---|---|---|
| `submit_order()` | store.py:~3000 | THROW — order must have company |
| `_create_mr_for_store_order()` | store.py:~3727 | Read from `order.company` (already set at submit) — never calls resolve |
| `stamp_material_request_contract()` | supply_chain_contracts.py:~374 | If source or target is None, THROW — MR must have valid companies |
| `build_bki_store_sale_invoice()` | commissary.py:~1014 | If None, fall back to CSV entity_row as before |
| `_create_fee_sales_invoice_for_billing()` | billing.py:~540 | If None, fall back to CSV entity_row as before |

### Fix B5: Phase 0 verification artifact

Add Task 0.0 before Task 0.1:

**Task 0.0: Generate Phase 0 verification artifact**

After fixing all warehouses, the SSM script writes:
```
output/s190/phase_0_verification.json
```
Content: `{"warehouses_total": 49, "warehouses_with_company": 49, "warehouses_missing_company": 0}`

Phase 1 boot checks this file exists and `warehouses_missing_company == 0` before starting.

### Fix B6: L3 test account correction

| Scenario | Old Account | New Account | Reason |
|---|---|---|---|
| 1, 5 | test.supervisor@bebang.ph | test.area@bebang.ph | Area Supervisor sees all stores |
| 2 | test.commissary@bebang.ph | test.commissary@bebang.ph | Correct (approver role) |
| 3 | test.hr@bebang.ph | test.hr@bebang.ph | Correct (API call) |

### Additional Fixes (Warnings)

- Task 1.4 is clarified as **inheriting from Task 1.3** — if `resolve_store_buyer_entity()` returns correct entity_row, `_get_store_customer()` works unchanged. Task 1.4 only adds a guard for None.
- L3 should run in a **separate fresh session** (65 units > 40-unit threshold).
- Phase 5 closeout must include `git add -f output/l3/s190/ && git push` for release manager gate.
- Governor feedback loop: REJECT → read PR comment, fix, push. NEEDS_FIX → apply, push. Merge Conflict → rebase, resolve, push.

---

## Amendment v3 — Phase 5: CSV Retirement (2026-04-14)

**Trigger:** Post-deploy audit found 27/53 stores (51%) billable via Company-first; 23 missing from CSV register. Rather than patching CSV rows, retire the CSV entirely.

**Canonical source of truth:** `F:\Downloads\bei_company_register (2).xlsx` → extracted to `hrms/data_seed/company_register_2026-04-14.csv` and `hrms/data_seed/store_entity_mapping_2026-04-14.csv`. No other data source.

### Phase 5 Tasks (12u)

- **Task 5.1:** Re-point all 49 store warehouses to correct buyer entity Company per workbook mapping. If buyer has per-store child in Frappe, point to child; else point to buyer entity directly. Skip excluded.
- **Task 5.2:** Ensure Customer exists for every target Company with tax_id from Company.tax_id. Create missing.
- **Task 5.3:** Remove CSV fallback from `resolve_store_buyer_entity`. Company-first becomes the only path. Missing Customer → return hold dict (fail-safe).
- **Task 5.4:** `load_store_buyer_entity_register` raises NotImplementedError pointing to Company Master.
- **Task 5.5:** Delete `hrms/fixtures/store_buyer_entity_register/` + `data/_CLEANROOM/2026-03-12-s037-store-buyer-entity-register/`.
- **Task 5.6:** Post-retirement forensic audit. Target: 100% billable (minus explicit excluded/hold).

### HARD BLOCKERS (Phase 5)

- **HB-5:** Every Active store warehouse has `Warehouse.company` = non-group Company with matching Customer.
- **HB-6:** PR review before merge (destructive — deletes CSV fixtures).
