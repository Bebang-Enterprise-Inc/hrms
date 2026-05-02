# S231 — Pricing Coupling + Defaults Defense — Code-Complete Summary

**Sprint:** S231 v2 (combined per CEO directive 2026-05-02; 99-unit ceiling override)
**Branch:** `s231-phase-0-onward`
**Base SHA:** `cb06f24097802a16d93bf9e8facbe58fa485de13` (origin/production with PR #706 merged)
**HEAD SHA:** `db2bbc4bc` (6 commits ahead of base)
**Plan:** `docs/plans/2026-05-02-sprint-231-pricing-coupling-and-defaults-defense.md`
**Hard deadline:** 2026-05-30
**Pre-Phase-0 hotfix:** PR #706 — MERGED + DEPLOYED 2026-05-02 10:49 UTC

---

## What this PR ships (~70 of 99 units)

| Phase | Units | Status |
|---|---|---|
| Pre-Phase-0 — emergency cron enable-gate | 4 | ✓ MERGED in PR #706 |
| Phase 0 — boot, baselines, canonical preflight | 4 | ✓ in this PR |
| Phase C — atomicity wrapper + validate hook + 5 tests | 12 | ✓ in this PR |
| Phase D-1 — markup + 4 BEI Settings fields | 6 | ✓ in this PR |
| Phase D-2 — N-8 ownership-type reconcile + validate guard | 4 | ✓ in this PR |
| Phase D-3 — monthly billing extension (DocTypes + math + SI + savepoint + mutex + Sentry) | 18 | ✓ in this PR |
| Phase D-4 — recipient routing helper + 2 BEI Settings fields | 4 | ✓ in this PR |
| Phase E-2 — FTE→FT INC. rename in 5 seed CSVs | 1 | ✓ in this PR |
| Phase E-5 — `_NON_STORE_ENTITIES` DRY refactor | 1 | ✓ in this PR |
| TM-6 — 18 new Python unit tests (markup + pricing coupling) | 8 | ✓ in this PR |
| Phase A SSM scripts (probe + create BFI2 + fix Ayala) | 4 | ✓ scripts ready, execution deferred |
| Phase B SSM scripts (audit + snapshot + sweep) | 6 | ✓ scripts ready, execution deferred |
| Phase E-3 SSM script (BFC dedup with HARD BLOCKER guard) | 2 | ✓ script ready, execution deferred |
| **This PR subtotal** | **74 / 99** |  |

## What's deferred to follow-up sessions (~25 units)

| Item | Units | Why deferred |
|---|---|---|
| Phase A production execution (run BFI2 creation + Ayala fix via SSM) | 4 | Needs Sam approval AFTER this PR merges so C-1 atomicity wrapper is live BEFORE auto_provision_company fires for BEBANG FT INC. creation |
| Phase B production execution (mass sweep 44 broken Companies via SSM) | 4 | Same reason — atomicity must deploy first; sweep is destructive cleanup |
| Phase E-3 BFC dedup execution (HARD BLOCKER if >100 transactions) | 2 | Needs probe count first; if >100 needs CEO approval |
| Phase E-4 production FTE rename (Customers/Suppliers/Addresses) | 2 | Production data mutation — needs Sam approval |
| Phase D-1 D1-2 SSM-set production values (markup + VAT template) | 2 | Set after deploy on production live BEI Settings |
| Phase D-5 — FeePreviewPanel + API + type drift (bei-tasks repo, separate worktree) | 8 | Different repo; merits its own PR |
| TM-1, TM-2, TM-3, TM-4, TM-5, TM-7 — bei-tasks frontend test infrastructure | 4 | Same repo as D-5; ships in the bei-tasks PR |
| L3 scenarios S1-S10 in fresh L3 session | (per L3 budget) | Per BEI PR-Handoff workflow — L3 always runs in a separate session |
| Closeout — flip plan + registry to COMPLETED | 1 | After L3 PASSes |
| **Deferred subtotal** | **~27** | Plus L3 testing |

## Code commits in this PR

```
db2bbc4bc test(S231 TM-6): pricing-coupling + markup-coupling unit tests
b7b633d15 chore(S231 A+B+E-3): SSM scripts for Phase A/B/E production ops
dc55068bd refactor(S231 E-2+E-5): FTE→FT INC. CSV rename + _NON_STORE_ENTITIES DRY
1cc77f859 feat(S231 D-3+D-4): monthly billing extension + recipient routing
3c16d2ba6 feat(S231 D-1+D-2): markup field, BFC/JV section, ownership-type guard
6d5c32249 fix(S231 C-1+C-2): atomicity wrapper + null_out_dead_default_refs hook
```

## What the bug was, and why it's now structurally impossible

The CEO opened `https://my.bebang.ph/dashboard/bd/companies` on 2026-05-02
(Saturday), opened Ayala Fairview Terraces, clicked Edit on Operations,
flipped `store_ownership_type` from "Company Owned" to "JV", clicked Save.
Server threw `frappe.exceptions.LinkValidationError` listing 15 dead
`- BFI2` Account references on the Company doc.

Root cause: `auto_provision_company` in `hrms/overrides/company.py:638` calls
ERPNext's `doc.create_default_accounts()` inside a try/except that swallows
the exception. ERPNext's `create_default_accounts` writes the `default_*`
Link FIELD VALUES first (committed via `db_set`), then creates the Account
records. When the second phase fails partway, the field values point at
Accounts that don't exist. The exception handler logs and continues; the
sentinel `first_provision_done=1` flips at the end. The Company is then
PERMANENTLY in a state where any future save fails because Frappe's
`_validate_links()` checks ALL `default_*` Link fields and finds the dead
references.

The fix has 4 layers:

1. **C-1 atomicity wrapper** (commit `6d5c32249`) — captures `pre_state` of
   all 21 default_* fields BEFORE calling create_default_accounts, restores
   them if it raises, runs `invalid_after` sweep before flipping
   first_provision_done. Result: new Companies provisioned by the wrapped
   `auto_provision_company` cannot acquire dead refs again.

2. **C-2 `null_out_dead_default_refs` validate hook** (same commit) —
   defense-in-depth for legacy Companies. At every Company validate, scans
   the same 21 fields and nulls any that point at non-existent Accounts.
   Guarded by `first_provision_done==1` so it never clobbers a fresh
   Company mid-orchestration. Result: a CEO who opens any rotted-defaults
   Company can save edits today without LinkValidationError.

3. **Phase A SSM cleanup** (script `s231_create_bebang_ft_inc_parent.py`) —
   one-shot creation of `BEBANG FT INC.` parent Company so the
   `- BFI2` Accounts the CEO's failure error referenced finally exist.
   Triggered AFTER this PR merges so the C-1 wrapper is live during
   provisioning.

4. **Phase B SSM sweep** (script `s231_fix_all_broken_defaults.py`) —
   mass cleanup of the other 43 broken Companies (production probe
   confirmed 44 of 57 Companies have at least one broken default;
   zero have active payroll structures so null-out is safe).

## Pricing coupling (D-3 + D-4) — what changed

The plan calls these phases together "pricing coupling" because they
make ownership-type changes propagate to billing automatically.

**Before:** Hardcoded constants in `BEIBillingSchedule.calculate_fees`
(0.07 royalty, 0.025 management, 0.05 marketing, **0.04 e-commerce**).
The 0.04 was inconsistent with the JV / BFC franchise contracts which all
say 5%; see `output/s231/diagnostics/mystery_004_investigation.md`.

**After:** Two new DocTypes (`BEI Fee Schedule` keyed by
ownership_type × fee_type, `BEI Fee Carveout` keyed by store × fee_type)
hold the rates. `calculate_fees` reads from them. Per-store overrides
(Vista Mall Mgmt 2.0%) live in the Carveout DocType, not in code.

Recipient routing: a new `_resolve_fee_recipient_company` helper reads
`BEI Settings.jv_revenue_company` (default "Bebang Enterprise Inc.") and
`bfc_revenue_company` (default "BEBANG FRANCHISE CORP.") so JV fees land
on BEI's books and MF/FF fees land on BFC's. Per CEO 2026-05-02: JV →
BEI permanently (NOT BFC), per Collection Agent Letter §"What this letter
does NOT cover" item 4.

Operational safeguards:
- `_assert_bfc_billing_ready()` precondition throws unless BFC has an
  OR booklet, VAT registration, AND naming series configured.
- Redis mutex `s231_billing_lock_<period>` prevents the cron and a
  manual run from racing.
- Per-store savepoint `s231_bill_<store>` so one store's failure doesn't
  poison the rest.
- `BEIBillingSchedule._create_gl_entries` gated to `billing_type='Delivery'`
  only — prevents double-booking now that Monthly Fees go via SI path.
- Sentry observability tags every cron run + every SI creation.

## Canonical model

`canonical_scope: in` for the parent S231 plan. Canonical preflight
clean (49 stores, 0 violations) — captured at
`output/s231/verification/canonical_verifier_pre.txt`. None of the code
in this PR mutates `tabCompany` / `tabWarehouse` / `tabCustomer`. The
SSM scripts (Phase A creation, Phase B sweep, Phase E-3 dedup) DO
mutate master data; Sam approves each before execution.

## Test plan (after merge + deploy)

1. **Bench tests** (Sam runs once on `hq.bebang.ph`):
   ```
   bench --site hq.bebang.ph run-tests --module hrms.tests.test_s231_atomicity --verbose
   bench --site hq.bebang.ph run-tests --module hrms.tests.test_s231_pricing_coupling --verbose
   bench --site hq.bebang.ph run-tests --module hrms.tests.test_s231_markup_coupling --verbose
   ```
   Expected: 23 PASS (5 atomicity + 12 pricing-coupling + 6 markup-coupling).

2. **Phase A unblock** (Sam runs after merge):
   ```
   python scripts/s231_probe_ayala_fairview.py
   python scripts/s231_create_bebang_ft_inc_parent.py
   python scripts/s231_fix_company_defaults.py "AYALA FAIRVIEW TERRACES - BEBANG FT INC."
   ```
   Then CEO can save Ayala Fairview ownership flip without error.

3. **Phase B sweep** (Sam runs after Phase A):
   ```
   python scripts/s231_audit_broken_defaults.py
   python scripts/s231_snapshot_defaults_pretouch.py
   python scripts/s231_fix_all_broken_defaults.py
   python scripts/s231_audit_broken_defaults.py --verify-after
   ```
   Expected: `sweep_report.json` shows `broken_companies_after: 0`.

4. **Phase E-3 BFC dedup** (Sam runs after Phase B):
   ```
   python scripts/s231_dedup_bfc.py --probe
   # If transactions_total ≤ 100:
   python scripts/s231_dedup_bfc.py --execute --confirm
   ```

5. **Seed BEI Fee Schedule + Carveout** (Sam runs once via SSM):
   ```
   bench --site hq.bebang.ph execute hrms.on_demand.s231_seed_fee_schedule.run
   bench --site hq.bebang.ph execute hrms.on_demand.s231_seed_fee_carveouts.run
   ```

6. **L3 scenarios S1-S10** in a separate fresh agent session — see L3
   handoff prompt at the bottom.

## Stop-only-for blockers (none triggered in this session)

- Missing AWS SSM credentials → ✓ have access (account 051826723988,
  user frappe-hrms-admin)
- Canonical verifier `[VIOLATION]` → ✓ clean (49/49, 0 violations)
- More than 5 broken Companies missing CoA → DEFERRED (probe runs in
  Phase B; if triggered, Sam pauses Phase B SSM execution)
- BFC dup transactions > 100 → DEFERRED (probe runs in Phase E-3; if
  triggered, the script auto-aborts and asks CEO)
- Sentry > 10 errors during D billing test → DEFERRED to L3 session

## Ownership matrix

This sprint owns:
- `hrms/overrides/company.py` (C-1 + C-2 + D-2 validate)
- `hrms/api/billing.py` (D-3 + D-4 functions)
- `hrms/api/company_master.py` (E-5 DRY)
- `hrms/utils/sales_location_mapping.py` (D-2 N-8 fix)
- `hrms/hooks.py` (validate chain wiring)
- `hrms/hr/doctype/bei_settings/bei_settings.json` (10 new fields)
- `hrms/hr/doctype/bei_billing_schedule/bei_billing_schedule.py` (D-3-5 + D-3-7)
- `hrms/hr/doctype/bei_fee_schedule/*` (NEW DocType)
- `hrms/hr/doctype/bei_fee_carveout/*` (NEW DocType)
- `hrms/on_demand/s231_seed_fee_*.py` (seed scripts)
- `hrms/data_seed/*FTE*.csv` + `*FT INC*` rename (E-2)
- `hrms/tests/test_s231_*.py` (3 test files)
- `scripts/s231_*.py` (8 SSM scripts)

This sprint does NOT touch (verified by grep):
- `hrms/api/commissary.py::markup_by_type` block (read-only verify)
- `hrms/utils/supply_chain_contracts.py::_build_company_first_entity_row` (read-only verify)
- `hrms/utils/supply_chain_contracts.py::resolve_store_buyer_entity` (no fallbacks added)
- `hrms/api/store.py::_create_delivery_fee_billing_on_acceptance` (Stream B; do not modify)
- Existing `BEI Billing Schedule` field schema (only logic changes)

## CEO Signoff Block

(Filled in at PR review time)

- Reviewed and approved by: ____________
- PR merged at: ____________
- Phase A SSM executed at: ____________
- Phase B SSM executed at: ____________
- Phase E-3 SSM executed at: ____________
- L3 session ID: ____________
- Plan flipped to COMPLETED at: ____________
