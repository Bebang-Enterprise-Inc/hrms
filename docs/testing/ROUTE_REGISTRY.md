# Route Registry: my.bebang.ph

**Purpose:** Single source of truth for all mapped feature routes, test roles, and API endpoints.
**Last Updated:** 2026-02-26
**Source:** `docs/plans/system-flow-gaps-v3-full-route-map.md` (row-level sync)

- Total mapped routes/pages/features: **169**
- Rows with explicit API endpoint mapping: **56**
- Rows without explicit API endpoint mapping: **113**
- Registry status carried from source map (yes/no): **169 / 0**

Agents MUST consult this registry instead of guessing URLs.

## Home & Profile

| Feature | Route | Test Role | API Endpoint | Flow | Coverage | Registry |
|---------|-------|-----------|--------------|------|----------|----------|
| Dashboard | `/dashboard` | (not mapped) | - | module-level | module-level (map assertions per route) | yes |
| My Profile | `/dashboard/my-profile` | (not mapped) | - | module-level | module-level (map assertions per route) | yes |
| Login | `/login` | (not mapped) | - | module-level | module-level (map assertions per route) | yes |

## HR Self-Service

| Feature | Route | Test Role | API Endpoint | Flow | Coverage | Registry |
|---------|-------|-----------|--------------|------|----------|----------|
| OB Check-in (Geo) | `/dashboard/attendance/ob-checkin` | (not mapped) | - | module-level | module-level (map assertions per route) | yes |
| OB Check-out (Geo) | `/dashboard/attendance/ob-checkout` | (not mapped) | - | module-level | module-level (map assertions per route) | yes |
| Remote Punch | `/dashboard/attendance/punch` | test.crew1 | `hrms.api.shift_tracking.punch_in` | module-level | module-level (map assertions per route) | yes |
| Punch In | `/dashboard/attendance/punch-in` | (not mapped) | - | module-level | module-level (map assertions per route) | yes |
| Punch Out | `/dashboard/attendance/punch-out` | (not mapped) | - | module-level | module-level (map assertions per route) | yes |
| Punch Review | `/dashboard/attendance/punch/review` | test.supervisor | `hrms.api.shift_tracking.get_pending_reviews` | module-level | module-level (map assertions per route) | yes |
| HR Landing | `/dashboard/hr` | test.crew1 | - | module-level | module-level (map assertions per route) | yes |
| Attendance | `/dashboard/hr/attendance` | test.crew1 | `hrms.api.get_attendance` | module-level | module-level (map assertions per route) | yes |
| Attendance Correction | `/dashboard/hr/attendance-correction` | (not mapped) | - | module-level | module-level (map assertions per route) | yes |
| Correction Review | `/dashboard/hr/attendance-correction/review` | (not mapped) | - | module-level | module-level (map assertions per route) | yes |
| Coverage Request | `/dashboard/hr/coverage` | test.crew1 | `hrms.api.coverage.submit_coverage_request` | module-level | module-level (map assertions per route) | yes |
| Disciplinary | `/dashboard/hr/disciplinary` | (not mapped) | - | module-level | module-level (map assertions per route) | yes |
| Disciplinary Detail | `/dashboard/hr/disciplinary/[id]` | (not mapped) | - | module-level | module-level (map assertions per route) | yes |
| Enrichment Tracker | `/dashboard/hr/enrichment-tracker` | (not mapped) | - | module-level | module-level (map assertions per route) | yes |
| Leave | `/dashboard/hr/leave` | test.crew1 | `hrms.api.submit_leave_application` | module-level | module-level (map assertions per route) | yes |
| Leave Management | `/dashboard/hr/leave` | test.crew1 | `hrms.api.submit_leave_application` | module-level | module-level (map assertions per route) | yes |
| Official Business | `/dashboard/hr/official-business` | test.crew1 | `hrms.api.official_business.create_ob` | module-level | module-level (map assertions per route) | yes |
| OB Check-in | `/dashboard/hr/official-business/checkin` | (not mapped) | - | module-level | module-level (map assertions per route) | yes |
| OB Check-out | `/dashboard/hr/official-business/checkout` | (not mapped) | - | module-level | module-level (map assertions per route) | yes |
| Payroll | `/dashboard/hr/payroll` | (not mapped) | - | module-level | module-level (map assertions per route) | yes |
| Payslip | `/dashboard/hr/payslip` | test.crew1 | `hrms.api.payroll.get_salary_slips` | module-level | module-level (map assertions per route) | yes |
| Performance | `/dashboard/hr/performance` | (not mapped) | - | module-level | module-level (map assertions per route) | yes |
| Performance Detail | `/dashboard/hr/performance/[id]` | (not mapped) | - | module-level | module-level (map assertions per route) | yes |
| Regularization | `/dashboard/hr/performance/regularization` | (not mapped) | - | module-level | module-level (map assertions per route) | yes |
| Reports | `/dashboard/hr/reports` | (not mapped) | - | module-level | module-level (map assertions per route) | yes |
| Report Detail | `/dashboard/hr/reports/[reportId]` | (not mapped) | - | module-level | module-level (map assertions per route) | yes |
| Schedule | `/dashboard/hr/schedule` | test.crew1 | `hrms.api.roster.get_my_schedule` | module-level | module-level (map assertions per route) | yes |
| Training | `/dashboard/hr/training` | (not mapped) | - | module-level | module-level (map assertions per route) | yes |
| Transfers | `/dashboard/hr/transfers` | test.supervisor | `hrms.api.transfer_requests.list_transfer_requests` | module-level | module-level (map assertions per route) | yes |
| Create Transfer Request | `/dashboard/hr/transfers` | test.supervisor | `hrms.api.transfer_requests.create_transfer_request` | module-level | module-level (map assertions per route) | yes |
| Transfer Form Options | `/dashboard/hr/transfers` | test.supervisor | `hrms.api.transfer_requests.get_transfer_form_options` | module-level | module-level (map assertions per route) | yes |
| Transfer Stage Approval | `/dashboard/hr/transfers` | test.area | `hrms.api.transfer_requests.approve_transfer_stage` | module-level | module-level (map assertions per route) | yes |
| Leave Command Center | `/hr-admin/leaves` | (not mapped) | - | module-level | module-level (map assertions per route) | yes |

## Expenses

| Feature | Route | Test Role | API Endpoint | Flow | Coverage | Registry |
|---------|-------|-----------|--------------|------|----------|----------|
| My Expenses | `/dashboard/expense` | test.crew1 | `hrms.api.expense.get_my_expenses` | module-level | module-level (map assertions per route) | yes |
| Expense Detail | `/dashboard/expense/[id]` | (not mapped) | - | module-level | module-level (map assertions per route) | yes |
| PCF Dashboard | `/dashboard/expense/pcf` | test.supervisor | `hrms.api.pcf.get_pcf_dashboard` | module-level | module-level (map assertions per route) | yes |
| Add PCF Entry | `/dashboard/expense/pcf/add` | (not mapped) | - | module-level | module-level (map assertions per route) | yes |
| PCF History | `/dashboard/expense/pcf/history` | (not mapped) | - | module-level | module-level (map assertions per route) | yes |
| PCF History Detail | `/dashboard/expense/pcf/history/[id]` | (not mapped) | - | module-level | module-level (map assertions per route) | yes |
| Pending PCF | `/dashboard/expense/pcf/pending` | (not mapped) | - | module-level | module-level (map assertions per route) | yes |
| Edit Pending PCF | `/dashboard/expense/pcf/pending/[id]/edit` | (not mapped) | - | module-level | module-level (map assertions per route) | yes |
| Submit Expense | `/dashboard/expense/submit` | test.crew1 | `hrms.api.expense.submit_expense` | module-level | module-level (map assertions per route) | yes |

## Store Operations

| Feature | Route | Test Role | API Endpoint | Flow | Coverage | Registry |
|---------|-------|-----------|--------------|------|----------|----------|
| Maintenance Queue | `/dashboard/maintenance` | (not mapped) | - | module-level | module-level (map assertions per route) | yes |
| My R&M Requests | `/dashboard/rm` | test.crew1 | `hrms.api.projects.get_my_requests` | module-level | module-level (map assertions per route) | yes |
| R&M Dashboard | `/dashboard/rm-admin` | test.projects | `hrms.api.projects.get_maintenance_dashboard` | module-level | module-level (map assertions per route) | yes |
| Pending Charges | `/dashboard/rm-admin/charges` | test.projects | `hrms.api.projects.get_pending_charges` | module-level | module-level (map assertions per route) | yes |
| R&M Job Queue | `/dashboard/rm-admin/queue` | test.projects | `hrms.api.projects.get_maintenance_queue` | module-level | module-level (map assertions per route) | yes |
| Maintenance Request | `/dashboard/rm/new` | test.crew1 | `hrms.api.projects.create_maintenance_request` | module-level | module-level (map assertions per route) | yes |
| Store Ops Landing | `/dashboard/store-ops` | test.crew1 | - | module-level | module-level (map assertions per route) | yes |
| Closing Report | `/dashboard/store-ops/closing` | test.crew1 | `hrms.api.store.submit_closing_report` | module-level | module-level (map assertions per route) | yes |
| Bank Deposit | `/dashboard/store-ops/deposit` | test.crew1 | `hrms.api.store.submit_bank_deposit` | module-level | module-level (map assertions per route) | yes |
| Cashier Handover | `/dashboard/store-ops/handover` | test.crew1 | `hrms.api.store.submit_handover_report` | module-level | module-level (map assertions per route) | yes |
| Maintenance (legacy) | `/dashboard/store-ops/maintenance` | (not mapped) | - | module-level | module-level (map assertions per route) | yes |
| Mid-Shift Check | `/dashboard/store-ops/midshift` | test.crew1 | `hrms.api.store.submit_midshift_report` | module-level | module-level (map assertions per route) | yes |
| Opening Report | `/dashboard/store-ops/opening` | test.crew1 | `hrms.api.store.submit_opening_report` | module-level | module-level (map assertions per route) | yes |
| POS Upload | `/dashboard/store-ops/pos` | test.crew1 | `hrms.api.store.submit_pos_report` | module-level | module-level (map assertions per route) | yes |

## Inventory

| Feature | Route | Test Role | API Endpoint | Flow | Coverage | Registry |
|---------|-------|-----------|--------------|------|----------|----------|
| Inventory Landing | `/dashboard/inventory` | test.crew1 | `hrms.api.inventory.submit_cycle_count` | dispatch-warehouse-commissary | ready | yes |
| Cycle Counts | `/dashboard/inventory/counts` | (not mapped) | - | dispatch-warehouse-commissary | ready | yes |
| Store Ordering | `/dashboard/inventory/ordering` | test.crew1 | `hrms.api.inventory.submit_store_order` | dispatch-warehouse-commissary | ready | yes |
| Returns | `/dashboard/inventory/returns` | test.crew1 | `hrms.api.inventory.submit_return` | dispatch-warehouse-commissary | ready | yes |
| Shelf Life | `/dashboard/inventory/shelf-life` | test.crew1 | `hrms.api.inventory.submit_shelf_life_check` | dispatch-warehouse-commissary | ready | yes |
| Variances | `/dashboard/inventory/variances` | test.crew1 | `hrms.api.inventory.submit_variance_report` | dispatch-warehouse-commissary | ready | yes |
| Stock Count List | `/inventory/stock-counts` | test.staff | `hrms.api.inventory.get_cycle_counts` | dispatch-warehouse-commissary | ready | yes |
| Count Detail | `/inventory/stock-counts/[id]` | test.staff | `hrms.api.inventory.get_cycle_count` | dispatch-warehouse-commissary | ready | yes |
| New Count Form | `/inventory/stock-counts/new` | test.staff | `hrms.api.inventory.submit_cycle_count_v2` | dispatch-warehouse-commissary | ready | yes |

## Receiving

| Feature | Route | Test Role | API Endpoint | Flow | Coverage | Registry |
|---------|-------|-----------|--------------|------|----------|----------|
| My Delivery | `/dashboard/my-delivery` | (not mapped) | - | dispatch-warehouse-commissary | ready | yes |
| Store Receiving | `/dashboard/receiving` | test.crew1 | `hrms.api.store.submit_receiving_report` | dispatch-warehouse-commissary | ready | yes |
| My Deliveries | `/dashboard/receiving/dispatch` | (not mapped) | - | dispatch-warehouse-commissary | ready | yes |
| FQI Report | `/dashboard/receiving/fqi` | test.crew1 | `hrms.api.store.submit_fqi_report` | dispatch-warehouse-commissary | ready | yes |

## Supervisor Tools

| Feature | Route | Test Role | API Endpoint | Flow | Coverage | Registry |
|---------|-------|-----------|--------------|------|----------|----------|
| Completeness | `/dashboard/completeness` | (not mapped) | - | module-level | module-level (map assertions per route) | yes |
| Verify Data | `/dashboard/enrichment` | (not mapped) | - | module-level | module-level (map assertions per route) | yes |
| Approval Queue | `/dashboard/queue` | test.supervisor | `hrms.api.supervisor.get_approval_queue` | module-level | module-level (map assertions per route) | yes |
| Labor Plan | `/dashboard/supervisor/labor-plan` | test.supervisor | `hrms.api.supervisor.get_labor_plan` | module-level | module-level (map assertions per route) | yes |
| Reports Feed | `/dashboard/supervisor/reports-feed` | test.supervisor | `hrms.api.supervisor.get_reports_feed` | module-level | module-level (map assertions per route) | yes |
| My Team | `/dashboard/team` | test.supervisor | `hrms.api.supervisor.get_team_members` | module-level | module-level (map assertions per route) | yes |
| Store Visits | `/dashboard/team/visits` | (not mapped) | - | module-level | module-level (map assertions per route) | yes |

## Finance & Accounting (HQ User only)

| Feature | Route | Test Role | API Endpoint | Flow | Coverage | Registry |
|---------|-------|-----------|--------------|------|----------|----------|
| Accounting Dashboard | `/dashboard/accounting` | (no test account) | `hrms.api.expense_review.get_review_dashboard` | procure-to-pay | ready | yes |
| Awaiting OR | `/dashboard/accounting/awaiting-or` | (not mapped) | - | procure-to-pay | ready | yes |
| Exception Approvals | `/dashboard/accounting/exceptions` | (not mapped) | - | procure-to-pay | ready | yes |
| Expense Review | `/dashboard/accounting/expenses` | (no test account) | `hrms.api.expense_review.get_pending_expenses` | procure-to-pay | ready | yes |
| Expense Detail | `/dashboard/accounting/expenses/[id]` | (not mapped) | - | procure-to-pay | ready | yes |
| Batch Approval | `/dashboard/accounting/expenses/batch` | (not mapped) | - | procure-to-pay | ready | yes |
| Expense Review Detail | `/dashboard/accounting/expenses/review` | (not mapped) | - | procure-to-pay | ready | yes |
| Outstanding Advances | `/dashboard/accounting/outstanding-advances` | (not mapped) | - | procure-to-pay | ready | yes |
| Billing | `/dashboard/billing` | (not mapped) | - | procure-to-pay | ready | yes |
| Billing Approval | `/dashboard/billing/approval` | (not mapped) | - | procure-to-pay | ready | yes |
| Delivery Rates | `/dashboard/billing/rates` | (not mapped) | - | procure-to-pay | ready | yes |

## Procurement (HQ User only)

| Feature | Route | Test Role | API Endpoint | Flow | Coverage | Registry |
|---------|-------|-----------|--------------|------|----------|----------|
| Dashboard | `/dashboard/procurement` | (no test account) | `hrms.api.procurement.get_procurement_dashboard` | procure-to-pay | ready | yes |
| Approvals | `/dashboard/procurement/approvals` | (not mapped) | - | procure-to-pay | ready | yes |
| PO Aging | `/dashboard/procurement/audit/aging` | (not mapped) | - | procure-to-pay | ready | yes |
| Price History | `/dashboard/procurement/audit/price-history` | (not mapped) | - | procure-to-pay | ready | yes |
| Goods Receipts | `/dashboard/procurement/goods-receipts` | (not mapped) | - | procure-to-pay | ready | yes |
| GR Detail | `/dashboard/procurement/goods-receipts/[id]` | (not mapped) | - | procure-to-pay | ready | yes |
| New GR | `/dashboard/procurement/goods-receipts/new` | (not mapped) | - | procure-to-pay | ready | yes |
| Invoices | `/dashboard/procurement/invoices` | (no test account) | `hrms.api.procurement.get_invoices` | procure-to-pay | ready | yes |
| Invoices | `/dashboard/procurement/invoices` | (no test account) | `hrms.api.procurement.get_invoices` | procure-to-pay | ready | yes |
| Invoice Detail | `/dashboard/procurement/invoices/[id]` | (not mapped) | - | procure-to-pay | ready | yes |
| New Invoice | `/dashboard/procurement/invoices/new` | (not mapped) | - | procure-to-pay | ready | yes |
| OR Follow-Up | `/dashboard/procurement/or-follow-up` | (not mapped) | - | procure-to-pay | ready | yes |
| Payment Requests | `/dashboard/procurement/payments` | (not mapped) | - | procure-to-pay | ready | yes |
| Payment Requests | `/dashboard/procurement/payments` | (not mapped) | - | procure-to-pay | ready | yes |
| Payment Detail | `/dashboard/procurement/payments/[id]` | (not mapped) | - | procure-to-pay | ready | yes |
| New Payment | `/dashboard/procurement/payments/new` | (not mapped) | - | procure-to-pay | ready | yes |
| Purchase Orders | `/dashboard/procurement/purchase-orders` | (no test account) | `hrms.api.procurement.get_purchase_orders` | procure-to-pay | ready | yes |
| PO Detail | `/dashboard/procurement/purchase-orders/[id]` | (not mapped) | - | procure-to-pay | ready | yes |
| New PO | `/dashboard/procurement/purchase-orders/new` | (not mapped) | - | procure-to-pay | ready | yes |
| Purchase Requisitions | `/dashboard/procurement/purchase-requisitions` | (not mapped) | - | procure-to-pay | ready | yes |
| PR Detail | `/dashboard/procurement/purchase-requisitions/[id]` | (not mapped) | - | procure-to-pay | ready | yes |
| New PR | `/dashboard/procurement/purchase-requisitions/new` | (not mapped) | - | procure-to-pay | ready | yes |
| AP Reports | `/dashboard/procurement/reports` | (not mapped) | - | procure-to-pay | ready | yes |
| Reports | `/dashboard/procurement/reports` | (not mapped) | - | procure-to-pay | ready | yes |
| Settings | `/dashboard/procurement/settings` | (not mapped) | - | procure-to-pay | ready | yes |
| Suppliers | `/dashboard/procurement/suppliers` | (no test account) | `hrms.api.procurement.get_suppliers` | procure-to-pay | ready | yes |
| Supplier Detail | `/dashboard/procurement/suppliers/[id]` | (not mapped) | - | procure-to-pay | ready | yes |
| Edit Supplier | `/dashboard/procurement/suppliers/[id]/edit` | (not mapped) | - | procure-to-pay | ready | yes |
| New Supplier | `/dashboard/procurement/suppliers/new` | (not mapped) | - | procure-to-pay | ready | yes |

## Warehouse

| Feature | Route | Test Role | API Endpoint | Flow | Coverage | Registry |
|---------|-------|-----------|--------------|------|----------|----------|
| Dashboard | `/dashboard/warehouse` | test.warehouse | `hrms.api.warehouse.get_warehouse_dashboard` | dispatch-warehouse-commissary | ready | yes |
| Approve Orders | `/dashboard/warehouse/approve` | test.warehouse | `hrms.api.warehouse.get_pending_material_requests` | dispatch-warehouse-commissary | ready | yes |
| Order Detail | `/dashboard/warehouse/approve/[mr_name]` | (not mapped) | - | dispatch-warehouse-commissary | ready | yes |
| Billing | `/dashboard/warehouse/billing` | (not mapped) | - | dispatch-warehouse-commissary | ready | yes |
| Dispatch | `/dashboard/warehouse/dispatch` | test.warehouse | `hrms.api.warehouse.get_ready_for_dispatch` | dispatch-warehouse-commissary | ready | yes |
| Drivers | `/dashboard/warehouse/drivers` | (not mapped) | - | dispatch-warehouse-commissary | ready | yes |
| Inventory | `/dashboard/warehouse/inventory` | (not mapped) | - | dispatch-warehouse-commissary | ready | yes |
| Orders | `/dashboard/warehouse/orders` | (not mapped) | - | dispatch-warehouse-commissary | ready | yes |
| Picking | `/dashboard/warehouse/picking` | (not mapped) | - | dispatch-warehouse-commissary | ready | yes |
| Receive POs | `/dashboard/warehouse/receive` | test.warehouse | `hrms.api.warehouse.get_pending_purchase_orders` | dispatch-warehouse-commissary | ready | yes |
| PO Receive Detail | `/dashboard/warehouse/receive/[po_name]` | (not mapped) | - | dispatch-warehouse-commissary | ready | yes |
| Routes | `/dashboard/warehouse/routes` | (not mapped) | - | dispatch-warehouse-commissary | ready | yes |
| Route Detail | `/dashboard/warehouse/routes/[id]` | (not mapped) | - | dispatch-warehouse-commissary | ready | yes |
| Trips List | `/dashboard/warehouse/trips` | (not mapped) | - | dispatch-warehouse-commissary | ready | yes |
| Create Trip | `/dashboard/warehouse/trips/create` | (not mapped) | - | dispatch-warehouse-commissary | ready | yes |

## Commissary

| Feature | Route | Test Role | API Endpoint | Flow | Coverage | Registry |
|---------|-------|-----------|--------------|------|----------|----------|
| Dashboard | `/dashboard/commissary` | test.commissary | `hrms.api.commissary.get_dashboard` | dispatch-warehouse-commissary | ready | yes |
| Expiring Items | `/dashboard/commissary/expiring` | (not mapped) | - | dispatch-warehouse-commissary | ready | yes |
| Fulfillment | `/dashboard/commissary/fulfillment` | test.commissary | `hrms.api.commissary.get_fulfillment_orders` | dispatch-warehouse-commissary | ready | yes |
| Inventory | `/dashboard/commissary/inventory` | test.commissary | `hrms.api.commissary.get_finished_goods` | dispatch-warehouse-commissary | ready | yes |
| Production | `/dashboard/commissary/production` | test.commissary | `hrms.api.commissary.get_production_runs` | dispatch-warehouse-commissary | ready | yes |
| Quality | `/dashboard/commissary/quality` | (not mapped) | - | dispatch-warehouse-commissary | ready | yes |
| Raw Materials | `/dashboard/commissary/raw-materials` | (not mapped) | - | dispatch-warehouse-commissary | ready | yes |
| Transfer | `/dashboard/commissary/transfer` | (not mapped) | - | dispatch-warehouse-commissary | ready | yes |
| Wastage | `/dashboard/commissary/wastage` | (not mapped) | - | dispatch-warehouse-commissary | ready | yes |
| Wastage Trends | `/dashboard/commissary/wastage-trends` | (not mapped) | - | dispatch-warehouse-commissary | ready | yes |
| Work Orders | `/dashboard/commissary/work-orders` | (not mapped) | - | dispatch-warehouse-commissary | ready | yes |

## Tasks & Projects

| Feature | Route | Test Role | API Endpoint | Flow | Coverage | Registry |
|---------|-------|-----------|--------------|------|----------|----------|
| Projects | `/dashboard/projects` | (not mapped) | - | module-level | module-level (map assertions per route) | yes |
| Project Kanban | `/dashboard/projects-mgmt` | (not mapped) | - | module-level | module-level (map assertions per route) | yes |
| Project Detail | `/dashboard/projects-mgmt/[id]` | (not mapped) | - | module-level | module-level (map assertions per route) | yes |
| New Project | `/dashboard/projects-mgmt/new` | (not mapped) | - | module-level | module-level (map assertions per route) | yes |
| Project Detail | `/dashboard/projects/[projectId]` | (not mapped) | - | module-level | module-level (map assertions per route) | yes |
| Task Reports | `/dashboard/reports/tasks` | (not mapped) | - | module-level | module-level (map assertions per route) | yes |
| My Tasks | `/dashboard/tasks` | (not mapped) | - | module-level | module-level (map assertions per route) | yes |
| Calendar | `/dashboard/tasks/calendar` | (not mapped) | - | module-level | module-level (map assertions per route) | yes |
| Gantt Chart | `/dashboard/tasks/gantt` | (not mapped) | - | module-level | module-level (map assertions per route) | yes |
| Kanban Board | `/dashboard/tasks/kanban` | (not mapped) | - | module-level | module-level (map assertions per route) | yes |
| Tree View | `/dashboard/tasks/tree` | (not mapped) | - | module-level | module-level (map assertions per route) | yes |
| Templates | `/dashboard/templates` | (not mapped) | - | module-level | module-level (map assertions per route) | yes |

## Analytics

| Feature | Route | Test Role | API Endpoint | Flow | Coverage | Registry |
|---------|-------|-----------|--------------|------|----------|----------|
| Analytics Landing | `/dashboard/analytics` | (not mapped) | - | module-level | module-level (map assertions per route) | yes |
| Area Dashboard | `/dashboard/analytics/area` | (not mapped) | - | module-level | module-level (map assertions per route) | yes |
| Store Dashboard | `/dashboard/analytics/store` | (not mapped) | - | module-level | module-level (map assertions per route) | yes |

## Communication

| Feature | Route | Test Role | API Endpoint | Flow | Coverage | Registry |
|---------|-------|-----------|--------------|------|----------|----------|
| Kudos | `/dashboard/communication` | test.crew1 | `hrms.api.communication.send_kudos` | module-level | module-level (map assertions per route) | yes |
| Announcements | `/dashboard/communication/announcements` | test.crew1 | `hrms.api.communication.get_announcements` | module-level | module-level (map assertions per route) | yes |
| Complaint to CEO | `/dashboard/communication/complaint` | test.crew1 | `hrms.api.communication.submit_complaint` | module-level | module-level (map assertions per route) | yes |
| Support | `/dashboard/communication/support` | test.crew1 | `hrms.api.communication.create_support_ticket` | module-level | module-level (map assertions per route) | yes |

## Employee Clearance

| Feature | Route | Test Role | API Endpoint | Flow | Coverage | Registry |
|---------|-------|-----------|--------------|------|----------|----------|
| Clearance | `/clearance` | (not mapped) | - | hire-to-onboard | ready | yes |
| Exit Interview | `/clearance/exit-interview` | (not mapped) | - | hire-to-onboard | ready | yes |

## Recruitment

| Feature | Route | Test Role | API Endpoint | Flow | Coverage | Registry |
|---------|-------|-----------|--------------|------|----------|----------|
| Recruitment | `/dashboard/hr/recruitment` | (not mapped) | - | hire-to-onboard | ready | yes |
| MRF Create | `/dashboard/hr/recruitment/mrf` | (not mapped) | - | hire-to-onboard | ready | yes |

## Onboarding

| Feature | Route | Test Role | API Endpoint | Flow | Coverage | Registry |
|---------|-------|-----------|--------------|------|----------|----------|
| Onboarding Requests | `/dashboard/onboarding` | (not mapped) | - | hire-to-onboard | ready | yes |
| Onboarding (Me) | `/dashboard/onboarding/me` | (not mapped) | - | hire-to-onboard | ready | yes |
| Onboarding Detail | `/dashboard/onboarding/requests/[requestId]` | (not mapped) | - | hire-to-onboard | ready | yes |
| Public Onboarding | `/onboarding` | (not mapped) | - | hire-to-onboard | ready | yes |


