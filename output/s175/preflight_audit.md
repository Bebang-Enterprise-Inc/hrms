# S175 Phase A — Preflight COA Audit

**Generated:** 2026-04-09T05:24:28.874933Z
**Source:** hq.bebang.ph (live, read-only via SSM)

## 1. Companies

- Total Frappe companies: **39**
- BFC company exists: **True**

| name | abbr | tax_id | currency |
|---|---|---|---|
| Bebang Enterprise Inc. | BEI |  | PHP |
| JV | JV |  | PHP |
| Managed Franchise | MF |  | PHP |
| Triple I Holdings | TIH |  | PHP |
| Bebang Kitchen Inc. | BKI |  | PHP |
| BEBANG ARANETA GATEWAY | BAG |  | PHP |
| BEBANG AYALA SOLENAD | BAS |  | PHP |
| BEBANG BF HOMES INC. | BBHI |  | PHP |
| BEBANG D'VERDE | BDV |  | PHP |
| BEBANG EVER GOTESCO COMMONWEALTH | BEGC |  | PHP |
| BEBANG FESTIVAL INC. | BFI |  | PHP |
| BEBANG FT INC. | BFI2 |  | PHP |
| BEBANG GRAND CENTRAL INC. | BGCI |  | PHP |
| BEBANG LCT INC. | BLI |  | PHP |
| BEBANG MARILAO INC. | BMI |  | PHP |
| BEBANG MARKET MARKET INC. | BMMI |  | PHP |
| BEBANG MEGA INC. | BMI2 |  | PHP |
| BEBANG NORTH EDSA INC. | BNEI |  | PHP |
| BEBANG PASEO INC. | BPI |  | PHP |
| BEBANG PITX INC. | BPI2 |  | PHP |
| BEBANG ROBINSONS GALLERIA SOUTH | BRGS |  | PHP |
| BEBANG SM BICUTAN INC. | BSBI |  | PHP |
| BEBANG SM CALOOCAN | BSC |  | PHP |
| BEBANG SM CLARK | BSC2 |  | PHP |
| BEBANG SM MARIKINA INC. | BSMI |  | PHP |
| BEBANG SM SANGANDAAN | BSS |  | PHP |
| BEBANG SM SJDM | BSS2 |  | PHP |
| BEBANG SM TAYTAY | BST |  | PHP |
| BEBANG SMEO INC. | BSI |  | PHP |
| BEBANG SMM INC. | BSI2 |  | PHP |
| BEBANG SMOA INC. | BSI3 |  | PHP |
| BEBANG SMV INC. | BSI4 |  | PHP |
| BEBANG STARMALL ALABANG INC. | BSAI |  | PHP |
| BEBANG THE GRID FOOD MARKET | BTGF |  | PHP |
| BEBANG TOMAS MORATO | BTM |  | PHP |
| BEBANG UP TOWN CENTER INC. | BUTC |  | PHP |
| BEBANG VENICE GRAND CANAL INC. | BVGC |  | PHP |
| BEBANG VISTAMALL | BV |  | PHP |
| DMD HOLDINGS INC. | DHI |  | PHP |

## 2. BEI 6xxxxxx breakdown (HB-4)

- Total 6xxxxxx accounts: **136**
- Total 6xxxxxx GL entries: **0** (HB-4 PASS if 0)

| root_type | report_type | count |
|---|---|---|
| Expense | Profit and Loss | 2 |
| Income | Profit and Loss | 134 |

## 3. BKI delete-targets (HB-2)

| account_number | exists | gl_entries | children | name | root_type | gate |
|---|---|---|---|---|---|---|
| 4000001 | True | 0 | 0 | IN-STORE SALES | Income | PASS |
| 4000002 | True | 0 | 0 | ONLINE SALES | Income | PASS |
| 4000100 | True | 0 | 1 | WHOLESALE / B2B SALES | Income | PASS |
| 4000101 | True | 0 | 0 | SALES - BKI TO STORES | Income | PASS |
| 4000200 | True | 0 | 0 | DISCOUNTS AND PROMO | Income | PASS |
| 4000201 | True | 0 | 0 | SALES DISCOUNT DUE TO FREE HALOHALO | Income | PASS |
| 4000202 | True | 0 | 0 | SALES DISCOUNT OF SENIOR CITIZENS | Income | PASS |
| 4000203 | True | 0 | 0 | SALES DISCOUNTS OF PWDS | Income | PASS |
| 4000204 | True | 0 | 0 | SALES DISCOUNTS OF STAFFS AND EMPLOYEES | Income | PASS |
| 4000205 | True | 0 | 0 | SALES DISCOUNTS FROM VAT OF PWD | Income | PASS |
| 4000206 | True | 0 | 0 | SALES DISCOUNTS FROM VAT OF SENIOR CITIZENS | Income | PASS |
| 4000207 | True | 0 | 0 | SALES REFUNDS TO CUSTOMER | Income | PASS |
| 4000208 | False | 0 | 0 |  |  | N/A (absent) |
| 4000300 | True | 0 | 6 | FRANCHISE INCOME | Income | PASS |
| 4000301 | True | 0 | 0 | ROYALTIES INCOME | Income | PASS |
| 4000302 | True | 0 | 0 | MARKETING FEE INCOME | Income | PASS |
| 4000303 | True | 0 | 0 | MANAGEMENT FEE INCOME | Income | PASS |
| 4000304 | True | 0 | 0 | ECOMMERCE FEE INCOME | Income | PASS |
| 4000305 | True | 0 | 0 | DELIVERY INCOME | Income | PASS |
| 4000306 | True | 0 | 0 | LOGISTICS INCOME | Income | PASS |

_Summary (HB-2): 19 of 20 exist, 19 have 0 GL entries._

## 4. BEI delete/migrate-targets (HB-3)

| account_number | exists | gl_entries | children | name | root_type | gate |
|---|---|---|---|---|---|---|
| 4000001 | True | 0 | 0 | IN-STORE SALES | Income | PASS |
| 4000002 | True | 0 | 0 | ONLINE SALES | Income | PASS |
| 4000003 | True | 0 | 0 | ROYALTY INCOME | Income | PASS |
| 4000004 | True | 0 | 0 | MANAGEMENT FEE INCOME | Income | PASS |
| 4000005 | True | 0 | 0 | BRAND GROWTH FEE INCOME | Income | PASS |
| 4000006 | True | 0 | 0 | MARKETING FEE INCOME | Income | PASS |
| 4000200 | True | 0 | 1 | DISCOUNTS AND PROMO | Income | PASS |
| 4000201 | True | 0 | 0 | SALES DISCOUNT DUE TO FREE HALOHALO | Income | PASS |
| 4000202 | True | 0 | 0 | SALES DISCOUNT OF SENIOR CITIZENS | Income | PASS |
| 4000203 | True | 0 | 0 | SALES DISCOUNTS OF PWDS | Income | PASS |
| 4000204 | True | 0 | 0 | SALES DISCOUNTS OF STAFFS AND EMPLOYEES | Income | PASS |
| 4000205 | True | 0 | 0 | SALES DISCOUNTS FROM VAT OF PWD | Income | PASS |
| 4000206 | True | 0 | 0 | SALES DISCOUNTS FROM VAT OF SENIOR CITIZENS | Income | PASS |
| 4000207 | True | 0 | 0 | SALES REFUNDS TO CUSTOMER | Income | PASS |
| 4000208 | True | 0 | 0 | SALES DISCOUNTS - EMPLOYEE DISC | Income | PASS |
| 4000300 | True | 0 | 6 | FRANCHISE INCOME | Income | PASS |
| 4000301 | True | 0 | 0 | ROYALTIES INCOME | Income | PASS |
| 4000302 | True | 0 | 0 | MARKETING FEE INCOME | Income | PASS |
| 4000303 | True | 0 | 0 | MANAGEMENT FEE INCOME | Income | PASS |
| 4000304 | True | 0 | 0 | ECOMMERCE FEE INCOME | Income | PASS |
| 4000305 | True | 0 | 0 | DELIVERY INCOME | Income | PASS |
| 4000306 | True | 0 | 0 | LOGISTICS INCOME | Income | PASS |

_Summary (HB-3): 22 of 22 exist, 22 have 0 GL entries._

## 5. BEI Settings Account-link fields

| field | value | linked account exists |
|---|---|---|
| gr_ir_clearing_account | GR/IR CLEARING - BEI | True |
| input_vat_goods_account |  | False |
| input_vat_services_account | INPUT VAT - SERVICES - Bebang Enterprise Inc. | True |
| input_vat_capital_goods_account | INPUT VAT - GOODS - Bebang Enterprise Inc. | True |
| advances_to_suppliers_account | 1105203 - ADVANCES TO SUPPLIERS - BEI | True |
| ewt_payable_account | CREDITABLE WITHHOLDING TAXES - Bebang Enterprise Inc. | True |
| ap_trade_account | ACCOUNTS PAYABLE - Bebang Enterprise Inc. | True |
| bki_sales_income_account | SALES - BKI TO STORES - BKI | True |
| bki_output_vat_account | OUTPUT VAT PAYABLE - BKI | True |

## 6. Incoming Link references to delete-targets (HB-7)

### DISCOUNTS AND PROMO - Bebang Enterprise Inc.
- **tabAccount.parent_account** (1): 4000208 - SALES DISCOUNTS - EMPLOYEE DISC - BEI

### FRANCHISE INCOME - BKI
- **tabAccount.parent_account** (6): DELIVERY INCOME - BKI, ECOMMERCE FEE INCOME - BKI, LOGISTICS INCOME - BKI, MANAGEMENT FEE INCOME - BKI, MARKETING FEE INCOME - BKI, ROYALTIES INCOME - BKI

### WHOLESALE / B2B SALES - BKI
- **tabAccount.parent_account** (1): SALES - BKI TO STORES - BKI

### FRANCHISE INCOME - BEI
- **tabAccount.parent_account** (6): DELIVERY INCOME - BEI, ECOMMERCE FEE INCOME - BEI, LOGISTICS INCOME - BEI, MANAGEMENT FEE INCOME - BEI, MARKETING FEE INCOME - BEI, ROYALTIES INCOME - BEI

## 7. BKI Store customer group

- Customers in BKI Store group: **35**

## 8. S168 Custom Fields regression check

- Matching custom fields: **3**

## 9. BEI 2104xxx range

| account_number | account_name | is_group |
|---|---|---|
| 2104100 | SHORT TERM DEBT | 0 |
| 2104101 | LOANS PAYABLE - CURRENT | 0 |

## 10. Template collisions across companies (W15)

- Total template collisions: **11**

### Top companies by collision count

- Bebang Kitchen Inc.: 3
- Bebang Enterprise Inc.: 2
- JV: 2
- Managed Franchise: 2
- Triple I Holdings: 2

### Collisions by template number

- 4000000: 5
- 4000200: 5
- 4000100: 1
