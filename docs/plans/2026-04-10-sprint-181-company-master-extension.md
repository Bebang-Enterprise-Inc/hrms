# S181 — Company Master Extension: Auto-Provisioned Branches

> **Context in one line:** Extend the Frappe Company DocType into a full Company Master with BIR/legal, location, operations, contacts, compliance documents, and BD pipeline fields — and wire an `on_update` sentinel-gated hook that auto-provisions COA (27-account Sales template + 20-account Balance Sheet skeleton), Warehouse, Cost Center, default accounts, and BKI Customer so that when BD creates a new branch, the entire accounting system is ready instantly. Dual-lane execution: backend on `hrms`, frontend on `bei-tasks`, each with its own branch and PR.

**Plan version:** v4 (audit amendment 2026-04-11 — 14 blockers resolved with feature-preserving fixes)

```yaml
sprint: S181
status: PLANNED
planned_date: 2026-04-10
amended_date: 2026-04-11
plan_version: v4
plan_file: docs/plans/2026-04-10-sprint-181-company-master-extension.md

lanes:
  backend_lane:
    repo: Bebang-Enterprise-Inc/hrms
    branch: s181-company-master-extension
    phases: [1, 2, 2B, 3, 4, 5, 6]
    owner_files:
      - "hrms/hr/doctype/bei_company_document/**"
      - "hrms/hr/doctype/bei_company_adms_device/**"
      - "hrms/fixtures/custom_field.json"
      - "hrms/overrides/company.py"
      - "hrms/hooks.py"
      - "hrms/api/company_master.py"
      - "hrms/public/js/company.js"
      - "scripts/s181_phase_3_seed_company_fields.py"
      - "scripts/s181_phase_4_branch_tin_backfill.py"
      - "output/s181/**"
  frontend_lane:
    repo: Bebang-Enterprise-Inc/BEI-Tasks
    branch: s181-company-master-frontend
    phases: [3B, 3C, 6]
    blocked_until:
      - backend_lane_phase_1_merged
      - backend_lane_phase_2B_merged
      - hq.bebang.ph bench migrate succeeded
      - output/s181/interface_contract.md exists on backend_lane branch
    owner_files:
      - "bei-tasks/lib/queries/company-master.ts"
      - "bei-tasks/lib/roles.ts"
      - "bei-tasks/app/dashboard/bd/companies/**"
      - "bei-tasks/app/dashboard/layout.tsx"
      - "bei-tasks/components/company-master/**"

# Legacy top-level keys kept for back-compat with older tooling
branch: s181-company-master-extension
repos: hrms (backend lane) + bei-tasks (frontend lane)

depends_on:
  - S178 Custom Fields (stakeholders, store_locations, partner_names) present in hrms/fixtures/custom_field.json (verified in Agent Boot Sequence Step 5, HB-0)
canonical_unit_total: 102
backend_serial_path: 80   # Phases 1 (15) + 2 (15) + 2B (10) + 3 (12) + 4 (8) + 5 (10) + 6 (10)
frontend_serial_path: 22  # Phases 3B (12) + 3C (10)
critical_path: backend_serial_path  # frontend runs in parallel once unblocked
execution_started:
completed_date:
execution_summary:
```

---

## Design Rationale (For Cold-Start Agents)

### Why this sprint exists

BEI operates 45+ stores across company-owned, JV, managed franchise, and full franchise entities. Today, creating a new branch in Frappe requires:

1. Create the Company record manually
2. Manually create Accounts (27-account Sales template) via SSM scripts or Frappe desk
3. Manually create a Warehouse
4. Manually create a Cost Center
5. Set default accounts on the Company record
6. Hope someone remembers all 5 steps

This is slow, error-prone, and blocks BD from opening new stores quickly. Meanwhile, the Company form itself lacks critical operational fields — no BIR branch TIN, no GPS coordinates, no lease info, no document vault, no POS system link, no operational status.

S175 created the 27-account Sales template and the `ensure_account` helper pattern. S178 completed the company-level master data (TINs, hierarchy, store_locations). S181 connects the dots: extend Company into a comprehensive Company Master and wire the after_insert hook so that **BD fills out one form, clicks Save, and the company is billing-ready**.

### What this sprint delivers

1. **BEI Company Document** child DocType — compliance document vault (lease agreements, BIR forms, business permits, fire safety, sanitary permits) with **both file upload AND Google Drive link** per row (controller `validate()` enforces at least one), expiry tracking, and status. Branch-level `drive_folder_url` on Company points to the top-level Drive folder where the team already stores corporate docs.
2. **BEI Company ADMS Device** child DocType — ADMS biometric device registry per company with auto-enrollment via enqueue-backed `on_update` worker.
3. **47 Custom Fields on Company** across 8 sections (BIR & Legal, Location, Operations, ADMS Devices, Contacts, Compliance Documents, BD Pipeline, Provisioning State) — includes `drive_folder_url`, `revenue_share_pct`, `google_maps_place_id`, `entity_category` / `store_ownership_type` two-level select, and the `first_provision_done` sentinel that gates the on_update hook.
4. **`auto_provision_company` sentinel-gated `on_update` hook** — on first Company save, automatically creates Warehouse, Cost Center, applies the 27-account Sales template + the 20-account Balance Sheet skeleton (Debtors / Creditors / Cost of Goods Sold / Round Off / Cash), sets default accounts, and creates the BKI Customer via S037 register lookup (no duplication — shared across stores that map to the same buyer entity).
5. **`retry_provision_company` whitelisted method + Desk button + frontend pill** — one-click recovery for half-provisioned companies.
6. **`hrms.api.company_master` module** — whitelisted API methods (`list_companies`, `get_company`, `update_company_section`, `upsert_compliance_document`, `upsert_adms_device`, `retry_provision`, etc.) consumed by the bei-tasks frontend via `/api/frappe/api/method/...` proxy (matches the convention used across all existing bei-tasks integrations).
7. **bei-tasks Company Master page** — list page with filters (entity_category, store_ownership_type, operational_status, region) + fullscreen detail dialog mirroring the Employee Master pattern, section edit modals, ADMS device grid, Compliance Documents section with dual upload + Drive link pattern, Stakeholders grid, retry provisioning CTA.
8. **Seed script** to backfill existing 45 companies with new field data from known sources (S037 register, store locations CSV, Mosaic POS CSV).
9. **Migration script** to backfill branch TINs from BIR register.
10. **Pre-migrate backup + rollback procedure** — snapshot fixture + DB rows before `bench migrate`; clean rollback if anything fails.
11. **L3 testing with S092-mandated evidence trio** — `form_submissions.json` + `api_mutations.json` + `state_verification.json` alongside 9 per-scenario evidence files.

### What this sprint does NOT do

- No changes to S175 COA template structure (the 27 accounts are locked)
- No BFC intercompany changes (S175 scope)
- No store ordering or POS integration (different sprints)
- No Frappe Desk form layout customization beyond what Custom Fields auto-generate (the operator UX lives on my.bebang.ph, not Frappe Desk)
- No Google Drive API integration to auto-discover documents inside the branch Drive folder (future sprint; for now BD pastes Drive URLs manually per document row)

### Key architectural decisions

1. **Custom Fields on Company, NOT a separate DocType.** Frappe's Company DocType already has 50+ standard fields. Adding operational fields as Custom Fields keeps everything on one form, avoids join complexity, and plays nicely with Frappe's permissions/workflow engine.

2. **`on_update` with `first_provision_done` sentinel, NOT bare `after_insert`** *(revised in v4 per audit Blocker 9)*. ERPNext creates its Standard Template Debtors / Creditors / Cost of Goods Sold / default Warehouses / default Cost Center inside the Company `on_update` lifecycle. If S181's provisioning ran at `after_insert`, those accounts would not yet exist and `_set_default_accounts` would silently no-op. The sentinel-gated `on_update` approach fires exactly once (guarded by `first_provision_done` Custom Field) AFTER ERPNext's defaults exist, and is idempotent on subsequent saves. Trade-off: one extra Custom Field (sentinel) in exchange for correct lifecycle ordering.

3. **Bulk-import / migration guard** *(added in v4 per audit Blocker 13)*. `auto_provision_company` checks `frappe.flags.in_import or in_migrate or in_install` and returns early. Without this, the Frappe Data Import Tool could trigger 27 × N account creations during a mass Company import.

4. **`ensure_account` pattern reused from S175, plus the new Balance Sheet template** *(extended in v4 per audit Blocker 5)*. The `ensure_account(company, number, name, parent_number, is_group, root_type, account_type)` function is idempotent. S181 extends it with `_MASTER_BALANCE_SHEET_TEMPLATE` — 20 accounts covering Asset / Liability / Equity / Expense roots, Debtors, Creditors, Cost of Goods Sold, Round Off, Cash — so `_set_default_accounts` is guaranteed to find its targets regardless of whether ERPNext's Standard Template is fully populated.

5. **`frappe.local.flags.ignore_root_company_validation = True`** — required because most new companies will have `parent_company` set (under BEI or a holding company). Without this flag, ERPNext throws "Please add the account to root level Company" during account creation. This is the Frappe-sanctioned per-request flag, not a hack.

6. **BKI Customer via S037 register lookup, NOT docname** *(rewritten in v4 per audit Blocker 4)*. `build_bki_store_sale_invoice` in `hrms/api/commissary.py:1027-1050` (shipped S168 code) looks up the Customer by `buyer_entity_name` from the S037 register. `_ensure_bki_customer` now reads that same register, matches by `doc.name == store_name or warehouse_docname`, uses `buyer_entity_name` as the Customer's `customer_name` (+ copies `tax_id`, `bir_rdo_code`, `vat_status`), and shares the Customer across stores that map to the same buyer entity (48 stores → 38 unique buyer entities). Non-store entities (head office, commissary, holding, franchisor) skip BKI Customer creation entirely.

7. **ADMS enrollment via enqueue, NOT blocking HTTP in the request path** *(rewritten in v4 per audit Blocker 12)*. The `auto_enroll_adms_devices` hook enqueues `_enroll_adms_devices_job` in Frappe's `short` queue, passes the pending device list by value, and updates child rows via `frappe.db.set_value` (which does NOT re-trigger `on_update`). Timeout is 10s per device. Failed enrollments are retried on the next Company save.

8. **Backend API module for the frontend lane, NOT raw `/api/resource/`** *(added in v4 per audit Blocker 6)*. The bei-tasks codebase uses `/api/frappe/api/method/<module>.<function>` exclusively. S181 publishes `hrms.api.company_master` with method-level permission checks, mass-assignment guardrails (`EDITABLE_SECTIONS`), and matching Sentry observability. The interface is frozen into `output/s181/interface_contract.md` so the frontend lane has a stable target.

9. **Dual-lane execution with explicit blocked_until gates** *(added in v4 per audit Blocker 8)*. Backend lane (hrms, 80u) and frontend lane (bei-tasks, 22u) run in parallel once Phase 2B is merged and `bench migrate` has succeeded. Each lane gets its own branch and PR; closeout requires BOTH PR numbers in SPRINT_REGISTRY.md. The `lanes:` YAML block in plan metadata declares file ownership and blocking conditions explicitly — no prose-only parallelization claims.

10. **Sentry observability** on all whitelisted methods per DM-7 rule: `set_backend_observability_context(module="company", action="...", mutation_type="...")`.

---

## Data Sources

| Source | Path | Contents |
|---|---|---|
| BIR entity register (51 rows) | `data/_CLEANROOM/batch_2026-02-28_cleanroom_v1/raw_snapshot/ENTITY_TIN_RDO_2026-02-27.csv` | All TINs, RDOs, VAT status — for branch_tin + bir_rdo_code backfill |
| Store-entity mapping (48 stores) | `data/_CLEANROOM/2026-03-12-s037-store-buyer-entity-register/store_buyer_entity_register_2026-03-12.csv` | Maps stores to entities, store types, addresses |
| Warehouse tree | `docs/erp/WAREHOUSE_TREE_2025-12-31.csv` | Existing warehouse names for seeding |
| Store locations CSV | `docs/stores/Bebang_Halo-Halo_Stores_Locations_2025-12-29.csv` | GPS coordinates, addresses, mall names |
| Mosaic POS API keys | `data/POS_Extraction/MOSAIC_POS_API_KEYS.csv` | Store → mosaic_location_id mapping |
| S175 canonical COA template | `data/_CLEANROOM/2026-04-09_s175_coa_restructure/01_CANONICAL_COA_TEMPLATE.md` | 27-account Sales template spec |
| S175 template Python | `scripts/s175_master_coa_template.py` | `MASTER_SALES_TEMPLATE` list (27 tuples) |
| S175 ensure_account pattern | `scripts/s175_phase_2_apply_template.py` lines 109-160 | Idempotent account creation/verification |
| Existing Company hooks | `hrms/overrides/company.py` | `make_company_fixtures`, `set_default_hr_accounts`, `validate_default_accounts` |
| Existing hook registration | `hrms/hooks.py` line 181 | Company doc_events (validate, on_update, on_trash) |
| BEI Company Stakeholder child table | `hrms/hr/doctype/bei_company_stakeholder/bei_company_stakeholder.json` | Pattern for child DocType creation |
| Existing Company Custom Fields | `hrms/fixtures/custom_field.json` lines 740-781 | S178 fields: store_locations, partner_names, stakeholders_section, stakeholders |

---

## Phase Budget Contract

```yaml
phase_unit_budget:
  # ===== BACKEND LANE (hrms repo, branch s181-company-master-extension) =====
  Phase 1  (2 child DocTypes + 47 Custom Fields + pre-migrate backup):           15
  Phase 2  (on_update hook — sentinel-gated auto-provision + BSh + BKI + retry): 15
  Phase 2B (hrms.api.company_master whitelisted API methods + interface_contract): 10
  Phase 3  (Seed existing companies with new field data):                        12
  Phase 4  (Branch TIN backfill migration script):                                8
  Phase 5  (L3 testing — 9 scenarios with per-scenario + S092 trio evidence):    10
  Phase 6  (Closeout — TWO PRs, registry update, SIGNOFF):                       10
  # ===== FRONTEND LANE (bei-tasks repo, branch s181-company-master-frontend) =====
  Phase 3B (bei-tasks Company Master list page + fullscreen detail dialog):      12
  Phase 3C (bei-tasks section edit modals + ADMS + Compliance Documents):        10
hard_limit_per_phase: 15
preferred_split_threshold: 12
total_units: 102
backend_lane_serial_path: 80   # Phases 1 + 2 + 2B + 3 + 4 + 5 + 6
frontend_lane_serial_path: 22  # Phases 3B + 3C (parallel to backend Phase 3/4/5)
```

## Scope Size Warning (resolved via explicit parallel lanes, v4)

Total is 102 units across both repos, above the 80-unit ceiling, but the plan is
structured as two explicit execution lanes with a declared `lanes:` YAML block, file
ownership matrix, and blocked_until gates (see plan metadata at top).

**Backend lane serial path = 80u** — fits exactly at the S089 80u ceiling.

**Frontend lane serial path = 22u** — starts AFTER backend Phase 2B merges and
`bench migrate` succeeds, runs in parallel with backend Phase 3 / 4 / 5. Each lane
has its own branch, its own PR, and its own closeout task.

This is NOT the same as the original "70u claim" in v3, which was an un-contracted
prose assertion. v4 adds:
- The `lanes:` YAML block declaring each lane's repo, branch, phases, owner_files,
  and blocked_until conditions.
- A frozen `output/s181/interface_contract.md` that Phase 2B produces and Phase 3B/3C
  consume — frontend cannot reference any field or endpoint outside that contract.
- Two sprint registry rows (one per lane) — see SPRINT_REGISTRY.md.
- Two closeout tasks, one per lane, each creating its own PR.

If an agent cannot run both lanes in parallel (single-agent-per-session constraint),
execute them sequentially: full backend lane first, then the frontend lane — serial
path remains 80 + 22 = 102u over two agent sessions.

---

## Requirements Regression Checklist

- [ ] **RR-1:** `BEI Company Document` child DocType exists with all 8 fields (document_type, document_name, file, drive_file_url, issue_date, expiry_date, status, notes) AND controller `validate()` enforces that at least one of `file` or `drive_file_url` is set per row
- [ ] **RR-2:** All 47 Custom Fields on Company exist across 8 sections (BIR & Legal, Location, Operations, ADMS Devices, Contacts, Compliance Documents [includes `drive_folder_url`], BD Pipeline, Provisioning State [includes `first_provision_done` sentinel])
- [ ] **RR-3:** `on_update` sentinel-gated hook on Company auto-creates Warehouse named `<Company Name> - <Abbr>` on first provision
- [ ] **RR-4:** `on_update` hook auto-creates Cost Center named `<Company Name> - <Abbr>` on first provision
- [ ] **RR-5:** `on_update` hook applies the 27-account Sales template using `ensure_account` pattern
- [ ] **RR-5a:** `on_update` hook applies the 20-account Balance Sheet + Expense skeleton (`_apply_balance_sheet_template`) so Debtors / Creditors / Cost of Goods Sold / Round Off / Cash exist before `_set_default_accounts` runs (Blocker 5 fix)
- [ ] **RR-6:** `on_update` hook sets default accounts (receivable, payable, income, expense, cash, round_off) — NEVER silently no-ops on missing accounts; if any default is missing, raises to roll back the savepoint
- [ ] **RR-7:** `on_update` hook uses `frappe.local.flags.ignore_root_company_validation = True`
- [ ] **RR-8:** `on_update` hook has Sentry observability context (`module="company"`, `action="auto_provision_company"`)
- [ ] **RR-9:** `on_update` hook uses `frappe.db.savepoint()` for atomicity (if any provisioning step fails, the Company still saves but provisioning is rolled back with error logged)
- [ ] **RR-9a:** `on_update` hook is gated by `first_provision_done` Custom Field sentinel — runs exactly once per Company, never re-runs on subsequent saves (Blocker 9 fix)
- [ ] **RR-9b:** `on_update` hook skips during `frappe.flags.in_import / in_migrate / in_install` — bulk imports do not trigger mass account creation (Blocker 13 fix)
- [ ] **RR-9c:** `retry_provision_company` whitelisted method exists + Desk button + frontend pill appear when `first_provision_done == 0` (Blocker 14 fix)
- [ ] **RR-10:** Existing 45 companies have `entity_category` populated from store-entity mapping (and `store_ownership_type` populated where `entity_category == 'Store'`)
- [ ] **RR-11:** Existing companies have `mosaic_location_id` populated from POS API keys CSV
- [ ] **RR-12:** Existing companies have GPS coordinates populated from `Bebang_Halo-Halo_Stores_Locations_2025-12-29.csv` (NOT 2025-12-31 — Blocker 2 fix)
- [ ] **RR-13:** Branch TINs backfilled from BIR register where different from head office TIN
- [ ] **RR-14:** S175 verification still passes (1080 template positions intact)
- [ ] **RR-15:** S178 custom fields unchanged (store_locations, partner_names, stakeholders_section, stakeholders) and verified present in fixture (HB-0 precondition)
- [ ] **RR-16:** Existing Company hooks (`make_company_fixtures`, `set_default_hr_accounts`, `validate_default_accounts`) still function correctly
- [ ] **RR-17:** Custom Field fixture file (`hrms/fixtures/custom_field.json`) updated with all new fields
- [ ] **RR-18:** hooks.py updated with `on_update` entries for Company (`auto_provision_company` + `auto_enroll_adms_devices`) — NOT `after_insert` (Blocker 9 fix)
- [ ] **RR-19:** BEI Company ADMS Device child DocType exists with fields: device_serial, device_name, bio_device_id, adms_enrolled, enrollment_date, ip_address, notes
- [ ] **RR-20:** ADMS auto-enrollment `on_update` hook uses `frappe.enqueue` for the HTTP call (non-blocking) and `frappe.db.set_value` for child row updates (non-recursive — does NOT re-trigger `on_update`) — Blocker 12 fix
- [ ] **RR-21:** `_ensure_bki_customer` reads the S037 register (`store_buyer_entity_register_2026-03-12.csv`) and uses `buyer_entity_name` as the Customer's `customer_name` (NOT `doc.name`); skips gracefully for non-store entities; copies tax_id / rdo / vat_status (Blocker 4 fix)
- [ ] **RR-22:** `hrms.api.company_master` module exists with 8 whitelisted methods (`list_companies`, `get_company`, `update_company_section`, `upsert_compliance_document`, `delete_compliance_document`, `upsert_adms_device`, `delete_adms_device`, `retry_provision`), all with Sentry observability and `EDITABLE_SECTIONS` mass-assignment guardrails (Blocker 6 fix)
- [ ] **RR-23:** `output/s181/interface_contract.md` exists, frozen after Phase 2B, listing every endpoint + fieldname the frontend lane may consume (Blocker 8 fix)
- [ ] **RR-24:** Pre-migrate backup files exist at `output/s181/backups/custom_field_BEFORE.json`, `tabCustomField_Company_BEFORE.sql`, `BACKUP_TIMESTAMP.txt` BEFORE `bench migrate` runs (Blocker 11 fix, HB-6 gate)
- [ ] **RR-25:** bei-tasks Company Master page exists at `app/dashboard/bd/companies/page.tsx` with fullscreen `CompanyDetailDialog`, 8 section cards, filter chips, search, and sidebar entry in Operations (Blocker 7 fix)
- [ ] **RR-26:** bei-tasks frontend queries use ONLY the `/api/frappe/api/method/hrms.api.company_master.*` proxy pattern — zero references to `/api/resource/Company/` (Blocker 6 fix)
- [ ] **RR-27:** Compliance Documents section in bei-tasks renders BOTH upload button AND Google Drive folder link per row, with Save disabled until at least one is provided (mirrors backend validator)
- [ ] **RR-28:** L3 Evidence Contract produces `output/l3/s181/form_submissions.json`, `api_mutations.json`, `state_verification.json` (S092 trio — Blocker 10 fix) alongside 9 per-scenario files
- [ ] **RR-29:** Two sprint branches reserved: `s181-company-master-extension` (backend hrms) AND `s181-company-master-frontend` (frontend bei-tasks); both appear in SPRINT_REGISTRY.md S181 row
- [ ] **RR-30:** Two PRs created at closeout — one on `Bebang-Enterprise-Inc/hrms`, one on `Bebang-Enterprise-Inc/BEI-Tasks` — both PR numbers recorded in SPRINT_REGISTRY.md

---

## HARD BLOCKERS

- **HB-0:** If the S178 Custom Fields (`stakeholders`, `store_locations`, `partner_names`, `stakeholders_section`) are not present in `hrms/fixtures/custom_field.json`, STOP. S181 Phase 1 Section 1 inserts after `stakeholders` — the field must exist. Run the Agent Boot Sequence Step 5 verification script. (Audit amendment 2026-04-11 — added because SPRINT_REGISTRY.md shows S178 as PLANNED even though the fields are on disk; governance/reality mismatch.)
- **HB-1:** If the `MASTER_SALES_TEMPLATE` from `scripts/s175_master_coa_template.py` has changed since S175 (not 27 rows), STOP. The template is locked — do not modify it. Investigate why it changed.
- **HB-2:** If `hrms/overrides/company.py` already has an `on_update` entry for `auto_provision_company` from another sprint, STOP. Merge the logic, do not replace. Ask Sam if unclear.
- **HB-3:** If any of the 8 new Custom Field sections conflict with a field that already exists on Company (same `fieldname`), STOP. Rename the new field to avoid collision.
- **HB-4:** If the `BEI Company Document` or `BEI Company ADMS Device` DocType names collide with existing DocTypes, STOP. Check `frappe.db.exists("DocType", "...")` first.
- **HB-5:** If `bench migrate` fails after adding the Custom Fields or DocTypes, STOP. Execute the rollback procedure in Task 1.4a, fix the fixture JSON, and retry. Do NOT proceed with broken migrations.
- **HB-6:** Refuse to run `bench migrate` until Task 1.4a's three pre-migrate backup files exist in `output/s181/backups/`. No backup = no migrate.
- **HB-7:** If the `auto_enroll_adms_devices` hook calls `doc.save()` or makes synchronous HTTP calls in the request path, STOP. It must use `frappe.enqueue` + `frappe.db.set_value`. (Blocker 12 — if reverted, double-save and blocking I/O return.)
- **HB-8:** If the frontend lane code references `/api/resource/Company/`, STOP. That is the wrong pattern — use `/api/frappe/api/method/hrms.api.company_master.*` instead. (Blocker 6)

---

## Phase 1: BEI Company Document Child DocType + Custom Fields

**Units: 15** — No external dependencies. Pure DocType + fixture creation.

### Task 1.1: Create BEI Company Document child DocType

```
MUST_CREATE: hrms/hr/doctype/bei_company_document/__init__.py
MUST_CREATE: hrms/hr/doctype/bei_company_document/bei_company_document.py
MUST_CREATE: hrms/hr/doctype/bei_company_document/bei_company_document.json
```

Follow the same pattern as `hrms/hr/doctype/bei_company_stakeholder/bei_company_stakeholder.json`.

DocType definition:
```json
{
    "doctype": "DocType",
    "name": "BEI Company Document",
    "module": "HR",
    "istable": 1,
    "editable_grid": 1,
    "engine": "InnoDB",
    "naming_rule": "Random",
    "field_order": [
        "document_type",
        "document_name",
        "column_break_1",
        "file",
        "drive_file_url",
        "status",
        "section_break_dates",
        "issue_date",
        "column_break_2",
        "expiry_date",
        "section_break_notes",
        "notes"
    ],
    "fields": [
        {
            "fieldname": "document_type",
            "fieldtype": "Select",
            "label": "Document Type",
            "options": "\nLease Agreement\nBusiness Permit\nBIR Form 2303\nFire Safety Certificate\nSanitary Permit\nSEC Certificate\nOther",
            "in_list_view": 1,
            "reqd": 1,
            "columns": 2
        },
        {
            "fieldname": "document_name",
            "fieldtype": "Data",
            "label": "Document Name",
            "in_list_view": 1,
            "columns": 3
        },
        {
            "fieldname": "column_break_1",
            "fieldtype": "Column Break"
        },
        {
            "fieldname": "file",
            "fieldtype": "Attach",
            "label": "File (Upload)",
            "description": "Optional: upload a copy of the document directly to Frappe. Use this for ad-hoc uploads, scanned receipts, or documents not yet in Google Drive."
        },
        {
            "fieldname": "drive_file_url",
            "fieldtype": "Data",
            "label": "Google Drive URL",
            "options": "URL",
            "description": "Direct link to this specific document in Google Drive. Preferred over Attach when the document already lives in the branch Drive folder (avoids duplication and keeps Drive as the source of truth). Either `file` or `drive_file_url` must be set — both are allowed."
        },
        {
            "fieldname": "status",
            "fieldtype": "Select",
            "label": "Status",
            "options": "\nValid\nExpired\nPending Renewal\nNot Required",
            "in_list_view": 1,
            "default": "Valid",
            "columns": 1
        },
        {
            "fieldname": "section_break_dates",
            "fieldtype": "Section Break",
            "label": "Dates"
        },
        {
            "fieldname": "issue_date",
            "fieldtype": "Date",
            "label": "Issue Date",
            "in_list_view": 1,
            "columns": 1
        },
        {
            "fieldname": "column_break_2",
            "fieldtype": "Column Break"
        },
        {
            "fieldname": "expiry_date",
            "fieldtype": "Date",
            "label": "Expiry Date",
            "in_list_view": 1,
            "columns": 1
        },
        {
            "fieldname": "section_break_notes",
            "fieldtype": "Section Break",
            "collapsible": 1,
            "label": "Notes"
        },
        {
            "fieldname": "notes",
            "fieldtype": "Small Text",
            "label": "Notes"
        }
    ]
}
```

Controller (`bei_company_document.py`):
```python
# Copyright (c) 2026, Bebang Enterprise Inc. and contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe.model.document import Document

class BEICompanyDocument(Document):
    def validate(self):
        # At least one of `file` (Attach) or `drive_file_url` (Drive link) must be set.
        # BD can upload directly to Frappe OR link to the existing Google Drive copy.
        # Both are allowed (e.g., upload the scan AND link to the authoritative Drive version).
        if not self.file and not self.drive_file_url:
            frappe.throw(
                f"Document '{self.document_name or self.document_type}' must have either an uploaded File or a Google Drive URL (or both)."
            )
        # Light URL shape check on Drive link
        if self.drive_file_url and not (
            self.drive_file_url.startswith("https://drive.google.com/")
            or self.drive_file_url.startswith("https://docs.google.com/")
        ):
            frappe.throw(
                f"Google Drive URL for '{self.document_name or self.document_type}' must start with https://drive.google.com/ or https://docs.google.com/"
            )
```

### Task 1.2: Add all Custom Fields to Company via fixture

```
MUST_MODIFY: hrms/fixtures/custom_field.json
```

Append the following Custom Fields to the fixture array. Insert after the existing S178 `stakeholders` field. All fields use `dt: "Company"`.

**Section 1 — BIR & Legal Identity:**

| name | fieldname | fieldtype | label | options | insert_after | description |
|---|---|---|---|---|---|---|
| Company-bir_legal_section | bir_legal_section | Section Break | BIR & Legal Identity | — | stakeholders | S181: BIR registration and SEC details |
| Company-branch_tin | branch_tin | Data | Branch TIN | — | bir_legal_section | S181: Branch-specific BIR TIN (may differ from head office tax_id) |
| Company-bir_rdo_code | bir_rdo_code | Data | BIR RDO Code | — | branch_tin | S181: Revenue District Office code |
| Company-bir_registration_date | bir_registration_date | Date | BIR Registration Date | — | bir_rdo_code | S181: BIR Form 2303 date |
| Company-bir_legal_col1 | bir_legal_col1 | Column Break | — | — | bir_registration_date | — |
| Company-sec_registration_no | sec_registration_no | Data | SEC Registration No. | — | bir_legal_col1 | S181: SEC registration number |
| Company-sec_registration_date | sec_registration_date | Date | SEC Registration Date | — | sec_registration_no | S181 |

**Section 2 — Location:**

| name | fieldname | fieldtype | label | options | insert_after | description |
|---|---|---|---|---|---|---|
| Company-location_section | location_section | Section Break | Location | — | sec_registration_date | S181: Physical address and GPS |
| Company-full_address | full_address | Small Text | Full Address | — | location_section | S181: Complete street address |
| Company-city | city | Data | City | — | full_address | S181 |
| Company-province | province | Data | Province | — | city | S181 |
| Company-region | region | Select | Region | \nNCR\nLuzon\nVisayas\nMindanao | province | S181 |
| Company-location_col1 | location_col1 | Column Break | — | — | region | — |
| Company-mall_or_building | mall_or_building | Data | Mall / Building | — | location_col1 | S181: e.g. SM Megamall, Ayala Fairview Terraces |
| Company-gps_latitude | gps_latitude | Float | GPS Latitude | — | mall_or_building | S181 |
| Company-gps_longitude | gps_longitude | Float | GPS Longitude | — | gps_latitude | S181 |
| Company-google_maps_place_id | google_maps_place_id | Data | Google Maps Place ID | — | gps_longitude | S181: For website store locator + Google Business Profile. Format: ChIJ... (Google Place ID string) |

**Section 3 — Operations:**

| name | fieldname | fieldtype | label | options | insert_after | description |
|---|---|---|---|---|---|---|
| Company-operations_section | operations_section | Section Break | Operations | — | gps_longitude | S181: Store operations metadata |
| Company-entity_category | entity_category | Select | Entity Category | \nHead Office\nCommissary\nStore\nWarehouse\nHolding Company\nFranchisor | operations_section | S181: Top-level classification. When "Store" is selected, store_ownership_type becomes visible. |
| Company-store_ownership_type | store_ownership_type | Select | Store Ownership Type | \nCompany Owned\nJV\nManaged Franchise\nFull Franchise | entity_category | S181: Sub-classification for stores. `depends_on`: `eval:doc.entity_category=='Store'` — hidden when entity_category is not Store. |
| Company-operational_status | operational_status | Select | Operational Status | \nActive\nPre-Opening\nTemporarily Closed\nPermanently Closed\nPipeline | store_ownership_type | S181 |
| Company-opening_date | opening_date | Date | Opening Date | — | operational_status | S181: Date the store/entity began operations |
| Company-operations_col1 | operations_col1 | Column Break | — | — | opening_date | — |
| Company-operating_hours | operating_hours | Data | Operating Hours | — | operations_col1 | S181: e.g. 10:00 AM - 9:00 PM |
| Company-pos_system | pos_system | Select | POS System | \nMosaic\nOther\nNone | operating_hours | S181 |
| Company-mosaic_location_id | mosaic_location_id | Data | Mosaic Location ID | — | pos_system | S181: For POS data sync |
| Company-adms_devices_section | adms_devices_section | Section Break | Biometric Devices (ADMS) | — | mosaic_location_id | S181: ZKTeco MB10-VL biometric devices assigned to this branch. Adding a device here auto-enrolls it in the ADMS receiver. |
| Company-adms_devices | adms_devices | Table | ADMS Devices | BEI Company ADMS Device | adms_devices_section | S181: Child table — one row per physical biometric device. On save, triggers ADMS auto-enrollment via the ADMS receiver API. |

**Section 4 — Contacts:**

| name | fieldname | fieldtype | label | options | insert_after | description |
|---|---|---|---|---|---|---|
| Company-contacts_section | contacts_section | Section Break | Contacts | — | adms_devices | S181: Key personnel for this entity |
| Company-store_manager | store_manager | Link | Store Manager | Employee | contacts_section | S181 |
| Company-store_manager_phone | store_manager_phone | Data | Store Manager Phone | Phone | store_manager | S181 |
| Company-contacts_col1 | contacts_col1 | Column Break | — | — | store_manager_phone | — |
| Company-area_supervisor | area_supervisor | Link | Area Supervisor | Employee | contacts_col1 | S181 |
| Company-regional_manager | regional_manager | Link | Regional Manager | Employee | area_supervisor | S181 |

**Section 5 — Compliance Documents:**

| name | fieldname | fieldtype | label | options | insert_after | description |
|---|---|---|---|---|---|---|
| Company-compliance_docs_section | compliance_docs_section | Section Break | Compliance Documents | — | regional_manager | S181: BIR forms, leases, permits — supports BOTH Frappe upload AND Google Drive link per document, with expiry tracking |
| Company-drive_folder_url | drive_folder_url | Data | Branch Drive Folder URL | URL | compliance_docs_section | S181: Top-level Google Drive folder URL for this branch's corporate documents (lease, BIR, permits, fire safety, sanitary). BD pastes this once; operator UI exposes a "📁 Open Drive Folder" button. Format: https://drive.google.com/drive/folders/... |
| Company-compliance_documents | compliance_documents | Table | Compliance Documents | BEI Company Document | drive_folder_url | S181: Metadata registry per document — each row tracks document_type, dates, status, and supports BOTH file upload AND per-document Drive URL |

**Section 6 — BD Pipeline:**

| name | fieldname | fieldtype | label | options | insert_after | description |
|---|---|---|---|---|---|---|
| Company-bd_pipeline_section | bd_pipeline_section | Section Break | BD Pipeline | — | compliance_documents | S181: Business development pipeline tracking |
| Company-pipeline_status | pipeline_status | Select | Pipeline Status | \nProspect\nLOI Signed\nLease Signed\nUnder Construction\nPre-Opening\nOperational | bd_pipeline_section | S181 |
| Company-target_opening_date | target_opening_date | Date | Target Opening Date | — | pipeline_status | S181 |
| Company-bd_pipeline_col1 | bd_pipeline_col1 | Column Break | — | — | target_opening_date | — |
| Company-lease_start_date | lease_start_date | Date | Lease Start Date | — | bd_pipeline_col1 | S181 |
| Company-lease_end_date | lease_end_date | Date | Lease End Date | — | lease_start_date | S181 |
| Company-lease_monthly_rent | lease_monthly_rent | Currency | Lease Monthly Rent | — | lease_end_date | S181 |
| Company-revenue_share_pct | revenue_share_pct | Percent | Revenue Share % | — | lease_monthly_rent | S181: Some malls charge a % of gross sales on top of fixed rent. Set to 0 if fixed-rent only. |

**Section 7 — Provisioning State (S181 internal, hidden by default):**

| name | fieldname | fieldtype | label | options | insert_after | description |
|---|---|---|---|---|---|---|
| Company-provisioning_state_section | provisioning_state_section | Section Break | Provisioning State (S181) | — | revenue_share_pct | S181: Internal state for the auto-provisioning hook — collapsed by default. |
| Company-first_provision_done | first_provision_done | Check | S181 First Provision Done | — | provisioning_state_section | S181 sentinel (Blocker 9 fix). Set to 1 after auto_provision_company runs successfully. Prevents re-running on every save. Visible to Accounts Manager only (used as the gate for the Retry Provisioning button). |

**Total new Custom Fields: 47** (8 section breaks + 5 column breaks + 2 Table fields + 32 data fields = 47 fixture entries). Added in v2: `entity_category` + `store_ownership_type` (2-level select), `google_maps_place_id`, `revenue_share_pct`, `adms_devices` child table (replaces passive text field). Added in v3: `drive_folder_url` on Company Section 5 + `drive_file_url` on BEI Company Document child table (both complementary to `file` Attach field — BD can choose upload OR Drive link OR both). Added in v4 (audit amendment 2026-04-11): `provisioning_state_section` + `first_provision_done` (sentinel gating the on_update hook — Blocker 9 fix). **Programmatic field-count verification: run `grep -c "| Company-" docs/plans/2026-04-10-sprint-181-company-master-extension.md` — must return 47.**

### Task 1.1a: Create BEI Company ADMS Device child DocType

```
MUST_CREATE: hrms/hr/doctype/bei_company_adms_device/__init__.py
MUST_CREATE: hrms/hr/doctype/bei_company_adms_device/bei_company_adms_device.py
MUST_CREATE: hrms/hr/doctype/bei_company_adms_device/bei_company_adms_device.json
```

Follow the same pattern as `hrms/hr/doctype/bei_company_stakeholder/`. The JSON spec is already defined in Task 1.1b below (device_serial, device_name, bio_device_id, adms_enrolled, enrollment_date, ip_address, notes).

### Task 1.1b: Create BEI Company ADMS Device child DocType

New child table: `hrms/hr/doctype/bei_company_adms_device/`

```json
{
  "istable": 1,
  "fields": [
    {"fieldname": "device_serial", "fieldtype": "Data", "label": "Device Serial No.", "reqd": 1, "in_list_view": 1, "columns": 2,
     "description": "The ZKTeco MB10-VL serial number (printed on device back). Must be unique across all companies."},
    {"fieldname": "device_name", "fieldtype": "Data", "label": "Device Name", "in_list_view": 1, "columns": 2,
     "description": "Human-readable label, e.g. 'SM Bicutan - Main Entrance'"},
    {"fieldname": "bio_device_id", "fieldtype": "Data", "label": "Bio Device ID", "in_list_view": 1, "columns": 1,
     "description": "The ADMS device ID used for attendance punch matching (e.g., 1, 2, 3)"},
    {"fieldname": "column_break_1", "fieldtype": "Column Break"},
    {"fieldname": "adms_enrolled", "fieldtype": "Check", "label": "ADMS Enrolled", "default": "0", "read_only": 1, "in_list_view": 1, "columns": 1,
     "description": "Auto-set to 1 when the device is successfully enrolled in the ADMS receiver via API"},
    {"fieldname": "enrollment_date", "fieldtype": "Date", "label": "Enrollment Date", "read_only": 1},
    {"fieldname": "ip_address", "fieldtype": "Data", "label": "IP Address",
     "description": "Device IP on the store's local network (if known)"},
    {"fieldname": "notes", "fieldtype": "Small Text", "label": "Notes"}
  ]
}
```

**ADMS auto-enrollment hook (Phase 2):** On `Company.on_update`, enqueue a background
job per un-enrolled device. The job POSTs to the ADMS receiver and updates each row's
`adms_enrolled = 1` / `enrollment_date` via `frappe.db.set_value` (NOT `doc.save`), so
the hook does not re-trigger itself and does not block the Company save.

**Blocker 12 fix (2026-04-11):** the original draft used `doc.save(ignore_permissions=True)`
at the end, which re-enters `on_update` on the same request — double-saving every Company
edit and cascading through `make_company_fixtures` / `set_default_hr_accounts` /
`auto_provision_company` twice. It also made a synchronous HTTP call inside the request,
which could slow or time out the user's save. Rewritten to be non-blocking, non-recursive,
and circuit-breakable.

```python
# In hrms/overrides/company.py — on_update hook
def auto_enroll_adms_devices(doc, method=None):
    """Enqueue ADMS enrollment for any un-enrolled devices.

    Non-blocking: the HTTP call to the ADMS receiver runs in a background job
    (`frappe.enqueue`). The worker updates the child-row state via
    `frappe.db.set_value`, which does NOT trigger `on_update`, so there is no
    double-save / infinite recursion.

    Guards: skip during bulk-import / migration (Blocker 13 fix).
    """
    from hrms.utils.sentry import set_backend_observability_context
    set_backend_observability_context(
        module="company",
        action="auto_enroll_adms_devices",
        mutation_type="update",
        extras={"company": doc.name},
    )

    if frappe.flags.in_import or frappe.flags.in_migrate or frappe.flags.in_install:
        return
    if not doc.adms_devices:
        return

    pending = [
        {
            "row_name": device.name,
            "device_serial": device.device_serial,
            "bio_device_id": device.bio_device_id,
        }
        for device in doc.adms_devices
        if not device.adms_enrolled and device.device_serial
    ]
    if not pending:
        return

    frappe.enqueue(
        "hrms.overrides.company._enroll_adms_devices_job",
        queue="short",
        timeout=120,
        job_name=f"s181_adms_enroll_{doc.name}",
        company_name=doc.name,
        pending=pending,
    )


def _enroll_adms_devices_job(company_name: str, pending: list):
    """Background worker for ADMS device enrollment.

    Circuit breaker: if the receiver is unreachable or returns non-2xx, log the
    error and leave the row un-enrolled. The row will be retried on the next
    Company save (the `auto_enroll_adms_devices` hook re-scans for un-enrolled
    rows each time).
    """
    import requests

    try:
        receiver_base_url = frappe.conf.get("adms_receiver_base_url") \
            or frappe.db.get_single_value("ADMS Settings", "receiver_base_url")
    except Exception:
        receiver_base_url = None

    if not receiver_base_url:
        frappe.log_error(
            title=f"S181 ADMS enrollment: no receiver URL configured ({company_name})",
            message=f"Pending devices: {pending}",
        )
        return

    for entry in pending:
        try:
            resp = requests.post(
                f"{receiver_base_url.rstrip('/')}/api/devices/enroll",
                json={
                    "device_serial": entry["device_serial"],
                    "bio_device_id": entry["bio_device_id"],
                    "company": company_name,
                },
                timeout=10,  # circuit breaker — never block the worker > 10s per device
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("success"):
                # frappe.db.set_value on a child row — does NOT trigger parent on_update
                frappe.db.set_value(
                    "BEI Company ADMS Device",
                    entry["row_name"],
                    {
                        "adms_enrolled": 1,
                        "enrollment_date": frappe.utils.nowdate(),
                    },
                    update_modified=False,
                )
            else:
                frappe.log_error(
                    title=f"S181 ADMS enrollment rejected for {entry['device_serial']}",
                    message=f"Receiver response: {data}",
                )
        except Exception as e:
            frappe.log_error(
                title=f"S181 ADMS enrollment failed for {entry['device_serial']}",
                message=f"Company: {company_name}\nError: {e}",
            )

    frappe.db.commit()
```

### Task 1.1c: Frontend UX — Fullscreen + Popup Edit Pattern

**CRITICAL UX REQUIREMENT (from Sam 2026-04-10):** The Company Master form in my.bebang.ph (bei-tasks repo) MUST use the same fullscreen + popup edit pattern as:

1. **Employee Master** (`bei-tasks/app/dashboard/hr/employee-master/page.tsx` + `employee-detail-dialog.tsx`) — list page with a fullscreen detail dialog (section cards, inline editing, photo upload). The dialog opens over the list without navigating away.
2. **Payroll Compensation Setup** (`bei-tasks/app/dashboard/hr/payroll/compensation-setup/page.tsx` + `compensation-setup/[employee]/page.tsx` + `components/hr/compensation-detail-panel.tsx`) — list + detail pattern with a popup/panel to edit compensation details without leaving the list page

**Specifically:**
- Company list page shows all companies in a searchable/filterable table (entity_category, operational_status, store_ownership_type as filter chips)
- Clicking a company opens a **fullscreen detail page** with collapsible section cards (Identity, Location, Operations, Contacts, Documents, Stakeholders, BD Pipeline)
- Each section card has an **Edit** button that opens a **popup modal** to edit that section's fields without leaving the page
- The Stakeholders child table renders as an inline editable grid (same as Employee bank accounts or Compensation components)
- The ADMS Devices child table renders similarly with an "Add Device" button that opens a small form

**Compliance Documents section — dual upload/link pattern (REQUIRED):**
The section card MUST render BOTH capabilities, side by side, so BD and store managers can choose whichever is easier for each document:

1. **Header — Branch Drive Folder banner:**
   - Shows the `drive_folder_url` value as a large pill button: **"📁 Open Branch Drive Folder"** (opens in a new tab).
   - If `drive_folder_url` is empty, shows a muted **"+ Link Branch Drive Folder"** CTA that opens an inline input modal to paste the Drive URL.
   - Edit pencil icon next to the pill allows replacing the URL.

2. **Document grid — cards with expiry badges:**
   - Each document row from `compliance_documents` child table renders as a card with:
     - Document type icon + document_name + status pill (green = Valid, red = Expired, yellow = Expiring ≤30 days, gray = Pending Renewal)
     - Issue date / expiry date with countdown ("expires in 14 days")
     - **TWO action buttons** per card (one or both enabled depending on which field is set):
       - **⬇ Download** — enabled if `file` (Attach) is set; triggers Frappe file download
       - **🔗 Open in Drive** — enabled if `drive_file_url` is set; opens the Drive link in a new tab
     - Edit / Delete icons in the card footer

3. **"+ Add Document" CTA** opens a popup modal with:
   - Document type (Select)
   - Document name (Data)
   - Issue date + expiry date
   - Status (Select)
   - **Upload section** — drag-and-drop or file picker (writes to `file` via Frappe Attach)
   - **Google Drive URL section** — paste URL input with live validation (must start with `https://drive.google.com/` or `https://docs.google.com/`)
   - Helper text: *"Upload a copy to Frappe OR paste a Google Drive link (or both). Drive links are preferred when the document already lives in the branch Drive folder."*
   - Save button is disabled until at least one of the two is provided (mirrors the backend `validate()` rule)

4. **Expiry dashboard strip** at the top of the Documents section:
   - "X expiring in 30 days • Y expired • Z valid" — counts pulled from the child table, with click-to-filter.

**Implementation note:** This is a bei-tasks (React/Next.js) frontend feature, not a Frappe Desk form. The Frappe Desk form also gets the fields (via Custom Fields), but the primary operator UX is on my.bebang.ph. The bei-tasks frontend reads Company data via Frappe API (`/api/resource/Company/<name>`) and renders it in the BEI design system (Shadcn UI + Tailwind). File uploads use the existing Frappe `/api/method/upload_file` endpoint; Drive URLs are plain text stored directly on the child table row.

**Rationale for dual pattern (not Drive-link-only):**
- Drive links are ideal for stable corporate documents (lease, BIR 2303, SEC cert) that already live in the shared Drive folder
- Upload is ideal for ad-hoc scans, inspection reports, or documents a store manager snaps on their phone and doesn't want to manually file to Drive first
- Having both removes the friction that would otherwise push users back to WhatsApp/email attachments
- The child table becomes a true compliance calendar either way — expiry tracking works regardless of where the bytes live

### Task 1.3: Verify fixture JSON is valid

```bash
python -c "import json; d=json.load(open('hrms/fixtures/custom_field.json')); print(f'{len(d)} custom fields, valid JSON')"
```

Check that:
1. No duplicate `name` values in the fixture
2. No duplicate `fieldname` values for `dt: "Company"`
3. All `insert_after` references point to fields that exist (either standard Company fields or earlier custom fields)

### Task 1.4a: Pre-migrate backup (MANDATORY — HB-6 gate)

```
MUST_CREATE: output/s181/backups/custom_field_BEFORE.json
MUST_CREATE: output/s181/backups/tabCustomField_Company_BEFORE.sql
MUST_CREATE: output/s181/backups/BACKUP_TIMESTAMP.txt
```

**Blocker 11 fix (audit amendment 2026-04-11):** adding 47 Custom Fields + 2 new child
DocTypes in a single `bench migrate` is a non-trivial schema change. If the migrate
fails partway, the working tree and the DB can end up in a mutually inconsistent state
(fixture updated on disk, half the rows inserted in `tabCustom Field`). Without a
pre-migrate snapshot there is no clean rollback path.

**Required before running `bench migrate`:**

```bash
# 1. Snapshot the fixture file
mkdir -p output/s181/backups
cp hrms/fixtures/custom_field.json output/s181/backups/custom_field_BEFORE.json

# 2. Dump the Company-scoped Custom Field rows from the DB (via SSM / bench console):
bench --site hq.bebang.ph mariadb -e "
  SELECT * FROM \`tabCustom Field\` WHERE dt='Company'
" > output/s181/backups/tabCustomField_Company_BEFORE.sql

# 3. Record the timestamp so recovery knows the baseline moment
date -Iseconds > output/s181/backups/BACKUP_TIMESTAMP.txt

# 4. Verify files exist
ls -la output/s181/backups/ | grep -E 'BEFORE|TIMESTAMP'
```

**Rollback procedure (if migrate fails):**

```bash
# 1. Restore the fixture file
cp output/s181/backups/custom_field_BEFORE.json hrms/fixtures/custom_field.json

# 2. Delete any partial S181 Custom Field rows (use the names from the fixture additions)
bench --site hq.bebang.ph mariadb -e "
  DELETE FROM \`tabCustom Field\`
  WHERE dt='Company'
    AND name LIKE 'Company-bir_legal%'
    OR name LIKE 'Company-branch_tin'
    OR name LIKE 'Company-bir_rdo_code'
    OR name LIKE 'Company-bir_registration_date'
    OR name LIKE 'Company-sec_registration%'
    OR name LIKE 'Company-location%'
    OR name LIKE 'Company-full_address'
    OR name LIKE 'Company-city'
    OR name LIKE 'Company-province'
    OR name LIKE 'Company-region'
    OR name LIKE 'Company-mall_or_building'
    OR name LIKE 'Company-gps_%'
    OR name LIKE 'Company-google_maps_place_id'
    OR name LIKE 'Company-operations%'
    OR name LIKE 'Company-entity_category'
    OR name LIKE 'Company-store_ownership_type'
    OR name LIKE 'Company-operational_status'
    OR name LIKE 'Company-opening_date'
    OR name LIKE 'Company-operating_hours'
    OR name LIKE 'Company-pos_system'
    OR name LIKE 'Company-mosaic_location_id'
    OR name LIKE 'Company-adms_devices%'
    OR name LIKE 'Company-contacts%'
    OR name LIKE 'Company-store_manager%'
    OR name LIKE 'Company-area_supervisor'
    OR name LIKE 'Company-regional_manager'
    OR name LIKE 'Company-compliance_docs%'
    OR name LIKE 'Company-compliance_documents'
    OR name LIKE 'Company-drive_folder_url'
    OR name LIKE 'Company-bd_pipeline%'
    OR name LIKE 'Company-pipeline_status'
    OR name LIKE 'Company-target_opening_date'
    OR name LIKE 'Company-lease_%'
    OR name LIKE 'Company-revenue_share_pct'
    OR name LIKE 'Company-provisioning_state%'
    OR name LIKE 'Company-first_provision_done';
"

# 3. Drop the two new child DocTypes if they were partially created
bench --site hq.bebang.ph mariadb -e "
  DROP TABLE IF EXISTS \`tabBEI Company Document\`;
  DROP TABLE IF EXISTS \`tabBEI Company ADMS Device\`;
  DELETE FROM tabDocType WHERE name IN ('BEI Company Document', 'BEI Company ADMS Device');
  DELETE FROM \`tabDocField\` WHERE parent IN ('BEI Company Document', 'BEI Company ADMS Device');
"

# 4. Clear cache and rebuild
bench --site hq.bebang.ph clear-cache
bench --site hq.bebang.ph build
```

If rollback succeeds, investigate the migrate failure (likely a fixture JSON error, a
circular `insert_after` chain, or a DocType JSON schema mismatch) and retry.

### Task 1.4: Verify bench migrate succeeds

```
MUST_VERIFY: bench migrate completes without errors
MUST_VERIFY: grep -c '| Company-' docs/plans/2026-04-10-sprint-181-company-master-extension.md returns 47
MUST_VERIFY: pre-migrate backup files (Task 1.4a) exist before running migrate — refuse otherwise
```

After creating the DocTypes and updating the fixture, first confirm Task 1.4a's three
backup files exist (HB-6 gate), then run `bench migrate` on the test site. If it fails,
execute the rollback procedure above, fix the fixture JSON, and retry (HB-5 applies).

---

## Phase 2: Auto-Provision on_update Hook (sentinel-gated)

**Units: 15** — Depends on Phase 1 (fields must exist for default account references, including the `first_provision_done` sentinel).

### Task 2.1: Implement auto_provision_company function

```
MUST_MODIFY: hrms/overrides/company.py
MUST_CONTAIN: 'auto_provision_company'
MUST_CONTAIN: 'set_backend_observability_context'
MUST_CONTAIN: 'ignore_root_company_validation'
MUST_CONTAIN: 'ensure_account'
MUST_CONTAIN: 'MASTER_SALES_TEMPLATE'
MUST_CONTAIN: 'savepoint'
```

Add to `hrms/overrides/company.py`:

```python
def auto_provision_company(doc, method=None):
    """Auto-provision COA, Warehouse, Cost Center, and default accounts on Company creation.

    **Lifecycle note (audit fix 2026-04-11, Blockers 9, 13):**
    This hook runs on ``Company.on_update`` with a ``first_provision_done`` sentinel
    Custom Field so that (a) it fires AFTER ERPNext's own ``create_default_accounts()``
    (which creates the Standard Template Debtors / Creditors / Cost of Goods Sold /
    Stores / All Warehouses / Main - Cost Center), and (b) it does not re-run on
    every subsequent save.

    S181 promise: BD creates a Company, clicks Save, and the entire accounting system
    is plugged in and ready.

    Uses frappe.db.savepoint() for atomicity — if provisioning fails, the Company
    record still saves but the S181 provisioning is rolled back, the sentinel is
    left unset, and the error is logged. Operator can click the "Retry Provisioning"
    button to run ``retry_provision_company`` (see Task 2.4).
    """
    # Blocker 13 guard: skip during bulk-import / migration so ERPNext's Data Import
    # Tool and `bench migrate` do not trigger 45+ provisioning runs at once.
    if frappe.flags.in_import or frappe.flags.in_migrate or frappe.flags.in_install:
        return

    # Blocker 9 fix: idempotency sentinel — only run once per company.
    # The field `first_provision_done` is a Custom Field on Company (see Phase 1).
    if frappe.db.get_value("Company", doc.name, "first_provision_done"):
        return

    from hrms.utils.sentry import set_backend_observability_context
    set_backend_observability_context(
        module="company",
        action="auto_provision_company",
        mutation_type="create",
        extras={"company": doc.name, "abbr": doc.abbr},
    )

    try:
        frappe.db.savepoint("s181_auto_provision")

        # Bypass ERPNext group-company validator for this session
        frappe.local.flags.ignore_root_company_validation = True

        # Step 0: Ensure ERPNext's default accounts / warehouses / cost center exist.
        # When on_update fires, ERPNext's own create_default_accounts() has typically
        # already run. Call it defensively so first-provision works even on edge cases
        # (e.g. Companies created via bench console bypassing the normal wizard path).
        try:
            if hasattr(doc, "create_default_accounts"):
                doc.create_default_accounts()
            if hasattr(doc, "create_default_warehouses"):
                doc.create_default_warehouses()
            if hasattr(doc, "create_default_cost_center"):
                doc.create_default_cost_center()
        except Exception as erpnext_err:
            # ERPNext defaults are best-effort; S181 template creates the critical
            # accounts regardless. Log and continue.
            frappe.log_error(
                title=f"S181 ERPNext default seeding non-fatal for {doc.name}",
                message=str(erpnext_err),
            )

        # Step 1: Create Warehouse (S181 branch warehouse)
        _ensure_warehouse(doc)

        # Step 2: Create Cost Center (S181 branch cost center)
        _ensure_cost_center(doc)

        # Step 3: Apply the 27-account Sales template (all Income root_type)
        _apply_sales_template(doc)

        # Step 4: Apply the Balance Sheet & Expense template — Asset / Liability /
        # Expense root groups + Debtors / Creditors / Cost of Goods Sold children.
        # This guarantees _set_default_accounts can find the targets even if ERPNext's
        # Standard Template hasn't populated them.
        _apply_balance_sheet_template(doc)

        # Step 5: Set default accounts (receivable / payable / expense / round-off)
        _set_default_accounts(doc)

        # Step 6: Create / link the BKI Customer via the S037 register (Blocker 4 fix)
        _ensure_bki_customer(doc)

        # Step 7: Mark the sentinel so this hook never re-runs for this company.
        frappe.db.set_value("Company", doc.name, "first_provision_done", 1, update_modified=False)

        frappe.db.release_savepoint("s181_auto_provision")
        frappe.msgprint(
            f"Auto-provisioned COA, Warehouse, Cost Center, default accounts and BKI Customer for {doc.name}",
            indicator="green",
            alert=True,
        )

    except Exception:
        frappe.db.rollback_to_savepoint("s181_auto_provision")
        frappe.log_error(
            title=f"S181 auto-provision failed for {doc.name}",
            message=frappe.get_traceback(),
        )
        frappe.msgprint(
            f"Auto-provisioning failed for {doc.name}. The company was created but COA/Warehouse/Cost Center must be set up manually — click 'Retry Provisioning' on the Company form, or call hrms.overrides.company.retry_provision_company via bench console. Check Error Log for details.",
            indicator="red",
            alert=True,
        )
```

### Task 2.2: Implement helper functions

Add these helpers to `hrms/overrides/company.py` (underscore-prefixed, private — no Sentry per DM-7 rule):

```python
def _ensure_warehouse(doc):
    """Create the default warehouse for the company."""
    wh_name = f"{doc.name} - {doc.abbr}"
    if not frappe.db.exists("Warehouse", wh_name):
        wh = frappe.new_doc("Warehouse")
        wh.warehouse_name = doc.name
        wh.company = doc.name
        wh.is_group = 0
        wh.flags.ignore_permissions = True
        wh.insert()


def _ensure_cost_center(doc):
    """Create the default cost center for the company."""
    cc_name = f"{doc.name} - {doc.abbr}"
    if not frappe.db.exists("Cost Center", cc_name):
        cc = frappe.new_doc("Cost Center")
        cc.cost_center_name = doc.name
        cc.company = doc.name
        cc.is_group = 0
        cc.flags.ignore_permissions = True
        cc.insert()


def _ensure_account(company, number, name, parent_number, is_group, root_type, account_type):
    """Idempotent account creation. Reuses the S175 ensure_account pattern.
    
    If account exists: verifies is_group and root_type match. Fixes mismatches via SQL.
    If account missing: creates it via frappe.new_doc("Account").
    """
    abbr = frappe.db.get_value("Company", company, "abbr")
    
    # Resolve parent
    if parent_number is None:
        # Root-level account — find the company's Income root group
        parent_name = frappe.db.get_value("Account", {
            "company": company,
            "root_type": root_type,
            "is_group": 1,
            "parent_account": ["in", ["", None]],
        }, "name")
        if not parent_name:
            frappe.log_error(f"S181: No {root_type} root group found on {company}. Creating account {number} with parent_account=None.")
    else:
        parent_name = frappe.db.get_value(
            "Account", {"company": company, "account_number": parent_number}, "name"
        )
        if not parent_name:
            frappe.throw(f"S181: Parent account {parent_number} not found for {company}")
    
    existing = frappe.db.get_value(
        "Account",
        {"company": company, "account_number": number},
        ["name", "is_group", "root_type"],
        as_dict=True,
    )
    
    if existing:
        # Verify is_group match
        if int(existing.is_group) != int(is_group):
            frappe.throw(
                f"S181: Account {number} on {company} has is_group={existing.is_group}, expected {is_group}"
            )
        # Fix root_type mismatch
        if existing.root_type != root_type:
            frappe.db.sql(
                "UPDATE `tabAccount` SET root_type=%s WHERE name=%s",
                (root_type, existing.name),
            )
        return existing.name
    
    # Create new account
    acc = frappe.new_doc("Account")
    acc.account_name = name
    acc.account_number = number
    acc.company = company
    acc.parent_account = parent_name
    acc.is_group = is_group
    acc.root_type = root_type
    if account_type:
        acc.account_type = account_type
    acc.flags.ignore_permissions = True
    acc.flags.ignore_mandatory = True
    acc.insert()
    return acc.name


# The 27-account Sales template (canonical from S175)
_MASTER_SALES_TEMPLATE = [
    # (number, name, parent_number, is_group, root_type, account_type)
    ("4000000", "SALES",                                      None,        1, "Income", None),
    ("4000100", "STORE SALES",                                "4000000",   1, "Income", None),
    ("4000110", "IN-STORE SALES",                             "4000100",   0, "Income", "Income Account"),
    ("4000120", "ONLINE SALES",                               "4000100",   1, "Income", None),
    ("4000121", "BEI WEBSITE",                                "4000120",   0, "Income", "Income Account"),
    ("4000122", "FOOD PANDA",                                 "4000120",   0, "Income", "Income Account"),
    ("4000123", "GRAB",                                       "4000120",   0, "Income", "Income Account"),
    ("4000200", "BKI SALES",                                  "4000000",   1, "Income", None),
    ("4000210", "DELIVERIES",                                 "4000200",   0, "Income", "Income Account"),
    ("4000220", "LOGISTICS",                                  "4000200",   1, "Income", None),
    ("4000221", "DELIVERY INCOME",                            "4000220",   0, "Income", "Income Account"),
    ("4000222", "LOGISTICS INCOME",                           "4000220",   0, "Income", "Income Account"),
    ("4000230", "FEES",                                       "4000000",   1, "Income", None),
    ("4000231", "ROYALTY FEES",                               "4000230",   0, "Income", "Income Account"),
    ("4000232", "MANAGEMENT FEES",                            "4000230",   0, "Income", "Income Account"),
    ("4000233", "FRANCHISE FEES",                             "4000230",   0, "Income", "Income Account"),
    ("4000234", "MARKETING FEES",                             "4000230",   0, "Income", "Income Account"),
    ("4000235", "E-COMMERCE FEES",                            "4000230",   0, "Income", "Income Account"),
    ("4000900", "DISCOUNTS AND PROMO",                        "4000000",   1, "Income", None),
    ("4000901", "SALES DISCOUNT DUE TO FREE HALOHALO",        "4000900",   0, "Income", "Income Account"),
    ("4000902", "SALES DISCOUNT OF SENIOR CITIZENS",          "4000900",   0, "Income", "Income Account"),
    ("4000903", "SALES DISCOUNTS OF PWDS",                    "4000900",   0, "Income", "Income Account"),
    ("4000904", "SALES DISCOUNTS OF STAFFS AND EMPLOYEES",    "4000900",   0, "Income", "Income Account"),
    ("4000905", "SALES DISCOUNTS FROM VAT OF PWD",            "4000900",   0, "Income", "Income Account"),
    ("4000906", "SALES DISCOUNTS FROM VAT OF SENIOR CITIZENS","4000900",   0, "Income", "Income Account"),
    ("4000907", "SALES REFUNDS TO CUSTOMER",                  "4000900",   0, "Income", "Income Account"),
    ("4000908", "SALES DISCOUNTS - EMPLOYEE DISC",            "4000900",   0, "Income", "Income Account"),
]
assert len(_MASTER_SALES_TEMPLATE) == 27


def _apply_sales_template(doc):
    """Apply the 27-account Sales template to a newly created company."""
    for number, name, parent_number, is_group, root_type, account_type in _MASTER_SALES_TEMPLATE:
        _ensure_account(doc.name, number, name, parent_number, is_group, root_type, account_type)


# Balance Sheet & Expense template — Blocker 5/9 fix (2026-04-11).
# Guarantees that Debtors / Creditors / Cost of Goods Sold exist on every newly
# provisioned Company, independent of whether ERPNext's Standard Template ran first.
# Idempotent: reuses existing accounts if ERPNext already created them under its
# own naming convention (account_name match), otherwise creates the S181 version.
_MASTER_BALANCE_SHEET_TEMPLATE = [
    # (number, name, parent_number, is_group, root_type, account_type)
    # ----- ASSETS -----
    ("1000000", "ASSETS",              None,        1, "Asset",     None),
    ("1100000", "CURRENT ASSETS",      "1000000",   1, "Asset",     None),
    ("1110000", "CASH AND EQUIVALENTS","1100000",   1, "Asset",     None),
    ("1110100", "CASH ON HAND",        "1110000",   0, "Asset",     "Cash"),
    ("1110200", "CASH IN BANK",        "1110000",   0, "Asset",     "Bank"),
    ("1120000", "ACCOUNTS RECEIVABLE", "1100000",   1, "Asset",     None),
    ("1120100", "Debtors",             "1120000",   0, "Asset",     "Receivable"),
    ("1130000", "INVENTORY",           "1100000",   0, "Asset",     "Stock"),
    # ----- LIABILITIES -----
    ("2000000", "LIABILITIES",         None,        1, "Liability", None),
    ("2100000", "CURRENT LIABILITIES", "2000000",   1, "Liability", None),
    ("2110000", "ACCOUNTS PAYABLE",    "2100000",   1, "Liability", None),
    ("2110100", "Creditors",           "2110000",   0, "Liability", "Payable"),
    ("2120000", "ROUND OFF",           "2100000",   0, "Liability", "Round Off"),
    # ----- EQUITY -----
    ("3000000", "EQUITY",              None,        1, "Equity",    None),
    ("3100000", "Retained Earnings",   "3000000",   0, "Equity",    None),
    # ----- EXPENSES -----
    ("5000000", "EXPENSES",                     None,        1, "Expense", None),
    ("5100000", "COST OF GOODS SOLD (GROUP)",   "5000000",   1, "Expense", None),
    ("5100100", "Cost of Goods Sold",           "5100000",   0, "Expense", "Cost of Goods Sold"),
    ("5200000", "OPERATING EXPENSES",           "5000000",   1, "Expense", None),
    ("5200100", "Stock Adjustment",             "5200000",   0, "Expense", "Stock Adjustment"),
]
assert len(_MASTER_BALANCE_SHEET_TEMPLATE) == 20


def _apply_balance_sheet_template(doc):
    """Apply the Asset/Liability/Equity/Expense skeleton so default-account lookups
    in `_set_default_accounts` always resolve.

    Idempotent: `_ensure_account` reuses accounts by (company, account_number) match,
    so this will not duplicate accounts ERPNext's Standard Template may have already
    created under the same numbers.
    """
    for number, name, parent_number, is_group, root_type, account_type in _MASTER_BALANCE_SHEET_TEMPLATE:
        _ensure_account(doc.name, number, name, parent_number, is_group, root_type, account_type)


def _set_default_accounts(doc):
    """Set default income / expense / receivable / payable / round-off accounts on the company.

    **Blocker 5 fix (2026-04-11):** this used to silently no-op because Debtors /
    Creditors / Cost of Goods Sold were assumed to come from ERPNext's Standard
    Template. At `after_insert` that template had not run yet. With the lifecycle
    moved to `on_update` + sentinel AND `_apply_balance_sheet_template` running
    earlier in `auto_provision_company`, the required accounts are now guaranteed
    to exist by the time this helper runs.
    """
    abbr = doc.abbr

    # Default income account = IN-STORE SALES (the most common revenue posting account)
    income_account = frappe.db.get_value(
        "Account", {"company": doc.name, "account_number": "4000110"}, "name"
    )
    if income_account:
        doc.db_set("default_income_account", income_account)

    # Default receivable / payable / expense / round-off / cash.
    # Lookups are tolerant — try S181's numbered accounts first, fall back to
    # ERPNext Standard Template name-based matches.
    default_map = [
        ("default_receivable_account", ["1120100"], ["Debtors"]),
        ("default_payable_account",    ["2110100"], ["Creditors"]),
        ("default_expense_account",    ["5100100"], ["Cost of Goods Sold"]),
        ("round_off_account",          ["2120000"], ["Round Off"]),
        ("default_cash_account",       ["1110100"], ["Cash", "Cash On Hand"]),
    ]
    missing = []
    for field, numbers, names in default_map:
        account = None
        for num in numbers:
            account = frappe.db.get_value(
                "Account",
                {"company": doc.name, "account_number": num, "is_group": 0},
                "name",
            )
            if account:
                break
        if not account:
            for nm in names:
                account = frappe.db.get_value(
                    "Account",
                    {"company": doc.name, "account_name": nm, "is_group": 0},
                    "name",
                )
                if account:
                    break
        if account:
            doc.db_set(field, account)
        else:
            missing.append(field)

    if missing:
        # This should NOT happen because _apply_balance_sheet_template runs first,
        # but if it does, raise so the savepoint rolls back and the operator sees
        # a clear error instead of a silently half-provisioned company.
        frappe.throw(
            f"S181 _set_default_accounts: missing required default accounts on {doc.name}: {missing}. "
            f"Check that _apply_balance_sheet_template ran successfully."
        )


def _ensure_bki_customer(doc):
    """Ensure the BKI Customer for this company exists using S037 register + ENTITY_TIN_RDO.

    **Why this is non-trivial (audit fix 2026-04-11, Blocker 4):**
    S168's `build_bki_store_sale_invoice` in `hrms/api/commissary.py:1027-1050` looks up
    the Customer via `frappe.db.get_value("Customer", {"customer_name": buyer_entity_name}, "name")`
    and THROWS if not found. The `buyer_entity_name` comes from the S037 register
    (`data/_CLEANROOM/2026-03-12-s037-store-buyer-entity-register/store_buyer_entity_register_2026-03-12.csv`)
    — it is NOT the Frappe Company docname. 48 stores map to only 38 unique buyer entities
    (e.g. "Ayala Evo City" store → "Bebang Mega Inc" buyer entity → "Ayala Evo - Bebang Enterprise Inc." Frappe docname).

    Tax details (TIN / RDO / VAT status) live in the ENTITY_TIN_RDO register
    (`data/_CLEANROOM/batch_2026-02-28_cleanroom_v1/raw_snapshot/ENTITY_TIN_RDO_2026-02-27.csv`),
    keyed by `Entity Name` which matches `buyer_entity_name` from S037.

    Therefore this helper MUST:
    1. Resolve the buyer_entity_name for `doc` via the S037 register (match by store_name OR warehouse_docname)
    2. If found, look up tax details in ENTITY_TIN_RDO by Entity Name = buyer_entity_name
    3. Create the Customer with customer_name = buyer_entity_name (NOT doc.name)
    4. Copy tax_id / RDO / VAT status from ENTITY_TIN_RDO onto the Customer (when columns exist on Customer)
    5. Default territory = "Philippines", customer_group = "BKI Store"
    6. If the buyer_entity_name is already linked to an existing Customer, DO NOT create a duplicate
    7. If the register doesn't map this company, log INFO and skip — do NOT block Company creation.
       (Head office / commissary / holding / franchisor entities do not need a BKI Customer.)

    This is idempotent and matches the convention in `scripts/s168_seed_customers.py`.
    """
    import csv, os

    # --- S037 register path ---
    s037_path = os.path.normpath(frappe.get_app_path(
        "hrms", "..", "data", "_CLEANROOM",
        "2026-03-12-s037-store-buyer-entity-register",
        "store_buyer_entity_register_2026-03-12.csv",
    ))
    # --- ENTITY_TIN_RDO register path (for tax details) ---
    tin_register_path = os.path.normpath(frappe.get_app_path(
        "hrms", "..", "data", "_CLEANROOM",
        "batch_2026-02-28_cleanroom_v1", "raw_snapshot",
        "ENTITY_TIN_RDO_2026-02-27.csv",
    ))

    if not os.path.exists(s037_path):
        frappe.log_error(
            title="S181 _ensure_bki_customer: S037 register missing",
            message=f"Cannot resolve BKI Customer for {doc.name} — register not found at {s037_path}",
        )
        return

    # --- Step 1: find this Company in S037 by store_name OR warehouse_docname ---
    buyer_row = None
    with open(s037_path, encoding="utf-8-sig") as f:  # utf-8-sig handles possible BOM
        for row in csv.DictReader(f):
            wh_docname = (row.get("warehouse_docname") or "").strip()
            store_name = (row.get("store_name") or "").strip()
            if wh_docname == doc.name or store_name == doc.name:
                buyer_row = row
                break

    if not buyer_row:
        # Non-store companies (head office, commissary, holding, franchisor) do not need
        # a BKI Customer. Log info and skip gracefully.
        frappe.logger().info(
            f"S181 _ensure_bki_customer: {doc.name} not in S037 register — skipping BKI Customer (expected for non-store entities)"
        )
        return

    buyer_entity_name = (buyer_row.get("buyer_entity_name") or "").strip()
    if not buyer_entity_name:
        frappe.log_error(
            title="S181 _ensure_bki_customer: empty buyer_entity_name",
            message=f"Row for {doc.name} has no buyer_entity_name: {buyer_row}",
        )
        return

    # --- Step 2: idempotent — if Customer already exists, don't duplicate ---
    existing = frappe.db.get_value("Customer", {"customer_name": buyer_entity_name}, "name")
    if existing:
        return  # Another store already created this BKI Customer — shared across stores by design

    # --- Step 3: look up tax details from ENTITY_TIN_RDO (optional — may not exist for every entity) ---
    tax_id = None
    rdo = None
    vat_status = None
    if os.path.exists(tin_register_path):
        with open(tin_register_path, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                # ENTITY_TIN_RDO column headers: "Entity Name", "TIN", "RDO Code", "VAT Status"
                entity_name = (row.get("Entity Name") or "").strip()
                if entity_name == buyer_entity_name:
                    tax_id = (row.get("TIN") or "").strip() or None
                    rdo = (row.get("RDO Code") or "").strip() or None
                    vat_status = (row.get("VAT Status") or "").strip() or None
                    break

    # --- Step 4: create Customer ---
    customer = frappe.new_doc("Customer")
    customer.customer_name = buyer_entity_name
    customer.customer_type = "Company"
    customer.customer_group = "BKI Store"
    customer.territory = "Philippines"
    customer.default_currency = "PHP"
    if tax_id:
        customer.tax_id = tax_id
    # Set custom fields only if they exist on the Customer DocType
    meta = frappe.get_meta("Customer")
    if rdo and meta.has_field("custom_bir_rdo_code"):
        customer.custom_bir_rdo_code = rdo
    if vat_status and meta.has_field("custom_vat_status"):
        customer.custom_vat_status = vat_status
    customer.flags.ignore_permissions = True
    customer.flags.ignore_mandatory = True
    customer.insert()
```

### Task 2.3: Register on_update hook in hooks.py

```
MUST_MODIFY: hrms/hooks.py
```

**Lifecycle note (audit fix 2026-04-11, Blocker 9):** the provisioning hook is registered
on `on_update` (NOT `after_insert`) so that ERPNext's own `create_default_accounts()` /
`create_default_warehouses()` / `create_default_cost_center()` have already run by the
time `auto_provision_company` fires. The `first_provision_done` sentinel Custom Field
ensures the hook runs exactly once per company.

Update the Company doc_events at line 181:

```python
"Company": {
    "validate": "hrms.overrides.company.validate_default_accounts",
    "on_update": [
        "hrms.overrides.company.make_company_fixtures",
        "hrms.overrides.company.set_default_hr_accounts",
        "hrms.overrides.company.auto_provision_company",      # S181 — runs once per company (sentinel gated)
        "hrms.overrides.company.auto_enroll_adms_devices",    # S181 — idempotent, enqueued
    ],
    "on_trash": "hrms.overrides.company.handle_linked_docs",
},
```

### Task 2.4: Add `retry_provision_company` whitelisted method + UI button

```
MUST_MODIFY: hrms/overrides/company.py
MUST_CONTAIN: '@frappe.whitelist'
MUST_CONTAIN: 'retry_provision_company'
MUST_CONTAIN: 'first_provision_done'
```

**Blocker 14 fix (2026-04-11):** if `auto_provision_company` fails midway (e.g. the
savepoint rolls back because an account insertion failed), the Company record is still
saved but the sentinel is not set. The operator needs a one-click path to retry.

```python
@frappe.whitelist()
def retry_provision_company(company_name: str):
    """Retry S181 auto-provisioning for a Company whose first-provision attempt failed.

    Permission: requires "Accounts Manager" role.
    Idempotent: safe to call repeatedly; reuses existing accounts/warehouses/cost centers.
    """
    from hrms.utils.sentry import set_backend_observability_context
    set_backend_observability_context(
        module="company",
        action="retry_provision_company",
        mutation_type="update",
        extras={"company": company_name},
    )

    if not frappe.has_permission("Company", "write", doc=company_name):
        frappe.throw("Not permitted to retry provisioning for this company.")

    doc = frappe.get_doc("Company", company_name)
    # Clear the sentinel so auto_provision_company runs again
    frappe.db.set_value("Company", company_name, "first_provision_done", 0, update_modified=False)
    # Call directly — this WILL honor the in_import/in_migrate guard and the sentinel
    auto_provision_company(doc)
    return {"ok": True, "company": company_name}
```

Add a form button that calls this method from the Desk Company form. In
`hrms/public/js/company.js` (create if missing):

```javascript
frappe.ui.form.on("Company", {
    refresh(frm) {
        if (frm.doc.first_provision_done != 1) {
            frm.add_custom_button(__("Retry Provisioning (S181)"), () => {
                frappe.call({
                    method: "hrms.overrides.company.retry_provision_company",
                    args: { company_name: frm.doc.name },
                    freeze: true,
                    freeze_message: __("Retrying S181 provisioning..."),
                    callback(r) {
                        if (!r.exc) frm.reload_doc();
                    },
                });
            }, __("Actions"));
        }
    }
});
```

Also register the JS in `hrms/hooks.py`:

```python
doctype_js = {"Company": "public/js/company.js"}
```

The frontend (Company Master page in bei-tasks) also exposes this retry via a
"Retry Provisioning" pill on the Identity section card when
`first_provision_done == 0`. See Phase 3C Task 3C.3.

### Task 2.5: Verify hook registration

```bash
bench --site hq.bebang.ph console
>>> import frappe
>>> hooks = frappe.get_hooks("doc_events")
>>> print(hooks.get("Company", {}).get("on_update"))
# Must include: 'hrms.overrides.company.auto_provision_company'
# Must include: 'hrms.overrides.company.auto_enroll_adms_devices'
```

---

## Phase 2B: Backend API Methods for the Frontend Lane

**Units: 10** — Depends on Phase 1 (fields must exist) and Phase 2 (hook must exist).

**Blocker 6 fix (audit amendment 2026-04-11):** the original draft told the bei-tasks
frontend to read/write Company data via `/api/resource/Company/<name>`. That pattern
does NOT match the rest of the bei-tasks codebase — `lib/queries/hr-employee-detail.ts`,
`lib/queries/hr-payroll.ts`, `app/dashboard/hr/overtime/apply/`, and every other bei-tasks
surface uses the `/api/frappe/api/method/<module>.<function>` proxy exclusively. Trying
to mix patterns would break CSRF handling and the child-table PATCH semantics that
bei-tasks has already solved for its other pages.

This phase publishes a dedicated `hrms.api.company_master` module with the exact
endpoints the frontend lane consumes, matching the convention across all existing
bei-tasks integrations.

### Task 2B.1: Create the `hrms.api.company_master` module

```
MUST_CREATE: hrms/api/company_master.py
MUST_CONTAIN: '@frappe.whitelist'
MUST_CONTAIN: 'list_companies'
MUST_CONTAIN: 'get_company'
MUST_CONTAIN: 'update_company_section'
MUST_CONTAIN: 'upsert_compliance_document'
MUST_CONTAIN: 'delete_compliance_document'
MUST_CONTAIN: 'upsert_adms_device'
MUST_CONTAIN: 'delete_adms_device'
MUST_CONTAIN: 'retry_provision'
MUST_CONTAIN: 'set_backend_observability_context'
```

Endpoints (all `@frappe.whitelist()`):

```python
# hrms/api/company_master.py
import frappe
from frappe import _
from hrms.utils.sentry import set_backend_observability_context


# Fields that the frontend is allowed to write, grouped by section.
# Keeps mass assignment safe — the frontend cannot mutate fields outside this list.
EDITABLE_SECTIONS = {
    "bir_legal": [
        "company_name", "tax_id", "branch_tin", "bir_rdo_code",
        "bir_registration_date", "sec_registration_no", "sec_registration_date",
    ],
    "location": [
        "full_address", "city", "province", "region", "mall_or_building",
        "gps_latitude", "gps_longitude", "google_maps_place_id",
    ],
    "operations": [
        "entity_category", "store_ownership_type", "operational_status",
        "opening_date", "operating_hours", "pos_system", "mosaic_location_id",
    ],
    "contacts": [
        "store_manager", "store_manager_phone", "area_supervisor", "regional_manager",
    ],
    "compliance": ["drive_folder_url"],
    "bd_pipeline": [
        "pipeline_status", "target_opening_date", "lease_start_date",
        "lease_end_date", "lease_monthly_rent", "revenue_share_pct",
    ],
}


@frappe.whitelist()
def list_companies(filters: dict | None = None, search: str | None = None):
    """Return the list rows for the Company Master table.

    Projects only the columns the list page needs (name, entity_category,
    store_ownership_type, operational_status, city, first_provision_done).
    """
    set_backend_observability_context(module="company", action="list_companies", mutation_type="read")
    where = ["1=1"]
    params = {}
    if filters:
        if filters.get("entity_category"):
            where.append("entity_category = %(ec)s")
            params["ec"] = filters["entity_category"]
        if filters.get("store_ownership_type"):
            where.append("store_ownership_type = %(sot)s")
            params["sot"] = filters["store_ownership_type"]
        if filters.get("operational_status"):
            where.append("operational_status = %(os)s")
            params["os"] = filters["operational_status"]
    if search:
        where.append("(name LIKE %(s)s OR company_name LIKE %(s)s OR city LIKE %(s)s)")
        params["s"] = f"%{search}%"
    sql = f"""
        SELECT name, company_name, abbr, entity_category, store_ownership_type,
               operational_status, city, province, mosaic_location_id,
               first_provision_done
        FROM `tabCompany`
        WHERE {' AND '.join(where)}
        ORDER BY entity_category, name
    """
    return frappe.db.sql(sql, params, as_dict=True)


@frappe.whitelist()
def get_company(name: str):
    """Return the full Company document including all S181 Custom Fields,
    the stakeholders / adms_devices / compliance_documents child tables, and
    a computed expiry_summary for the compliance calendar strip.
    """
    set_backend_observability_context(module="company", action="get_company", mutation_type="read", extras={"company": name})
    if not frappe.has_permission("Company", "read", doc=name):
        frappe.throw(_("Not permitted to read company {0}").format(name))
    doc = frappe.get_doc("Company", name).as_dict()
    # Compute expiry summary for the Compliance Documents section strip
    from frappe.utils import getdate, add_days, today
    today_d = getdate(today())
    expiring = expired = valid = 0
    for d in doc.get("compliance_documents") or []:
        if d.get("expiry_date"):
            ed = getdate(d["expiry_date"])
            if ed < today_d:
                expired += 1
            elif ed <= add_days(today_d, 30):
                expiring += 1
            else:
                valid += 1
    doc["expiry_summary"] = {"valid": valid, "expiring": expiring, "expired": expired}
    return doc


@frappe.whitelist()
def update_company_section(name: str, section: str, payload: dict):
    """Update a single section of the Company form. Mass-assignment is restricted
    to `EDITABLE_SECTIONS[section]` — any field outside that allow-list is rejected.
    """
    set_backend_observability_context(
        module="company", action="update_company_section",
        mutation_type="update", extras={"company": name, "section": section},
    )
    if not frappe.has_permission("Company", "write", doc=name):
        frappe.throw(_("Not permitted to write company {0}").format(name))
    if section not in EDITABLE_SECTIONS:
        frappe.throw(_("Unknown section: {0}").format(section))

    allowed = set(EDITABLE_SECTIONS[section])
    clean = {k: v for k, v in (payload or {}).items() if k in allowed}
    if not clean:
        return {"ok": True, "noop": True}

    doc = frappe.get_doc("Company", name)
    for k, v in clean.items():
        doc.set(k, v)
    doc.save()  # triggers on_update — idempotent hooks are safe (sentinel-gated)
    return {"ok": True, "updated_fields": list(clean.keys())}


@frappe.whitelist()
def upsert_compliance_document(company: str, row: dict):
    """Create or update a BEI Company Document row on the Company's compliance_documents
    child table. Enforces the 'at least one of file OR drive_file_url' rule at the API
    layer too (in addition to the BEI Company Document controller validator).
    """
    set_backend_observability_context(
        module="company", action="upsert_compliance_document",
        mutation_type="update", extras={"company": company},
    )
    if not frappe.has_permission("Company", "write", doc=company):
        frappe.throw(_("Not permitted"))
    if not row.get("file") and not row.get("drive_file_url"):
        frappe.throw(_("Document must have either an uploaded File or a Google Drive URL (or both)."))
    if row.get("drive_file_url") and not (
        row["drive_file_url"].startswith("https://drive.google.com/")
        or row["drive_file_url"].startswith("https://docs.google.com/")
    ):
        frappe.throw(_("Google Drive URL must start with https://drive.google.com/ or https://docs.google.com/"))
    doc = frappe.get_doc("Company", company)
    if row.get("name"):
        for child in doc.compliance_documents:
            if child.name == row["name"]:
                child.update(row)
                break
    else:
        doc.append("compliance_documents", row)
    doc.save()
    return {"ok": True}


@frappe.whitelist()
def delete_compliance_document(company: str, row_name: str):
    set_backend_observability_context(
        module="company", action="delete_compliance_document",
        mutation_type="delete", extras={"company": company, "row": row_name},
    )
    if not frappe.has_permission("Company", "write", doc=company):
        frappe.throw(_("Not permitted"))
    doc = frappe.get_doc("Company", company)
    doc.compliance_documents = [c for c in doc.compliance_documents if c.name != row_name]
    doc.save()
    return {"ok": True}


@frappe.whitelist()
def upsert_adms_device(company: str, row: dict):
    """Add or update an ADMS device row. Saving triggers the on_update auto-enroll
    worker which enqueues the enrollment HTTP call in the background.
    """
    set_backend_observability_context(
        module="company", action="upsert_adms_device",
        mutation_type="update", extras={"company": company},
    )
    if not frappe.has_permission("Company", "write", doc=company):
        frappe.throw(_("Not permitted"))
    if not row.get("device_serial"):
        frappe.throw(_("device_serial is required"))
    # Cross-company uniqueness check — one device serial maps to one company
    existing = frappe.db.sql(
        """SELECT parent FROM `tabBEI Company ADMS Device`
           WHERE device_serial=%s AND parent != %s LIMIT 1""",
        (row["device_serial"], company),
    )
    if existing:
        frappe.throw(_("Device serial {0} is already assigned to company {1}").format(
            row["device_serial"], existing[0][0],
        ))
    doc = frappe.get_doc("Company", company)
    if row.get("name"):
        for child in doc.adms_devices:
            if child.name == row["name"]:
                child.update(row)
                break
    else:
        doc.append("adms_devices", row)
    doc.save()
    return {"ok": True}


@frappe.whitelist()
def delete_adms_device(company: str, row_name: str):
    set_backend_observability_context(
        module="company", action="delete_adms_device",
        mutation_type="delete", extras={"company": company, "row": row_name},
    )
    if not frappe.has_permission("Company", "write", doc=company):
        frappe.throw(_("Not permitted"))
    doc = frappe.get_doc("Company", company)
    doc.adms_devices = [d for d in doc.adms_devices if d.name != row_name]
    doc.save()
    return {"ok": True}


@frappe.whitelist()
def retry_provision(company: str):
    """Frontend-facing wrapper for `hrms.overrides.company.retry_provision_company`."""
    from hrms.overrides.company import retry_provision_company
    return retry_provision_company(company)
```

### Task 2B.2: Register Sentry instrumentation

Every endpoint above MUST call `set_backend_observability_context` as its first
meaningful line (DM-7 rule). The MUST_CONTAIN block above enforces this.

### Task 2B.3: Freeze the interface_contract.md artifact

```
MUST_CREATE: output/s181/interface_contract.md
```

Write a markdown document that lists every endpoint name, its HTTP method, its
argument schema, its response schema, and the exact Custom Field fieldnames the
frontend may read/write. This becomes the single source of truth for Phase 3B/3C
to consume — no frontend implementation may reference a field or endpoint that is
not in this file.

### Task 2B.4: Permission check

```bash
# From bench console
>>> from hrms.api.company_master import list_companies, get_company
>>> list_companies()  # Should return 45+ rows
>>> get_company("Bebang Enterprise Inc.")  # Should return dict with expiry_summary
```

---

## Phase 3: Seed Existing Companies With New Field Data

**Units: 12** — Depends on Phase 1 (fields must exist). No external input needed — all source CSVs are in the repo.

### Task 3.1: Build seeding script

```
MUST_CREATE: scripts/s181_phase_3_seed_company_fields.py
MUST_CONTAIN: 'entity_category'
MUST_CONTAIN: 'mosaic_location_id'
MUST_CONTAIN: 'gps_latitude'
MUST_CONTAIN: 'gps_longitude'
MUST_CONTAIN: 'operational_status'
```

This script reads 3 source CSVs and sets field values on existing companies via SSM:

1. **entity_category + store_ownership_type** (two-level fields) — from `store_buyer_entity_register_2026-03-12.csv` column `store_type`:
   - For stores: set `entity_category = "Store"` and `store_ownership_type` from the CSV:
     - CSV `JV` → `store_ownership_type = "JV"`
     - CSV `Managed Franchise` → `store_ownership_type = "Managed Franchise"`
     - CSV `Full Franchise` → `store_ownership_type = "Full Franchise"`
     - CSV empty/default → `store_ownership_type = "Company Owned"`
   - For non-stores: set `entity_category` directly, leave `store_ownership_type` empty:
     - `Bebang Enterprise Inc.` → `entity_category = "Head Office"`
     - `Bebang Kitchen Inc.` → `entity_category = "Commissary"`
     - `BEBANG FRANCHISE CORP.` → `entity_category = "Franchisor"`
     - `Irresistible Infusions Inc.` → `entity_category = "Holding Company"`
     - `DMD HOLDINGS INC.` → `entity_category = "Holding Company"`

2. **mosaic_location_id** — from `MOSAIC_POS_API_KEYS.csv` column `location_id`, matched by store name to company via store-entity mapping

3. **GPS coordinates + address + mall_or_building** — from `Bebang_Halo-Halo_Stores_Locations_2025-12-29.csv`, matched by store name

4. **operational_status** — set `Active` for all companies that exist and have stores with POS data. Set entities with `entity_category = 'Holding Company'` to `Active`.

5. **pos_system** — set `Mosaic` for all companies that have a `mosaic_location_id`

**Matching logic:** Normalize names: lowercase, strip "Inc.", "Corp.", "OPC", strip periods/commas/extra spaces. Use the store-entity mapping as the bridge between physical store names (in locations CSV / POS CSV) and Frappe company names.

### Task 3.2: Execute seeding script via SSM

```
MUST_CREATE: output/s181/phase3_seed_results.json
```

Run the script and capture results: how many companies updated, which fields populated, any unmatched stores.

### Task 3.3: Verify seeding

Assert:
1. At least 35 companies have `entity_category` populated
2. At least 40 companies have `mosaic_location_id` populated (45 stores in Mosaic)
3. At least 30 companies have `gps_latitude` and `gps_longitude` populated
4. `operational_status` = `Active` for all companies that have stores

---

## Phase 3B: bei-tasks Company Master — List Page + Fullscreen Detail Dialog

**Units: 12** — Frontend lane. Runs in the `bei-tasks` repo on branch
`s181-company-master-frontend`. Blocked until: Phase 2B merged + Phase 1 bench migrate
succeeded on `hq.bebang.ph` + `output/s181/interface_contract.md` exists.

**Pattern reference:** `bei-tasks/app/dashboard/hr/employee-master/page.tsx` +
`employee-detail-dialog.tsx`. The Company Master page is a DIRECT structural mirror —
list table at the top, click a row to open a fullscreen dialog that overlays the list
(no route change). This is the pattern Sam locked on 2026-04-10.

### Task 3B.1: Create the query module

```
MUST_CREATE: bei-tasks/lib/queries/company-master.ts
MUST_CONTAIN: '/api/frappe/api/method/hrms.api.company_master.list_companies'
MUST_CONTAIN: '/api/frappe/api/method/hrms.api.company_master.get_company'
MUST_CONTAIN: '/api/frappe/api/method/hrms.api.company_master.update_company_section'
MUST_CONTAIN: '/api/frappe/api/method/hrms.api.company_master.upsert_compliance_document'
MUST_CONTAIN: '/api/frappe/api/method/hrms.api.company_master.delete_compliance_document'
MUST_CONTAIN: '/api/frappe/api/method/hrms.api.company_master.upsert_adms_device'
MUST_CONTAIN: '/api/frappe/api/method/hrms.api.company_master.delete_adms_device'
MUST_CONTAIN: '/api/frappe/api/method/hrms.api.company_master.retry_provision'
MUST_CONTAIN: 'useCompanyList'
MUST_CONTAIN: 'useCompanyDetail'
```

Mirror the structure of `bei-tasks/lib/queries/hr-employee-detail.ts`. Export TanStack
Query hooks: `useCompanyList(filters, search)`, `useCompanyDetail(name)`,
`useUpdateCompanySection()`, `useUpsertComplianceDocument()`, `useDeleteComplianceDocument()`,
`useUpsertAdmsDevice()`, `useDeleteAdmsDevice()`, `useRetryProvision()`. All API calls
go through the `/api/frappe/api/method/hrms.api.company_master.*` proxy.

### Task 3B.2: Add RBAC role + route permissions

```
MUST_MODIFY: bei-tasks/lib/roles.ts
MUST_CONTAIN: 'business-development'
MUST_CONTAIN: 'company-master'
```

Add module entry:

```typescript
// bei-tasks/lib/roles.ts — MODULES map
"company-master": {
    label: "Company Master",
    href: "/dashboard/bd/companies",
    icon: "Building2",
    allowedRoles: [
        "System Manager",
        "Accounts Manager",
        "Business Development",
        "BD Manager",
    ],
    section: "Operations",
},
```

If the "Business Development" / "BD Manager" roles don't yet exist in Frappe, create
them via a one-line SSM script (included in Phase 3B's deployment task).

### Task 3B.3: Create the list page

```
MUST_CREATE: bei-tasks/app/dashboard/bd/companies/page.tsx
MUST_CONTAIN: 'use client'
MUST_CONTAIN: 'useCompanyList'
MUST_CONTAIN: 'CompanyDetailDialog'
MUST_CONTAIN: 'entity_category'
MUST_CONTAIN: 'store_ownership_type'
MUST_CONTAIN: 'operational_status'
MUST_CONTAIN: 'Retry Provisioning'
MUST_MODIFY: bei-tasks/app/dashboard/layout.tsx
```

Structure (follow `employee-master/page.tsx` line-for-line):

- Header: `<PageHeader title="Company Master" description="BEI group companies with full provisioning state" />`
- Filter chip row:
  - Entity Category (Head Office / Commissary / Store / Warehouse / Holding Company / Franchisor)
  - Store Ownership Type (Company Owned / JV / Managed Franchise / Full Franchise) — shown only when Entity Category = Store
  - Operational Status (Active / Pre-Opening / Temporarily Closed / Permanently Closed / Pipeline)
  - Region (NCR / Luzon / Visayas / Mindanao)
- Search input (debounced)
- Table columns: `name`, `entity_category` badge, `store_ownership_type` badge (if store), `operational_status` pill, `city`, `mosaic_location_id`, provisioning state icon (green check if `first_provision_done==1`, yellow warning if 0 with a "Retry Provisioning" tooltip CTA)
- Click row → opens `<CompanyDetailDialog open={...} onClose={...} companyName={row.name} />` as a fullscreen overlay (does NOT navigate)
- "+ New Company" button in the header (opens an inline creation dialog — minimal form: name, abbr, entity_category. Save creates via `frappe.client.insert` through the Frappe proxy. Full editing is then done in the detail dialog.)

Also add a sidebar entry: modify `bei-tasks/app/dashboard/layout.tsx` (or the sidebar
component it pulls from) to add "Company Master" under the existing "Operations" section,
visible only to the roles listed in `roles.ts`.

### Task 3B.4: Create the fullscreen detail dialog

```
MUST_CREATE: bei-tasks/app/dashboard/bd/companies/company-detail-dialog.tsx
MUST_CONTAIN: 'useCompanyDetail'
MUST_CONTAIN: 'BIR & Legal Identity'
MUST_CONTAIN: 'Location'
MUST_CONTAIN: 'Operations'
MUST_CONTAIN: 'ADMS Devices'
MUST_CONTAIN: 'Contacts'
MUST_CONTAIN: 'Compliance Documents'
MUST_CONTAIN: 'BD Pipeline'
MUST_CONTAIN: 'Stakeholders'
MUST_CONTAIN: 'Retry Provisioning'
MUST_CONTAIN: 'first_provision_done'
```

Structure (mirror `employee-detail-dialog.tsx`):

- Fullscreen overlay (Dialog from Shadcn with `className="max-w-none w-screen h-screen"`)
- Top bar: company name, abbr, entity_category + store_ownership_type badges, close button, `Retry Provisioning` button shown ONLY when `first_provision_done == 0` (calls `useRetryProvision()` hook)
- Scrollable body with collapsible section cards (one per Section from Phase 1):
  1. **BIR & Legal Identity** — branch_tin, bir_rdo_code, bir_registration_date, sec_registration_no, sec_registration_date
  2. **Location** — full_address, city, province, region, mall_or_building, gps_latitude, gps_longitude, google_maps_place_id
  3. **Operations** — entity_category, store_ownership_type (depends_on), operational_status, opening_date, operating_hours, pos_system, mosaic_location_id
  4. **ADMS Devices** (child table grid, see Phase 3C)
  5. **Contacts** — store_manager (Employee Link picker), store_manager_phone, area_supervisor, regional_manager
  6. **Stakeholders** (child table grid — already exists from S178, reuse the existing pattern)
  7. **Compliance Documents** (child table + Drive folder banner — see Phase 3C)
  8. **BD Pipeline** — pipeline_status, target_opening_date, lease_start_date, lease_end_date, lease_monthly_rent, revenue_share_pct
- Each section card has an **Edit** button (opens a popup modal — see Phase 3C)
- Each section card is collapsible (collapsed by default except the first)
- Loading / empty / error states implemented per S026 rule

### Task 3B.5: L3 scenarios for Phase 3B

Add two new L3 scenarios (numbered 5.8 and 5.9):

**Scenario 5.8: Company Master list page + filter + open detail dialog**
- Log in as a user with "Business Development" role
- Navigate to `/dashboard/bd/companies`
- Verify the page loads with 45+ rows
- Click the "Entity Category" filter, select "Store", verify the row count drops (~48 stores)
- Click the "Store Ownership Type" filter (now visible), select "Managed Franchise"
- Click the first row in the filtered list
- Verify the fullscreen detail dialog opens with the company name in the top bar
- Verify all 8 section cards render with correct labels
- Close the dialog — URL should not have changed
- Evidence: `form_submissions.json` (filter changes), `api_mutations.json` (none yet — read-only), `state_verification.json` (row counts)

**Scenario 5.9: Retry Provisioning button gates on `first_provision_done`**
- Create a Company via `bench console` bypassing the on_update hook: `company = frappe.new_doc("Company"); company.company_name = "S181 L3 Test"; ...; company.insert(); frappe.db.set_value("Company", "S181 L3 Test", "first_provision_done", 0)`
- Open `/dashboard/bd/companies`, find "S181 L3 Test", click to open detail dialog
- Verify "Retry Provisioning" button is visible in the top bar
- Click it → verify the API call `hrms.api.company_master.retry_provision` is made
- Verify `first_provision_done` flips to 1 after success
- Verify the button disappears on re-render
- Evidence: trio files

---

## Phase 3C: bei-tasks Company Master — Section Edit Modals + ADMS + Documents

**Units: 10** — Frontend lane. Depends on Phase 3B.

### Task 3C.1: Section Edit Modal component

```
MUST_CREATE: bei-tasks/components/company-master/section-edit-modal.tsx
MUST_CONTAIN: 'useUpdateCompanySection'
MUST_CONTAIN: 'section'
```

A reusable modal that takes a `section` prop (bir_legal / location / operations / contacts / compliance / bd_pipeline) and renders the matching form. On Save, calls
`useUpdateCompanySection(companyName, section, payload)`. Uses Shadcn Dialog + react-hook-form + zod validation.

### Task 3C.2: ADMS Devices child table grid

```
MUST_CREATE: bei-tasks/components/company-master/adms-devices-grid.tsx
MUST_CONTAIN: 'useUpsertAdmsDevice'
MUST_CONTAIN: 'useDeleteAdmsDevice'
MUST_CONTAIN: 'device_serial'
MUST_CONTAIN: 'bio_device_id'
MUST_CONTAIN: 'adms_enrolled'
```

Inline editable grid rendered inside the "ADMS Devices" section card:
- Columns: Device Serial, Device Name, Bio Device ID, IP Address, Enrollment Status (badge: ✅ Enrolled / ⏳ Pending / ❌ Failed)
- "+ Add Device" button opens a small inline form
- On save, calls `upsertAdmsDevice`
- Enrollment status is read-only from `adms_enrolled` flag
- Background job polling: refetch every 15s while any row is ⏳ Pending

### Task 3C.3: Compliance Documents section (dual upload + Drive link pattern)

```
MUST_CREATE: bei-tasks/components/company-master/compliance-documents-section.tsx
MUST_CONTAIN: 'drive_folder_url'
MUST_CONTAIN: 'drive_file_url'
MUST_CONTAIN: 'file'
MUST_CONTAIN: 'expiry_summary'
MUST_CONTAIN: 'Open Branch Drive Folder'
MUST_CONTAIN: 'Open in Drive'
MUST_CONTAIN: 'Download'
MUST_CONTAIN: 'useUpsertComplianceDocument'
```

Follows the dual-pattern spec already in Task 1.1c (DO NOT REMOVE THAT SPEC — this task
is the implementation contract for the spec). Key elements:

1. **Drive Folder pill** — at the top of the section. Shows "📁 Open Branch Drive Folder"
   when `drive_folder_url` is set (opens in new tab); shows "+ Link Branch Drive Folder"
   inline input when empty. Edit pencil icon to replace URL.
2. **Expiry summary strip** — green/yellow/red counts pulled from `expiry_summary` in
   the `get_company` response. Click to filter the grid below.
3. **Document cards grid** — one card per row in `compliance_documents`:
   - Type icon + name + status pill + expiry countdown
   - **⬇ Download** button (enabled when `file` is set — calls Frappe file download via proxy)
   - **🔗 Open in Drive** button (enabled when `drive_file_url` is set — opens new tab)
   - Edit / Delete icons in footer
4. **+ Add Document popup** — react-hook-form modal with:
   - Document Type (Select)
   - Document Name (Input)
   - Issue Date / Expiry Date (DatePicker)
   - Status (Select, default "Valid")
   - **Upload** section: drag-drop + file picker using Frappe upload endpoint
   - **Google Drive URL** section: Input with live regex validation
     (`/^https:\/\/(drive|docs)\.google\.com\//`)
   - Helper text: *"Upload a copy to Frappe OR paste a Google Drive link (or both). Drive
     links are preferred when the document already lives in the branch Drive folder."*
   - Save button is DISABLED until at least one of file / URL is provided (mirrors backend
     validator in `BEI Company Document.validate()` and in `upsert_compliance_document`)

### Task 3C.4: Stakeholders child table grid (reuse S178 pattern)

```
MUST_CREATE: bei-tasks/components/company-master/stakeholders-grid.tsx
```

S178 added the `stakeholders` Custom Field (Table) on Company. Reuse the existing pattern
from whichever bei-tasks page already renders that child table. If none exists yet, mirror
the compensation-component grid in `components/hr/compensation-detail-panel.tsx`.

Columns: Stakeholder Name, Role, Ownership %, Email, Phone, Portal Access, Notes.

### Task 3C.5: L3 scenarios for Phase 3C

Already covered by Scenario 5.7 (dual upload + Drive link) which was added in v3. Verify
5.7 passes end-to-end through the bei-tasks UI (not just the backend validator):
- Open a company detail dialog
- Open the Compliance Documents section
- Click "+ Add Document"
- Try to save with empty file and empty URL → save button stays disabled
- Fill only the file upload → save enabled → save succeeds
- Fill only the Drive URL → save enabled → save succeeds
- Fill invalid Drive URL → inline validation error
- Fill both → save succeeds

Evidence: trio files including `form_submissions.json` entry for the document save POST.

---

## Phase 4: Branch TIN Backfill Migration Script

**Units: 8** — Depends on Phase 1 (branch_tin field must exist).

### Task 4.1: Build branch TIN backfill script

```
MUST_CREATE: scripts/s181_phase_4_branch_tin_backfill.py
MUST_CONTAIN: 'branch_tin'
MUST_CONTAIN: 'bir_rdo_code'
MUST_CONTAIN: 'ENTITY_TIN_RDO'
```

Read `ENTITY_TIN_RDO_2026-02-27.csv`. For each row:
- If the entity has a branch TIN different from its head office TIN (column `tin` vs parent company's `tax_id`), set `branch_tin` on the Frappe Company
- Set `bir_rdo_code` from the RDO column
- Set `bir_registration_date` if available in the CSV

**Important:** S178 already populated `tax_id` on all companies. This phase adds the branch-level TIN (`branch_tin`) which may be different for stores registered under a separate BIR branch.

### Task 4.2: Execute branch TIN script via SSM

```
MUST_CREATE: output/s181/phase4_tin_results.json
```

### Task 4.3: Verify TIN backfill

Assert:
1. Companies with branch-specific TINs have `branch_tin` populated
2. At least 30 companies have `bir_rdo_code` populated
3. No `branch_tin` value is identical to the company's `tax_id` (that would be redundant — branch_tin is only for cases where it differs)

---

## Phase 5: L3 Testing — BD Creates a Test Company

**Units: 10** — Depends on Phase 2 (hook must be deployed).

### L3 Scenario 5.1: Happy Path — BD Creates a New Store Company

**Preconditions:**
- S181 code deployed to hq.bebang.ph (bench migrate completed)
- Logged in as Administrator

**Steps:**
1. Navigate to Company List → New Company
2. Fill in:
   - Company Name: `S181 Test Store Inc.`
   - Abbreviation: `S181T`
   - Default Currency: `PHP`
   - Country: `Philippines`
   - Entity Category: `Store`
   - Store Ownership Type: `Company Owned`
   - Operational Status: `Pipeline`
   - Region: `NCR`
3. Click Save

**Expected Results (all must be verified with evidence):**
- [ ] **E-5.1.1:** Green msgprint "Auto-provisioned COA, Warehouse, and Cost Center for S181 Test Store Inc."
- [ ] **E-5.1.2:** Warehouse `S181 Test Store Inc. - S181T` exists (`frappe.db.exists("Warehouse", "S181 Test Store Inc. - S181T")`)
- [ ] **E-5.1.3:** Cost Center `S181 Test Store Inc. - S181T` exists
- [ ] **E-5.1.4:** All 27 Sales template accounts exist under `S181 Test Store Inc.` (query: `SELECT COUNT(*) FROM tabAccount WHERE company='S181 Test Store Inc.' AND account_number LIKE '4%'` = 27)
- [ ] **E-5.1.5:** `default_income_account` is set to `IN-STORE SALES - S181T`
- [ ] **E-5.1.6:** `default_receivable_account` is set (Debtors)
- [ ] **E-5.1.7:** `default_payable_account` is set (Creditors)
- [ ] **E-5.1.8:** No entries in Error Log for "S181 auto-provision"
- [ ] **E-5.1.9:** Customer `S181 Test Store Inc.` exists with `customer_group='BKI Store'`

### L3 Scenario 5.2: Company With parent_company (Group Company Validation)

**Preconditions:** Same as 5.1.

**Steps:**
1. Create Company:
   - Company Name: `S181 Test JV Store Inc.`
   - Abbreviation: `S181J`
   - Parent Company: `Bebang Enterprise Inc.`
   - Entity Category: `Store`
   - Store Ownership Type: `JV`
2. Click Save

**Expected Results:**
- [ ] **E-5.2.1:** Company created without "Please add the account to root level Company" error (flag bypass works)
- [ ] **E-5.2.2:** All 27 Sales template accounts created
- [ ] **E-5.2.3:** Warehouse and Cost Center created

### L3 Scenario 5.3: Existing Company Update Does NOT Re-Provision

**Steps:**
1. Open `S181 Test Store Inc.` (created in 5.1)
2. Change `operational_status` to `Active`
3. Click Save

**Expected Results:**
- [ ] **E-5.3.1:** No "Auto-provisioned" msgprint (after_insert does not fire on update)
- [ ] **E-5.3.2:** Still exactly 27 Sales accounts (no duplicates)
- [ ] **E-5.3.3:** Warehouse count unchanged

### L3 Scenario 5.4: S175 Regression Check

**Steps:**
Run the S175 verification query:
```sql
SELECT company, COUNT(*) as cnt 
FROM tabAccount 
WHERE account_number LIKE '4%' 
GROUP BY company 
HAVING cnt < 27;
```

**Expected Results:**
- [ ] **E-5.4.1:** Query returns 0 rows (all existing companies still have their 27 accounts)
- [ ] **E-5.4.2:** S178 Custom Fields (store_locations, partner_names, stakeholders) still exist and have data

### L3 Scenario 5.5: Cleanup Test Data

**Steps:**
1. Delete `S181 Test JV Store Inc.` and `S181 Test Store Inc.`
2. Verify their Warehouses, Cost Centers, and Accounts are also deleted (Frappe cascades)

**Expected Results:**
- [ ] **E-5.5.1:** Both test companies deleted
- [ ] **E-5.5.2:** No orphan accounts remain for `S181T` or `S181J`

### L3 Scenario 5.6: ADMS Device Auto-Enrollment

**Steps:**
1. Open `S181 Test Store Inc.` (from 5.1)
2. Add a row to the ADMS Devices child table:
   - Device Serial: `TEST-SERIAL-001`
   - Device Name: `S181 Test - Main Entrance`
   - Bio Device ID: `999`
3. Click Save

**Expected Results:**
- [ ] **E-5.6.1:** Row saved with `adms_enrolled = 0` initially (ADMS API may not be reachable in test — enrollment attempt logged)
- [ ] **E-5.6.2:** Error Log contains an ADMS enrollment attempt entry (showing the API was called, even if it failed due to test device)
- [ ] **E-5.6.3:** No Python traceback on Save — the ADMS enrollment failure is caught by try/except and does NOT block the Company save

### L3 Scenario 5.7: Compliance Documents — Dual Upload + Drive Link Pattern

**Steps:**
1. Open `S181 Test Store Inc.` (from 5.1)
2. Set the `drive_folder_url` field at the top of the Compliance Documents section to `https://drive.google.com/drive/folders/1ABCtestfolder123`
3. Add 3 rows to the Compliance Documents child table:
   - Row A (upload only): document_type=`Lease Agreement`, document_name=`Test Lease`, issue_date=today, expiry_date=today+1year, file=`/files/test_lease.pdf` (pre-uploaded fixture), drive_file_url=empty
   - Row B (Drive link only): document_type=`BIR Form 2303`, document_name=`Test BIR 2303`, issue_date=today, file=empty, drive_file_url=`https://drive.google.com/file/d/1abc123/view`
   - Row C (both): document_type=`Business Permit`, document_name=`Test Mayors Permit`, issue_date=today, expiry_date=today+30days, file=`/files/test_permit.pdf`, drive_file_url=`https://drive.google.com/file/d/1def456/view`
4. Click Save
5. Try to add a Row D with NEITHER `file` NOR `drive_file_url` set — expect validation error
6. Try to set `drive_file_url = "https://example.com/bad"` on Row D — expect validation error

**Expected Results:**
- [ ] **E-5.7.1:** Company saves with all 3 valid rows in `compliance_documents` child table
- [ ] **E-5.7.2:** `frappe.db.get_value("Company", "S181 Test Store Inc.", "drive_folder_url")` returns the pasted URL
- [ ] **E-5.7.3:** Row A has `file` populated and `drive_file_url` empty (upload-only pattern works)
- [ ] **E-5.7.4:** Row B has `drive_file_url` populated and `file` empty (Drive-link-only pattern works)
- [ ] **E-5.7.5:** Row C has BOTH fields populated (dual pattern works)
- [ ] **E-5.7.6:** Row D (no file, no URL) raises a `frappe.ValidationError` with message containing "must have either an uploaded File or a Google Drive URL"
- [ ] **E-5.7.7:** Row D with invalid `drive_file_url` (non-Google domain) raises a `frappe.ValidationError` with message containing "must start with https://drive.google.com/"
- [ ] **E-5.7.8:** Expiry badge logic computes correctly: Row C (expires in 30 days) should be flagged as "Expiring" (yellow); Row A (expires in 1 year) should be "Valid" (green)

### L3 Scenario 5.8: BKI Customer Lookup via S037 Register (Blocker 4 fix)

**Steps:**
1. Create a new Company via `bench console` with a docname that matches a `warehouse_docname` in the S037 register (e.g. "Ayala Evo - Bebang Enterprise Inc."). Save.
2. Verify `auto_provision_company` ran (first_provision_done=1, no error log).
3. Query `tabCustomer` for the newly-linked BKI Customer.
4. Attempt to simulate an S168 BKI invoice lookup in bench console:
   ```python
   buyer_entity_name = "Bebang Mega Inc"  # from S037 row for Ayala Evo City
   found = frappe.db.get_value("Customer", {"customer_name": buyer_entity_name}, "name")
   ```
5. Create a second Company in the same buyer entity group (e.g. another store mapped to "Bebang Mega Inc") and verify it reuses the existing Customer without duplication.
6. Create a non-store Company (e.g. `entity_category == 'Head Office'`) and verify `_ensure_bki_customer` skips gracefully (no Customer created, no error).

**Expected Results:**
- [ ] **E-5.8.1:** Customer row created with `customer_name = "Bebang Mega Inc"` (NOT the Frappe docname)
- [ ] **E-5.8.2:** Customer has `tax_id`, `custom_bir_rdo_code`, `custom_vat_status` populated from S037 columns
- [ ] **E-5.8.3:** Customer has `customer_group = "BKI Store"` and `territory = "Philippines"`
- [ ] **E-5.8.4:** S168-style lookup `frappe.db.get_value("Customer", {"customer_name": "Bebang Mega Inc"}, "name")` returns a valid row
- [ ] **E-5.8.5:** Second store (same buyer entity) does NOT create a duplicate Customer — same customer row is reused
- [ ] **E-5.8.6:** Non-store Company (head office) does not trigger `_ensure_bki_customer` creation (skipped gracefully, info log only)
- [ ] **E-5.8.7:** Error Log has NO entry matching "S181 _ensure_bki_customer" (for the store case)

### L3 Scenario 5.9: Company Master list page + filter + detail dialog (Phase 3B)

**Steps:**
1. Log in to `https://my.bebang.ph` as a user with the "Business Development" role.
2. Navigate to `/dashboard/bd/companies`.
3. Verify the page loads with 45+ rows (list_companies endpoint called).
4. Click the "Entity Category" filter → select "Store" → verify row count drops to ~48.
5. Click the "Store Ownership Type" filter (now visible) → select "Managed Franchise" → verify row count drops further.
6. Click the first row in the filtered list → verify the fullscreen `CompanyDetailDialog` opens.
7. Verify the URL did NOT change (still `/dashboard/bd/companies`).
8. Verify all 8 section cards render with correct labels: BIR & Legal Identity, Location, Operations, ADMS Devices, Contacts, Stakeholders, Compliance Documents, BD Pipeline.
9. Close the dialog with the close button.

**Expected Results:**
- [ ] **E-5.9.1:** `list_companies` API call returns ≥45 rows (captured in `api_mutations.json`)
- [ ] **E-5.9.2:** Entity Category filter POST recorded in `form_submissions.json`
- [ ] **E-5.9.3:** Store Ownership Type filter is hidden when Entity Category != Store (DOM assertion)
- [ ] **E-5.9.4:** Fullscreen dialog opens with `companyName` prop = the clicked row's name
- [ ] **E-5.9.5:** All 8 section card headings present in the DOM
- [ ] **E-5.9.6:** Closing the dialog does not navigate away (URL unchanged, list page still mounted)

### L3 Scenario 5.10: Retry Provisioning button gates on `first_provision_done` (Blocker 14 fix)

**Steps:**
1. Create a Company via `bench console` bypassing the hook: `company = frappe.new_doc("Company"); company.company_name = "S181 L3 Test"; company.abbr = "SL"; company.default_currency = "PHP"; company.country = "Philippines"; company.insert(ignore_permissions=True); frappe.db.set_value("Company", "S181 L3 Test", "first_provision_done", 0)`
2. Open `/dashboard/bd/companies`, find "S181 L3 Test" in the list (should have a yellow warning icon in the provisioning state column).
3. Click the row → detail dialog opens → verify "Retry Provisioning" pill is visible in the top bar.
4. Click "Retry Provisioning" → verify API call `hrms.api.company_master.retry_provision` is made.
5. Verify `first_provision_done` flips to 1 in the DB after success.
6. Verify the "Retry Provisioning" pill disappears on re-render.
7. Verify the Desk-side button (in `company.js`) also appears when `first_provision_done == 0` — open `hq.bebang.ph/app/company/S181 L3 Test` and confirm the button is in the Actions menu.

**Expected Results:**
- [ ] **E-5.10.1:** "Retry Provisioning" pill visible in the bei-tasks detail dialog top bar when `first_provision_done == 0`
- [ ] **E-5.10.2:** API call `hrms.api.company_master.retry_provision` recorded in `api_mutations.json` with `{"company": "S181 L3 Test"}`
- [ ] **E-5.10.3:** After retry success, `frappe.db.get_value("Company", "S181 L3 Test", "first_provision_done")` returns 1
- [ ] **E-5.10.4:** Company now has COA (27 Sales accounts + 20 Balance Sheet accounts) + Warehouse + Cost Center + default_receivable_account + default_payable_account + default_expense_account populated
- [ ] **E-5.10.5:** After a subsequent save of the Company, auto_provision_company does NOT re-run (sentinel gate works) — verified by counting GL accounts before/after the save (no change)
- [ ] **E-5.10.6:** Desk-side "Retry Provisioning (S181)" button in Actions menu is visible when `first_provision_done == 0`

### L3 Evidence Contract

**S092 Anti-Corrupt-Success mandate (audit fix 2026-04-11, Blocker 10):** every L3
scenario must produce a per-scenario evidence file AND the three S092-mandated trio
files. Closeout cannot pass without all of them — the release-manager gate rejects
PRs whose branch is missing the trio.

```
# Per-scenario evidence (one per L3 scenario run):
MUST_CREATE: output/l3/s181/scenario_5_1.json
MUST_CREATE: output/l3/s181/scenario_5_2.json
MUST_CREATE: output/l3/s181/scenario_5_3.json
MUST_CREATE: output/l3/s181/scenario_5_4.json
MUST_CREATE: output/l3/s181/scenario_5_5.json
MUST_CREATE: output/l3/s181/scenario_5_6.json
MUST_CREATE: output/l3/s181/scenario_5_7.json
MUST_CREATE: output/l3/s181/scenario_5_8.json
MUST_CREATE: output/l3/s181/scenario_5_9.json
MUST_CREATE: output/l3/s181/scenario_5_10.json

# S092-mandated trio (aggregated across all scenarios):
MUST_CREATE: output/l3/s181/form_submissions.json
MUST_CREATE: output/l3/s181/api_mutations.json
MUST_CREATE: output/l3/s181/state_verification.json
```

**Trio contents:**

- `form_submissions.json` — every form POST the L3 runner submitted, with: timestamp,
  scenario ID, form URL/route, payload, response status. Proves forms were actually
  filled and submitted (not just page-loaded).
- `api_mutations.json` — every Frappe API method call that mutated state, with: method
  path (e.g. `hrms.api.company_master.update_company_section`), request payload,
  response, affected row IDs. Proves backend state actually changed.
- `state_verification.json` — every post-mutation DB assertion (`frappe.db.get_value`
  / `frappe.db.count` / `frappe.db.sql` result) that verified the mutation landed.
  Proves the test didn't just observe a success toast.

**Release manager gate:** before Phase 6 closeout, commit evidence:

```bash
git add -f output/l3/s181/
git commit -m "test(S181): L3 evidence trio + per-scenario files"
git push origin s181-company-master-extension
```

Without this step, the bei-release-manager auto-gate blocks merge.

Each per-scenario evidence file must contain: timestamp, scenario ID, each assertion
ID (E-5.x.y), pass/fail, and the raw evidence (SQL output, API response, screenshot path).

---

## Phase 6: Closeout

**Units: 10**

### Task 6.1: Update fixtures in repo

```
MUST_VERIFY: hrms/fixtures/custom_field.json contains all S181 fields
MUST_VERIFY: hrms/hr/doctype/bei_company_document/bei_company_document.json exists
MUST_VERIFY: hrms/overrides/company.py contains auto_provision_company
MUST_VERIFY: hrms/hooks.py contains after_insert for Company
```

### Task 6.2: S175 + S178 regression verification

```
MUST_CREATE: output/s181/s175_regression.json
MUST_CREATE: output/s181/s178_regression.json
```

Verify:
- 1080 template positions across 40+ companies (S175)
- All S178 Custom Fields intact (store_locations, partner_names, stakeholders_section, stakeholders)
- `BEI Settings.input_vat_goods_account` still set
- Company hierarchy (`parent_company`) unchanged

### Task 6.3: Closeout artifacts

```
MUST_CREATE: data/_CLEANROOM/agent_runs/2026-04-10_s181/RUN_STATUS.json
MUST_CREATE: data/_CLEANROOM/agent_runs/2026-04-10_s181/RUN_SUMMARY.md
MUST_CREATE: data/_CLEANROOM/agent_runs/2026-04-10_s181/DEFECT_REGISTER.csv
MUST_CREATE: output/s181/SIGNOFF.md
MUST_MODIFY: docs/plans/2026-04-10-sprint-181-company-master-extension.md (status → COMPLETED)
MUST_MODIFY: docs/plans/SPRINT_REGISTRY.md (S181 row → COMPLETED)
```

### Task 6.4: Commit + push + PR

```bash
git add hrms/hr/doctype/bei_company_document/
git add hrms/overrides/company.py
git add hrms/hooks.py
git add hrms/fixtures/custom_field.json
git add scripts/s181_*.py
git add -f output/s181/
git add -f data/_CLEANROOM/agent_runs/2026-04-10_s181/
git add docs/plans/2026-04-10-sprint-181-company-master-extension.md
git add docs/plans/SPRINT_REGISTRY.md
git commit -m "feat(S181): Company Master extension — auto-provision COA + WH + CC on Company.after_insert"
git push -u origin s181-company-master-extension
GH_TOKEN="" gh pr create --repo Bebang-Enterprise-Inc/hrms --base production --head s181-company-master-extension \
  --title "S181: Company Master Extension — Auto-Provision on New Branch" \
  --body "$(cat data/_CLEANROOM/agent_runs/2026-04-10_s181/RUN_SUMMARY.md)"
```

**STOP after PR creation.** Sam handles merge.

---

## Autonomous Execution Contract

```yaml
completion_condition:
  - Phase 1 fully executed (BEI Company Document DocType created with dual file/drive_file_url fields + 45 Custom Fields added to fixture [includes drive_folder_url on Section 5] + bench migrate succeeds)
  - Phase 2 fully executed (auto_provision_company hook in company.py + after_insert registered in hooks.py)
  - Phase 3 fully executed (existing companies seeded with entity_category, store_ownership_type, mosaic_location_id, GPS, operational_status)
  - Phase 4 fully executed (branch TINs + RDO codes backfilled)
  - Phase 3B + 3C fully executed (bei-tasks Company Master page, list, detail dialog, section modals, ADMS + Documents child tables, RBAC, route registered, sidebar entry)
  - Phase 5 L3 scenarios all-pass with per-scenario evidence files AND the S092-mandated trio
  - Phase 5 evidence committed to branches (`git add -f output/l3/s181/`) on BOTH lanes
  - S175 + S178 regression checks pass
  - Plan YAML status = COMPLETED
  - SPRINT_REGISTRY.md S181 row = COMPLETED with BOTH PR numbers (backend hrms + frontend bei-tasks)
  - TWO PRs created: one on `Bebang-Enterprise-Inc/hrms` (backend lane), one on `Bebang-Enterprise-Inc/BEI-Tasks` (frontend lane)

stop_only_for:
  - HB-0: S178 Custom Fields (stakeholders, store_locations, partner_names) not present in working tree
  - HB-1: MASTER_SALES_TEMPLATE has changed (not 27 rows)
  - HB-2: on_update function already exists on Company from another sprint
  - HB-3: Custom Field name collision
  - HB-4: BEI Company Document DocType already exists
  - HB-5: bench migrate fails
  - HB-6: pre-migrate backup (Task 1.4a) missing — refuse to run migrate without it
  - L3 scenario fails with no obvious programmatic fix

continue_without_pause_through:
  - Phase 1 (pure DocType + fixture creation)
  - Phase 2 (Python code — auto_provision_company + _apply_balance_sheet_template + _ensure_bki_customer + retry_provision_company + ADMS enqueue worker)
  - Phase 2B (whitelisted API methods for the frontend lane)
  - Phase 3 (seeding from local CSVs)
  - Phase 3B (bei-tasks list + fullscreen detail page) — frontend lane, unblocked by Phase 2B merge
  - Phase 3C (bei-tasks section modals + ADMS + Documents) — frontend lane
  - Phase 4 (TIN backfill from local CSV)
  - Phase 5 (L3 testing — writes per-scenario + trio evidence)
  - Phase 6 (closeout — TWO PRs, registry update, SIGNOFF.md)

blocker_policy:
  programmatic: fix and continue
  deploy_failure: check traceback, fix, redeploy
  l3_failure: diagnose, fix code, rerun scenario
  frontend_backend_interface_drift: if Phase 3B/3C discover a backend field/endpoint mismatch, update interface_contract.md, notify backend lane, pause until backend lane catches up

signoff_authority: single-owner (Sam Karazi)

canonical_closeout_artifacts:
  - data/_CLEANROOM/agent_runs/2026-04-10_s181/RUN_STATUS.json
  - data/_CLEANROOM/agent_runs/2026-04-10_s181/RUN_SUMMARY.md
  - data/_CLEANROOM/agent_runs/2026-04-10_s181/DEFECT_REGISTER.csv
  - output/s181/SIGNOFF.md
  - output/s181/backups/custom_field_BEFORE.json  # Blocker 11 — pre-migrate backup
  - output/s181/backups/tabCustomField_Company_BEFORE.sql
  - output/s181/interface_contract.md  # Blocker 8 — frozen contract between backend + frontend lanes
  - output/l3/s181/scenario_5_1.json
  - output/l3/s181/scenario_5_2.json
  - output/l3/s181/scenario_5_3.json
  - output/l3/s181/scenario_5_4.json
  - output/l3/s181/scenario_5_5.json
  - output/l3/s181/scenario_5_6.json
  - output/l3/s181/scenario_5_7.json
  - output/l3/s181/scenario_5_8.json  # BKI Customer lookup (Blocker 4)
  - output/l3/s181/scenario_5_9.json  # Phase 3B list+detail (Blocker 7)
  - output/l3/s181/scenario_5_10.json # Retry Provisioning (Blocker 14)
  - output/l3/s181/form_submissions.json    # S092 trio
  - output/l3/s181/api_mutations.json       # S092 trio
  - output/l3/s181/state_verification.json  # S092 trio
  - docs/plans/2026-04-10-sprint-181-company-master-extension.md (COMPLETED)
  - docs/plans/SPRINT_REGISTRY.md (S181 row COMPLETED with BOTH PR numbers)
```

---

## Zero-Skip Enforcement

Every task above MUST be executed. No silent skipping.

**Forbidden agent behaviors:**
1. Skipping the `BEI Company Document` or `BEI Company ADMS Device` child DocTypes and putting all fields inline (the child table pattern is specified — follow it)
2. Skipping `frappe.db.savepoint()` in `auto_provision_company` ("it's probably fine without it")
3. Skipping Sentry `set_backend_observability_context` in the hook or in the new whitelisted API methods
4. Skipping `frappe.local.flags.ignore_root_company_validation = True` and hoping ERPNext won't validate
5. Hardcoding company names in `auto_provision_company` (it must work for ANY new company)
6. Reverting the hook back to `after_insert` (Blocker 9 — ERPNext's Standard Template runs during `on_update`, not before `after_insert`)
7. Dropping the `first_provision_done` sentinel (it is what prevents re-running on every save)
8. Dropping the `frappe.flags.in_import / in_migrate / in_install` guard (Blocker 13 — bulk imports would create 27 × N accounts)
9. Dropping `_apply_balance_sheet_template` (Blocker 5 — without it, `_set_default_accounts` silently no-ops on Debtors/Creditors/COGS)
10. Reverting `_ensure_bki_customer` to use `doc.name` as customer_name (Blocker 4 — S168's `build_bki_store_sale_invoice` keys on `buyer_entity_name` from the S037 register)
11. Using `doc.save()` inside `auto_enroll_adms_devices` or making the HTTP call synchronously (Blocker 12 — use `frappe.enqueue` + `frappe.db.set_value`)
12. Using `/api/resource/Company/...` in the bei-tasks frontend lane (Blocker 6 — use `/api/frappe/api/method/hrms.api.company_master.*`)
13. Leaving Phase 3B / 3C under-specified (Blocker 7 — both phases have full MUST_CREATE / MUST_MODIFY / MUST_CONTAIN contracts and must be executed to completion)
14. Skipping the pre-migrate backup Task 1.4a (HB-6 — migrate without backup is refused)
15. Skipping the L3 trio files `form_submissions.json` / `api_mutations.json` / `state_verification.json` (Blocker 10 — release-manager gate will reject)
16. Marking Phase 3/4 as "done" without running the seeding script (verify with output JSON)
17. Skipping L3 Scenario 5.2 (the parent_company test is the hardest case — it's where `ignore_root_company_validation` matters)
18. Skipping L3 Scenario 5.3 (verifying the sentinel actually prevents re-provisioning on subsequent saves)
19. Skipping L3 Scenario 5.7 (the dual upload/Drive link test — the validator must reject rows with neither file nor drive_file_url)
20. Skipping L3 Scenario 5.8 (the BKI Customer lookup test — must use buyer_entity_name from S037)
20b. Skipping L3 Scenario 5.9 (Phase 3B list page + detail dialog — must actually render in bei-tasks)
20c. Skipping L3 Scenario 5.10 (Retry Provisioning button — must flip first_provision_done and repopulate COA)
21. Failing to create the second branch `s181-company-master-frontend` on bei-tasks (frontend lane needs its own branch + PR)
22. Using `--no-verify` on any git commit
10. Deleting or modifying S178 Custom Fields (store_locations, partner_names, stakeholders_section, stakeholders)

---

## Signoff Model

- **mode:** single-owner
- **approver_of_record:** Sam Karazi (CEO)
- **signoff_artifact:** `output/s181/SIGNOFF.md`
- **deploy_required:** YES — this sprint has application code (`hrms/overrides/company.py`, `hrms/hooks.py`). Requires `bench migrate` after deploy.

---

## Agent Boot Sequence

1. Read this plan fully.
2. **Create sprint branch (hrms — backend lane):** `cd F:\Dropbox\Projects\BEI-ERP && git fetch origin production && git checkout -b s181-company-master-extension origin/production`. NEVER write code on production.
3. **Create sprint branch (bei-tasks — frontend lane):** `cd F:\Dropbox\Projects\bei-tasks && git fetch origin main && git checkout -b s181-company-master-frontend origin/main`. The frontend lane gets its own branch and its own PR.
4. Verify `docs/plans/SPRINT_REGISTRY.md` has the S181 row with branch `s181-company-master-extension` AND the second reserved branch `s181-company-master-frontend`.
5. **HARD PRECONDITION — S178 field existence check (HB-0):** before touching Phase 1, run this verification:
   ```bash
   python -c "import json; fx=json.load(open('hrms/fixtures/custom_field.json')); found=[f['fieldname'] for f in fx if f.get('dt')=='Company' and f['fieldname'] in ('stakeholders','store_locations','partner_names','stakeholders_section')]; print('S178 fields on disk:', found); assert len(found)==4, f'MISSING S178 fields: {found}'"
   ```
   S178 (per SPRINT_REGISTRY.md) may show status `PLANNED` but the S178 Custom Fields must already exist in the working tree. If the assertion fails — STOP, cannot proceed, file a blocker.
6. Read `hrms/overrides/company.py` — understand existing Company hooks.
7. Read `hrms/hooks.py` lines 180-190 — understand existing doc_events for Company.
8. Read `hrms/fixtures/custom_field.json` — find the S178 Company fields (last ~40 lines). This is where new fields will be appended.
9. Read `hrms/hr/doctype/bei_company_stakeholder/bei_company_stakeholder.json` — pattern for child DocType JSON structure.
10. Read `scripts/s175_master_coa_template.py` — the canonical 27-account Sales template (must match `_MASTER_SALES_TEMPLATE` in the hook exactly).
11. Read `scripts/s175_phase_2_apply_template.py` lines 109-160 — the `ensure_account` pattern to replicate.
12. Read `hrms/api/commissary.py` lines 1027-1050 — the `build_bki_store_sale_invoice` Customer lookup (proves BKI uses `buyer_entity_name`, not Company name).
13. Read `data/_CLEANROOM/2026-03-12-s037-store-buyer-entity-register/store_buyer_entity_register_2026-03-12.csv` — the S037 register used by both `_ensure_bki_customer` and Phase 3 seeding.
14. Read `bei-tasks/lib/queries/hr-employee-detail.ts` and `hr-payroll.ts` — confirm the `/api/frappe/api/method/<module>.<function>` proxy pattern used across bei-tasks. The S181 frontend MUST use this pattern, not `/api/resource/`.
15. **Task 1.4a — pre-migrate backup (MANDATORY before bench migrate):** snapshot `hrms/fixtures/custom_field.json` to `output/s181/backups/custom_field_BEFORE.json` + mysqldump `tabCustom Field` rows where `dt='Company'` to `output/s181/backups/tabCustomField_Company_BEFORE.sql`. If migrate fails, restore from these.
16. **Execute Phase 1 (backend lane)** — create DocTypes, update fixtures, verify migrate.
17. **Execute Phase 2 (backend lane)** — implement hook, register in hooks.py.
18. **Execute Phase 2B (backend lane)** — whitelisted API methods for the frontend (`hrms.api.company_master.*`).
19. **Deploy + bench migrate** before Phase 3 (fields must exist on production for SSM scripts AND for the frontend lane to be unblocked).
20. **Execute Phase 3 (backend lane)** — seed existing companies.
21. **Execute Phase 4 (backend lane)** — backfill branch TINs.
22. **Execute Phase 3B (frontend lane, unblocked by Phase 2B merge + bench migrate)** — bei-tasks Company Master list + fullscreen detail.
23. **Execute Phase 3C (frontend lane)** — bei-tasks popup edit modals + ADMS/Documents sections.
24. **Execute Phase 5 (backend lane)** — L3 testing on production, writing the S092-mandated evidence trio (`form_submissions.json`, `api_mutations.json`, `state_verification.json`) alongside per-scenario evidence.
25. **Execute Phase 6 (both lanes)** — closeout + TWO PRs (one on `Bebang-Enterprise-Inc/hrms` for the backend, one on `Bebang-Enterprise-Inc/BEI-Tasks` for the frontend). Update SPRINT_REGISTRY.md with both PR numbers.

---

## Execution Authority

All 9 phases (Phase 1, 2, 2B, 3, 3B, 3C, 4, 5, 6) can execute autonomously. No external dependencies or human input required (all source data is in the repo). The only gate is the HB-0 precondition: S178 Custom Fields must be present in `hrms/fixtures/custom_field.json` (verify via Agent Boot Sequence Step 5).

Do not stop for progress-only updates. Only pause for items listed in the `stop_only_for` section.

---

## Amendment Log

### v4.1 — 2026-04-11 (sprint renumber: S179 → S181)

**Why:** at the start of the execution pass, `git branch -a` on both repos
revealed that `s179-product-mix-per-channel` was already MERGED as S179
(hrms PR #530 + bei-tasks PR #375 — "Product Mix / Product Analytics
dashboard"). S180 was also already taken by the Forensic Logistics Audit
plan (`docs/plans/2026-04-10-sprint-180-forensic-logistics-audit.md`,
status COMPLETED). The v4 registry reservation for S179 was stale — the
local `SPRINT_REGISTRY.md` claimed S179 free while reality had moved on.

**What changed:**
- Plan file renamed: `2026-04-10-sprint-179-company-master-extension.md`
  → `2026-04-10-sprint-181-company-master-extension.md`
- All 227 `S179`/`s179` references inside the plan rewritten to `S181`/`s181`
  in one atomic pass (branch names, output directories, agent run dir,
  savepoint name, enqueue job name, L3 test fixture names, script filenames,
  plan-audit references, inline comments/log messages, YAML `sprint:` key).
- `output/plan-audit/s179-company-master-extension/` directory renamed to
  `output/plan-audit/s181-company-master-extension/` (contents unchanged —
  they are historical audit findings, gitignored).
- `docs/plans/SPRINT_REGISTRY.md` updated: added correct S179 row for the
  shipped Product Mix sprint (hrms#530 + bei-tasks#375 MERGED), added S180
  row for Forensic Logistics Audit (COMPLETED), added S181 row for Company
  Master Extension (PLANNED, dual-branch reservation), bumped Next Sprint
  Reservation to S182, and added a new item #5 to the Next block that
  mandates `git branch -a` cross-check against both repos BEFORE reserving
  any S### (the registry alone is not authoritative — remote branches and
  plan files are).

**Nothing else changed.** All 14 blocker fixes, 47 Custom Fields, 9 phases,
102 units, 30 RR items, 9 HARD BLOCKERs, 10 L3 scenarios, and the
feature-preserving spirit of v4 are intact. This amendment is purely
identifier-level.

### v4 — 2026-04-11 (audit resolution, 14 CRITICAL blockers fixed)

Full audit run: 8 parallel domain agents + code verifier (10/10 CONFIRMED against source) + adversarial fact-checker (13 SUPPORTED + 1 PARTIAL, 0 hallucinations). See `output/plan-audit/s181-company-master-extension/verified_blockers.md`.

**Feature-preserving fixes applied (no features lost — all gaps resolved by improving, not removing):**

1. **Blocker 1 — typo fix:** L348 `insert_after: adms_device_ids` → `adms_devices`. One-character fix.
2. **Blocker 2 — stale CSV path:** `Bebang_Halo-Halo_Stores_Locations_2025-12-31.csv` → `_2025-12-29.csv` (only file that exists). Two replacements (L76 + L837).
3. **Blocker 3 — S178 precondition:** added HB-0 + Agent Boot Sequence Step 5 verification script that asserts the 4 S178 Custom Fields exist on disk before Phase 1 starts. Governance mismatch flagged (registry says PLANNED but fields are present).
4. **Blocker 4 — BKI Customer rewrite:** `_ensure_bki_customer` now reads `store_buyer_entity_register_2026-03-12.csv`, matches by `doc.name == store_name or warehouse_docname`, uses `buyer_entity_name` as the Customer's `customer_name` (matches S168's `build_bki_store_sale_invoice` lookup), copies tax_id / rdo / vat_status, shares Customers across stores mapping to the same buyer entity, skips non-store entities gracefully. Feature preserved: company creation still auto-provisions BKI Customer — just with the correct naming convention.
5. **Blocker 5 — default accounts no-op:** added `_MASTER_BALANCE_SHEET_TEMPLATE` (20 accounts) + `_apply_balance_sheet_template(doc)` helper so Debtors / Creditors / Cost of Goods Sold / Round Off / Cash exist before `_set_default_accounts` runs. `_set_default_accounts` now raises (no longer silently skips) if any required default is missing — triggers savepoint rollback. Feature preserved + COA coverage improved from Income-only to full Asset / Liability / Equity / Expense skeleton.
6. **Blocker 6 — frontend API pattern:** added Phase 2B (10 units) creating `hrms/api/company_master.py` with 8 whitelisted methods (`list_companies`, `get_company`, `update_company_section`, `upsert_compliance_document`, `delete_compliance_document`, `upsert_adms_device`, `delete_adms_device`, `retry_provision`). Mass-assignment safety via `EDITABLE_SECTIONS` allow-list. Sentry on every endpoint (DM-7). Frontend now uses the `/api/frappe/api/method/...` proxy pattern consistent with the rest of bei-tasks. Feature preserved + proper API layer added.
7. **Blocker 7 — Phase 3B/3C bodies:** written out in full with file paths (MUST_CREATE, MUST_MODIFY), exact routes (`/dashboard/bd/companies`), RBAC roles (Business Development, BD Manager, Accounts Manager, System Manager), sidebar placement in Operations section, MUST_CONTAIN per component, 2 new L3 scenarios (5.8 list filter + 5.9 retry provisioning gate). 22 units of frontend scope now has machine-verifiable contracts. Feature preserved + task structure added.
8. **Blocker 8 — parallel lanes contract:** added `lanes:` YAML block with `backend_lane` + `frontend_lane`, each with repo, branch, phases, owner_files, blocked_until gates. Second branch `s181-company-master-frontend` reserved for bei-tasks. `output/s181/interface_contract.md` is a frozen artifact that Phase 2B produces and Phase 3B/3C consume. Closeout requires TWO PRs (one per repo). Backend lane serial path = 80u (exactly at S089 ceiling), frontend lane = 22u (parallel). Feature preserved + parallelism made real.
9. **Blocker 9 — lifecycle order:** changed hook from `after_insert` to `on_update` with `first_provision_done` sentinel Custom Field (new, added to Section 7 Provisioning State). Hook now fires AFTER ERPNext's own `create_default_accounts()` / `create_default_warehouses()` / `create_default_cost_center()`. Still runs exactly once per Company (sentinel-gated). Feature preserved + Frappe lifecycle respected.
10. **Blocker 10 — S092 evidence trio:** added `output/l3/s181/form_submissions.json`, `api_mutations.json`, `state_verification.json` to the L3 Evidence Contract + `completion_condition` + `canonical_closeout_artifacts`. Per-scenario evidence files renamed from `output/s181/l3_evidence/` to `output/l3/s181/` (matches S092 convention). Feature preserved + corrupt-success prevention strengthened.
11. **Blocker 11 — migrate rollback:** added Task 1.4a pre-migrate backup (snapshots fixture + mysqldump of `tabCustom Field` where `dt='Company'` + timestamp file) + full rollback procedure with DELETE statements for every S181-added row + DROP for new child DocTypes. HB-6 refuses `bench migrate` without the backup. Feature preserved + safety added.
12. **Blocker 12 — ADMS enqueue:** rewrote `auto_enroll_adms_devices` to enqueue `_enroll_adms_devices_job` in Frappe's `short` queue, pass device list by value, update child rows via `frappe.db.set_value` (does NOT re-trigger `on_update`), 10s timeout per device, error log + retry-on-next-save circuit breaker. No more blocking HTTP, no more double-save. Feature preserved + resilience improved.
13. **Blocker 13 — bulk-import guard:** added `if frappe.flags.in_import or in_migrate or in_install: return` at the top of `auto_provision_company` and `auto_enroll_adms_devices`. Bulk imports of 10 companies no longer trigger 10 × 27 = 270 account creations. Feature preserved + import safety added.
14. **Blocker 14 — retry path:** added `retry_provision_company(company_name)` whitelisted method + `hrms/public/js/company.js` Desk button + frontend "Retry Provisioning" pill (visible when `first_provision_done == 0`). Clears the sentinel and reruns `auto_provision_company` idempotently. Error Log entry on every failure includes remediation steps in msgprint. Feature added (new recovery capability).

**Metadata changes:**
- Field count: 45 → 47 (added `provisioning_state_section` + `first_provision_done`)
- Sections: 7 → 8 (added Provisioning State)
- Phases: 8 → 9 (added Phase 2B)
- Total units: 92 → 102 (backend 80u serial path fits S089 ceiling; frontend 22u runs in parallel)
- RR checklist items: 21 → 30
- HARD BLOCKERs: 5 → 9 (added HB-0, HB-6, HB-7, HB-8)
- L3 scenarios: 7 → 9 (added 5.8, 5.9)
- Hook registration: `after_insert` → `on_update` with sentinel
- Sprint Registry: dual-branch reservation (`s181-company-master-extension` + `s181-company-master-frontend`)
- Forbidden behaviors list: 9 → 22 (added all Blocker-specific reversal traps)
- Plan line count: ~1,208 → ~2,400

No features removed. Every blocker was resolved by improving the feature, not by dropping it.
