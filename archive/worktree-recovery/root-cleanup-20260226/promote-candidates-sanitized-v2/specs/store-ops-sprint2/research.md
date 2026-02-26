---
spec: store-ops-sprint2
phase: research
created: 2026-02-07
---

# Research: store-ops-sprint2

## Executive Summary

44 OPEN issues remain from Feb 6 Ops UAT on my.bebang.ph. After auditing the backend (hrms/api/*.py, DocType JSONs) and frontend (bei-tasks pages), I classify: **8 BUG fixes**, **22 ENHANCEMENT modifications**, **8 NEW FEATURE builds**, **6 DATA/CONFIG items**. Effort estimate: **3-5 days** for 2 agents (1 backend + 1 frontend) working in parallel across both repos. The biggest risk is the 2-repo deployment (BEI-ERP Docker build + bei-tasks Vercel) -- changes must ship to BOTH repos simultaneously for most items.

---

## Item-by-Item Classification

### Store Ops (9 items)

| ID | Issue | Classification | Backend | Frontend | Effort | Notes |
|----|-------|---------------|---------|----------|--------|-------|
| H-1 | Handover limited to supervisor | **BUG (RBAC)** | No change needed | Fix `RoleGuard` or remove supervisor-only store fetch | S | Handover page calls `/api/supervisor/my-stores` which only returns stores for supervisor role users. Staff need their branch from employee record instead. |
| H-2 | Cannot complete handover | **BUG (RBAC)** | DocType `bei_mid_shift_handover` already has Employee perms | Fix frontend store resolution for non-supervisor users | S | Same root cause as H-1. Once H-1 fixed, H-2 resolves. |
| D-1 | No Bank Deposit vs Pickup selector | **ENHANCEMENT** | Add `deposit_type` Select field to BEI Bank Deposit DocType | Add radio/select for "Bank Deposit" vs "Pickup" | S | New field on DocType + frontend select component. |
| D-2 | Date shows range instead of single day | **BUG** | N/A | Change `dates_covered` text input to single date picker | S | Frontend-only: deposit entries have free-text `dates_covered`. Change to `date` input type. |
| D-3 | Can upload more than 4 photos | **ENHANCEMENT** | N/A | Add `photos.length < 4` check to `addPhoto()` | XS | Frontend-only: 3-line change to cap photo array at 4. |
| P-1 | POS access limited to supervisor | **BUG (RBAC)** | POS DocType `bei_pos_upload` missing Employee permissions | Add Employee role to POS Upload DocType perms | S | Same pattern as other DocType permission bugs. Plus frontend may use supervisor-only store fetch. |
| P-2 | No date validation on POS file upload | **ENHANCEMENT** | Backend has `upload_pos_data()` with date validation already built | Wire frontend to send `skip_date_validation=false` and show warning | S | Backend already implemented (lines 656-714 of store.py). Frontend needs to display the `date_mismatch` warning. |
| C-2 | Denomination for funds unavailable | **NEW FEATURE** | Add denomination child table to BEI Store Closing Report | Build denomination breakdown UI (bills/coins grid for PCF, Delivery, Change Fund) | M | Requires new child DocType `BEI Denomination Entry` + new frontend component. |
| C-3 | PCF/Delivery voucher depleted amounts | **NEW FEATURE** | Add `pcf_voucher_amount`, `delivery_voucher_amount` fields to closing report | Add reconciliation fields in closing Stage 1 | S | New fields on existing DocType + frontend form fields. |

### Inventory (13 items)

| ID | Issue | Classification | Backend | Frontend | Effort | Notes |
|----|-------|---------------|---------|----------|--------|-------|
| SO-1 | Items not filtered to store SKU | **ENHANCEMENT** | `get_orderable_items()` returns ALL items (line 120-128 of store.py). Need store-specific item list. | N/A (backend filter) | M | Requires new config: "store item list" mapping (or Item custom field `allowed_stores`). |
| SO-2 | UOM not showing per item | **BUG** | `stock_uom` already returned by API (line 126). | Frontend not displaying `stock_uom` field | S | Frontend reads `item.stock_uom` but doesn't render it. Likely a missing column. |
| SO-3 | Items not sorted by most ordered | **ENHANCEMENT** | Need to aggregate order history per item per store and sort by frequency | Update `get_orderable_items()` to sort by order frequency | M | New SQL join on BEI Store Order Item to count historical orders. |
| SO-4 | No confirmation dialog before submit | **ENHANCEMENT** | N/A | Add confirmation Dialog with order summary before final submit | S | Frontend-only: Shadcn AlertDialog with item list + quantities. |
| SO-5 | Submitter should be Store Staff | **ENHANCEMENT (RBAC)** | API already accepts any authenticated user. Need role check. | Update frontend to allow Staff role to submit | S | Currently `submit_order()` has no role restriction. Backend fine. Frontend ordering page may restrict via RoleGuard. |
| SO-6 | Approver should be Area Supervisor | **ENHANCEMENT (Workflow)** | `approve_order()` already checks Area Supervisor role (line 229). | Approval queue routing needs to target Area Supervisor, not Store Supervisor | S | Backend correct. Need to verify approval queue entry routes to Area Supervisor. |
| CC-2 | No date picker in header | **ENHANCEMENT** | `submit_cycle_count()` auto-sets `count_date = nowdate()`. Add optional param. | Add date picker in cycle count form header | S | Backend: accept optional `count_date` param. Frontend: add date input. |
| CC-3 | Negative entries allowed | **BUG** | No validation in `submit_cycle_count()` for negative `counted_qty` | Add `min="0"` to quantity inputs + backend validation | S | Both repos: backend `flt(item["counted_qty"])` should validate `>= 0`. Frontend: `min="0"` on input. |
| CC-4 | Cannot resubmit/override | **ENHANCEMENT** | `resubmit_cycle_count()` already exists (line 102-156 of inventory.py) | Frontend doesn't expose resubmit button for rejected counts | S | Backend exists. Frontend needs "Resubmit" button on rejected cycle counts. |
| IV-1 | Variance Report button unavailable | **NEW FEATURE** | `report_variance()` exists (line 160-181 of inventory.py). `get_variances()` exists. | No variance report page exists in frontend (only `variances/page.tsx` exists but needs review) | M | Backend API exists. Frontend page at `inventory/variances/page.tsx` exists but may not be wired up or linked from inventory hub. |
| IV-2 | Shelf Life Check button unavailable | **NEW FEATURE** | `request_shelf_extension()` and `approve_shelf_extension()` exist | Frontend page at `inventory/shelf-life/page.tsx` exists but may not be linked | M | Same as IV-1 -- page exists but likely not in navigation. |
| IV-3 | Returns - no stores assigned | **DATA/CONFIG** | `get_returnable_items()` queries Bin table for items with stock | Test stores need actual stock entries (Bin records) | S | Need to seed test stock in TEST-STORE-BGC warehouse. |
| IV-4 | Dispatch Receive - no information | **DATA/CONFIG** | `get_expected_deliveries()` queries BEI Distribution Trip | No test delivery trips exist | S | Need to seed test distribution trip data. |

### Receiving (3 items)

| ID | Issue | Classification | Backend | Frontend | Effort | Notes |
|----|-------|---------------|---------|----------|--------|-------|
| FQ-1 | Item name not dropdown | **ENHANCEMENT** | API accepts any `item_code` string. Need item list endpoint. | Replace text input with searchable Select fetching from Item master | M | Frontend needs combobox with API call to `frappe.client.get_list("Item", ...)`. |
| FQ-2 | "Other" doesn't trigger manual input | **ENHANCEMENT** | N/A | Add conditional text input when item selection = "Other" | S | Frontend-only: show text field when Select value is "Other". |
| FQ-3 | Error submitting FQI report | **BUG** | `create_fqi_report()` missing `naming_series` set. DocType may lack Employee permission. | N/A (backend fix) | S | FQI Report DocType has Employee permission with write. Check if `naming_series` is set on DocType default. BUG-09 from audit. |

### HR Self-Service (9 items)

| ID | Issue | Classification | Backend | Frontend | Effort | Notes |
|----|-------|---------------|---------|----------|--------|-------|
| HR-1 | Leave not visible in supervisor | **BUG** | Frappe Leave Application uses `reports_to` field for approval routing. May not be set on test accounts. | N/A | S | Check test employee `reports_to` field. Supervisor needs to be linked. |
| HR-2 | Approved leave stays pending | **BUG** | Frappe Leave Application workflow may have status mismatch or missing workflow transition | N/A | M | Need to audit Frappe Leave Application workflow states. May need to configure Leave Approval workflow. |
| HR-3 | Approved leave not reflected in crew | **BUG** | Same root cause as HR-2 | N/A | - | Resolves with HR-2. |
| HR-4 | No attendance data | **DATA/CONFIG** | Attendance records don't exist for test accounts | Seed attendance data for test employees | S | Need to create Attendance records via bench console. |
| HR-5 | Schedule shifts not restricted | **ENHANCEMENT** | BEI Shift Template DocType exists (`bei_shift_template.json`) | Frontend schedule page uses free-form input instead of predefined shifts | M | Need to: (1) populate 7 shift templates in DocType, (2) frontend fetches and renders as dropdown. |
| HR-6 | No payslip data | **DATA/CONFIG** | No Salary Slip records exist for test employees | Seed sample payslip data | S | Need salary structure + salary slip for test accounts. |
| HR-7 | Coverage Request store name not dropdown | **ENHANCEMENT** | `request_coverage()` accepts any store string, `resolve_warehouse()` handles resolution | Replace text input with warehouse/store dropdown | S | Frontend: fetch store list from API, render as Select. |
| HR-8 | Coverage Request employee name not dropdown | **ENHANCEMENT** | `resolve_employee()` already exists (coverage.py line 37-65) for fuzzy matching | Replace text input with employee search combobox | S | Frontend: employee search API + combobox. |
| HR-9 | Coverage Request submission error | **BUG** | Status mismatch: Coverage Request sets no explicit status on insert (defaults to DocType default) | N/A | S | Check BEI Staff Coverage Request DocType default status. API should set explicit `doc.status = "Open"`. |

### Communication (4 items)

| ID | Issue | Classification | Backend | Frontend | Effort | Notes |
|----|-------|---------------|---------|----------|--------|-------|
| COM-1 | Kudos error sending | **BUG** | `send_kudos()` calls `doc.insert()`. BEI Kudos Employee perm: create=1, read=1 but **NO write**. Category mismatch: DocType has "Teamwork,Customer Service,Innovation,Leadership,Going Extra Mile" but frontend sends "Teamwork,Excellence,Positivity,Leadership". | Fix Kudos DocType Employee perms (add write=1) + align category values | S | Two bugs: (1) Missing write permission, (2) Frontend categories don't match DocType Select options. |
| COM-2 | Kudos employee name should be dropdown | **ENHANCEMENT** | `send_kudos()` expects `to_employee` as Employee ID | Replace text/ID input with employee search combobox | S | Same pattern as HR-8. |
| COM-4 | Help & Support ticket creation error | **BUG** | `create_support_ticket()` on line 202-211 of communication.py. BEI Support Ticket has Employee create+read+write. | Check if frontend sends correct field names (category, subject, description, priority) | S | DocType perms look correct. Likely frontend sends wrong field names or category values don't match DocType Select options. |
| COM-5 | Announcements no data | **DATA/CONFIG** | `get_announcements()` filters for `status=Published`. No published announcements exist. | N/A | XS | Seed a test announcement with status=Published. |

### Supervisor Tools (8 items)

| ID | Issue | Classification | Backend | Frontend | Effort | Notes |
|----|-------|---------------|---------|----------|--------|-------|
| SUP-1 | Queue - no orders to approve | **DATA/CONFIG** | Approval queue depends on BEI Approval Queue records. Orders go to "Pending Approval" but may not create queue entries. | N/A | M | Need to check if `submit_order()` creates an Approval Queue entry. If not, add it. |
| SUP-2 | Leave approval stays pending | **BUG** | Same as HR-2. Frappe Leave Application workflow issue. | N/A | - | Resolves with HR-2. |
| SUP-3 | Reports Feed empty | **DATA/CONFIG** | Reports Feed reads store reports (opening, closing, etc.) | No submitted reports exist for test stores | S | Depends on fixing the report submission bugs first (already fixed per plan). |
| SUP-4 | Labor Plan store list not dropdown | **ENHANCEMENT** | `supervisor.py` has labor plan endpoints. Store list is passed by frontend. | Replace text input with store dropdown | S | Frontend: fetch supervisor's stores, render as Select. |
| SUP-5 | Completeness Tracker not filtered | **BUG** | Completeness page may fetch all stores instead of filtering by supervisor's assigned stores | Filter by `reports_to` chain or `custom_area_supervisor` | M | Need to verify completeness API filters by user's store scope. |
| SUP-6 | Enrichment Tracker unavailable | **NEW FEATURE** | Enrichment tracker API exists (`hrms/api/enrichment.py`) | Page exists at `dashboard/enrichment/page.tsx` but not in supervisor nav | S | Link exists but not wired into supervisor section of navigation. |
| SUP-7 | Store Dashboard unavailable | **NEW FEATURE** | `get_store_dashboard()` exists (dashboard.py) | Page exists at `dashboard/analytics/store/page.tsx` but not in supervisor nav | S | Same as SUP-6 -- page exists but missing from supervisor nav links. |
| SUP-8 | Store Visit no stores available | **BUG** | `create_store_visit()` expects store param. Frontend store list empty. | Fix store list fetch for Area Supervisor role (may use `custom_area_supervisor` field on Warehouse) | S | Store Visit Report permissions: System Manager + HR User only. Missing Area Supervisor role. Also frontend may not fetch stores correctly. |

### Area Supervisor (2 items)

| ID | Issue | Classification | Backend | Frontend | Effort | Notes |
|----|-------|---------------|---------|----------|--------|-------|
| AS-1 | Area Dashboard no data | **DATA/CONFIG** | `get_area_dashboard()` filters by `custom_area_supervisor` field on Warehouse. Test warehouses may not have this field set. | N/A | S | Set `custom_area_supervisor` on test warehouses to test.area@bebang.ph. |
| AS-2 | Analytics Overview no data | **DATA/CONFIG** | Same as AS-1 -- no data because no stores linked to area supervisor | N/A | - | Resolves with AS-1. |

### Profile (1 item)

| ID | Issue | Classification | Backend | Frontend | Effort | Notes |
|----|-------|---------------|---------|----------|--------|-------|
| PR-1 | Submission error | **BUG** | BEI Edit Request DocType may have permission issue or field mismatch | Check frontend payload vs DocType fields | M | Need to inspect my-profile page submission flow and BEI Edit Request insert pathway. Possible pending approval conflict (user can't have 2 pending edit requests for same field). |

---

## Classification Summary

| Classification | Count | Effort Range |
|----------------|-------|-------------|
| **BUG** | 8 | XS-M |
| **ENHANCEMENT** | 22 | XS-M |
| **NEW FEATURE** | 8 | S-M |
| **DATA/CONFIG** | 6 | XS-S |
| **Total** | 44 | |

---

## Existing Codebase Inventory

### Backend APIs (hrms/api/)

| File | Endpoints | Relevant Issues | Status |
|------|-----------|----------------|--------|
| `store.py` | 22 | H-1/H-2, D-1/D-2/D-3, P-1/P-2, C-2/C-3 | All endpoints exist. Missing: deposit_type field, denomination, photo limit. |
| `inventory.py` | 12 | SO-1 to SO-6, CC-2 to CC-4, IV-1 to IV-4 | Order/count/variance/return APIs exist. Missing: store-specific item filter, sort-by-frequency. |
| `communication.py` | 12 | COM-1, COM-2, COM-4, COM-5 | Kudos/complaint/ticket/announcement APIs exist. Bugs: Kudos perms + categories. |
| `coverage.py` | 4 | HR-7, HR-8, HR-9 | Coverage API exists with `resolve_employee()` and `resolve_warehouse()`. Bug: missing status set. |
| `supervisor.py` | 28+ | SUP-1 to SUP-8 | Approval queue, store visit, labor plan APIs exist. Store visit perms need update. |
| `dashboard.py` | 6 | AS-1, AS-2 | Store/area/ops dashboard APIs exist. Data depends on `custom_area_supervisor` config. |
| `enrichment.py` | 17 | SUP-6 | Full enrichment API exists. Frontend page exists at `dashboard/enrichment/`. |

### BEI DocTypes (Permissions Audit)

| DocType | Employee Perm | Issue | Fix Needed |
|---------|--------------|-------|------------|
| BEI Mid-Shift Handover | create+read+write | OK | N/A |
| BEI POS Upload | Missing Employee | P-1 | Add Employee role |
| BEI Kudos | create+read (NO write) | COM-1 | Add write perm |
| BEI Support Ticket | create+read+write | OK | N/A |
| BEI Store Order | Employee exists | OK | N/A |
| BEI FQI Report | Employee create+read+write | OK | Check naming_series |
| BEI Staff Coverage Request | Employee exists | OK | Check status default |
| BEI Store Visit Report | Missing Employee/Area Supervisor | SUP-8 | Add Area Supervisor role |
| BEI Bank Deposit | Employee (already fixed per plan) | OK | N/A |
| BEI Cycle Count | Employee (already fixed per plan) | OK | N/A |

### Frontend Pages (bei-tasks)

| Path | Exists | Issues | Notes |
|------|--------|--------|-------|
| `store-ops/handover/page.tsx` | Yes | H-1, H-2 | Uses `/api/supervisor/my-stores` -- needs fallback for staff |
| `store-ops/deposit/page.tsx` | Yes | D-1, D-2, D-3 | Missing deposit type selector, free-text dates, no photo limit |
| `store-ops/pos/page.tsx` | Yes | P-1, P-2 | Missing date validation display |
| `store-ops/closing/page.tsx` | Yes | C-2, C-3 | Missing denomination UI, voucher amounts |
| `inventory/ordering/page.tsx` | Yes | SO-1 to SO-6 | Missing SKU filter, UOM display, sort, confirmation dialog |
| `inventory/counts/page.tsx` | Yes | CC-2 to CC-4 | Missing date picker, negative validation, resubmit |
| `inventory/variances/page.tsx` | Yes | IV-1 | Page exists but may not be in nav |
| `inventory/shelf-life/page.tsx` | Yes | IV-2 | Page exists but may not be in nav |
| `inventory/returns/page.tsx` | Yes | IV-3 | Exists, needs stock data |
| `receiving/dispatch/page.tsx` | Yes | IV-4 | Exists, needs trip data |
| `receiving/fqi/page.tsx` | Yes | FQ-1 to FQ-3 | Text input needs dropdown conversion |
| `hr/leave/page.tsx` | Yes | HR-1 to HR-3 | Frappe workflow issue, not frontend |
| `hr/attendance/page.tsx` | Yes | HR-4 | Needs test data |
| `hr/schedule/page.tsx` | Yes | HR-5 | Free-form instead of predefined shifts |
| `hr/payslip/page.tsx` | Yes | HR-6 | Needs test data |
| `hr/coverage/page.tsx` | Yes | HR-7 to HR-9 | Text inputs need dropdowns |
| `communication/kudos/page.tsx` | Yes | COM-1, COM-2 | Category mismatch + text input |
| `communication/support/page.tsx` | Yes | COM-4 | Check field name alignment |
| `communication/announcements/page.tsx` | Yes | COM-5 | Needs published test data |
| `supervisor/labor-plan/page.tsx` | Yes | SUP-4 | Text input for store |
| `supervisor/reports-feed/page.tsx` | Yes | SUP-3 | Needs submitted report data |
| `queue/page.tsx` | Yes | SUP-1, SUP-2 | Needs queue entries |
| `completeness/page.tsx` | Yes | SUP-5 | Filter by supervisor's stores |
| `enrichment/page.tsx` | Yes | SUP-6 | Not in supervisor nav |
| `analytics/store/page.tsx` | Yes | SUP-7 | Not in supervisor nav |
| `analytics/area/page.tsx` | Yes | AS-1, AS-2 | Needs area_supervisor config on warehouses |
| `my-profile/page.tsx` | Yes | PR-1 | Edit request submission error |

---

## Feasibility Assessment

| Aspect | Assessment | Notes |
|--------|------------|-------|
| Technical Viability | **High** | All APIs exist. Most issues are permission fixes, dropdown conversions, or small UI enhancements. |
| Effort Estimate | **M** (3-5 days) | 2 parallel agents: backend (1.5-2 days), frontend (2-3 days). Deployment adds 0.5 day. |
| Risk Level | **Medium** | 2-repo deployment synchronization. Leave workflow (HR-1/HR-2/HR-3) may need Frappe core workflow config. |

---

## Risk Analysis

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Deployment sync (2 repos must ship together) | High | High | Deploy backend first (permissions/API), then frontend. Backend changes are backward-compatible. |
| Leave Application workflow not configurable | Medium | Medium | HR-1/HR-2/HR-3 may require Frappe core Workflow setup, not just API fixes. Test on local first. |
| Store-specific item list (SO-1) needs data | Medium | Medium | Need to define which items each store can order. Placeholder: use Item Group or custom field. |
| Denomination feature (C-2) is most complex | Low | Medium | New child DocType + new frontend component. Scope carefully -- start with simple bill count, not full denomination grid. |
| Test data seeding for DATA/CONFIG items | Low | Low | Script to create attendance, payslip, announcement, stock entries for test accounts. |

---

## Recommended Implementation Order

### Phase 1: Quick Wins (Day 1) -- 16 items
Fixes that unblock the most users with the least effort.

**Backend (parallel):**
1. Fix BEI POS Upload DocType permissions (add Employee role) -- P-1
2. Fix BEI Kudos DocType permissions (add write) + align categories -- COM-1
3. Fix BEI Store Visit Report permissions (add Area Supervisor) -- SUP-8
4. Fix Coverage Request default status to "Open" -- HR-9
5. Fix FQI naming_series if needed -- FQ-3
6. Add `deposit_type` field to BEI Bank Deposit DocType -- D-1
7. Add negative qty validation to cycle count API -- CC-3

**Frontend (parallel):**
8. Fix handover store resolution for non-supervisor users -- H-1, H-2
9. Fix deposit date to single date input -- D-2
10. Cap deposit photos to 4 max -- D-3
11. Add POS date validation warning display -- P-2
12. Add confirmation dialog for ordering -- SO-4
13. Display UOM column in ordering list -- SO-2
14. Add date picker to cycle count header -- CC-2
15. Add resubmit button for rejected cycle counts -- CC-4
16. Add `min="0"` on cycle count quantity inputs -- CC-3 (frontend half)

### Phase 2: Dropdown Conversions (Day 2) -- 8 items
All text-to-dropdown conversions use the same pattern (employee combobox or store Select).

17. FQI item name dropdown + "Other" conditional input -- FQ-1, FQ-2
18. Coverage Request store dropdown -- HR-7
19. Coverage Request employee dropdown -- HR-8
20. Kudos employee dropdown -- COM-2
21. Labor Plan store dropdown -- SUP-4
22. Schedule shifts restricted to 7 predefined -- HR-5

### Phase 3: Navigation & Config (Day 2-3) -- 8 items
Link existing pages, seed test data, fix store scope filtering.

23. Link Variance Report to inventory nav -- IV-1
24. Link Shelf Life Check to inventory nav -- IV-2
25. Link Enrichment Tracker to supervisor nav -- SUP-6
26. Link Store Dashboard to supervisor nav -- SUP-7
27. Fix completeness tracker store filtering -- SUP-5
28. Seed test data: announcements, attendance, payslips, stock -- COM-5, HR-4, HR-6, IV-3, IV-4
29. Configure `custom_area_supervisor` on test warehouses -- AS-1, AS-2
30. Fix SUP-1 queue: ensure orders create Approval Queue entries

### Phase 4: Complex Features (Day 3-4) -- 6 items
Larger scope items requiring new components or data modeling.

31. Denomination breakdown for closing report (C-2, C-3)
32. Store-specific item list filtering for ordering (SO-1)
33. Sort items by most-ordered frequency (SO-3)
34. Ordering RBAC: Staff submits, Area Supervisor approves (SO-5, SO-6)
35. Profile submission error fix (PR-1)
36. Help & Support ticket creation fix (COM-4)

### Phase 5: Leave Workflow (Day 4-5) -- 4 items
Requires careful Frappe Leave Application workflow configuration.

37. Fix leave visibility in supervisor account (HR-1)
38. Fix leave approval status reflection (HR-2, HR-3)
39. Fix supervisor leave approval queue (SUP-2)
40. Verify reports feed populates after report submission (SUP-3)

---

## Dependencies Between Items

```
H-1 → H-2 (same root cause)
HR-2 → HR-3 (same root cause)
HR-2 → SUP-2 (same root cause)
SO-5 → SO-6 (RBAC change affects both)
AS-1 → AS-2 (same config change)
COM-1 depends on DocType permission fix + category alignment
Phase 4 depends on Phase 1 (permissions must be deployed first)
Phase 5 (leave workflow) is independent of all other phases
SUP-1 depends on ordering being functional (SO-5/SO-6)
SUP-3 depends on reports being submittable (already fixed items)
IV-3 depends on test stock seeding
IV-4 depends on test trip data seeding
```

---

## Related Specs

| Spec | Relevance | mayNeedUpdate |
|------|-----------|---------------|
| `commissary-completion-testing` | Low -- different module (commissary vs store ops). Shared warehouse resolution pattern. | No |
| `procurement-bugfix` | Low -- different module (procurement). No shared components. | No |

---

## Quality Commands

| Type | Command | Source |
|------|---------|--------|
| Lint (bei-tasks) | `cd F:\Dropbox\Projects\bei-tasks && npx eslint` | bei-tasks package.json scripts.lint |
| Build (bei-tasks) | `cd F:\Dropbox\Projects\bei-tasks && npm run build` | bei-tasks package.json scripts.build |
| Build (BEI-ERP) | `cd F:\Dropbox\Projects\BEI-ERP && yarn build` | BEI-ERP package.json scripts.build |
| TypeCheck | Not found | N/A |
| Unit Test (Frappe) | `bench --site hq.bebang.ph run-tests --module hrms.api.store` | Frappe convention |
| E2E Test | `/test-full-cycle` | Claude skill |
| Local Frappe Dev | `/local-frappe` | Claude skill |

**Local CI**: `cd bei-tasks && npm run lint && npm run build`

---

## External Research

### QSR Store Operations App Best Practices

- **Standardized digital checklists** ensure all shifts complete required tasks. Align with BEI's opening/midshift/closing pattern. (Source: [SafetyCulture](https://safetyculture.com/apps/qsr-management-software))
- **Real-time issue reporting** -- staff flag problems during inspections rather than waiting for manual reviews. Maps to FQI and maintenance request flows.
- **Mobile-first design** -- all QSR management software expects phone-first usage. BEI's approach (React PWA + Shadcn) is correct.
- **Role-based task assignment** -- QSR apps differentiate crew, shift lead, store manager, area manager. BEI has Store Staff, Store Supervisor, Area Supervisor. (Source: [KNOW App](https://www.getknowapp.com/blog/quick-service-restaurant-operations/))
- **Unified commerce** -- 2026 trend is integrating all touchpoints (POS, inventory, ordering, reporting) into one platform. BEI's my.bebang.ph approach is aligned. (Source: [QSR Magazine](https://www.qsrmagazine.com/story/restaurant-trends-for-2026-hospitality-reenters-the-innovation-cycle/))

### Dropdown/Combobox Patterns

- **Employee search combobox**: Use `frappe.client.get_list("Employee", filters, fields, limit)` with debounced search. Return `name` (ID) + `employee_name` for display.
- **Store/warehouse selector**: Fetch from `/api/method/frappe.client.get_list` with doctype=Warehouse, filtered by company.
- **Item selector**: Same pattern, doctype=Item, filtered by `is_stock_item=1`.

### Denomination Breakdown Patterns

- Philippine banknotes: 1000, 500, 200, 100, 50, 20
- Coins: 10, 5, 1, 0.25
- Standard denomination form: rows per denomination, columns for count + subtotal
- Total auto-calculates from count * denomination value

---

## Open Questions

1. **SO-1 (Store-specific items)**: How should store item lists be defined? Options:
   - (a) Custom field `allowed_stores` on Item with multi-select of warehouses
   - (b) Separate "Store Item List" DocType linking stores to items
   - (c) Use Item Group filtering (all stores in same group get same items)
   -- **Recommendation**: Option (a) is simplest for now.

2. **HR-5 (7 predefined shifts)**: What are the exact 7 shifts? Need names and time ranges.
   -- Can be seeded into BEI Shift Template DocType.

3. **C-2 (Denomination)**: Should denomination be per-fund (separate for PCF, Delivery Fund, Change Fund) or a single combined denomination count?
   -- Ops training guide implies per-fund denomination.

4. **SO-6 (Area Supervisor approval)**: The backend already checks Area Supervisor role in `approve_order()`. Is the issue that orders are NOT being routed to Area Supervisor in the approval queue?

5. **PR-1 (Profile error)**: Need to reproduce the exact error. Could be duplicate pending edit request, or field validation failure.

---

## Sources

### Internal Files
- `F:\Dropbox\Projects\BEI-ERP\docs\plans\STORE_OPS_EMERGENCY_FIX_PLAN_2026-02-07.md`
- `F:\Dropbox\Projects\BEI-ERP\docs\plans\STORE_OPS_AUDIT_REPORT_2026-02-07.md`
- `F:\Dropbox\Projects\BEI-ERP\docs\MY_BEBANG_PH_COMPLETE_REFERENCE.md`
- `F:\Dropbox\Projects\BEI-ERP\hrms\api\store.py`
- `F:\Dropbox\Projects\BEI-ERP\hrms\api\communication.py`
- `F:\Dropbox\Projects\BEI-ERP\hrms\api\inventory.py`
- `F:\Dropbox\Projects\BEI-ERP\hrms\api\supervisor.py`
- `F:\Dropbox\Projects\BEI-ERP\hrms\api\coverage.py`
- `F:\Dropbox\Projects\BEI-ERP\hrms\api\dashboard.py`
- `F:\Dropbox\Projects\bei-tasks\lib\roles.ts`
- `F:\Dropbox\Projects\bei-tasks\app\dashboard\store-ops\handover\page.tsx`
- `F:\Dropbox\Projects\bei-tasks\app\dashboard\store-ops\deposit\page.tsx`
- `F:\Dropbox\Projects\bei-tasks\app\dashboard\store-ops\pos\page.tsx`
- `F:\Dropbox\Projects\bei-tasks\app\dashboard\inventory\ordering\page.tsx`
- `F:\Dropbox\Projects\bei-tasks\app\dashboard\communication\kudos\page.tsx`

### External Sources
- [SafetyCulture QSR Management Software](https://safetyculture.com/apps/qsr-management-software)
- [KNOW App - QSR Operations Best Practices 2025](https://www.getknowapp.com/blog/quick-service-restaurant-operations/)
- [QSR Magazine - 2026 Restaurant Trends](https://www.qsrmagazine.com/story/restaurant-trends-for-2026-hospitality-reenters-the-innovation-cycle/)
- [QSR Magazine - 2026 Top Priorities](https://www.qsrmagazine.com/sponsored_content/2026-top-priorities-for-restaurant-operators/)
- [Ordering Stack - QSR Technology Trends 2026](https://orderingstack.com/blog/top-5-technologies-for-qsr-chains-that-facilitate-business-operations-and-help-stand-out-in-the-market)
