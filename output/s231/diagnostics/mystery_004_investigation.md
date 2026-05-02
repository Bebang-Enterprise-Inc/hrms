# S231 D-3-1 — Mystery 0.04 Rate Investigation

**Date:** 2026-05-02 PHT
**File analyzed:** `hrms/hr/doctype/bei_billing_schedule/bei_billing_schedule.py`
**Method analyzed:** `BEIBillingSchedule.calculate_fees` (line 187)
**Suspect line:** `self.ecommerce_fee = web * 0.04`  (line 211, pre-S231)

---

## What I found

```python
# Line 210-211 of bei_billing_schedule.py (pre-S231):
# eCommerce fee: 4% of website sales (same for all store types)
self.ecommerce_fee = web * 0.04
```

The constant `0.04` (4%) is applied to `website_sales` for every Monthly Fees billing
regardless of store ownership type (JV, Managed Franchise, Full Franchise). The inline
comment claims "4% of website sales (same for all store types)".

## What the franchise contracts say

Cross-referenced against the cleanroom franchise documents:

| Document | Section | Rate Stated |
|---|---|---|
| `data/_CLEANROOM/2026-04-09_franchise_agreements/01_JV_Agreement_Grand_Central_Gabaldon.md` | §9.1 (eCommerce Fee) | **5%** of bebang.ph website sales, payable to BEI |
| `data/_CLEANROOM/2026-04-09_franchise_agreements/03_Franchise_Agreement_BFC.md` | §XI.I (eCommerce Fee) | **5%** of bebang.ph website sales, payable to BFC |
| `data/_CLEANROOM/2026-04-09_franchise_agreements/06_CEO_Approvals_2026-05-02.md` | "Pricing Coupling" decision | **5%** confirmed by CEO 2026-05-02; "Ecommerce charge is only on sales generated through bebang.ph website and not Foodpanda and Grab" |

All three sources agree the e-commerce fee is **5%**, not 4%.

## Conclusion: this is a code bug

The `0.04` constant in `calculate_fees` is **inconsistent** with the contractual rate of
**5%** (`0.05`). It is also not derived from any document or BEI Settings field — it
appears to be a typo or placeholder that was never reconciled against the contracts.

There is no git history annotation explaining 0.04 (the file was created with this value).
No BEI Settings field stores this rate. No comment cites a source.

## Impact assessment (read-only)

- **No production financial loss.** The cron `scheduled_monthly_billing` was silently
  erroring before S231 PR #706 deployed (2026-05-02) because `tabBEI Billing Schedule`
  hadn't been migrated. After PR #706, the cron is gated by
  `bki_billing_cron_enabled=0` and will not fire until Finance flips the switch. So
  no Monthly Fees BEI Billing Schedule rows exist in production today; the 0.04 rate
  has never produced a real fee invoice.
- **Frontend / preview impact:** any UI that displays the calculated fee (the new
  S231 D-5 FeePreviewPanel) would show 4% if it derived from this code path. D-5
  reads from BEI Fee Schedule directly, so it's already on the corrected rate.
- **Manual invoices:** if Finance ever manually created a Monthly Fees BEI Billing
  Schedule pre-S231, the e-com fee would be 1pp low. Finance review of any such
  rows is recommended.

## Fix applied in S231 D-3-5

The hardcoded `0.04` (and the other hardcoded rates `0.07`, `0.025`, `0.05` for
royalty/management/marketing) are removed from `calculate_fees`. The new
implementation reads rates from the new `BEI Fee Schedule` DocType:

```python
# New BEI Fee Schedule rows seeded by hrms/on_demand/s231_seed_fee_schedule.py:
# (ownership_type, fee_type, rate, base_field, recipient_company)
("JV", "Marketing", 0.05, "gross_sales", "Bebang Enterprise Inc."),
("JV", "E-commerce", 0.05, "website_sales", "Bebang Enterprise Inc."),
("Managed Franchise", "Royalty", 0.07, "net_sales_ex_vat", "BEBANG FRANCHISE CORP."),
("Managed Franchise", "Marketing", 0.05, "net_sales_ex_vat", "BEBANG FRANCHISE CORP."),
("Managed Franchise", "Management", 0.025, "gross_sales", "BEBANG FRANCHISE CORP."),
("Managed Franchise", "E-commerce", 0.05, "website_sales", "BEBANG FRANCHISE CORP."),
("Full Franchise", "Royalty", 0.07, "net_sales_ex_vat", "BEBANG FRANCHISE CORP."),
("Full Franchise", "Marketing", 0.05, "net_sales_ex_vat", "BEBANG FRANCHISE CORP."),
("Full Franchise", "E-commerce", 0.05, "website_sales", "BEBANG FRANCHISE CORP."),
# Co-Owned: no fees (early return in calculate_fees).
```

The 0.04 → 0.05 correction lives in the seed data, not in code. Per-store overrides
(e.g., Vista Mall 2.0% Mgmt) are stored in `BEI Fee Carveout` and consulted before
the schedule rate, so contract carve-outs no longer require code changes.

## Open question for CEO (none)

CEO 2026-05-02 already confirmed 5% e-com on bebang.ph website-only. No further
clarification needed. The investigation result and the 0.04 → 0.05 correction are
recorded in this document as the source of truth for the change.
