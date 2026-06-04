# S258 Phase 1 Cold-Start Handoff

> **For an agent entering Phase 1 from a fresh session.** Sam launched this
> handoff after the initial S258 execution session completed Phase 0 + the
> safe read-only Phase 1.4 (A4 template extract) but ran short of context
> for the live mutations. Paste the prompt below verbatim into the new
> session.

---

## Prior session status (2026-06-04, ended at Phase 1 partial)

| Phase | Subtask | Status | Evidence |
|---|---|---|---|
| 0 | All (0.0–0.8) | PASS | Phase 0 commit `8a66a0ecd` on branch `s258-coa-gl-finalization-bridge-handoff` |
| 1 | 1.4 A4 — extract template | PASS | `data/_FINAL/COA_HEALTHY_REFERENCE.csv` (114 stems, 82 in all 6 HEALTHY) |
| 1 | 1.5 A5 grep gate | PASS | 0 hits for "BFI2" in hrms/api/ + hrms/utils/ |
| 1 | 1.3 A3 probe | DONE | `tmp/s258/probe_round_off.json` — ROBDA UPPER form has 2 GL postings (JE+DELETE path); XMM UPPER form has 0 GL postings (DELETE-direct with `flags.ignore_links=True` acceptable; still cross-root_type → use JE+DELETE for uniformity) |
| 1 | 1.3.5 BEI round_off probe | DONE | `tmp/s258/probe_bei_round_off.json` — BEI current `round_off_account = "Stock Adjustment - Bebang Enterprise Inc."` (Expense, 0 GL → JE transfer **NOT needed**) |
| 1 | 1.0, 1.1, 1.2, 1.3 script, 1.3.5 script, 1.5 script | PENDING | _lib.py shared library written; per-subtask scripts not yet authored |

## Critical findings from prior session (read these first)

1. **DEFECTS.md D0-2:** III gl_entry_count = 0 (v1.0 was correct, v1.1 over-corrected). III IS a true zero-GL holdco with 338 accounts (highest of 3 Apex parents). Phase 3a still runs first because: 0 GL + smallest sales sub-tree complexity + cascade dependency on root tree.
2. **DEFECTS.md D0-3:** BFC + BFT have `first_provision_done=0`. Phase 2 + 3 scripts seeding them MUST set `frappe.flags.in_migrate = True` in preamble.
3. **DEFECTS.md D0-1:** Cleanroom source has 20 COA-175 rows (not 23). Phase 0.0 transcribed 20; Phase 7.1 adds 7 more (COA-175-024..030); total 27 at closeout.
4. **AYVER quirk:** AYVER's `default_inventory_account = "Stock In Hand - BMI2"` (parent's ABBR, not own ABBR). Decision needed in Phase 1.1: leave as-is (cross-Company reference, pre-existing) or relocate to `Stock In Hand - AYVER` (cleaner). Recommended: leave as-is; AYVER is already HEALTHY; the parent-Company reference is functional and there's no Sam directive to clean it up.

## Read-first sequence for fresh agent

```
1. F:/Dropbox/Projects/BEI-ERP-s258-coa-gl-finalization-bridge-handoff/docs/plans/2026-06-04-sprint-258-coa-gl-finalization-bridge-handoff.md  (full plan)
2. F:/Dropbox/Projects/BEI-ERP-s258-coa-gl-finalization-bridge-handoff/output/s258/PHASE_GATES.md  (running status)
3. F:/Dropbox/Projects/BEI-ERP-s258-coa-gl-finalization-bridge-handoff/output/s258/DEFECTS.md  (findings from prior session)
4. F:/Dropbox/Projects/BEI-ERP-s258-coa-gl-finalization-bridge-handoff/output/s258/baseline_state.json  (per-Company HEALTHY/PARTIAL/MINIMAL/MISSING + GL counts)
5. F:/Dropbox/Projects/BEI-ERP-s258-coa-gl-finalization-bridge-handoff/data/_FINAL/COA_HEALTHY_REFERENCE.csv  (114-stem template)
6. F:/Dropbox/Projects/BEI-ERP-s258-coa-gl-finalization-bridge-handoff/scripts/coa_fix/_lib.py  (shared library — Doppler creds, api_get/post/put, create_account, set_company_field, write_rollback_sql)
7. F:/Dropbox/Projects/BEI-ERP-s258-coa-gl-finalization-bridge-handoff/tmp/s258/probe_round_off.json + probe_bei_round_off.json  (live probe results)
```

## Working directory

`F:/Dropbox/Projects/BEI-ERP-s258-coa-gl-finalization-bridge-handoff`

This worktree already exists (do NOT re-spawn). Verify:
```
cd F:/Dropbox/Projects/BEI-ERP-s258-coa-gl-finalization-bridge-handoff
git status --short  # should show nothing or only fresh untracked files
git log -1 --format='%h %s'  # should show Phase 0 commit
```

## Doppler

```
doppler secrets get FRAPPE_API_KEY FRAPPE_API_SECRET FRAPPE_ADMIN_PASSWORD --plain --project bei-erp --config dev
```

All three must return non-empty.

## Your job this session

Complete Phase 1 (10 units, subtasks 1.0 + 1.1 + 1.2 + 1.3 + 1.3.5 + 1.5;
1.4 already PASS). Goal: 45 PARTIAL Companies move to HEALTHY (51 of 58
HEALTHY after Phase 1).

### Subtask scripts to author + execute

For each: write `scripts/coa_fix/Axx_NAME.py`, dry-run first
(`--dry-run` flag), inspect output, then execute live with rollback SQL
written before mutation. Each commit = one subtask.

| # | Script | Mechanism | Risk |
|---|---|---|---|
| 1.0 | `_gen_rollback_phase1.py` | Optional standalone — easier to use `_lib.write_rollback_sql()` from inside each Axx script. | ZERO |
| 1.1 | `A1_seed_default_inventory.py` | Per PARTIAL Company w/ `default_inventory_account=NULL` (43 of 45 — BEI + BKI already have non-NULL Apex names; handle separately): `frappe.client.exists("Account", f"Current Assets - {abbr}")` → if absent, CREATE the group first; then CREATE leaf `Stock In Hand - {abbr}` (root_type=Asset, account_type=Stock, currency=PHP, is_group=0); then `set_company_field(company, "default_inventory_account", f"Stock In Hand - {abbr}")`. **Pre-check (W9):** `SELECT COUNT(*) FROM tabBin WHERE warehouse.company IN (43 PARTIAL)`. Non-zero → log to DEFECTS.md but proceed (Bins already track movement; Company-level default is independent). **AYVER quirk:** out-of-scope (already HEALTHY); leave AYVER's parent-ABBR reference unchanged. **BEI + BKI**: skip — they have `INVENTORY - COMMISSARY - <abbr>` already and Phase 3b/3c will canonicalize them. | MED |
| 1.2 | `A2_set_l77_srbnb.py` | `set_company_field("LEGACY77 FOOD CORP.", "stock_received_but_not_billed", "Stock Received But Not Billed - L77")`. Verify the target account exists; if not, CREATE it. | LOW |
| 1.3 | `A3_dedupe_round_off.py` | Per `tmp/s258/probe_round_off.json`: for ROBDA (2 GL postings on `2120000 - ROUND OFF - ROBDA` Liability), build a Journal Entry: `Dr "Round Off - ROBDA" (Expense), Cr "2120000 - ROUND OFF - ROBDA" (Liability)` for the full balance; submit JE; then `frappe.delete_doc("Account", "2120000 - ROUND OFF - ROBDA", force=True, flags.ignore_links=True)`. For XMM (0 GL), skip JE and DELETE direct with `flags.ignore_links=True`. Both target Companies's `tabCompany.round_off_account` should already point at the canonical `Round Off - <ABBR>` (verify; if not, UPDATE). | HIGH (live JE on production GL) |
| 1.3.5 | `A3_5_canonicalize_bei_round_off.py` | CREATE `Round Off - BEI` Expense leaf under `Indirect Expenses - BEI` (create the group if absent — check first). `set_company_field("BEBANG ENTERPRISE INC.", "round_off_account", "Round Off - BEI")`. Verify the old `Stock Adjustment - Bebang Enterprise Inc.` still exists (0 GL postings — leave it; Phase 3c.4 will reparent under `Direct Expenses - BEI`). | LOW (0 GL on old account; no JE needed) |
| 1.5 | `A5_rename_bfi2_to_bft.py` | `company = frappe.get_doc("Company", "BEBANG FT INC.")`; `company.flags.ignore_validate_constants = True`; `frappe.db.set_value("Company", "BEBANG FT INC.", "abbr", "BFT", update_modified=True)`. Per-Account loop: `for acct in frappe.get_all("Account", filters={"name": ("like", "%- BFI2")}, pluck="name"): frappe.rename_doc("Account", acct, acct.replace("- BFI2", "- BFT"), force=True)`. **Lower risk than v1.1 estimated:** BFT (formerly BFI2) has 0 accounts per baseline (status=MISSING), so the per-Account loop is a no-op. Only the abbr field needs updating. | LOW |

### Execution rules (HARD BLOCKERS)

- Every account RENAME uses `frappe.rename_doc("Account", old, new)`. NO raw SQL UPDATE on `tabAccount.name`.
- Before each mutation, snapshot `SELECT COUNT(*) FROM tabGL Entry WHERE company=X` per affected Company → `tmp/s258/gl_total_phase1_pre.json`.
- After each mutation, re-query — total count IDENTICAL pre vs post. Non-zero delta = STOP.
- Generate per-phase rollback SQL via `_lib.write_rollback_sql(phase=1, sql_lines=[...])` BEFORE any mutation.
- Idempotent: re-running each script should be safe (account_exists checks before CREATE, value checks before SET).
- Commit after each subtask (`feat(S258 P1.X): ...`).

### Verification per subtask + Phase 1 closeout

Write `output/s258/verify_phase1.py` matching the assertion list in plan §Phase 1
verification script. Run after the last Phase 1 commit. PASS = proceed to Phase 2.

### Stop conditions (from plan §Autonomous Execution Contract)

- Doppler creds fail
- Canonical preflight VIOLATION
- GL postings count delta detected
- Phase 1 verification FAIL
- LinkValidationError on active GL postings

On success, hand off to Phase 2 (templates + migration map + 4 BEI-TIN stub seeds) in the SAME session if context budget > 30%; else generate Phase 2 handoff prompt.

---

## Estimated work-unit budget

| Subtask | Est wall-clock | Est API calls |
|---|---|---|
| 1.0 (rollback gen helper — already in `_lib.py`) | 0 | 0 |
| 1.1 A1 — 43 Companies × (exists-check + CREATE + SET) | ~5 min | ~130 |
| 1.2 A2 — L77 srbnb set | <1 min | ~5 |
| 1.3 A3 — ROBDA JE + 2 DELETEs | ~2 min | ~10 |
| 1.3.5 — BEI Round Off CREATE + UPDATE | <1 min | ~5 |
| 1.5 A5 — BFI2→BFT (abbr only — 0 child accounts) | <1 min | ~3 |
| verify_phase1.py | ~1 min | ~60 |
| **Total Phase 1** | **~10 min wall** | **~210 API calls** |

After Phase 1, baseline_state should show 51 HEALTHY / 4 MISSING (BFC + 4 stubs) / 3 MINIMAL/PARTIAL (Apex parents BEI/BKI/III still need Phase 3 rewrite).

---

## Copy this verbatim into a new Claude Code session

```
/execute-plan-bei-erp docs/plans/2026-06-04-sprint-258-coa-gl-finalization-bridge-handoff.md

You are continuing S258. Phase 0 PASS. Phase 1.4 PASS. Resume from Phase 1.0
via output/s258/PHASE1_HANDOFF.md (read it FIRST). The worktree at
F:/Dropbox/Projects/BEI-ERP-s258-coa-gl-finalization-bridge-handoff
already exists — do NOT re-spawn it. Branch:
s258-coa-gl-finalization-bridge-handoff. Last commit: 8a66a0ecd Phase 0.

After Phase 1 PASS, continue Phase 2 (templates + migration map + 4 stub
seeds) in same session if context budget > 30%; else generate Phase 2
handoff prompt before stopping.

After Phase 2 PASS, the plan's embedded "Phase 3 Cold-Start Handoff Prompt"
takes over (begin Phase 3a/b/c III→BKI→BEI Apex rewrite in another fresh
session).
```
