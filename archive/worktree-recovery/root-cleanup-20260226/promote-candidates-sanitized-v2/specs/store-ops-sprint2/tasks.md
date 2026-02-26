# Tasks: Store Ops Sprint 2 -- Fix 44 UAT Issues

## Phase 1: Make It Work (POC)

Focus: Ship all backend changes first (permissions, fields, API fixes), then batch frontend fixes. Validate end-to-end via API calls and browser automation.

### Backend Batch 1: Permissions + Quick API Fixes (BEI-ERP repo)

- [ ] 1.1 Fix DocType permissions: POS Upload, Kudos, Store Visit Report
  - **Do**:
    1. Edit `bei_pos_upload.json` -- add `{"role": "Employee", "create": 1, "read": 1, "write": 1}` to permissions array
    2. Edit `bei_kudos.json` -- find Employee role in permissions, add `"write": 1`
    3. Edit `bei_store_visit_report.json` -- add `{"role": "Area Supervisor", "create": 1, "read": 1, "write": 1}` and `{"role": "Employee", "read": 1}` to permissions array
  - **Files**:
    - `F:\Dropbox\Projects\BEI-ERP\hrms\hr\doctype\bei_pos_upload\bei_pos_upload.json`
    - `F:\Dropbox\Projects\BEI-ERP\hrms\hr\doctype\bei_kudos\bei_kudos.json`
    - `F:\Dropbox\Projects\BEI-ERP\hrms\hr\doctype\bei_store_visit_report\bei_store_visit_report.json`
  - **Done when**: All 3 JSON files have correct permission entries
  - **Verify**: `python -c "import json; [print(f'{f}: {[p[\"role\"] for p in json.load(open(f))[\"permissions\"]]}') for f in ['hrms/hr/doctype/bei_pos_upload/bei_pos_upload.json','hrms/hr/doctype/bei_kudos/bei_kudos.json','hrms/hr/doctype/bei_store_visit_report/bei_store_visit_report.json']]"`
  - **Commit**: `fix(doctype): add Employee/Area Supervisor permissions to POS Upload, Kudos, Store Visit`
  - _Requirements: FR-2, FR-3, FR-18 | AC-4.2, AC-26.1, AC-36.1_
  - _Design: Pattern 3 (DocType Permission Fix)_

- [ ] 1.2 Add DocType fields: deposit_type, denomination (30 fields), voucher amounts
  - **Do**:
    1. Edit `bei_bank_deposit.json` -- add `deposit_type` Select field with options `"Bank Deposit\nPickup"`, required=1, insert before existing fields
    2. Edit `bei_store_closing_report.json` -- add 3 section breaks + 30 denomination Currency fields (`pcf_denom_1000`...`pcf_denom_coins`, `del_denom_1000`...`del_denom_coins`, `chg_denom_1000`...`chg_denom_coins`) + 3 read-only total fields (`pcf_denom_total`, `del_denom_total`, `chg_denom_total`) + 2 Currency fields (`pcf_voucher_amount`, `delivery_voucher_amount`)
    3. Verify `bei_fqi_report.json` has `naming_series` in its fields with a default value
  - **Files**:
    - `F:\Dropbox\Projects\BEI-ERP\hrms\hr\doctype\bei_bank_deposit\bei_bank_deposit.json`
    - `F:\Dropbox\Projects\BEI-ERP\hrms\hr\doctype\bei_store_closing_report\bei_store_closing_report.json`
    - `F:\Dropbox\Projects\BEI-ERP\hrms\hr\doctype\bei_fqi_report\bei_fqi_report.json`
  - **Done when**: JSON files contain all new fields with correct types and defaults
  - **Verify**: `python -c "import json; d=json.load(open('hrms/hr/doctype/bei_store_closing_report/bei_store_closing_report.json')); pcf=[f['fieldname'] for f in d['fields'] if f.get('fieldname','').startswith('pcf_denom')]; print(f'PCF denom fields: {len(pcf)}'); d2=json.load(open('hrms/hr/doctype/bei_bank_deposit/bei_bank_deposit.json')); dt=[f for f in d2['fields'] if f.get('fieldname')=='deposit_type']; print(f'deposit_type exists: {len(dt)>0}')"`
  - **Commit**: `feat(doctype): add denomination fields, voucher amounts, deposit type`
  - _Requirements: FR-4, FR-5, FR-6, FR-11 | AC-2.1, AC-5.1-5.5, AC-6.1-6.3, AC-19.1_
  - _Design: Pattern 4 (Denomination Grid), US-2, US-5, US-6_

- [ ] 1.3 Fix backend APIs: coverage status, cycle count validation, store resolution, approval queue
  - **Do**:
    1. In `coverage.py` `request_coverage()`: add `doc.status = "Open"` before `doc.insert()`
    2. In `inventory.py` `submit_cycle_count()`: add `if flt(item["counted_qty"]) < 0: frappe.throw(...)` validation; add optional `count_date` parameter (fallback to `nowdate()`)
    3. In `store.py`: add new `get_user_store()` whitelisted endpoint per design Pattern 1
    4. In `store.py` `submit_order()`: after order insert, create `BEI Approval Queue` entry with `reference_doctype`, `reference_name`, `assigned_approver` from `_get_area_supervisor_for_store(warehouse)`
    5. In `inventory.py` `get_orderable_items()`: add LEFT JOIN on `BEI Store Order Item` for frequency sort, add `stock_uom` to response fields
  - **Files**:
    - `F:\Dropbox\Projects\BEI-ERP\hrms\api\coverage.py`
    - `F:\Dropbox\Projects\BEI-ERP\hrms\api\inventory.py`
    - `F:\Dropbox\Projects\BEI-ERP\hrms\api\store.py`
  - **Done when**: All 5 API changes applied, `get_user_store()` returns store info for any role, `submit_order()` creates approval queue entry
  - **Verify**: Use `/local-frappe` to run: `bench --site hq.bebang.ph run-tests --module hrms.api.store --test test_get_user_store` (create minimal test) or verify endpoint exists via `grep -c "def get_user_store" hrms/api/store.py`
  - **Commit**: `feat(api): add store resolution endpoint, approval queue creation, cycle count validation`
  - _Requirements: FR-1, FR-7, FR-8, FR-9, FR-10, FR-12, FR-15 | AC-1.1-1.4, AC-11.2, AC-12.4, AC-13.2, AC-25.1_
  - _Design: Pattern 1 (Store Resolution), Pattern 5 (Approval Queue)_

- [ ] 1.4 [VERIFY] Quality checkpoint: backend Python syntax + JSON validity
  - **Do**: Validate all modified Python files parse without syntax errors and all JSON files are valid
  - **Verify**: `python -m py_compile hrms/api/store.py && python -m py_compile hrms/api/inventory.py && python -m py_compile hrms/api/coverage.py && python -c "import json; [json.load(open(f)) for f in ['hrms/hr/doctype/bei_pos_upload/bei_pos_upload.json','hrms/hr/doctype/bei_kudos/bei_kudos.json','hrms/hr/doctype/bei_store_visit_report/bei_store_visit_report.json','hrms/hr/doctype/bei_bank_deposit/bei_bank_deposit.json','hrms/hr/doctype/bei_store_closing_report/bei_store_closing_report.json','hrms/hr/doctype/bei_fqi_report/bei_fqi_report.json']]; print('ALL OK')"` -- exit 0
  - **Done when**: All files parse/validate without errors
  - **Commit**: `chore(store-ops): pass quality checkpoint` (only if fixes needed)

- [ ] 1.5 Deploy backend via PR
  - **Do**:
    1. Commit all BEI-ERP changes on feature branch `fix/store-ops-sprint2`
    2. Use `/pr-deploy` to create PR to `production` branch
    3. Poll deployment with `scripts/wait_for_deployment.py`
    4. After deploy, verify via `curl -s https://hq.bebang.ph/api/method/hrms.api.store.get_user_store | jq .` (should return 403 unauthenticated, not 404 missing)
  - **Verify**: `curl -s -o /dev/null -w "%{http_code}" https://hq.bebang.ph/api/method/hrms.api.store.get_user_store` returns `403` (endpoint exists but requires auth) not `404` (endpoint missing)
  - **Done when**: Backend deployed, new endpoint accessible, DocType migrations applied
  - **Commit**: None (PR merge triggers deploy)

### Frontend Batch 1: Store Resolution + Quick Fixes (bei-tasks repo)

- [ ] 1.6 Create useUserStore hook + API route + EntityCombobox component
  - **Do**:
    1. Create `F:\Dropbox\Projects\bei-tasks\hooks\use-user-store.ts` -- SWR hook calling `/api/store/user-store`, returns `{stores, defaultStore, isMultiStore, isLoading}` per design Pattern 1
    2. Create `F:\Dropbox\Projects\bei-tasks\app\api\store\user-store\route.ts` -- Next.js API route proxying to `hrms.api.store.get_user_store()` using existing cookie-forwarding pattern (copy from `app/api/supervisor/my-stores/route.ts`)
    3. Create `F:\Dropbox\Projects\bei-tasks\components\shared\entity-combobox.tsx` -- per design Pattern 2 with props: `doctype`, `filters`, `displayField`, `valueField`, `searchField`, `value`, `onChange`, `placeholder`, `allowOther`, `icon`. Built on Shadcn Command+Popover (follow `branch-selector.tsx` pattern)
  - **Files**:
    - `F:\Dropbox\Projects\bei-tasks\hooks\use-user-store.ts`
    - `F:\Dropbox\Projects\bei-tasks\app\api\store\user-store\route.ts`
    - `F:\Dropbox\Projects\bei-tasks\components\shared\entity-combobox.tsx`
  - **Done when**: Hook, route, and component created. EntityCombobox accepts all props from design.
  - **Verify**: `cd F:\Dropbox\Projects\bei-tasks && npx tsc --noEmit hooks/use-user-store.ts components/shared/entity-combobox.tsx 2>&1 | head -20` (no type errors)
  - **Commit**: `feat(shared): add useUserStore hook, API route, EntityCombobox component`
  - _Requirements: FR-1, FR-19 | AC-1.1, AC-18.1_
  - _Design: Pattern 1 (Store Resolution), Pattern 2 (Entity Combobox)_

- [ ] 1.7 Fix store-ops pages: handover, deposit, POS, closing
  - **Do**:
    1. **Handover** (`store-ops/handover/page.tsx`): Replace `get_my_stores` / supervisor store fetch with `useUserStore()`. Auto-populate store for single-store users, show dropdown for multi-store.
    2. **Deposit** (`store-ops/deposit/page.tsx`): Add deposit_type radio group (Bank Deposit / Pickup) as first field. Change `dates_covered` from free text to single date picker. Cap photo upload to 4 (`photos.length >= 4` disables add button).
    3. **POS** (`store-ops/pos/page.tsx`): After upload API response, check for `date_mismatch` flag. If true, show yellow warning banner (dismissable) with date info.
    4. **Closing** (`store-ops/closing/page.tsx`): Create `DenominationGrid` component at `components/store-ops/denomination-grid.tsx` per design Pattern 4. Add 3 grids (PCF, Delivery, Change Fund) + 2 voucher amount Currency inputs to Stage 1 cash section.
  - **Files**:
    - `F:\Dropbox\Projects\bei-tasks\app\dashboard\store-ops\handover\page.tsx`
    - `F:\Dropbox\Projects\bei-tasks\app\dashboard\store-ops\deposit\page.tsx`
    - `F:\Dropbox\Projects\bei-tasks\app\dashboard\store-ops\pos\page.tsx`
    - `F:\Dropbox\Projects\bei-tasks\app\dashboard\store-ops\closing\page.tsx`
    - `F:\Dropbox\Projects\bei-tasks\components\store-ops\denomination-grid.tsx` (NEW)
  - **Done when**: All 4 pages updated, DenominationGrid component created
  - **Verify**: `cd F:\Dropbox\Projects\bei-tasks && npm run build 2>&1 | tail -5` (build succeeds)
  - **Commit**: `fix(store-ops): fix handover access, deposit form, POS warning, closing denominations`
  - _Requirements: FR-1, FR-4, FR-5, FR-6 | AC-1.1-1.4, AC-2.1-2.3, AC-3.1-3.3, AC-4.3-4.4, AC-5.1-5.5, AC-6.1-6.3_
  - _Design: Pattern 1, Pattern 4, US-1 through US-6_

- [ ] 1.8 Fix inventory pages: ordering, counts
  - **Do**:
    1. **Ordering** (`inventory/ordering/page.tsx`): Display `stock_uom` next to item name. Add AlertDialog confirmation before submit (show summary: items, quantities, UOMs). Remove RoleGuard restriction so Store Staff can access (or add "Store Staff" to allowed roles). Wire to submit via existing API.
    2. **Counts** (`inventory/counts/page.tsx`): Add date picker in header (default today, no future dates). Add `min="0"` to all quantity inputs. Add "Resubmit" button on rejected counts calling existing `resubmit_cycle_count()` API.
  - **Files**:
    - `F:\Dropbox\Projects\bei-tasks\app\dashboard\inventory\ordering\page.tsx`
    - `F:\Dropbox\Projects\bei-tasks\app\dashboard\inventory\counts\page.tsx`
  - **Done when**: UOM visible, confirmation dialog works, date picker works, min=0 enforced, resubmit button rendered
  - **Verify**: `cd F:\Dropbox\Projects\bei-tasks && npm run build 2>&1 | tail -5` (build succeeds)
  - **Commit**: `fix(inventory): add UOM display, order confirmation, count date picker, resubmit button`
  - _Requirements: FR-7, FR-8, FR-9, FR-10 | AC-8.1-8.2, AC-10.1-10.3, AC-12.1-12.4, AC-13.1, AC-14.1-14.3_
  - _Design: US-8, US-10, US-12, US-13, US-14_

- [ ] 1.9 [VERIFY] Quality checkpoint: bei-tasks lint + build
  - **Do**: Run lint and build on bei-tasks repo
  - **Verify**: `cd F:\Dropbox\Projects\bei-tasks && npx eslint --max-warnings 0 hooks/use-user-store.ts components/shared/entity-combobox.tsx components/store-ops/denomination-grid.tsx && npm run build` -- exit 0
  - **Done when**: No lint errors, build succeeds
  - **Commit**: `chore(frontend): pass quality checkpoint` (only if fixes needed)

- [ ] 1.10 POC Checkpoint -- verify store resolution + order flow E2E
  - **Do**:
    1. Push bei-tasks changes to main (Vercel auto-deploys)
    2. Wait for Vercel deploy (~60s)
    3. Use browser automation (Chrome DevTools MCP) to:
       a. Login as test.staff@bebang.ph at my.bebang.ph
       b. Navigate to /dashboard/store-ops/handover
       c. Verify store is auto-populated (not empty)
       d. Navigate to /dashboard/inventory/ordering
       e. Verify page loads without RoleGuard block
       f. Take screenshots as evidence
    4. Verify `get_user_store` API returns data: `curl -s -b cookies.txt https://hq.bebang.ph/api/method/hrms.api.store.get_user_store | jq .`
  - **Verify**: Screenshots show handover page with store populated + ordering page accessible for Staff role
  - **Done when**: Store Staff can access handover and ordering pages with correct store data
  - **Commit**: `feat(store-ops): complete POC -- store resolution + ordering access verified`

## Phase 2: Refactoring -- Dropdown Conversions (bei-tasks repo)

Focus: Batch-convert 6 text inputs to EntityCombobox. All use the shared component from 1.6.

- [ ] 2.1 Convert FQI + communication dropdowns
  - **Do**:
    1. **FQI** (`receiving/fqi/page.tsx`): Replace item name text input with `EntityCombobox` (doctype="Item", filters={is_stock_item:1}, displayField="item_name", allowOther=true). When "Other" selected, show conditional free-text input.
    2. **Kudos** (`communication/kudos/page.tsx`): Replace recipient text with `EntityCombobox` (doctype="Employee", filters={status:"Active"}, displayField="employee_name"). Fix category dropdown values to match DocType: `["Teamwork","Customer Service","Innovation","Leadership","Going Extra Mile"]`.
    3. **Support** (`communication/support/page.tsx`): Fix category values to match DocType: `["IT/Technical","HR Question","Payroll Issue","App Bug","Feature Request","Other"]`.
  - **Files**:
    - `F:\Dropbox\Projects\bei-tasks\app\dashboard\receiving\fqi\page.tsx`
    - `F:\Dropbox\Projects\bei-tasks\app\dashboard\communication\kudos\page.tsx`
    - `F:\Dropbox\Projects\bei-tasks\app\dashboard\communication\support\page.tsx`
  - **Done when**: FQI uses item combobox with Other, Kudos uses employee combobox + correct categories, Support has correct categories
  - **Verify**: `cd F:\Dropbox\Projects\bei-tasks && npm run build 2>&1 | tail -5` (build succeeds)
  - **Commit**: `fix(dropdowns): convert FQI item, kudos recipient to EntityCombobox, fix categories`
  - _Requirements: FR-3, FR-17, FR-19 | AC-18.1-18.4, AC-26.2, AC-27.1-27.3, AC-28.2_
  - _Design: Pattern 2 (Entity Combobox)_

- [ ] 2.2 Convert HR + supervisor dropdowns
  - **Do**:
    1. **Coverage** (`hr/coverage/page.tsx`): Replace store text with `EntityCombobox` (doctype="Warehouse", filters={is_group:0}, displayField="warehouse_name"). Replace employee text with `EntityCombobox` (doctype="Employee", filters={status:"Active"}, displayField="employee_name").
    2. **Schedule** (`hr/schedule/page.tsx`): Replace free-form shift input with `EntityCombobox` (doctype="BEI Shift Template", displayField="template_name"). On select, auto-fill start_time/end_time.
    3. **Labor Plan** (`supervisor/labor-plan/page.tsx`): Replace store text with `EntityCombobox` using `useUserStore` stores as filter.
  - **Files**:
    - `F:\Dropbox\Projects\bei-tasks\app\dashboard\hr\coverage\page.tsx`
    - `F:\Dropbox\Projects\bei-tasks\app\dashboard\hr\schedule\page.tsx`
    - `F:\Dropbox\Projects\bei-tasks\app\dashboard\supervisor\labor-plan\page.tsx`
  - **Done when**: All 3 pages use EntityCombobox for entity selection
  - **Verify**: `cd F:\Dropbox\Projects\bei-tasks && npm run build 2>&1 | tail -5`
  - **Commit**: `fix(dropdowns): convert coverage, schedule, labor plan to EntityCombobox`
  - _Requirements: FR-14, FR-19 | AC-22.2-22.4, AC-24.1-24.4, AC-32.1-32.2_
  - _Design: Pattern 2 (Entity Combobox)_

- [ ] 2.3 [VERIFY] Quality checkpoint: full bei-tasks lint + build
  - **Do**: Full lint + build of bei-tasks
  - **Verify**: `cd F:\Dropbox\Projects\bei-tasks && npx eslint . && npm run build` -- exit 0
  - **Done when**: No lint errors, build succeeds
  - **Commit**: `chore(frontend): pass quality checkpoint` (only if fixes needed)

## Phase 3: Data Seeding + Scope Filtering (Mixed repos)

Focus: Seed test data, fix scope filtering, verify data-dependent pages load.

- [ ] 3.1 Create and run test data seed script
  - **Do**:
    1. Create `F:\Dropbox\Projects\BEI-ERP\scripts\seed_sprint2_test_data.py` that uses Frappe API (bench console) to:
       a. Create 10 Attendance records for test employees (last 2 weeks)
       b. Create 1 Salary Slip for each test employee
       c. Create 1 BEI Announcement with status="Published"
       d. Create Stock Bin records (5 items) for TEST-STORE-BGC warehouse
       e. Create 1 BEI Distribution Trip targeting test warehouse
       f. Create 7 BEI Shift Template records (Opening 5:00-14:00, Mid 10:00-19:00, Closing 14:00-23:00, Split 5:00-9:00+14:00-18:00, Graveyard 22:00-7:00, Early 4:00-13:00, Late 15:00-24:00)
       g. Set `custom_area_supervisor = "test.area@bebang.ph"` on test warehouses
    2. Deploy script via `/local-frappe` or SSM pipeline
  - **Files**:
    - `F:\Dropbox\Projects\BEI-ERP\scripts\seed_sprint2_test_data.py` (NEW)
  - **Done when**: Script runs without errors, test data exists in production
  - **Verify**: `curl -s -b cookies.txt "https://hq.bebang.ph/api/method/frappe.client.get_count?doctype=BEI Shift Template" | jq .message` returns >= 7
  - **Commit**: `feat(seed): add sprint 2 test data seeding script`
  - _Requirements: FR-14 | AC-17.1-17.4, AC-21.1, AC-22.1, AC-23.1, AC-29.1, AC-37.1_
  - _Design: Phase 3 (Navigation & Config)_

- [ ] 3.2 Fix completeness tracker filtering + store visits store list
  - **Do**:
    1. **Completeness** (`completeness/page.tsx`): Filter data query to only show stores where `custom_area_supervisor` = current user OR stores in user's `reports_to` chain. Use `useUserStore()` to get authorized stores.
    2. **Store Visits** (`team/visits/page.tsx`): Replace store list fetch with `useUserStore()`. Area Supervisors see their assigned stores.
  - **Files**:
    - `F:\Dropbox\Projects\bei-tasks\app\dashboard\completeness\page.tsx`
    - `F:\Dropbox\Projects\bei-tasks\app\dashboard\team\visits\page.tsx`
  - **Done when**: Completeness shows only user's stores, store visits page populates store list
  - **Verify**: `cd F:\Dropbox\Projects\bei-tasks && npm run build 2>&1 | tail -5`
  - **Commit**: `fix(supervisor): filter completeness by user stores, fix store visit store list`
  - _Requirements: FR-16, FR-18 | AC-33.1-33.2, AC-36.2-36.3_
  - _Design: US-33, US-36_

- [ ] 3.3 Fix profile submission + verify navigation pages load
  - **Do**:
    1. **Profile** (`my-profile/page.tsx`): Investigate and fix submission error. Check for duplicate pending BEI Edit Request (add check before insert). If existing pending request for same field, show message. Fix any field name mismatches.
    2. **Verify pages load**: Check that `inventory/variances/page.tsx`, `inventory/shelf-life/page.tsx`, `enrichment/page.tsx`, `analytics/store/page.tsx` load data from their APIs. These pages and nav links already exist per design research.
  - **Files**:
    - `F:\Dropbox\Projects\bei-tasks\app\dashboard\my-profile\page.tsx`
  - **Done when**: Profile edit submits without error, navigation pages confirmed functional
  - **Verify**: `cd F:\Dropbox\Projects\bei-tasks && npm run build 2>&1 | tail -5`
  - **Commit**: `fix(profile): fix edit request submission, verify nav page data loading`
  - _Requirements: FR-20 | AC-15.1-15.3, AC-16.1-16.3, AC-34.1-34.3, AC-35.1-35.3, AC-38.1-38.3_
  - _Design: US-15, US-16, US-34, US-35, US-38_

- [ ] 3.4 [VERIFY] Quality checkpoint: both repos
  - **Do**: Full validation of both repos
  - **Verify**: `cd F:\Dropbox\Projects\BEI-ERP && python -m py_compile hrms/api/store.py && python -m py_compile hrms/api/inventory.py && python -m py_compile hrms/api/coverage.py` AND `cd F:\Dropbox\Projects\bei-tasks && npx eslint . && npm run build` -- both exit 0
  - **Done when**: No syntax errors, lint clean, build succeeds
  - **Commit**: `chore(sprint2): pass quality checkpoint` (only if fixes needed)

## Phase 4: Leave Workflow + Final Integration

Focus: Configure Frappe Leave Workflow, deploy final frontend, verify all 44 items.

- [ ] 4.1 Configure Frappe Leave Application Workflow
  - **Do**:
    1. Via bench console or Frappe Desk, create/configure Workflow on Leave Application DocType:
       - State: Draft (initial) -> Applied (on Submit) -> Approved (Area Supervisor/Supervisor action) -> Rejected (Area Supervisor/Supervisor action)
       - Transitions: Draft->Applied (Employee submits), Applied->Approved (reports_to approves), Applied->Rejected (reports_to rejects)
    2. Verify test employee `reports_to` chain: TEST-STAFF-001 -> TEST-SUPERVISOR-001 -> TEST-AREA-001
    3. Create script `scripts/configure_leave_workflow.py` with bench console commands
    4. Deploy via SSM pipeline
  - **Files**:
    - `F:\Dropbox\Projects\BEI-ERP\scripts\configure_leave_workflow.py` (NEW)
  - **Done when**: Leave Application workflow active, test employee chain configured
  - **Verify**: `curl -s -b cookies.txt "https://hq.bebang.ph/api/method/frappe.client.get_list?doctype=Workflow&filters=[[\"document_type\",\"=\",\"Leave Application\"]]" | jq '.message | length'` returns >= 1
  - **Commit**: `feat(hr): configure Leave Application approval workflow`
  - _Requirements: FR-13 | AC-20.1-20.6_
  - _Design: Phase 5 (Leave Workflow)_

- [ ] 4.2 Deploy frontend + full E2E test
  - **Do**:
    1. Push all bei-tasks changes to main branch (Vercel auto-deploys)
    2. Wait for Vercel deployment
    3. Run browser automation to verify critical flows:
       a. Login as test.staff@bebang.ph -> handover page loads with store
       b. Navigate to ordering -> page accessible, items show UOM
       c. Navigate to cycle count -> date picker present, min=0 on inputs
       d. Navigate to FQI -> item field is combobox
       e. Navigate to kudos -> recipient is combobox, categories correct
       f. Navigate to coverage -> store/employee are comboboxes
       g. Navigate to deposit -> deposit type selector present
       h. Navigate to closing -> denomination grids render
    4. Login as test.area@bebang.ph -> verify area dashboard shows data, store visits shows stores
    5. Login as test.supervisor@bebang.ph -> verify completeness filtered, approval queue visible
  - **Verify**: All pages load without errors, no 403/404/500 responses, all comboboxes functional
  - **Done when**: All 4 test accounts can access their authorized pages
  - **Commit**: None (deploy only)
  - _Requirements: All US-1 through US-38_

## Phase 5: Quality Gates

- [ ] 5.1 [VERIFY] Full local CI: lint + build both repos
  - **Do**: Run complete validation suite
  - **Verify**:
    - BEI-ERP: `cd F:\Dropbox\Projects\BEI-ERP && python -m py_compile hrms/api/store.py && python -m py_compile hrms/api/inventory.py && python -m py_compile hrms/api/coverage.py && python -c "import json; [json.load(open(f'hrms/hr/doctype/{d}/{d}.json')) for d in ['bei_pos_upload','bei_kudos','bei_store_visit_report','bei_bank_deposit','bei_store_closing_report','bei_fqi_report']]; print('ALL JSON VALID')"`
    - bei-tasks: `cd F:\Dropbox\Projects\bei-tasks && npm run lint && npm run build`
  - **Done when**: All commands pass with no errors
  - **Commit**: `fix(sprint2): address lint/type issues` (if fixes needed)

- [ ] 5.2 Create PRs and verify CI
  - **Do**:
    1. **BEI-ERP**: Verify on feature branch `fix/store-ops-sprint2`. Push to origin. Create PR to `production` via `/pr-deploy`. Monitor CI with `gh pr checks --watch`.
    2. **bei-tasks**: All changes should already be on `main` (Vercel auto-deployed). If on feature branch, create PR to `main` and merge.
  - **Verify**: `gh pr checks` shows all green for BEI-ERP PR
  - **Done when**: All CI checks pass, PRs ready for review/merged
  - **If CI fails**: Read failure details, fix locally, push, re-verify

- [ ] 5.3 [VERIFY] AC checklist -- programmatic verification of all acceptance criteria
  - **Do**: For each AC group, verify implementation exists:
    1. AC-1.x (Handover): Grep `useUserStore` in handover page
    2. AC-2.x (Deposit type): Grep `deposit_type` in deposit page + DocType JSON
    3. AC-3.x (Deposit form): Grep date picker + photo limit in deposit page
    4. AC-4.x (POS): Grep `Employee` in pos_upload.json permissions + `date_mismatch` in POS page
    5. AC-5.x (Denomination): Count pcf_denom fields in closing report JSON (should be 11)
    6. AC-6.x (Voucher): Grep `pcf_voucher_amount` in closing report JSON
    7. AC-7-10.x (Ordering): Grep `stock_uom` + `AlertDialog` + `min.*0` in ordering page
    8. AC-11.x (RBAC): Grep `BEI Approval Queue` in store.py submit_order
    9. AC-12-14.x (Cycle count): Grep `count_date` in inventory.py + date picker in counts page
    10. AC-18.x (FQI): Grep `EntityCombobox` in fqi page
    11. AC-20.x (Leave): Verify workflow configured via API
    12. AC-22.x (Shifts): Grep `EntityCombobox.*Shift` in schedule page
    13. AC-24.x (Coverage): Grep `EntityCombobox` in coverage page (2 instances)
    14. AC-26-27.x (Kudos): Grep `EntityCombobox` + correct categories in kudos page
    15. AC-28.x (Support): Grep correct categories in support page
    16. AC-30.x (Queue): Grep `BEI Approval Queue` creation in store.py
    17. AC-33.x (Completeness): Grep `useUserStore` in completeness page
    18. AC-36.x (Store Visit): Grep `Area Supervisor` in store_visit_report.json
    19. AC-38.x (Profile): Grep duplicate-check or error handling in my-profile page
  - **Verify**: All greps return matches (exit 0)
  - **Done when**: All 38 user stories have verifiable code implementations
  - **Commit**: None

---

## Unresolved Questions

1. **BEI Shift Template exact names/times**: Using placeholders (Opening, Mid, Closing, Split, Graveyard, Early, Late). Ops can update via Frappe Desk.
2. **Item Group store mapping (SO-1)**: Defaulting to all stock items with frequency sort. If `custom_allowed_item_group` exists on Warehouse, will filter by it.
3. **PR-1 root cause**: Will investigate during task 3.3. Could be duplicate pending request, field validation, or permission issue.

## Notes

- **POC shortcuts taken**: Shift template times are placeholders. Item group filtering falls back to all items. Profile fix may be a workaround if root cause unclear.
- **Production TODOs**: Ops team should confirm shift templates. Item-to-store mapping may need custom field on Warehouse. Leave workflow may need adjustment based on actual approval chain.
- **Two-repo deployment sequence**: Backend (BEI-ERP) deploys first via Docker build (5-10 min). Frontend (bei-tasks) deploys second via Vercel push (~60s). Backend changes are backward-compatible.
- **Key shared components**: `EntityCombobox` (used 6 times), `DenominationGrid` (used 3 times), `useUserStore` (used 5+ times). These are the highest-leverage pieces.
- **44 items mapped to 14 tasks**: Grouped by pattern (permissions batch, dropdown batch, data seed batch) rather than individual items.
