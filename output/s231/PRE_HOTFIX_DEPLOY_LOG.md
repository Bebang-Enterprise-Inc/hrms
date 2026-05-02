# S231 Pre-Phase-0 — Emergency Cron Enable-Gate Hotfix Deploy Log

**Created:** 2026-05-02 (Saturday) PHT
**Branch:** `s231-pricing-coupling-and-defaults-defense`
**Worktree:** `F:/Dropbox/Projects/BEI-ERP-s231-pricing-coupling-and-defaults-defense`
**Base SHA:** `c2bbb813f94419fa7e86248bd921fbedd16484a2` (origin/production)
**Plan:** `docs/plans/2026-05-02-sprint-231-pricing-coupling-and-defaults-defense.md`
**Sprint:** S231 v2 (combined; CEO override on 80-unit ceiling 2026-05-02)
**Hard deadline:** 2026-05-30 (June 1 cron firing protected by this hotfix)

---

## Why this ships first (PR-1 of the sprint)

`hrms.api.billing.scheduled_monthly_billing` is wired in `hrms/hooks.py` `scheduler_events.cron`
at `0 6 1 * *`. Today (2026-05-02) the cron silently errors because:

1. `tabBEI Billing Schedule` is not migrated to production (`billing_table_exists: false`
   per `dep_production_state.json`).
2. `bki_sales_vat_template` is empty in production BEI Settings.

Once the main S231 PR deploys (which runs `bench migrate` and creates the table + the
`BEI Fee Schedule` / `BEI Fee Carveout` DocTypes), the cron starts WORKING. We need a
kill-switch in production BEFORE main S231 ships so the next cron firing on
**2026-06-01 06:00 PHT** stays no-op until Finance ratifies dry-run output.

---

## Changes in this PR

### File 1: `hrms/hr/doctype/bei_settings/bei_settings.json`

- Added new field `bki_billing_cron_enabled` (Check, default `"0"`).
- Inserted in `field_order` after `bki_markup_full_franchise_percent`.
- Inserted in `fields[]` array after the matching field definition.
- BEI-owned in-tree DocType pattern (NOT custom_field.json), per `dep_schema_migration.md`.

### File 2: `hrms/api/billing.py`

- Added kill-switch gate at the top of `scheduled_monthly_billing()` (line 1426).
- Reads `BEI Settings.bki_billing_cron_enabled` via `frappe.db.get_single_value`.
- Returns early (no-op) when the flag is 0/falsy.
- Preserves existing `generate_monthly_billing` call signature when flag is 1.
- Docstring extended with S231 Pre-Phase-0 rationale.

---

## MUST_MODIFY assertions

| File | Modified | Verified by |
|---|---|---|
| `hrms/hr/doctype/bei_settings/bei_settings.json` | YES | `git diff --stat` shows +8 lines |
| `hrms/api/billing.py` | YES | `git diff --stat` shows +9 lines |

## MUST_CONTAIN assertions

| String | File | Found at line |
|---|---|---|
| `"bki_billing_cron_enabled"` | `bei_settings.json` field_order | line 59 |
| `"bki_billing_cron_enabled"` (fieldname) | `bei_settings.json` fields[] | inserted after `bki_markup_full_franchise_percent` |
| `"default": "0"` | `bei_settings.json` (new field) | inserted with field |
| `"S231 Pre-Phase-0"` | `bei_settings.json` description | inserted with field |
| `"S231 Pre-Phase-0"` | `billing.py` docstring | line 1431 |
| `"bki_billing_cron_enabled"` | `billing.py` gate | line 1440 |

---

## Post-deploy verification (Sam runs after merge + redeploy)

Via SSM (bench python on `i-026b7477d27bd46d6`):

```python
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
val = frappe.db.get_single_value("BEI Settings", "bki_billing_cron_enabled")
assert val == 0, f"Expected 0, got {val}"
print("PRE-PHASE-0 GATE LIVE")
```

Expected output: `PRE-PHASE-0 GATE LIVE`. Capture the SSM stdout and append to
this log under "Deploy Verification" once Sam confirms.

---

## What does NOT change

- Existing `generate_monthly_billing()` API behavior (still callable manually by Finance).
- Existing `hooks.py` cron schedule (`0 6 1 * *`) — still fires; gate now enforces no-op.
- Any other BEI Settings field.
- Any DocType schema other than the additive field on BEI Settings (single-table `tabSingles` row).

---

## What Sam needs to do

1. Review this PR.
2. Merge to `production`.
3. Trigger the deploy workflow (or wait for the auto-deploy on push to production).
4. Run the verification snippet above via SSM.
5. Confirm production reports `bki_billing_cron_enabled=0`.
6. Comment "PRE-PHASE-0 LIVE" on this PR or the S231 closeout PR so the agent can
   resume Phase 0+ in a subsequent session.

After step 6 is complete, the main S231 work (Phase 0 → Phase E + tests + closeout)
proceeds in subsequent agent sessions. Agent does NOT proceed to Phase 0 until
production reports the gate is live (per plan PH-3).

---

## Stop point per plan

> **Plan PH-3 (line 222):** Ship as separate PR (PR-1 of the sprint), merge + deploy
> fast (~30 min). Sam reviews + merges + deploys; agent does NOT proceed to Phase 0
> until production reports `bki_billing_cron_enabled=0` is live.

This is one of the explicit "stop only for" reasons in the execute-plan-bei-erp skill:
the plan declared a HARD BLOCKER between Pre-Phase-0 and Phase 0.

---

## Canonical preflight

Verified before code change:

```
======================================================================
CANONICAL STRUCTURE VERIFICATION
Stores checked: 49
Violations: 0
======================================================================
[RESULT] ALL CANONICAL — no action required
```

Captured to `output/s231/verification/canonical_verifier_pre.txt`. No master-data
mutations in Pre-Phase-0; canonical structure unchanged.

---

## Worktree status at PR creation

```
Branch: s231-pricing-coupling-and-defaults-defense
Base:   c2bbb813f94419fa7e86248bd921fbedd16484a2 (origin/production)
Files:  2 modified, 17 lines inserted, 0 deleted
Path:   F:/Dropbox/Projects/BEI-ERP-s231-pricing-coupling-and-defaults-defense
```

Main checkout `F:/Dropbox/Projects/BEI-ERP` was NOT touched. Worktree will be
cleaned up by the agent that closes out the main S231 PR (or by /merge-bei-erp
after the closeout PR merges).
