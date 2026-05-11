# Billing Sweep — Per-Store Gap Analysis

**Generated:** 2026-05-11
**Probe source:** `tmp/billing-sweep/probe_result.json` (S244_PROBE)
**Scope:** All candidate buyer Companies that the BKI→Store PI generator (S238) would fire for.

## Headline

- **Candidate buyer Companies queried:** 51
- **🟢 READY for live-fire smoke test (45):** All canonical store Companies with full preconditions
- **🟥 BLOCKED — defects discovered (4):** Stores missing `Company.cost_center`
- **⚪ NOT-IN-SCOPE (2):** Companies that aren't store buyers

## Global state — ✅ all good

| Check | Value |
|---|---|
| `BEI Settings.enable_bki_store_pi_generator` | True ✓ |
| `BEI Settings.bki_sales_naming_series` | `BKI-SI-.YYYY.-.#####` ✓ |
| BKI Company exists | True ✓ |
| BKI TRADE Supplier exists | True ✓ (disabled=0, is_internal_supplier=0, PHP) |
| Custom Field SI.custom_bei_store_order | ✓ present |
| Custom Field PI.bki_si_reference | ✓ present |
| SI autoname hook | `hrms.api.bki_si_naming.set_bki_si_name` ✓ |
| SI on_submit hook | `hrms.api.bki_store_pi_generator.maybe_generate_store_pi` ✓ |
| SI on_cancel hook | `hrms.api.bki_store_pi_generator.cascade_cancel_store_pi` ✓ |
| PI validate hook | `hrms.api.bki_store_pi_generator.lock_posting_date_on_bki_paired_pi` ✓ |

Two extra Purchase Invoice fields the probe expected (`custom_bei_store_order`, `custom_bki_paired_si`) are absent. **Verified non-issue:** the generator only reads/writes `bki_si_reference` on PI. Those two fields were either de-scoped from v2 or never added — generator works fine without them. Removed from defects list.

## Historical state (Sam already flagged for cleanup)

| Metric | Count |
|---|---|
| BKI SIs total | 839 |
| BKI SIs submitted | 560 |
| BKI SIs cancelled | 230 |
| BKI SIs draft | 49 |

All test data per Sam's directive. Cleanup is the #1 follow-up.

## 🟥 DEFECT — 4 stores will fail PI generation silently

These 4 stores are the **same ones S243 just seeded canonical CoA for**. S243 added the accounts but did NOT set `Company.cost_center`. The PI generator's `_resolve_per_store_cost_center` will throw, the savepoint will rollback, and the SI submit proceeds without an error — **silent miss**.

| Store | Abbr | Accounts (S243) | cost_center | Customer | Warehouse |
|---|---|---|---|---|---|
| ROBINSONS ANTIPOLO - BEBANG ENTERPRISE INC. | ROA | ✓ 3/3 | ❌ NULL | ✓ | ✓ |
| SM MANILA - BEBANG ENTERPRISE INC. | SMM | ✓ 3/3 | ❌ NULL | ✓ | ✓ |
| SM MEGAMALL - BEBANG ENTERPRISE INC. | SMMM | ✓ 3/3 | ❌ NULL | ✓ | ✓ |
| SM SOUTHMALL - BEBANG ENTERPRISE INC. | SMS | ✓ 3/3 | ❌ NULL | ✓ | ✓ |

**Severity:** CRITICAL — silent revenue posting miss for 4 active stores.

**Suggested fix (S245 candidate):** small UPDATE per store, using each store's canonical `Main - <ABBR>` cost center (the convention used by every other ready store). Example:

```sql
UPDATE `tabCompany` SET cost_center = 'Main - ROA'  WHERE name = 'ROBINSONS ANTIPOLO - BEBANG ENTERPRISE INC.';
UPDATE `tabCompany` SET cost_center = 'Main - SMM'  WHERE name = 'SM MANILA - BEBANG ENTERPRISE INC.';
UPDATE `tabCompany` SET cost_center = 'Main - SMMM' WHERE name = 'SM MEGAMALL - BEBANG ENTERPRISE INC.';
UPDATE `tabCompany` SET cost_center = 'Main - SMS'  WHERE name = 'SM SOUTHMALL - BEBANG ENTERPRISE INC.';
```

**Pre-fix verification needed:** confirm `Main - <ABBR>` Cost Center exists for each of the 4 stores. If absent, the cost center itself must be created first (standard `Main - <ABBR>` is auto-created by `frappe.get_doc("Company", name).save()` but may not have run for these recently-seeded Companies).

## ⚪ Not-in-scope buyer Companies (2)

These Companies appear in the candidate query but are not actual store buyers:

| Company | Abbr | Why excluded |
|---|---|---|
| BEBANG FRANCHISE CORP. | BFC | No matching Customer record; no Warehouse; no S238 accounts — separate franchise legal entity, not a store buyer |
| LEGACY77 FOOD CORP. | L77 | Has Customer but no Warehouse, no S238 accounts — separate entity, not a store buyer |

These would never receive a store order from BKI, so PI generation isn't applicable.

## 🟡 Minor info — BKI TRADE Supplier missing per-Company Party Account entries

All 51 candidate Companies lack `Supplier.accounts[company]` rows for `BEBANG KITCHEN INC. - Trade`. **Not a runtime blocker** — the generator computes `pi.credit_to` directly from `resolve_account_by_number(buyer_company, "2103210")`, bypassing the Supplier.accounts table.

**Future Finance UX impact:** When a Finance user opens the PI manually, the AP account won't auto-populate from Supplier. Worth a one-time backfill but not blocking this sweep.

## Proposed sweep plan

**Phase A — Smoke-test the 45 READY stores (live-fire):**
- Reuse `tmp/s238/smoke_test.py` pattern (create+submit+verify+cancel+force-delete per store)
- Track every artifact in teardown ledger
- Sequential execution (≈10s/store + cleanup → ~10 min total)
- Expected: 45/45 PASS

**Phase B — Smoke-test the 4 BROKEN stores AS-IS (defect proof):**
- Run same pattern against ROA, SMM, SMMM, SMS
- Expected: 4/4 SI submits succeed BUT PI not created (silent failure)
- This confirms the defect is real and the test catches it

**Phase C — Fix the 4 stores' `Company.cost_center` (S245 candidate, separate PR):**
- UPDATE 4 Companies' `cost_center` field
- Verify `Main - <ABBR>` cost center exists per store (create if absent)
- Spawn worktree, commit script, open PR

**Phase D — Re-smoke the 4 stores post-fix:**
- Should now 4/4 PASS

**Phase E — Cleanup all test artifacts:**
- Force-delete any leftover test SIs from the sweep
- Document final state in `output/l3/billing-sweep-2026-05-11/SUMMARY.md`
- Open DEFECTS.md with the cost_center defect

## Decision needed from Sam

| Option | What I'd run | Risk | Time |
|---|---|---|---|
| **A. Full sweep (49 stores)** — phases A+B+C+D+E | Sweep 45 ready + 4 broken + fix + re-test | Moderate (creates+deletes ~53 test SIs; touches 4 Companies' master data) | ~25 min |
| **B. Ready-only sweep (45 stores)** — phase A+E only | Just smoke 45 ready stores, defer 4-store fix to S245 | Low (no master-data changes) | ~10 min |
| **C. Defect proof only** — phase B only | Just show the 4 broken stores fail | Very low (4 test SIs only) | ~3 min |
