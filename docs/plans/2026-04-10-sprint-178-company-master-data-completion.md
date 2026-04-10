# S178 — BEI Group Company Master Data Completion

> **Context in one line:** Fix every pending company-level data gap that blocks billing, accounting, consolidated reporting, and BIR compliance across the 40+ Bebang Group Frappe Companies — TINs, parent_company hierarchy, legal entity names, missing Managed Franchise companies, store-searchable Custom Fields, orphan accounts, and franchise fee routing policy.

```yaml
sprint: S178
branch: s178-company-master-data-completion
status: PLANNED
planned_date: 2026-04-10
plan_file: docs/plans/2026-04-10-sprint-178-company-master-data-completion.md
repos: hrms (SSM scripts + Custom Field fixture + verification artifacts — NO application code changes)
depends_on:
  - S175 merged (PR #523) — provides the 40-company COA structure this sprint completes
canonical_unit_total: 65
execution_started:
completed_date:
execution_summary:
```

---

## Design Rationale (For Cold-Start Agents)

### Why this sprint exists

S175 delivered the uniform 27-account Sales template across 40 Frappe Companies, created BFC, fixed BEI 6xxxxxx classification, and built intercompany scaffolding. But S175 was scoped as a **COA structure** sprint — it deliberately deferred company-level master data:

1. **38 of 40 companies have `tax_id = NULL`** in Frappe even though the BIR entity register (`ENTITY_TIN_RDO_2026-02-27.csv`) has all 51 TINs. Any Frappe-generated invoice or tax document prints blank where the TIN should be.

2. **33 store corporations are standalone** (no `parent_company`). Frappe consolidated P&L/BS won't roll them up under BEI or the holding company. BEI + BKI + JV + MF are correctly parented to Irresistible Infusions Inc. — but the 33 stores, DMD Holdings, and BFC are orphaned from the group tree.

3. **~12 Managed Franchise legal entities exist in the BIR register but NOT as Frappe Companies.** TAJ Food Corp, Tungsten Capital Holdings, Legacy77 Food Corp, HFFM Solenad Food Services Inc., Red Taldawa Foods OPC, B Cubed Ventures Corp., Day Ones Food and Drink Establishments Corp., Tricern Food Corp., BB Estancia Food Corp., BEIFranchise Food OPC, Everyday Delight Food Ventures Inc., Halo-Halo Terminal Food Corp. For S168 BKI→Store billing to work for these stores, each needs its own Frappe Company + COA.

4. **`JV` and `Managed Franchise` are placeholder names** — not SEC-registered legal entity names. Printing "JV" on an invoice is not BIR-compliant.

5. **Operators can't find companies by store name** in Frappe dropdowns. They know "SM Bicutan" but the dropdown shows "BEBANG SM BICUTAN INC." Adding a searchable `store_locations` Custom Field solves this without renaming.

6. **4 pre-existing BEI orphan accounts** have broken `parent_account` references (STOCK ADJUSTMENT, GR/IR CLEARING, PP&E, ADVANCES TO SSS). S175 identified these but scoped them out.

7. **`BEI Settings.input_vat_goods_account` is empty** — procurement flows that need input VAT for goods will fail or skip VAT.

8. **`rebuild_tree("Account")` was skipped** in S175 (SSM timeout). Precautionary rebuild needed.

9. **Franchise fee routing policy** (Fork 1 vs Fork 2) is undecided. Butch's questionnaire is pending. The GL structure supports both — this sprint locks the policy decision.

### What this sprint does NOT do

- No application code changes (`hrms/api/*.py`, `bei-tasks/` untouched)
- No COA restructure (S175 did this — template is locked)
- No BFC bank account setup (Treasury workstream)
- No BFC→BEI intercompany services agreement (Legal workstream)
- No non-BEI 5/7/8/9-series account classification (separate sprint)

---

## Data Sources

| Source | Path | Contents |
|---|---|---|
| BIR entity register (51 rows) | `data/_CLEANROOM/batch_2026-02-28_cleanroom_v1/raw_snapshot/ENTITY_TIN_RDO_2026-02-27.csv` | All TINs, RDOs, VAT status, store-level registrations |
| Store-to-entity mapping (48 stores) | `data/_CLEANROOM/2026-03-12-s037-store-buyer-entity-register/store_buyer_entity_register_2026-03-12.csv` | Maps physical stores → legal buyer entities, store types (JV/MF/Full Franchise) |
| Company Register XLSX (sent to team) | `tmp/bei_company_register.xlsx` | Pre-filled 40-company register with team-input columns for TINs, parent_company, comments |
| S175 cleanroom (6 files) | `data/_CLEANROOM/2026-04-09_s175_coa_restructure/` | All COA decisions, template spec, intercompany accounting patterns |
| Butch questionnaire | `tmp/butch_s175_questionnaire.docx` | 5 policy questions for franchise fee routing |
| Collection Agent Letter draft | `data/_CLEANROOM/2026-04-09_franchise_agreements/04_BEI_BFC_Collection_Agent_Letter_DRAFT.md` | Fork 1 enabler |
| SSM execution pattern | `.claude/skills/frappe-bulk-edits/SKILL.md` | Proven SSM base64→docker cp→exec pattern |

---

## Phase Budget Contract

```yaml
phase_unit_budget:
  Phase 1 (Immediate fixes — zero dependencies):           10
  Phase 2 (Company Register — needs team input):           15
  Phase 3 (Missing company creation — needs Phase 2):      15
  Phase 4 (Franchise fee routing — needs Butch):           10
  Phase 5 (Verification + closeout):                       10
  reconciliation_overhead:                                  5
hard_limit_per_phase: 15
preferred_split_threshold: 12
total_units: 65
```

---

## Requirements Regression Checklist

- [ ] **RR-1:** All 40+ companies have `tax_id` populated from the BIR entity register
- [ ] **RR-2:** All 33 store corps have `parent_company` set per team-confirmed hierarchy
- [ ] **RR-3:** DMD Holdings and BFC have `parent_company` set per team confirmation
- [ ] **RR-4:** `JV` and `Managed Franchise` renamed to their actual SEC-registered legal entity names (or deprecated if not real entities)
- [ ] **RR-5:** `company_name` (what prints on invoices) matches BIR legal entity name exactly for every company
- [ ] **RR-6:** `store_locations` Custom Field on Company DocType exists and is populated for every company that has physical stores
- [ ] **RR-7:** The 4 BEI orphan accounts have their `parent_account` fixed to valid accounts
- [ ] **RR-8:** `BEI Settings.input_vat_goods_account` linked to `INPUT VAT - GOODS - Bebang Enterprise Inc.`
- [ ] **RR-9:** `rebuild_tree("Account")` has been run successfully
- [ ] **RR-10:** ~12 missing Managed Franchise legal entities created in Frappe with TIN, COA template, parent_company, store_locations
- [ ] **RR-11:** S175 verification still passes (1080 template positions, BEI Settings cutover, 134 BEI 6xxx fix, BFC Company, intercompany scaffolding)
- [ ] **RR-12:** Franchise fee routing policy locked (Fork 1 or Fork 2 or hybrid) based on Butch's answers
- [ ] **RR-13:** No application code changed in this sprint

---

## HARD BLOCKERS

- **HB-1:** If the team's completed Company Register XLSX names a parent_company that doesn't exist in Frappe, STOP. Create the parent first or ask the team to correct.
- **HB-2:** If any company rename would cascade to GL entries or posted invoices, STOP. Rename only companies with 0 postings.
- **HB-3:** If `rebuild_tree` times out via SSM (>900s), try per-company rebuild. If still fails, schedule for maintenance window and continue.
- **HB-4:** If a BIR entity's TIN matches more than one Frappe Company, STOP. Ask the team to resolve the ambiguity (known issue: DMD Holdings previously shared TIN with Irresistible Infusions Inc. — corrected 2026-02-27 per Butch).

---

## Phase 1: Immediate Fixes (Zero Dependencies)

**Units: 10** — Can execute immediately, no team input needed.

### Task 1.1: Fix 4 BEI orphan accounts
```
MUST_CREATE: scripts/s178_phase_1_orphan_fix.py
```

Fix these orphaned `parent_account` references on BEI:

| Account | Current broken parent | Fix to |
|---|---|---|
| `STOCK ADJUSTMENT - BEI` | `COST OF SALES - BEI` (missing) | Find/create the correct BEI COGS parent |
| `GR/IR CLEARING - BEI` | `INVENTORY - BEI` (missing) | Find/create the correct BEI Inventory parent |
| `PROPERTY, PLANT AND EQUIPMENT - BEI` | `NON-CURRENT ASSETS - BEI` (missing) | Find/create the correct BEI NCA parent |
| `ADVANCES TO SSS - BEI` | `NON-TRADE RECEIVABLES - BEI` (missing) | Find/create the correct BEI NTR parent |

**Approach:** Query BEI's existing account tree to find the real group accounts that should be the parents (they may have slightly different names than what's referenced). If no suitable parent exists, create the missing group account. Use `frappe.db.set_value("Account", <name>, "parent_account", <correct_parent>)` — NOT rename_doc.

### Task 1.2: Fix BEI Settings.input_vat_goods_account
```
MUST_CREATE: scripts/s178_phase_1_bei_settings_fix.py
MUST_CONTAIN: 'input_vat_goods_account'
MUST_CONTAIN: 'INPUT VAT - GOODS'
```

```python
account_name = frappe.db.get_value("Account",
    {"company": "Bebang Enterprise Inc.", "account_name": "INPUT VAT - GOODS"},
    "name")
assert account_name, "INPUT VAT - GOODS - BEI not found"
frappe.db.set_single_value("BEI Settings", "input_vat_goods_account", account_name)
```

### Task 1.3: Run rebuild_tree("Account")
```
MUST_CREATE: scripts/s178_phase_1_rebuild_tree.py
```

```python
from frappe.utils.nestedset import rebuild_tree
rebuild_tree("Account", "parent_account")
frappe.db.commit()
```

If this times out (>900s via SSM), split into per-company rebuilds:
```python
for company in frappe.get_all("Company", pluck="name"):
    # rebuild only accounts for this company
    ...
```

**HB-3 applies:** If per-company also fails, defer to maintenance window and proceed to Phase 1.4.

### Task 1.4: Create store_locations Custom Field on Company DocType
```
MUST_CREATE: scripts/s178_phase_1_store_locations_field.py
MUST_CONTAIN: 'store_locations'
MUST_CONTAIN: 'Custom Field'
```

```python
if not frappe.db.exists("Custom Field", "Company-store_locations"):
    cf = frappe.new_doc("Custom Field")
    cf.dt = "Company"
    cf.fieldname = "store_locations"
    cf.label = "Store Locations"
    cf.fieldtype = "Small Text"
    cf.insert_after = "company_name"  # or "abbr" — visible near the top
    cf.description = "Physical store names registered under this entity. Searchable in dropdowns."
    cf.in_list_view = 1
    cf.in_standard_filter = 1
    cf.search_index = 1
    cf.insert(ignore_permissions=True)
    frappe.db.commit()
```

### Task 1.5: Populate store_locations from store-entity mapping
```
MUST_CREATE: scripts/s178_phase_1_populate_store_locations.py
```

Read `data/_CLEANROOM/2026-03-12-s037-store-buyer-entity-register/store_buyer_entity_register_2026-03-12.csv` and `ENTITY_TIN_RDO_2026-02-27.csv`. For each Frappe Company, set `store_locations` to the comma-separated list of store names registered under that entity.

**Matching logic:** Fuzzy-match Frappe company names against BIR entity names (lowercase, strip "Inc.", "Corp.", "OPC", periods, commas). For the known special cases:
- `Bebang Enterprise Inc.` → "Head Office, SM Megamall, SM Manila, SM Southmall, Robinsons Place Antipolo"
- `Bebang Kitchen Inc.` → "Commissary (Shaw Blvd, Mandaluyong)"
- `BEBANG FRANCHISE CORP.` → "(Franchisor entity — no stores)"
- `Irresistible Infusions Inc.` → "(Holding company — no stores)"
- `Bebang Mega Inc.` → "SM Tanza, Robinsons Place Imus, Evo City, Vermosa, Robinsons Place Gen. Trias"
- etc.

### Task 1.6: Verify Phase 1
```
MUST_CREATE: output/s178/phase1_verification.json
```

Assert:
1. 4 orphan accounts now have valid `parent_account`
2. `BEI Settings.input_vat_goods_account` resolves to a valid account
3. `store_locations` Custom Field exists on Company DocType
4. At least 30 companies have non-empty `store_locations`
5. `rebuild_tree` ran successfully (or was deferred with HB-3 documented)

---

## Phase 2: Company Register Completion (Needs Team Input)

**Units: 15** — BLOCKED until team returns completed `tmp/bei_company_register.xlsx`.

### Task 2.1: Ingest completed Company Register XLSX
```
MUST_CREATE: scripts/s178_phase_2_ingest_register.py
```

Read the team-completed XLSX. For each row, extract:
- Frappe company name
- Confirmed `parent_company` (column F "SHOULD BE")
- Confirmed `tax_id` (column H, verified by team)
- Confirmed `company_name` (if team corrected to match BIR legal name)
- Team comments

Parse into a structured JSON at `output/s178/phase2_confirmed_register.json`.

### Task 2.2: Bulk-update tax_id on 38 companies
```
MUST_CREATE: scripts/s178_phase_2_update_tins.py
MUST_CONTAIN: 'tax_id'
```

For each company where `tax_id` is NULL and the team confirmed a TIN:
```python
frappe.db.set_value("Company", company_name, "tax_id", confirmed_tin)
```

**HB-4:** If any TIN appears on more than one Frappe Company, STOP and flag the duplicate.

### Task 2.3: Set parent_company hierarchy
```
MUST_CREATE: scripts/s178_phase_2_set_hierarchy.py
MUST_CONTAIN: 'parent_company'
```

For each company where the team confirmed a `parent_company` different from current:
```python
frappe.db.set_value("Company", company_name, "parent_company", confirmed_parent)
```

**Note:** Setting `parent_company` on a company that already has accounts may trigger Frappe's Group Company validator on future account operations. Use `frappe.local.flags.ignore_root_company_validation = True` during the batch update (same pattern as S175 Phase 2).

### Task 2.4: Fix company_name to match BIR legal names
```
MUST_CREATE: scripts/s178_phase_2_fix_company_names.py
```

For companies where `company_name` (what prints on invoices) doesn't match the BIR legal entity name:
```python
frappe.db.set_value("Company", company_name, "company_name", correct_bir_name)
```

**Critical:** Do NOT use `frappe.rename_doc` here. We only change the display name (`company_name`), NOT the Frappe primary key (`name`). The PK stays as-is to avoid cascade risks.

### Task 2.5: Resolve JV and Managed Franchise placeholders

Based on team input:
- If `JV` should be renamed to an actual legal entity name → `frappe.rename_doc("Company", "JV", "<real name>")` (safe — JV has 0 GL entries, 0 postings per S175 audit)
- If `Managed Franchise` should be renamed → same pattern
- If they should be deprecated → document the decision but leave the records (don't delete Frappe Companies with accounts)

### Task 2.6: Verify Phase 2
```
MUST_CREATE: output/s178/phase2_verification.json
```

Assert:
1. All companies have non-empty `tax_id`
2. All store corps have `parent_company` set (not standalone)
3. `company_name` matches BIR legal entity name for all companies
4. No duplicate TINs across companies (except known multi-branch TINs like BEI's 647-243-690-00000 → 00005)

---

## Phase 3: Missing Company Creation (Depends on Phase 2)

**Units: 15** — Only if team confirms these ~12 entities need their own Frappe Companies.

### Task 3.1: Determine which entities are missing
```
MUST_CREATE: output/s178/phase3_missing_entities.json
```

Cross-reference the BIR entity register against the Frappe company list. Entities in BIR but NOT in Frappe:

| BIR Entity | Store(s) | TIN | Status |
|---|---|---|---|
| TAJ Food Corp | SM Caloocan, D'Verde Calamba | 681-325-053-00001/00002 | Missing from Frappe |
| Tungsten Capital Holdings OPC | SM Sangandaan, Galleria South | 679-843-234-00001/00002 | Missing (note: "Tungsten Capital Holdings Inc." IS in Frappe as a different entity for Gateway Mall) |
| Legacy77 Food Corp | SM San Jose Del Monte | 691-654-007-00000 | Missing |
| HFFM Solenad Food Services Inc. | Ayala Solenad 2 | 681-476-808-00001 | Missing |
| Red Taldawa Foods OPC | SM Clark | 687-525-727-00007 | Missing |
| B Cubed Ventures Corp. | Tomas Morato (CTTM Square) | 682-574-745-00001 | Missing |
| Day Ones Food and Drink Establishments Corp. | SM Taytay | 010-939-944-00000 | Missing |
| Tricern Food Corp. | Vista Mall Taguig | 010-038-108-00005 | Missing |
| BB Estancia Food Corp. | Ortigas Estancia | 693-136-289-00001 | Missing |
| BEIFranchise Food OPC | Ortigas Greenhills | 688-721-280-00001 | Missing |
| Everyday Delight Food Ventures Inc. | Robinsons Place Dasmarinas | (not BIR-registered yet) | Missing + not BIR-ready |
| Halo-Halo Terminal Food Corp. | NAIA T3 (Departure) | 690-528-808-00000 | Missing |
| Sweet Harmony Food Corp | SM Sta. Rosa | 691-378-334-00000 | Missing |

**Wait for team input:** Some of these may not need their own Frappe Company (e.g., if they bill through BEI as a proxy). The Company Register XLSX asks the team to confirm.

### Task 3.2: Create confirmed missing companies
```
MUST_CREATE: scripts/s178_phase_3_create_missing_companies.py
```

For each confirmed entity:
```python
company = frappe.new_doc("Company")
company.company_name = "<BIR legal entity name>"
company.abbr = "<derived abbr>"
company.default_currency = "PHP"
company.country = "Philippines"
company.tax_id = "<TIN from BIR register>"
company.chart_of_accounts = "Standard"
company.create_chart_of_accounts_based_on = "Standard Template"
company.parent_company = "<confirmed parent>"
company.enable_perpetual_inventory = 0
company.insert(ignore_permissions=True)
```

### Task 3.3: Apply MASTER_SALES_TEMPLATE to each new company
```
MUST_CREATE: scripts/s178_phase_3_apply_template.py
```

Same `ensure_account` helper as S175 Phase 2/8. Apply the 27-account Sales template + `rebuild_tree` per company.

### Task 3.4: Set store_locations on new companies

For each new company, populate the `store_locations` field with the store names from the BIR register.

### Task 3.5: Verify Phase 3
```
MUST_CREATE: output/s178/phase3_verification.json
```

Assert:
1. All confirmed missing entities exist as Frappe Companies
2. Each has `tax_id`, `parent_company`, `company_name`, `store_locations` populated
3. Each has the 27-account Sales template (27 assertions per company)
4. Total Frappe Company count increased by the expected number

---

## Phase 4: Franchise Fee Routing Policy (Depends on Butch)

**Units: 10** — BLOCKED until Butch answers `tmp/butch_s175_questionnaire.docx`.

### Task 4.1: Ingest Butch's answers
```
MUST_CREATE: data/_CLEANROOM/2026-04-09_s175_coa_restructure/06_BUTCH_ANSWERS.md
```

Harvest Butch's responses from Chat or returned questionnaire. Persist verbatim.

### Task 4.2: Lock Fork 1 vs Fork 2 decision

Based on Butch's OQ-1/OQ-2/OQ-3 answers:

**If Fork 1 (collection-agent):**
- Sign the Collection Agent Letter (Sam signs both sides + board resolutions)
- Verify BFC has operational BIR OR booklet
- Configure BFC Sales Invoice template with `Debit To = 1104200 DUE FROM BEI - BFC`
- Create Customer Group `BFC Franchisees` if not exists
- Document the operational runbook

**If Fork 2 (interim BEI revenue):**
- Configure BEI Sales Invoice template for franchise fees with `Income Account = 4000231-4000235`
- Document the restatement plan for when BFC bank opens
- Create Customer Group `BFC Franchisees` on BEI

**If hybrid:**
- Document per team's decision

### Task 4.3: Create operational runbook
```
MUST_CREATE: data/_CLEANROOM/2026-04-09_s175_coa_restructure/07_FRANCHISE_FEE_OPERATIONAL_RUNBOOK.md
```

Step-by-step instructions for the accountant: which company to invoice from, which accounts, which Customer Group, which SI template, how to reconcile intercompany (if Fork 1).

### Task 4.4: Verify Phase 4
```
MUST_CREATE: output/s178/phase4_verification.json
```

Assert routing policy is documented, SI template is configured, Customer Group exists.

---

## Phase 5: Verification + Closeout

**Units: 10**

### Task 5.1: Full company inventory audit
```
MUST_CREATE: scripts/s178_phase_5_final_audit.py
MUST_CREATE: output/s178/final_company_audit.json
```

For every Frappe Company (now ~52), verify:
1. `tax_id` is non-empty
2. `company_name` is the BIR legal entity name
3. `parent_company` is set (unless legitimately standalone like the holding company itself)
4. `store_locations` is populated (or "(no stores)" for holding/franchisor entities)
5. Has 27 Sales template accounts (4000xxx range)
6. No orphan accounts (parent_account points to valid Account)

### Task 5.2: S175 regression check
```
MUST_CREATE: output/s178/s175_regression.json
```

Re-run S175 Phase 10 verification:
- 1080 template positions on original 40 companies
- BEI Settings.bki_sales_income_account resolves
- BEI 6xxxxxx = 0 Income
- BFC + intercompany accounts exist
- BKI Store customer count = 35

### Task 5.3: Generate updated Company Register XLSX
```
MUST_CREATE: tmp/bei_company_register_final.xlsx
```

Regenerate the Company Register XLSX with the completed data (all TINs filled, all parents set, all legal names correct, all store_locations populated). This becomes the canonical company reference for the Finance team.

### Task 5.4: Closeout artifacts
```
MUST_CREATE: data/_CLEANROOM/agent_runs/2026-04-10_s178/RUN_STATUS.json
MUST_CREATE: data/_CLEANROOM/agent_runs/2026-04-10_s178/RUN_SUMMARY.md
MUST_CREATE: data/_CLEANROOM/agent_runs/2026-04-10_s178/DEFECT_REGISTER.csv
MUST_CREATE: output/s178/SIGNOFF.md
MUST_MODIFY: docs/plans/2026-04-10-sprint-178-company-master-data-completion.md (status → COMPLETED)
MUST_MODIFY: docs/plans/SPRINT_REGISTRY.md (S178 row → COMPLETED)
```

### Task 5.5: Commit + push + PR
```bash
git add -f docs/plans/2026-04-10-sprint-178-company-master-data-completion.md
git add -f docs/plans/SPRINT_REGISTRY.md
git add scripts/s178_*.py
git add -f output/s178/
git add -f data/_CLEANROOM/agent_runs/2026-04-10_s178/
git add -f tmp/bei_company_register_final.xlsx
git commit -m "closeout(S178): company master data completion — TINs + hierarchy + missing entities + store_locations"
git push -u origin s178-company-master-data-completion
GH_TOKEN="" gh pr create --repo Bebang-Enterprise-Inc/hrms --base production --head s178-company-master-data-completion \
  --title "S178: Company Master Data Completion" \
  --body "$(cat data/_CLEANROOM/agent_runs/2026-04-10_s178/RUN_SUMMARY.md)"
```

**STOP after PR creation.** Sam handles merge.

---

## Autonomous Execution Contract

```yaml
completion_condition:
  - Phase 1 fully executed (orphans fixed, BEI Settings fixed, rebuild_tree run, store_locations populated)
  - Phase 2 fully executed (TINs + parent_company + company_name from team XLSX)
  - Phase 3 fully executed (missing companies created + template applied) OR explicitly dispositioned ("team says not needed")
  - Phase 4 fully executed (routing policy locked + runbook written) OR explicitly dispositioned ("Butch hasn't answered — defer")
  - Phase 5 verification all-pass
  - S175 regression check passes
  - Plan YAML status = COMPLETED
  - SPRINT_REGISTRY.md S178 row = COMPLETED
  - PR created on hrms

stop_only_for:
  - HB-1: parent_company target doesn't exist in Frappe
  - HB-2: company rename would cascade to GL entries or posted invoices
  - HB-3: rebuild_tree timeout (try per-company, then defer)
  - HB-4: duplicate TIN across companies
  - Team hasn't returned the Company Register XLSX (Phase 2 blocks)
  - Butch hasn't answered the questionnaire (Phase 4 blocks)

continue_without_pause_through:
  - Phase 1 (zero dependencies — execute immediately)
  - Phase 5 verification

blocker_policy:
  programmatic: fix and continue
  team_input_missing: execute Phase 1 + pre-write Phase 2/3 scripts, pause Phase 2+ until XLSX returns
  butch_not_answered: execute Phases 1-3, pause Phase 4 until answers arrive, proceed to Phase 5 after 1-3

signoff_authority: single-owner (Sam Karazi)

canonical_closeout_artifacts:
  - data/_CLEANROOM/agent_runs/2026-04-10_s178/RUN_STATUS.json
  - data/_CLEANROOM/agent_runs/2026-04-10_s178/RUN_SUMMARY.md
  - data/_CLEANROOM/agent_runs/2026-04-10_s178/DEFECT_REGISTER.csv
  - output/s178/SIGNOFF.md
  - tmp/bei_company_register_final.xlsx
  - docs/plans/2026-04-10-sprint-178-company-master-data-completion.md (COMPLETED)
  - docs/plans/SPRINT_REGISTRY.md (S178 row COMPLETED)
```

---

## Zero-Skip Enforcement

Every task above MUST be executed. No silent skipping.

**Forbidden agent behaviors:**
1. Skipping a company because "it's probably fine"
2. Setting `tax_id` without verifying it against the BIR entity register
3. Setting `parent_company` without the team's explicit confirmation
4. Creating a new Frappe Company without first checking it doesn't already exist under a different name
5. Using `frappe.rename_doc` on a company with GL entries or posted invoices (HB-2)
6. Marking Phase 2/3/4 as "done" when the blocking input hasn't arrived — use "deferred" status instead

---

## Signoff Model

- **mode:** single-owner
- **approver_of_record:** Sam Karazi (CEO)
- **signoff_artifact:** `output/s178/SIGNOFF.md`
- **team's role:** provide the completed Company Register XLSX (Phase 2 input) + confirm/reject the ~12 missing entity list (Phase 3 input)
- **Butch's role:** answer the 5 policy questions in the questionnaire (Phase 4 input)

---

## Agent Boot Sequence

1. Read this plan fully.
2. **Create sprint branch:** `git fetch origin production && git checkout -b s178-company-master-data-completion origin/production`. NEVER write code on production.
3. Verify `docs/plans/SPRINT_REGISTRY.md` has the S178 row.
4. Read `data/_CLEANROOM/2026-04-09_s175_coa_restructure/00_INDEX.md` → S175 cleanroom context.
5. Read `.claude/skills/frappe-bulk-edits/SKILL.md` for SSM pattern.
6. Read `data/_CLEANROOM/batch_2026-02-28_cleanroom_v1/raw_snapshot/ENTITY_TIN_RDO_2026-02-27.csv` — the BIR entity register.
7. Read `data/_CLEANROOM/2026-03-12-s037-store-buyer-entity-register/store_buyer_entity_register_2026-03-12.csv` — store-entity mapping.
8. **Execute Phase 1 immediately** (zero dependencies).
9. Check if `tmp/bei_company_register.xlsx` has been updated by the team (look for a newer modified date or a `_completed` variant). If yes, execute Phase 2-3. If no, pre-write the Phase 2-3 scripts and wait.
10. Check if Butch's answers exist in Chat or as a returned questionnaire. If yes, execute Phase 4. If no, defer.
11. Execute Phase 5 after all available phases complete.
12. Closeout per Phase 5.4-5.5.

---

## Execution Authority

Phase 1 is intended for immediate autonomous execution — zero external dependencies.
Phases 2-4 depend on external inputs. The agent should execute Phase 1 fully, pre-write scripts for Phases 2-3, and resume when inputs arrive.
Do not stop for progress-only updates.
Only pause for items listed in the `stop_only_for` section.
Sam is the sole signoff authority.
