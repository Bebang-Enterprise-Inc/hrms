# S238 Smoke Test Results — FULL PASS

**Date:** 2026-05-10
**Test type:** Production smoke test (NOT consuming BIR-authorized serials per Sam's clarification — Frappe ERP is internal/supplementary, not BIR-accredited)
**Test transaction:** Created + cancelled + force-deleted in single SSM execution; production state restored to clean.

---

## Why a smoke test was safe on production

Earlier closeout SUMMARY incorrectly stated *"Plan forbids production test SI submission (consumes BIR ATP serials)"*. **That premise was wrong.** Per Sam's clarification 2026-05-10:

> Frappe ERP documents are internal-only and **NOT BIR-accredited**. Creating test transactions doesn't consume any BIR-authorized serials. The right concern is **leaving test transactions polluting production** — every test SI must be deleted after the run.

This corrects the earlier SUMMARY text (lines about "BIR ATP serial consumption" and "first organic SI" deferral). The smoke test is **the** validation step.

The 839 BKI SIs already in production are also test transactions (not real). Cleanup of all test transactions is a follow-up sprint candidate (see below).

---

## Smoke test path

**Single test SI: `BKI-SI-2026-00981-2`** (ARANETA GATEWAY, ₱1.00 + ₱0.12 VAT = ₱1.12 total, 1 line item PM003)

| Stage | Behavior | Result |
|---|---|---|
| **Autoname hook** | `set_bki_si_name` parses `custom_bei_store_order=BEI-ORD-2026-00981` → counts existing SIs (1) → assigns `BKI-SI-2026-00981-2` | ✅ Matched expected |
| **SI submit** | docstatus 0 → 1; grand_total ₱1.12 | ✅ |
| **on_submit hook** | `maybe_generate_store_pi` fires → savepoint → `build_store_pi` → insert | ✅ |
| **PI created** | `ACC-PINV-2026-00700` Draft PI on ARANETA's books | ✅ |
| **PI fields** | All 14 expected fields present and correct (see table below) | ✅ |
| **SI cancel** | docstatus 1 → 2; `cascade_cancel_store_pi` fires | ✅ |
| **Cascade delete** | Paired Draft PI deleted (`pi_still_exists: false` post-cancel) | ✅ |
| **Force-delete SI** | Test SI removed from `tabSales Invoice` | ✅ |
| **Final state** | Production clean — no test artifacts | ✅ |

## PI field-level verification (per audit fix mapping)

| Field | Expected | Actual | Audit fix |
|---|---|---|---|
| `pi.company` | per-store Co | `ARANETA GATEWAY - TUNGSTEN CAPITAL HOLDINGS OPC` | — |
| `pi.supplier` | external Trade Supplier (not internal) | `BEBANG KITCHEN INC. - Trade` | ICT-001..006 (CFO Butch) |
| `pi.docstatus` | 0 (Draft, awaiting Finance review) | `0` | v2-B11 (always Draft, no auto-submit) |
| `pi.bill_no` | SI's docname | `BKI-SI-2026-00981-2` | — |
| `pi.bki_si_reference` | SI's docname (Custom Field) | `BKI-SI-2026-00981-2` | Phase 2 Custom Field |
| `pi.inter_company_invoice_reference` | NULL (incompatible w/ external supplier) | `null` | hotfix #3 (PR #742) |
| `pi.posting_date` | mirrors SI | `2026-05-10` | — |
| `pi.credit_to` | per-store AP-Trade-BKI | `2103210 - 2103210 - AP-Trade-BKI - ARGW` | v2-B4 (resolve_account_by_number) |
| `pi.update_stock` | 1 (inventory tracking) | `1` | — |
| `pi.set_warehouse` | per-store warehouse (canonical: same as Company) | `ARANETA GATEWAY - TUNGSTEN CAPITAL HOLDINGS OPC` | v2-B2 |
| `pi.bei_legal_entity` | **buyer's** (NOT seller's) | `ARANETA GATEWAY - TUNGSTEN CAPITAL HOLDINGS OPC` | **v2.1-CRIT-1** |
| `pi.bei_store_label` | mirrored from SI | `ARANETA GATEWAY` | v2.1-W7 (has_field guard) |
| `pi.currency` | PHP (per-store Company default) | `PHP` (verified — no INR/PHP mismatch) | hotfix #2 (PR #741) |
| `pi.grand_total` | matches SI | `1.12` | — |
| Item `expense_account` | per-store Inventory-from-Commissary | `1104210 - 1104210 - Inventory-from-Commissary - ARGW` | Phase 1 leaf |
| Item `cost_center` | **per-store** (NOT BKI's) | `Main - ARGW` | **v2.1-CRIT-2** + hotfix #1 (PR #740) |
| Tax `account_head` | per-store Input VAT | `1106210 - 1106210 - Input VAT - BKI Inter-Co - ARGW` | Phase 1 leaf |
| Tax `tax_amount` | 12% × 1.00 | `0.12` | — |
| Tax `cost_center` | per-store | `Main - ARGW` | v2.1-CRIT-2 |
| Tax `charge_type` | "Actual" | `Actual` | v2-B9 |

## Hotfixes triggered by smoke test

The audit chain (3 cycles + adversarial fact-check, 0 hallucinations) caught all plan-level CRITs but missed 3 ERPNext **runtime validation** defects. Smoke test caught them in 3 iterations:

| # | PR | Defect | Why audit missed it |
|---|---|---|---|
| 1 | [#740](https://github.com/Bebang-Enterprise-Inc/hrms/pull/740) | `Warehouse.custom_cost_center` Custom Field doesn't exist on production (plan referenced a pattern from `store.py:5278` that's itself broken/dead code) | Audit verified plan against plan; smoke verified code against runtime |
| 2 | [#741](https://github.com/Bebang-Enterprise-Inc/hrms/pull/741) | `frappe.new_doc('Purchase Invoice')` defaults `currency` to system default INR; ERPNext rejects on PHP/INR mismatch with credit_to account | Frappe behavior, not visible in plan text |
| 3 | [#742](https://github.com/Bebang-Enterprise-Inc/hrms/pull/742) | ERPNext `validate_inter_company_party` rejects `inter_company_invoice_reference` when supplier is `is_internal_supplier=0` (which is required per ICT-001..006) | ERPNext business rule, not visible in plan text |

## Cleanup verification

```
created_artifacts: {
  "si_name": "BKI-SI-2026-00981-2",
  "si_pre_autoname": "BKI-SI-2026-00981-2",
  "pi_name": "ACC-PINV-2026-00700"
}
```

After smoke test execution:
- ✅ SI `BKI-SI-2026-00981-2` cancelled (docstatus=2) and force-deleted from `tabSales Invoice`
- ✅ PI `ACC-PINV-2026-00700` deleted by `cascade_cancel_store_pi` hook (cleanly handled the cascade path that was the smoke's final assertion)
- ✅ No GL entries persisted (PI was Draft, never submitted; cancellation cascade triggered before submit)
- ✅ No SLE entries (Draft PI doesn't post stock movements)
- ✅ Production state restored to clean: 0 BKI SIs created since deploy

---

## Corrections to closeout SUMMARY.md

### Correction 1 — Test data, not real transactions

The earlier closeout SUMMARY listed *"42 historical Submitted Q2 carry-forward Input VAT recovery (~PHP 51,765)"* as follow-up sprint candidate. **This was based on the wrong assumption that the 839 historical BKI SIs are real transactions.** They are NOT real — they are accumulated test data from prior development cycles. The correct follow-up is:

> **Follow-up: cleanup of all test transactions before go-live.** All 839 BKI SIs (49 Draft + 560 Submitted + 230 Cancelled) on production are test data. They must be cancelled (where Submitted) and deleted, along with their associated GL/SLE entries, before BEI's actual go-live. This is a master-data cleanup sprint, not a VAT recovery sprint.

### Correction 2 — BIR accreditation

The earlier closeout SUMMARY referenced *"production trial is FORBIDDEN per plan (consumes BIR ATP serials)"*. **Frappe ERP is NOT BIR-accredited.** Per Sam 2026-05-10 + the `tmp/s238/BIR_SERIES_RESEARCH.md` finding from S238 v2.1 work:

> Frappe SIs are internal/supplementary documents, not BIR-registered principal invoices. The buyer's BIR-input-VAT-eligible SI comes from a separate BIR-registered channel (Mosaic POS at retail; loose-leaf or PTU CAS for B2B). Test SI submissions on Frappe production do NOT consume any BIR-authorized serials.

The "production smoke test forbidden" guidance was incorrect. The smoke test that ran today validated the entire hook chain end-to-end on production safely.

### Correction 3 — Live-fire validation status

The earlier SUMMARY said *"Live-fire validation pending first organic BKI SI submission post-deploy"*. **Live-fire validation is now complete** via the smoke test:
- Hook chain works correctly
- 3 runtime defects found and patched (PRs #740, #741, #742)
- All 14 PI fields verified against expected mapping
- Cancel cascade verified
- Cleanup mechanism verified

S238 is now functionally complete and validated. The Draft PI generation path is proven on production.

---

## Updated follow-up sprint candidates (corrected)

| # | Candidate | Notes |
|---|---|---|
| 1 | **Cleanup of all test transactions before go-live** | 839 BKI SIs are test data. Cancel/delete in bulk via `/frappe-bulk-edits`. Includes GL/SLE entries. Before this happens: BEI's per-store P&L will show test ₱483K of "sales" that's not real. |
| 2 | Extend `verify_canonical_structure.py` with CoA-completeness rule (S243 audit B8) | Same skeleton-CoA gap on next per-store Company creation would surface only via S238-style probe |
| 3 | Full canonical CoA harmonization for the 4 BEI stores | Replace non-canonical `1100000 - ASSETS - <ABBR>` and `2104000 - INTERCOMPANY PAYABLES - <ABBR>` with Frappe-default canonical roots |
| 4 | Auto-submit toggle for BKI store PIs (v2-B11 deferral) | Currently always Draft pending Finance review |
| 5 | Update G-046 dashboard queries to use `bki_si_reference` instead of `inter_company_invoice_reference` (hotfix #3 follow-up) | Hotfix #3 removed the IC ref because incompatible with external Supplier; dashboards filtering on `inter_company_invoice_reference IS NOT NULL` won't see paired PIs from S238 |
| 6 | Install `Warehouse.custom_cost_center` Custom Field if per-warehouse cost-center granularity becomes a requirement (hotfix #1 follow-up) | Currently using Company.cost_center default for all per-store PIs |
| 7 | Backfill paired PIs for any RE-deployed BKI SIs that were submitted between the original #738 deploy (2026-05-09T11:28Z) and the #742 hotfix deploy (2026-05-10T06:31Z) | Probe shows 0 BKI SIs were submitted in that window, so no backfill needed |

## Updated PR table

| Repo | PR# | Title | Status |
|---|---|---|---|
| hrms | #729 | S238 plan v1 | ✅ MERGED |
| hrms | #730 | S238 v2 amendment (11 CRITs) | ✅ MERGED |
| hrms | #733 | S238 v2.1 amendment (4 CRITs + adversarial fact-check) | ✅ MERGED |
| hrms | #735 | S243 plan + v1.1 amendment | ✅ MERGED |
| hrms | #736 | S243 execute (Canonical CoA backfill) | ✅ MERGED + DEPLOYED |
| hrms | #738 | S238 build (Phases 0-3) | ✅ MERGED + DEPLOYED 2026-05-09T11:28Z |
| hrms | #739 | S238 closeout (plan/registry COMPLETED) | ✅ MERGED + DEPLOYED 2026-05-09T22:33Z |
| hrms | #740 | Hotfix #1: cost-center has_field guard | ✅ MERGED + DEPLOYED 2026-05-09T23:06Z |
| hrms | #741 | Hotfix #2: explicit pi.currency = PHP | ✅ MERGED + DEPLOYED 2026-05-10T03:11Z |
| hrms | #742 | Hotfix #3: remove inter_company_invoice_reference | ✅ MERGED + DEPLOYED 2026-05-10T06:31Z |
| hrms | **TBD** | **Closeout amendment: smoke test results + SUMMARY corrections (this PR)** | 🟡 OPEN |

---

## Final state

**S238 v2.2 is functionally complete and production-validated.**

- All 4 BEI stores (ROA, SMM, SMMM, SMS) have canonical CoA (S243)
- All 49 stores have the 3 S238 leaf accounts (Phase 1)
- BKI Trade Supplier exists with TIN + 49 companies
- All 5 hooks registered (autoname, on_submit, on_cancel, PI validate, weekly drift)
- Toggle armed (`enable_bki_store_pi_generator=1`)
- Smoke test verified end-to-end PI generation, cancel cascade, and cleanup
- Production state clean (no test artifacts)

**Plan status:** COMPLETED (was COMPLETED in PR #739; this amendment refines the SUMMARY with smoke test results and corrects test-data/BIR notes).

**Follow-up sprints:** logged above. Most urgent is **cleanup of all 839 test BKI SIs** before BEI's go-live.
