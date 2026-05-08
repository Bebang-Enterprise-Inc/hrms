---
sprint_id: S243
sprint_title: Canonical CoA Backfill — 4 BEBANG ENTERPRISE INC. Stores
plan_branch: s243-canonical-coa-4-stores
status: PLANNED
version: 1.0
created_date: 2026-05-09
canonical_scope: in
canonical_model_reference: docs/STORE_COMPANY_CANONICAL.md
canonical_preflight: required
depends_on: none
unblocks: S238 (Phase 0-T4 CoA-completeness gate)
evidence_committed:
  - output/s243/SUMMARY.md
  - output/s243/verification/before_state.json
  - output/s243/verification/reference_xmm_coa.json
  - output/s243/verification/coa_gap_analysis.json
  - output/s243/verification/seed_dry_run_report.json
  - output/s243/verification/after_state.json
  - output/s243/verification/canonical_post_check.log
  - output/s243/verification/coa_complete_count.json
  - output/s243/verification/seed_ledger.json
evidence_transient:
  - tmp/s243/probe_*.json
  - tmp/s243/seed_dry_run_*.log
  - tmp/s243/diff_*.txt
sprint_registry_row: |
  | `S243` | Sprint 243 | `s243-canonical-coa-4-stores` | TBD | PLANNED 2026-05-09 — Canonical CoA Backfill (4 BEBANG ENTERPRISE INC. stores) to unblock S238 Phase 0-T4. ~22 work units. | `docs/plans/2026-05-09-sprint-243-canonical-coa-4-stores.md` |
---

# S243 — Canonical CoA Backfill — 4 BEBANG ENTERPRISE INC. Stores

> **Canonical model reference:** `docs/STORE_COMPANY_CANONICAL.md`
> **Unblocks:** S238 Phase 0-T4 CoA-completeness gate.

---

## Design Rationale (For Cold-Start Agents)

### Why this exists

S238 Phase 0-T4 probe (executed 2026-05-08, command `24e4ba52-5984-435c-b91e-c68760806587`) found 4 of 49 per-store Companies have skeleton Charts of Accounts: only 5 accounts each (2 group + 3 leaf), missing the canonical `Stock Assets - <ABBR>`, `Accounts Payable - <ABBR>`, and `Current Assets - <ABBR>` parent groups that S238's Phase 1 seeder requires for its 3 leaf accounts (`Inventory-from-Commissary`, `AP-Trade-BKI`, `Input VAT - BKI Inter-Co`).

The 4 affected stores — all on `BEBANG ENTERPRISE INC.` legal entity, all created 2026-04-13:

| Store name | Abbr | Total accounts | Group accts | Submitted BKI SIs | Submitted ₱ |
|---|---|---:|---:|---:|---:|
| ROBINSONS ANTIPOLO - BEBANG ENTERPRISE INC. | ROA | 5 | 2 | 8 | ₱11,846.88 |
| SM MANILA - BEBANG ENTERPRISE INC. | SMM | 5 | 2 | 11 | ₱16,289.46 |
| SM MEGAMALL - BEBANG ENTERPRISE INC. | SMMM | 5 | 2 | 13 | **₱443,955.60** |
| SM SOUTHMALL - BEBANG ENTERPRISE INC. | SMS | 5 | 2 | 10 | ₱11,040.64 |
| **Total** | | **20** | **8** | **42** | **₱483,132.58** |

What they DO have: a Frappe Company record, a billing Customer (per canonical), one Warehouse, and `1100000 - ASSETS - <ABBR>` (Asset root group) + `2104000 - INTERCOMPANY PAYABLES - <ABBR>` (Liability sub-group) + 3 Frappe-default leaf accounts.

What they DON'T have: any leaf accounts under `Stock Assets`, `Accounts Payable`, or `Current Assets` parent groups. The `_find_parent_group()` helper in `hrms/on_demand/s206_seed_intercompany_accounts.py:90` looks up parents by leaf-name pattern (e.g., `WHERE account_name LIKE 'Stock Assets%'`) and falls back to `WHERE is_group=1 AND account_name='Stock Assets'`. For these 4 stores both queries return None.

The 45 complete stores have full canonical CoA hierarchies (e.g., XENTROMALL MONTALBAN: `Stock Assets - XMM`, `2110000 - ACCOUNTS PAYABLE - XMM`, `1100000 - CURRENT ASSETS - XMM` group accounts plus dozens of leaves). Bringing the 4 incomplete stores up to that shape — at minimum the parent groups S238 needs — closes the gate.

### Why this is a separate sprint (not an in-flight S238 amendment)

1. **Scope discipline:** S238 is the PI mirror sprint. Auto-creating master-data parent groups inside it would expand scope into canonical territory and risk PR #638-class drift (the 2026-04-19 incident where 3 sprints each shipped correct in isolation but cumulative drift broke per-store billing).
2. **`canonical_scope: in` rule:** the canonical-model rule explicitly says *"Never invent new store concepts. If bypassed, drift compounds and costs days to clean up."* Master-data mutation needs its own audit gate.
3. **Plan stop directive:** S238 v2.2 plan body (Phase 1-T2 + `stop_only_for`) literally says *"If any store has missing parent groups (some stores may not have all 3 of `Stock Assets`, `Accounts Payable`, `Current Assets`), STOP — Phase 0-T4 should have caught this; if it slipped through, ask Sam."*
4. **CEO directive 2026-05-08 (in-conversation):** "Stop S238. Kick a small canonical CoA seeder sprint that fills out CoA for these 4 stores to match the 45 complete stores. Resume S238 after." (Cleanest path; ~4-8 hours sprint; treats CoA gap as canonical drift.)

### Why this approach (and what was rejected)

| Considered | Why rejected |
|---|---|
| Skip these 4 in S238 Phase 1 seeder; PI generator no-ops with Sentry breadcrumb | ~₱58K of Q1 Input VAT silently uncapturable from these 4 stores' Submitted SIs. Drift-detection alerts are paper trails, not money recovered. |
| Auto-create parent groups inside S238 Phase 1 | Violates `canonical_scope: in` rule + plan's explicit stop directive + master-data drift in execution sprint = PR #638 risk. |
| Full canonical CoA harmonization (every account every legal entity has) | Out of scope — the goal is unblock S238, not re-canonicalize 4 entire CoAs. The S243 seeder creates ONLY the parent groups + nothing else. Future sprints can fill remaining gaps once 4 stores actually transact (e.g., when their Mosaic POS revenue starts hitting these per-store books). |
| **(chosen)** Targeted S243 seeder — only the 4 stores, only the missing parent groups + their immediate ancestors discovered in Phase 1 reference comparison | Smallest possible change to clear S238's gate. Reuses proven `_find_parent_group()` / `_ensure_account()` patterns from s206. Scoped, idempotent, savepoint-safe. |

### Key trade-off decisions

| Decision | Choice | Rationale |
|---|---|---|
| Reference store for canonical comparison | `XENTROMALL MONTALBAN - PERPETUAL FOOD CORP.` (XMM) | Has full canonical CoA per S238 probe; not a parent legal entity (so all accounts are per-store); recently active. |
| Naming convention | Match XMM's account_name strings exactly (with `<ABBR>` substitution) | Naming consistency across the 49 per-store Companies — required for `_find_parent_group()` LIKE patterns to match. |
| Account number scheme | Use the same account_numbers XMM uses (with collision check on the 4 target stores) | Prevents number collision on existing `1100000 ASSETS` / `2104000 INTERCOMPANY PAYABLES` accounts. |
| Scope boundary | Create ONLY the parent groups required by S238 + their immediate ancestors. NO leaf accounts, NO Sales tree, NO COGS/Expense seeding. | Smallest change that unblocks S238. Anything beyond is OUT OF SCOPE for this sprint. |
| Idempotency | Hard requirement | Re-running the seeder must be safe (creates only what's missing, leaves existing accounts untouched). |
| Tooling | New `scripts/s243/seed_canonical_coa_for_4_stores.py` following `hrms/on_demand/s206_seed_intercompany_accounts.py` pattern | Reuses proven savepoint + ledger + idempotent helpers. |

### Known limitations and their mitigations

| Limitation | Mitigation |
|---|---|
| 42 historical Submitted BKI SIs (₱483K) cannot retroactively get a store-side PI mirror via S238 alone (S238 hooks `Sales Invoice on_submit`, not `on_existing`). | Out of scope for S243. Note in closeout SUMMARY for follow-up Q1 Input VAT recovery sprint. |
| These 4 stores still won't have a full Sales tree, COGS accounts, or Expense hierarchy after S243. | Out of scope. S243 only closes the S238-gate. Full CoA harmonization is a separate (larger) sprint, triggered only when these stores need to post Sales (e.g., when their Mosaic POS revenue recognition kicks in). |
| The `_find_parent_group()` LIKE-match pattern depends on canonical naming. If XMM-style naming and these 4 stores' existing groups (`1100000 - ASSETS - <ABBR>`) co-exist with no overlap, no problem. If they overlap unexpectedly, Phase 1 detects and STOPs. | Phase 1 reference comparison + Phase 2 dry-run. |
| `disabled` column doesn't exist on `tabCompany` in this Frappe build (v15 confirmed via S238 probe SQL failure). All Company queries must use `is_group=0` filter, never `disabled=0`. | Documented in HARD BLOCKER section below + reused from S238 probe fix. |

### Source references

- **S238 plan body:** `docs/plans/2026-05-07-sprint-238-ict003-store-pi-generator.md` Phase 0-T4 + `stop_only_for`
- **S238 Phase 0 probe results (this sprint's starting evidence):**
  - `tmp/s238/phase0_probe_result.json` — full Phase 0 probe (`coa_survey_complete_count: 45/49`)
  - `tmp/s238/followup_4stores_result.json` — group-account inventory for the 4 stores
  - `tmp/s238/followup2_si_activity.json` — SI activity proving they're live
  - `tmp/s238/HARD_STOP_phase0_4stores_coa_gap.md` — full incident analysis
- **Reference seeder pattern:** `hrms/on_demand/s206_seed_intercompany_accounts.py` (functions: `_find_parent_group` line 90, `_ensure_account` line 194, `_in_scope_companies` line 76, `execute` line 337)
- **Canonical CoA template doc:** `data/_CLEANROOM/2026-04-09_s175_coa_restructure/01_CANONICAL_COA_TEMPLATE.md`
- **Canonical model SSOT:** `docs/STORE_COMPANY_CANONICAL.md`
- **Verifier:** `scripts/verify_canonical_structure.py` (read-only audit, ALL CANONICAL pre/post)
- **CEO directive:** in-conversation 2026-05-08, captured in S238 HARD_STOP file

---

## Canonical Model Preflight (Mandatory)

Executing agent MUST run before the first code change:

```bash
python scripts/verify_canonical_structure.py 2>&1 | tee tmp/s243/canonical_preflight.log
```

Must print `[RESULT] ALL CANONICAL — no action required` (or only the pre-existing `BILLING_CUST_TIN_EMPTY` for `ORTIGAS GREENHILLS - BEIFRANCHISE FOOD OPC`). If any other `[VIOLATION]`, STOP and ask Sam — do NOT add records, flip fields, or work around it. Same baseline expected post-execution.

**Canonical law (summary — full rules in `docs/STORE_COMPANY_CANONICAL.md`):**
- Every store has EXACTLY 1 per-store Company + 1 Warehouse + 1 billing Customer + 1 Internal Customer.
- All four share the same name string.
- Per-store Company's `parent_company` links to the legal entity parent (here: `BEBANG ENTERPRISE INC.`).
- Warehouse.company = the per-store Company (NEVER the parent).

**Forbidden in this plan (without explicit CEO approval in-line):**
- Creating a second Warehouse / Customer / Company for any store (we already have one each).
- Modifying `represents_company` on any Internal Customer.
- Adding new fallback branches to `resolve_store_buyer_entity`.
- Ad-hoc SQL `UPDATE tabCompany / tabWarehouse / tabCustomer` on production.
- `frappe.delete_doc` on any master record.
- Creating accounts outside the 4 named target Companies.
- Creating leaf accounts that are not strictly required by S238 (no Sales tree, no COGS, no Expense seeding — that's out of scope).

**Scope claim:** This plan creates only **group accounts** (`is_group=1`) on these 4 Companies:
- `ROBINSONS ANTIPOLO - BEBANG ENTERPRISE INC.` (abbr: `ROA`)
- `SM MANILA - BEBANG ENTERPRISE INC.` (abbr: `SMM`)
- `SM MEGAMALL - BEBANG ENTERPRISE INC.` (abbr: `SMMM`)
- `SM SOUTHMALL - BEBANG ENTERPRISE INC.` (abbr: `SMS`)

No `tabCompany`/`tabWarehouse`/`tabCustomer`/`tabSupplier` mutations. No leaf accounts. The exact group account list is determined dynamically in Phase 1 by reference comparison vs XMM (canonical reference store).

---

## Canonical Model Binding

This sprint binds to the canonical model as follows:
- Reads `tabCompany.name` for the 4 target stores → resolves `abbr` for account naming
- Reads XMM's existing `tabAccount` rows → derives canonical group account list
- Writes `tabAccount` rows with `is_group=1` only, on the 4 target Companies, mirroring XMM's parent group structure with `<ABBR>` substitution
- Inserts via Frappe ORM (`frappe.new_doc("Account")` + `.insert(ignore_permissions=True)`) — never raw SQL — to preserve Frappe's account-tree integrity (lft/rgt updates)

Does NOT:
- Touch `tabCompany`, `tabWarehouse`, `tabCustomer`, `tabSupplier`
- Create leaf accounts (those are S238's Phase 1 deliverable)
- Modify any other Company's CoA
- Touch GL Entries, Stock Ledger Entries, or any transactional data
- Modify `resolve_store_buyer_entity` or any resolver function
- Alter `bei_config.py` or `supply_chain_contracts.py`

---

## Worktree Isolation & Evidence Split

Per `.claude/rules/worktree-isolation.md`, the executing agent works in `F:/Dropbox/Projects/BEI-ERP-s243-canonical-coa-4-stores/` (already spawned at plan creation; confirmed in Phase 0).

| Path | Tracked? | Lifetime |
|---|---|---|
| `output/s243/SUMMARY.md` | committed | permanent |
| `output/s243/verification/*.json` | committed | permanent (audit-ready evidence) |
| `output/s243/verification/canonical_post_check.log` | committed | permanent |
| `output/s243/verification/seed_ledger.json` | committed | permanent (records every account created) |
| `tmp/s243/probe_*.json` | gitignored | session-local |
| `tmp/s243/seed_dry_run_*.log` | gitignored | session-local |
| `tmp/s243/diff_*.txt` | gitignored | session-local |

---

## Test Data Seeding Contract

**Not applicable.** S243 creates *production* canonical master-data (group accounts on 4 per-store Companies). These are PERMANENT records — they are never to be deleted post-creation. There is no "teardown" because there is no test data; the sprint's deliverable IS the production change.

If the seeder fails mid-run, the savepoint pattern from s206 rolls back the partial transaction. No teardown ledger needed.

---

## Phases

### Phase 0 — Boot, Worktree Confirm, Canonical Preflight, Pre-State Probe (4 units)

**0-T1** Read this plan fully. Read `data/_CLEANROOM/2026-04-09_s175_coa_restructure/01_CANONICAL_COA_TEMPLATE.md` for canonical CoA shape reference.

**0-T2** Confirm worktree:
```bash
cd F:/Dropbox/Projects/BEI-ERP-s243-canonical-coa-4-stores
git status --short    # must be clean other than this plan + registry
mkdir -p tmp/s243 output/s243/verification
git rev-parse origin/production > tmp/s243/remote_truth_baseline_hrms.sha
```

**0-T3** Run canonical preflight + capture baseline:
```bash
python scripts/verify_canonical_structure.py 2>&1 | tee tmp/s243/canonical_preflight.log
```
Must show `ALL CANONICAL`. If violations, STOP.

**0-T4** Probe full account inventory for the 4 target stores via SSM. Reuse the probe pattern from `tmp/s238/probe_4_incomplete_stores.py`. Write `output/s243/verification/before_state.json` with:
- For each of 4 stores: `total_accounts`, `group_accounts`, `leaf_accounts`, all `is_group=1` rows with full fields, all leaf rows
- Their billing Customer existence + name
- Their Warehouse(s)
- Their `parent_company` and `abbr`
- BKI SI counts (from `tabSales Invoice WHERE company='BEBANG KITCHEN INC.' AND customer=<store>`)

**MUST_MODIFY:** `output/s243/verification/before_state.json`
**MUST_CONTAIN:** `"ROBINSONS ANTIPOLO"`, `"SM MANILA"`, `"SM MEGAMALL"`, `"SM SOUTHMALL"`, `"all_group_accounts"`, `"total_accounts"`, `"abbr"`

**Phase 0 verify:**
```python
import os, json, sys
errs = []
for f in ["tmp/s243/canonical_preflight.log", "output/s243/verification/before_state.json"]:
    if not os.path.exists(f): errs.append(f"MISSING: {f}")
log = open("tmp/s243/canonical_preflight.log", encoding="utf-8", errors="replace").read()
if "ALL CANONICAL" not in log: errs.append("Canonical preflight not clean")
state = json.load(open("output/s243/verification/before_state.json", encoding="utf-8"))
expected = {
    "ROBINSONS ANTIPOLO - BEBANG ENTERPRISE INC.",
    "SM MANILA - BEBANG ENTERPRISE INC.",
    "SM MEGAMALL - BEBANG ENTERPRISE INC.",
    "SM SOUTHMALL - BEBANG ENTERPRISE INC.",
}
missing = expected - set(state.get("stores", {}).keys())
if missing: errs.append(f"missing stores in before_state: {missing}")
print("PASS" if not errs else "\n".join(errs))
sys.exit(0 if not errs else 1)
```

---

### Phase 1 — Reference Mapping & Gap Analysis (5 units)

**1-T1** Probe XENTROMALL MONTALBAN (canonical reference store) full CoA via SSM. Write `output/s243/verification/reference_xmm_coa.json`:
- All `tabAccount` rows for `company='XENTROMALL MONTALBAN - PERPETUAL FOOD CORP.'`
- For each row: `name`, `account_name`, `account_number`, `parent_account`, `is_group`, `root_type`, `account_type`
- Group-only subset: every `is_group=1` row organized by `root_type` (Asset/Liability/Equity/Income/Expense)

**MUST_MODIFY:** `output/s243/verification/reference_xmm_coa.json`
**MUST_CONTAIN:** `"Stock Assets"`, `"Current Assets"`, `"Accounts Payable"`, `"XMM"`, `"groups_by_root_type"`

**1-T2** Build the gap-analysis: compare each of the 4 incomplete stores against XMM's group structure. For each `(target_store, root_type)`, compute:
- Group accounts XMM has under this root_type that the target store lacks (matched by `account_name` after stripping the abbr suffix)
- The exact `account_number` and `parent_account` chain XMM uses
- Whether intermediate ancestor groups need creation first (e.g., if XMM has `Stock Assets - XMM` parented to `1100000 - ASSETS - XMM` and the target store also has its own `1100000 - ASSETS - <ABBR>`, the chain is reusable; otherwise create ancestors top-down)

Output: `output/s243/verification/coa_gap_analysis.json`:
```json
{
  "ROA": {
    "abbr": "ROA",
    "existing_group_count": 2,
    "groups_to_create": [
      {
        "account_number": "<from XMM>",
        "account_name": "Stock Assets - ROA",
        "parent_account": "1100000 - ASSETS - ROA",
        "root_type": "Asset",
        "rationale": "S238 Phase 1-T1 needs this parent for Inventory-from-Commissary leaf"
      },
      ...
    ]
  },
  ...
}
```

**1-T3** **HARD BLOCKER:** if any of these conditions are true, STOP and present to Sam:
1. The gap analysis suggests creating MORE than 4 group accounts per store. Means the gap is wider than expected; needs scope discussion.
2. XMM's parent chain references group accounts that don't exist on target stores AND can't be reused from existing target-store ancestors. Means we'd need to create intermediate groups; quantify and decide.
3. The 4 target stores' existing `1100000 - ASSETS - <ABBR>` and `2104000 - INTERCOMPANY PAYABLES - <ABBR>` groups conflict with XMM's account-number scheme (e.g., XMM uses `1100000` for `CURRENT ASSETS`, not `ASSETS`). Means we need a naming/numbering reconciliation decision before proceeding.

**1-T4** Write summary of gap to conversation + present to Sam if any HARD BLOCKER from 1-T3 fires. Otherwise proceed to Phase 2.

**MUST_MODIFY:** `output/s243/verification/coa_gap_analysis.json`
**MUST_CONTAIN:** `"groups_to_create"`, all 4 abbreviations (`"ROA"`, `"SMM"`, `"SMMM"`, `"SMS"`), `"rationale"`

**Phase 1 verify:**
```python
import json, sys
errs = []
gap = json.load(open("output/s243/verification/coa_gap_analysis.json", encoding="utf-8"))
for abbr in ("ROA", "SMM", "SMMM", "SMS"):
    if abbr not in gap: errs.append(f"missing {abbr} in gap analysis")
    g = gap.get(abbr, {})
    if "groups_to_create" not in g: errs.append(f"{abbr} missing groups_to_create")
    if len(g.get("groups_to_create", [])) > 4:
        errs.append(f"{abbr} wants to create {len(g['groups_to_create'])} groups — wider than expected, see HARD BLOCKER 1-T3")
print("PASS" if not errs else "\n".join(errs))
sys.exit(0 if not errs else 1)
```

---

### Phase 2 — Seeder Script + Dry-Run (6 units)

**2-T1** Write `scripts/s243/seed_canonical_coa_for_4_stores.py` (NEW). Structure mirrors `hrms/on_demand/s206_seed_intercompany_accounts.py`:

```python
#!/usr/bin/env python3
"""S243 — Canonical CoA backfill for 4 BEBANG ENTERPRISE INC. stores.

Reads gap analysis from output/s243/verification/coa_gap_analysis.json,
creates the missing parent group accounts on the 4 target stores via Frappe
ORM (preserves lft/rgt account-tree integrity), savepoint-wrapped, idempotent.

Strictly scoped to:
  TARGET_COMPANIES = [
      "ROBINSONS ANTIPOLO - BEBANG ENTERPRISE INC.",
      "SM MANILA - BEBANG ENTERPRISE INC.",
      "SM MEGAMALL - BEBANG ENTERPRISE INC.",
      "SM SOUTHMALL - BEBANG ENTERPRISE INC.",
  ]

If asked to create on any other Company, raise — do not silently expand scope.

Reuses helpers conceptually from s206_seed_intercompany_accounts.py:
  - _ensure_account(...) — idempotent INSERT-or-skip (line 194 reference)
  - savepoint pattern (s206 SAVEPOINT_NAME line 45)
  - report-style return value (s206 _write_report line 317)

Run on production via SSM:
  python tmp/s243/run_seeder.py [--dry-run]
"""
```

Required helpers in the script:
- `_load_gap_analysis()` — read `output/s243/verification/coa_gap_analysis.json`; assert all 4 stores present
- `_ensure_group_account(company, account_number, account_name, parent_account, root_type)` — return `(name, status)` where status ∈ `{created, existed, error}`. Use `frappe.new_doc("Account")` + `.insert()`; idempotent on duplicate-name (look up existing first).
- `_validate_target_company(company)` — assert in `TARGET_COMPANIES`; raise `ValueError` otherwise.
- `execute(dry_run: bool = False) -> dict` — main entry; loops the 4 companies × their gap; returns ledger dict.

**MUST_MODIFY:** `scripts/s243/seed_canonical_coa_for_4_stores.py` (NEW)
**MUST_CONTAIN:** `TARGET_COMPANIES`, `_ensure_group_account`, `_load_gap_analysis`, `_validate_target_company`, `frappe.db.savepoint`, `BEBANG ENTERPRISE INC.`, `s243_seed_canonical_coa`

**2-T2** **HARD BLOCKER:** the seeder MUST refuse to run if the gap analysis JSON requests:
- An account on a Company NOT in `TARGET_COMPANIES`
- An account with `is_group=0` (this sprint creates only group accounts)
- An account whose name doesn't follow `<canonical group name> - <ABBR>` pattern
- More than 4 accounts per Company (anti-scope-creep)

If any of the above, raise `ValueError(f"S243: refusing to create out-of-scope account: ...")` and exit non-zero.

**2-T3** Wire SSM execution: `tmp/s243/run_seeder.py` (uses the boilerplate from `frappe-bulk-edits` skill). Two modes:
- `--dry-run`: opens savepoint, creates accounts, writes ledger to `tmp/s243/seed_dry_run_<timestamp>.log`, ROLLBACK savepoint, exits with status info
- (default): same but COMMIT savepoint, write final ledger to `output/s243/verification/seed_ledger.json`

**2-T4** Run dry-run for `ROA` only (single-store smoke). Capture log to `tmp/s243/seed_dry_run_roa.log`. Verify:
- All requested accounts created OR existed (no errors)
- Frappe account tree didn't crash on insert
- ROLLBACK was clean (post-run probe shows ROA still has only 5 accounts)

**MUST_CONTAIN (in dry-run log):** `"ROA"`, `"created"` OR `"existed"` per requested account, `"ROLLBACK"` confirmation

**2-T5** Run dry-run for ALL 4 stores. Write `output/s243/verification/seed_dry_run_report.json`:
```json
{
  "mode": "dry-run",
  "timestamp_utc": "...",
  "stores": {
    "ROA": {"abbr": "ROA", "to_create": [...], "result": [{"name": "...", "status": "created"}, ...]},
    "SMM": {...},
    "SMMM": {...},
    "SMS": {...}
  },
  "rollback_confirmed": true,
  "post_dry_run_account_counts": {
    "ROA": 5, "SMM": 5, "SMMM": 5, "SMS": 5
  }
}
```
`post_dry_run_account_counts` MUST equal pre-state (proves rollback worked).

**MUST_MODIFY:** `output/s243/verification/seed_dry_run_report.json`
**MUST_CONTAIN:** `"rollback_confirmed": true`, `"post_dry_run_account_counts"`, all 4 abbrs

**2-T6** **HARD BLOCKER:** if dry-run leaves ANY new account on production (rollback failed for any reason), STOP. Do NOT proceed to Phase 3. Investigate, fix the seeder, redo dry-run.

**Phase 2 verify:**
```python
import os, json, sys
errs = []
for f in [
    "scripts/s243/seed_canonical_coa_for_4_stores.py",
    "output/s243/verification/seed_dry_run_report.json",
]:
    if not os.path.exists(f): errs.append(f"MISSING: {f}")
seeder = open("scripts/s243/seed_canonical_coa_for_4_stores.py", encoding="utf-8").read()
for needle in ["TARGET_COMPANIES", "_ensure_group_account", "_load_gap_analysis", "_validate_target_company", "savepoint"]:
    if needle not in seeder: errs.append(f"seeder missing: {needle}")
report = json.load(open("output/s243/verification/seed_dry_run_report.json"))
if not report.get("rollback_confirmed"): errs.append("dry-run rollback not confirmed")
counts = report.get("post_dry_run_account_counts", {})
for abbr in ("ROA", "SMM", "SMMM", "SMS"):
    if counts.get(abbr) != 5: errs.append(f"{abbr} post-dry-run count != 5 (rollback failed)")
print("PASS" if not errs else "\n".join(errs))
sys.exit(0 if not errs else 1)
```

---

### Phase 3 — Apply Seeder to All 4 Stores (4 units)

**3-T1** Run the seeder in COMMIT mode against production via SSM. Output to `output/s243/verification/seed_ledger.json`:
```json
{
  "mode": "commit",
  "timestamp_utc": "...",
  "stores": {
    "ROA": {"abbr": "ROA", "result": [{"name": "Stock Assets - ROA", "account_number": "...", "status": "created"}, ...]},
    ...
  },
  "errors": [],
  "total_created": <N>,
  "total_existed": <N>,
  "total_errors": 0
}
```

**MUST_MODIFY:** `output/s243/verification/seed_ledger.json`
**MUST_CONTAIN:** `"mode": "commit"`, `"total_errors": 0`, all 4 abbrs

**3-T2** Re-probe account inventory for all 4 target stores. Run the same probe shape as Phase 0-T4 but post-seed. Write `output/s243/verification/after_state.json`. Compare to `before_state.json`:
- `total_accounts` increased by exactly the number of accounts created per store (per the ledger)
- `group_accounts` increased correspondingly
- `leaf_accounts` UNCHANGED (we only created groups)
- Pre-existing groups (`1100000 - ASSETS - <ABBR>`, `2104000 - INTERCOMPANY PAYABLES - <ABBR>`) preserved untouched

**MUST_MODIFY:** `output/s243/verification/after_state.json`

**3-T3** Re-run the S238 Phase 0-T4 CoA-completeness probe pattern (the `_find_parent_group_for(company, "Stock Assets")` etc. pattern from `tmp/s238/probe_phase0_state.py`). Verify the 4 stores now resolve all 3 parent groups. Write `output/s243/verification/coa_complete_count.json`:
```json
{
  "checked_stores": 49,
  "complete_stores": 49,
  "incomplete_stores": [],
  "per_store_resolution": {
    "ROBINSONS ANTIPOLO - BEBANG ENTERPRISE INC.": {
      "stock_assets_parent": "Stock Assets - ROA",
      "ap_parent": "Accounts Payable - ROA",
      "current_assets_parent": "Current Assets - ROA"
    },
    ...
  }
}
```

**MUST_MODIFY:** `output/s243/verification/coa_complete_count.json`
**MUST_CONTAIN:** `"complete_stores": 49`, `"incomplete_stores": []`, all 49 store keys

**3-T4** **HARD BLOCKER:** if `complete_stores != 49` or `incomplete_stores` is non-empty after seeder commit, STOP. The seeder didn't fully close the gap. Investigate (Phase 1 gap analysis may have missed parent-chain ancestors).

**Phase 3 verify:**
```python
import json, sys
errs = []
ledger = json.load(open("output/s243/verification/seed_ledger.json"))
if ledger.get("total_errors", 1) != 0: errs.append(f"seeder had errors: {ledger.get('errors')}")
counts = json.load(open("output/s243/verification/coa_complete_count.json"))
if counts.get("complete_stores") != 49: errs.append(f"only {counts.get('complete_stores')} stores complete (expected 49)")
if counts.get("incomplete_stores"): errs.append(f"still incomplete: {counts['incomplete_stores']}")
print("PASS" if not errs else "\n".join(errs))
sys.exit(0 if not errs else 1)
```

---

### Phase 4 — Closeout (3 units)

**4-T1** Run canonical post-check:
```bash
python scripts/verify_canonical_structure.py 2>&1 | tee output/s243/verification/canonical_post_check.log
```
Must show `ALL CANONICAL` (same baseline as Phase 0). If new violations, STOP — the seeder introduced drift.

**4-T2** Update plan YAML metadata in this file:
- `status: PLANNED` → `status: COMPLETED`
- Add `completed_date: 2026-05-XX`
- Add `pr: <PR#>`
- Add `execution_summary: <one-paragraph result>`

Update `docs/plans/SPRINT_REGISTRY.md` S243 row:
- Status: `PLANNED` → `COMPLETED`
- PR field filled
- Execution summary appended

`git add -f` for both files (docs/ is gitignored).

**4-T3** Write `output/s243/SUMMARY.md` with:
- Pre-state vs post-state comparison (account counts per store, before/after diff)
- Number of accounts created (total + per-store)
- Confirmation that `complete_stores: 49` post-seed
- Reference to `output/s243/verification/seed_ledger.json` for the full audit trail
- Note: 42 historical Submitted BKI SIs (₱483K) on these 4 stores remain WITHOUT a store-side PI mirror — that's a separate Q1 Input VAT recovery sprint, not S243's scope.
- Note: S238 Phase 0-T4 gate is now unblocked — agent can resume S238 from Phase 0-T1 in a fresh session.

**4-T4** Create PR:
```bash
GH_TOKEN="" gh pr create --repo Bebang-Enterprise-Inc/hrms \
  --base production --head s243-canonical-coa-4-stores \
  --title "S243: Canonical CoA Backfill — 4 BEBANG ENTERPRISE INC. Stores" \
  --body "$(cat output/s243/SUMMARY.md)"
```

**4-T5** Worktree exit clean:
```bash
cd F:/Dropbox/Projects/BEI-ERP-s243-canonical-coa-4-stores
git status --short    # must be clean
cd F:/Dropbox/Projects/BEI-ERP
git worktree remove F:/Dropbox/Projects/BEI-ERP-s243-canonical-coa-4-stores
```

**Phase 4 verify:**
```python
import os, json, sys, re
errs = []
for f in [
    "output/s243/SUMMARY.md",
    "output/s243/verification/canonical_post_check.log",
]:
    if not os.path.exists(f): errs.append(f"MISSING: {f}")
log = open("output/s243/verification/canonical_post_check.log", encoding="utf-8", errors="replace").read()
if "ALL CANONICAL" not in log: errs.append("post-check not clean")
plan = open("docs/plans/2026-05-09-sprint-243-canonical-coa-4-stores.md", encoding="utf-8").read()
if "status: COMPLETED" not in plan: errs.append("plan YAML status not updated to COMPLETED")
print("PASS" if not errs else "\n".join(errs))
sys.exit(0 if not errs else 1)
```

---

## Phase Budget Contract

| Phase | Units | Notes |
|---|---:|---|
| Phase 0 — Boot, preflight, pre-state probe | 4 | Worktree confirm + canonical preflight + 4-store before_state |
| Phase 1 — Reference mapping & gap analysis | 5 | XMM probe + comparison + gap JSON + HARD BLOCKER eval |
| Phase 2 — Seeder script + dry-run | 6 | Script writing + dry-run on 1 store + dry-run on all 4 + rollback proof |
| Phase 3 — Apply seeder + verify | 4 | Commit-mode seed + after-state probe + coa_complete_count probe |
| Phase 4 — Closeout | 3 | Post-check + SUMMARY + plan/registry update + PR + worktree remove |
| **Total** | **22** | well under 80-unit ceiling; no phase exceeds 12-unit preferred-split threshold |

---

## Surface Ownership Matrix (S087)

| Surface | Owner | Allowed mutations |
|---|---|---|
| `scripts/s243/seed_canonical_coa_for_4_stores.py` | S243 | NEW file |
| `tmp/s243/run_seeder.py` | S243 | NEW (transient — gitignored, SSM execution wrapper) |
| `tabAccount` (4 target Companies only) | S243 | INSERT — group accounts only (`is_group=1`); strictly scoped to ROA/SMM/SMMM/SMS |
| `output/s243/verification/*.json` | S243 | NEW evidence files |
| `output/s243/SUMMARY.md` | S243 | NEW closeout summary |
| `docs/plans/2026-05-09-sprint-243-canonical-coa-4-stores.md` | S243 | UPDATE (closeout YAML) |
| `docs/plans/SPRINT_REGISTRY.md` | S243 | UPDATE (S243 row + Next Sprint Reservation bump to S244) |
| `tabCompany` / `tabWarehouse` / `tabCustomer` / `tabSupplier` | NOT S243 | UNCHANGED |
| `tabAccount` (45 complete stores OR BEBANG KITCHEN INC. OR BEBANG ENTERPRISE INC. parent) | NOT S243 | UNCHANGED |
| `tabAccount` leaf accounts on the 4 target stores | NOT S243 (S238's job) | UNCHANGED |
| `hrms/api/*.py` | NOT S243 | UNCHANGED |
| `hrms/utils/*.py` | NOT S243 | UNCHANGED |
| `hrms/on_demand/s206_seed_intercompany_accounts.py` | NOT S243 (referenced as pattern only) | UNCHANGED |
| Existing 42 BKI SIs to these 4 stores | NOT S243 (separate VAT recovery sprint) | UNCHANGED |

---

## Anti-Rewind / Concurrent-Run Protection

- **protected_surfaces:**
  - 49 per-store billing Customers — UNCHANGED
  - 45 complete stores' CoAs — UNCHANGED
  - 4 target stores' EXISTING accounts (`1100000 - ASSETS - <ABBR>`, `2104000 - INTERCOMPANY PAYABLES - <ABBR>`, default root accounts) — UNCHANGED (only NEW accounts added)
  - All Sales Invoices, Purchase Invoices, GL Entries, Stock Ledger Entries — UNCHANGED
  - Canonical Rules 1-8 — UNCHANGED
- **remote_truth_baseline:** `tmp/s243/remote_truth_baseline_hrms.sha`
- **pretouch_backup:** none required (insert-only operation; no UPDATE/DELETE on existing records)
- **supersession_map:** S238 Phase 0-T4 gate becomes UNBLOCKED post-S243; S238 can resume.

---

## Requirements Regression Checklist

Before calling this sprint COMPLETED, verify:

- [ ] Canonical preflight passed pre-execute (Phase 0)
- [ ] Canonical preflight passed post-execute (Phase 4)
- [ ] No new canonical violations introduced
- [ ] Only the 4 named target Companies received account inserts
- [ ] All inserted accounts have `is_group=1` (no leaf accounts created)
- [ ] All inserted accounts follow `<canonical group name> - <ABBR>` naming pattern
- [ ] Pre-existing accounts on the 4 target stores preserved untouched (no UPDATE, no DELETE, no rename)
- [ ] No accounts created on any of the 45 complete stores
- [ ] No accounts created on `BEBANG KITCHEN INC.`, `BEBANG ENTERPRISE INC.`, or any parent legal entity
- [ ] `tabCompany`, `tabWarehouse`, `tabCustomer`, `tabSupplier` unchanged
- [ ] No SI / PI / GL / SLE mutations
- [ ] `coa_complete_count: 49 / 49` post-seed
- [ ] S238 `_find_parent_group_for(company, "Stock Assets")` returns non-null for all 4 target stores post-seed
- [ ] Same for `Accounts Payable` and `Current Assets` parent lookups
- [ ] Plan YAML status updated to COMPLETED
- [ ] SPRINT_REGISTRY.md S243 row updated to COMPLETED + PR# filled
- [ ] PR opened and number recorded
- [ ] Worktree removed clean

### HARD BLOCKERS (must STOP, do not proceed)

- [ ] **HB-1:** Phase 0 canonical preflight fails. Root-cause before any Phase 1 work.
- [ ] **HB-2:** Phase 1 gap analysis finds >4 group accounts needed per store. Wider scope than expected — present to Sam for decision.
- [ ] **HB-3:** Phase 1 finds XMM's account_number scheme conflicts with target stores' existing accounts. Naming/numbering reconciliation needed before proceeding.
- [ ] **HB-4:** Phase 2 dry-run rollback fails (post-dry-run state != pre-state). Seeder bug; do NOT proceed to commit-mode.
- [ ] **HB-5:** Phase 3 seeder reports `total_errors > 0`. Investigate, do NOT mark complete.
- [ ] **HB-6:** Phase 3 `coa_complete_count != 49` after seed. Phase 1 missed something; do NOT close out.
- [ ] **HB-7:** Phase 4 canonical post-check shows new violations vs pre-execute baseline. Roll back the change before merging.

### Forbidden agent behaviors (per S154 Zero-Skip rule)

- [ ] Skipping a HARD BLOCKER silently
- [ ] Marking partial work as "done"
- [ ] Auto-creating accounts on Companies outside the 4-store target list
- [ ] Creating leaf accounts (S238's job, not S243's)
- [ ] Renaming or deleting any pre-existing account on the 4 stores
- [ ] Modifying `_find_parent_group()` patterns in `s206_seed_intercompany_accounts.py` to "fix" the gap (the fix is data, not pattern)
- [ ] Bypassing the savepoint+ledger pattern for "speed"
- [ ] Saying "deferred to next sprint" for any Phase 1-4 task

---

## Autonomous Execution Contract

- **completion_condition:**
  - All 5 phases complete with verify scripts PASS
  - 4 stores have `coa_complete_count: 49` post-seed
  - Canonical post-check `ALL CANONICAL`
  - Plan YAML + SPRINT_REGISTRY.md updated and pushed
  - PR created
  - Worktree removed clean
- **stop_only_for:**
  - HB-1..HB-7 (HARD BLOCKERS above)
  - Canonical preflight returns violations (pre or post)
  - SSM access fails (no recovery path)
  - Three failed attempts at the same seeder step
  - Sam explicitly requests halt
- **continue_without_pause_through:**
  - All 5 phases end-to-end → PR creation → closeout
- **blocker_policy:**
  - Frappe ORM insert fails on a single account → check parent_account exists, retry with corrected hierarchy
  - SSM execution times out → re-run with TimeoutSeconds increased
  - 3 consecutive seeder failures on same account → STOP and reassess
- **signoff_authority:** `single-owner` (Sam)
- **canonical_closeout_artifacts:**
  - `output/s243/SUMMARY.md`
  - `output/s243/verification/before_state.json`
  - `output/s243/verification/reference_xmm_coa.json`
  - `output/s243/verification/coa_gap_analysis.json`
  - `output/s243/verification/seed_dry_run_report.json`
  - `output/s243/verification/after_state.json`
  - `output/s243/verification/seed_ledger.json`
  - `output/s243/verification/canonical_post_check.log`
  - `output/s243/verification/coa_complete_count.json`
  - `docs/plans/2026-05-09-sprint-243-canonical-coa-4-stores.md` (status COMPLETED)
  - `docs/plans/SPRINT_REGISTRY.md` (S243 row → COMPLETED)

---

## Status Reconciliation Contract

Whenever counts, blockers, stage, or status changes, update in the same work unit:
1. `output/s243/SUMMARY.md`
2. plan YAML status line
3. `SPRINT_REGISTRY.md` S243 row
4. `output/s243/verification/*.json` files
5. seed_ledger.json
6. canonical post-check log

---

## Signoff Model

- **mode:** `single-owner`
- **approver_of_record:** Sam Karazi (CEO) — CFO seat vacant indefinitely per 2026-05-07 update to DECISIONS.md
- **signoff_artifact:** `output/s243/SUMMARY.md`
- **note:** Sam approved the architecture in conversation 2026-05-08-09 (chose Option 1 from S238 HARD_STOP triage). No further sign-off needed during execution unless one of the `stop_only_for` conditions trips.

---

## Ground-Truth Lock

- **evidence_sources:**
  - `tmp/s238/phase0_probe_result.json` → S238 Phase 0 probe identifying `coa_survey_complete_count: 45/49`
  - `tmp/s238/followup_4stores_result.json` → group-account inventory for the 4 target stores
  - `tmp/s238/followup2_si_activity.json` → 42 Submitted BKI SIs / ₱483K total
  - `tmp/s238/HARD_STOP_phase0_4stores_coa_gap.md` → full incident analysis + 3-option triage
  - `data/_CLEANROOM/2026-04-09_s175_coa_restructure/01_CANONICAL_COA_TEMPLATE.md` → canonical CoA shape reference
  - `hrms/on_demand/s206_seed_intercompany_accounts.py` → reference seeder pattern (`_find_parent_group` line 90, `_ensure_account` line 194, savepoint pattern)
  - `scripts/verify_canonical_structure.py` → canonical preflight + post-check verifier
- **count_method:**
  - **`coa_complete_count`** — for each store, run `_find_parent_group_for(company, pattern)` for each of `("Stock Assets", "Accounts Payable", "Current Assets")`. A store is "complete" iff all 3 lookups return non-null. Method: `tabAccount` LIKE search by `account_name` pattern, fallback to `is_group=1 AND account_name=pattern`.
  - **`bki_si_total`** — `SELECT COUNT(*) FROM tabSales Invoice WHERE company='BEBANG KITCHEN INC.' AND customer=<billing_customer>` per store, grouped by docstatus.
  - **`accounts_created`** — count of rows in `output/s243/verification/seed_ledger.json` `stores[*].result[*]` with `status='created'`.
- **authoritative_sections:**
  - Phases 0-4 task tables are authoritative for execution.
  - Audit/amendment history (this section + future amendments) is traceability only.
- **normalization_required:**
  - any amendment that changes counts, target stores, or seed list must update Phase 1-T2 gap analysis + Surface Ownership Matrix + Phase Budget Contract in the same edit
- **unresolved_value_policy:**
  - Phase 1's `groups_to_create` per store is data-driven from XMM reference probe — should never be `[UNVERIFIED]`. If Phase 1 cannot determine the gap deterministically, that's HB-3 (HARD BLOCKER), not unresolved data.

---

## Execution Skills Reference

- Spawn worktree (already done at plan creation; Phase 0-T2 confirms): `.claude/rules/worktree-isolation.md`
- SSM execution: `/frappe-bulk-edits` skill
- Canonical verifier: `python scripts/verify_canonical_structure.py`
- Backend deploy: NOT NEEDED — this sprint creates only data, no code paths to deploy
- Reference seeder: `hrms/on_demand/s206_seed_intercompany_accounts.py`

---

## Sprint Registry Row (Evidence of Lock)

```
| `S243` | Sprint 243 | `s243-canonical-coa-4-stores` (hrms — `scripts/s243/seed_canonical_coa_for_4_stores.py` + per-store `tabAccount` group inserts) | TBD | PLANNED 2026-05-09 — Canonical CoA Backfill (4 BEBANG ENTERPRISE INC. stores) to unblock S238 Phase 0-T4. ~22 work units. | `docs/plans/2026-05-09-sprint-243-canonical-coa-4-stores.md` |
```

(Row added to `docs/plans/SPRINT_REGISTRY.md` in same commit as this plan; Next Sprint Reservation bumped from S242 → S244.)

---

## Execution Authority

This sprint is intended for autonomous end-to-end execution by a single agent in a single session.
Do not stop for progress-only updates.
Only pause for items listed in the Autonomous Execution Contract `stop_only_for` section above.

Total budget: 22 units. Single-session executable. Sam has pre-approved the architecture (Option 1 chosen from S238 HARD_STOP triage 2026-05-08-09); no Phase-0 decision gate needed.

---

## Out of Scope (Explicit)

The following are NOT in S243's scope. Each may warrant its own future sprint:

1. **Q1 Input VAT recovery for the 42 historical Submitted BKI SIs (₱483K) on these 4 stores.** S238's PI generator hooks `Sales Invoice on_submit` — it does NOT create PIs for already-Submitted historical SIs. A separate sprint would need to retroactively create Draft PIs (or Journal Vouchers) for the 42 historical SIs to claim the input VAT. Note in closeout SUMMARY for ph-finance follow-up.
2. **Full canonical CoA harmonization for the 4 stores (Sales tree, COGS, Expense, Equity hierarchy).** S243 only creates the 3-4 group accounts S238 needs. The 4 stores still won't have a `4000000 SALES` tree, COGS accounts, or Expense hierarchy after S243. Future sprint when these stores need to post Sales (e.g., Mosaic POS revenue recognition).
3. **Investigate why 4 stores were created with skeleton CoA on 2026-04-13.** Root-cause analysis of which canonical-seeder script was bypassed or never ran. Out of scope for the fix; in scope for a separate post-mortem if Sam decides to pursue.
4. **Backfill S238 Phase 1 leaf accounts to these 4 stores.** That's S238's job once it resumes after S243 ships.
