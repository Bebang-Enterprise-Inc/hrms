---
**Last Scanned:** 2026-02-23 | **Previous Scan:** 2026-02-17
**Commit:** 7b998877f | **Health Score:** 88% LIVE
---

# Department Feature Matrix: HR Management

## Summary

- Frontend pages: 16 (across `/hr/` management pages and `/hr-admin/leaves/`)
- Backend endpoints: 58 LIVE (payroll.py, performance.py, disciplinary.py, recruitment.py, transfers.py, hr_reports.py, attendance_correction.py, enrichment.py, overtime.py)
- DocTypes: 9 BEI custom + 5 Frappe standard
- Health Score: 88% LIVE (1 stub: payroll comparison; 2 buggy: reject_correction, enrichment GChat reminders)

## Feature Matrix

| Feature | Frontend Page | FE Status | Backend API | BE Status | Notes |
|---------|--------------|-----------|-------------|-----------|-------|
| Payroll Dashboard | `/hr/payroll` | LIVE | `payroll.get_payroll_dashboard`, `get_salary_slip_list` | LIVE | |
| Bank File Generation | `/hr/payroll` (button) | LIVE | `payroll.generate_bank_file` | LIVE | BPI tab-delimited format |
| Payroll vs APEX Comparison | `/hr/payroll` (tab) | PAGE EXISTS | `payroll.get_payroll_comparison` | **STUB** | GAP-049: returns Frappe data labeled as APEX |
| Government Remittance | `/hr/payroll` (tab) | LIVE | `payroll.get_government_remittance` | LIVE | SSS/PhilHealth/Pag-IBIG |
| Attendance Summary | `/hr/attendance` | LIVE | `payroll.get_attendance_summary` | LIVE | |
| Attendance Correction Review | `/hr/attendance-correction/review` | LIVE | `attendance_correction.approve_correction`, `reject_correction` | LIVE (buggy reject) | GAP-019: reject uses db_set, balance not released |
| Leave Command Center | `/hr-admin/leaves` | LIVE (Sprint 09) | `hr_reports.get_leave_overview`, `get_all_leaves`, `check_leave_conflicts`, `bulk_update_leave_status` | LIVE | on_leave_today, pending, upcoming; bulk approve/reject |
| Performance Reviews | `/hr/performance`, `/hr/performance/[id]` | LIVE | `performance.get_pending_reviews`, `submit_appraisal_scores` | LIVE | 90-day and 150-day triggers |
| Regularization Queue | `/hr/performance/regularization` | LIVE | `performance.get_regularization_queue`, `regularize_employee` | LIVE | 170-180 day window |
| Incident Report | `/hr/disciplinary`, `/hr/disciplinary/[id]` | LIVE | `disciplinary.create_incident_report` | LIVE | |
| NTE Issuance | `/hr/disciplinary/[id]` | LIVE | `disciplinary.create_nte` | LIVE | DOLE 5-day response deadline |
| NOD Issuance | `/hr/disciplinary/[id]` | LIVE | `disciplinary.create_nod` | LIVE | |
| Employee Appeal | `/hr/disciplinary/[id]` | LIVE | `disciplinary.create_appeal` | LIVE | |
| MRF Submit | `/hr/recruitment/mrf` | LIVE | `recruitment.create_mrf` | LIVE | |
| Recruitment MRF Pipeline | `/hr/recruitment` | LIVE | `recruitment.get_mrf_list`, `approve_mrf`, `update_applicant_stage`, `create_job_offer` | LIVE | **GAP-010: stage names mismatch; kanban shows 0** |
| Employee Transfers | `/hr/transfers` | LIVE | `transfers.create_transfer`, `approve_transfer` | LIVE | |
| HR Reports | `/hr/reports`, `/hr/reports/[reportId]` | LIVE | `hr_reports.get_employee_masterlist` (+7 more) | LIVE | 8 report types; JSON only |
| Overtime Approve/Reject | — | NOT BUILT | `overtime.approve_overtime`, `reject_overtime`, `get_pending_overtime` | LIVE | **GAP-005: zero frontend** |
| Enrichment Campaign | `/hr/enrichment-tracker` | LIVE | `enrichment.get_enrichment_tracker`, `send_enrichment_reminders` | LIVE | GChat reminders dead code (GAP-076) |
| DOLE Compliance Checklist | — | NOT BUILT | None | GAP | **GAP-023: DocType exists, zero API/frontend** |
| Exit Interview Management | — | NOT BUILT | None | GAP | **GAP-024: DocTypes exist, no API in hr_mgmt** |

## DocType Relationships

| DocType | Link Fields | Child Tables | Submittable? |
|---------|-------------|-------------|--------------|
| BEI Notice to Explain | employee→Employee, incident_report→BEI Incident Report | None | No |
| BEI Notice of Decision | employee→Employee, notice_to_explain→BEI Notice to Explain | None | No |
| BEI Employee Appeal | employee→Employee, notice_of_decision→BEI Notice of Decision | None | No |
| BEI Manpower Request Form | requested_by→Employee, store→Warehouse, linked_job_opening→Job Opening | None | No |
| BEI Overtime Request | attendance→Attendance, employee→Employee, reviewed_by→User | None | No |
| BEI Incident Report | employee→Employee, reported_by→Employee | None | No |
| BEI Dole Compliance Checklist | (per-store) | BEI Dole Compliance Item | No |
| Appraisal (Frappe) | employee→Employee | Appraisal Goal | Yes |
| Employee Transfer (Frappe) | employee→Employee | Employee Property History | Yes |

## Gaps Found

| ID | Feature | Blocker Type | Severity | Notes |
|----|---------|-------------|----------|-------|
| GAP-005 | Overtime: 4 live endpoints, zero frontend | Frontend | Critical | OT requests pile up unmanaged |
| GAP-010 | Recruitment kanban stage name mismatch | Bug | Critical | Pipeline always shows 0 applicants |
| GAP-011 | Job Offer → Employee creation gap | Design | Critical | HR must manually trigger onboarding |
| GAP-019 | Leave rejection uses db_set not doc.cancel | Bug | High | Balance not released on rejection |
| GAP-023 | DOLE Compliance: no API/frontend | Feature Gap | High | Compliance tracking unimplemented |
| GAP-024 | Exit Interview: no API/frontend in HR mgmt | Feature Gap | High | |
| GAP-040 | CEO MRF approval uses System Manager role | Bug | Medium | Governance bypass |
| GAP-049 | Payroll comparison is a stub | Backend Stub | Medium | HR sees misleading data |
| GAP-076 | Enrichment GChat reminder dead code | Bug | Medium | Only email works |
| GAP-085 | bulk_import_gov_ids only via script | Frontend | Low | |

## Improvements

| Feature | Current State | Suggested Improvement | Priority |
|---------|--------------|----------------------|----------|
| bulk_update_leave_status consistency | Approve uses doc.submit(); reject uses db_set | Both should use same docstatus mechanism | HIGH |
| extend_probation | Adds comment only | Add actual probation_end_date custom field | MEDIUM |
| HR reports export | JSON only; no CSV/Excel | Add generate_report_file endpoint | MEDIUM |
