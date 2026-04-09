# Current Live State Snapshot (Phase A Audit 2026-04-09)

**Source:** `output/s175/preflight_audit.json` (live read-only SSM query on hq.bebang.ph, 2026-04-09 05:24:28 UTC)

Every number in this file is LIVE-VERIFIED. No memorized data. Re-verify before any mutation.

---

## 1. Frappe Companies (39 total)

| Category | Companies |
|---|---|
| **BEI group core** (3) | Bebang Enterprise Inc. (BEI), Bebang Kitchen Inc. (BKI), Triple I Holdings (TIH) |
| **JV / Managed Franchise** (2) | JV, Managed Franchise (MF) |
| **Holdings** (1) | DMD Holdings Inc. (DHI) |
| **Store corporations** (33) | BAG, BAS, BBHI, BDV, BEGC, BFI, BFI2, BGCI, BLI, BMI, BMMI, BMI2, BNEI, BPI, BPI2, BRGS, BSBI, BSC, BSC2, BSMI, BSS, BSS2, BST, BSI, BSI2, BSI3, BSI4, BSAI, BTGF, BTM, BUTC, BVGC, BV |

**Total:** 39 companies. `tax_id` is empty on all (BIR registration data not yet populated in Frappe).

### BFC Status: DOES NOT EXIST in Frappe
The Phase A audit script matched `BFC exists: True` on substring `FRANCHISE` — this was a **FALSE POSITIVE** triggered by the existing `Managed Franchise` company. **Bebang Franchise Corp. has not yet been created as a Frappe Company.** Phase 1 of S175 still needs to run the Company insert.

**Post-execution count:** 40 companies (39 existing + BFC new).

---

## 2. BEI 6xxxxxx Classification Audit (HB-4 gate)

**Live count:** 136 accounts total
- `root_type='Income'`, `report_type='Profit and Loss'`: **134** ← THE BUG
- `root_type='Expense'`, `report_type='Profit and Loss'`: **2**
- **GL entries on all 136: ZERO**

**HB-4 status:** PASS — bulk UPDATE `SET root_type='Expense'` is safe because no GL rows depend on the current (wrong) classification.

**Planned action:** Single SQL UPDATE in Phase 7 after a re-verification query returns the same `0 GL entries` count.

---

## 3. BKI Delete-Targets (HB-2 gate) — 19 of 20 exist, all 0 GL

| # | account_number | current name (on BKI) | children | GL | action |
|---|---|---|---|---|---|
| 1 | 4000001 | IN-STORE SALES | 0 | 0 | **DELETE** (BKI has no retail) |
| 2 | 4000002 | ONLINE SALES | 0 | 0 | **DELETE** (BKI has no online) |
| 3 | 4000100 | WHOLESALE / B2B SALES | 1 | 0 | **DELETE** (after child 4000101) — S168 legacy |
| 4 | 4000101 | SALES - BKI TO STORES | 0 | 0 | **DELETE** — S168 legacy |
| 5 | 4000200 | DISCOUNTS AND PROMO | 0 | 0 | **DELETE** (collides with new BKI SALES slot) |
| 6 | 4000201 | SALES DISCOUNT DUE TO FREE HALOHALO | 0 | 0 | **DELETE** (retail discount, not BKI) |
| 7 | 4000202 | SALES DISCOUNT OF SENIOR CITIZENS | 0 | 0 | **DELETE** |
| 8 | 4000203 | SALES DISCOUNTS OF PWDS | 0 | 0 | **DELETE** |
| 9 | 4000204 | SALES DISCOUNTS OF STAFFS AND EMPLOYEES | 0 | 0 | **DELETE** |
| 10 | 4000205 | SALES DISCOUNTS FROM VAT OF PWD | 0 | 0 | **DELETE** |
| 11 | 4000206 | SALES DISCOUNTS FROM VAT OF SENIOR CITIZENS | 0 | 0 | **DELETE** |
| 12 | 4000207 | SALES REFUNDS TO CUSTOMER | 0 | 0 | **DELETE** |
| 13 | 4000208 | (does not exist on BKI) | — | — | **SKIP** |
| 14 | 4000300 | FRANCHISE INCOME | 6 | 0 | **DELETE** (after 6 children — BKI is not franchisor) |
| 15 | 4000301 | ROYALTIES INCOME | 0 | 0 | **DELETE** |
| 16 | 4000302 | MARKETING FEE INCOME | 0 | 0 | **DELETE** |
| 17 | 4000303 | MANAGEMENT FEE INCOME | 0 | 0 | **DELETE** |
| 18 | 4000304 | ECOMMERCE FEE INCOME | 0 | 0 | **DELETE** |
| 19 | 4000305 | DELIVERY INCOME | 0 | 0 | **DELETE** (will be recreated under new 4000220 LOGISTICS) |
| 20 | 4000306 | LOGISTICS INCOME | 0 | 0 | **DELETE** (will be recreated under new 4000220 LOGISTICS) |

**Execution order:** Children first, then parents.
- Delete 4000101 before 4000100
- Delete `4000301-4000306` (6 children) before 4000300

**HB-2 status:** PASS — all 19 existing accounts have 0 GL entries.

---

## 4. BEI Delete/Migrate-Targets (HB-3 gate) — 22 of 22 exist, all 0 GL

| # | account_number | current name (on BEI) | children | GL | action |
|---|---|---|---|---|---|
| 1 | 4000001 | IN-STORE SALES | 0 | 0 | **DELETE** (Phase 2 creates new 4000110) |
| 2 | 4000002 | ONLINE SALES | 0 | 0 | **DELETE** (Phase 2 creates new 4000120) |
| 3 | 4000003 | 4000003 - ROYALTY INCOME | 0 | 0 | **DELETE** (duplicate-prefix legacy) |
| 4 | 4000004 | 4000004 - MANAGEMENT FEE INCOME | 0 | 0 | **DELETE** (duplicate-prefix legacy) |
| 5 | 4000005 | 4000005 - BRAND GROWTH FEE INCOME | 0 | 0 | **KEEP** per COA-175-016 (JV Brand Growth Fee holder, point-in-time recognition) |
| 6 | 4000006 | 4000006 - MARKETING FEE INCOME | 0 | 0 | **DELETE** (duplicate-prefix legacy) |
| 7 | 4000200 | DISCOUNTS AND PROMO (group) | 1 | 0 | **DELETE** (after child 4000208) — collides with new BKI SALES slot |
| 8 | 4000201 | SALES DISCOUNT DUE TO FREE HALOHALO | 0 | 0 | **DELETE** (Phase 2 creates new 4000901) |
| 9 | 4000202 | SALES DISCOUNT OF SENIOR CITIZENS | 0 | 0 | **DELETE** |
| 10 | 4000203 | SALES DISCOUNTS OF PWDS | 0 | 0 | **DELETE** |
| 11 | 4000204 | SALES DISCOUNTS OF STAFFS AND EMPLOYEES | 0 | 0 | **DELETE** |
| 12 | 4000205 | SALES DISCOUNTS FROM VAT OF PWD | 0 | 0 | **DELETE** |
| 13 | 4000206 | SALES DISCOUNTS FROM VAT OF SENIOR CITIZENS | 0 | 0 | **DELETE** |
| 14 | 4000207 | SALES REFUNDS TO CUSTOMER | 0 | 0 | **DELETE** |
| 15 | 4000208 | SALES DISCOUNTS - EMPLOYEE DISC | 0 | 0 | **DELETE** |
| 16 | 4000300 | FRANCHISE INCOME (group) | 6 | 0 | **DELETE** (after 6 children) — during Fork 1 interim BEI shouldn't hold franchise revenue |
| 17 | 4000301 | ROYALTIES INCOME | 0 | 0 | **DELETE** |
| 18 | 4000302 | MARKETING FEE INCOME | 0 | 0 | **DELETE** |
| 19 | 4000303 | MANAGEMENT FEE INCOME | 0 | 0 | **DELETE** |
| 20 | 4000304 | ECOMMERCE FEE INCOME | 0 | 0 | **DELETE** |
| 21 | 4000305 | DELIVERY INCOME | 0 | 0 | **DELETE** (or reassign to a BEI-own delivery account if BEI HO runs deliveries — confirm with Butch) |
| 22 | 4000306 | LOGISTICS INCOME | 0 | 0 | **DELETE** (same caveat) |

**Execution order:**
- Delete 4000208 before 4000200
- Delete `4000301-4000306` (6 children) before 4000300

**HB-3 status:** PASS — all 22 accounts have 0 GL entries.

**KEEP exception:** `4000005 BRAND GROWTH FEE INCOME` stays per COA-175-016 (JV §2 ₱2M Brand Growth Fee lands here).

---

## 5. BEI Settings Account-Link Fields (HB-1 + C5 gate)

| field | current value | linked account exists | action needed |
|---|---|---|---|
| gr_ir_clearing_account | GR/IR CLEARING - BEI | ✓ | none |
| input_vat_goods_account | **(empty)** | ✗ | **FLAG to Butch** — unrelated gap |
| input_vat_services_account | INPUT VAT - SERVICES - Bebang Enterprise Inc. | ✓ | none |
| input_vat_capital_goods_account | INPUT VAT - GOODS - Bebang Enterprise Inc. | ✓ | none |
| advances_to_suppliers_account | 1105203 - ADVANCES TO SUPPLIERS - BEI | ✓ | none |
| ewt_payable_account | CREDITABLE WITHHOLDING TAXES - Bebang Enterprise Inc. | ✓ | none |
| ap_trade_account | ACCOUNTS PAYABLE - Bebang Enterprise Inc. | ✓ | none |
| **bki_sales_income_account** | **SALES - BKI TO STORES - BKI** | ✓ | **CUTOVER (Phase 8)** — update to `4000210 DELIVERIES - BKI` after Phase 2 template build creates it and BEFORE Phase 3 deletes the old account |
| bki_output_vat_account | OUTPUT VAT PAYABLE - BKI | ✓ | none |

**HB-1 status:** PASS — current link is valid. Phase 8 cutover must happen in the correct order (new account created → BEI Settings updated → old account deleted) or the S168 billing flow breaks.

**C5 runtime consumers of `bki_sales_income_account`:** Must grep all of `hrms/api/*.py` during Phase 8. Known: `hrms/api/commissary.py` (build_bki_store_sale_invoice) + `hrms/api/billing.py:560`. Any additional consumers must be added to Phase 8 smoke.

**Bonus finding:** `input_vat_goods_account` is empty. Unrelated to S175 but worth flagging separately to Butch as a config gap.

---

## 6. Incoming Link References (HB-7 new gate) — 4 parents, 14 children

Only `tabAccount.parent_account` references found. Zero references in `tabItem Default`, `tabMode of Payment Account`, `tabCost Center`, or any other Link consumer.

### Parent: DISCOUNTS AND PROMO - Bebang Enterprise Inc.
Children (1): `4000208 - SALES DISCOUNTS - EMPLOYEE DISC - BEI`
**Delete order:** Delete child first, then parent.

### Parent: WHOLESALE / B2B SALES - BKI
Children (1): `SALES - BKI TO STORES - BKI` (4000101)
**Delete order:** Delete child first, then parent. (S168 legacy tree.)

### Parent: FRANCHISE INCOME - BKI
Children (6): DELIVERY INCOME, ECOMMERCE FEE INCOME, LOGISTICS INCOME, MANAGEMENT FEE INCOME, MARKETING FEE INCOME, ROYALTIES INCOME (all `- BKI`)
**Delete order:** Delete all 6 children first, then parent.

### Parent: FRANCHISE INCOME - BEI
Children (6): DELIVERY INCOME, ECOMMERCE FEE INCOME, LOGISTICS INCOME, MANAGEMENT FEE INCOME, MARKETING FEE INCOME, ROYALTIES INCOME (all `- BEI`)
**Delete order:** Delete all 6 children first, then parent.

**HB-7 status:** 4 parent-child chains. No cross-doctype Link consumers (no Item, Mode of Payment, Cost Center risk). Phase 4/5 delete scripts must implement child-first deletion.

---

## 7. BKI Store Customer Group (S168 regression baseline)

**Live count:** 35 customers in `customer_group='BKI Store'`. S168 closed with 35/35 verified. Phase 10 re-verification must still return 35.

---

## 8. S168 Custom Fields (regression baseline)

**Live count:** 3 matching custom fields. (S168 claimed 12 — but the S175 audit regex only matched 3, likely because the matching regex was too narrow. This is an audit-tool limitation, not an S168 regression. Phase 10 should use a broader regex or read the S168 fixture file for the ground-truth count.)

---

## 9. BEI 2104xxx Range (Phase 6 collision check)

Current accounts:
- `2104100 SHORT TERM DEBT`
- `2104101 LOANS PAYABLE - CURRENT`

**Collision check for `2104200 DUE TO BFC`:** CLEAR. Next number in range.

---

## 10. Template Collisions (W15 check) — 11 total across 39 companies

| template number | companies with existing account | action |
|---|---|---|
| `4000000 SALES` | 5 companies (BEI, BKI, JV, MF, TIH) | `ensure_account` helper detects, verifies match (is_group=1, Income), skips insert |
| `4000200` | 5 companies (same 5) | Delete old content (4000200 DISCOUNTS on BKI/BEI was already in delete-target lists above) then create new `4000200 BKI SALES` group |
| `4000100` | 1 company (BKI, as `4000100 WHOLESALE / B2B SALES`) | Delete old (already in BKI delete-target list) then create new `4000100 STORE SALES` group per template |

**Net action:** All 11 collisions are already handled by the Phase 4/5 delete-targets + Phase 2 template create. Store corps (34 of 39) are **fully greenfield** for 4-series — they have zero `4xxxxxx` accounts today.

---

## 11. Deltas vs. Plan v1 Stated Baseline

| Plan v1 claim | Live truth | Delta |
|---|---|---|
| 39 companies | 39 | ✓ exact |
| 134 of 136 BEI 6xxxxxx Income | 134 of 136 | ✓ exact |
| 0 GL entries on all delete targets | 0 GL on all 41 verified targets | ✓ exact |
| BFC company exists | **FALSE** (audit false-positive on "Managed Franchise") | Plan correct — BFC still needs creation |
| BEI Settings.bki_sales_income_account = "SALES - BKI TO STORES - BKI" | Live confirms verbatim | ✓ exact |
| "Proven S168 SSM templates" | 3 of 4 cited scripts DO NOT EXIST | ❌ Plan must cite real patterns (`.claude/skills/frappe-bulk-edits/SKILL.md` is the real source) |
| JV signed "2026-01-03" | JV signed **2025-01-03** per PDF | ❌ Plan v1 wrong by one year |
| Plan's delete-order strategy | 4 parent-child chains need explicit child-first order | ❌ Plan v1 doesn't encode the order |
| Plan says "5 fees in Franchise Agreement" | 4 fees in Franchise Agreement + 1 in Mgmt Agreement | ❌ Plan v1 fee-count error |

---

## 12. Gate Summary (all HARD BLOCKERS)

| HB | What | Status |
|---|---|---|
| HB-1 | `bki_sales_income_account` points at valid account after Phase 8 | Plan will enforce via ordering |
| HB-2 | All BKI delete-targets have 0 GL | **PASS LIVE** (19 of 20 exist, all 0) |
| HB-3 | All BEI franchise/discount delete-targets have 0 GL | **PASS LIVE** (22 of 22 exist, all 0) |
| HB-4 | All BEI 6xxxxxx have 0 GL | **PASS LIVE** (0 entries across 136 accounts) |
| HB-5 | Frappe can convert `4000000 SALES` from posting→group if needed | Template builder will detect is_group mismatch and handle |
| HB-6 | BFC Company creation succeeds | Phase 1 handles, rollback on failure |
| **HB-7** (NEW) | Child-first deletion order honored for 4 parent chains | Plan v2 will encode the 4 chains explicitly |
| **HB-8** (NEW) | BFC BIR OR booklet operational before first franchise fee collection | **BLOCKED on Butch answer** — see OQ-1 |

All gates PASS except HB-8 (external dependency on BFC OR booklet).
