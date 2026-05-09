---
sprint_id: S243
sprint_title: Canonical CoA Backfill — 4 BEBANG ENTERPRISE INC. Stores
plan_branch: s243-canonical-coa-4-stores
status: COMPLETED
version: 1.1
created_date: 2026-05-09
revised_date: 2026-05-09
completed_date: 2026-05-09
audit_pr: 735
pr: 735
canonical_scope: in
canonical_model_reference: docs/STORE_COMPANY_CANONICAL.md
canonical_preflight: required
depends_on: none
unblocks: S238 (Phase 0-T4 CoA-completeness gate)
execution_summary: |
  S243 v1.1 executed end-to-end 2026-05-09 in worktree
  F:/Dropbox/Projects/BEI-ERP-s243-execute on branch s243-canonical-coa-4-stores.
  All 5 phases complete: 12 group accounts created (3 per store * 4 stores)
  using BARE-NAME convention. coa_complete_count post-seed: 49/49.
  Canonical post-check ALL CANONICAL (0 new violations vs pre-execute baseline).
  S238 Phase 0-T4 gate unblocked.
  Iteration finding: AP could not be parented to NULL (Frappe rejects 2nd
  Liability root); parented to existing 2104000 - INTERCOMPANY PAYABLES - <ABBR>
  instead. Follow-up sprint candidate logged for full canonical CoA
  harmonization + verify_canonical_structure.py CoA-completeness extension.
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
  | `S243` | Sprint 243 | `s243-canonical-coa-4-stores` | #735 | PLANNED_AUDITED_v1_1 2026-05-09 — Canonical CoA Backfill (4 BEBANG ENTERPRISE INC. stores) to unblock S238 Phase 0-T4. v1.1 = 8 CRITICAL audit fixes applied (BARE-NAME canonical, ignore_root_company_validation flag, account_name shape, dry-run outer savepoint, evidence regen, Phase 4 gates, PR checklist). ~24 work units. | `docs/plans/2026-05-09-sprint-243-canonical-coa-4-stores.md` |
---

# S243 — Canonical CoA Backfill — 4 BEBANG ENTERPRISE INC. Stores (v1.1 — Audited)

> **Canonical model reference:** `docs/STORE_COMPANY_CANONICAL.md`
> **Unblocks:** S238 Phase 0-T4 CoA-completeness gate.

---

## v1 → v1.1 Audit Amendments (2026-05-09)

`/audit-plan-bei-erp` ran 7 parallel domain auditors + code verifier + adversarial fact-checker on v1 (PR #735). 8 CRITICAL blockers + 10 WARNINGs surfaced. 0 hallucinations detected by adversarial fact-check. Full audit evidence: `output/plan-audit/s243-canonical-coa-4-stores/{frappe-backend,ph-finance,deployment-qa,system-arch,zero-skip,cold-start,team-orchestration}_findings.md` + `code_verification.md` + `fact_check_verification.md` + `verified_blockers.md`.

**v1.1 applies the 8 CRITICAL fixes WITHOUT changing scope.** Architectural goal is preserved exactly: targeted seeder, 4 named target Companies, group accounts only, no leaf accounts, no other surface mutations. The amendments are correctness fixes within that scope.

### CRITICAL fixes applied (8)

| # | v1 Bug | v1.1 Fix |
|---|---|---|
| **B1** | Plan picked XMM as canonical reference. Code-verifier cross-check of `tmp/s238/phase0_probe_result.json` showed XMM is a 2/45 outlier for AP and Current Assets parents (uses number-prefix style). 43 of 45 complete stores use BARE-NAME convention (`Stock Assets - <ABBR>`, `Accounts Payable - <ABBR>`, `Current Assets - <ABBR>` with `account_number = NULL`, Title Case). XMM-style would propagate the minority convention. | Adopt **43-store BARE-NAME convention** as canonical. Phase 1-T1 reference probe samples 5 stores from `{AMM, AFT, AYEVO, UPTC, AYSOL}` (all bare-name), not XMM. Phase 1-T2 example sets `account_name = "Stock Assets"` (BARE), `account_number = NULL`. The `1100000` collision panic dissolves automatically. |
| **B2** | `ignore_root_company_validation` flag missing. s206 sets it at line 358 because every Frappe `Account.insert()` on a child Company throws "Please add the account to root level Company" without it. All 4 target stores have `parent_company = "BEBANG ENTERPRISE INC."`. | Phase 2-T1 helper wraps the per-Company loop with `frappe.local.flags.ignore_root_company_validation = True` (restored on exit). Pattern mirrors s206 lines 358-359 + 452. |
| **B3** | Phase 1-T2 example set `account_name = "Stock Assets - ROA"` (docname shape). Frappe stores `account_name` BARE; abbr is only on `name` column. Phase 3-T3 verification probe queries `account_name = "Stock Assets"` (exact match), so v1 example would break the verifier. Verified in `tmp/s238/followup_4stores_result.json` lines 11-12 (`"name": "1100000 - ASSETS - ROA"`, `"account_name": "1100000 - ASSETS"`). | Phase 1-T2 example explicitly distinguishes `account_name` (BARE = `"Stock Assets"`) from `name` (docname = `"Stock Assets - ROA"`, auto-constructed by Frappe). Phase 2-T1 helper passes `account_name` BARE to `frappe.get_doc()`. |
| **B4** | Dry-run rollback ambiguous. s206's per-company `frappe.db.savepoint(sp)` + `release_savepoint(sp)` then outer `frappe.db.commit()` pattern doesn't roll back; releases are markers, not commits, but the outer commit persists everything. Plan said "ROLLBACK savepoint" without specifying which. Phase 2-T5 verification (post-dry-run state == pre-state) would fail. | Phase 2-T3 specifies dry-run = wrap entire loop in OUTER savepoint `s243_dry_run_outer`, run per-company inserts, **skip the outer `frappe.db.commit()`**, issue `frappe.db.rollback(save_point=s243_dry_run_outer)` at end. Commit-mode = same flow but with outer commit at end. |
| **B5** | `tmp/s238/*` evidence files cited 5+ times but `tmp/` is gitignored — files exist only in main checkout, NOT in worktree. | Phase 0-T4 expanded: agent **regenerates** the probes inline by running `tmp/s238/probe_phase0_state.py` and `tmp/s238/probe_4_incomplete_stores.py` patterns via SSM as part of S243 Phase 0. Evidence written to `tmp/s243/probe_*.json` (worktree-local). Plan body now refers to `tmp/s243/` paths, not `tmp/s238/`. |
| **B6** | Phase 4-T3 SUMMARY.md had no MUST_MODIFY/MUST_CONTAIN gate. Phase 4 verify only checked `os.path.exists` — could be 1 byte and pass. Asymmetric with Phases 0-3. | Phase 4-T3 adds MUST_MODIFY + MUST_CONTAIN gates symmetric to Phases 0-3. SUMMARY.md must contain the Requirements Regression Checklist as a PASS/FAIL table (each check ✓ or ✗). |
| **B7** | PR description = `cat SUMMARY.md` with no task-by-task gate. Requirements Regression Checklist existed in plan body but wasn't enforced as PR content. | Phase 4-T3 requires Requirements Regression Checklist embedded in SUMMARY.md as PASS/FAIL table. Phase 4-T4 PR body includes it via `cat SUMMARY.md`. Phase 4 verify confirms the table is present. |
| **B8** | Canonical verifier blind to CoA-completeness gap. `scripts/verify_canonical_structure.py` checks Company/Warehouse/Customer identity but never `tabAccount` completeness. Same skeleton-CoA bug fires next time a per-store Company is created. | **OUT OF SCOPE for S243** (avoid scope-creep into architectural change). Closeout SUMMARY records this as a follow-up sprint candidate (S244 or later) so it's not lost. The recurrence prevention angle is documented; S243 stays focused on the 4-store fix. |

### WARNINGs applied

- **W5 (rebase-before-push)**: Phase 4 adds `git fetch origin --prune && git rebase origin/production` step before push.
- **W6 (`git add -f output/`)**: Phase 4-T2 includes `git add -f output/s243/` to stage gitignored evidence files.
- **W1 (idempotency check key)**: Phase 2-T1 helper specifies `frappe.db.exists("Account", final_docname)` where `final_docname` follows the BARE convention.
- **W2 (topological ordering)**: Phase 2-T1 helper orders `groups_to_create` by parent depth (ancestors first).
- **W4 (account dict shape)**: Phase 2-T1 helper enumerates the exact dict passed to `frappe.get_doc({})` (no `account_type` for groups; `account_currency = "PHP"`).

### Findings dropped as STALE / FALSE POSITIVE (4)

- **CS-5** (savepoint API claim) — STALE: s206 uses real `frappe.db.savepoint()` API. Plan's MUST_CONTAIN `"frappe.db.savepoint"` is correct.
- **TO-W2** (probe filename) — STALE: file `probe_4_incomplete_stores.py` exists at `F:\Dropbox\Projects\BEI-ERP\tmp\s238\probe_4_incomplete_stores.py`.
- **DQ-9** — duplicate of FB-12 (frappe.log_error).
- **SA-9** — `bki_sales_naming_series` change is S238's surface, not S243's.

### Findings DOWNGRADED to WARNING (3)

- **B5 (`_ensure_account` is_group=0)** — mitigated: plan's MUST_CONTAIN requires NEW helper `_ensure_group_account`; plan body now explicitly says "do NOT call s206's `_ensure_account` directly".
- **B7 (`frappe-bulk-edits` not in worktree)** — mitigated: Skill tool registry surfaces it globally; plan now says "invoke `Skill(skill='frappe-bulk-edits')` not `Read` of file path".
- **B8 (SSM boilerplate not inlined)** — mitigated: plan now explicitly inlines the 4 log-dir creation pattern in Phase 2-T1.

### Phase budget impact

| Phase | v1 | v1.1 | Δ rationale |
|---|---:|---:|---|
| Phase 0 — Boot, preflight, pre-state probe | 4 | 5 | +1: regenerate `tmp/s238` evidence as `tmp/s243/probe_*.json` (B5) |
| Phase 1 — Reference mapping & gap analysis | 5 | 5 | unchanged (sample 5 BARE-NAME stores instead of just XMM) |
| Phase 2 — Seeder + dry-run + rollback proof | 6 | 8 | +2: inline SSM boilerplate, `ignore_root_company_validation` flag wrapping, outer-savepoint scoping for dry-run, exact dict shape (W1, W2, W4, B2, B4) |
| Phase 3 — Commit-mode seed + 49/49 verify | 4 | 4 | unchanged |
| Phase 4 — Closeout + PR | 3 | 4 | +1: SUMMARY.md MUST_MODIFY/MUST_CONTAIN gates, Requirements Regression Checklist PASS/FAIL embed, rebase-before-push, `git add -f output/` (B6, B7, W5, W6) |
| **Total** | **22** | **26** | **+4 units (8 CRITICAL fixes + 5 WARNINGs)** |

26 units — well under 80-unit ceiling. No phase exceeds 12-unit preferred-split threshold. Single-session executable.

### One v1 finding REFUTED by adversarial fact-check (Blocker 1 framing)

The fact-checker noted Blocker 1's framing was slightly overstated: XMM is **not** an outlier for `Stock Assets` parent (XMM uses bare `Stock Assets - XMM` matching all 45 stores). XMM is an outlier ONLY for `Accounts Payable` and `Current Assets` parents (uses number-prefix where 43 others use bare). ROBDA shares the same outlier pattern. The substance — that the plan's "match XMM exactly" rule would propagate the minority convention to AP and Current Assets — stands. The v1.1 amendment uses the dominant 43-store BARE-NAME convention for ALL three groups (Stock Assets, Accounts Payable, Current Assets) on the 4 target stores.

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

### Phase 0 — Boot, Worktree Confirm, Canonical Preflight, Pre-State Probe (5 units — v1.1)

**0-T1 (v1.1)** Read this plan fully — including the v1 → v1.1 Audit Amendments section above. **Do NOT read** `data/_CLEANROOM/2026-04-09_s175_coa_restructure/01_CANONICAL_COA_TEMPLATE.md` for canonical reference (audit W7: that file is the S175 Sales-tree template; it does not define `Stock Assets` / `Accounts Payable` / `Current Assets` group structure). The canonical reference for this sprint is **the existing 43 bare-name complete stores in production**, sampled in Phase 1-T1.

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

**0-T4 (v1.1)** Probe full account inventory for the 4 target stores via SSM and write `output/s243/verification/before_state.json`. **HARD BLOCKER (audit B5):** the plan body originally cited `tmp/s238/probe_4_incomplete_stores.py` and `tmp/s238/phase0_probe_result.json` as starting evidence — those files exist only in the main checkout (`F:/Dropbox/Projects/BEI-ERP/tmp/s238/`), NOT in this worktree. **DO NOT** attempt to read them via relative paths. Instead, **regenerate** the probes as part of S243 Phase 0:

1. Author `tmp/s243/probe_phase0_state.py` (NEW — clone-and-adapt the s238 pattern). Required behavior:
   - Frappe init boilerplate: create 4 log directories (`/home/frappe/logs`, `/home/frappe/frappe-bench/logs`, `/home/frappe/frappe-bench/hq.bebang.ph/logs`, `/home/frappe/frappe-bench/sites/hq.bebang.ph/logs`) BEFORE `import frappe`.
   - For each of 4 target stores: query all `tabAccount` rows (group + leaf), `parent_company` from `tabCompany`, billing Customer name, Warehouse list, BKI SI counts (`tabSales Invoice WHERE company='BEBANG KITCHEN INC.' AND customer=<billing_customer>`).
   - Emit between `S243_PHASE0_BEGIN` / `S243_PHASE0_END` markers.

2. SSM-execute via `Skill(skill='frappe-bulk-edits')` pattern (NOT `Read` of skill file path). Capture log to `tmp/s243/phase0_probe_run.log`.

3. Parse output to `output/s243/verification/before_state.json`.

**MUST_MODIFY:** `tmp/s243/probe_phase0_state.py` (NEW), `output/s243/verification/before_state.json`
**MUST_CONTAIN (in before_state.json):** `"ROBINSONS ANTIPOLO"`, `"SM MANILA"`, `"SM MEGAMALL"`, `"SM SOUTHMALL"`, `"all_group_accounts"`, `"total_accounts"`, `"abbr"`, `"parent_company"`, `"BKI_si_counts"`
**MUST_CONTAIN (in probe_phase0_state.py):** `os.makedirs`, `frappe.init`, `frappe.connect`, `S243_PHASE0_BEGIN`, all 4 target store names

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

### Phase 1 — Reference Mapping & Gap Analysis (5 units — v1.1: BARE-NAME convention)

**1-T1 (v1.1 — REPLACES "XMM probe")** Sample 5 BARE-NAME complete stores as canonical reference (NOT XMM). Per audit B1 + adversarial fact-check: 43 of 45 complete stores use the bare-name convention (`Stock Assets - <ABBR>`, `Accounts Payable - <ABBR>`, `Current Assets - <ABBR>` with `account_number = NULL`, Title Case). XMM and ROBDA are the 2/45 outliers (use number-prefix style for AP and Current Assets). The dominant bare-name pattern is canonical.

Sample 5 of these stores: `AMM`, `AFT`, `AYEVO`, `UPTC`, `AYSOL` (any 5 from the 43 will work; if any is unavailable, substitute another BARE-NAME store from `before_state.json`'s implied universe).

For each sampled store, probe its full `tabAccount` rows via SSM. Write `output/s243/verification/reference_bare_name_coa.json`:
- For each sampled store: all `tabAccount` rows where `is_group=1` (only group accounts, that's all S243 needs)
- Confirm convention is consistent: `account_name` BARE (no abbr), `account_number` NULL or matching the existing target-store pattern, Title Case naming

**MUST_MODIFY:** `output/s243/verification/reference_bare_name_coa.json`
**MUST_CONTAIN:** `"Stock Assets"`, `"Current Assets"`, `"Accounts Payable"`, all 5 sampled abbreviations, `"groups_by_root_type"`, `"convention_consistent": true`

If `convention_consistent` is false (i.e., the 5 sampled stores disagree among themselves), STOP — present to Sam with the disagreement detail.

**1-T2 (v1.1)** Build the gap-analysis: compare each of the 4 incomplete stores against the BARE-NAME canonical convention. For each `(target_store, missing_group)`, compute the exact group account to create.

Output: `output/s243/verification/coa_gap_analysis.json`:
```json
{
  "ROA": {
    "abbr": "ROA",
    "existing_group_count": 2,
    "groups_to_create": [
      {
        "account_name": "Stock Assets",
        "account_number": null,
        "parent_account": "1100000 - ASSETS - ROA",
        "root_type": "Asset",
        "is_group": 1,
        "expected_docname": "Stock Assets - ROA",
        "rationale": "S238 Phase 1-T1 needs this parent for Inventory-from-Commissary leaf; reuses target-store's existing Asset root"
      },
      {
        "account_name": "Current Assets",
        "account_number": null,
        "parent_account": "1100000 - ASSETS - ROA",
        "root_type": "Asset",
        "is_group": 1,
        "expected_docname": "Current Assets - ROA",
        "rationale": "S238 Phase 1-T1 needs this parent for Input VAT - BKI Inter-Co leaf"
      },
      {
        "account_name": "Accounts Payable",
        "account_number": null,
        "parent_account": "<existing root liability group on ROA, e.g. '2 - Liability - ROA' if Frappe-default exists, OR '2104000 - INTERCOMPANY PAYABLES - ROA' as fallback>",
        "root_type": "Liability",
        "is_group": 1,
        "expected_docname": "Accounts Payable - ROA",
        "rationale": "S238 Phase 1-T1 needs this parent for AP-Trade-BKI leaf"
      }
    ]
  }
}
```

**Critical convention notes (audit B3 fix):**
- `account_name` = BARE (e.g., `"Stock Assets"`, no abbr suffix). Frappe stores `account_name` BARE; abbr is on `name` only.
- `account_number = NULL` (BARE-NAME convention has no number prefix).
- `expected_docname` = `"<account_name> - <abbr>"` — Frappe auto-constructs this on insert from `account_name` + Company.abbr.
- `parent_account` for `Stock Assets` and `Current Assets` reuses the target store's EXISTING `1100000 - ASSETS - <ABBR>` Asset root group (visible in `before_state.json`).
- `parent_account` for `Accounts Payable` uses the target store's existing root Liability group (probe `before_state.json` to determine name; typical shape `"2 - Liability - <ABBR>"` or `"2104000 - INTERCOMPANY PAYABLES - <ABBR>"`).

**1-T3 (v1.1)** **HARD BLOCKER:** STOP and present to Sam if any of these conditions are true:
1. The gap analysis suggests creating MORE than 4 group accounts per store. Means the gap is wider than expected; needs scope discussion.
2. The 5 sampled BARE-NAME stores' conventions disagree among themselves (1-T1's `convention_consistent` is false).
3. A target store has NO root Liability group at all (i.e., `Accounts Payable`'s `parent_account` cannot be resolved from `before_state.json`). Means we need to create the root Liability group first; quantify and decide.
4. A `groups_to_create` entry would conflict on `expected_docname` with an existing account on that target store. (Should not happen with BARE-NAME convention since target stores' existing accounts use number-prefix style — but check defensively.)

**1-T4** Write summary of gap to conversation + present to Sam if any HARD BLOCKER from 1-T3 fires. Otherwise proceed to Phase 2.

**MUST_MODIFY:** `output/s243/verification/coa_gap_analysis.json`
**MUST_CONTAIN:** `"groups_to_create"`, all 4 abbreviations (`"ROA"`, `"SMM"`, `"SMMM"`, `"SMS"`), `"account_name": "Stock Assets"` (BARE — no abbr), `"account_number": null`, `"expected_docname"`, `"is_group": 1`, `"rationale"`

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

### Phase 2 — Seeder Script + Dry-Run (8 units — v1.1)

**2-T1 (v1.1 — full code skeleton, replaces v1 prose)** Write `scripts/s243/seed_canonical_coa_for_4_stores.py` (NEW). All v1 audit fixes (B2, B3, B4, B5/W1/W2/W4) inlined:

```python
#!/usr/bin/env python3
"""S243 — Canonical CoA backfill for 4 BEBANG ENTERPRISE INC. stores.

Adopts the 43-store BARE-NAME convention (audit B1):
  account_name  = "Stock Assets" / "Accounts Payable" / "Current Assets"  (BARE — no abbr)
  account_number = NULL
  is_group = 1
  Frappe constructs name = "<account_name> - <abbr>" automatically

Strictly scoped to 4 target Companies. If asked to create on any other Company,
raises ValueError. No leaf accounts (S238's Phase 1 deliverable).

Audit fixes baked in:
  B2: ignore_root_company_validation flag wraps loop (s206 lines 358-359 pattern)
  B3: account_name passed BARE to frappe.get_doc; abbr handled by Frappe
  B4: outer-savepoint scoping for dry-run mode (skips outer commit on dry-run)
  W1: idempotency check key = frappe.db.exists("Account", expected_docname)
  W2: groups_to_create sorted by parent depth (ancestors first)
  W4: account dict shape enumerated explicitly (no account_type/currency for groups)

Reference pattern (NOT a callable): hrms/on_demand/s206_seed_intercompany_accounts.py.
Do NOT call s206._ensure_account directly — it hardcodes is_group=0 for leaves.
"""
from __future__ import annotations

# v1.1-B5: SSM boilerplate inlined — log dirs MUST exist before import frappe
import os
for _d in [
    "/home/frappe/logs",
    "/home/frappe/frappe-bench/logs",
    "/home/frappe/frappe-bench/hq.bebang.ph/logs",
    "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
]:
    os.makedirs(_d, exist_ok=True)

import json
import sys
import traceback
from datetime import datetime
from pathlib import Path

import frappe  # type: ignore

OUTER_SAVEPOINT = "s243_seed_outer"
GAP_PATH = "output/s243/verification/coa_gap_analysis.json"
LEDGER_PATH = "output/s243/verification/seed_ledger.json"

TARGET_COMPANIES = frozenset({
    "ROBINSONS ANTIPOLO - BEBANG ENTERPRISE INC.",
    "SM MANILA - BEBANG ENTERPRISE INC.",
    "SM MEGAMALL - BEBANG ENTERPRISE INC.",
    "SM SOUTHMALL - BEBANG ENTERPRISE INC.",
})

ALLOWED_ACCOUNT_NAMES = frozenset({
    "Stock Assets",
    "Accounts Payable",
    "Current Assets",
})


def _validate_target_company(company: str) -> None:
    """v1.1-B2 + W4: refuse out-of-scope companies."""
    if company not in TARGET_COMPANIES:
        raise ValueError(
            f"S243: refusing to create accounts on out-of-scope Company {company!r}; "
            f"target list = {sorted(TARGET_COMPANIES)}"
        )


def _validate_gap_entry(entry: dict, company: str) -> None:
    """Anti-scope-creep gates (v1.1-B1)."""
    if entry.get("is_group") != 1:
        raise ValueError(f"S243: only group accounts allowed (is_group=1); got {entry}")
    if entry.get("account_name") not in ALLOWED_ACCOUNT_NAMES:
        raise ValueError(
            f"S243: account_name {entry.get('account_name')!r} not in {sorted(ALLOWED_ACCOUNT_NAMES)}"
        )
    if entry.get("account_number") not in (None, ""):
        raise ValueError(
            f"S243: BARE-NAME convention requires account_number=NULL; got {entry.get('account_number')}"
        )


def _load_gap_analysis() -> dict:
    """v1.1: read + validate Phase 1 gap analysis."""
    gap = json.loads(Path(GAP_PATH).read_text(encoding="utf-8"))
    expected = {"ROA", "SMM", "SMMM", "SMS"}
    if set(gap.keys()) - expected or not expected.issubset(gap.keys()):
        raise ValueError(f"S243: gap analysis abbr keys mismatch; got {sorted(gap.keys())}")
    for abbr, store_data in gap.items():
        if len(store_data.get("groups_to_create", [])) > 4:
            raise ValueError(
                f"S243: {abbr} requests {len(store_data['groups_to_create'])} groups, max=4"
            )
    return gap


def _topological_sort(groups: list[dict]) -> list[dict]:
    """v1.1-W2: order ancestors first (parents before children)."""
    # For S243's 3 group accounts per store, parent_account always references
    # an EXISTING account on the target store (per Phase 1-T2 design).
    # No inter-group dependencies, so input order is fine.
    # Defensive sort: groups with shorter parent_account string first.
    return sorted(groups, key=lambda g: len(g.get("parent_account", "")))


def _ensure_group_account(
    company: str, account_name: str, parent_account: str, root_type: str
) -> tuple[str, str]:
    """Idempotent INSERT for a group account. Returns (docname, status).

    status ∈ {"created", "existed"}. Raises on validation/insert failure.
    """
    abbr = frappe.db.get_value("Company", company, "abbr")
    if not abbr:
        raise ValueError(f"S243: Company {company} has no abbr")
    expected_docname = f"{account_name} - {abbr}"

    # v1.1-W1: idempotency check by docname
    if frappe.db.exists("Account", expected_docname):
        return expected_docname, "existed"

    # v1.1-W4: explicit dict shape — no account_type, no account_currency for groups
    # v1.1-B3: account_name BARE, no abbr suffix; Frappe auto-constructs name from account_name + Company.abbr
    doc = frappe.get_doc({
        "doctype": "Account",
        "account_name": account_name,           # BARE
        "parent_account": parent_account,       # full docname of existing parent
        "company": company,
        "is_group": 1,                          # GROUP ONLY
        "root_type": root_type,                 # Asset / Liability
    })
    doc.insert(ignore_permissions=True)
    if doc.name != expected_docname:
        # Defensive: Frappe may have appended a counter on collision
        raise ValueError(
            f"S243: docname mismatch — expected {expected_docname!r}, got {doc.name!r}"
        )
    return doc.name, "created"


def execute(dry_run: bool = False) -> dict:
    """Main entry. dry_run=True: outer savepoint + skip outer commit + final rollback.
    dry_run=False: outer savepoint + outer commit (release savepoint after).
    """
    frappe.set_user("Administrator")
    gap = _load_gap_analysis()

    ledger: dict = {
        "mode": "dry-run" if dry_run else "commit",
        "timestamp_utc": datetime.utcnow().isoformat() + "Z",
        "stores": {},
        "errors": [],
        "total_created": 0,
        "total_existed": 0,
        "total_errors": 0,
    }

    # v1.1-B2: bypass parent_company root-account validator for child Companies
    original_root_flag = getattr(frappe.local.flags, "ignore_root_company_validation", False)
    frappe.local.flags.ignore_root_company_validation = True

    # v1.1-B4: OUTER savepoint wraps entire 4-store loop
    frappe.db.savepoint(OUTER_SAVEPOINT)

    try:
        for abbr, store_data in gap.items():
            company = store_data["company"]  # full docname e.g. "ROBINSONS ANTIPOLO - BEBANG ENTERPRISE INC."
            _validate_target_company(company)

            store_ledger: dict = {"abbr": abbr, "result": []}
            for entry in _topological_sort(store_data["groups_to_create"]):
                _validate_gap_entry(entry, company)
                try:
                    docname, status = _ensure_group_account(
                        company=company,
                        account_name=entry["account_name"],
                        parent_account=entry["parent_account"],
                        root_type=entry["root_type"],
                    )
                    store_ledger["result"].append({
                        "name": docname,
                        "account_name": entry["account_name"],
                        "status": status,
                    })
                    if status == "created":
                        ledger["total_created"] += 1
                    else:
                        ledger["total_existed"] += 1
                except Exception as exc:
                    frappe.log_error(
                        title=f"S243 seed failed for {company} / {entry.get('account_name')}",
                        message=traceback.format_exc()[:1500],
                    )
                    store_ledger["result"].append({
                        "account_name": entry.get("account_name"),
                        "status": "error",
                        "error": str(exc)[:300],
                    })
                    ledger["errors"].append({
                        "company": company,
                        "account_name": entry.get("account_name"),
                        "error": str(exc)[:300],
                    })
                    ledger["total_errors"] += 1

            ledger["stores"][abbr] = store_ledger

        # v1.1-B4: dry-run = rollback outer savepoint (NEVER commit)
        if dry_run:
            frappe.db.rollback(save_point=OUTER_SAVEPOINT)
        else:
            frappe.db.release_savepoint(OUTER_SAVEPOINT)
            frappe.db.commit()

    finally:
        frappe.local.flags.ignore_root_company_validation = original_root_flag

    return ledger
```

**MUST_MODIFY:** `scripts/s243/seed_canonical_coa_for_4_stores.py` (NEW)
**MUST_CONTAIN:** `TARGET_COMPANIES`, `_ensure_group_account`, `_load_gap_analysis`, `_validate_target_company`, `_validate_gap_entry`, `_topological_sort`, `frappe.db.savepoint`, `frappe.db.rollback(save_point=`, `frappe.db.release_savepoint`, `frappe.db.commit`, `frappe.local.flags.ignore_root_company_validation`, `is_group=1` OR `"is_group": 1`, `BEBANG ENTERPRISE INC.`, `os.makedirs`, `s243_seed_outer`
**MUST_NOT_CONTAIN:** `_ensure_account(` (s206's leaf-only helper — must NOT be reused), `is_group=0`, `is_group: 0`, `account_number = "1100000"`, `"Stock Assets - "` followed by abbr in account_name (BARE only)

**2-T2** **HARD BLOCKER:** the seeder's `_validate_target_company` and `_validate_gap_entry` raise `ValueError` if the gap analysis JSON requests:
- An account on a Company NOT in `TARGET_COMPANIES`
- An account with `is_group=0` (only groups allowed)
- An account_name not in `ALLOWED_ACCOUNT_NAMES = {"Stock Assets", "Accounts Payable", "Current Assets"}`
- A non-NULL `account_number` (BARE-NAME requires NULL)
- More than 4 accounts per Company

These validators run BEFORE any insert. Errors abort the seeder run.

**2-T3 (v1.1)** Wire SSM execution: `tmp/s243/run_seeder.py` (gitignored, transient).

Per audit B7+B8 mitigation: invoke `Skill(skill='frappe-bulk-edits')` to obtain the canonical SSM boilerplate; do NOT `Read` the SKILL.md file directly. The boilerplate logs dirs are already inlined in `seed_canonical_coa_for_4_stores.py` (so no additional steps needed). The SSM wrapper just base64-encodes the seeder, docker-cps to the backend container, and runs it.

Two modes:
- `--dry-run`: invokes `seed_canonical_coa_for_4_stores.execute(dry_run=True)`. Per the seeder design, this opens outer savepoint, runs all inserts, **rolls back outer savepoint at end**, **never calls `frappe.db.commit()`**. Result: production state unchanged. Writes ledger to `tmp/s243/seed_dry_run_<timestamp>.log` (transient).
- (default): invokes `seed_canonical_coa_for_4_stores.execute(dry_run=False)`. Per the seeder design, this opens outer savepoint, runs all inserts, releases savepoint, **calls `frappe.db.commit()`**. Writes final ledger to `output/s243/verification/seed_ledger.json` (committed).

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

### Phase 4 — Closeout (4 units — v1.1)

**4-T1** Run canonical post-check:
```bash
python scripts/verify_canonical_structure.py 2>&1 | tee output/s243/verification/canonical_post_check.log
```
Must show `ALL CANONICAL` (same baseline as Phase 0). If new violations, STOP — the seeder introduced drift.

**4-T2 (v1.1 — adds rebase + output/ git add -f)** Update plan YAML metadata + registry, then stage all closeout artifacts:

```bash
# Plan + Registry (docs/ gitignored)
git add -f docs/plans/2026-05-09-sprint-243-canonical-coa-4-stores.md
git add -f docs/plans/SPRINT_REGISTRY.md

# v1.1-W6: output/ is also gitignored — closeout evidence files need -f too
git add -f output/s243/

# v1.1-W5: rebase against current production before pushing
git fetch origin --prune
git rebase origin/production
# If conflicts: resolve, do NOT --force --skip; if blocked, STOP and present to Sam.
```

Plan YAML edits:
- `status: PLANNED_AUDITED_v1_1` → `status: COMPLETED`
- Add `completed_date: 2026-05-XX`
- Add `pr: <PR#>`
- Add `execution_summary: <one-paragraph result>`

Registry S243 row edits:
- Status: `PLANNED_AUDITED_v1_1` → `COMPLETED`
- PR field filled
- Execution summary appended

**4-T3 (v1.1 — adds MUST_MODIFY + MUST_CONTAIN + embedded Requirements Regression Checklist)** Write `output/s243/SUMMARY.md` with the EXACT structure below:

```markdown
# S243 Closeout Summary

## Pre-state vs post-state

| Store | Abbr | Pre accounts | Post accounts | Created | Existed |
|---|---|---:|---:|---:|---:|
| ROBINSONS ANTIPOLO - BEBANG ENTERPRISE INC. | ROA | 5 | <N> | <N> | <N> |
| SM MANILA - BEBANG ENTERPRISE INC. | SMM | 5 | <N> | <N> | <N> |
| SM MEGAMALL - BEBANG ENTERPRISE INC. | SMMM | 5 | <N> | <N> | <N> |
| SM SOUTHMALL - BEBANG ENTERPRISE INC. | SMS | 5 | <N> | <N> | <N> |
| **Total** | | **20** | **<N>** | **<N>** | **<N>** |

`coa_complete_count` post-seed: **49 / 49** ✓

## Requirements Regression Checklist (PASS/FAIL)

Each item below MUST be checked ✓ or marked ✗ with reason. v1.1 audit-fix items:

- [ ] **A1 (BARE-NAME convention)**: All created accounts use `account_name` BARE (no abbr); `account_number = NULL`; Title Case. Verified by post-state probe (`tmp/s243/probe_phase0_state.py` re-run shows the new groups have `account_name` BARE matching the 43-store dominant convention).
- [ ] **A2 (ignore_root_company_validation)**: Seeder used `frappe.local.flags.ignore_root_company_validation = True` during inserts and restored on exit. Confirmed via `grep -c "ignore_root_company_validation" scripts/s243/seed_canonical_coa_for_4_stores.py` ≥ 2.
- [ ] **A3 (account_name shape)**: Seeder passed `account_name` BARE to `frappe.get_doc({})`; Frappe constructed `name = "<account_name> - <abbr>"` automatically. Confirmed via `seed_ledger.json` showing each created account's `name` matches `expected_docname` from `coa_gap_analysis.json`.
- [ ] **A4 (outer-savepoint dry-run)**: Phase 2-T5 dry-run report shows `rollback_confirmed: true` and `post_dry_run_account_counts` for all 4 stores equal pre-state.
- [ ] **A5 (evidence regen)**: `tmp/s243/probe_phase0_state.py` exists in worktree (NOT cited from `tmp/s238/`); `output/s243/verification/before_state.json` was produced by this script.
- [ ] **A6 (Phase 4-T3 gates)**: This SUMMARY.md exists with the Requirements Regression Checklist as a PASS/FAIL table (this very section).
- [ ] **A7 (PR description gate)**: PR body = this SUMMARY.md (via `cat output/s243/SUMMARY.md`); Requirements Regression Checklist visible in PR.
- [ ] **A8 (`git add -f output/`)**: Closeout staged `output/s243/` evidence files via `git add -f`.

Original v1 regression items (must all PASS):

- [ ] Canonical preflight passed pre-execute (Phase 0)
- [ ] Canonical preflight passed post-execute (Phase 4)
- [ ] No new canonical violations introduced
- [ ] Only the 4 named target Companies received account inserts (per `seed_ledger.json`)
- [ ] All inserted accounts have `is_group=1` (no leaf accounts created)
- [ ] All inserted accounts follow BARE-NAME convention (verified A1)
- [ ] Pre-existing accounts on the 4 target stores preserved untouched
- [ ] No accounts created on any of the 45 complete stores
- [ ] No accounts created on `BEBANG KITCHEN INC.`, `BEBANG ENTERPRISE INC.`, or any parent legal entity
- [ ] `tabCompany`, `tabWarehouse`, `tabCustomer`, `tabSupplier` unchanged
- [ ] No SI / PI / GL / SLE mutations
- [ ] `coa_complete_count: 49 / 49` post-seed (per `coa_complete_count.json`)
- [ ] S238 `_find_parent_group_for(company, "Stock Assets")` returns non-null for all 4 target stores post-seed
- [ ] Same for `Accounts Payable` and `Current Assets` parent lookups
- [ ] Plan YAML status updated to COMPLETED
- [ ] SPRINT_REGISTRY.md S243 row updated to COMPLETED + PR# filled

## Follow-up sprint candidates (out-of-scope for S243, recorded for S244+)

1. **Q1 Input VAT recovery for the 42 historical Submitted BKI SIs (~PHP 51,765 input VAT)** on these 4 stores. Q1 2550Q deadline (2026-04-25) has passed; recoverable via Q2 carry-forward (deadline 2026-07-25). PH Finance audit PH-3.
2. **Extend `scripts/verify_canonical_structure.py` with a CoA-completeness rule** (e.g., `COA_INCOMPLETE_<root>`) so the same skeleton-CoA gap on a future per-store Company creation surfaces at canonical-preflight time, not via a separate S238-style probe. Architectural blocker B8 from S243 audit.
3. **Full canonical CoA harmonization for the 4 stores** (Sales tree, COGS, Expense, Equity hierarchy). S243 only created the 3 group accounts S238 needs.

## S238 unblock confirmation

S238 Phase 0-T4 CoA-completeness gate is now passable for all 49 stores. S238 can resume from Phase 0-T1 in a fresh session.
```

**MUST_MODIFY:** `output/s243/SUMMARY.md`
**MUST_CONTAIN:** `"Requirements Regression Checklist"`, `"A1 (BARE-NAME convention)"`, `"A2 (ignore_root_company_validation)"`, `"A3 (account_name shape)"`, `"A4 (outer-savepoint dry-run)"`, `"A5 (evidence regen)"`, `"A6 (Phase 4-T3 gates)"`, `"A7 (PR description gate)"`, `"A8 (`git add -f output/`)"`, `"S238 unblock confirmation"`, `"Follow-up sprint candidates"`, `"49 / 49"`

**4-T4** Create PR:
```bash
GH_TOKEN="" gh pr create --repo Bebang-Enterprise-Inc/hrms \
  --base production --head s243-canonical-coa-4-stores \
  --title "S243: Canonical CoA Backfill — 4 BEBANG ENTERPRISE INC. Stores (v1.1)" \
  --body "$(cat output/s243/SUMMARY.md)"
```

PR body = entire SUMMARY.md including the Requirements Regression Checklist (audit B7 fix). Reviewer (Sam) sees the full PASS/FAIL table in the PR description.

**4-T5** Worktree exit clean:
```bash
cd F:/Dropbox/Projects/BEI-ERP-s243-canonical-coa-4-stores
git status --short    # must be clean
cd F:/Dropbox/Projects/BEI-ERP
git worktree remove F:/Dropbox/Projects/BEI-ERP-s243-canonical-coa-4-stores
```

**Phase 4 verify (v1.1 — comprehensive):**
```python
import os, json, sys, re, subprocess
errs = []

# Required artifacts
required_files = [
    "output/s243/SUMMARY.md",
    "output/s243/verification/canonical_post_check.log",
    "output/s243/verification/before_state.json",
    "output/s243/verification/reference_bare_name_coa.json",
    "output/s243/verification/coa_gap_analysis.json",
    "output/s243/verification/seed_dry_run_report.json",
    "output/s243/verification/after_state.json",
    "output/s243/verification/seed_ledger.json",
    "output/s243/verification/coa_complete_count.json",
    "scripts/s243/seed_canonical_coa_for_4_stores.py",
    "tmp/s243/probe_phase0_state.py",  # v1.1-B5
]
for f in required_files:
    if not os.path.exists(f): errs.append(f"MISSING: {f}")

# Canonical post-check clean
log = open("output/s243/verification/canonical_post_check.log", encoding="utf-8", errors="replace").read()
if "ALL CANONICAL" not in log: errs.append("post-check not clean")

# Plan YAML closed
plan = open("docs/plans/2026-05-09-sprint-243-canonical-coa-4-stores.md", encoding="utf-8").read()
if "status: COMPLETED" not in plan: errs.append("plan YAML status not updated to COMPLETED")

# v1.1-B6/B7: SUMMARY.md must contain Requirements Regression Checklist
summary = open("output/s243/SUMMARY.md", encoding="utf-8").read()
required_summary_strings = [
    "Requirements Regression Checklist",
    "A1 (BARE-NAME convention)",
    "A2 (ignore_root_company_validation)",
    "A3 (account_name shape)",
    "A4 (outer-savepoint dry-run)",
    "A5 (evidence regen)",
    "A6 (Phase 4-T3 gates)",
    "A7 (PR description gate)",
    "A8 (`git add -f output/`)",
    "S238 unblock confirmation",
    "49 / 49",
]
for s in required_summary_strings:
    if s not in summary: errs.append(f"SUMMARY.md missing: {s}")

# v1.1-A1 enforce: seeder must use BARE convention + flag
seeder = open("scripts/s243/seed_canonical_coa_for_4_stores.py", encoding="utf-8").read()
for s in ["TARGET_COMPANIES", "ignore_root_company_validation", "is_group=1", "frappe.db.savepoint",
          "frappe.db.rollback(save_point=", "_validate_target_company", "_ensure_group_account",
          "ALLOWED_ACCOUNT_NAMES", "Stock Assets", "Accounts Payable", "Current Assets"]:
    if s not in seeder: errs.append(f"seeder missing: {s}")
forbidden_in_seeder = [
    'is_group=0', 'is_group: 0',
    '_ensure_account(',  # do NOT call s206's leaf helper
]
for s in forbidden_in_seeder:
    if s in seeder: errs.append(f"seeder must NOT contain: {s}")

# Coa completeness
counts = json.load(open("output/s243/verification/coa_complete_count.json"))
if counts.get("complete_stores") != 49: errs.append(f"only {counts.get('complete_stores')} stores complete (expected 49)")
if counts.get("incomplete_stores"): errs.append(f"still incomplete: {counts['incomplete_stores']}")

# Ledger sanity
ledger = json.load(open("output/s243/verification/seed_ledger.json"))
if ledger.get("total_errors", 1) != 0: errs.append(f"seeder had errors: {ledger.get('errors')}")

# Registry updated
registry = open("docs/plans/SPRINT_REGISTRY.md", encoding="utf-8").read()
if "| `S243` |" not in registry: errs.append("SPRINT_REGISTRY missing S243 row")

# Worktree status (best-effort — only check if git is reachable here)
try:
    out = subprocess.check_output(["git", "status", "--short"], encoding="utf-8")
    if out.strip(): errs.append(f"worktree dirty: {out!r}")
except Exception:
    pass

print("PASS" if not errs else "\n".join(errs))
sys.exit(0 if not errs else 1)
```

---

## Phase Budget Contract (v1.1 — audit-amended)

| Phase | v1 | v1.1 | v1.1 Δ rationale |
|---|---:|---:|---|
| Phase 0 — Boot, preflight, pre-state probe | 4 | 5 | +1: regenerate `tmp/s238` evidence as `tmp/s243/probe_*.json` (B5) |
| Phase 1 — Reference mapping & gap analysis | 5 | 5 | unchanged (sample 5 BARE-NAME stores instead of just XMM; B1 framing fix) |
| Phase 2 — Seeder script + dry-run | 6 | 8 | +2: inline SSM boilerplate, `ignore_root_company_validation` flag, outer-savepoint dry-run scoping, exact dict shape (B2/B3/B4, W1/W2/W4) |
| Phase 3 — Apply seeder + verify | 4 | 4 | unchanged |
| Phase 4 — Closeout | 3 | 4 | +1: SUMMARY.md MUST_MODIFY/MUST_CONTAIN gates, embedded Requirements Regression Checklist, rebase-before-push, `git add -f output/` (B6/B7, W5/W6) |
| **Total** | **22** | **26** | **+4 units (8 CRITICAL fixes + 5 WARNINGs)** |

**v1.1 total: 26 units** — well under 80-unit ceiling. No phase exceeds 12-unit preferred-split threshold. Single-session executable.

---

## Surface Ownership Matrix (S087, v1.1)

| Surface | Owner | Allowed mutations |
|---|---|---|
| `scripts/s243/seed_canonical_coa_for_4_stores.py` | S243 | NEW file (v1.1: inlined SSM boilerplate, `ignore_root_company_validation` flag, outer-savepoint dry-run scoping, BARE-NAME convention, exact dict shape) |
| `tmp/s243/probe_phase0_state.py` | S243 | **NEW (v1.1-B5)** — regenerates Phase 0 probes (replaces `tmp/s238/probe_4_incomplete_stores.py` which is gitignored / not in worktree) |
| `tmp/s243/run_seeder.py` | S243 | NEW (transient — gitignored, SSM execution wrapper) |
| `tabAccount` (4 target Companies only) | S243 | INSERT — group accounts only (`is_group=1`, BARE-NAME convention, `account_number=NULL`); strictly scoped to ROA/SMM/SMMM/SMS |
| `output/s243/verification/*.json` | S243 | NEW evidence files (`before_state`, `reference_bare_name_coa`, `coa_gap_analysis`, `seed_dry_run_report`, `after_state`, `seed_ledger`, `coa_complete_count`, `canonical_post_check`) |
| `output/s243/SUMMARY.md` | S243 | NEW closeout summary (v1.1: MUST_MODIFY + MUST_CONTAIN gates, embedded Requirements Regression Checklist as PASS/FAIL table) |
| `docs/plans/2026-05-09-sprint-243-canonical-coa-4-stores.md` | S243 | UPDATE (audit amendment v1.1, then closeout YAML) |
| `docs/plans/SPRINT_REGISTRY.md` | S243 | UPDATE (S243 row + Next Sprint Reservation bump to S244) |
| `tabCompany` / `tabWarehouse` / `tabCustomer` / `tabSupplier` | NOT S243 | UNCHANGED |
| `tabAccount` (45 complete stores OR BEBANG KITCHEN INC. OR BEBANG ENTERPRISE INC. parent) | NOT S243 | UNCHANGED |
| `tabAccount` leaf accounts on the 4 target stores | NOT S243 (S238's job) | UNCHANGED |
| `tabAccount` existing groups on 4 target stores (`1100000 - ASSETS - <ABBR>`, `2104000 - INTERCOMPANY PAYABLES - <ABBR>`, root types) | NOT S243 | UNCHANGED — preserved untouched |
| `hrms/api/*.py` | NOT S243 | UNCHANGED |
| `hrms/utils/*.py` | NOT S243 | UNCHANGED |
| `hrms/on_demand/s206_seed_intercompany_accounts.py` | NOT S243 (referenced as pattern only; do NOT call `_ensure_account` directly per audit B5) | UNCHANGED |
| `scripts/verify_canonical_structure.py` | NOT S243 (architectural extension OUT OF SCOPE per audit B8 — recorded as follow-up sprint candidate) | UNCHANGED |
| Existing 42 BKI SIs to these 4 stores | NOT S243 (separate Q1/Q2 Input VAT recovery sprint per audit PH-3) | UNCHANGED |

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

## Requirements Regression Checklist (v1.1)

### NEW v1.1 audit-fix checks (must all pass)

- [ ] **A1 (BARE-NAME convention)**: All inserted accounts have `account_name` BARE (no abbr suffix), `account_number = NULL`, Title Case. `grep -c "account_name BARE" scripts/s243/seed_canonical_coa_for_4_stores.py` ≥ 1 (or equivalent inline comment); `grep -c "is_group=0" scripts/s243/...` returns 0; `grep -c "_ensure_account(" scripts/s243/...` returns 0 (must use NEW `_ensure_group_account`).
- [ ] **A2 (ignore_root_company_validation)**: Seeder has `frappe.local.flags.ignore_root_company_validation = True` set before inserts and restored on exit. `grep -c "ignore_root_company_validation"` ≥ 2.
- [ ] **A3 (account_name shape)**: Phase 1-T2's `coa_gap_analysis.json` has `account_name` BARE (e.g., `"Stock Assets"`, NOT `"Stock Assets - ROA"`). Phase 2-T1 seeder passes the BARE value to `frappe.get_doc({})` and lets Frappe construct `name`. Verified by `seed_ledger.json` showing each created account's `name` = `"<account_name> - <abbr>"` matching `expected_docname`.
- [ ] **A4 (outer-savepoint dry-run)**: Seeder's `execute(dry_run=True)` opens outer savepoint, runs all inserts, calls `frappe.db.rollback(save_point=OUTER_SAVEPOINT)` at end, NEVER calls `frappe.db.commit()`. Phase 2-T5 dry-run report shows `rollback_confirmed: true` and `post_dry_run_account_counts` for all 4 stores equal pre-state.
- [ ] **A5 (evidence regen, NOT cited from `tmp/s238/`)**: Phase 0-T4 produced `tmp/s243/probe_phase0_state.py` (NEW file in the worktree); plan body refers to `tmp/s243/` paths (NOT `tmp/s238/`); `output/s243/verification/before_state.json` was generated by this script.
- [ ] **A6 (Phase 4-T3 SUMMARY.md gates)**: SUMMARY.md exists with the Requirements Regression Checklist as a PASS/FAIL table (per Phase 4-T3 MUST_CONTAIN list).
- [ ] **A7 (PR description gate)**: PR body = `cat output/s243/SUMMARY.md`; Requirements Regression Checklist visible in PR description.
- [ ] **A8 (`git add -f output/`)**: Closeout staged `output/s243/` evidence files via `git add -f` so they appear in the PR diff.
- [ ] **W5 (rebase-before-push)**: Phase 4-T2 ran `git fetch origin --prune && git rebase origin/production` before push.
- [ ] **A9 (B8 follow-up recorded)**: SUMMARY.md "Follow-up sprint candidates" section names extending `verify_canonical_structure.py` with a CoA-completeness rule as a future S244+ sprint.

### Original v1 checks (must all pass)

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
