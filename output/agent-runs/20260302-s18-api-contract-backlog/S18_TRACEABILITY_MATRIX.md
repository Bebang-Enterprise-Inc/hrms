# S18 Traceability Matrix

- run_group_id: `20260302-s18-api-contract-backlog`
- baseline_source: `scratchpad/e2e_map_refresh/contracts_s18/api_contract_issues.json`
- high_issue_count: `44`

| packet | issue_count | categories | representative_evidence |
|---|---:|---|---|
| p01-route-method-fixes (portal) | 11 | malformed_endpoint | `app/api/accounting/form-2307/route.ts:10`<br>`app/api/accounting/form-2307/route.ts:39` |
| p02-commissary-module-drift-remap (portal) | 24 | module_drift | `app/api/commissary/route.ts:107`<br>`app/api/commissary/route.ts:327` |
| p03-shared-library-remap (portal) | 9 | malformed_endpoint | `app/dashboard/attendance/punch/page.tsx:70`<br>`app/dashboard/attendance/punch/review/page.tsx:95` |

## Issue Inventory

| issue_id | category | endpoint | evidence | packet |
|---|---|---|---|---|
| API-001 | malformed_endpoint | `hrms.api.tax` | `app/api/accounting/form-2307/route.ts:10` | p01-route-method-fixes (portal) |
| API-002 | malformed_endpoint | `hrms.api.tax` | `app/api/accounting/form-2307/route.ts:39` | p01-route-method-fixes (portal) |
| API-003 | malformed_endpoint | `hrms.api.finance` | `app/api/accounting/reports/route.ts:10` | p01-route-method-fixes (portal) |
| API-004 | malformed_endpoint | `hrms.api.finance` | `app/api/accounting/reports/route.ts:33` | p01-route-method-fixes (portal) |
| API-029 | malformed_endpoint | `hrms.api.compliance` | `app/api/hr/compliance/route.ts:10` | p01-route-method-fixes (portal) |
| API-030 | malformed_endpoint | `hrms.api.compliance` | `app/api/hr/compliance/route.ts:38` | p01-route-method-fixes (portal) |
| API-031 | malformed_endpoint | `hrms.api.employee_clearance` | `app/api/hr/exit-interview/route.ts:10` | p01-route-method-fixes (portal) |
| API-032 | malformed_endpoint | `hrms.api.employee_clearance` | `app/api/hr/exit-interview/route.ts:39` | p01-route-method-fixes (portal) |
| API-033 | malformed_endpoint | `hrms.api.pcf` | `app/api/pcf/route.ts:10` | p01-route-method-fixes (portal) |
| API-034 | malformed_endpoint | `hrms.api.pcf` | `app/api/pcf/route.ts:47` | p01-route-method-fixes (portal) |
| API-035 | malformed_endpoint | `hrms.api.get_current_employee_info` | `app/api/projects/my-requests/route.ts:38` | p01-route-method-fixes (portal) |
| API-005 | module_drift | `hrms.api.commissary.get_commissary_dashboard` | `app/api/commissary/route.ts:86` | p02-commissary-module-drift-remap (portal) |
| API-006 | module_drift | `hrms.api.commissary.get_production_items` | `app/api/commissary/route.ts:96` | p02-commissary-module-drift-remap (portal) |
| API-007 | module_drift | `hrms.api.commissary.get_production_history` | `app/api/commissary/route.ts:107` | p02-commissary-module-drift-remap (portal) |
| API-008 | module_drift | `hrms.api.commissary.get_rm_reorder_alerts` | `app/api/commissary/route.ts:327` | p02-commissary-module-drift-remap (portal) |
| API-009 | module_drift | `hrms.api.commissary.get_rm_for_requisition` | `app/api/commissary/route.ts:341` | p02-commissary-module-drift-remap (portal) |
| API-010 | module_drift | `hrms.api.commissary.get_my_requisitions` | `app/api/commissary/route.ts:356` | p02-commissary-module-drift-remap (portal) |
| API-011 | module_drift | `hrms.api.commissary.get_production_suggestions` | `app/api/commissary/route.ts:371` | p02-commissary-module-drift-remap (portal) |
| API-012 | module_drift | `hrms.api.commissary.get_work_orders` | `app/api/commissary/route.ts:388` | p02-commissary-module-drift-remap (portal) |
| API-013 | module_drift | `hrms.api.commissary.get_pending_inspections` | `app/api/commissary/route.ts:401` | p02-commissary-module-drift-remap (portal) |
| API-014 | module_drift | `hrms.api.commissary.get_inspection_history` | `app/api/commissary/route.ts:418` | p02-commissary-module-drift-remap (portal) |
| API-015 | module_drift | `hrms.api.commissary.get_inspection_details` | `app/api/commissary/route.ts:438` | p02-commissary-module-drift-remap (portal) |
| API-016 | module_drift | `hrms.api.commissary.get_wastage_history` | `app/api/commissary/route.ts:455` | p02-commissary-module-drift-remap (portal) |
| API-017 | module_drift | `hrms.api.commissary.get_wastage_reasons` | `app/api/commissary/route.ts:469` | p02-commissary-module-drift-remap (portal) |
| API-018 | module_drift | `hrms.api.commissary.get_wastage_trends` | `app/api/commissary/route.ts:484` | p02-commissary-module-drift-remap (portal) |
| API-019 | module_drift | `hrms.api.commissary.get_fefo_picking_list` | `app/api/commissary/route.ts:504` | p02-commissary-module-drift-remap (portal) |
| API-020 | module_drift | `hrms.api.commissary.get_expiring_batches` | `app/api/commissary/route.ts:521` | p02-commissary-module-drift-remap (portal) |
| API-021 | module_drift | `hrms.api.commissary.submit_production_output` | `app/api/commissary/route.ts:578` | p02-commissary-module-drift-remap (portal) |
| API-022 | module_drift | `hrms.api.commissary.create_rm_requisition` | `app/api/commissary/route.ts:695` | p02-commissary-module-drift-remap (portal) |
| API-023 | module_drift | `hrms.api.commissary.approve_requisition` | `app/api/commissary/route.ts:719` | p02-commissary-module-drift-remap (portal) |
| API-024 | module_drift | `hrms.api.commissary.create_work_order` | `app/api/commissary/route.ts:760` | p02-commissary-module-drift-remap (portal) |
| API-025 | module_drift | `hrms.api.commissary.start_work_order` | `app/api/commissary/route.ts:780` | p02-commissary-module-drift-remap (portal) |
| API-026 | module_drift | `hrms.api.commissary.complete_work_order` | `app/api/commissary/route.ts:800` | p02-commissary-module-drift-remap (portal) |
| API-027 | module_drift | `hrms.api.commissary.create_quality_inspection` | `app/api/commissary/route.ts:820` | p02-commissary-module-drift-remap (portal) |
| API-028 | module_drift | `hrms.api.commissary.log_wastage` | `app/api/commissary/route.ts:846` | p02-commissary-module-drift-remap (portal) |
| API-036 | malformed_endpoint | `hrms.api.shift_tracking` | `app/dashboard/attendance/punch/page.tsx:70` | p03-shared-library-remap (portal) |
| API-037 | malformed_endpoint | `hrms.api.shift_tracking` | `app/dashboard/attendance/punch/review/page.tsx:95` | p03-shared-library-remap (portal) |
| API-038 | malformed_endpoint | `hrms.api.compliance` | `hooks/use-compliance.ts:7` | p03-shared-library-remap (portal) |
| API-039 | malformed_endpoint | `hrms.api.employee_clearance` | `hooks/use-exit-interview.ts:7` | p03-shared-library-remap (portal) |
| API-040 | malformed_endpoint | `hrms.api.finance` | `hooks/use-finance-reports.ts:7` | p03-shared-library-remap (portal) |
| API-041 | malformed_endpoint | `hrms.api.tax` | `hooks/use-form-2307.ts:7` | p03-shared-library-remap (portal) |
| API-042 | malformed_endpoint | `hrms.api.pcf` | `hooks/use-pcf.ts:7` | p03-shared-library-remap (portal) |
| API-043 | malformed_endpoint | `hrms.api.employee_clearance` | `lib/clearance/api.ts:5` | p03-shared-library-remap (portal) |
| API-044 | malformed_endpoint | `hrms.api.transfer_requests` | `lib/queries/hr-transfers.ts:3` | p03-shared-library-remap (portal) |
