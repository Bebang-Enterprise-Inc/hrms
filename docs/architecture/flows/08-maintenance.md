# Flow 08: Maintenance Request to Completion
**Departments:** Store → Projects → Finance (cost charges) | **Scanned:** 2026-02-23 | **Agent:** flow-tracer-3

## Flow Diagram (Mermaid)

```mermaid
sequenceDiagram
    participant Staff as Store Staff/OIC
    participant RMPage as /dashboard/rm/new
    participant RMQueue as /dashboard/rm
    participant AdminQ as /dashboard/maintenance
    participant AdminD as /dashboard/maintenance/[id]
    participant ChargesPage as /dashboard/rm-admin/charges
    participant StoreAPI as store.submit_maintenance_request()
    participant ProjAPI as projects.py API
    participant SLAJob as check_sla_violations (hourly)
    participant BillingAPI as billing.generate_monthly_billing()
    participant MaintDT as BEI Maintenance Request
    participant CompDT as BEI Maintenance Completion
    participant Projects as Projects User/Manager
    participant Supervisor as Store Supervisor/OIC
    participant Finance as Finance (monthly billing)

    Staff->>RMPage: Fill title, category, priority, description, before-photos
    RMPage->>StoreAPI: submit_maintenance_request()
    StoreAPI->>MaintDT: INSERT (status=Open, charge_to_store=0)
    StoreAPI-->>Staff: Success message

    Note over SLAJob: Hourly: check_sla_violations()<br/>Urgent: 4h, High: 24h, Normal: 72h
    SLAJob->>MaintDT: Query status IN [Open, Assigned] AND creation < threshold
    SLAJob-->>Projects: GChat alert with breached requests list

    Projects->>AdminQ: View queue with filters (status, category, store, priority)
    AdminQ->>ProjAPI: get_maintenance_queue()
    Projects->>AdminD: Assign to internal user or external vendor
    AdminD->>ProjAPI: assign_maintenance_request()
    ProjAPI->>MaintDT: status=Assigned, assigned_to / vendor set

    Projects->>AdminD: Update status to In Progress
    AdminD->>ProjAPI: update_maintenance_status(status="In Progress")
    ProjAPI->>MaintDT: status=In Progress

    Projects->>AdminD: Add materials (child table)
    AdminD->>ProjAPI: add_maintenance_materials()
    ProjAPI->>MaintDT: BEI Maintenance Material appended; total_cost recalculated

    Projects->>AdminD: Update labor/vendor cost
    AdminD->>ProjAPI: update_maintenance_costs(labor_cost, vendor_cost)
    ProjAPI->>MaintDT: labor_cost, vendor_cost, total_cost updated

    Projects->>AdminD: Record completion + after photo (REQUIRED — throws if absent)
    AdminD->>ProjAPI: record_maintenance_completion()
    ProjAPI->>CompDT: INSERT (status=Pending Verification, savepoint-protected)
    ProjAPI->>MaintDT: completion=CompDT.name, status=Completed, resolved_date set

    Projects->>AdminQ: Set concern type (assess request)
    AdminQ->>ProjAPI: assess_maintenance_request(concern_type)
    ProjAPI->>MaintDT: concern_type set (Wear & Tear / Supplier / Contractor)

    alt charge_to_store = True
        Projects->>ChargesPage: Set charge amount + reason
        ChargesPage->>ProjAPI: set_maintenance_charge()
        ProjAPI->>MaintDT: charge_to_store=1, charge_amount, status=Pending Acknowledgement

        Supervisor->>ChargesPage: View pending charges; acknowledge charge (store-binding check)
        ChargesPage->>ProjAPI: acknowledge_maintenance_charge()
        ProjAPI->>MaintDT: store_acknowledged=1, acknowledged_by, acknowledgement_date, status=Verified
    else no charge
        Projects->>AdminD: Update status to Verified directly
        AdminD->>ProjAPI: update_maintenance_status(status="Verified")
        ProjAPI->>MaintDT: status=Verified
    end

    Finance->>BillingAPI: 1st of month cron
    BillingAPI->>MaintDT: Query charge_to_store=1, billing_status=Not Billed, resolved_date in period
    BillingAPI->>Finance: maintenance_charges rolled into BEI Billing Schedule line item
    BillingAPI->>MaintDT: billing_status=Billed (for included requests)
```

## Step-by-Step Trace

| Step | Actor | Action | Frontend Page | API Endpoint | DocType Created/Updated | Status |
|------|-------|--------|---------------|-------------|------------------------|--------|
| 1 | Store Staff/OIC | Submit R&M request: title, category (8 options), priority (Urgent/High/Normal), description, before-photos (multi-photo capture component) | `/dashboard/rm/new` | `store.submit_maintenance_request` | BEI Maintenance Request (INSERT — status=Open, reported_by=user, photos in child table BEI Maintenance Request Photo) | LIVE |
| 2 | Store Staff/OIC | View own maintenance queue (paginated, filtered) | `/dashboard/rm` | `projects.get_maintenance_queue` | BEI Maintenance Request (read; SLA breach flag computed in query) | LIVE |
| 3 | SLA Scheduler | Hourly check: Urgent (<4h), High (<24h), Normal (<72h) breach detection | Background (no UI) | `projects.check_sla_violations` | BEI Maintenance Request (read); GChat alert to SPACE_NOTIFICATIONS | LIVE |
| 4 | Projects User | View admin maintenance queue with all filters | `/dashboard/maintenance` | `projects.get_maintenance_queue` | BEI Maintenance Request (read) | LIVE |
| 5 | Projects User | View dashboard stats (MTD cost, SLA counts, by_category) | `/dashboard/maintenance` header | `projects.get_maintenance_dashboard_stats` | BEI Maintenance Request + BEI Maintenance Completion (read) | LIVE |
| 6 | Projects User | Assign request to internal technician or external vendor; set scheduled_date, estimated_cost | `/dashboard/maintenance` (assign dialog) | `projects.assign_maintenance_request` | BEI Maintenance Request (status=Assigned, assigned_to or vendor set) | LIVE |
| 7 | Projects User | Update status to In Progress | `/dashboard/maintenance/[id]` | `projects.update_maintenance_status(status="In Progress")` | BEI Maintenance Request (status=In Progress, resolved_date cleared) | LIVE |
| 8 | Projects User | Add materials used (item, qty, unit_cost) — updates total_cost | `/dashboard/maintenance/[id]` | `projects.add_maintenance_materials` | BEI Maintenance Material (child appended); BEI Maintenance Request (materials_cost + total_cost recalculated) | LIVE |
| 9 | Projects User | Update labor hours/cost and vendor invoice amount | `/dashboard/maintenance/[id]` | `projects.update_maintenance_costs` | BEI Maintenance Request (labor_cost, vendor_cost, total_cost = materials+labor+vendor) | LIVE |
| 10 | Projects User | Record completion: completion_date, technician_name, work_description, resolution_status, actual_cost, follow_up_needed, **after_photo (REQUIRED — throws if absent)** | `/dashboard/maintenance/[id]` | `projects.record_maintenance_completion` | BEI Maintenance Completion (INSERT — status=Pending Verification); BEI Maintenance Request (completion linked, status=Completed, resolved_date set) — savepoint rollback on failure | LIVE; photo enforcement is ENABLED (line 610: `if not after_photos: frappe.throw(...)`) |
| 11 | Projects User | Assess concern type post-completion | `/dashboard/rm-admin/queue` | `projects.assess_maintenance_request` | BEI Maintenance Request (concern_type = Wear & Tear / Supplier / Contractor) | LIVE |
| 12 | Projects User | Set store charge: amount + reason → status becomes Pending Acknowledgement | `/dashboard/rm-admin/queue` | `projects.set_maintenance_charge` | BEI Maintenance Request (charge_to_store=1, charge_amount, charging_reason, status=Pending Acknowledgement) | LIVE |
| 13 | Store Supervisor | View pending charges for own store | `/dashboard/rm-admin/charges` | `projects.get_pending_charges` | BEI Maintenance Request (read; filter charge_to_store=1, store_acknowledged=0) | LIVE |
| 14 | Store Supervisor | Acknowledge charge (store-binding check: own store only) | `/dashboard/rm-admin/charges` | `projects.acknowledge_maintenance_charge` | BEI Maintenance Request (store_acknowledged=1, acknowledged_by, acknowledgement_date, status=Verified) | LIVE |
| 15 | Finance Cron | Monthly billing (1st of month, 6 AM): roll up all `charge_to_store=1`, `billing_status=Not Billed` requests resolved in the billing period into franchise billing | Scheduled | `billing.generate_monthly_billing` | BEI Maintenance Request (billing_status=Billed set after inclusion); BEI Billing Schedule line_item (fee_type=Maintenance) created | LIVE — only for Full Franchise and Managed Franchise store types |

## Handoff Points

| From Dept | To Dept | Trigger | Mechanism | Status |
|-----------|---------|---------|-----------|--------|
| Store | Projects | New maintenance request created (status=Open) | No push notification to Projects team. Projects must poll `/dashboard/maintenance` queue. Comment in `submit_maintenance_request` says "Notifies Projects team (Daniel)" but no GChat notification is implemented in the function. | BROKEN — comment says notification will happen; no actual notification code found |
| Projects | Store Supervisor | Work completed, charge set (status=Pending Acknowledgement) | No push notification to store. Store supervisor must poll `/dashboard/rm-admin/charges`. | BROKEN — no notification on charge set |
| Store Supervisor | Projects | Charge acknowledged (status=Verified) | No notification back to Projects that acknowledgement occurred | PASSIVE — Projects must observe status change |
| SLA Scheduler | Projects | Hourly breach alerts | GChat to SPACE_NOTIFICATIONS space | LIVE |
| Projects | Finance | Completed requests with `charge_to_store=1` rolled into monthly billing | Automatic via scheduled `generate_monthly_billing` cron (1st of month). Requests marked `billing_status=Billed` after inclusion. | LIVE — but only Full Franchise and Managed Franchise stores; Internal store charges silently excluded from billing |

## Broken Links / Gaps

| ID | Location | Problem | Impact | Severity |
|----|----------|---------|--------|----------|
| FL08-BL01 | `store.submit_maintenance_request` (line 2288) | Return message says "Projects team will be notified" but NO GChat notification is sent in this function. The `_notify_store_ops` helper exists in store.py but is not called here. Projects team must poll the queue manually. | New urgent requests can sit unattended for hours until manually discovered | HIGH |
| FL08-BL02 | `projects.set_maintenance_charge` | Sets status=Pending Acknowledgement but sends no notification to the store supervisor or the GChat space. Store supervisor has no alert that a charge awaits acknowledgement. | Charges can go unacknowledged indefinitely; delays billing cycle | HIGH |
| FL08-BL03 | `projects.record_maintenance_completion` after_photos handling | Only the FIRST photo from the array is saved (`after_photos[0]`). The BEI Maintenance Completion DocType has a single `after_photos` field (Attach Image). Multi-photo completion evidence is silently truncated to one photo. | Completion documentation incomplete; only one proof photo retained | MEDIUM |
| FL08-BL04 | `projects.update_maintenance_status` valid_transitions | The transition graph lists `Assigned → Pending Acknowledgement` as valid. This means Projects can skip the `Completed` state entirely and jump to `Pending Acknowledgement` without creating a BEI Maintenance Completion record. The `record_maintenance_completion` function (which requires after_photo) can be bypassed. | Projects can mark a request "pending acknowledgement" without creating a completion record or uploading proof photos. The photo requirement (BL03 above) is effectively optional via this path. | MEDIUM |
| FL08-BL05 | `billing.generate_monthly_billing` — store type filter | Only `Full Franchise` and `Managed Franchise` stores trigger maintenance charge roll-up (line 299). `Internal` store type maintenance costs (charged to store) are excluded from billing. | Internal stores with `charge_to_store=1` requests are never billed; charges are orphaned in `billing_status=Not Billed` forever | MEDIUM |
| FL08-BL06 | `projects.check_sla_violations` | SLA check only covers `status IN ['Open', 'Assigned']`. A request stuck in `In Progress` beyond the SLA window generates no alert. | Long-running In Progress requests go unmonitored by SLA system | LOW |
| FL08-BL07 | Permit flow | `permits.py` has `create_permit`, `update_permit`, `get_expiring_permits`, `get_permit_summary` — all LIVE but zero frontend pages. Mall permits cannot be created or managed from my.bebang.ph. | Projects team must use Frappe Desk for mall permit management | MEDIUM |
| FL08-BL08 | Preventive maintenance | No DocType, no API, no frontend (PROJ-G003 from dept scan). Mentioned in Sprint 04 plan but not implemented. | No scheduled/preventive maintenance workflow; all maintenance is reactive | HIGH |
| FL08-BL09 | Maintenance history tab | Uses Frappe Version log. If Version module is disabled for BEI Maintenance Request DocType, status history will be empty. | Status timeline on detail page may show no history | LOW |

## Error Paths

| Trigger | What Happens | User Experience | Status |
|---------|-------------|----------------|--------|
| `record_maintenance_completion` — no after_photos | `frappe.throw(_("At least one after photo is required as proof of completion"))` | Projects user sees error; completion blocked | LIVE — photo enforcement ENABLED |
| `record_maintenance_completion` — savepoint rollback | `frappe.db.rollback(save_point="maintenance_completion")` on any exception | User gets raw exception; BEI Maintenance Completion is not created; request status unchanged | LIVE |
| `record_maintenance_completion` — completion already exists | `frappe.throw(_("Completion record already exists: {0}"))` | Error with existing completion name | LIVE |
| `update_maintenance_status` — invalid transition | `frappe.throw(_("Cannot change status from {0} to {1}. Valid transitions: {2}"))` | User sees allowed transitions | LIVE |
| `assign_maintenance_request` — request not in Open/Assigned | `frappe.throw(_("Cannot assign request with status {0}"))` | User sees error | LIVE |
| `acknowledge_maintenance_charge` — wrong store (B-10) | `frappe.throw(_("You can only acknowledge charges for your own store"))` | Store supervisor blocked from acknowledging another store's charge | LIVE |
| `check_sla_violations` — GChat send fails | Wrapped in `try/except: frappe.log_error("SLA alert failed")` | Alert silently dropped; logged in Error Log | LIVE |
| `submit_maintenance_request` — invalid photo base64 | `save_base64_image` → `frappe.throw("Invalid image data")` | User gets error; request not saved | LIVE |

## Improvement Suggestions

1. **FL08-BL01 — New Request Notification**: Add GChat notification in `store.submit_maintenance_request` when priority is Urgent or High. Use `_notify_store_ops` pattern already present in store.py. Include request name, store, category, priority.

2. **FL08-BL02 — Charge Notification**: Add GChat notification in `projects.set_maintenance_charge` to notify the store supervisor's GChat space that a charge requires acknowledgement. Include amount, reason, request link.

3. **FL08-BL03 — Multi-photo Completion**: Add a child table `BEI Maintenance Completion Photo` (similar to `BEI Maintenance Request Photo`) to BEI Maintenance Completion. Update `record_maintenance_completion` to save all after_photos to the child table, not just the first one.

4. **FL08-BL04 — Close the Bypass Path**: Remove `Pending Acknowledgement` from the valid transitions of `Assigned` and `In Progress` in `update_maintenance_status`. Force the path: `In Progress → Completed` (via `record_maintenance_completion` with required photo) → `Pending Acknowledgement` (via `set_maintenance_charge`). This ensures the completion record + after photo requirement is always enforced before charges are set.

5. **FL08-BL08 — Preventive Maintenance**: Design `BEI PM Schedule` DocType with recurrence rules (daily/weekly/monthly) and auto-generate BEI Maintenance Request records via a daily scheduler job. Critical for equipment uptime.

6. **Sprint 04 — SLA In-Progress Monitoring**: Extend `check_sla_violations` to also monitor `In Progress` status using the SLA windows as an escalation trigger for requests that started work but have not been completed within the SLA window.
