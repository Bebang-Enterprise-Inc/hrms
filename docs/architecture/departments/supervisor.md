---
**Last Scanned:** 2026-02-23 | **Previous Scan:** 2026-02-17
**Commit:** 7b998877f | **Health Score:** 95% LIVE
---

# Department Feature Matrix: Supervisor Tools

## Summary

- Frontend pages: 12
- Backend endpoints: 38 total — 36 LIVE, 1 STUB (visit template is hardcoded dict), 1 partial (approval queue ref-doc update is best-effort)
- DocTypes: 6 (BEI Approval Queue, BEI Store Visit Report, BEI Visit Photo, BEI Coaching Log, BEI Weekly Labor Plan, BEI Action Plan)
- Health Score: 95% LIVE

## Feature Matrix

| Feature | Frontend Page | FE Status | Backend API | BE Status | Notes |
|---------|--------------|-----------|-------------|-----------|-------|
| Area supervisor dashboard | `/dashboard/supervisor/visits` (dual mode) | LIVE | `supervisor.get_area_dashboard` | LIVE | Returns stores, pending approvals, visit stats, action plans |
| Store list | Next.js `/api/supervisor/my-stores` | LIVE | `supervisor.get_my_stores` | LIVE | Uses custom_area_supervisor on Warehouse |
| Store visits list | `/dashboard/supervisor/visits` | LIVE | `supervisor.get_store_visits` | LIVE | |
| Create store visit | `/dashboard/supervisor/visits/new` | LIVE | `supervisor.create_store_visit` | LIVE | 100-point scoring: A=Funds, B=Stocks, C=Organization, D=Staffing, E=Coaching |
| Visit detail | `/dashboard/supervisor/visits/[id]` | LIVE | `supervisor.get_visit_detail` | LIVE | |
| Acknowledge visit | `/dashboard/supervisor/visits/[id]` | LIVE | `supervisor.acknowledge_visit` | LIVE | Sets status=Acknowledged |
| Visit template | `/dashboard/supervisor/visits/new` | LIVE | `supervisor.get_store_visit_template` | STUB | Hardcoded Python dict; no DB read |
| Reports feed | `/dashboard/supervisor/reports-feed` | LIVE | `supervisor.get_area_store_reports`, `get_reports_feed` | LIVE | 5 report types |
| Mark report reviewed | Reports feed | LIVE | `supervisor.mark_report_reviewed` | LIVE | |
| Flag report for revision | Reports feed | LIVE | `supervisor.request_report_revision` | LIVE | GChat notification to submitter |
| Action plans list | `/dashboard/supervisor/action-plans` | LIVE | `supervisor.get_action_plans` | LIVE | |
| Create action plan | `/dashboard/supervisor/action-plans` | LIVE | `supervisor.create_action_plan` | LIVE | Can link to source_visit |
| Coaching log list | `/dashboard/supervisor/coaching` | LIVE | `supervisor.get_coaching_history` | LIVE | |
| Create coaching log | `/dashboard/supervisor/coaching` | LIVE | `supervisor.create_coaching_log` | LIVE | Links to source_visit and source_action_plan |
| Weekly labor plan | `/dashboard/supervisor/labor-plan` | LIVE | `supervisor.get_weekly_plan`, `create_weekly_plan`, `approve_weekly_plan` | LIVE | |
| Unified approval queue | `/dashboard/queue` | LIVE | `supervisor.get_unified_approval_queue` | LIVE | Aggregates 6 approval types |
| Queue approve item | Queue page | LIVE | `supervisor.approve_item` | LIVE | **GAP-053: swallows errors on ref-doc update** |
| Queue reject item | Queue page | LIVE | `supervisor.reject_item` | LIVE | |
| Queue escalate | Queue page | LIVE | `supervisor.escalate_item` | LIVE | **GAP-054: no notification to new approver** |
| Supervisor home dashboard | — | NOT BUILT | — | — | **GAP-038: no /dashboard/supervisor/page.tsx** |
| Coverage request approve | — | NOT BUILT | `supervisor.approve_item` | LIVE | **GAP-037: not wired in queue FE** |
| Biometric punch review | — | NOT BUILT | None | GAP | **GAP-056: not wired into supervisor tools** |

## DocType Relationships

| DocType | Link Fields | Child Tables | Submittable? |
|---------|-------------|-------------|--------------|
| BEI Approval Queue | reference_doctype→DocType, store→Warehouse, submitted_by→User, assigned_approver→User | None | No |
| BEI Store Visit Report | store→Warehouse, visited_by→User | audit_items (BEI Store Audit Item), photos (BEI Visit Photo) | No |
| BEI Coaching Log | store→Warehouse, employee→Employee, source_visit→BEI Store Visit Report | None | No |
| BEI Weekly Labor Plan | store→Warehouse, planned_by→User, approved_by→User | shifts (child) | No |
| BEI Action Plan | store→Warehouse, source_visit→BEI Store Visit Report, assigned_to→User | None | No |

## Gaps Found

| ID | Feature | Blocker Type | Severity | Notes |
|----|---------|-------------|----------|-------|
| GAP-037 | Coverage request approve: not wired in queue | Frontend | High | No approveCoverage handler in use-supervisor-queue.ts |
| GAP-038 | Supervisor landing page missing | Frontend | High | Area supervisors land on Visits to see dashboard |
| GAP-053 | Queue approve_item swallows ref-doc errors | Bug | Medium | Approval Queue approved but source doc NOT updated |
| GAP-054 | Queue escalate: no notification | Integration | Medium | Escalated approver unaware |
| GAP-055 | Action plan overdue: no auto-status update | Feature Gap | Medium | DB status stays Open despite overdue count |
| GAP-056 | Biometric punch review not in supervisor tools | Feature Gap | High | Biometric monitoring exists but not wired |

## Improvements

| Feature | Current State | Suggested Improvement | Priority |
|---------|--------------|----------------------|----------|
| Dedicated area supervisor home | Dual-mode in visits page | Create `/dashboard/supervisor/page.tsx` | HIGH |
| Visit template configurability | Hardcoded Python dict | Move to BEI Visit Template DocType | LOW |
| Action plan auto-overdue | No scheduler | Daily: set status=Overdue for Open plans past due_date | MEDIUM |
| Coverage request approve | No handler in queue hook | Add approveCoverage to useQueueActions + /api/coverage/approve route | MEDIUM |
