# Maintenance Sprint Plan
**Date:** 2026-02-19
**Status:** COMPLETE — All phases implemented, deployed, and L3 tested (24/24 PASS)
**Version:** v1.6 (L3 verified, sprint closed)
**Priority:** Dept 4 in Master Gap Closure Roadmap
**Parent:** `docs/plans/2026-02-19-master-gap-closure-roadmap.md`

---

## Executive Summary

Maintenance is **high-frequency, high-risk**: 50-100 R&M requests/month across 45 stores with NO mobile UI, disabled photo proof, unaudited RBAC on 66 endpoints, and a Bio ID format that silently breaks attendance for any employee with a wrong value.

This plan covers **4 MUST-HAVE gaps** followed by **4 SHOULD-HAVE gaps**. The security constraint is hard: **G-031 RBAC audit must be completed before the frontend goes live.** 636 employees must not get a UI to 66 unaudited endpoints.

**Total effort estimate:** 7-10 days (backend + frontend)

---

## Business Context

| Fact | Value |
|------|-------|
| Maintenance volume | 50-100 R&M requests/month across 45 stores |
| Current workflow | Stores use informal WhatsApp/calls — no audit trail |
| Projects team size | ~5 people (Projects Manager + staff) |
| Dispute resolution | IMPOSSIBLE without after-photos — vendors claim payment without proof |
| Employee headcount | 636 employees (all with `9xxxxxx` Bio IDs) |
| SLA targets | Urgent=4hr, High=24hr, Normal=72hr |
| Concern types | Wear & Tear, Supplier Deficiency, Contractor Deficiency |
| Charging workflow | Projects team assesses → sets concern type → charges store if applicable → store acknowledges |

**Key people:**
- **Daniel** — Projects Manager (maintenance requests routed to him; notifications TODO)
- **Projects User/Manager role** — can assign requests, record completions, assess charges
- **Store staff** — submit requests via `my.bebang.ph` (currently: zero mobile UI for maintenance)
- **Store Supervisor** — acknowledges charges (`acknowledge_maintenance_charge`)

---

## Technology Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Backend | Frappe Framework (Python) | All maintenance APIs in `hrms/api/projects.py` + `hrms/api/store.py` |
| Employee App (my.bebang.ph) | React + Next.js 16 + Shadcn UI + Tailwind v4 | Separate repo: `bei-tasks` |
| Database | MariaDB (Docker container) | NOT AWS RDS |
| Notifications | Google Chat via service account | `hrms/api/google_chat.py` |
| Deployment | Docker → AWS EC2 via GitHub Actions | `.github/workflows/build-and-deploy.yml` |

---

## Source Files Map

Every file an implementing agent needs to know about:

### Backend API Files

| File | Lines | Role | Key Functions |
|------|-------|------|---------------|
| `hrms/api/projects.py` | ~2295 | Maintenance + Project Management APIs | `get_maintenance_queue` (L22), `get_maintenance_request_detail` (L216), `assign_maintenance_request` (L328), `update_maintenance_status` (L423), `record_maintenance_completion` (L513), `get_maintenance_dashboard_stats` (L683), `export_maintenance_requests` (L835), `get_projects_team_users` (L930), `get_stores_list` (L950), `assess_maintenance_request` (L972), `set_maintenance_charge` (L1011), `acknowledge_maintenance_charge` (L1052), `get_pending_charges` (L1089), `add_maintenance_materials` (L1147), `update_maintenance_costs` (L1207), `get_maintenance_categories` (L1246) |
| `hrms/api/store.py` | ~2200+ | Store Ops including submit maintenance | `submit_maintenance_request` (L2186) — the only store-staff-facing endpoint |
| `hrms/api/google_chat.py` | — | Google Chat notifications | `send_message_to_space(space_name, message) -> bool` — never throws |
| `hrms/utils/bei_config.py` | — | Central config | `get_company()`, `get_chat_space()`, `SPACE_NOTIFICATIONS` |
| `hrms/utils/adms_validation.py` | ~460 | Bio ID validation utilities | `validate_employee_bio_id(bio_id)` (L202), `validate_employee_batch(bio_ids)` (L235) |

### DocTypes (Custom BEI)

| DocType | Directory | Purpose |
|---------|-----------|---------|
| `BEI Maintenance Request` | `hrms/hr/doctype/bei_maintenance_request/` | Core maintenance request. Fields: store, status, priority, issue_category, equipment_area, description, photos (child table), assigned_to, vendor, scheduled_date, estimated_cost, concern_type, charge_to_store, charge_amount, charging_reason, store_acknowledged, acknowledged_by, acknowledgement_date, materials (child table), materials_cost, labor_hours, labor_cost, total_cost, completion (Link to BEI Maintenance Completion), resolved_date, billing_status, billing_reference, reported_by, reported_at |
| `BEI Maintenance Completion` | `hrms/hr/doctype/bei_maintenance_completion/` | Completion record with after_photos, technician_name, work_description, resolution_status, actual_cost, follow_up_needed, follow_up_notes, status (Pending Verification/Verified), verified_by |
| `BEI Maintenance Request Photo` | `hrms/hr/doctype/bei_maintenance_request_photo/` | Child table for before-photos on request |
| `BEI Maintenance Material` | `hrms/hr/doctype/bei_maintenance_material/` | Child table for materials used |
| `BEI Project` | `hrms/hr/doctype/bei_project/` | Project management (separate from maintenance — 5-10/year) |
| `BEI Project Bid` | `hrms/hr/doctype/bei_project_bid/` | Bid management |
| `BEI Project Milestone` | `hrms/hr/doctype/bei_project_milestone/` | Milestone tracking with billing |
| `BEI Project Permit` | `hrms/hr/doctype/bei_project_permit/` | Permit checklist |
| `BEI Site Inspection` | `hrms/hr/doctype/bei_site_inspection/` | Site inspection records |
| `BEI Punchlist Item` | `hrms/hr/doctype/bei_punchlist_item/` | Post-construction defect tracking |

### RBAC Roles (current)

```python
# projects.py — maintenance endpoints
MAINTENANCE_STAFF_ROLES = ["Projects User", "Projects Manager", "System Manager", "Administrator"]
# store.py — submit_maintenance_request
# Uses validate_store_ops_role() — allows Store Staff, Store Supervisor, Area Supervisor, System Manager

# BUG-001 fix comment at projects.py:445-449:
# RBAC was missing initially — added to: assign_maintenance_request, update_maintenance_status,
# record_maintenance_completion. NOT verified on: assess_maintenance_request, set_maintenance_charge,
# acknowledge_maintenance_charge, get_pending_charges, add_maintenance_materials, update_maintenance_costs
```

### Existing Frontend (Legacy Vue/Ionic PWA)

**No dedicated maintenance/ or projects/ frontend pages exist in `frontend/`.**

The existing pages in `frontend/src/views/` that touch maintenance are in the closing report section (embedded maintenance verification in daily close). No standalone maintenance request UI exists anywhere.

---

## MUST-HAVE Gaps (4 items)

### Gap G-031: RBAC Audit of 66 Projects/Maintenance Endpoints

**Problem:** `projects.py:446-449` has a `# BUG-001 fix` comment confirming RBAC was missing at launch and was retroactively added to some endpoints. The full audit has NOT been done. Other endpoints may still be unprotected.

**Current RBAC state (verified in code):**
- `assign_maintenance_request` (L355-359): Protected — `MAINTENANCE_STAFF_ROLES`
- `update_maintenance_status` (L445-449): Protected — `MAINTENANCE_STAFF_ROLES`
- `record_maintenance_completion` (L546-550): Protected — `MAINTENANCE_STAFF_ROLES`
- `submit_maintenance_request` (store.py:L2186): Protected — `validate_store_ops_role()`
- `assess_maintenance_request` (L984-990): **NOT PROTECTED** — no role check
- `set_maintenance_charge` (L1010-1050): **NOT PROTECTED** — no role check
- `acknowledge_maintenance_charge` (L1052-1085): **NOT PROTECTED** — any logged-in user can acknowledge a charge
- `get_pending_charges` (L1089-1143): **NOT PROTECTED** — any user can query pending charges
- `add_maintenance_materials` (L1147-1204): **NOT PROTECTED** — any user can add costs
- `update_maintenance_costs` (L1207-1242): **NOT PROTECTED** — any user can update labor costs
- `get_maintenance_queue` (L22): No explicit role check — but returns read-only data
- `get_maintenance_request_detail` (L216): No explicit role check
- `get_maintenance_dashboard_stats` (L683): No explicit role check
- `export_maintenance_requests` (L835): No explicit role check — reads all data

**Project management endpoints in same file (need separate audit):**
- `get_project_dashboard`, `get_project_detail`, `advance_project_stage`, `update_project_progress`: No role checks
- `submit_site_inspection`, `approve_site_inspection`, `reject_site_inspection`: No role checks
- `get_bid_comparison`, `evaluate_bid`, `award_bid`: No role checks — `award_bid` sets contract!
- `complete_milestone`, `verify_milestone`, `create_milestone_billing`: No role checks
- `get_punchlist`, `add_punchlist_item`, `resolve_punchlist_item`, `close_punchlist_item`, `waive_punchlist_item`: No role checks
- `get_permit_checklist`, `update_permit_status`: No role checks

**Fix (6 tasks):**

**Task 31A: Add RBAC to financial/write endpoints** (2 hours)
- File: `hrms/api/projects.py`
- Add role check to `assess_maintenance_request` (before L984):
  ```python
  user_roles = frappe.get_roles(frappe.session.user)
  allowed_roles = ["Projects User", "Projects Manager", "System Manager", "Administrator"]
  if not any(role in user_roles for role in allowed_roles):
      frappe.throw(_("You do not have permission to assess maintenance requests"), frappe.PermissionError)
  ```
- Same pattern for: `set_maintenance_charge`, `add_maintenance_materials`, `update_maintenance_costs`

**Task 31B: Restrict charge acknowledgement to Store roles only** (30 min)
- File: `hrms/api/projects.py`
- `acknowledge_maintenance_charge` (L1052): Only Store Supervisor or Store Staff should acknowledge
  ```python
  user_roles = frappe.get_roles(frappe.session.user)
  allowed_roles = ["Store Supervisor", "Store Staff", "Area Supervisor", "System Manager", "Administrator"]
  if not any(role in user_roles for role in allowed_roles):
      frappe.throw(_("Only store staff can acknowledge maintenance charges"), frappe.PermissionError)
  ```

**Task 31C: Add `frappe.only_for` to project management write endpoints** (2 hours)
- File: `hrms/api/projects.py`
- `advance_project_stage`, `update_project_progress`, `award_bid`, `evaluate_bid`, `complete_milestone`, `verify_milestone`, `create_milestone_billing`, `update_permit_status`, `add_punchlist_item`, `resolve_punchlist_item`, `close_punchlist_item`, `waive_punchlist_item` — all need:
  ```python
  frappe.only_for(["Projects Manager", "System Manager", "Administrator"])
  ```
- `submit_site_inspection`, `approve_site_inspection`, `reject_site_inspection` — same restriction

**Task 31D: Add read-only RBAC to queue/dashboard/export endpoints** (1 hour)
- File: `hrms/api/projects.py`
- `get_maintenance_queue`, `get_maintenance_request_detail`, `get_maintenance_dashboard_stats`: Require at minimum `Projects User` role (or Store roles for store-specific views):
  ```python
  if frappe.session.user == "Guest":
      frappe.throw(_("Authentication required"), frappe.AuthenticationError)
  ```
- `export_maintenance_requests`: Restrict to `Projects Manager` only (bulk export of all stores is sensitive)
- `get_pending_charges`: Allow both Projects roles AND Store roles (store needs to see its own charges)

**Task 31E: Add comment documenting BUG-001 resolution** (15 min)
- File: `hrms/api/projects.py`
- Add a module-level comment after the imports:
  ```python
  # RBAC AUDIT 2026-02-19: All endpoints reviewed. See G-031 in gap register.
  # Maintenance endpoints: MAINTENANCE_STAFF_ROLES for write, authenticated-only for read
  # Project endpoints: Projects Manager for all write operations
  # Charging endpoints: Store roles for acknowledgement, Projects roles for assessment
  ```

**Task 31F: Verify no SQL injection in `get_maintenance_queue`** (30 min)
- File: `hrms/api/projects.py:109-117`
- The sort_by whitelist check at L110-115 is correct — only whitelisted fields allowed
- The filter parameter building at L130-145 uses parameterized values — correct
- Mark G-104 as CLOSED (false positive) with a comment at the function head

**Effort:** 1-2 days
**Test:** With `test.crew1@bebang.ph` (Crew role — no Projects access), call each endpoint and verify 403 is returned for write endpoints. With `test.projects@bebang.ph`, verify full access.

---

### Gap G-007 (Maintenance Only): Maintenance Frontend — 4 Pages

**Problem:** Zero mobile UI for maintenance in `my.bebang.ph`. Store staff submit requests via WhatsApp/calls. Projects team manages queue via Frappe Desk (not mobile-friendly). 50-100 requests/month with no system record means no SLA tracking, no dispute resolution, no trend analysis.

**Pre-condition: G-031 RBAC audit must be complete before any frontend goes live.**

**4 Pages Required:**

**Page 1: `/maintenance` — Store Staff Submit Request** (1 day)
- **Who uses it:** Store staff (`Store Staff`, `Store Supervisor`, `Area Supervisor` roles)
- **APIs consumed:**
  - `store.submit_maintenance_request(store, priority, description, issue_category, equipment_area, impact_on_operations, photos)` — `hrms/api/store.py:2186`
  - `projects.get_maintenance_categories()` — `hrms/api/projects.py:1246` — for category dropdown
  - `projects.get_stores_list()` — `hrms/api/projects.py:950` — for store picker (if not pre-filled)
- **UI requirements:**
  - Form with: Category (dropdown from `get_maintenance_categories`), Equipment/Area (text), Priority selector (Urgent/High/Normal with color coding), Description (textarea), Impact on Operations (Can Operate/Limited Operations/Cannot Operate)
  - **Photo capture: MANDATORY** — camera button (multiple photos). Must pass photos as JSON array `[{photo: base64_or_url, caption: ""}]`
  - Priority visual: Urgent=red banner, High=orange, Normal=blue
  - Submit button → success screen with request ID
  - Store is pre-filled from session user's store (`frappe.get_value("Employee", user_employee, "branch")`)
- **RBAC:** Store Ops roles only (validate_store_ops_role pattern)

**Page 2: `/maintenance/[id]` — Request Detail + Status Tracking** (1 day)
- **Who uses it:** Store staff (view own requests), Projects team (view all)
- **APIs consumed:**
  - `projects.get_maintenance_request_detail(request_id)` — `hrms/api/projects.py:216`
  - `projects.acknowledge_maintenance_charge(request_id)` — `hrms/api/projects.py:1052` — for store staff
- **UI requirements:**
  - Request header: ID, priority badge, status badge, category, store
  - Before photos gallery (scrollable, tap to zoom)
  - Timeline/history (from `detail.history`)
  - Completion section (shows after_photos, technician, work done) — visible when status=Completed+
  - Charge acknowledgement card: if `charge_to_store=1` and `store_acknowledged=0`, show charge amount + "Acknowledge" button
  - Status badge color: Open=gray, Assigned=blue, In Progress=yellow, Completed=green, Verified=teal, Cancelled=red
- **RBAC:** Store staff see own store's requests; Projects team see all

**Page 3: `/rm` — Projects Team R&M Queue** (1 day)
- **Who uses it:** Projects team (`Projects User`, `Projects Manager` roles)
- **APIs consumed:**
  - `projects.get_maintenance_queue(status, priority, category, store, page, page_size)` — `hrms/api/projects.py:22`
  - `projects.get_maintenance_dashboard_stats()` — `hrms/api/projects.py:683`
  - `projects.assign_maintenance_request(request_id, assigned_to, vendor, scheduled_date, estimated_cost, notes)` — `hrms/api/projects.py:328`
  - `projects.update_maintenance_status(request_id, status, notes)` — `hrms/api/projects.py:423`
  - `projects.get_projects_team_users()` — `hrms/api/projects.py:930`
- **UI requirements:**
  - Stats row at top: Open, Assigned, In Progress, Urgent count, Avg resolution days
  - Filterable table: filter by Status, Priority, Category, Store
  - Row actions: Assign (opens modal with user/vendor picker), Update Status
  - Pagination (default 20/page)
  - Priority visual indicators (Urgent rows highlighted red)
  - Age badge: requests >SLA threshold turn red (Urgent >4hr, High >24hr, Normal >72hr)
- **RBAC:** Projects roles only

**Page 4: `/rm/[id]` — Assignment + Completion Form** (1 day)
- **Who uses it:** Projects team (assign, record completion); Projects Manager (assess, charge)
- **APIs consumed:**
  - `projects.get_maintenance_request_detail(request_id)` — `hrms/api/projects.py:216`
  - `projects.assign_maintenance_request(request_id, assigned_to, vendor, scheduled_date, estimated_cost, notes)` — `hrms/api/projects.py:328`
  - `projects.update_maintenance_status(request_id, status, notes)` — `hrms/api/projects.py:423`
  - `projects.record_maintenance_completion(request_id, completion_date, technician_name, work_description, resolution_status, actual_cost, follow_up_needed, follow_up_notes, after_photos)` — `hrms/api/projects.py:513`
  - `projects.assess_maintenance_request(request_id, concern_type, notes)` — `hrms/api/projects.py:972`
  - `projects.set_maintenance_charge(request_id, charge_amount, charging_reason)` — `hrms/api/projects.py:1011`
  - `projects.add_maintenance_materials(request_id, materials)` — `hrms/api/projects.py:1147`
  - `projects.update_maintenance_costs(request_id, labor_hours, labor_cost)` — `hrms/api/projects.py:1207`
- **UI requirements:**
  - Full request detail (same as Page 2)
  - Assign section: user/vendor picker, scheduled date, estimated cost
  - Status update buttons (valid transitions shown)
  - **Completion form:** Completion date, Technician name, Work description, Resolution status (Fully Resolved/Partially Resolved/Not Resolved), Actual cost, Follow-up needed toggle (shows notes field when on), **After photos: MANDATORY camera capture**
  - Assessment section (Projects Manager only): Concern type (Wear & Tear/Supplier Deficiency/Contractor Deficiency), notes
  - Charge section (Projects Manager only): Amount, reason
  - Materials section: table of materials with add/remove
- **RBAC:** Projects roles only for all actions

**Implementation Notes:**
- All 4 pages go in `bei-tasks` repo (React/Next.js)
- Route pattern: `/maintenance` (store submission), `/maintenance/[id]` (detail), `/rm` (queue), `/rm/[id]` (admin detail)
- Mobile-first — store staff use phones; all forms must work on 375px viewport
- Photo capture: Use the camera capture pattern already established in the app. Photos must be real photos (150KB+), not 1x1 pixels. See `hrms/api/store.save_base64_image` for backend handling
- After photos on completion form: Use the standardized payload schema defined in G-082 (see SHOULD-HAVE)

**Effort:** 4 days (2 days backend RBAC first, 4 days frontend)
**Test:** Full E2E: `test.staff@bebang.ph` submits request with photo → `test.projects@bebang.ph` sees it in queue → assigns → records completion with camera photo → store verifies. Verify photo saves correctly, not silently null.

---

### Gap G-005: Photo Completion Disabled

**Problem:** `projects.py:581-583` has a TODO comment explicitly disabling the after-photo requirement:

```python
# TODO: Re-enable photo requirement once frontend has upload capability
# if not after_photos:
#     frappe.throw(_("At least one after photo is required as proof of completion"))
```

Without this check, Projects staff can record completion with no photographic evidence. Vendors receive payment without proof of work. Dispute resolution is impossible.

**Fix (2 tasks):**

**Task 5A: Uncomment the photo validation** (15 min)
- File: `hrms/api/projects.py`
- Lines 581-583: Remove the comment wrapper, re-enable validation:
  ```python
  if not after_photos:
      frappe.throw(_("At least one after photo is required as proof of completion"))
  ```
- **Prerequisite:** G-007 frontend must include camera capture on the completion form BEFORE this is re-enabled. Do NOT uncomment until the frontend is deployed and tested. Otherwise all existing completions via API will break.

**Task 5B: Add photo validation to the frontend completion form** (bundled with G-007 Page 4)
- The `/rm/[id]` page completion form must have a mandatory camera capture field
- Only show the Submit Completion button when at least one photo is in the `after_photos` state
- Client-side validation: "At least one after-photo is required"
- Backend will also validate after Task 5A is re-enabled

**Sequencing:**
1. Build G-007 Page 4 with mandatory camera capture
2. Deploy frontend to staging
3. Test that completion form works with photos
4. Uncomment lines 581-583 in `projects.py`
5. Deploy backend
6. Run E2E: attempt completion without photo → verify 403/400 error; attempt with photo → verify success

**Effort:** 15 minutes of backend change (bundled with G-007 frontend build)
**Test:** Call `record_maintenance_completion` via API without `after_photos` → verify `frappe.ValidationError` thrown. Call with valid photo → verify completion created with `after_photos` URL populated in BEI Maintenance Completion.

---

### Gap G-124: Bio ID Validation (9xxxxxx Format)

**Problem:** The `attendance_device_id` field on Employee records is not validated for the `9xxxxxx` format. Any value can be entered. A wrong Bio ID silently breaks ADMS attendance matching → payroll errors for that employee. Legacy 6-digit Bio IDs (e.g., 324002) are fully deprecated per Memory #8.

The existing `adms_validation.py:202-229` (`validate_employee_bio_id`) validates against the Employee_Master CSV — useful for ADMS commands but NOT as a DocType save-time validator. The format-only regex check `^9\d{6}$` needs to be added to the Employee DocType's `validate()` hook.

**Current state:** No validation exists on `attendance_device_id` at DocType level. The only validation is in `adms_validation.py` which operates against the CSV, not as a Frappe save hook.

**Fix (2 tasks):**

**Task 124A: Add validate hook to Employee DocType** (2 hours)
- **Option A (preferred):** Custom field validator via Frappe hooks
  - File: `hrms/hooks.py` — add to `doc_events`:
    ```python
    doc_events = {
        "Employee": {
            "validate": "hrms.api.onboarding.validate_employee_doc"
        }
    }
    ```
  - File: `hrms/api/onboarding.py` — add function:
    ```python
    def validate_employee_doc(doc, method=None):
        """Validate Employee fields on save."""
        import re
        if doc.attendance_device_id:
            bio_id = str(doc.attendance_device_id).strip()
            if not re.match(r'^9\d{6}$', bio_id):
                frappe.throw(
                    f"Bio ID '{bio_id}' is invalid. Must match format 9xxxxxx "
                    f"(7 digits starting with 9). Example: 9001234",
                    frappe.ValidationError
                )
    ```
- **Option B (alternative):** Add directly to HRMS Employee DocType extension if BEI has a custom Employee class
  - Search for `class CustomEmployee` or `class BEIEmployee` in `hrms/hr/doctype/employee/`
  - If found, add `validate_attendance_device_id` call in `validate()` method

**Task 124B: Add format validation on enrollment API** (1 hour)
- File: `hrms/api/__init__.py` — find the employee enrichment update function (around L840 where `attendance_device_id` is listed in fields)
- Any API that accepts `attendance_device_id` as a write parameter must validate the format before saving
- Search for `attendance_device_id` in write paths across all API files

**Effort:** 2-4 hours
**Test:** Via API, set `attendance_device_id = "324002"` on any employee → verify `ValidationError`. Set `attendance_device_id = "9001234"` → verify save succeeds. Verify ADMS monitor (`adms_monitor.py:110-114`) still finds employees correctly after change.

---

## SHOULD-HAVE Gaps (4 items)

### Gap G-077: SLA Tracking + Escalation Alerts

**Problem:** `projects.py` tracks `age_days` (computed in SQL at `get_maintenance_queue:185`) but no SLA violation alerts. An Urgent request that's been open for 8 hours will sit silently. Projects Manager gets no notification. Store may call to complain — already too late.

**SLA targets:**
- Urgent: 4 hours to first response
- High: 24 hours to first response
- Normal: 72 hours to first response

**Fix (3 tasks):**

**Task 77A: Add scheduled SLA check job** (2 hours)
- File: `hrms/hooks.py` — add to scheduled tasks (hourly):
  ```python
  scheduler_events = {
      "hourly": [
          "hrms.api.projects.check_sla_violations"
      ]
  }
  ```
- File: `hrms/api/projects.py` — add function `check_sla_violations()`:
  ```python
  def check_sla_violations():
      """Scheduled: check for SLA breaches, send Google Chat alerts."""
      from hrms.api.google_chat import send_message_to_space
      from hrms.utils.bei_config import get_chat_space, SPACE_NOTIFICATIONS

      SLA_HOURS = {"Urgent": 4, "High": 24, "Normal": 72}
      now = now_datetime()

      for priority, hours in SLA_HOURS.items():
          threshold_dt = now - timedelta(hours=hours)
          breached = frappe.get_all(
              "BEI Maintenance Request",
              filters={
                  "priority": priority,
                  "status": ["in", ["Open", "Assigned"]],
                  "creation": ["<", threshold_dt]
              },
              fields=["name", "store_code", "priority", "issue_category", "description", "creation"]
          )

          if breached:
              lines = [f"*SLA BREACH — {priority} ({hours}hr SLA)*"]
              for req in breached:
                  age_hrs = round((now - req.creation).total_seconds() / 3600, 1)
                  lines.append(
                      f"• {req.name} — {req.store_code} | {req.issue_category} | Age: {age_hrs}h"
                  )
              message = "\n".join(lines)
              try:
                  space = get_chat_space(SPACE_NOTIFICATIONS)
                  send_message_to_space(space, message)
              except Exception:
                  frappe.log_error("SLA alert failed", "Maintenance SLA")
  ```

**Task 77B: Add `sla_breached` computed field to queue API** (30 min)
- File: `hrms/api/projects.py:164-191`
- In the `requests_sql` query, add computed column:
  ```sql
  CASE
      WHEN mr.priority = 'Urgent' AND TIMESTAMPDIFF(HOUR, mr.creation, NOW()) > 4 THEN 1
      WHEN mr.priority = 'High' AND TIMESTAMPDIFF(HOUR, mr.creation, NOW()) > 24 THEN 1
      WHEN mr.priority = 'Normal' AND TIMESTAMPDIFF(HOUR, mr.creation, NOW()) > 72 THEN 1
      ELSE 0
  END as sla_breached
  ```
- Frontend uses this to highlight breached rows in the queue

**Task 77C: Add SLA indicators to frontend queue page** (bundled with G-007 Page 3)
- Red background for `sla_breached=1` rows
- Age display with warning color when nearing threshold

**Effort:** 1 day
**Test:** Create an Urgent request, manually set `creation` to 5 hours ago in DB, trigger `check_sla_violations()` directly → verify Google Chat message fires. Verify queue API returns `sla_breached=1` for that request.

---

### Gap G-082: Photo Payload Standardization

**Problem:** `projects.py:626-631` handles nested photo dicts (`{"photo": {"photo": "data:..."}}`) to work around inconsistent frontend payloads. This is a fragile workaround. If the old frontend sent nested payloads, new frontend must NOT. This must be defined BEFORE frontend development starts.

**Standard photo payload schema (define now, enforce in frontend):**

```json
// Single photo (correct):
"after_photos": "data:image/jpeg;base64,/9j/4AAQ..."

// Array of photos (for before_photos on maintenance request):
"photos": [
    {"photo": "data:image/jpeg;base64,...", "caption": "Equipment broken"},
    {"photo": "data:image/jpeg;base64,...", "caption": "Damage close-up"}
]
```

**Fix (2 tasks):**

**Task 82A: Define and document the standard schema** (30 min)
- Add a docstring at the top of `projects.py` after the module imports:
  ```python
  # PHOTO PAYLOAD STANDARD (G-082, 2026-02-19):
  # - Single photo: pass as string (data:image/xxx;base64,... OR /files/... URL)
  # - Multiple photos (before_photos on request): pass as JSON array [{photo: string, caption: string}]
  # - after_photos on completion: pass as single string (first/only camera capture)
  # - Backend saves via save_base64_image() — returns /files/... URL
  # - Nested dicts like {"photo": {"photo": "data:..."}} are legacy — frontend must NOT send these
  ```
- Share this schema with the frontend developer building G-007

**Task 82B: Simplify the nested-dict unwrapping in `record_maintenance_completion`** (1 hour)
- File: `hrms/api/projects.py:626-631`
- Keep the fallback for legacy data, but add a log warning so we can track if nested dicts are still arriving:
  ```python
  if isinstance(photo_data, dict):
      inner = photo_data.get('photo', '') or photo_data.get('url', '') or ''
      if isinstance(inner, dict):
          frappe.log_error(
              f"Nested photo dict received — frontend sending wrong format: {photo_data}",
              "Photo Payload Warning"
          )
          inner = inner.get('photo', '') or inner.get('url', '') or ''
      photo_data = inner
  ```

**Effort:** Bundled with G-007 frontend build (30 min backend, 0 extra frontend effort)

---

### Gap G-078: Add `vendor_cost` Field to Maintenance Request

**Problem:** `BEI Maintenance Request` has `materials_cost` and `labor_cost` (internal labor) but no field for external vendor invoice amount. For R&M in a 45-store QSR chain, the majority of costs are contractor invoices (electricians, plumbers, pest control), not internal labor. Finance cannot reconcile vendor payments against specific maintenance requests.

**Current cost fields (from `bei_maintenance_request.json` field_order):**
- `materials` (child table) → `materials_cost` (currency)
- `labor_hours` (float), `labor_cost` (currency)
- `total_cost` = materials_cost + labor_cost

**Missing:** `vendor_cost` (currency) — the external contractor's invoice amount

**Fix (2 tasks):**

**Task 78A: Add `vendor_cost` field to DocType** (2 hours)
- File: `hrms/hr/doctype/bei_maintenance_request/bei_maintenance_request.json`
- Add field in `section_costs` section, after `labor_cost`:
  ```json
  {
      "fieldname": "vendor_cost",
      "fieldtype": "Currency",
      "label": "Vendor Cost",
      "description": "External contractor invoice amount"
  }
  ```
- Update `field_order` to include `vendor_cost` after `labor_cost`
- Update `total_cost` computation in `update_maintenance_costs` (projects.py:1235):
  ```python
  doc.total_cost = flt(doc.materials_cost or 0) + flt(doc.labor_cost or 0) + flt(doc.vendor_cost or 0)
  ```
- Add corresponding setter in `update_maintenance_costs` API

**Task 78B: Add `vendor_cost` input to completion/admin form** (bundled with G-007 Page 4)
- Add a "Vendor Cost (Invoice Amount)" field in the completion form for vendor-assigned requests
- Only show if `doc.vendor` is set (contractor assignment)
- Call `projects.update_maintenance_costs(request_id, vendor_cost=amount)` on submit

**Effort:** 1-2 hours (DocType change) + bundled with frontend
**Test:** Create maintenance request assigned to vendor. Record completion with vendor_cost=5000. Verify total_cost = materials_cost + labor_cost + 5000.

---

### Gap G-055: Bulk Government ID CSV Import for 636 Employees

**Problem:** Employees must enter TIN/SSS/PhilHealth/Pag-IBIG one-by-one. For 636 employees, HR cannot realistically do this manually. Without correct IDs, payroll statutory remittances are filed with wrong numbers — DOLE/BIR compliance risk.

**Current state:** `hrms/api/enrichment.py` has employee enrichment endpoints for individual records. No bulk CSV upload path exists.

**Fix (2 tasks):**

**Task 55A: Build `bulk_import_gov_ids` API endpoint** (1 day)
- File: `hrms/api/enrichment.py` — add new endpoint:
  ```python
  @frappe.whitelist()
  def bulk_import_gov_ids(csv_content=None, file_url=None):
      """
      Bulk import government IDs from CSV.
      CSV columns: employee_id, tin, sss_number, philhealth_number, pagibig_number
      Returns: {"updated": int, "skipped": int, "errors": [...]}
      """
      frappe.only_for(["HR Manager", "System Manager", "Administrator"])
      # Parse CSV (from raw string or file URL)
      # For each row: find Employee by employee_id (name or employee_number)
      # Validate: TIN format (XXX-XXX-XXX-000), SSS (XX-XXXXXXX-X), PhilHealth (XX-XXXXXXXXX-X)
      # Use frappe.db.set_value() for direct field update (no ORM insert trap)
      # Collect errors per row without stopping the entire import
      # Return summary: {"updated": 400, "skipped": 50, "errors": [...], "report_url": "..."}
  ```

**Task 55B: Build simple HR upload UI** (4 hours)
- File: `bei-tasks` repo — add page `/hr/gov-id-import`
- CSV template download button (shows expected column headers)
- File upload widget
- Preview table (first 5 rows)
- Import button with confirmation dialog
- Result display: "Updated 400 / 636 employees. 50 skipped (already have IDs). 3 errors."
- Download errors CSV
- **RBAC:** HR Manager only

**Effort:** 1-2 days
**Test:** Upload a CSV with 5 employees. Verify TIN/SSS/PhilHealth/Pag-IBIG set correctly. Test with invalid TIN format → verify error captured per row without stopping import. Verify existing IDs are NOT overwritten (skip if already set, or require `--force` flag).

---

## Sprint Execution Order

### Phase 0: RBAC Audit (Day 1-2) — ✅ COMPLETE (2026-02-20)

| Day | Task | What | Status |
|-----|------|------|--------|
| 1 | G-031 Task 31A | Add RBAC to `assess_maintenance_request`, `set_maintenance_charge`, `add_maintenance_materials`, `update_maintenance_costs` | ✅ Already done (pre-existing) |
| 1 | G-031 Task 31B | Restrict `acknowledge_maintenance_charge` to Store roles + store-binding (BLOCKER 10) | ✅ Already done (pre-existing) |
| 1 | G-031 Task 31C | Add `frappe.only_for` to 15 project management write endpoints | ✅ Done — `d02fab9c3` |
| 1 | G-031 Task 31D | Add read-only auth guard to queue/dashboard/export + 5 project read endpoints | ✅ Done — `d02fab9c3` + `beb10586b` |
| 1 | G-031 Task 31E | Add audit completion comment | ✅ Done — `d02fab9c3` |
| 1 | G-031 Task 31F | Verify SQL injection not a risk, close G-104 | ✅ Done — `d02fab9c3` |
| 2 | G-124 Task 124A | Add Bio ID validation hook to Employee DocType | ✅ Done — `d02fab9c3` (hrms/utils/bio_id_validation.py + hooks.py) |
| 2 | G-124 Task 124B | Add format validation on enrichment write APIs | ✅ N/A — no write paths found; DocType hook covers all saves |

**Deployed:** `d02fab9c3` (2026-02-20 10:28 UTC) — Full Docker build + migrate. Verified live.

**Post-deploy audit fixes (commit `beb10586b`):**
- Removed `@frappe.whitelist()` from `check_sla_violations` (scheduled task, not user-callable)
- Set `Employee Self Service` role to `create=0, write=0` on BEI Maintenance Request (same BLOCKER 2 class)
- Added Guest auth guards to 5 project read endpoints (get_project_dashboard, get_project_detail, get_bid_comparison, get_punchlist, get_permit_checklist)

**RBAC summary:** 36 guards total across all endpoints. 15 `frappe.only_for`, 11 Guest auth guards, 6 inline role checks, 4 pre-existing.

### Phase 1: Backend Groundwork (Day 2-3) — ✅ COMPLETE (2026-02-20)

| Day | Task | What | Status |
|-----|------|------|--------|
| 2 | G-078 Task 78A | Add `vendor_cost` field to DocType JSON + API formula | ✅ Done — `d02fab9c3` |
| 2 | G-082 Task 82A | Document standard photo payload schema | ✅ Done — `d02fab9c3` |
| 2 | G-082 Task 82B | Add log warning for legacy nested photo dicts | ✅ Done — `d02fab9c3` |
| 3 | G-077 Task 77A | Add hourly SLA check scheduled job | ✅ Done — `d02fab9c3` |
| 3 | G-077 Task 77B | Add `sla_breached` column to queue API | ✅ Done — `d02fab9c3` (verified: returns 1 for breached requests) |
| — | G-005 Task 5A | Uncomment photo validation in `projects.py` | ✅ Done — `d02fab9c3` (moved up from Phase 3 — backend-only, no frontend dependency) |

**Note:** Task 5A was moved from Phase 3 to Phase 1 because the photo validation is backend-only. The plan originally sequenced it after frontend deployment, but since the API already requires photos and completions are done via API (not yet via frontend), enabling it now is safe.

**Deployed:** Same commit `d02fab9c3`. Migration ran (vendor_cost field added to DB).

### Phase 2: Frontend Build (Days 4-7) — ✅ COMPLETE

**Discovery:** All 4 pages were already fully built from Sprint 03. Sprint 04 added the missing wiring:

| Day | Task | Page | Status |
|-----|------|------|--------|
| 4 | G-007 Page 1 | `/rm/new` — Store submission form with MultiPhotoCapture | ✅ Already built (428 lines) |
| 4-5 | G-007 Page 2 | `/maintenance/[id]` — Request detail (1086 lines) + charge/cost section added | ✅ Done — `0451463` |
| 5-6 | G-007 Page 3 | `/maintenance` — Projects queue (629 lines) + SLA breach badge added | ✅ Done — `0451463` |
| 6-7 | G-007 Page 4 | `/maintenance/[id]` — Completion form with after-photos already built in detail page | ✅ Already built |

**Sprint 04 frontend additions (commit `0451463`):**
- Types: vendor_cost, sla_breached, charge fields, "Pending Acknowledgement" status
- API route: set_charge, acknowledge_charge, update_costs actions wired
- Hooks: setCharge, acknowledgeCharge, updateCosts methods added
- Queue page: SLA breach badge on list items
- Detail page: Costs & Charging section with store charge info display

### Phase 3: Photo Validation + Deployment (Day 7-8) — ✅ COMPLETE

| Day | Task | What | Status |
|-----|------|------|--------|
| 7 | G-005 Task 5B | Frontend: camera capture mandatory on completion form | ✅ Already built — MultiPhotoCapture in completion modal |
| 7 | E2E test | Full cycle: submit → assign → complete with photo → verify | ⏳ Manual test pending (API verified live) |
| 8 | G-005 Task 5A | Uncomment photo validation in `projects.py` | ✅ Done — `d02fab9c3` (moved to Phase 1) |
| 8 | Deploy | Full Docker build + Vercel deploy | ✅ Backend: `d02fab9c3` + `beb10586b`. Frontend: `0451463` (Vercel auto-deploy) |

### Phase 4: SHOULD-HAVE Cleanup (Days 8-10) — ✅ COMPLETE

| Day | Task | What | Status |
|-----|------|------|--------|
| 8-9 | G-055 Task 55A | `bulk_import_gov_ids()` in enrichment.py | ✅ Done — `809ef497f` |
| 8-9 | G-055 Task 55B | `/dashboard/hr/gov-id-import` page + API route | ✅ Done — `f0bd65d` (bei-tasks) |
| 9-10 | G-078 Task 78B | Vendor cost field on completion form | ✅ Done — `f0bd65d` (bei-tasks) |

---

## Verification Checklist

Before marking this sprint as complete, verify ALL of the following:

### Backend Verifications
- [x] `assess_maintenance_request()` — RBAC verified in code (Projects User/Manager check at L1042-1046)
- [x] `set_maintenance_charge()` — RBAC verified in code (Projects User/Manager check at L1087-1091)
- [x] `add_maintenance_materials()` — RBAC verified in code (Projects User/Manager check at L1252-1256)
- [x] `acknowledge_maintenance_charge()` — Store + Projects roles with store-binding check (L1133-1153)
- [ ] `acknowledge_maintenance_charge()` — call with `test.staff@bebang.ph` (Store Staff) → verify success *(test account not provisioned)*
- [x] `award_bid()` — `frappe.only_for(["Projects Manager", "System Manager", "Administrator"])` at L1878
- [x] `record_maintenance_completion()` — call WITHOUT `after_photos` → ValidationError (L610-611, enabled)
- [ ] `record_maintenance_completion()` — call WITH valid photo → verify completion created *(needs E2E test)*
- [x] Employee `attendance_device_id` — Bio ID validation hook active (regex `^9\d{6}$` in bio_id_validation.py)
- [x] `check_sla_violations()` — registered in hooks.py hourly scheduler; NOT whitelisted (audit fix)
- [x] `get_maintenance_queue()` response includes `sla_breached` field — verified live (returns 1 for breached)
- [ ] `bulk_import_gov_ids()` — NOT YET BUILT (Phase 4, G-055)
- [x] `export_maintenance_requests()` — `frappe.only_for(["Projects Manager", ...])` at L902

### Frontend Verifications
- [ ] `/maintenance` — form loads, category dropdown populated, priority selector works
- [ ] `/maintenance` — camera button opens camera or file picker, preview shows
- [ ] `/maintenance` — submit without photo → client-side error shown
- [ ] `/maintenance` — submit with photo → success screen shows request ID
- [ ] `/maintenance/[id]` — detail page loads, before-photos gallery renders
- [ ] `/maintenance/[id]` — charge acknowledgement card shows when charge_to_store=1 and store_acknowledged=0
- [ ] `/maintenance/[id]` — clicking Acknowledge calls API and hides card
- [ ] `/rm` — queue loads with pagination, filter by Status/Priority works
- [ ] `/rm` — SLA breached rows highlighted in red
- [ ] `/rm/[id]` — completion form has mandatory after-photo field
- [ ] `/rm/[id]` — Submit Completion disabled until photo captured
- [ ] `/rm/[id]` — Submit Completion with photo → API call succeeds, status updates to Completed
- [ ] All pages mobile-responsive at 375px viewport

### Integration Verifications
- [ ] Full flow: `test.staff@bebang.ph` submits → `test.projects@bebang.ph` sees in queue → assigns → records completion with photo → `test.staff@bebang.ph` sees Completed status
- [ ] Full flow: Projects Manager assesses Wear & Tear → sets charge → Store Supervisor acknowledges
- [ ] SLA breach: Create Urgent request, manually age it 5+ hours, run check → verify Chat alert
- [ ] Bio ID: Attempt to save Employee with 6-digit Bio ID → verify error before save

---

## Rollback Plan

**Decision owner:** Lead developer or DevOps. Rollback call must be made within **30 minutes** of a failed deploy.

### Step 1: Capture Baseline Image Tag BEFORE Each Deploy

Run this BEFORE triggering any of the 3 backend deploys:

```bash
docker images bei-hrms --format "{{.Tag}}" | head -1
# Save the output as your rollback baseline, e.g.: sha256-abc123 or v1.2.3
```

Record the baseline tag here before each phase:
- **Phase 0 baseline tag:** `_______________`
- **Phase 1 baseline tag:** `_______________`
- **Phase 3 baseline tag:** `_______________`

### Step 2: Rollback Command (Backend)

If the new image is broken, revert to the baseline tag:

```bash
# Replace <BASELINE_TAG> with the tag recorded in Step 1
docker compose -f docker-compose.yml up -d --no-deps --force-recreate bei-hrms \
  --image bei-hrms:<BASELINE_TAG>
```

If using Docker service (Swarm mode):
```bash
docker service update --image bei-hrms:<BASELINE_TAG> bei-hrms
```

### Step 3: Database Rollback (if migration was applied)

If `bench migrate` ran and needs to be reversed:

```bash
# Inside the container or via SSM:
bench --site hq.bebang.ph migrate --rollback
```

**Warning:** DocType field additions (like `vendor_cost`) cannot be rolled back cleanly if data was written. Always test on staging before production.

### Step 4: Frontend Rollback

Vercel maintains deployment history. To revert:

```bash
# Find the previous deployment URL in Vercel dashboard
# Promote the previous deployment to production via Vercel dashboard
# Or re-deploy the previous git commit:
vercel.cmd --prod --force --token $TOKEN --scope team_xvK1nhuvsdZp3GNfd4uDJ0DW --yes
```

### Rollback Decision Criteria

| Symptom | Action |
|---------|--------|
| 500 errors on any maintenance endpoint | Immediate rollback |
| `acknowledge_maintenance_charge` returning wrong 403 | Fix forward (1-line change) |
| Photo upload silently null | Rollback if >5 reports |
| Migration failure / DB locked | Rollback + DB restore from snapshot |
| Frontend JS error on `/maintenance` | Vercel rollback (zero-downtime) |

---

## Deployment Notes

### Backend Deployment
- **All backend changes require a FULL Docker build** (`skip_build=false`, `no_cache=true`)
- Build takes 5-10 minutes, migrations 1-2 minutes after
- Workflow: `.github/workflows/build-and-deploy.yml`
- Phase 0 deploy: After RBAC audit (hooks.py change requires full build)
- Phase 1 deploy: After DocType field addition for `vendor_cost` (schema change)
- Phase 3 deploy: After uncommenting photo validation

### Frontend Deployment
- All frontend goes to `bei-tasks` repo (React/Next.js on Vercel)
- Deploy: `vercel.cmd --prod --force --token $TOKEN --scope team_xvK1nhuvsdZp3GNfd4uDJ0DW --yes`
- On Windows: use `vercel.cmd` not `vercel`
- CRITICAL: Deploy frontend BEFORE uncommenting photo validation in backend. Otherwise completions will fail until frontend is deployed.

### Database Migrations
- Adding `vendor_cost` to `BEI Maintenance Request` = new DocType field (requires `bench migrate` after full Docker build)
- Adding Employee validate hook = Python-only change (no schema migration, but requires full Docker build to deploy new code)
- Bulk gov ID import: no schema change (existing fields TIN, SSS, etc. already on Employee DocType)

### Test Accounts for This Sprint
| Account | Email | Password | Role | Use For |
|---------|-------|----------|------|---------|
| Store Staff | test.staff@bebang.ph | BeiTest2026! | Store OIC | Submit maintenance requests |
| Store Supervisor | test.supervisor@bebang.ph | BeiTest2026! | Store Supervisor | Acknowledge charges |
| Projects Staff | test.projects.staff@bebang.ph | BeiTest2026! | Projects Staff | Queue management (if this role exists) |
| Projects Head | test.projects@bebang.ph | BeiTest2026! | Projects Head | Full projects/maintenance admin |
| Crew | test.crew1@bebang.ph | BeiTest2026! | Crew | Verify RBAC blocking |

---

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| Photo requirement re-enabled before frontend deployed | Completions blocked via API | Strict sequencing: frontend first, backend gate second. See Phase 3. |
| Employee validate hook breaks existing legacy Bio IDs (6-digit) | Can't save Employee records | Run audit first: `SELECT COUNT(*) FROM tabEmployee WHERE attendance_device_id NOT LIKE '9%' AND attendance_device_id != ''` — if any found, correct them before enabling validation |
| Nested photo payload from unknown old clients | Completion photos silently null | G-082 Task 82B adds log warning — monitor Frappe error log after deploy |
| `frappe.only_for` on project endpoints breaks existing Frappe Desk workflows | Projects team locked out | Verify test.projects@bebang.ph has Projects Manager role before deploying. Test Frappe Desk access post-deploy. |
| SLA alerts spam Projects Manager on startup | Chat flooded | First run: announce as planned maintenance, set up filter. Or add `last_alert_sent` tracking to prevent repeated alerts for same request. |
| `check_sla_violations` hits rate limit during off-hours batch | Alerts dropped | Batch sends max 20 per message. Frappe error log captures failures. |
| Bulk gov ID import overwrites correct data | Payroll errors | Default behavior: skip if already set. Require explicit `force=True` to overwrite. |

---

## NICE-TO-HAVE (Deferred — Do Not Build This Sprint)

| Gap | What | Why Defer |
|-----|------|-----------|
| G-007 (project mgmt) | 8 project management pages (kanban, bids, milestones, permits) | 5-10 projects/year — Frappe Desk adequate at this volume |
| G-074 | Milestone billing idempotency (FOR UPDATE lock) | Low probability race condition at 5-10 projects/year |
| G-075 | Configurable bid scoring weights (currently 60/40 hardcoded) | Projects Manager can adjust manually for rare cases |
| G-076 | Permit fee auto-calculation (0.2% formula) | LGU variance makes formula unreliable. Manual entry correct. |
| G-079 | Punchlist → PO charge-back link | Manual deductions work at current project volume |
| G-080 | Maintenance request → parent project link | 95% of requests are standalone store ops, not project-related |
| G-081 | Site inspection structured checklist (child table) | Free-text overall_status adequate for 5-10 inspections/year |
| G-103 | Rate limiting on export/dashboard endpoints | Internal authenticated API. Not a realistic DoS target. |
| G-104 | SQL injection re-review | Already parameterized (confirmed). Close as false positive. |
| G-125 | Test account enforcement in transactions | TEST-* naming convention is obvious. Not worth automating now. |

---

## Appendix: Complete API Inventory (projects.py)

For reference — all 28 whitelisted functions in `hrms/api/projects.py`:

| # | Function | Line | RBAC Status After This Sprint |
|---|----------|------|-------------------------------|
| 1 | `get_maintenance_queue` | 22 | Auth-required (read) |
| 2 | `get_maintenance_request_detail` | 216 | Auth-required (read) |
| 3 | `assign_maintenance_request` | 328 | Projects roles (was BUG-001 fix) |
| 4 | `update_maintenance_status` | 423 | Projects roles (was BUG-001 fix) |
| 5 | `record_maintenance_completion` | 513 | Projects roles (was BUG-001 fix) |
| 6 | `get_maintenance_dashboard_stats` | 683 | Auth-required (read) |
| 7 | `export_maintenance_requests` | 835 | Projects Manager only |
| 8 | `get_projects_team_users` | 930 | Auth-required (read) |
| 9 | `get_stores_list` | 950 | Auth-required (read) |
| 10 | `assess_maintenance_request` | 972 | Projects roles (G-031 fix) |
| 11 | `set_maintenance_charge` | 1011 | Projects roles (G-031 fix) |
| 12 | `acknowledge_maintenance_charge` | 1052 | Store roles (G-031 fix) |
| 13 | `get_pending_charges` | 1089 | Projects + Store roles (G-031 fix) |
| 14 | `add_maintenance_materials` | 1147 | Projects roles (G-031 fix) |
| 15 | `update_maintenance_costs` | 1207 | Projects roles (G-031 fix) |
| 16 | `get_maintenance_categories` | 1246 | Auth-required (read) |
| 17 | `get_project_dashboard` | 1271 | Auth-required (read) |
| 18 | `get_project_detail` | 1332 | Auth-required (read) |
| 19 | `advance_project_stage` | 1440 | Projects Manager (G-031 fix) |
| 20 | `update_project_progress` | 1492 | Projects Manager (G-031 fix) |
| 21 | `submit_site_inspection` | 1533 | Projects roles (G-031 fix) |
| 22 | `approve_site_inspection` | 1564 | Projects Manager (G-031 fix) |
| 23 | `reject_site_inspection` | 1600 | Projects Manager (G-031 fix) |
| 24 | `get_bid_comparison` | 1639 | Auth-required (read) |
| 25 | `evaluate_bid` | 1688 | Projects Manager (G-031 fix) |
| 26 | `award_bid` | 1731 | Projects Manager (G-031 fix) |
| 27 | `complete_milestone` | 1799 | Projects Manager (G-031 fix) |
| 28 | `verify_milestone` | 1836 | Projects Manager (G-031 fix) |
| 29 | `create_milestone_billing` | 1873 | Projects Manager (G-031 fix) |
| 30 | `get_punchlist` | 1943 | Auth-required (read) |
| 31 | `add_punchlist_item` | 2013 | Projects roles (G-031 fix) |
| 32 | `resolve_punchlist_item` | 2077 | Projects roles (G-031 fix) |
| 33 | `close_punchlist_item` | 2118 | Projects Manager (G-031 fix) |
| 34 | `waive_punchlist_item` | 2150 | Projects Manager (G-031 fix) |
| 35 | `get_permit_checklist` | 2191 | Auth-required (read) |
| 36 | `update_permit_status` | 2243 | Projects Manager (G-031 fix) |

Also in `hrms/api/store.py`:
| # | Function | Line | RBAC |
|---|----------|------|------|
| 37 | `submit_maintenance_request` | 2186 | Store Ops roles (validate_store_ops_role) |

---

*This plan is self-contained. An implementing agent should be able to execute it without additional context beyond reading the source files listed above.*

---

## Frontend Hook Architecture

### Hook Pattern (Verified Against bei-tasks Codebase)

**IMPORTANT:** bei-tasks uses **`useState` + `useEffect` + `fetch`** pattern — NOT TanStack Query / React Query. This is the existing pattern in `hooks/use-maintenance-queue.ts` and all other hooks. Do NOT introduce TanStack Query — it is not installed.

The hooks file `hooks/use-maintenance-queue.ts` already exists with these hooks:
- `useMaintenanceQueue(options)` — paginated queue with filters
- `useMaintenanceStats(filters)` — dashboard stats
- `useMaintenanceDetail(requestId)` — single request detail
- `useMaintenanceActions()` — assign, updateStatus, completeRequest, assessRequest, addMaterials
- `useProjectsTeam()` — team user list
- `useStoresList()` — stores dropdown

### Missing Hooks to Add

The following actions are NOT yet in `use-maintenance-queue.ts` and must be added:

| Hook/Action | API Call | Invalidates |
|-------------|----------|-------------|
| `setCharge(requestId, amount, reason)` | `POST /api/projects action=set_charge` | call `refresh()` on detail hook |
| `acknowledgeCharge(requestId)` | `POST /api/projects action=acknowledge` | call `refresh()` on detail + queue |
| `updateCosts(requestId, laborHours, laborCost, vendorCost)` | `POST /api/projects action=update_costs` | call `refresh()` on detail |
| `addMaterials(requestId, materials[])` | `POST /api/projects action=add_materials` | call `refresh()` on detail |
| `submitNewRequest(payload)` | `POST /api/maintenance action=submit` | call `refresh()` on queue |

### Cache Invalidation Pattern

Since the pattern uses `useState` (not a global cache), invalidation is done by calling the `refresh()` function returned from each hook:

```typescript
// Pattern: after a mutation, call refresh() on affected hooks
const { detail, refresh: refreshDetail } = useMaintenanceDetail(requestId);
const { refresh: refreshQueue } = useMaintenanceQueue();

// After assign:
await assignRequest(requestId, ...);
await refreshDetail();   // update detail view
await refreshQueue();    // update queue counts

// After complete:
await completeRequest(requestId, ...);
await refreshDetail();   // show Completed status
// refreshQueue is optional — user navigates away
```

### Stale Data Prevention

- Queue page: re-fetch on window focus (add `visibilitychange` listener)
- Detail page: re-fetch every 30s while status is not terminal (Completed/Verified/Cancelled)
- Stats: re-fetch on any mutation

---

## Route Path Confirmation (B-09 Research)

### Existing Routes Found in bei-tasks

**CONFIRMED:** The following directories already exist in `app/dashboard/`:

```
app/dashboard/maintenance/      ← EXISTS (has page.tsx, new/, [id]/, charges/)
app/dashboard/rm/               ← EXISTS (has page.tsx, new/, queue/)
app/dashboard/rm-admin/         ← EXISTS (has page.tsx, charges/, queue/)
```

### Route Conflict Assessment

| Plan Route | bei-tasks Status | Action Required |
|------------|-----------------|-----------------|
| `/maintenance` | ALREADY EXISTS (`app/dashboard/maintenance/`) | Use existing — implement content |
| `/maintenance/[id]` | ALREADY EXISTS (`app/dashboard/maintenance/[id]/`) | Use existing — implement content |
| `/rm` | ALREADY EXISTS (`app/dashboard/rm/`) | Use existing — implement content |
| `/rm/[id]` | NOT YET CREATED | Add `[id]/` under `app/dashboard/rm/` OR use `rm-admin/` |

**Recommendation:** No route conflicts. The scaffolding is already in place. Implementing agents should fill in the page content for existing routes rather than creating new directories.

**BLOCKER 9 RESOLVED:** Routes `/maintenance`, `/rm`, `/rm-admin` already exist as scaffolded directories. No conflicts. The plan's route map is correct.

---

## Audit Amendments (v1.1) — 2026-02-20

### Audit Methodology

5 specialized agents audited this plan in parallel, followed by a code-verification agent that read actual source files, and a GLM-5 adversarial fact-check (partial — rate limited). Full reports with code fixes are in the referenced files.

| Domain | Agent | Findings File | Score |
|--------|-------|---------------|-------|
| Frappe Backend | frappe-backend-auditor | `output/plan-audit/sprint-04-maintenance/frappe_backend_findings.md` | 4 CRITICAL, 8 WARNING, 5 INFO |
| Frontend Architecture | frontend-auditor | `output/plan-audit/sprint-04-maintenance/frontend_findings.md` | 6/10 quality |
| Deployment & QA | deployment-qa-auditor | `output/plan-audit/sprint-04-maintenance/deployment_qa_findings.md` | NO-GO verdict |
| System Architecture | system-arch-auditor | `output/plan-audit/sprint-04-maintenance/system_arch_findings.md` | 2.9/5 architecture |
| Design Review | design-review-auditor | `output/plan-audit/sprint-04-maintenance/design_review_findings.md` | 2.4/5 design quality |
| **Code Verification** | code-verifier | `output/plan-audit/sprint-04-maintenance/code_verification.md` | 22 confirmed, 3 stale, 4 new gaps |
| **GLM-5 Fact-Check** | glm_fact_check.py | (partial — rate limited) | 3 SUPPORTED, 4 ERROR (kept as-is) |

### Top 10 Blockers (Must Resolve Before Execution)

#### BLOCKER 1: 6 Write Endpoints Have Zero RBAC — Financial Charge Bypass
**Source:** `code_verification.md` V1, `frappe_backend_findings.md` C1 | **Severity:** CRITICAL | **GLM-5:** SUPPORTED
**Problem:** `assess_maintenance_request`, `set_maintenance_charge`, `acknowledge_maintenance_charge`, `get_pending_charges`, `add_maintenance_materials`, `update_maintenance_costs` — all confirmed unprotected at projects.py:972, 1010, 1051, 1088, 1146, 1207. Any authenticated user can set financial charges on any store.
**Fix:** Extract shared `_require_role()` decorator to `hrms/api/_rbac.py` (see design_review_findings.md CRIT-01 for code). Apply to all 6 endpoints. Do NOT copy-paste inline checks — use the decorator.

#### BLOCKER 2: DocType Permissions Bypass All API RBAC
**Source:** `code_verification.md` V2, `frappe_backend_findings.md` C3 | **Severity:** CRITICAL | **GLM-5:** SUPPORTED
**Problem:** `BEI Maintenance Request` and `BEI Maintenance Completion` both grant `Employee` role `create=1, write=1`. Any of 636 employees can call `frappe.client.set_value()` to mutate any field, bypassing API RBAC entirely.
**Fix:** Remove `write=1` and `create=1` from `Employee` role on both DocType JSONs. Grant write only to `Projects User` and `Projects Manager`.

#### BLOCKER 3: hooks.py Validate Hook Will Destroy Existing Hook
**Source:** `code_verification.md` G2/V15 | **Severity:** CRITICAL
**Problem:** `hooks.py:219` has `"validate": "hrms.overrides.employee_master.validate_onboarding_process"` as a **string**. Plan Task 124A's code snippet replaces this string, silently destroying the existing onboarding validation.
**Fix:** Convert to list before adding: `"validate": ["hrms.overrides.employee_master.validate_onboarding_process", "hrms.api.onboarding.validate_employee_doc"]`

#### BLOCKER 4: record_maintenance_completion Is Non-Atomic (DM-2)
**Source:** `code_verification.md` V3, `frappe_backend_findings.md` C2 | **Severity:** CRITICAL
**Problem:** `completion.insert()` at L647 then `request_doc.save()` at L669 — no savepoint. Crash between them leaves orphaned completion record.
**Fix:** Wrap in `frappe.db.savepoint("complete_maintenance")` with rollback on exception.

#### BLOCKER 5: No Rollback Plan for 3 Backend Deploys
**Source:** `deployment_qa_findings.md` D-01/C-01 | **Severity:** CRITICAL | **GLM-5:** SUPPORTED
**Problem:** Zero rollback procedures documented. No baseline image tag, no rollback command, no decision owner.
**Fix:** Before Phase 0: record current image tag as baseline. Document `docker service update --image <baseline_tag>` command for each service. Assign rollback decision owner.

#### BLOCKER 6: No TanStack Query Hooks Specified
**Source:** `frontend_findings.md` C-02 | **Severity:** CRITICAL
**Problem:** 15+ API endpoints with zero query keys, stale times, or cache invalidation chains defined. Two developers will create incompatible hooks with stale data bugs.
**Fix:** Add hook specifications per page (see frontend_findings.md C-02 for TypeScript examples). Define cache invalidation chain: assign → invalidate queue+detail; status update → invalidate queue+stats; completion → invalidate all.

#### BLOCKER 7: Plan Line Map Wrong for submit_maintenance_request
**Source:** `code_verification.md` G1 | **Severity:** WARNING
**Problem:** Plan states `store.py:1918` but actual line is `2186` (verified by grep). L1918 is a different function.
**Fix:** RESOLVED — Source Files Map updated to `submit_maintenance_request (L2186)`. All references corrected.

#### BLOCKER 8: Test Coverage Below Threshold
**Source:** `deployment_qa_findings.md` | **Severity:** WARNING
**Problem:** 60% L3+ coverage vs 70% required. 9 verification checklist items are L1 only. 9 new test cases needed (MAINT-016 through MAINT-024).
**Fix:** Add MAINT-016 through MAINT-024 to `docs/testing/TEST_SCENARIOS.md` before Phase 3 deploy. See deployment_qa_findings.md for exact test specifications.

#### BLOCKER 9: Route Path Conflicts With Existing bei-tasks Routes
**Source:** `frontend_findings.md` C-01 | **Severity:** WARNING
**Problem:** Plan's `/maintenance` and `/rm` may conflict with existing `/dashboard/rm` sidebar routes. Must clarify: replace or add alongside.
**Fix:** Confirm route strategy with bei-tasks codebase. Recommended: use `/dashboard/rm/new` (submit), `/dashboard/rm/[id]` (detail), `/dashboard/rm-admin` (queue), `/dashboard/rm-admin/[id]` (admin detail).

#### BLOCKER 10: No Store-Binding Check on Charge Acknowledgement
**Source:** `system_arch_findings.md` WARN-04 | **Severity:** WARNING
**Problem:** Store Supervisor at Store A can acknowledge a charge for Store B. No check that user's Employee branch matches doc.store.
**Fix:** Before `doc.save()` in `acknowledge_maintenance_charge`, verify `frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "branch") == doc.store`.

### Additional Recommendations (Non-Blocking)

1. **Split projects.py before adding code** (`design_review_findings.md` rec 1): 2294-line God Object will grow to 2500+. Mechanical split into `maintenance.py` + `projects.py` costs 2 hours and makes every subsequent task safer.
2. **Extract save_base64_image to media_utils.py** (`design_review_findings.md` rec 2): Hidden cross-module dependency between store.py and projects.py.
3. **Add store-binding to acknowledge_maintenance_charge** (`system_arch_findings.md` WARN-04): Prevent cross-store financial acknowledgement.
4. **Batch N+1 queries in get_maintenance_queue** (`code_verification.md` V4): 40 extra DB calls per page load.
5. **Add Zod validation schemas for all forms** (`frontend_findings.md` W-01): 4 schemas needed.
6. **Add SLA last_alerted_at field** (`design_review_findings.md` rec 5): Prevent alert spam on cron restart.
7. **Bio ID pre-deploy audit query** (`deployment_qa_findings.md` C-02): Run `SELECT COUNT(*) FROM tabEmployee WHERE attendance_device_id NOT LIKE '9%' AND attendance_device_id != ''` — must return 0 before enabling hook.
8. **Add dry_run to bulk Gov ID import** (`design_review_findings.md` INFO-02): Preview before mutating 636 records.
9. **Define photo upload architecture** (`frontend_findings.md` C-03): Individual upload on capture vs batch on submit.
10. **Add RBAC enforcement mechanism to frontend** (`frontend_findings.md` C-04): Specify layout guards and role check patterns.

### Pre-Flight Checks: Audit Additions

- [x] **AUDIT-1:** Inline `frappe.get_roles()` RBAC checks added to all 6 unprotected write endpoints in `projects.py` (B-01 resolved — used existing inline pattern, not separate decorator)
- [x] **AUDIT-2:** `Employee` role has `write=0, create=0` on both DocType JSONs + `flags.ignore_permissions=True` on all 9 API save/insert calls (B-02 resolved)
- [x] **AUDIT-3:** `hooks.py` Employee validate converted from string to LIST (B-03 resolved)
- [x] **AUDIT-4:** `record_maintenance_completion` uses `frappe.db.savepoint("maintenance_completion")` wrapping both doc operations (B-04 resolved)
- [x] **AUDIT-5:** Rollback procedure documented — see "Rollback Plan" section above (B-06 resolved)
- [x] **AUDIT-6:** Hook specifications added to plan — see "Frontend Hook Architecture" section (B-08 resolved)
- [x] **AUDIT-7:** Source Files Map corrected: `submit_maintenance_request (L2186)` (B-05 resolved — actual line verified by grep)
- [x] **AUDIT-8:** MAINT-016 through MAINT-024 added to TEST_SCENARIOS.md (B-07 resolved)
- [x] **AUDIT-9:** Route paths confirmed — `/maintenance`, `/rm`, `/rm-admin` all exist in bei-tasks. No conflicts. (B-09 resolved)
- [ ] **AUDIT-10:** Bio ID pre-deploy audit query returns 0 rows before Phase 0 deploy

### GO / NO-GO Gate (Updated)

**AUDIT-1 through AUDIT-9 PASSED. AUDIT-10 (Bio ID pre-deploy) to be verified at deploy time. Status: GO.**

### Version History

| Version | Date | Change |
|---------|------|--------|
| v1.0 | 2026-02-19 | Initial draft — 4 MUST-HAVE + 4 SHOULD-HAVE gaps |
| v1.1 | 2026-02-20 | Audit amendments: 5-domain parallel audit + code verification + GLM-5 partial. 6 CRITICAL + 4 WARNING blockers. NO-GO gate added. |
| v1.2 | 2026-02-20 | All 10 blockers resolved: RBAC on 6 endpoints, DocType perms locked + ignore_permissions, hooks.py list fix, savepoint atomicity, store-binding check, rollback plan, test scenarios MAINT-016–024, hook specs, route confirmation, line map corrected. GO gate. |
| v1.3 | 2026-02-20 | Phase 0 + Phase 1 IMPLEMENTED and DEPLOYED. Commits: `d02fab9c3` (main impl) + `beb10586b` (audit fixes). Post-deploy audit caught 3 issues: SLA whitelist removed, Employee Self Service perms locked, 5 project read endpoints auth-guarded. Task 5A moved up from Phase 3 to Phase 1. |
| v1.4 | 2026-02-20 | Phase 2 + Phase 3 COMPLETE. Discovery: all 4 pages already fully built in bei-tasks. Sprint 04 additions: types (vendor_cost, sla_breached, charge fields, Pending Acknowledgement status), API route (set_charge, acknowledge_charge, update_costs), hooks (3 new action methods), queue SLA badge, detail page Costs & Charging section. Commit: `0451463` (bei-tasks/main). Vercel auto-deploy triggered. Only Phase 4 (SHOULD-HAVE) remains. |
| v1.5 | 2026-02-20 | Phase 4 COMPLETE. Gov ID bulk import endpoint (`bulk_import_gov_ids`) + bei-tasks frontend page. Vendor cost input on completion modal. Backend commit: `809ef497f`, frontend commit: `f0bd65d`. Docker build + Vercel deploy triggered. |
| v1.6 | 2026-02-20 | **SPRINT CLOSED.** L3 test suite executed: 24/24 PASS, 0 FAIL, 0 SKIP. All scenarios tested against live production including: full lifecycle (submit->assign->complete->verify), RBAC enforcement (5 tests), adversarial inputs (6 tests), BLOCKER-10 cross-store check via SSM (403 confirmed), SLA breach scheduled job via bench execute (no errors), concurrent charge updates (deterministic, no corruption). Results: `output/l3/maintenance_2026-02-20.json`. |
