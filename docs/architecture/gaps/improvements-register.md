# Improvements Register
**Scanned:** 2026-02-23 | **Commit:** 7b998877f
**Total Improvements: 30** — Things that work but could be significantly better

---

| ID | Department | Feature | Current State | Improvement | Benefit | Priority |
|----|-----------|---------|--------------|-------------|---------|----------|
| IMP-001 | Store Ops | Opening/closing checklists | Hardcoded in page.tsx arrays | Move to DocType or BEI Settings child table | Ops team can update without code deployment | HIGH |
| IMP-002 | Inventory | Blind count item loading | Loads ALL stock items per call | Add pagination/batch loading by item_group | Prevents timeout on large item masters | HIGH |
| IMP-003 | Inventory | Returns recipient warehouse | submit_return_request creates Material Issue with no destination | Use commissary warehouse as destination | Stock not lost without warehouse credit | HIGH |
| IMP-004 | Expenses/PCF | Batch replenishment workflow | Flag only; no GL entry or cheque tracking | Add BEI PCF Replenishment DocType with lifecycle | Full audit trail from request to disbursal | HIGH |
| IMP-005 | Expenses/PCF | ML model retrain | Manual bench command only | Monthly scheduler retrain when >50 corrections | Keeps classification accurate automatically | MEDIUM |
| IMP-006 | Finance | SOA frontend | Backend complete, no frontend | Add /dashboard/billing/soa/ pages | Finance can manage SOA from app | HIGH |
| IMP-007 | Finance | 3PL billing frontend | All endpoints built, no UI | Add /dashboard/billing/3pl/ module | Finance can process 3PL billing from app | HIGH |
| IMP-008 | Finance | Form 2307 DocType | JSON in tabComment | Create BEI Form 2307 DocType with PDF print format | BIR-compliant certificate generation | HIGH |
| IMP-009 | Finance | doc_events for BEI billing | Payment Entry hooks call upstream expense_claim | Add BEI Payment Request on_update handler | Auto-update BEI Invoice balance_due on payment | MEDIUM |
| IMP-010 | Procurement | PO submittable | is_submittable=0; editable post-approval | Set is_submittable=1; submit on final approval | Audit trail; prevent post-approval edits | HIGH |
| IMP-011 | Procurement | G-046 procurement visibility | Invisible from procurement module | Add inter-company invoice tab on PO/GR detail | Procurement team can audit inter-company | HIGH |
| IMP-012 | Procurement | Single Source Supplier UI | Backend live; no frontend | Add /procurement/audit/single-source/page.tsx | Monitor supplier concentration risk | HIGH |
| IMP-013 | Procurement | EWT JV account fix | 2101001 vs 2101101; DM-1 violation | Fix account + remove party from EWT row | Correct GL; DM-1 compliant | MEDIUM |
| IMP-014 | Warehouse | preview_trip_stops endpoint | Missing function | Add get_trip_stops_preview(route_name, date) to dispatch.py | Trip Wizard Step 3 works | HIGH |
| IMP-015 | Warehouse | Vehicle dropdown fix | Format mismatch | Fix wizard to read data.message.vehicles OR fix response | Vehicle selection works in Trip Wizard | MEDIUM |
| IMP-016 | Warehouse | Driver selector in Trip Wizard | Free-text input | Add combobox calling get_driver_list | Validated driver selection | MEDIUM |
| IMP-017 | Commissary | PRODUCT_THRESHOLDS dict | Hardcoded FG item code prefixes | Move to BEI Settings or custom Item fields | Admin-configurable without code deploy | HIGH |
| IMP-018 | Commissary | QC Form UI | Backend built, no frontend tab | Add QC Forms tab to /quality page | Commissary supervisors can submit QC forms | MEDIUM |
| IMP-019 | Commissary | G-046 failure notification | log_error only | Add GChat notification to commissary space on failure | Visible alert for failed inter-company invoices | MEDIUM |
| IMP-020 | Supervisor | Store visit template configurability | Hardcoded Python dict | Move to BEI Visit Template DocType | Templates updated without code deploy | LOW |
| IMP-021 | Supervisor | Action plan auto-overdue | No scheduler | Daily scheduler: set status=Overdue for Open plans where due_date < today | DB status matches displayed count | MEDIUM |
| IMP-022 | Supervisor | Dedicated area supervisor home | Dual-mode in visits page | Create /dashboard/supervisor/page.tsx | Better navigation; KPI overview | HIGH |
| IMP-023 | HR Management | bulk_update_leave_status consistency | Approve uses doc.submit(); reject uses db_set | Both should use same docstatus mechanism | Consistent leave lifecycle | HIGH |
| IMP-024 | HR Management | Performance review extend_probation | Adds comment only; no date field | Add probation_end_date custom field | Review trigger logic picks up extension | MEDIUM |
| IMP-025 | HR Management | HR reports export | JSON only; no CSV/Excel | Add generate_report_file endpoint for downloadable CSV | Finance/HR can export reports | MEDIUM |
| IMP-026 | Cross-cutting | ERP Sync stubs | 5/8 functions log only | Implement actual DB writes for all 5 | ERP go-live data integration | Critical |
| IMP-027 | Cross-cutting | Support ticket admin | Submitter-only views | Add assign_ticket, update_ticket_status, get_all_tickets + admin UI | IT can manage support from app | MEDIUM |
| IMP-028 | Cross-cutting | ADMS URL config | Hardcoded localhost:8080 | Move to frappe.db.get_single_value("BEI Settings", "adms_base_url") | Config-driven; survives ADMS migration | MEDIUM |
| IMP-029 | Finance | AP aging dedicated page | Buried in dashboard widget | Add /dashboard/accounting/ap-aging/page.tsx | Finance has drill-down AP aging view | MEDIUM |
| IMP-030 | Finance | Batch approve notifications | No employee DM in batch | Add _notify_employee() loop in batch_approve() | Employees know when expenses approved | MEDIUM |
