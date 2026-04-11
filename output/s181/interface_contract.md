# S181 Backend ⇄ Frontend Interface Contract (FROZEN)

**Sprint:** S181 — Company Master Extension
**Backend lane:** `hrms` repo, branch `s181-company-master-extension`
**Frontend lane:** `bei-tasks` repo, branch `s181-company-master-frontend`
**Frozen at:** end of backend Phase 2B (commit containing `hrms/api/company_master.py`)

This file is the single source of truth for every field name and endpoint
that the frontend lane may read or write. No frontend code in Phase 3B / 3C
may reference anything outside this contract. If a frontend requirement
needs something not listed here, the frontend lane **pauses**, the backend
lane adds it, this document is updated, and the frontend resumes. This is
the `blocked_until` gate for Blocker 8.

---

## Proxy pattern

All calls use the existing bei-tasks proxy at
`/api/frappe/api/method/<module>.<function>`, the same convention used by
`bei-tasks/lib/queries/hr-employee-detail.ts`, `hr-payroll.ts`, and every
other integration in bei-tasks.

`/api/resource/Company/<name>` is **NOT** permitted (Blocker 6). There are
no exceptions.

---

## Endpoints

### 1. `hrms.api.company_master.list_companies`

**Method:** POST (Frappe whitelist convention)
**Purpose:** Power the Company Master list page at `/dashboard/bd/companies`.

**Arguments:**
| Name | Type | Required | Description |
|---|---|---|---|
| `filters` | dict (JSON) | No | Any combination of: `entity_category`, `store_ownership_type`, `operational_status`, `region` — each matches exactly. Missing = no filter. |
| `search` | string | No | Substring match on `name`, `company_name`, `city`. |

**Response:** JSON array of rows. Each row is the minimum the list needs:

```json
[
  {
    "name": "Ayala Evo - Bebang Enterprise Inc.",
    "company_name": "Ayala Evo - Bebang Enterprise Inc.",
    "abbr": "AYE",
    "entity_category": "Store",
    "store_ownership_type": "Company Owned",
    "operational_status": "Active",
    "city": "Makati",
    "province": "Metro Manila",
    "region": "NCR",
    "mosaic_location_id": "12345",
    "first_provision_done": 1
  }
]
```

Sorted by `entity_category` then `name`. Does NOT return child tables — the
list page must call `get_company(name)` for the full detail.

---

### 2. `hrms.api.company_master.get_company`

**Purpose:** Power the fullscreen Company Master detail dialog.

**Arguments:** `name` (string, required)

**Response:** Full Company document as dict (`doc.as_dict()`), including
the three child tables (`stakeholders`, `adms_devices`, `compliance_documents`)
and a computed `expiry_summary`:

```json
{
  "name": "...",
  "company_name": "...",
  "abbr": "...",
  "tax_id": "...",
  "branch_tin": "...",
  "...": "...",
  "stakeholders": [ {...} ],
  "adms_devices": [ {...} ],
  "compliance_documents": [ {...} ],
  "first_provision_done": 1,
  "expiry_summary": { "valid": 8, "expiring": 2, "expired": 1 }
}
```

`expiry_summary` is computed at query time from `compliance_documents[*].expiry_date`:
- `expired` — `expiry_date < today`
- `expiring` — `expiry_date` within the next 30 days (inclusive)
- `valid` — `expiry_date` beyond 30 days OR null
- Rows with no `expiry_date` are ignored in all three counts.

**Errors:** throws if the caller lacks `Company.read` permission on `name`.

---

### 3. `hrms.api.company_master.update_company_section`

**Purpose:** Save a section of the Company detail dialog (one
Edit modal → one API call). Mass-assignment safe.

**Arguments:**
| Name | Type | Required | Description |
|---|---|---|---|
| `name` | string | Yes | Company docname |
| `section` | string | Yes | One of: `bir_legal`, `location`, `operations`, `contacts`, `compliance`, `bd_pipeline`. Unknown section throws. |
| `payload` | dict (JSON) | Yes | Keyed by fieldname. Any field NOT in `EDITABLE_SECTIONS[section]` is silently dropped — the frontend should not rely on this to filter unknown fields, but it is safe against accidental overreach. |

**`EDITABLE_SECTIONS` map (authoritative — mirror in
`bei-tasks/lib/queries/company-master.ts`):**

```typescript
const EDITABLE_SECTIONS = {
  bir_legal: [
    "company_name", "tax_id", "branch_tin", "bir_rdo_code",
    "bir_registration_date", "sec_registration_no", "sec_registration_date",
  ],
  location: [
    "full_address", "city", "province", "region", "mall_or_building",
    "gps_latitude", "gps_longitude", "google_maps_place_id",
  ],
  operations: [
    "entity_category", "store_ownership_type", "operational_status",
    "opening_date", "operating_hours", "pos_system", "mosaic_location_id",
  ],
  contacts: [
    "store_manager", "store_manager_phone", "area_supervisor", "regional_manager",
  ],
  compliance: [
    "drive_folder_url",
  ],
  bd_pipeline: [
    "pipeline_status", "target_opening_date", "lease_start_date",
    "lease_end_date", "lease_monthly_rent", "revenue_share_pct",
  ],
} as const;
```

**Note:** the `compliance` section only exposes `drive_folder_url`. Per-row
document mutations use `upsert_compliance_document` / `delete_compliance_document`
below. The ADMS Devices table uses `upsert_adms_device` /
`delete_adms_device`. The Stakeholders table (from S178) is edited via
Frappe's standard child-table save-on-parent flow — Phase 3C re-uses the
existing bei-tasks pattern for it.

**Response:** `{ok: true, updated_fields: ["..."]}` or
`{ok: true, noop: true, updated_fields: []}` if payload was empty after
allow-list filtering.

**Errors:** throws on missing write permission or unknown section.

---

### 4. `hrms.api.company_master.upsert_compliance_document`

**Purpose:** Create or update a row in `compliance_documents`.

**Arguments:**
| Name | Type | Required | Description |
|---|---|---|---|
| `company` | string | Yes | Company docname |
| `row` | dict (JSON) | Yes | See row shape below. |

**Row shape:**

```typescript
interface ComplianceDocumentRow {
  name?: string;  // present → update that row; absent → append new
  document_type: "Lease Agreement" | "Business Permit" | "BIR Form 2303"
               | "Fire Safety Certificate" | "Sanitary Permit"
               | "SEC Certificate" | "Other";
  document_name?: string;
  file?: string;          // Frappe Attach URL
  drive_file_url?: string; // must start with https://drive.google.com/ or https://docs.google.com/
  status?: "Valid" | "Expired" | "Pending Renewal" | "Not Required";
  issue_date?: string;    // YYYY-MM-DD
  expiry_date?: string;   // YYYY-MM-DD
  notes?: string;
}
```

**Validation enforced at the API layer (mirrors the
`BEI Company Document` controller `validate()`):**
- At least ONE of `file` or `drive_file_url` must be set; throws otherwise.
- If `drive_file_url` is set, it must start with `https://drive.google.com/`
  or `https://docs.google.com/`; throws otherwise.

The frontend Save button **MUST** mirror both checks so users never hit
the backend throw under normal conditions. This keeps UI + backend
behaviour aligned (Blocker 7's dual upload/Drive link pattern).

**Response:** `{ok: true}`

---

### 5. `hrms.api.company_master.delete_compliance_document`

**Arguments:** `company` (string), `row_name` (string)
**Response:** `{ok: true}`
**Errors:** throws on missing write permission.

---

### 6. `hrms.api.company_master.upsert_adms_device`

**Row shape:**

```typescript
interface AdmsDeviceRow {
  name?: string;
  device_serial: string;   // REQUIRED. Enforced unique across all Companies.
  device_name?: string;
  bio_device_id?: string;
  ip_address?: string;
  notes?: string;
  // adms_enrolled + enrollment_date are read-only — set by the worker.
}
```

**Cross-company uniqueness:** if `device_serial` is already assigned to a
different Company (`parent != company`), the backend throws with
"Device serial X is already assigned to company Y". The frontend grid
should surface this error message directly in the row-level validation.

**Side effect:** saving triggers the `auto_enroll_adms_devices` hook,
which enqueues a background job (`frappe.enqueue` → `short` queue) that
calls the ADMS receiver and flips `adms_enrolled = 1` on success. The
frontend should refetch every ~15s while at least one row has
`adms_enrolled = 0` to surface enrollment state transitions, then stop
polling when all rows are enrolled or after a reasonable cap
(Phase 3C task 3C.2 specifies 15s polling).

---

### 7. `hrms.api.company_master.delete_adms_device`

**Arguments:** `company` (string), `row_name` (string)
**Response:** `{ok: true}`

---

### 8. `hrms.api.company_master.retry_provision`

**Purpose:** Re-run `auto_provision_company` for a Company whose
first-provision attempt failed (rolled back at the savepoint, sentinel
left unset).

**Arguments:** `company` (string, required)

**Visibility gate:** the "Retry Provisioning" pill in the bei-tasks detail
dialog should only render when `first_provision_done == 0` on the Company
being displayed. After a successful retry, `first_provision_done` flips
to 1 and the pill disappears on the next refetch.

**Response:** `{ok: true, company: "..."}`

**Errors:** throws on missing write permission. Any failures inside
`auto_provision_company` itself are caught by its internal try/except
and surfaced via `frappe.msgprint` on the backend — the retry response
is still `{ok: true, company}` even if the underlying provisioning
rolled back, because the retry call itself succeeded. The frontend
should check `first_provision_done` in the subsequent `get_company`
refetch to confirm the retry actually worked.

---

## Read-only fields the frontend displays

These are returned by `get_company` but are NOT in `EDITABLE_SECTIONS` and
must not be written via `update_company_section`:

| Field | Purpose |
|---|---|
| `first_provision_done` | Gates the Retry Provisioning pill visibility |
| `name` | Frappe docname (read-only after creation) |
| `abbr` | Used in Warehouse / Cost Center naming — read-only after provision |

The Company name (`name`) and abbreviation (`abbr`) are set at creation
time through a separate small dialog ("+ New Company") that the list
page exposes. Once provisioned, they cannot be edited via S181 endpoints
— Frappe's rename-doctype flow is the only supported path, and S181 does
not wrap it.

---

## Role-based access control

**Frappe-side:** every endpoint runs `frappe.has_permission("Company",
"read" | "write", doc=name)` on the specific Company before touching it.
Permissions come from Frappe's standard Role Permissions Manager.

**bei-tasks-side:** `bei-tasks/lib/roles.ts` should add a `company-master`
module entry with `allowedRoles: ["System Manager", "Accounts Manager",
"Business Development", "BD Manager"]` and `section: "Operations"`. The
"Business Development" and "BD Manager" roles must exist in Frappe — if
they don't yet, a one-line seed script creates them as part of Phase 3B
deployment.

**Sidebar placement:** under the existing "Operations" section header
between Store Operations and Warehouse. Not under HR (it is not an
employee-data surface).

---

## Sentry observability

Every endpoint in `hrms/api/company_master.py` calls
`set_backend_observability_context(module="company", action=...,
mutation_type=...)` as its first meaningful line per DM-7. This means
every Company Master API call in production will show up in Sentry's
`bei-hrms` project with the correct module + action tags for filtering.

The frontend lane does NOT need manual Sentry instrumentation on the
corresponding route handlers — Next.js API routes are auto-instrumented
by `@sentry/nextjs` in bei-tasks.

---

## Change control

Any change to this contract (new field, new endpoint, changed shape,
changed validation) must be accompanied by:

1. The backend edit in `hrms/api/company_master.py`.
2. An update to this document in the same commit.
3. If the frontend lane has already started, a notification to the
   frontend lane with the diff.

Silent drift between `company_master.py` and this file is a process
violation and will cause the frontend lane to build against a stale
spec.
