---
**Last Scanned:** 2026-02-23 | **Previous Scan:** 2026-02-17
**Commit:** 7b998877f | **Health Score:** 100% LIVE (endpoints)
---

# Department Feature Matrix: Projects & Maintenance

## Summary

- Frontend pages: 10
- Backend endpoints: 40 LIVE (projects.py: 31, permits.py: 5, + 4 shared with store.py)
- DocTypes: 13 (all non-submittable)
- Health Score: 100% LIVE on implemented features; key features have zero implementation (preventive maintenance, incident report API)

## Feature Matrix

| Feature | Frontend Page | FE Status | Backend API | BE Status | Notes |
|---------|--------------|-----------|-------------|-----------|-------|
| Maintenance Queue (store view) | `/dashboard/rm` | LIVE | `projects.get_maintenance_queue` | LIVE | Paginated, SLA breach flag |
| Submit New Maintenance Request | `/dashboard/rm/new` | LIVE | `store.submit_maintenance_request` | LIVE | Uses store API |
| Maintenance Request Detail | `/dashboard/maintenance/[id]` | LIVE | `projects.get_maintenance_request_detail` | LIVE | Status history from Version log |
| Maintenance Admin Queue | `/dashboard/maintenance` | LIVE | `projects.get_maintenance_queue` | LIVE | Full filter/sort/pagination |
| Assign Maintenance Request | `/dashboard/maintenance` (dialog) | LIVE | `projects.assign_maintenance_request` | LIVE | Internal or vendor assignment |
| Update Maintenance Status | `/dashboard/maintenance/[id]` | LIVE | `projects.update_maintenance_status` | LIVE | Enforces valid transition graph. **GAP-087: bypass allows skipping Completed** |
| Record Completion + Photos | `/dashboard/maintenance/[id]` | LIVE | `projects.record_maintenance_completion` | LIVE | **GAP-086: only after_photos[0] saved** |
| Set Maintenance Charge | `/dashboard/rm-admin/queue` | LIVE | `projects.set_maintenance_charge` | LIVE | **GAP-033: no GChat to store supervisor** |
| Acknowledge Maintenance Charge | `/dashboard/rm-admin/charges` | LIVE | `projects.acknowledge_maintenance_charge` | LIVE | |
| SLA Breach Alerts | No frontend | Scheduled | `projects.check_sla_violations` | LIVE | Hourly; GChat per priority tier |
| Project Kanban Dashboard | `/dashboard/projects-mgmt` | LIVE | `projects.get_project_dashboard` | LIVE | 7 stages |
| Project Detail | `/dashboard/projects-mgmt/[id]` | LIVE | `projects.get_project_detail` | LIVE | Inspections, bids, permits, milestones |
| Advance Project Stage | `/dashboard/projects-mgmt/[id]` | LIVE | `projects.advance_project_stage` | LIVE | |
| Bid Comparison/Award | `/dashboard/projects-mgmt/[id]` | LIVE | `projects.evaluate_bid`, `projects.award_bid` | LIVE | 60/40 tech/financial scoring |
| Complete/Verify Milestone | `/dashboard/projects-mgmt/[id]` | LIVE | `projects.complete_milestone`, `verify_milestone` | LIVE | |
| Create Milestone Billing | `/dashboard/projects-mgmt/[id]` | LIVE | `projects.create_milestone_billing` | LIVE | Creates BEI Payment Request |
| Punchlist CRUD | `/dashboard/projects-mgmt/[id]` | LIVE | `projects.add_punchlist_item`, `resolve_punchlist_item`, `close_punchlist_item` | LIVE | |
| Mall Permit Registry View | `/dashboard/projects-mgmt/[id]` (linked) | LIVE | `permits.get_permits` | LIVE | |
| Mall Permit Create/Update | — | GAP | `permits.create_permit`, `update_permit` | LIVE | **GAP-031: no dedicated frontend** |
| Expiring Permits View | — | GAP | `permits.get_expiring_permits` | LIVE | **GAP-031** |
| Permit Expiry Check | N/A | Scheduled | `permits.check_permit_expiry` | LIVE | Daily; auto-update status + GChat |
| Preventive Maintenance | — | NOT BUILT | None | GAP | **GAP-030: no PM feature built; Sprint 04 backlog** |
| Incident Report (projects) | — | NOT BUILT | None | GAP | **GAP-074: DocType exists, no API/UI** |

## DocType Relationships

| DocType | Link Fields | Child Tables | Submittable? |
|---------|-------------|-------------|--------------|
| BEI Maintenance Request | store→Warehouse, assigned_to→User, completion→BEI Maintenance Completion | BEI Maintenance Request Photo, BEI Maintenance Material | No |
| BEI Maintenance Completion | maintenance_request→BEI Maintenance Request, store→Warehouse | None | No |
| BEI Project | store→Warehouse, project_manager→Employee, contractor→BEI Supplier | None | No |
| BEI Project Bid | project→BEI Project, contractor→BEI Supplier | BEI Project Bid Item | No |
| BEI Project Milestone | project→BEI Project, payment_request→BEI Payment Request | None | No |
| BEI Punchlist Item | project→BEI Project, store→Warehouse, assigned_to→User | None | No |
| BEI Mall Permit | store→Warehouse | None | No |
| BEI Incident Report | employee→Employee, reported_by→User, store→Warehouse | None | No |

## Gaps Found

| ID | Feature | Blocker Type | Severity | Notes |
|----|---------|-------------|----------|-------|
| GAP-030 | Preventive Maintenance: no implementation | Feature Gap | High | No DocType, no API, no frontend |
| GAP-031 | Mall Permits: 5 live endpoints, zero frontend | Frontend | High | Permit management requires Frappe Desk |
| GAP-033 | Maintenance charge: no notification to Store Supervisor | Bug | High | Charges go unacknowledged; billing delayed |
| GAP-074 | Incident Report: DocType exists, zero API/frontend | Feature Gap | Medium | |
| GAP-075 | Coaching Log → Performance Review link missing | Design | Medium | Coaching history not in performance review |
| GAP-086 | Maintenance multi-photo completion truncated | Bug | Medium | Only after_photos[0] saved |
| GAP-087 | Maintenance status bypass: skips Completed | Bug | Medium | After-photo requirement effectively optional |
| GAP-088 | Internal store charges never billed | Bug | Medium | Internal stores excluded from generate_monthly_billing |

## Improvements

| Feature | Current State | Suggested Improvement | Priority |
|---------|--------------|----------------------|----------|
| Mall Permit Registry | API fully built, no frontend | Build /dashboard/projects-mgmt/permits page | HIGH |
| Preventive Maintenance | Feature gap | Design PM DocType with recurrence rules + auto-generate requests | HIGH |
| SLA violation alerts | GChat only | Add SLA breach badge on maintenance queue page | HIGH |
| Maintenance photo truncation | Only after_photos[0] saved | Loop to save all photos | MEDIUM |
