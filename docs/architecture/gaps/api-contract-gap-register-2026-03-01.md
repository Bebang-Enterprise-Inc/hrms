# api-contract-gap-register (2026-03-01)

## Sprint 18 Reconciliation Snapshot

- run_group_id: `20260302-s18-api-contract-backlog`
- stage_scope: `Stage 01` through `Stage 05`
- status: `reconciled-for-packet-dispatch`
- traceability_matrix: `output/agent-runs/20260302-s18-api-contract-backlog/S18_TRACEABILITY_MATRIX.md`

| issue_id | severity | category | evidence | recommendation | owner | target_stage |
|---|---|---|---|---|---|---|
| API-001 | HIGH | malformed_endpoint | app/api/accounting/form-2307/route.ts:10 | Fix method string to full path format: hrms.api.<module>.<method>. | hrms+portal | Stage 02/03 |
| API-002 | HIGH | malformed_endpoint | app/api/accounting/form-2307/route.ts:39 | Fix method string to full path format: hrms.api.<module>.<method>. | hrms+portal | Stage 02/03 |
| API-003 | HIGH | malformed_endpoint | app/api/accounting/reports/route.ts:10 | Fix method string to full path format: hrms.api.<module>.<method>. | hrms+portal | Stage 02/03 |
| API-004 | HIGH | malformed_endpoint | app/api/accounting/reports/route.ts:33 | Fix method string to full path format: hrms.api.<module>.<method>. | hrms+portal | Stage 02/03 |
| API-005 | INFO | resolved | app/api/accounting/soa/route.ts:11 | Resolved in Sprint 17 canonical mapping. See docs/architecture/contracts/s17-endpoint-contract.v1.md | hrms+portal | Stage 03 |
| API-006 | HIGH | module_drift | app/api/commissary/route.ts:86 | Remap endpoint to `hrms.api.commissary_dashboard.get_commissary_dashboard`. | hrms+portal | Stage 02/03 |
| API-007 | HIGH | module_drift | app/api/commissary/route.ts:96 | Remap endpoint to `hrms.api.commissary_dashboard.get_production_items`. | hrms+portal | Stage 02/03 |
| API-008 | HIGH | module_drift | app/api/commissary/route.ts:107 | Remap endpoint to `hrms.api.commissary_dashboard.get_production_history`. | hrms+portal | Stage 02/03 |
| API-009 | HIGH | module_drift | app/api/commissary/route.ts:327 | Remap endpoint to `hrms.api.commissary_requisition.get_rm_reorder_alerts`. | hrms+portal | Stage 02/03 |
| API-010 | HIGH | module_drift | app/api/commissary/route.ts:341 | Remap endpoint to `hrms.api.commissary_requisition.get_rm_for_requisition`. | hrms+portal | Stage 02/03 |
| API-011 | HIGH | module_drift | app/api/commissary/route.ts:356 | Remap endpoint to `hrms.api.commissary_requisition.get_my_requisitions`. | hrms+portal | Stage 02/03 |
| API-012 | HIGH | module_drift | app/api/commissary/route.ts:371 | Remap endpoint to `hrms.api.commissary_requisition.get_production_suggestions`. | hrms+portal | Stage 02/03 |
| API-013 | HIGH | module_drift | app/api/commissary/route.ts:388 | Remap endpoint to `hrms.api.commissary_requisition.get_work_orders`. | hrms+portal | Stage 02/03 |
| API-014 | HIGH | module_drift | app/api/commissary/route.ts:401 | Remap endpoint to `hrms.api.commissary_quality.get_pending_inspections`. | hrms+portal | Stage 02/03 |
| API-015 | HIGH | module_drift | app/api/commissary/route.ts:418 | Remap endpoint to `hrms.api.commissary_quality.get_inspection_history`. | hrms+portal | Stage 02/03 |
| API-016 | HIGH | module_drift | app/api/commissary/route.ts:438 | Remap endpoint to `hrms.api.commissary_quality.get_inspection_details`. | hrms+portal | Stage 02/03 |
| API-017 | HIGH | module_drift | app/api/commissary/route.ts:455 | Remap endpoint to `hrms.api.commissary_quality.get_wastage_history`. | hrms+portal | Stage 02/03 |
| API-018 | HIGH | module_drift | app/api/commissary/route.ts:469 | Remap endpoint to `hrms.api.commissary_quality.get_wastage_reasons`. | hrms+portal | Stage 02/03 |
| API-019 | HIGH | module_drift | app/api/commissary/route.ts:484 | Remap endpoint to `hrms.api.commissary_quality.get_wastage_trends`. | hrms+portal | Stage 02/03 |
| API-020 | HIGH | module_drift | app/api/commissary/route.ts:504 | Remap endpoint to `hrms.api.commissary_quality.get_fefo_picking_list`. | hrms+portal | Stage 02/03 |
| API-021 | HIGH | module_drift | app/api/commissary/route.ts:521 | Remap endpoint to `hrms.api.commissary_quality.get_expiring_batches`. | hrms+portal | Stage 02/03 |
| API-022 | HIGH | module_drift | app/api/commissary/route.ts:578 | Remap endpoint to `hrms.api.commissary_dashboard.submit_production_output`. | hrms+portal | Stage 02/03 |
| API-023 | HIGH | module_drift | app/api/commissary/route.ts:695 | Remap endpoint to `hrms.api.commissary_requisition.create_rm_requisition`. | hrms+portal | Stage 02/03 |
| API-024 | HIGH | module_drift | app/api/commissary/route.ts:719 | Remap endpoint to `hrms.api.commissary_requisition.approve_requisition`. | hrms+portal | Stage 02/03 |
| API-025 | HIGH | module_drift | app/api/commissary/route.ts:760 | Remap endpoint to `hrms.api.commissary_requisition.create_work_order`. | hrms+portal | Stage 02/03 |
| API-026 | HIGH | module_drift | app/api/commissary/route.ts:780 | Remap endpoint to `hrms.api.commissary_requisition.start_work_order`. | hrms+portal | Stage 02/03 |
| API-027 | HIGH | module_drift | app/api/commissary/route.ts:800 | Remap endpoint to `hrms.api.commissary_requisition.complete_work_order`. | hrms+portal | Stage 02/03 |
| API-028 | HIGH | module_drift | app/api/commissary/route.ts:820 | Remap endpoint to `hrms.api.commissary_quality.create_quality_inspection`. | hrms+portal | Stage 02/03 |
| API-029 | HIGH | module_drift | app/api/commissary/route.ts:846 | Remap endpoint to `hrms.api.commissary_quality.log_wastage`. | hrms+portal | Stage 02/03 |
| API-030 | INFO | resolved | app/api/hr/[...slug]/route.ts:10 | Resolved by adding hrms.api.compliance module and explicit method map. | hrms+portal | Stage 03 |
| API-031 | INFO | resolved | app/api/hr/[...slug]/route.ts:11 | Resolved by adding employee_clearance analytics endpoint. | hrms+portal | Stage 03 |
| API-032 | INFO | resolved | app/api/hr/[...slug]/route.ts:12 | Resolved by adding employee_clearance team separations endpoint. | hrms+portal | Stage 03 |
| API-033 | INFO | stale | app/api/hr/[...slug]/route.ts:13 | Classified stale: namespace reference in route inventory, backend endpoint already exists. | hrms+portal | Stage 03 |
| API-034 | INFO | stale | app/api/hr/[...slug]/route.ts:19 | Classified stale: namespace reference in route inventory, backend endpoint already exists. | hrms+portal | Stage 03 |
| API-035 | INFO | resolved | app/api/hr/[...slug]/route.ts:20 | Resolved by using explicit module path for current employee lookup. | hrms+portal | Stage 03 |
| API-036 | HIGH | malformed_endpoint | app/api/hr/compliance/route.ts:10 | Fix method string to full path format: hrms.api.<module>.<method>. | hrms+portal | Stage 02/03 |
| API-037 | HIGH | malformed_endpoint | app/api/hr/compliance/route.ts:38 | Fix method string to full path format: hrms.api.<module>.<method>. | hrms+portal | Stage 02/03 |
| API-038 | HIGH | malformed_endpoint | app/api/hr/exit-interview/route.ts:10 | Fix method string to full path format: hrms.api.<module>.<method>. | hrms+portal | Stage 02/03 |
| API-039 | HIGH | malformed_endpoint | app/api/hr/exit-interview/route.ts:39 | Fix method string to full path format: hrms.api.<module>.<method>. | hrms+portal | Stage 02/03 |
| API-040 | HIGH | malformed_endpoint | app/api/pcf/route.ts:10 | Fix method string to full path format: hrms.api.<module>.<method>. | hrms+portal | Stage 02/03 |
| API-041 | HIGH | malformed_endpoint | app/api/pcf/route.ts:47 | Fix method string to full path format: hrms.api.<module>.<method>. | hrms+portal | Stage 02/03 |
| API-042 | HIGH | malformed_endpoint | app/api/projects/my-requests/route.ts:38 | Fix method string to full path format: hrms.api.<module>.<method>. | hrms+portal | Stage 02/03 |
| API-043 | INFO | stale | app/api/supervisor/dashboard/route.ts:42 | Classified stale: library namespace reference, not a missing backend endpoint. | hrms+portal | Stage 03 |
| API-044 | INFO | stale | app/api/supervisor/pending-reports/route.ts:42 | Classified stale: library namespace reference, not a missing backend endpoint. | hrms+portal | Stage 03 |
| API-045 | HIGH | malformed_endpoint | app/dashboard/attendance/punch/page.tsx:70 | Fix method string to full path format: hrms.api.<module>.<method>. | hrms+portal | Stage 02/03 |
| API-046 | HIGH | malformed_endpoint | app/dashboard/attendance/punch/review/page.tsx:95 | Fix method string to full path format: hrms.api.<module>.<method>. | hrms+portal | Stage 02/03 |
| API-047 | HIGH | malformed_endpoint | hooks/use-compliance.ts:7 | Fix method string to full path format: hrms.api.<module>.<method>. | hrms+portal | Stage 02/03 |
| API-048 | HIGH | malformed_endpoint | hooks/use-exit-interview.ts:7 | Fix method string to full path format: hrms.api.<module>.<method>. | hrms+portal | Stage 02/03 |
| API-049 | HIGH | malformed_endpoint | hooks/use-finance-reports.ts:7 | Fix method string to full path format: hrms.api.<module>.<method>. | hrms+portal | Stage 02/03 |
| API-050 | HIGH | malformed_endpoint | hooks/use-form-2307.ts:7 | Fix method string to full path format: hrms.api.<module>.<method>. | hrms+portal | Stage 02/03 |
| API-051 | HIGH | malformed_endpoint | hooks/use-pcf.ts:7 | Fix method string to full path format: hrms.api.<module>.<method>. | hrms+portal | Stage 02/03 |
| API-052 | HIGH | malformed_endpoint | lib/clearance/api.ts:5 | Fix method string to full path format: hrms.api.<module>.<method>. | hrms+portal | Stage 02/03 |
| API-053 | HIGH | malformed_endpoint | lib/queries/hr-transfers.ts:3 | Fix method string to full path format: hrms.api.<module>.<method>. | hrms+portal | Stage 02/03 |
