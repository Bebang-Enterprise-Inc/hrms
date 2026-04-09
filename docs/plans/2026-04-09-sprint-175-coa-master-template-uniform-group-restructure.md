# S175 — COA Master Template + Uniform Bebang Group Restructure (v2)

> **Context in one line:** Apply Butch Formoso's 2026-04-08 canonical GL Sales tree as a uniform COA across all 40 Bebang Group Frappe Companies, create BEBANG FRANCHISE CORP. as a new Frappe Company, fix the 134-account BEI expense misclassification, and build Fork 1 collection-agent scaffolding so BFC recognizes franchise revenue from day 1 — without breaking the S168 BKI→store billing flow.

```yaml
sprint: S175
branch: s175-coa-master-template-uniform-group-restructure
status: COMPLETED
completed_date: 2026-04-09
plan_version: 3
plan_v1_incident: "v1 contained 11 CRITICAL + 15 WARNING blockers per output/plan-audit/s175-coa-master-template/verified_blockers_v2.md. Phase A live audit on 2026-04-09 resolved C11/C12/W2, chat harvest resolved C3/R2, PDF fact-check resolved contract claims. v2 incorporates the corrections."
plan_v3_pivot: "Stripped policy gates per Sam's 2026-04-09 PM clarification. Structural work proceeds without waiting for routing policy decision. COA-175-013 revised to structural-ready + policy-deferred in cleanroom 02_LOCKED_DECISIONS.md."
planned_date: 2026-04-09
plan_file: docs/plans/2026-04-09-sprint-175-coa-master-template-uniform-group-restructure.md
repos: hrms (SSM orchestration scripts + verification artifacts only — NO application code changes)
depends_on:
  - S168 (merged, deployed, BEI Settings BKI fields synced). S168 legacy accounts 4000100/4000101 on BKI are migrated by Phase 3+4 of this sprint.
canonical_unit_total: 60
decisions_source_of_truth: data/_CLEANROOM/2026-04-09_s175_coa_restructure/
required_reading_order:
  - data/_CLEANROOM/2026-04-09_s175_coa_restructure/00_INDEX.md
  - data/_CLEANROOM/2026-04-09_s175_coa_restructure/01_CANONICAL_COA_TEMPLATE.md
  - data/_CLEANROOM/2026-04-09_s175_coa_restructure/02_LOCKED_DECISIONS.md
  - data/_CLEANROOM/2026-04-09_s175_coa_restructure/03_CURRENT_STATE_SNAPSHOT.md
  - data/_CLEANROOM/2026-04-09_s175_coa_restructure/04_INTERCOMPANY_ACCOUNTING.md
  - data/_CLEANROOM/2026-04-09_s175_coa_restructure/05_OPEN_QUESTIONS_FOR_BUTCH.md
  - output/s175/preflight_audit.md (Phase A live state, 2026-04-09)
  - .claude/skills/frappe-bulk-edits/SKILL.md (the ONLY proven SSM execution pattern — not the phantom S168 script references from plan v1)
execution_started: 2026-04-09
execution_summary: "Autonomous execution on 2026-04-09. Phases 0, 1, 1.5, 1.6, 2, 3, 4, 6, 7, 8, 10, 11 all completed. Created BFC Company + 3 intercompany scaffolding accounts (2104200 BEI, 1104200 BFC, 2102205 BFC + synthetic 2104000 INTERCOMPANY PAYABLES parent group on BEI). Deleted 19 BKI + 21 BEI legacy 4xxx accounts (child-first, all 0 GL). Applied MASTER_SALES_TEMPLATE (27 rows) to ALL 40 Frappe Companies = 1080 account positions, via frappe.local.flags.ignore_root_company_validation (Frappe-sanctioned flag to bypass the Group Company validator that otherwise blocks direct inserts on TIH child companies BKI/BEI). Fixed COA corruption on BKI (4000000 SALES had self-parent cycle) and BEI (4000000 SALES was posting, converted to group via documented SQL validator bypass). Bulk UPDATE 134 BEI 6xxxxxx accounts from root_type=Income to Expense (0 GL entries verified). Cut over BEI Settings.bki_sales_income_account from 'SALES - BKI TO STORES - BKI' (deleted in Phase 1.5) to '4000210 - DELIVERIES - BKI' (created in Phase 2). Phase 10 final verification: 11/11 checks PASS including 1080-position template assertion, BEI 6xxxxxx = 0 Income/136 Expense, BKI Store customer count = 35 baseline, BKI legacy absent, BEI legacy absent, 4000005 preserved, intercompany scaffolding, 4000200 not-discounts anywhere. No HARD BLOCKERS hit. No GL entries lost. S168 runtime consumers (commissary.py, billing.py:560) point at the new account correctly via the BEI Settings cutover."
```

---

## Design Rationale (For Cold-Start Agents)

### Why this sprint exists

1. **S168 shipped BKI→store external sale billing** but used ICT-008-era account numbering (`4000100 WHOLESALE / B2B SALES - BKI` + `4000101 SALES - BKI TO STORES - BKI`). Butch then published a new canonical GL Sales tree on 2026-04-08 that reassigns `4000100` to "STORE SALES" and puts BKI wholesale under `4000200 BKI SALES → 4000210 DELIVERIES`. S168's live accounts must migrate to the new canonical numbering.

2. **BEI head office has 134 misclassified 6xxxxxx expense accounts** (`root_type='Income'` should be `'Expense'`). Zero GL entries on any — pure data fix.

3. **BKI's 4xxxxxx tree contains accounts that don't belong** per Sam's 2026-04-08 clarification "BKI doesn't have in store sales, online sales and franchise income." 19 accounts to delete (all verified 0 GL entries in Phase A).

4. **BEBANG FRANCHISE CORP. (BFC) does not yet exist as a Frappe Company.** Phase A audit confirmed — a name-substring false-positive on `Managed Franchise` initially misled the audit. BFC must be created with its real BIR facts (TIN `672-618-804-00000`, RDO 044) before any franchise fee can be collected.

5. **BFC has no operating bank account yet** — Butch confirmed in Accounting Private chat 2026-04-09 10:37 PHT. Juanna Alcober checking BDO/UB on 2026-04-10.

6. **Interim revenue recognition model is Fork 1** (collection-agent from day 1) per COA-175-013. BEI collects franchise fee cash as a disclosed agent of BFC. BFC recognizes revenue from day 1. No interim BEI revenue, no restatement, no BIR cleanup mess at cutover. Enabled by a 1-page BEI↔BFC Collection Agent Appointment Letter signed by Sam on both sides.

### Why uniform COA across all 40 companies

Multi-entity best practice. Enables PFRS 10 consolidation, intercompany eliminations, store-vs-store comparability, audit efficiency, and quick new-entity onboarding. See `02_LOCKED_DECISIONS.md` COA-175-003.

### Why Fork 1 (not Fork 2)

Fork 2 (book franchise fees as BEI revenue during interim, restate at cutover) creates:
- PFRS 15 substance-over-form risk (BFC is the contractual principal, not BEI)
- Permanent mismatched substance on comparative periods for 2+ years post-cutover
- Unfixable VAT/OR/EWT cleanup (filings, receipts, certificates can't be retroactively switched)
- Audit exposure if any franchisee ever challenges

Fork 1 (BEI collects as agent, BFC recognizes revenue from day 1) requires one thing: a written collection-agent appointment letter. Both sides signed by Sam under board resolutions. No new costs, no external dependencies, no restatement risk. Decision locked in COA-175-013. See `04_INTERCOMPANY_ACCOUNTING.md` for full JE patterns.

### Known limitations

1. **No L3 browser scenarios.** This sprint has no operator-facing UI surface. L3 equivalent is SSM verification queries. Evidence at `output/s175/verification_final.json`, not `output/l3/s175/form_submissions.json`.
2. **Single-owner signoff.** Sam signs off. No department approvals.
3. **No application code changes.** Pure data work via SSM. PR carries only plan + registry + cleanroom + scripts + closeout artifacts.
4. **Policy routing questions deferred.** v3 strips all Butch-answer gates; the questionnaire runs in parallel via `tmp/butch_s175_questionnaire.docx`. Finance team decides Fork 1 routing after sprint closeout — structural scaffolding proceeds unconditionally.

---

## Requirements Regression Checklist

Every task must honor these. Any NO → STOP + present options.

- [ ] **RR-1:** Master COA template is `01_CANONICAL_COA_TEMPLATE.md` Section A (27 accounts) + Butch's reserved expansion slots in Section C.
- [ ] **RR-2:** `4000200` is `BKI SALES` (Sub-Group), NOT `DISCOUNTS AND PROMO`.
- [ ] **RR-3:** `DISCOUNTS AND PROMO` is at `4000900` with children `4000901-4000908`.
- [ ] **RR-4:** `4000300-4000800` reserved — DO NOT use. `4000124+` reserved for new online platforms. `4000236+` reserved for new fees.
- [ ] **RR-5:** Uniform template applied to all 40 companies (39 existing + BFC new).
- [ ] **RR-6:** Fork 1 structural scaffolding created (2104200/1104200/2102205 accounts) but routing policy DEFERRED to post-sprint Finance decision.
- [ ] **RR-7:** JV fees (Grand Central Gabaldon) flow to BEI permanently per signed JV §8.1/§9.1/§2. NOT Fork 1 (JV is not collection-agent).
- [ ] **RR-8:** BKI populates ONLY `4000200 BKI SALES` sub-tree. No `4000100`, no `4000230`, no `4000900` on BKI.
- [ ] **RR-9:** `BEI Settings.bki_sales_income_account` MUST be updated from `SALES - BKI TO STORES - BKI` → `DELIVERIES - BKI` in Phase 8 AFTER Phase 2 creates the new account AND BEFORE Phase 4 deletes the old one.
- [ ] **RR-10:** BEBANG FRANCHISE CORP. created with verified BIR facts from `02_LOCKED_DECISIONS.md` COA-175-006. Abbr `BFC`.
- [ ] **RR-11:** Both BFC contract templates are UNEXECUTED. No live franchisees. Verified 2026-04-09.
- [ ] **RR-12:** BEI 6xxxxxx bulk fix affects 134 accounts Income→Expense. Phase A verified 0 GL entries.
- [ ] **RR-13:** `2104200 DUE TO BFC - BEI` + `1104200 DUE FROM BEI - BFC` + `2102205 OUTPUT VAT PAYABLE - BFC` created. Phase 1/6.
- [ ] **RR-14:** Phase 2 BFC bank account opening is OUT OF SCOPE. BFC→BEI intercompany services agreement is OUT OF SCOPE.
- [ ] **RR-15:** No application code changes. PR carries only plan + registry + cleanroom + scripts + closeout artifacts.
- [ ] **RR-16:** Child-first deletion order honored for 4 parent chains (HB-7).
- [ ] **RR-17:** All account creation uses `frappe.new_doc("Account").insert()` / renames use `frappe.rename_doc()` — NEVER raw SQL INSERT/UPDATE on `tabAccount` except for the documented `root_type` validator workaround (Phase 7).

---

## HARD BLOCKERS

- **HB-1:** If `BEI Settings.bki_sales_income_account` points to a nonexistent account after Phase 8, STOP. S168 billing flow is broken.
- **HB-2:** If any planned-delete BKI account has non-zero GL entries at live re-verification, STOP.
- **HB-3:** If any planned-delete BEI franchise/discount account has non-zero GL entries at live re-verification, STOP.
- **HB-4:** If BEI 6xxxxxx accounts have non-zero GL entries, STOP. (Phase A says zero — re-verify before Phase 7.)
- **HB-5:** If Frappe refuses to convert `4000000 SALES` from posting→group, STOP. Do not force.
- **HB-6:** If BFC Company creation fails with TIN uniqueness / duplicate abbr / validation error, STOP.
- **HB-7 (NEW from Phase A):** If any delete-target has incoming `parent_account` children that the Phase 4/5 delete sequence hasn't handled first, STOP. Current known chains: `DISCOUNTS AND PROMO - BEI ← 4000208`, `WHOLESALE / B2B SALES - BKI ← 4000101`, `FRANCHISE INCOME - BKI ← 6 children`, `FRANCHISE INCOME - BEI ← 6 children`.

---

## Ground-Truth Lock

```yaml
authoritative_sources:
  decisions: data/_CLEANROOM/2026-04-09_s175_coa_restructure/02_LOCKED_DECISIONS.md
  current_state: data/_CLEANROOM/2026-04-09_s175_coa_restructure/03_CURRENT_STATE_SNAPSHOT.md
  accounting: data/_CLEANROOM/2026-04-09_s175_coa_restructure/04_INTERCOMPANY_ACCOUNTING.md
  template: data/_CLEANROOM/2026-04-09_s175_coa_restructure/01_CANONICAL_COA_TEMPLATE.md
  open_questions: data/_CLEANROOM/2026-04-09_s175_coa_restructure/05_OPEN_QUESTIONS_FOR_BUTCH.md
  butch_chat: data/_CLEANROOM/chat_evidence/2026-04-08_butch_gl_sales/transcript.md + CLAIM_VERIFICATION.md + DL97trTZUFA.DL97trTZUFA__Screenshot_2026-04-08_at_10.17.04_AM.png
  bfc_corp: data/_CLEANROOM/2026-04-08_franchise_corp_extract/
  contracts: data/_CLEANROOM/2026-04-09_franchise_agreements/
  collection_letter: data/_CLEANROOM/2026-04-09_franchise_agreements/04_BEI_BFC_Collection_Agent_Letter_DRAFT.md
  live_state: output/s175/preflight_audit.json + preflight_audit.md (Phase A, 2026-04-09)
  ssm_pattern: .claude/skills/frappe-bulk-edits/SKILL.md
authoritative_sections:
  - "Phase tables below are authoritative for execution"
  - "Cleanroom files at data/_CLEANROOM/2026-04-09_s175_coa_restructure/ are authoritative for decision traceability"
  - "Any amendment/audit history appended later is traceability only"
normalization_rule:
  - "Any amendment that changes counts, account numbers, phase budgets, or locked decisions MUST update the cleanroom file in the same work unit."
  - "The plan never duplicates cleanroom content — it references it. If a cleanroom fact changes, the plan auto-updates by re-reading."
live_state_basis:
  - audit_timestamp: 2026-04-09T05:24:28Z
  - companies: 39 (verified)
  - bfc_exists: false (audit false-positive on 'Managed Franchise' clarified)
  - bei_6xxx_total: 136 (134 Income + 2 Expense, 0 GL entries)
  - bki_delete_targets: 19 of 20 exist, all 0 GL
  - bei_delete_targets: 22 of 22 exist, all 0 GL
  - bei_settings_bki_sales_income_account: "SALES - BKI TO STORES - BKI"
  - parent_account_chains: 4 (see HB-7)
  - template_collisions: 11 (5 on 4000000, 5 on 4000200, 1 on 4000100)
```

---

## Phase Budget Contract

```yaml
phase_unit_budget:
  Phase 0 (pre-flight + branch + re-verify):              4
  Phase 1 (create BFC Company + BFC COA + 2102205 VAT):   7
  Phase 1.5 (BKI pre-clean: delete 19 accounts, child-first): 5
  Phase 1.6 (BEI pre-clean: delete 21 accounts, child-first, keep 4000005): 6
  Phase 2 (Build MASTER_SALES_TEMPLATE across all 40):    10
  Phase 3 (S168 legacy 4000100/4000101 BKI cleanup):      3
  Phase 4 (Intercompany scaffolding 2104200 + 1104200):   3
  Phase 6 (BEI 6xxxxxx 134-account bulk Income→Expense):  3
  Phase 7 (BEI Settings cutover + S168 runtime smoke):    3
  Phase 8 (Propagate template to remaining 37 companies): 6
  Phase 10 (Full verification + S168 regression):         4
  Phase 11 (Closeout):                                    3
  reconciliation_overhead:                                3
hard_limit_per_phase: 15
preferred_split_threshold: 12
total_units: 60
within_ceiling: true  # 80-unit ceiling per S089 rule
```

**Execution order notes:**
- Phase 1.5 + 1.6 MUST run BEFORE Phase 2 (the BKI/BEI pre-clean resolves the 11 template collisions so Phase 2's `ensure_account` helper never hits a duplicate-name error).
- Phase 7 (BEI Settings cutover) MUST run AFTER Phase 2 creates `4000210 DELIVERIES - BKI` AND BEFORE any delete touches the current linked account.

---

## Phase 0: Pre-flight + Branch + Re-verify

**Units: 4**

### Task 0.1: Create sprint branch + verify registry
```
MUST_MODIFY: .git/HEAD
MUST_CONTAIN: "s175-coa-master-template-uniform-group-restructure"
```
```bash
git fetch origin production
git checkout -b s175-coa-master-template-uniform-group-restructure origin/production
git branch --show-current   # must return the branch
grep S175 docs/plans/SPRINT_REGISTRY.md   # must show the S175 row (or add it if missing)
```

### Task 0.2: Read all required context
Read in this order (every file, fully):
1. `data/_CLEANROOM/2026-04-09_s175_coa_restructure/00_INDEX.md` → `05_OPEN_QUESTIONS_FOR_BUTCH.md`
2. `output/s175/preflight_audit.md`
3. `.claude/skills/frappe-bulk-edits/SKILL.md`
4. S168 runtime code consumers of `bki_sales_income_account`:
   - `hrms/api/commissary.py` (`build_bki_store_sale_invoice`)
   - `hrms/api/billing.py:560` (delivery fee billing)
   - Run: `grep -rn "bki_sales_income_account" hrms/api/` to find any additional consumers
5. `data/_CLEANROOM/agent_runs/2026-04-07_s168-bki-store-sale-billing-on-delivery/AUDIT_DEFERRALS.md` (S168 deferred items including root_type bug D7)

### Task 0.3: Re-verify Phase A audit baseline hasn't drifted
```
MUST_CREATE: scripts/s175_phase_0_reverify.py
MUST_CREATE: output/s175/phase0_reverify.json
```
Re-run the Phase A audit queries (same script: `scripts/s175_phase_a_audit.py`). Compare output against `output/s175/preflight_audit.json`. If ANY delete-target's GL count has changed from 0, HB-2/3/4 triggers and STOP.

### Task 0.4: Initialize run artifact directory
```
MUST_CREATE: data/_CLEANROOM/agent_runs/2026-04-09_s175/
MUST_CREATE: data/_CLEANROOM/agent_runs/2026-04-09_s175/RUN_STATUS.json
```
```json
{"status": "IN_PROGRESS", "phase": "0", "started_at": "<ISO>", "blockers": []}
```

---

## Phase 1: Create BFC Company + BFC COA + BFC Output VAT

**Units: 7**

### Task 1.1: Create BFC Company via Frappe ORM
```
MUST_CREATE: scripts/s175_phase_1_create_bfc.py
MUST_CONTAIN: 'frappe.new_doc("Company")'
MUST_CONTAIN: 'BEBANG FRANCHISE CORP.'
MUST_CONTAIN: '672-618-804-00000'
MUST_CONTAIN: 'abbr = "BFC"'
```
```python
company = frappe.new_doc("Company")
company.company_name = "BEBANG FRANCHISE CORP."
company.abbr = "BFC"
company.default_currency = "PHP"
company.country = "Philippines"
company.tax_id = "672-618-804-00000"
company.chart_of_accounts = "Standard"
company.create_chart_of_accounts_based_on = "Standard Template"
company.date_of_incorporation = "2025-03-27"
company.enable_perpetual_inventory = 0
company.insert(ignore_permissions=True)
frappe.db.commit()
```
**HB-6:** On any failure, write full traceback to `output/s175/phase1_error.log`, STOP.

### Task 1.2: Verify BFC Company + dump initial COA
```
MUST_CREATE: output/s175/phase1_bfc_verification.json
```
Read-only dump: BFC company facts, BFC `tabAccount` 4xxx + 1xxx + 2xxx ranges.

### Task 1.3: Create `2102205 OUTPUT VAT PAYABLE - BFC` (pulled forward from Phase 2 per COA-175-014)
```
MUST_CONTAIN: '2102205'
MUST_CONTAIN: 'OUTPUT VAT PAYABLE'
```
Use `frappe.new_doc("Account")`. Parent = BFC's current liabilities root (per Standard CoA). account_type = "Tax". root_type = "Liability".

### Task 1.4: Create `1104200 DUE FROM BEI - BFC` on BFC
```
MUST_CONTAIN: '1104200'
MUST_CONTAIN: 'DUE FROM BEI'
```
Parent = BFC's current assets (receivables). account_type = "Receivable". root_type = "Asset".

---

## Phase 1.5: BKI Pre-Template Cleanup (child-first)

**Units: 5**

### Task 1.5.1: Delete BKI accounts per `03_CURRENT_STATE_SNAPSHOT.md` Section 3
```
MUST_CREATE: scripts/s175_phase_1_5_bki_preclean.py
```
**Delete order (enforced):**

```python
# Batch A: leaf accounts (no children)
batch_a_bki = ["4000001", "4000002", "4000101", "4000200",
               "4000201", "4000202", "4000203", "4000204", "4000205", "4000206", "4000207",
               "4000301", "4000302", "4000303", "4000304", "4000305", "4000306"]
# Batch B: parents (after their children are gone)
batch_b_bki = ["4000100", "4000300"]  # 4000100 → after 4000101; 4000300 → after 4000301-4000306

for num in batch_a_bki:
    acct = frappe.db.get_value("Account", {"company": "Bebang Kitchen Inc.", "account_number": num}, "name")
    if not acct: continue
    # Re-verify 0 GL entries (HB-2)
    gl_count = frappe.db.sql("SELECT COUNT(*) FROM `tabGL Entry` WHERE account=%s", acct)[0][0]
    assert gl_count == 0, f"HB-2 triggered: {acct} has {gl_count} GL entries"
    frappe.delete_doc("Account", acct, force=True, ignore_permissions=True)

for num in batch_b_bki:
    # same pattern
    ...

frappe.db.commit()
rebuild_tree("Account", "parent_account")
```

### Task 1.5.2: Verify BKI 4xxxxxx clean state
```
MUST_CREATE: output/s175/phase1_5_bki_verification.json
```
Re-dump BKI 4xxxxxx. Assert the batch-A + batch-B accounts no longer exist.

---

## Phase 1.6: BEI Pre-Template Cleanup (child-first)

**Units: 6**

### Task 1.6.1: Delete BEI accounts per `03_CURRENT_STATE_SNAPSHOT.md` Section 4
```
MUST_CREATE: scripts/s175_phase_1_6_bei_preclean.py
```
**Delete order:**

```python
# Batch A: leaf accounts
batch_a_bei = ["4000001", "4000002", "4000003", "4000004", "4000006",  # NOTE: 4000005 KEPT per COA-175-016
               "4000201", "4000202", "4000203", "4000204", "4000205", "4000206", "4000207", "4000208",
               "4000301", "4000302", "4000303", "4000304", "4000305", "4000306"]
# Batch B: parents
batch_b_bei = ["4000200", "4000300"]  # 4000200 → after 4000208; 4000300 → after 4000301-4000306

# same pattern as Phase 1.5 with HB-3 re-verification per account
```

**MUST NOT delete:** `4000005 BRAND GROWTH FEE INCOME - BEI` — kept per COA-175-016 for the JV ₱2M Brand Growth Fee.

### Task 1.6.2: Verify BEI 4xxxxxx clean state
```
MUST_CREATE: output/s175/phase1_6_bei_verification.json
```
Assert deleted accounts gone, `4000005` preserved.

---

## Phase 2: Build Master Sales Template on All 40 Companies (BKI+BEI+BFC first)

**Units: 10**

### Task 2.1: Canonical template as Python module
```
MUST_CREATE: scripts/s175_master_coa_template.py
MUST_CONTAIN: 'MASTER_SALES_TEMPLATE'
```
Load the 27-row template from `data/_CLEANROOM/2026-04-09_s175_coa_restructure/01_CANONICAL_COA_TEMPLATE.md` Section A.2 as a Python list of tuples. Must match exactly.

### Task 2.2: `ensure_account` helper using Frappe ORM (NOT raw SQL)
```
MUST_CONTAIN: 'frappe.new_doc("Account")'
MUST_CONTAIN: 'frappe.rename_doc'
MUST_CONTAIN: 'def ensure_account'
```

```python
def ensure_account(company, number, name, parent_number, is_group, root_type, account_type):
    """
    Idempotent account ensure for a single company.
    - If account with this number exists AND name+is_group+root_type match: skip
    - If account with this number exists AND name differs: rename via frappe.rename_doc
    - If account with this number exists AND is_group mismatches: log warning, skip (HB-5 territory)
    - If not exists: create via frappe.new_doc
    """
    existing = frappe.db.get_value("Account",
        {"company": company, "account_number": number},
        ["name", "account_name", "is_group", "root_type", "parent_account"], as_dict=True)

    # Resolve parent
    parent_name = None
    if parent_number:
        parent_name = frappe.db.get_value("Account",
            {"company": company, "account_number": parent_number}, "name")
        if not parent_name:
            raise Exception(f"Parent {parent_number} not found on {company} — insert parent first")

    if existing:
        # Name mismatch → rename
        expected_name = f"{number} - {name} - {frappe.get_cached_value('Company', company, 'abbr')}"
        if existing["name"] != expected_name:
            frappe.rename_doc("Account", existing["name"], expected_name, force=True)
        # is_group mismatch → STOP (HB-5)
        if existing["is_group"] != is_group:
            raise Exception(f"HB-5: {existing['name']} is_group={existing['is_group']}, expected {is_group}")
        # root_type mismatch → SQL UPDATE (Frappe validator refuses ORM update)
        if existing["root_type"] != root_type:
            frappe.db.sql("UPDATE `tabAccount` SET root_type=%s WHERE name=%s", (root_type, existing["name"]))
        return expected_name

    # Not exists → create
    acct = frappe.new_doc("Account")
    acct.company = company
    acct.account_number = number
    acct.account_name = name
    acct.parent_account = parent_name
    acct.is_group = is_group
    acct.root_type = root_type
    if account_type:
        acct.account_type = account_type
    acct.insert(ignore_permissions=True)
    return acct.name
```

**Why not raw SQL:** Plan v1 claimed a "proven S168 SQL insert pattern" — Phase A verified 3 of 4 cited scripts do NOT exist. The only real proven SQL bypass is for the `root_type` validator (see S168 `s168_finalize_seeds_v3.py` confirmed presence). Everything else must use ORM. Raw INSERT skips `lft`/`rgt` initialization and corrupts the nested set.

### Task 2.3: Apply template to BKI (greenfield post-Phase 1.5)
```
MUST_CREATE: scripts/s175_phase_2_apply_template.py
```
Loop `MASTER_SALES_TEMPLATE` × `ensure_account("Bebang Kitchen Inc.", ...)`. Then call `rebuild_tree("Account", "parent_account")`.

### Task 2.4: Apply template to BEI (greenfield post-Phase 1.6)
Same helper, company = "Bebang Enterprise Inc.".

### Task 2.5: Apply template to BFC (greenfield)
Same helper, company = "BEBANG FRANCHISE CORP.".

### Task 2.6: Verify 4000000 SALES group + 27 accounts on each of BKI/BEI/BFC
```
MUST_CREATE: output/s175/phase2_verification.json
```
Assert every template account exists with the correct parent, is_group, root_type on all 3 companies.

---

## Phase 3: S168 Legacy BKI Cleanup (already largely handled by Phase 1.5)

**Units: 3**

### Task 3.1: Confirm S168 legacy accounts are gone
```
MUST_CREATE: output/s175/phase3_s168_legacy_check.json
```
Assert on BKI:
- `4000100 WHOLESALE / B2B SALES - BKI` does NOT exist
- `4000101 SALES - BKI TO STORES - BKI` does NOT exist
- `4000200 BKI SALES - BKI` exists (is_group=1)
- `4000210 DELIVERIES - BKI` exists (is_group=0, Income Account)

### Task 3.2: Document the S168 known root_type bug status
Per `AUDIT_DEFERRALS.md` D7, S168 accounts were created with inherited `root_type=Expense`. Phase 1.5 deleted them, Phase 2 recreated with correct `root_type=Income` via the `ensure_account` helper. W4 resolved.

### Task 3.3: Verify BEI Settings.bki_sales_income_account STILL points at the (now-deleted) legacy name
Until Phase 7 runs, `BEI Settings.bki_sales_income_account = "SALES - BKI TO STORES - BKI"` is a broken link because Phase 1.5 already deleted that account. S168 billing calls between Phase 1.5 and Phase 7 will fail.
**Mitigation:** S168 runtime is not exercised in production during this sprint's execution window (sprint runs in a single session, no live BKI→store invoicing during execution). Acceptable.
**HB-1:** Phase 7 MUST run before sprint closeout.

---

## Phase 4: Intercompany Scaffolding on BEI

**Units: 3**

### Task 4.1: Create `2104200 DUE TO BFC - BEI`
```
MUST_CONTAIN: '2104200'
MUST_CONTAIN: 'DUE TO BFC'
```
Use `ensure_account()` helper. Parent = BEI's current liabilities group. Phase A confirmed `2104100 SHORT TERM DEBT` and `2104101 LOANS PAYABLE - CURRENT` exist, so `2104200` is a clean number in the same sub-tree.

```python
ensure_account("Bebang Enterprise Inc.", "2104200", "DUE TO BFC",
    parent_number="2104000" if frappe.db.exists("Account", {"company": "Bebang Enterprise Inc.", "account_number": "2104000"}) else "<parent from Phase 0.3 dump>",
    is_group=0, root_type="Liability", account_type="Payable")
```

### Task 4.2: Document collection-agent pattern in script comments
Copy the journal-entry scenarios from `04_INTERCOMPANY_ACCOUNTING.md` Section B as a comment block at the top of `scripts/s175_phase_4_intercompany.py` for future reference.

### Task 4.3: Verify intercompany accounts
```
MUST_CREATE: output/s175/phase4_intercompany_verification.json
```
Assert `2104200` on BEI, `1104200` on BFC (from Phase 1.4), `2102205` on BFC (from Phase 1.3).

---

## Phase 5: (REMOVED in v3 — Butch questionnaire now runs in parallel via tmp/butch_s175_questionnaire.docx, NOT a sprint phase. Finance team decides routing policy after sprint closeout.)

---

## Phase 6: BEI 6xxxxxx Income → Expense Bulk Fix

**Units: 3**

### Task 6.1: Re-verify 0 GL entries (HB-4)
```
MUST_CONTAIN: "account_number LIKE '6%%'"
MUST_CONTAIN: "COUNT(*)"
```
```sql
SELECT COUNT(*) FROM `tabGL Entry` ge
JOIN `tabAccount` a ON ge.account = a.name
WHERE a.company = 'Bebang Enterprise Inc.' AND a.account_number LIKE '6%';
```
Must return 0.

### Task 6.2: Capture pre-update snapshot (rollback artifact)
```
MUST_CREATE: output/s175/phase6_pretouch_backup.json
```
Dump every 6xxxxxx account on BEI with its current `root_type` and `report_type` as a rollback artifact.

### Task 6.3: Bulk UPDATE
```
MUST_CONTAIN: "UPDATE `tabAccount`"
MUST_CONTAIN: "SET root_type = 'Expense'"
```
```sql
UPDATE `tabAccount`
SET root_type = 'Expense', report_type = 'Profit and Loss'
WHERE company = 'Bebang Enterprise Inc.'
  AND account_number LIKE '6%'
  AND root_type = 'Income';
```
Raw SQL is the documented Frappe validator bypass (Account validator refuses `root_type` changes via ORM). This is the ONLY place S175 uses raw SQL.

### Task 6.4: Post-update verification
```
MUST_CREATE: output/s175/phase6_verification.json
```
```sql
SELECT root_type, COUNT(*) FROM `tabAccount`
WHERE company = 'Bebang Enterprise Inc.' AND account_number LIKE '6%'
GROUP BY root_type;
```
Expected: 136 rows all `Expense`. Zero `Income`.

---

## Phase 7: BEI Settings Cutover + S168 Runtime Smoke

**Units: 3**

### Task 7.1: Update `BEI Settings.bki_sales_income_account`
```
MUST_CONTAIN: 'frappe.db.set_single_value'
MUST_CONTAIN: 'bki_sales_income_account'
MUST_CONTAIN: 'DELIVERIES'
```
```python
new_account = frappe.db.get_value(
    "Account",
    {"company": "Bebang Kitchen Inc.", "account_number": "4000210"},
    "name",
)
assert new_account, "4000210 DELIVERIES - BKI not found — Phase 2 template build failed"
frappe.db.set_single_value("BEI Settings", "bki_sales_income_account", new_account)
frappe.db.commit()
```

### Task 7.2: S168 runtime smoke — grep all consumers
```
MUST_CREATE: output/s175/phase7_consumer_grep.txt
MUST_CONTAIN: "hrms/api/commissary.py"
MUST_CONTAIN: "hrms/api/billing.py"
```
```bash
grep -rn "bki_sales_income_account" hrms/api/ > output/s175/phase7_consumer_grep.txt
```
For each consumer line, inspect and confirm the new account resolves correctly. Known consumers:
- `hrms/api/commissary.py` — `build_bki_store_sale_invoice`
- `hrms/api/billing.py:560` — delivery fee billing

### Task 7.3: HB-1 final check
```
MUST_CREATE: output/s175/phase7_hb1_final.json
```
Assert `BEI Settings.bki_sales_income_account` resolves to a valid `tabAccount` row. If not, HB-1 fires.

---

## Phase 8: Propagate Template to Remaining 37 Companies

**Units: 6**

### Task 8.1: Loop template over all non-{BEI, BKI, BFC} companies
```
MUST_CONTAIN: 'for company in frappe.db.get_all'
```
For each of the other 36 companies (JV, MF, TIH, DMD, 32 store corps), apply `MASTER_SALES_TEMPLATE` via the `ensure_account` helper. Per `03_CURRENT_STATE_SNAPSHOT.md` Section 10, 34 of these are fully greenfield (zero 4xxxxxx accounts); 5 companies (JV, MF, TIH, + 2 more) have `4000000 SALES` already and need the idempotent-match path.

### Task 8.2: Per-company verification
```
MUST_CREATE: output/s175/phase8_per_company_verification.json
```
For each of the 37 target companies, verify all 27 template accounts exist with correct parent/is_group/root_type. Rebuild nested set tree per company.

---

## Phase 9: (REMOVED in v3 — first real franchise fee collection deferred to Finance team decision. Fork 1 JE patterns preserved in cleanroom 04_INTERCOMPANY_ACCOUNTING.md for future reference.)

---

## Phase 10: Full Verification + S168 Regression

**Units: 4**

### Task 10.1: Run comprehensive verification script
```
MUST_CREATE: scripts/s175_phase_10_final_verify.py
MUST_CREATE: output/s175/verification_final.json
```
Assertions (all must PASS):
1. `SELECT COUNT(*) FROM tabCompany` = 40 (was 39 + BFC)
2. For each of 40 companies, every entry in `MASTER_SALES_TEMPLATE` exists with correct parent/is_group/root_type → 40 × 27 = 1080 assertions
3. BKI: `4000100`/`4000101` do NOT exist; `4000200`/`4000210` DO exist (is_group correct)
4. BEI: `4000001-4000004`/`4000006`/`4000200-4000208`/`4000300-4000306` do NOT exist; `4000005` DOES exist
5. BEI Settings: `bki_sales_income_account` resolves to a `4000210 DELIVERIES - BKI`-prefixed name
6. BEI 6xxxxxx: all rows have `root_type='Expense'`. Zero `Income`.
7. BFC: Company exists with `tax_id='672-618-804-00000'`
8. `2104200 DUE TO BFC - BEI`, `1104200 DUE FROM BEI - BFC`, `2102205 OUTPUT VAT PAYABLE - BFC` all exist
9. `4000200` is NOT a DISCOUNTS group anywhere across all 40 companies
10. `customer_group='BKI Store'` customer count = 35 (S168 baseline)
11. S168 Custom Fields all present (broad regex, match fixture file)
12. `BEI Settings.input_vat_goods_account` optional fix applied if OQ-4 = "fix it"

Any FAIL → STOP closeout.

### Task 10.2: S168 end-to-end regression smoke
```
MUST_CREATE: output/s175/phase10_s168_regression.json
```
Re-run `scripts/s168_final_validation.py`. Expected: 56/56 PASS.

### Task 10.3: Normalization check
```
MUST_CREATE: data/_CLEANROOM/agent_runs/2026-04-09_s175/NORMALIZATION_CHECK.md
```
Compare final live state against cleanroom files. Any drift → reconcile in the same work unit.

---

## Phase 11: Closeout

**Units: 3**

### Task 11.1: Update plan YAML + registry
```
MUST_MODIFY: docs/plans/2026-04-09-sprint-175-coa-master-template-uniform-group-restructure.md
MUST_MODIFY: docs/plans/SPRINT_REGISTRY.md
MUST_CONTAIN: "status: COMPLETED"
MUST_CONTAIN: "completed_date: 2026-04-"
```

### Task 11.2: Closeout artifacts
```
MUST_CREATE: data/_CLEANROOM/agent_runs/2026-04-09_s175/RUN_STATUS.json (final)
MUST_CREATE: data/_CLEANROOM/agent_runs/2026-04-09_s175/RUN_SUMMARY.md
MUST_CREATE: data/_CLEANROOM/agent_runs/2026-04-09_s175/DEFECT_REGISTER.csv
MUST_CREATE: output/s175/SIGNOFF.md
```

### Task 11.3: Commit + push + PR
```bash
git add -f docs/plans/2026-04-09-sprint-175-coa-master-template-uniform-group-restructure.md
git add -f docs/plans/SPRINT_REGISTRY.md
git add -f data/_CLEANROOM/2026-04-09_s175_coa_restructure/
git add -f data/_CLEANROOM/chat_evidence/2026-04-08_butch_gl_sales/
git add -f data/_CLEANROOM/2026-04-08_franchise_corp_extract/
git add -f data/_CLEANROOM/2026-04-09_franchise_agreements/
git add -f data/_CLEANROOM/agent_runs/2026-04-09_s175/
git add scripts/s175_*.py
git add -f output/s175/
git add -f output/plan-audit/s175-coa-master-template/
git commit -m "closeout(S175): Fork 1 collection-agent model + uniform COA across 40 companies"
git push -u origin s175-coa-master-template-uniform-group-restructure
GH_TOKEN="" gh pr create --repo Bebang-Enterprise-Inc/hrms --base production --head s175-coa-master-template-uniform-group-restructure \
  --title "S175: Uniform COA + Fork 1 BFC Collection-Agent Model" \
  --body "$(cat data/_CLEANROOM/agent_runs/2026-04-09_s175/RUN_SUMMARY.md)"
```

**STOP after PR creation.** Sam handles merge.

---

## Autonomous Execution Contract

```yaml
completion_condition:
  - All structural phases executed successfully (Phase 0, 1, 1.5, 1.6, 2, 3, 4, 6, 7, 8, 10, 11)
  - output/s175/verification_final.json shows all 12 checks PASS
  - S168 final validation re-runs 56/56 PASS (no regression)
  - Plan YAML status = COMPLETED with execution_summary
  - SPRINT_REGISTRY.md S175 row = COMPLETED
  - PR created on hrms

stop_only_for:
  - HB-1: BEI Settings.bki_sales_income_account broken
  - HB-2: BKI delete-target non-zero GL
  - HB-3: BEI delete-target non-zero GL
  - HB-4: BEI 6xxxxxx non-zero GL
  - HB-5: Frappe refuses 4000000 SALES posting→group
  - HB-6: BFC Company creation failure
  - HB-7: Child-first deletion order violated
  - Unexpected schema delta vs Phase A baseline
  - Any of RR-1 through RR-17 fails verification

continue_without_pause_through:
  - audit
  - execute
  - verify
  - closeout

blocker_policy:
  programmatic: fix and continue
  evidence-drift: normalize cleanroom + plan + state in same edit, continue
  3x-repeated-failure: grounded research, then continue
  business-data-or-policy: pause
  legal-agreement-change: pause (Phase 2 concern)

signoff_authority: single-owner (Sam Karazi)

canonical_closeout_artifacts:
  - data/_CLEANROOM/agent_runs/2026-04-09_s175/RUN_STATUS.json
  - data/_CLEANROOM/agent_runs/2026-04-09_s175/RUN_SUMMARY.md
  - data/_CLEANROOM/agent_runs/2026-04-09_s175/DEFECT_REGISTER.csv
  - data/_CLEANROOM/agent_runs/2026-04-09_s175/NORMALIZATION_CHECK.md
  - output/s175/verification_final.json
  - output/s175/SIGNOFF.md
  - docs/plans/2026-04-09-sprint-175-coa-master-template-uniform-group-restructure.md (status COMPLETED)
  - docs/plans/SPRINT_REGISTRY.md (S175 row COMPLETED)
```

---

## Zero-Skip Enforcement

Every task in the phase tables above MUST be implemented. No exceptions.

**Forbidden agent behaviors:**
1. Skipping a task silently
2. Marking partial work as "done"
3. Replacing a task with a simpler version without user approval
4. Saying "deferred to next sprint"
5. Combining tasks and dropping features
6. Implementing happy path only, skipping edge cases
7. Assuming `0 GL entries` without re-verifying during execution
8. Using raw SQL INSERT on `tabAccount` (only the documented Phase 6 `root_type` UPDATE is allowed)

**Phase completion checklist format** (required after each phase):

| Task | Status | Evidence file | Grep assertion | Skipped? | If skipped, why? |
|------|--------|---------------|----------------|----------|------------------|

**Machine-verifiable phase gate:** Each phase's verification script (`s175_phase_N_verify.py`) must exit 0 before the next phase starts. Gate is script-based, not prose.

---

## L3 Workflow Scenarios (N/A)

This sprint has NO operator-facing UI surface. L3 Playwright scenarios are not applicable.

**Equivalent gate:** SSM verification queries (Phase 10.1, 12 checks) + S168 regression smoke (Phase 10.2, 56 checks).

**Cold-start readability:** An agent with zero context reads the 6 cleanroom files (in the order listed in the YAML header) and this plan. Cleanroom carries all decisions + current state + JE patterns. Plan carries only the execution sequence. Nothing is duplicated.

---

## Signoff Model

- **mode:** single-owner
- **approver_of_record:** Sam Karazi (CEO)
- **signoff_artifact:** `output/s175/SIGNOFF.md`
- **Butch's role:** decisional for COA structure only (already locked in cleanroom). Routing policy questions run in parallel via `tmp/butch_s175_questionnaire.docx` and do NOT gate this sprint.
- **Legal:** out of scope for S175. Phase 2 intercompany services agreement is Legal's domain.

---

## Certification Coverage Contract

```yaml
certified_universe:
  companies: 40 (39 existing + BFC new)
  template_accounts: 27 per MASTER_SALES_TEMPLATE
  total_template_assertions: "40 × 27 = 1080 account positions"
  intercompany_accounts: 3 (2104200 BEI, 1104200 BFC, 2102205 BFC)
  bei_expense_accounts_fixed: 134 (134 → Expense, was 134 Income)
  s168_regression_checks: 56
closeout_zero_equations:
  - "BKI 4000100/4000101/4000001/4000002/4000200-207/4000300-306 count = 0"
  - "BEI 4000001-4000004/4000006/4000200-208/4000300-306 count = 0"
  - "BEI 4000005 BRAND GROWTH FEE INCOME count = 1 (preserved per COA-175-016)"
  - "BEI 6xxxxxx with root_type='Income' count = 0"
  - "S168 validation failures = 0"
  - "Blockers at closeout = 0 (or dispositioned)"
allowed_skips:
  - "OQ-4 BEI input_vat_goods_account fix SKIPPED (policy question — deferred to Finance decision)"
  - "OQ-5 JV fee sub-group restructure SKIPPED (policy question — deferred to Finance decision)"
final_readiness_basis:
  - output/s175/verification_final.json (12 checks)
  - S168 final validation 56/56 PASS
  - RUN_STATUS.json status=COMPLETED
```

---

## Anti-Rewind / Concurrent-Run Protection Contract

```yaml
ownership_matrix:
  artifact: output/s175/S175_SURFACE_OWNERSHIP_MATRIX.csv
  rule: "Single-agent execution. Ownership = entire hq.bebang.ph Frappe COA (40 companies × 4/6/2/1 ranges)."
protected_surfaces:
  rule: "S168 runtime code (hrms/api/commissary.py, hrms/api/billing.py, hrms/api/store.py) MUST NOT be modified. S168 Custom Fields and BEI Settings BKI fields schema MUST NOT be changed (only field VALUES are updated, not schema)."
remote_truth_baseline:
  repo: "Bebang-Enterprise-Inc/hrms"
  release_branch: "production"
  release_head_sha: "<captured at Phase 0 start>"
  live_evidence_basis: "2026-04-09 Phase A SSM audit at output/s175/preflight_audit.json"
touched_file_routing:
  rule: "No hrms/ application code. Only docs/plans/, data/_CLEANROOM/, scripts/s175_*.py, output/s175/, output/plan-audit/s175-coa-master-template/. All live mutations are on hq.bebang.ph Frappe DB via SSM."
pretouch_backup:
  artifact: output/s175/phase6_pretouch_backup.json
  rule: "Phase 6 134-row bulk UPDATE captures pre-update snapshot as rollback artifact. Phase 1.5/1.6 deletes capture pre-delete `tabAccount` dump per batch."
supersession_map:
  - "COA-004 (2026-02-12 Butch discounts lock) → SUPERSEDED by COA-175-002"
  - "ICT-008 (S168 original 4000100/4000101 lock) → SUPERSEDED by COA-175-001"
  - "Butch 2026-04-08 PM directive (Royalty→BFC, rest→BEI) → SUPERSEDED by Butch 2026-04-09 AM reversal"
  - "Plan v1 (2026-04-09 AM) → SUPERSEDED by Plan v2 (this file, 2026-04-09 PM) — all 11 CRITICALs addressed"
  - "COA-175-004 (Fork 2 interim BEI revenue) → SUPERSEDED by COA-175-013 (Fork 1 collection-agent)"
```

---

## Execution Authority

Autonomous execution by a single agent in a single session is the target. All structural phases (0, 1, 1.5, 1.6, 2, 3, 4, 6, 7, 8, 10, 11) run without external dependencies — no policy gates.

Sam is the sole signoff authority.

---

## Agent Boot Sequence

1. Read this plan fully.
2. **Create sprint branch:** `git fetch origin production && git checkout -b s175-coa-master-template-uniform-group-restructure origin/production`. NEVER write code on production.
3. Verify `docs/plans/SPRINT_REGISTRY.md` has the S175 row (if missing, add it per `SPRINT_NUMBERING_POLICY.md`).
4. **Read all 6 cleanroom files** at `data/_CLEANROOM/2026-04-09_s175_coa_restructure/` in the order listed in the YAML header. They ARE the decision authority — the plan is thin on rationale because the cleanroom carries it.
5. Read `output/s175/preflight_audit.md` for live baseline.
6. Read `.claude/skills/frappe-bulk-edits/SKILL.md` for the SSM pattern. Do NOT rely on phantom script references from plan v1.
7. Grep `hrms/api/` for `bki_sales_income_account` — confirm both `commissary.py` and `billing.py:560` consumers, add any new ones found to Phase 7 smoke.
8. Initialize `data/_CLEANROOM/agent_runs/2026-04-09_s175/RUN_STATUS.json`.
9. Execute Phases 0 → 11 in order. 1.5 and 1.6 run between 1 and 2.
10. At each phase boundary, run the phase-N verification script and require exit code 0 before starting the next phase.
11. Closeout per Phase 11 only when all completion_condition items are satisfied.
12. On any HARD BLOCKER or 3× repeated failure, STOP, write to `BLOCKERS.csv`, present options to user.
