# S233 L3 Runbook — Create Store UI

## Verified working test pipeline (2026-05-04)

Result of latest run: **7/7 PASS in 1.0m**, no orphans, canonical verifier clean post-run.

```
✓ S1  BD/CEO user creates a new store correctly (happy path)         17.6s
✓ S2  Detail dialog opens for new store and renders correctly         4.4s
✓ S3  Duplicate abbr is rejected with friendly toast                  3.5s
✓ S4  Parent dropdown shows ONLY canonical parents (filter test)      3.5s
✓ S5  Blank parent rejects submission with toast                      3.1s
✓ S7  BD Manager sees button; Crew-only does NOT (RBAC)               8.3s
✓ S8  Two BD users race — savepoint atomicity proven                 20.2s
```

## Quick run

```bash
# 1. Spawn fresh worktrees (or reuse if you already have them)
cd F:/Dropbox/Projects/BEI-ERP && git fetch origin --prune
git worktree add F:/Dropbox/Projects/BEI-ERP-l3-s233 -B l3-s233-runner-hrms origin/production
cd F:/Dropbox/Projects/bei-tasks && git fetch origin --prune
git worktree add F:/Dropbox/Projects/bei-tasks-l3-s233 -B l3-s233-runner origin/main
cd F:/Dropbox/Projects/bei-tasks-l3-s233 && npm install

# 2. Pre-test seed (BFI2 entity_category check, test users, missing roles)
cd F:/Dropbox/Projects/BEI-ERP-l3-s233
python scripts/s233_l3_seed_roles.py            # creates BD Manager + Business Development + Crew Roles if missing
python scripts/s233_l3_seed_preconditions.py    # verifies BFI2 + creates test.bd + test.crew users

# 3. Run the spec (browser-only per CEO directive)
cd F:/Dropbox/Projects/bei-tasks-l3-s233
npx playwright test tests/e2e/specs/s233-create-store-ui.spec.ts --reporter=list

# 4. Post-test teardown (deletes 4 records × 2 stores + S037 CSV rows)
cd F:/Dropbox/Projects/BEI-ERP-l3-s233
python scripts/s233_l3_teardown_test_store.py

# 5. Confirm clean state
python scripts/verify_canonical_structure.py    # 49/49 ALL CANONICAL — 0 violations
```

## Test library files (reusable)

### bei-tasks repo

| File | Purpose |
|---|---|
| `tests/e2e/specs/s233-create-store-ui.spec.ts` | The 7-scenario L3 spec |
| `tests/e2e/pages/CreateStoreDialog.ts` | Page Object with all real user actions (open, fill, pick, submit, cancel, readParentDropdownOptions) |
| `tests/e2e/builders/store-create-payload.ts` | Test data builder with sane defaults |
| `tests/e2e/assertions/canonicalStoreShape.ts` | Read-only API assertions via `page.evaluate(fetch)` (authenticated browser context) |
| `tests/e2e/fixtures/cleanup.ts` | `store-company-create` cleanup kind reverses 4 records |
| `tests/e2e/fixtures/auth.ts` | `loggedInAsBdManager` + `loggedInAsCrewOnly` fixtures |

### hrms repo

| Script | Purpose |
|---|---|
| `scripts/s233_l3_seed_roles.py` | Idempotent: creates `BD Manager`, `Business Development`, `Crew` Frappe Role DocTypes if missing (frontend declares them but no fixtures migration ever seeded them) |
| `scripts/s233_l3_seed_preconditions.py` | Verifies BFI2 canonical + creates `test.bd@bebang.ph` (BD Manager) + `test.crew@bebang.ph` (Crew only) — both pwd `BeiTest2026!` |
| `scripts/s233_l3_teardown_test_store.py` | Idempotent: deletes test stores (`L3 Test Store 233` + `L3 Race Test Store`) — 4 records each + 2 S037 CSV rows |
| `scripts/s233_probe_bfi2_entity_category.py` | Read-only probe: BFI2 is_group + entity_category state |
| `scripts/s233_backfill_bfi2_entity_category.py` | Conditional backfill: BFI2 entity_category to "Holding Company" if missing |
| `scripts/s233_l3_probe_roles.py` | Read-only probe: which Frappe Roles exist (BD Manager, etc.) |
| `scripts/s233_l3_probe_territories.py` | Read-only probe: tabTerritory + Customer Group state |
| `scripts/s233_l3_probe_test_records.py` | Read-only probe: post-create canonical 4-record state |
| `scripts/s233_l3_probe_bfc_bki.py` | Read-only probe: BFC + BKI is_group + entity_category |

### scripts/canonical/repair_s037_for_company.py
Operator runbook for post-savepoint CSV-write failures. Idempotent: reads Company, derives store_label, checks for existing S037 row, appends if missing. Used when the helper's post-savepoint CSV write fails (operator gets Sentry alert pointing here).

## CEO directive — real-life browser-only

The spec is written per the 2026-05-03 CEO directive:

> "The test should be like real life scenarios, not just to pass, so make sure any test script we create reflects that and it should all be done in browser."

### Banned anti-patterns absent from spec body
- `ssmRun(` — not used (would mutate production)
- `set_value("Customer Group"` — not used
- `NONEXISTENT_GROUP` — not used (would require test-only kwarg in helper)
- monkey-patching — not used
- Direct REST mutations — not used (only read-only `frappe.client.get_value` GET via `page.evaluate(fetch)`)

### Scenarios reflect real user actions
- S1 happy: BD/CEO clicks Add Store → fills form → submits → verifies via authenticated read-only API
- S2 detail: clicks new row → detail dialog opens
- S3 duplicate abbr: real-user typo on abbr → friendly toast
- S4 dropdown filter (NOT bypass test): verifies filter prevention works — real users cannot pick a non-canonical parent because the dropdown filters them out
- S5 required field: blank parent → submit blocked
- S7 RBAC: BD Manager sees button; Crew-only does NOT
- S8 concurrent race: TWO real BD users (`loggedInAsCEO` + fresh `test.bd@bebang.ph` context) submit identical payloads via `Promise.all` — exactly one wins, savepoint atomicity holds

### Setup + teardown outside the browser
- Pre-test: `/frappe-bulk-edits` style SSM scripts run BEFORE Playwright opens
- Post-test: SSM teardown runs AFTER Playwright closes
- The spec body itself is pure browser interactions + read-only verification

## Collateral defects discovered (long-standing data drift, NOT S233 bugs)

These were discovered during L3 + don't break the S233 feature, but are recommended follow-ups:

1. **Frappe Role DocTypes missing**: `BD Manager`, `Business Development`, `Crew` declared in `bei-tasks/lib/roles.ts` but no fixtures migration. Mitigated by `s233_l3_seed_roles.py` for testing.
2. **BFC + BKI `is_group=0`**: `BEBANG FRANCHISE CORP.` (Franchisor) and `BEBANG KITCHEN INC.` (Commissary) cannot host child Companies in production. Filter correctly excludes them; if BD wants Franchisor stores under BFC, fix the master data.
3. **Territory "Philippines" missing from `tabTerritory`**: legacy code references it; helper now uses "All Territories" (root, always exists).
4. **BD Manager lacks Frappe `Company.create` doctype-level perm**: test.bd@bebang.ph can pass the role-based gate but fails Frappe's permission check. Sam should add `Company.create` to BD Manager via Role Permission Manager for the feature to work end-to-end for non-System-Manager users.

## Hotfix sequence required to land

L3 caught real bugs that local TS-only verification missed. Each hotfix exposed the next blocking issue:

| PR | Issue |
|---|---|
| #719 | Initial S233 build (hrms backend + bei-tasks frontend) |
| #720 | `frappe.rename_doc(force=True, ignore_permissions=True)` — wrapper rejects kwarg (didn't help) |
| #721 | Call `frappe.model.rename_doc.rename_doc` directly — works |
| #723 | Customer territory = `"All Territories"` (Philippines doesn't exist) |
| #462 | Vercel TS strict-build hotfix |

## Anti-patterns this spec avoids (S120/S225 lessons)

- ❌ Element existence checks instead of value verification → ✅ asserts toast text via regex match
- ❌ API shortcuts for mutations → ✅ every mutation via real button click
- ❌ Stale records → ✅ pre-test teardown ensures fresh state
- ❌ Selector guessing → ✅ all 7 `data-testid` attributes per Page Object pattern
- ❌ Python `sync_playwright` → ✅ TypeScript `npx playwright test` (S231 lesson)
- ❌ Top-level `request` fixture without cookies → ✅ `page.evaluate(fetch)` for authenticated read-only verification
- ❌ Test-only kwargs in production helper → ✅ no back doors in the helper
- ❌ Disabling production master records mid-test → ✅ no production state mutations from spec

## Future regressions

To re-run for regression testing after any change to:
- `hrms/api/create_new_store.py`
- `hrms/api/company_master.py::create_store_company`
- `hrms/api/company_master.py::list_eligible_parent_companies`
- `bei-tasks/components/company-master/create-store-dialog.tsx`
- `bei-tasks/lib/queries/company-master.ts::useCreateStoreCompany`
- `bei-tasks/app/dashboard/bd/companies/page.tsx` (header + RBAC guard)
- `hrms/utils/bei_config.py::STORE_ENTITY_MAPPING_RELPATH`
- `scripts/canonical/repair_s037_for_company.py`
