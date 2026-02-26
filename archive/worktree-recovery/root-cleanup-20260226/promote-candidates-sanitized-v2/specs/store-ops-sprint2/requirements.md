---
spec: store-ops-sprint2
phase: requirements
created: 2026-02-07
roles: [Store Staff, Store Supervisor, Area Supervisor, HR User]
repos: [BEI-ERP (hrms), bei-tasks (frontend)]
---

# Requirements: Store Ops Sprint 2 -- Fix 44 UAT Issues

## Goal

Resolve all 44 remaining OPEN issues from the Feb 6 Ops UAT on my.bebang.ph so that Store Staff, Supervisors, and Area Supervisors can complete their daily workflows without errors, missing data, or blocked access.

---

## Deleted Items (Per Duplication Audit)

These items MUST NOT be built. Rationale below.

| ID | Original Proposal | Why Deleted | Alternative |
|----|-------------------|-------------|-------------|
| C-2 (child DocType) | New `BEI Denomination Entry` child table | Closing Report already has `denom_1000` through `denom_coins` fields | [EXTEND] Add per-fund denomination fields to existing DocType |
| SO-1 (mapping DocType) | New "Store Item List" mapping DocType | Frappe Item Group hierarchy + Warehouse filtering already handles this | [EXTEND] Filter `get_orderable_items()` by warehouse's default Item Group |
| PR-1 (new flow) | New profile edit workflow | BEI Edit Request DocType already exists with full approval flow | [EXTEND] Fix existing submission bug (likely duplicate-pending or field mismatch) |

---

## User Stories

### Module 1: Store Ops -- Handover & Deposits

#### US-1: Handover Access for Store Staff [EXTEND]
**As a** Store Staff member
**I want to** access and complete mid-shift handover forms
**So that** I can record cash reconciliation during shift changes

**Items:** H-1, H-2
**Root cause:** Frontend calls `supervisor.get_my_stores()` which only returns stores for supervisor-role users. Staff get empty response.

**Acceptance Criteria:**
- [ ] AC-1.1: Store Staff user can open `/dashboard/store-ops/handover` without error
- [ ] AC-1.2: Store Staff's assigned branch/warehouse auto-populates from their Employee record (`branch` or `company_email` lookup)
- [ ] AC-1.3: Store Staff can submit a BEI Mid-Shift Handover successfully
- [ ] AC-1.4: Store Supervisor can still access handover page with multi-store selector (no regression)

---

#### US-2: Bank Deposit Type Selection [BUILD]
**As a** Store Staff member
**I want to** specify whether a deposit is a "Bank Deposit" or "Pickup"
**So that** accounting can distinguish deposit methods

**Items:** D-1
**Backend:** Add `deposit_type` Select field to BEI Bank Deposit DocType (options: "Bank Deposit", "Pickup")

**Acceptance Criteria:**
- [ ] AC-2.1: Deposit form shows "Bank Deposit" / "Pickup" radio or select before other fields
- [ ] AC-2.2: Selection is required -- form cannot submit without it
- [ ] AC-2.3: `deposit_type` persists in DocType and appears in Frappe Desk

---

#### US-3: Deposit Form Enhancements [EXTEND]
**As a** Store Staff member
**I want to** select a single date and upload max 4 photos per deposit
**So that** entries are accurate and storage is controlled

**Items:** D-2, D-3

**Acceptance Criteria:**
- [ ] AC-3.1: `dates_covered` renders as a single date picker (not free text, not range)
- [ ] AC-3.2: Photo upload capped at 4 -- "Add Photo" button disabled/hidden when 4 photos attached
- [ ] AC-3.3: Existing deposits with >4 photos display correctly (no data loss)

---

#### US-4: POS Access for Store Staff [EXTEND]
**As a** Store Staff member
**I want to** upload POS data files
**So that** daily sales are recorded in the system

**Items:** P-1, P-2
**Backend:** Add Employee role to BEI POS Upload DocType permissions (create, read, write)

**Acceptance Criteria:**
- [ ] AC-4.1: Store Staff can open `/dashboard/store-ops/pos` without access denied
- [ ] AC-4.2: POS Upload DocType has Employee role with create+read+write permissions
- [ ] AC-4.3: When uploaded file's date differs from selected date, warning banner appears (backend already returns `date_mismatch` flag)
- [ ] AC-4.4: Warning is dismissable -- user can proceed after acknowledging

---

#### US-5: Closing Report -- Per-Fund Denominations [BUILD]
**As a** Store Staff member
**I want to** enter denomination breakdown for PCF, Delivery Fund, and Change Fund separately
**So that** closing cash reconciliation is accurate per fund

**Items:** C-2 (modified per audit)
**Backend:** Add fields to BEI Store Closing Report: `pcf_denom_1000`, `pcf_denom_500`, ..., `pcf_denom_coins`, `delivery_denom_1000`, ..., `change_fund_denom_1000`, ... (3 sets x 10 denominations = 30 fields, or use JSON field per fund)

**Acceptance Criteria:**
- [ ] AC-5.1: Closing Stage 1 shows 3 denomination grids: PCF, Delivery Fund, Change Fund
- [ ] AC-5.2: Each grid has rows for 1000, 500, 200, 100, 50, 20, 10, 5, 1, 0.25
- [ ] AC-5.3: Each row shows: denomination label, count input (integer >= 0), auto-calculated subtotal
- [ ] AC-5.4: Fund total auto-sums from denomination subtotals
- [ ] AC-5.5: Existing `denom_1000` through `denom_coins` fields continue to work (backward compatible)

---

#### US-6: Closing Report -- Voucher Depleted Amounts [BUILD]
**As a** Store Staff member
**I want to** enter PCF and Delivery voucher depleted amounts
**So that** fund utilization is tracked at closing

**Items:** C-3
**Backend:** Add `pcf_voucher_amount` (Currency) and `delivery_voucher_amount` (Currency) to BEI Store Closing Report

**Acceptance Criteria:**
- [ ] AC-6.1: Closing Stage 1 shows PCF Voucher Depleted Amount and Delivery Voucher Depleted Amount fields
- [ ] AC-6.2: Fields accept currency values (2 decimal places, >= 0)
- [ ] AC-6.3: Values persist and appear in Frappe Desk

---

### Module 2: Inventory -- Ordering

#### US-7: Store-Specific Item Filtering [EXTEND]
**As a** Store Staff member
**I want to** see only items my store can order
**So that** I don't accidentally order items not available at my location

**Items:** SO-1 (modified per audit -- NO new DocType)
**Approach:** Filter `get_orderable_items()` using Item Group hierarchy or warehouse-linked item groups

**Acceptance Criteria:**
- [ ] AC-7.1: `get_orderable_items(warehouse)` returns only items relevant to that warehouse's item group
- [ ] AC-7.2: If no item group filter configured, fallback to all stock items (no regression)
- [ ] AC-7.3: Item list loads in <2 seconds for typical store (~200 items)

---

#### US-8: Ordering UOM Display [EXTEND]
**As a** Store Staff member
**I want to** see the unit of measure next to each item when ordering
**So that** I know whether I'm ordering in packs, pieces, or kilograms

**Items:** SO-2
**Note:** API already returns `stock_uom`. Frontend not rendering it.

**Acceptance Criteria:**
- [ ] AC-8.1: Each item in ordering list shows `stock_uom` next to item name (e.g., "Chicken Breast -- KG")
- [ ] AC-8.2: UOM appears in confirmation dialog summary

---

#### US-9: Order by Frequency [EXTEND]
**As a** Store Staff member
**I want to** see frequently ordered items first
**So that** daily reordering is faster

**Items:** SO-3
**Backend:** Modify `get_orderable_items()` to join on BEI Store Order Item and sort by historical order count descending

**Acceptance Criteria:**
- [ ] AC-9.1: Items sorted by order frequency for that specific warehouse (most-ordered first)
- [ ] AC-9.2: Items with zero order history appear at the end, sorted alphabetically
- [ ] AC-9.3: Sort is the default -- no manual toggle needed

---

#### US-10: Order Confirmation Dialog [EXTEND]
**As a** Store Staff member
**I want to** review my order before submitting
**So that** I can catch mistakes before they go for approval

**Items:** SO-4

**Acceptance Criteria:**
- [ ] AC-10.1: Clicking "Submit Order" opens AlertDialog showing order summary (items, quantities, UOMs)
- [ ] AC-10.2: Dialog has "Cancel" and "Confirm" buttons
- [ ] AC-10.3: Order only submits on "Confirm" click

---

#### US-11: Ordering RBAC -- Staff Submits, Area Approves [BUILD]
**As a** Store Staff member
**I want to** submit orders directly
**So that** orders don't require supervisor intermediary

**As an** Area Supervisor
**I want to** be the approver for store orders
**So that** I maintain oversight over multiple stores' ordering

**Items:** SO-5, SO-6, SUP-1 (approval queue)
**Backend changes:**
1. Frontend RoleGuard allows Store Staff to access ordering page
2. `submit_order()` creates a BEI Approval Queue entry routed to Area Supervisor
3. `approve_order()` already checks Area Supervisor role (no change needed)

**Acceptance Criteria:**
- [ ] AC-11.1: Store Staff can access `/dashboard/inventory/ordering` (no RoleGuard block)
- [ ] AC-11.2: On submit, a BEI Approval Queue record is created with `approver_role = "Area Supervisor"`
- [ ] AC-11.3: Area Supervisor sees pending orders in their approval queue
- [ ] AC-11.4: Store Supervisor can NOT approve orders (only Area Supervisor)

---

### Module 3: Inventory -- Cycle Count

#### US-12: Cycle Count Date Picker [EXTEND]
**As a** Store Staff member
**I want to** select the count date rather than it auto-defaulting to today
**So that** I can submit counts for yesterday or backdate when needed

**Items:** CC-2
**Backend:** Accept optional `count_date` param in `submit_cycle_count()` (fallback to `nowdate()`)

**Acceptance Criteria:**
- [ ] AC-12.1: Date picker appears in cycle count form header
- [ ] AC-12.2: Defaults to today's date
- [ ] AC-12.3: Cannot select future dates
- [ ] AC-12.4: Selected date is sent to API and saved in BEI Cycle Count

---

#### US-13: Cycle Count -- No Negative Quantities [EXTEND]
**As a** Store Staff member
**I want to** be prevented from entering negative counts
**So that** data integrity is maintained

**Items:** CC-3
**Backend:** Add `if flt(item["counted_qty"]) < 0: frappe.throw()` in `submit_cycle_count()`

**Acceptance Criteria:**
- [ ] AC-13.1: Frontend quantity inputs have `min="0"` attribute
- [ ] AC-13.2: Backend rejects any item with `counted_qty < 0` with descriptive error message
- [ ] AC-13.3: Existing valid counts (qty=0) still accepted

---

#### US-14: Cycle Count Resubmission [EXTEND]
**As a** Store Staff member
**I want to** resubmit a rejected cycle count with corrections
**So that** I don't have to start from scratch

**Items:** CC-4
**Note:** Backend `resubmit_cycle_count()` already exists. Frontend missing resubmit button.

**Acceptance Criteria:**
- [ ] AC-14.1: Rejected cycle counts show "Resubmit" button
- [ ] AC-14.2: Resubmit pre-fills previous values for editing
- [ ] AC-14.3: Resubmitted count creates new version linked to original

---

### Module 4: Inventory -- Navigation & Data

#### US-15: Variance Report Navigation [EXTEND]
**As a** Store Supervisor
**I want to** access the Variance Report from the inventory section
**So that** I can investigate stock discrepancies

**Items:** IV-1

**Acceptance Criteria:**
- [ ] AC-15.1: Inventory nav/hub shows "Variance Report" link
- [ ] AC-15.2: Link navigates to `/dashboard/inventory/variances`
- [ ] AC-15.3: Page loads data from `inventory.get_variances()` API

---

#### US-16: Shelf Life Check Navigation [EXTEND]
**As a** Store Staff member
**I want to** access Shelf Life Check from the inventory section
**So that** I can flag items approaching expiry

**Items:** IV-2

**Acceptance Criteria:**
- [ ] AC-16.1: Inventory nav shows "Shelf Life Check" link
- [ ] AC-16.2: Link navigates to `/dashboard/inventory/shelf-life`
- [ ] AC-16.3: Page loads and renders shelf life data

---

#### US-17: Returns & Dispatch Data [DATA/CONFIG]
**As a** Store Staff member
**I want to** see returnable items and expected deliveries
**So that** I can process returns and receive dispatches

**Items:** IV-3, IV-4

**Acceptance Criteria:**
- [ ] AC-17.1: Test warehouse (TEST-STORE-BGC) has Stock Bin records for at least 5 items
- [ ] AC-17.2: At least 1 BEI Distribution Trip exists targeting test warehouse
- [ ] AC-17.3: Returns page shows returnable items from stock data
- [ ] AC-17.4: Dispatch Receive page shows expected delivery from trip data

---

### Module 5: Receiving -- FQI

#### US-18: FQI Item Dropdown + Other [EXTEND]
**As a** Store Staff member
**I want to** select received items from a dropdown (with "Other" option for manual entry)
**So that** item names are standardized and consistent

**Items:** FQ-1, FQ-2

**Acceptance Criteria:**
- [ ] AC-18.1: Item name field is a searchable Combobox fetching from Item master (`is_stock_item=1`)
- [ ] AC-18.2: Combobox includes "Other" as last option
- [ ] AC-18.3: Selecting "Other" shows a free-text input for manual item name
- [ ] AC-18.4: Both dropdown-selected and manually-entered items submit successfully

---

#### US-19: FQI Submission Fix [EXTEND]
**As a** Store Staff member
**I want to** submit FQI reports without errors
**So that** food quality issues are documented at receiving

**Items:** FQ-3
**Backend:** Ensure BEI FQI Report has `naming_series` configured. Set explicit defaults on insert.

**Acceptance Criteria:**
- [ ] AC-19.1: FQI report submits without naming_series error
- [ ] AC-19.2: Created report visible in Frappe Desk with correct naming format
- [ ] AC-19.3: Employee role has create+read+write permissions on BEI FQI Report

---

### Module 6: HR Self-Service

#### US-20: Leave Visibility & Approval Workflow [EXTEND]
**As a** Store Supervisor
**I want to** see and approve/reject leave applications from my direct reports
**So that** leave management works through the app

**As a** Store Staff member
**I want to** see my approved leave reflected in my leave balance
**So that** I trust the system is working

**Items:** HR-1, HR-2, HR-3, SUP-2
**Root cause:** Frappe Leave Application workflow config. Test employees may lack `reports_to` linkage.

**Acceptance Criteria:**
- [ ] AC-20.1: Test employees have `reports_to` set correctly (Staff -> Supervisor -> Area)
- [ ] AC-20.2: Leave Application Workflow is active in Frappe with states: Draft -> Applied -> Approved/Rejected
- [ ] AC-20.3: Supervisor sees pending leave applications from direct reports
- [ ] AC-20.4: After supervisor approves, leave status changes to "Approved" (not stuck on "Pending")
- [ ] AC-20.5: Approved leave appears in employee's leave balance
- [ ] AC-20.6: Supervisor's approval queue shows leave applications

---

#### US-21: Attendance Data [DATA/CONFIG]
**As a** Store Staff member
**I want to** see my attendance records
**So that** I can verify my work hours

**Items:** HR-4

**Acceptance Criteria:**
- [ ] AC-21.1: Test employees have at least 5 Attendance records (last 2 weeks)
- [ ] AC-21.2: Attendance page shows records sorted by date descending
- [ ] AC-21.3: Each record shows: date, status (Present/Absent/Half Day), check-in/out times

---

#### US-22: Shift Schedule Restriction [BUILD]
**As a** Store Supervisor
**I want to** assign shifts from predefined shift templates only
**So that** scheduling is consistent and compliant with labor rules

**Items:** HR-5
**Backend:** Populate 7 BEI Shift Template records (Opening, Mid, Closing, Split, etc.)

**Acceptance Criteria:**
- [ ] AC-22.1: 7 BEI Shift Templates exist with name + start_time + end_time
- [ ] AC-22.2: Schedule page shows dropdown of shift templates (not free-text input)
- [ ] AC-22.3: Selected shift auto-fills start and end times
- [ ] AC-22.4: Cannot enter arbitrary shift times outside templates

---

#### US-23: Payslip Data [DATA/CONFIG]
**As a** Store Staff member
**I want to** view my payslip in the app
**So that** I can check my salary details

**Items:** HR-6

**Acceptance Criteria:**
- [ ] AC-23.1: Test employees have at least 1 Salary Slip record
- [ ] AC-23.2: Payslip page renders salary slip data (gross, deductions, net)

---

#### US-24: Coverage Request Dropdowns [EXTEND]
**As a** Store Staff member
**I want to** select store and employee from dropdowns when requesting coverage
**So that** I pick valid values instead of typing free-text

**Items:** HR-7, HR-8

**Acceptance Criteria:**
- [ ] AC-24.1: Store field is a searchable Combobox fetching warehouses (store type)
- [ ] AC-24.2: Employee field is a searchable Combobox fetching employees with name display
- [ ] AC-24.3: Both fields use debounced search (300ms)
- [ ] AC-24.4: Existing `resolve_employee()` and `resolve_warehouse()` backend APIs used

---

#### US-25: Coverage Request Submission Fix [EXTEND]
**As a** Store Staff member
**I want to** submit coverage requests without errors
**So that** I can request shift coverage when needed

**Items:** HR-9
**Backend:** Set `doc.status = "Open"` explicitly in `request_coverage()` before insert

**Acceptance Criteria:**
- [ ] AC-25.1: Coverage request submits successfully
- [ ] AC-25.2: Created request has status "Open" in Frappe Desk
- [ ] AC-25.3: Request appears in supervisor's pending items

---

### Module 7: Communication

#### US-26: Kudos Fix -- Permissions & Categories [EXTEND]
**As a** Store Staff member
**I want to** send kudos to colleagues
**So that** I can recognize good work

**Items:** COM-1
**Backend:** (1) Add write=1 to Employee role on BEI Kudos. (2) Align categories: update DocType Select options to match frontend values OR update frontend to match DocType.

**Acceptance Criteria:**
- [ ] AC-26.1: BEI Kudos DocType has Employee role with create+read+write
- [ ] AC-26.2: Category values match between frontend dropdown and DocType Select options
- [ ] AC-26.3: Kudos submits successfully from Store Staff account
- [ ] AC-26.4: Submitted kudos visible in recipient's feed

---

#### US-27: Kudos Employee Dropdown [EXTEND]
**As a** Store Staff member
**I want to** search and select an employee from a dropdown when sending kudos
**So that** I pick the right person

**Items:** COM-2

**Acceptance Criteria:**
- [ ] AC-27.1: Recipient field is a searchable Combobox
- [ ] AC-27.2: Search queries employees by name with debounced input
- [ ] AC-27.3: Selected employee shows name + ID

---

#### US-28: Help & Support Fix [EXTEND]
**As a** Store Staff member
**I want to** submit support tickets without errors
**So that** I can report issues and get help

**Items:** COM-4
**Backend:** Align category values between frontend and BEI Support Ticket DocType. Verify field names match.

**Acceptance Criteria:**
- [ ] AC-28.1: Support ticket submits successfully from Store Staff account
- [ ] AC-28.2: Category dropdown values match DocType Select options exactly
- [ ] AC-28.3: Created ticket visible in Frappe Desk with all fields populated

---

#### US-29: Announcements Test Data [DATA/CONFIG]
**As a** Store Staff member
**I want to** see company announcements
**So that** I stay informed

**Items:** COM-5

**Acceptance Criteria:**
- [ ] AC-29.1: At least 1 BEI Announcement exists with `status=Published`
- [ ] AC-29.2: Announcements page displays published announcements

---

### Module 8: Supervisor Tools

#### US-30: Approval Queue Population [BUILD]
**As a** Store Supervisor or Area Supervisor
**I want to** see pending items in my approval queue
**So that** I can approve/reject orders and requests

**Items:** SUP-1
**Backend:** Ensure `submit_order()` creates a BEI Approval Queue entry. Verify queue entry has correct `approver_role`, `reference_doctype`, `reference_name`.

**Acceptance Criteria:**
- [ ] AC-30.1: After order submission, BEI Approval Queue record is created
- [ ] AC-30.2: Queue entry routes to correct approver role (Area Supervisor for orders)
- [ ] AC-30.3: Approval queue page shows pending items with status, type, and timestamp
- [ ] AC-30.4: Approving/rejecting from queue updates the underlying document

---

#### US-31: Reports Feed Data [DATA/CONFIG]
**As a** Store Supervisor
**I want to** see submitted reports in my feed
**So that** I can track store compliance

**Items:** SUP-3
**Dependency:** Requires report submission bugs to be fixed first (US-1, US-5, US-6)

**Acceptance Criteria:**
- [ ] AC-31.1: After an Opening or Closing report is submitted, it appears in the reports feed
- [ ] AC-31.2: Feed shows report type, store, date, and status

---

#### US-32: Labor Plan Store Dropdown [EXTEND]
**As a** Store Supervisor
**I want to** select my store from a dropdown for labor planning
**So that** I pick valid stores only

**Items:** SUP-4

**Acceptance Criteria:**
- [ ] AC-32.1: Store field is a Combobox fetching supervisor's assigned stores
- [ ] AC-32.2: Only stores the supervisor manages appear in dropdown

---

#### US-33: Completeness Tracker Filtering [EXTEND]
**As a** Store Supervisor
**I want to** see completeness data only for my assigned stores
**So that** the tracker is relevant to my scope

**Items:** SUP-5
**Fix:** Filter completeness query by `reports_to` chain or `custom_area_supervisor` field

**Acceptance Criteria:**
- [ ] AC-33.1: Completeness tracker shows only stores where user is supervisor or area supervisor
- [ ] AC-33.2: Data loads without showing other supervisors' stores

---

#### US-34: Enrichment Tracker Navigation [EXTEND]
**As a** Store Supervisor
**I want to** access the Enrichment Tracker from my dashboard
**So that** I can track store enrichment activities

**Items:** SUP-6

**Acceptance Criteria:**
- [ ] AC-34.1: Supervisor nav shows "Enrichment Tracker" link
- [ ] AC-34.2: Link navigates to `/dashboard/enrichment`
- [ ] AC-34.3: Page loads enrichment data from existing API

---

#### US-35: Store Dashboard Navigation [EXTEND]
**As a** Store Supervisor
**I want to** access the Store Dashboard from my dashboard
**So that** I can see store-level KPIs

**Items:** SUP-7

**Acceptance Criteria:**
- [ ] AC-35.1: Supervisor nav shows "Store Dashboard" link
- [ ] AC-35.2: Link navigates to `/dashboard/analytics/store`
- [ ] AC-35.3: Page loads store dashboard data

---

#### US-36: Store Visit -- Permissions & Store List [EXTEND]
**As an** Area Supervisor
**I want to** create store visit reports
**So that** I can document audit visits to my stores

**Items:** SUP-8
**Backend:** Add Area Supervisor + Employee roles to BEI Store Visit Report DocType permissions

**Acceptance Criteria:**
- [ ] AC-36.1: BEI Store Visit Report has Area Supervisor role with create+read+write
- [ ] AC-36.2: Store list fetches from warehouses where `custom_area_supervisor` matches current user
- [ ] AC-36.3: Area Supervisor can submit a store visit report successfully

---

### Module 9: Area Supervisor

#### US-37: Area Dashboard & Analytics Data [DATA/CONFIG]
**As an** Area Supervisor
**I want to** see dashboard and analytics data for my stores
**So that** I can monitor area-level performance

**Items:** AS-1, AS-2

**Acceptance Criteria:**
- [ ] AC-37.1: Test warehouses have `custom_area_supervisor` set to test.area@bebang.ph
- [ ] AC-37.2: Area Dashboard loads data for assigned stores
- [ ] AC-37.3: Analytics Overview shows aggregated metrics for area

---

### Module 10: Profile

#### US-38: Profile Submission Fix [EXTEND]
**As a** Store Staff member
**I want to** edit my profile without submission errors
**So that** I can update my personal information

**Items:** PR-1
**Investigation needed:** Check for duplicate pending BEI Edit Request, field validation mismatch, or permission issue.

**Acceptance Criteria:**
- [ ] AC-38.1: Profile edit submits successfully (no 400/500 error)
- [ ] AC-38.2: If a pending edit request exists for same field, show clear message (not generic error)
- [ ] AC-38.3: Created BEI Edit Request visible in Frappe Desk with status "Pending"

---

## Functional Requirements

| ID | Requirement | Priority | Tag | Acceptance Criteria |
|----|-------------|----------|-----|---------------------|
| FR-1 | Fix store resolution for non-supervisor users | High | [EXTEND] | Staff resolves store from Employee.branch |
| FR-2 | Add Employee permissions to POS Upload, Store Visit DocTypes | High | [EXTEND] | Employee role has create+read+write |
| FR-3 | Fix BEI Kudos DocType permissions + category alignment | High | [EXTEND] | write=1 on Employee role; categories match |
| FR-4 | Add `deposit_type` Select to BEI Bank Deposit | High | [BUILD] | Field exists with "Bank Deposit"/"Pickup" options |
| FR-5 | Add per-fund denomination fields to Closing Report | High | [BUILD] | 3 fund sections with 10 denomination rows each |
| FR-6 | Add voucher depleted amount fields to Closing Report | Medium | [BUILD] | `pcf_voucher_amount`, `delivery_voucher_amount` fields |
| FR-7 | Filter orderable items by store/warehouse | High | [EXTEND] | API returns store-relevant items only |
| FR-8 | Sort orderable items by order frequency | Medium | [EXTEND] | Most-ordered items first |
| FR-9 | Add negative qty validation to cycle count | High | [EXTEND] | Backend rejects qty < 0 |
| FR-10 | Accept optional count_date in cycle count API | Medium | [EXTEND] | Date picker works, no future dates |
| FR-11 | Fix FQI naming_series and submit flow | High | [EXTEND] | FQI creates without error |
| FR-12 | Fix Coverage Request default status | High | [EXTEND] | Status="Open" on insert |
| FR-13 | Configure Frappe Leave Application Workflow | High | [EXTEND] | Draft->Applied->Approved/Rejected transitions work |
| FR-14 | Populate 7 BEI Shift Templates | Medium | [BUILD] | Templates with name+start+end times |
| FR-15 | Create BEI Approval Queue entries on order submit | High | [BUILD] | Queue record created with correct approver |
| FR-16 | Fix completeness tracker store scope filtering | Medium | [EXTEND] | Shows only user's stores |
| FR-17 | Fix Help & Support category alignment | High | [EXTEND] | Categories match between frontend and DocType |
| FR-18 | Add Area Supervisor perm to Store Visit Report | High | [EXTEND] | Area Supervisor role on DocType |
| FR-19 | Convert 6 text inputs to searchable Combobox | Medium | [EXTEND] | FQI item, coverage store/employee, kudos recipient, labor plan store, shift schedule |
| FR-20 | Add 4 navigation links to existing pages | Medium | [EXTEND] | Variance, Shelf Life, Enrichment, Store Dashboard in nav |

## Non-Functional Requirements

| ID | Requirement | Metric | Target |
|----|-------------|--------|--------|
| NFR-1 | API response time | P95 latency | < 500ms for all modified endpoints |
| NFR-2 | Combobox search latency | Time to first result | < 300ms with debounce |
| NFR-3 | Denomination grid rendering | Time to interactive | < 200ms on mobile |
| NFR-4 | Backward compatibility | Existing data integrity | Zero data loss on DocType field additions |
| NFR-5 | Mobile responsiveness | All new/modified UI | Usable on 375px viewport width |
| NFR-6 | Deployment sequence | Backend before frontend | Backend changes backward-compatible; frontend deploy after |

---

## Glossary

- **BEI**: Bebang Enterprise Inc.
- **UAT**: User Acceptance Testing
- **FQI**: Food Quality Inspection (receiving quality check)
- **PCF**: Petty Cash Fund
- **UOM**: Unit of Measure
- **Combobox**: Shadcn UI searchable dropdown with type-ahead filtering
- **RoleGuard**: Frontend route protection component in bei-tasks that checks user roles
- **DocType**: Frappe framework data model (equivalent to a database table + form)
- **naming_series**: Frappe auto-naming pattern for document IDs (e.g., "FQI-.YYYY.-.####")
- **reports_to**: Employee field linking to their direct supervisor's Employee record
- **custom_area_supervisor**: Custom field on Warehouse DocType linking to Area Supervisor user
- **Stock Bin**: Frappe record tracking item quantity per warehouse

---

## Out of Scope

- New DocTypes (per duplication audit -- use existing)
- Mobile app (native iOS/Android) -- all work targets PWA
- POS integration (real-time POS data sync) -- only manual file upload
- Payroll calculation logic -- only displaying existing Salary Slip data
- Leave balance calculation changes -- only workflow/visibility fixes
- Commissary module changes (separate spec)
- Procurement module changes (separate spec)
- Performance optimization of existing working endpoints
- User registration / account creation flows

---

## Dependencies

| Dependency | Blocks | Notes |
|------------|--------|-------|
| Frappe Leave Workflow config | US-20 (HR-1/HR-2/HR-3/SUP-2) | Must configure in Frappe before testing |
| Test employee `reports_to` linkage | US-20 | Staff->Supervisor->Area chain must be set |
| Backend DocType permission deploys | US-4, US-26, US-36 | Deploy backend before testing frontend |
| Test data seeding script | US-17, US-21, US-23, US-29, US-31, US-37 | 6 DATA/CONFIG items need seed data |
| BEI Shift Template definitions | US-22 | Need exact 7 shift names/times from Ops team |
| bei-tasks frontend deploy (Vercel) | All frontend items | After backend is deployed and verified |
| Backend deploy (Docker build) | All backend items | Must precede frontend deploy |

### Dependency Chain
```
Backend permissions/fields (Phase 1) --> Frontend UI fixes (Phase 2)
Leave workflow config (Phase 1) --> Leave testing (Phase 3)
Test data seeding (anytime) --> DATA/CONFIG item verification
Order RBAC fix (US-11) --> Approval queue (US-30) --> Reports feed (US-31)
Handover fix (US-1) --> Closing report denomination (US-5)
```

---

## Implementation Phasing (Recommended)

| Phase | Items | Stories | Effort | Parallel? |
|-------|-------|---------|--------|-----------|
| 1: Permissions & Quick Fixes | 16 | US-1,2,3,4,6,8,10,13,14,19,25,26 | 1 day | Backend + Frontend |
| 2: Dropdown Conversions | 8 | US-18,24,27,32,22 | 1 day | Frontend-heavy |
| 3: Navigation & Config | 8 | US-15,16,17,21,23,29,34,35,37 | 0.5 day | Mixed |
| 4: Complex Features | 6 | US-5,7,9,11,30,38 | 1.5 days | Backend + Frontend |
| 5: Leave Workflow | 4 | US-20,28,31,33,36 | 1 day | Config + Test |

**Total estimated: 3-5 days with 2 parallel agents**

---

## Success Criteria

- [ ] All 44 UAT issues marked CLOSED in emergency fix plan
- [ ] 0 submission errors on any form across all 4 roles
- [ ] All navigation links reachable (no dead-end pages)
- [ ] All dropdown fields use Combobox (no free-text for entity fields)
- [ ] Leave approval workflow completes end-to-end (apply -> approve -> reflected)
- [ ] Full E2E test pass (`/test-full-cycle`) with all 4 test accounts

---

## Unresolved Questions

1. **BEI Shift Templates**: Exact 7 shift names and time ranges not confirmed by Ops team. Placeholder: Opening (5:00-14:00), Mid (10:00-19:00), Closing (14:00-23:00), Split, etc.
2. **Item Group filtering (SO-1)**: Which Item Group tree branch maps to which store type? Need Ops confirmation or fallback to all items.
3. **Denomination approach (C-2)**: 30 individual fields vs 3 JSON fields? Individual fields are queryable but verbose. JSON is cleaner but harder to report on.
4. **PR-1 root cause**: Need to reproduce the exact error before confirming the fix approach. Could be duplicate pending request, field validation, or permission.
5. **Category alignment (COM-1, COM-4)**: Should frontend categories match DocType or vice versa? Recommendation: update frontend to match DocType (source of truth).

---

## Next Steps

1. Approve requirements and proceed to design phase
2. Design phase creates implementation tasks for 2-agent parallel execution
3. Backend agent: DocType permissions, field additions, API bug fixes
4. Frontend agent: UI enhancements, dropdown conversions, navigation links
5. Seed test data script (can run in parallel with both agents)
6. Deploy backend first, then frontend
7. Run `/test-full-cycle` to verify all 44 items resolved
