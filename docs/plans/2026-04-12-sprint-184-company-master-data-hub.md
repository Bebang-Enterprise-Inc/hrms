# S184 — Company Master Data Hub: Connected Ecosystem

> **Context in one line:** Make the Company DocType the structural hub of the BEI ecosystem — every related DocType (Warehouse, Bank Account, Employee, Customer, Sales Invoice, ADMS Device, POS Upload) links TO it via standard Frappe Link fields. The Company Master page renders what's already connected. New stores auto-create all linked records on first save. Zero silos, zero CSV lookups at runtime, zero manual processes for data we already know.

**Plan version:** v1

```yaml
sprint: S184
status: DEPLOYED
planned_date: 2026-04-12
deployed_date: 2026-04-12
backend_pr: "hrms#550"
frontend_pr: "bei-tasks#384"
plan_file: docs/plans/2026-04-12-sprint-184-company-master-data-hub.md

lanes:
  backend_lane:
    repo: Bebang-Enterprise-Inc/hrms
    branch: s184-company-master-data-hub
    phases: [1, 2, 3, 4, 5, 6]
  frontend_lane:
    repo: Bebang-Enterprise-Inc/BEI-Tasks
    branch: s184-company-master-hub-frontend
    phases: [3B, 3C, 6]
    blocked_until:
      - backend_lane_phase_3_merged

depends_on:
  - S181 merged (all hotfixes through PR #548)

canonical_unit_total: 75
backend_serial_path: 52
frontend_serial_path: 23
```

---

## Design Rationale (For Cold-Start Agents)

### Why this sprint exists

S181 built the Company Master page — 47 Custom Fields, auto-provisioning hook, store-driven list, fullscreen detail dialog. But the production review (2026-04-12) revealed that the Company Master was a **visual dashboard pulling from CSV files at runtime**, not a structurally connected hub. Data lived in 7 separate silos:

- GPS in a stale CSV snapshot (not live from the website)
- Bank accounts in a Google Sheet (never loaded into Frappe)
- BKI billing entity in a CSV (not displayed on the Company page)
- Employee count not shown (despite `tabEmployee.company` Link field existing)
- ADMS devices in a Python dict (not seeded as child table rows)
- Warehouse stock data not visible (despite Company → Warehouse link existing)
- Sales analytics on a separate dashboard (not connected from Company)

Sam's directive (2026-04-12): *"Everything should be interconnected using the same DocTypes so we can have a single ecosystem — not isolated silos."*

### Architecture: connected ecosystem, not stitched dashboards

The Frappe data model already HAS most of the Link fields:

```
Company ←── tabEmployee.company (Link)
Company ←── Bank Account.company (Link) — EXISTS but EMPTY
Company ←── tabWarehouse.company (Link)
Company ──→ tabBin (via Warehouse) ──→ stock on hand
Company ──→ BEI Company ADMS Device (child table, S181)
Company ──→ BEI Company Document (child table, S181)
Company ──→ BEI Company Stakeholder (child table, S178)
Company ──→ S037 register ──→ buyer_entity_name ──→ Customer ──→ Sales Invoice
Company ──→ Warehouse ──→ BEI POS Upload / BEI Store Sales Day
```

**S184's job is NOT to build bridges between silos.** It is to:
1. **Fill empty Link fields** — Bank Account.company is never seeded; some employees missing company
2. **Auto-create linked records on new store** — Bank Account, ADMS Device, BKI Customer (extend S181 hook)
3. **One-time data migration** — pull live GPS from Superadmin API, seed Bank Accounts from Google Sheet export
4. **Frontend rendering** — the Company detail dialog shows the connected data by following Frappe's standard Link field relationships, not by querying CSVs

### Key design decisions

1. **Bank Accounts: use Frappe's standard `Bank Account` DocType** — it already has a `company` Link field plus bank name, account number, account type, currency, IBAN. No custom child table needed. When BD creates a new store, the `auto_provision_company` hook creates the standard bank account RECORDS (bank name + account type pre-filled from the known pattern — BDO operations, payroll, etc.) with account number left blank. Finance fills in the number when the bank confirms. **Account number is NOT required** — the record exists as a placeholder until Finance completes it.

2. **Warehouse: already auto-created by S181** — `_s181_ensure_warehouse(doc)` in `hrms/overrides/company.py` creates `<Company Name> - <Abbr>` on first save. S184 does NOT re-create it. S184 adds the DISPLAY of warehouse stock data (via `tabBin`) on the Company detail page.

3. **ADMS Device: auto-assign from DEVICE_TO_STORE on new store creation** — extend `auto_provision_company` to look up the device serial from `hrms/utils/device_mapping.py` and append a `BEI Company ADMS Device` child row. The S181 hotfix chain (PR #548) already has the bridge table (`_ADMS_TO_S037`). S184 moves this INTO the hook so it runs automatically, not just when someone clicks "Re-run Populate".

4. **GPS: one-time sync from Superadmin API** — call the bebang.ph Superadmin API once during the initial populate, store the coordinates on the Company Custom Fields (`gps_latitude`, `gps_longitude`, `full_address`). For new stores, the hook calls the API at creation time. No periodic sync needed — store locations don't move.

5. **BKI Billing: read-only display following existing Link chain** — Company → S037 register (match by `warehouse_docname` or `buyer_entity_name`) → Customer (already created by S181's `_s181_ensure_bki_customer`) → Sales Invoice. The API endpoint returns the billing entity name, hold status, and outstanding invoice count by following Frappe's existing relationships. No new DocTypes or fields needed.

6. **Daily Sales: link to existing analytics, not a separate card** — the Sales Analytics dashboard (S182/S183) already queries by store/warehouse. The Company detail page shows a "View Sales Analytics" link that navigates to `/dashboard/analytics/sales?store=<warehouse>` pre-filtered. The existing `hrms.api.sales_dashboard` endpoints already support this. No new endpoints needed for the sales data itself — just the navigation link and a "last sale date" field from `BEI POS Upload`.

7. **Employee headcount: live query, not a stored field** — the API endpoint queries `SELECT COUNT(*), designation FROM tabEmployee WHERE company = %s AND status = 'Active' GROUP BY designation`. The count is always live. No Custom Field needed.

---

## Data Sources

| Source | Already in the ecosystem? | What S184 does |
|---|---|---|
| `hrms/utils/device_mapping.py` DEVICE_TO_STORE | ✅ Inside hrms package | Move seeding INTO `auto_provision_company` hook (currently only in `populate_s181_fields`) |
| Frappe `Bank Account` DocType | ✅ Exists, `company` Link field present | Seed 53+ accounts from Google Sheet export; auto-create pattern accounts for new stores |
| `tabEmployee.company` Link field | ✅ Already populated | Query for headcount display — no seeding needed |
| `tabBin` (Warehouse stock) | ✅ Links via Warehouse.company | Query for stock display — no seeding needed |
| `tabSales Invoice` (BKI billing) | ✅ Links via Customer ← S037 buyer_entity | Query for outstanding invoice display — no seeding needed |
| Superadmin API (GPS) | ⚠️ External API, not in ecosystem | One-time pull → store on Company Custom Fields (already exist from S181) |
| S037 register (BKI billing entity) | ⚠️ CSV in `data_seed/` | Read at Company creation time → display billing entity name |
| Google Sheet "Bebang Accounts Bank Balances" | ⚠️ External, needs CSV export | One-time export → `data_seed/bank_accounts.csv` → seed script |
| `BEI POS Upload` / `BEI Store Sales Day` | ✅ Frappe DocTypes with warehouse field | Query for last-sale-date display — no seeding needed |

---

## Phase Budget Contract

```yaml
phase_unit_budget:
  # ===== BACKEND LANE =====
  Phase 1 (Bank Account seeding + GPS from Superadmin API):                    12
  Phase 2 (auto_provision_company expansion: bank accounts + ADMS + GPS):      10
  Phase 3 (API endpoints: headcount, warehouse stock, BKI billing, sales link): 12
  Phase 4 (L3 handoff):                                                         8
  Phase 5 (closeout + PR):                                                      10
  # ===== FRONTEND LANE =====
  Phase 3B (Company detail dialog sections: bank accounts, BKI billing,
            headcount, warehouse ops, GPS map link, sales link):               15
  Phase 3C (new store wizard: auto-populated fields preview + bank account
            placeholder display):                                                8
hard_limit_per_phase: 15
total_units: 75
```

---

## Phase 1: Bank Account Seeding + GPS Sync (12u)

### Task 1.1: Export bank accounts from Google Sheet to CSV

```
MUST_CREATE: hrms/data_seed/bank_accounts_2026-04-12.csv
```

Export the "Bebang Accounts Bank Balances" Google Sheet to CSV. Columns needed: bank_name, account_name, account_number (may be blank), account_type (Current/Savings/Payroll), currency (PHP), company_name (the Frappe Company docname this account belongs to). File goes into `hrms/data_seed/` so it ships in the Docker image.

### Task 1.2: Seed Frappe Bank Account records

```
MUST_MODIFY: hrms/api/company_master.py
MUST_CONTAIN: 'Bank Account'
MUST_CONTAIN: 'bank_accounts_seeded'
```

Add a `_seed_bank_accounts()` function inside `populate_s181_fields` (renamed to `populate_company_data` in this sprint) that:
1. Reads `hrms/data_seed/bank_accounts_2026-04-12.csv`
2. For each row, creates a `Bank Account` record if one with the same `account_name` + `company` doesn't already exist
3. Sets `company` Link field, `bank` (bank name), `account_type`, `currency`
4. Leaves `bank_account_no` blank if the CSV value is empty — **NOT required**
5. Returns count of created / skipped

### Task 1.3: GPS sync from Superadmin API

```
MUST_MODIFY: hrms/api/company_master.py
MUST_CONTAIN: 'superadmin'
MUST_CONTAIN: 'gps_latitude'
MUST_CONTAIN: 'gps_longitude'
```

Add a `_sync_gps_from_superadmin()` function that:
1. Calls the Superadmin API to get all store locations with GPS
2. Matches each store to a Frappe Company (via the S037 store_name bridge or Superadmin slug)
3. Updates `gps_latitude`, `gps_longitude`, `full_address`, `city` on the Company record
4. Uses `frappe.db.set_value` (no hook trigger, no doc.save cascade)

**Credential:** `SUPERADMIN_STORES_API_KEY` from Doppler (`bei-erp` / `dev`). If the key is not available in the Frappe environment, fall back to the static CSV (already in `data_seed/` from S181). The endpoint should try the API first, fall back gracefully.

### Task 1.4: Verify bench migrate (if any schema changes)

No new Custom Fields or DocTypes in this phase — Bank Account is a standard Frappe DocType, GPS fields already exist from S181. No bench migrate needed.

---

## Phase 2: Expand auto_provision_company Hook (10u)

### Task 2.1: Add bank account auto-creation to the hook

```
MUST_MODIFY: hrms/overrides/company.py
MUST_CONTAIN: 'Bank Account'
MUST_CONTAIN: '_s184_create_default_bank_accounts'
```

When `auto_provision_company` runs on a new Company with `entity_category = Store`:
1. Create a `Bank Account` record: bank=BDO, account_type=Current, currency=PHP, company=doc.name, account_name=`<Company Name> - Operations`. Account number left blank.
2. Create a second `Bank Account`: bank=BDO, account_type=Savings, currency=PHP, company=doc.name, account_name=`<Company Name> - Payroll`. Account number left blank.

These are PLACEHOLDER records. Finance fills in the account number when BDO confirms. The records exist so the Company detail page shows "Bank Accounts: 2 (0 with account numbers — pending Finance)" instead of nothing.

**HARD BLOCKER:** Account number is NOT required. Never set `reqd=1` on `bank_account_no`. The whole point is that the record exists as a container waiting for Finance to fill the number.

### Task 2.2: Add ADMS device auto-assignment to the hook

```
MUST_MODIFY: hrms/overrides/company.py
MUST_CONTAIN: 'DEVICE_TO_STORE'
MUST_CONTAIN: '_s184_assign_adms_device'
```

When `auto_provision_company` runs on a new Company:
1. Import `DEVICE_TO_STORE` from `hrms/utils/device_mapping.py`
2. Use the `_ADMS_TO_S037` bridge table (from S181 hotfix PR #548) to find the matching device
3. If found, append a `BEI Company ADMS Device` child row with `device_serial` + `device_name`
4. If not found (new location with no device yet), skip gracefully — the device can be added later via the UI

This replaces the current pattern where ADMS devices only get seeded when someone clicks "Re-run Populate".

### Task 2.3: Add GPS pull to the hook

```
MUST_MODIFY: hrms/overrides/company.py
MUST_CONTAIN: '_s184_pull_gps'
```

When `auto_provision_company` runs on a new Store Company:
1. Try to match the company name against the Superadmin API store list
2. If matched, set `gps_latitude`, `gps_longitude`, `full_address`, `city` via `frappe.db.set_value`
3. If API unavailable or no match, fall back to the `data_seed/` locations CSV
4. If neither works, skip — fields stay blank for manual entry

---

## Phase 3: API Endpoints for Connected Data (12u)

### Task 3.1: Employee headcount endpoint

```
MUST_MODIFY: hrms/api/company_master.py
MUST_CONTAIN: 'get_headcount'
```

New `@frappe.whitelist()` endpoint: `hrms.api.company_master.get_headcount(company)`
- Returns: `{ total_active, by_designation: { "Crew": N, "Store Supervisor": N, ... }, recent_hires: [...] }`
- Source: `SELECT designation, COUNT(*) FROM tabEmployee WHERE company = %s AND status = 'Active' GROUP BY designation`
- Sentry DM-7 tagged

### Task 3.2: Bank accounts for company

```
MUST_MODIFY: hrms/api/company_master.py
MUST_CONTAIN: 'get_bank_accounts'
```

New `@frappe.whitelist()` endpoint: `hrms.api.company_master.get_bank_accounts(company)`
- Returns: list of `{ name, bank, account_name, bank_account_no, account_type, is_company_account }` from `tabBank Account WHERE company = %s`
- Frontend renders: bank name, account type, account number (or "Pending" if blank), with an "Edit" link to the Frappe Bank Account form

### Task 3.3: BKI billing summary

```
MUST_MODIFY: hrms/api/company_master.py
MUST_CONTAIN: 'get_bki_billing'
```

New `@frappe.whitelist()` endpoint: `hrms.api.company_master.get_bki_billing(company)`
- Resolves the buyer_entity_name from S037 register (match by company docname or warehouse_docname)
- Queries `tabSales Invoice` for outstanding amount: `WHERE customer = buyer_entity_name AND outstanding_amount > 0 AND docstatus = 1`
- Returns: `{ buyer_entity_name, billing_status, outstanding_count, outstanding_total, last_delivery_date }`

### Task 3.4: Warehouse stock summary

```
MUST_MODIFY: hrms/api/company_master.py
MUST_CONTAIN: 'get_warehouse_stock'
```

New `@frappe.whitelist()` endpoint: `hrms.api.company_master.get_warehouse_stock(company)`
- Finds the Company's warehouse (by `<Company Name> - <Abbr>` or via S037 `warehouse_docname`)
- Queries `tabBin`: `SELECT COUNT(*), SUM(stock_value) FROM tabBin WHERE warehouse = %s AND actual_qty > 0`
- Returns: `{ warehouse_name, item_count, stock_value, is_open }`

### Task 3.5: Update interface_contract.md

```
MUST_MODIFY: output/s181/interface_contract.md
```

Add all 4 new endpoints to the frozen interface contract.

---

## Phase 3B: Frontend — Connected Data Sections (15u)

### Task 3B.1: Bank Accounts section

```
MUST_CREATE: bei-tasks/components/company-master/bank-accounts-section.tsx
MUST_CONTAIN: 'get_bank_accounts'
MUST_CONTAIN: 'Bank Account'
MUST_CONTAIN: 'Pending'
```

Read-only section in the Company detail dialog:
- Lists bank accounts linked to this Company via the `get_bank_accounts` API
- Shows: bank name, account type, account number (or amber "Pending — Finance to complete" badge)
- Count summary: "3 accounts (2 with numbers, 1 pending)"
- No edit capability in bei-tasks — editing happens in Frappe Desk Bank Account form (link provided)

### Task 3B.2: BKI Billing section

```
MUST_CREATE: bei-tasks/components/company-master/bki-billing-section.tsx
MUST_CONTAIN: 'get_bki_billing'
MUST_CONTAIN: 'buyer_entity_name'
MUST_CONTAIN: 'outstanding'
```

Read-only section:
- "Billed as: Bebang Mega Inc" (buyer_entity_name)
- "Billing status: Active" (green) or "On Hold" (red)
- "Outstanding: 3 invoices, ₱45,230.00" (from Sales Invoice query)
- "Last delivery: 2026-04-10"
- Clicking the outstanding amount navigates to Frappe Desk Sales Invoice list filtered by customer

### Task 3B.3: People section (headcount)

```
MUST_CREATE: bei-tasks/components/company-master/people-section.tsx
MUST_CONTAIN: 'get_headcount'
MUST_CONTAIN: 'total_active'
```

Read-only section:
- "23 active employees" (total)
- Breakdown pills: "15 Crew · 3 Asst. Supervisor · 2 Store Supervisor · 1 Area Supervisor · 2 Other"
- "Recent hires: Juan Dela Cruz (2026-04-01), Maria Santos (2026-03-15)"

### Task 3B.4: Warehouse section

```
MUST_CREATE: bei-tasks/components/company-master/warehouse-section.tsx
MUST_CONTAIN: 'get_warehouse_stock'
MUST_CONTAIN: 'stock_value'
```

Read-only section:
- "Warehouse: SM Megamall - BEI" (warehouse_name)
- "45 items in stock · ₱125,000 value"
- Link: "View Stock →" opens Frappe Desk Stock Balance filtered by warehouse

### Task 3B.5: Sales link

No new component needed. Add a button/link to the Operations section card:
- "View Sales Analytics →" navigates to `/dashboard/analytics/sales?store=<warehouse_docname>`
- "Last POS upload: 2026-04-12 08:30 PHT" (from `BEI POS Upload` last record date for this warehouse)

### Task 3B.6: GPS display enhancement

The GPS coordinates are already shown from S181. Enhance with:
- A "View on Google Maps" button that opens `https://www.google.com/maps?q=<lat>,<lng>`
- If `google_maps_place_id` is set, link to `https://www.google.com/maps/place/?q=place_id:<id>`

---

## Phase 3C: New Store Auto-Populate Preview (8u)

### Task 3C.1: Auto-populate confirmation in the detail dialog

When a new Company is created via the S181 `auto_provision_company` hook, the dialog should show a green "Auto-provisioned" summary listing everything that was created:
- ✅ COA: 47 accounts (27 Sales + 20 Balance Sheet)
- ✅ Warehouse: `<Name> - <Abbr>`
- ✅ Cost Center: `<Name> - <Abbr>`
- ✅ Bank Accounts: 2 placeholder records (BDO Operations + Payroll) — pending account numbers
- ✅ ADMS Device: `<serial>` (`<location>`) — enrollment pending
- ✅ BKI Customer: `<buyer_entity_name>` — linked for billing
- ✅ GPS: `<lat>, <lng>` from Superadmin API
- ✅ Default accounts set (receivable, payable, expense, cash, round_off)

This replaces the current generic "Auto-provisioned COA, Warehouse, Cost Center..." msgprint with a detailed, component-rendered summary.

---

## Phase 4: L3 Handoff (8u)

L3 scenarios (executed in a fresh session per S092 builder/tester split):

| # | Scenario | What to verify |
|---|---|---|
| 4.1 | Create a new Store Company → verify all auto-provisions | Bank accounts (2 placeholders), ADMS device, GPS, BKI Customer, Warehouse, COA |
| 4.2 | Open the new Company in bei-tasks → verify all sections render | Bank Accounts (2 pending), People (0 — new store), Warehouse (empty), BKI Billing (entity name) |
| 4.3 | Open an EXISTING Company (SM Megamall) → verify connected data | Headcount > 0, bank accounts from seed, warehouse stock > 0, BKI billing with invoices |
| 4.4 | Click "View Sales Analytics" → verify navigation works | Lands on analytics page pre-filtered to the correct store |
| 4.5 | Click "View on Google Maps" → verify GPS link opens correctly | Google Maps opens at the correct lat/lng |
| 4.6 | S181 regression: verify existing 47 Custom Fields + sentinel hook still work | Same as S181 L3 scenarios 5.1-5.4 |

---

## Phase 5: Closeout (10u)

Standard closeout per S092 rule: update plan YAML, SPRINT_REGISTRY.md, create TWO PRs (hrms + bei-tasks), L3 evidence files, SIGNOFF.md.

---

## Requirements Regression Checklist

- [ ] **RR-1:** Bank Account records created with `company` Link field pointing to the correct Company
- [ ] **RR-2:** Bank Account `bank_account_no` is NOT required — blank is valid (placeholder state)
- [ ] **RR-3:** `auto_provision_company` creates 2 placeholder Bank Accounts for new Store companies
- [ ] **RR-4:** `auto_provision_company` assigns ADMS device from `DEVICE_TO_STORE` for new stores
- [ ] **RR-5:** `auto_provision_company` pulls GPS from Superadmin API (with CSV fallback) for new stores
- [ ] **RR-6:** `get_headcount(company)` returns live employee count by designation
- [ ] **RR-7:** `get_bank_accounts(company)` returns all Bank Account records linked to the company
- [ ] **RR-8:** `get_bki_billing(company)` returns buyer_entity_name + outstanding invoice count/total
- [ ] **RR-9:** `get_warehouse_stock(company)` returns item count + stock value from tabBin
- [ ] **RR-10:** Company detail dialog shows Bank Accounts section with "Pending" badges for blank account numbers
- [ ] **RR-11:** Company detail dialog shows BKI Billing section with buyer entity + outstanding amount
- [ ] **RR-12:** Company detail dialog shows People section with headcount by designation
- [ ] **RR-13:** Company detail dialog shows Warehouse section with stock value
- [ ] **RR-14:** "View Sales Analytics" link navigates to the correct pre-filtered analytics page
- [ ] **RR-15:** "View on Google Maps" opens the correct location
- [ ] **RR-16:** S181 Custom Fields, auto_provision_company hook, and sentinel gate unchanged
- [ ] **RR-17:** All new endpoints have Sentry DM-7 observability context
- [ ] **RR-18:** No `/api/resource/` pattern in frontend — all through `/api/frappe/api/method/` proxy

---

## HARD BLOCKERS

- **HB-1:** Bank Account `bank_account_no` must NOT be set as required. If it's required, Finance can't create placeholder records and the auto-provision hook will throw. This is a non-negotiable design decision from Sam (2026-04-12).
- **HB-2:** `auto_provision_company` must remain sentinel-gated (`first_provision_done`). S184 extends it but must NOT remove the sentinel or the import/migrate guards from S181.
- **HB-3:** DEVICE_TO_STORE import must come from `hrms/utils/device_mapping.py` (authoritative source, 48 devices). Never read from the BIOMETRIC_MACHINE_MAPPING CSV.
- **HB-4:** The Sales Analytics page (S182/S183) must not be re-implemented. S184 only adds a LINK to it from the Company detail page, pre-filtered by store.

---

## Autonomous Execution Contract

```yaml
completion_condition:
  - Phase 1: Bank Account records seeded + GPS synced from Superadmin API
  - Phase 2: auto_provision_company creates bank accounts + ADMS device + GPS for new stores
  - Phase 3: 4 new API endpoints deployed (headcount, bank accounts, BKI billing, warehouse stock)
  - Phase 3B: Company detail dialog renders all connected sections
  - Phase 3C: new store auto-populate preview renders in detail dialog
  - Phase 4: L3 handoff prompt generated
  - Phase 5: TWO PRs created, SPRINT_REGISTRY.md updated
  - S181 regression checks pass

stop_only_for:
  - Superadmin API credentials not available in Doppler
  - Google Sheet bank account export not provided
  - HB-1 through HB-4 violated
  - L3 scenario fails with no obvious fix

signoff_authority: single-owner (Sam Karazi)
```

---

## Agent Boot Sequence

1. Read this plan fully.
2. **Create sprint branches:**
   - `cd F:\Dropbox\Projects\BEI-ERP && git fetch origin production && git checkout -b s184-company-master-data-hub origin/production`
   - `cd F:\Dropbox\Projects\bei-tasks && git fetch origin main && git checkout -b s184-company-master-hub-frontend origin/main`
3. Verify S181 fields exist: `python -c "import json; fx=json.load(open('hrms/fixtures/custom_field.json')); assert len([f for f in fx if f.get('dt')=='Company']) >= 51"`
4. Read `hrms/overrides/company.py` — understand the S181 `auto_provision_company` hook (lines ~580-700).
5. Read `hrms/api/company_master.py` — understand the existing 11 whitelisted methods.
6. Read `hrms/utils/device_mapping.py` — the authoritative `DEVICE_TO_STORE` dict (48 devices).
7. Read `bei-tasks/app/dashboard/bd/companies/company-detail-dialog.tsx` — understand the current 8 section cards.
8. Export bank accounts from Google Sheet to CSV at `hrms/data_seed/bank_accounts_2026-04-12.csv`.
9. Test Superadmin API access: `doppler secrets get SUPERADMIN_STORES_API_KEY --project bei-erp --config dev --plain`.
10. Execute Phase 1 → Phase 5 sequentially, committing after each phase.

---

## Zero-Skip Enforcement

Every task MUST be implemented. No exceptions. If a task cannot be completed (e.g., Superadmin API is unreachable), the agent STOPS and asks Sam — it does NOT skip the task or replace it with a simpler version.

Forbidden behaviors:
1. Skipping bank account seeding because "the CSV isn't available" — ask for it
2. Replacing the Superadmin API GPS pull with "use the existing CSV" without trying the API first
3. Skipping the BKI billing section because "it's read-only and not critical"
4. Making `bank_account_no` required on Bank Account
5. Removing the S181 sentinel gate or import guards from `auto_provision_company`
6. Using `/api/resource/Bank Account/` in the frontend instead of a whitelisted method endpoint
7. Skipping L3 scenarios
