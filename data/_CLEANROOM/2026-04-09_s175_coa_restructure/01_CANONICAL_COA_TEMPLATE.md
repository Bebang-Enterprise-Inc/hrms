# Canonical COA Master Template (S175)

**Source of truth for the 30-account Sales tree + Fork 1 intercompany scaffolding + Butch's reserved expansion slots.**

Applied uniformly to **all 40 Frappe Companies** (39 existing + BFC new). Each company populates only its relevant sub-tree per the fee routing matrix in `02_LOCKED_DECISIONS.md`.

---

## Section A: Sales Tree (4xxxxxx)

### A.1 Top-level structure

```
4000000 SALES (Group, Income)
├── 4000100 STORE SALES (Sub-Group, Income)
│   ├── 4000110 IN-STORE SALES (Posting, Income Account)
│   └── 4000120 ONLINE SALES (Sub-Group, Income)
│       ├── 4000121 BEI WEBSITE (Posting, Income Account)
│       ├── 4000122 FOOD PANDA (Posting, Income Account)
│       ├── 4000123 GRAB (Posting, Income Account)
│       └── 4000124+ [RESERVED for new online platforms] ← Butch's expansion slot
├── 4000200 BKI SALES (Sub-Group, Income)
│   ├── 4000210 DELIVERIES (Posting, Income Account)
│   └── 4000220 LOGISTICS (Sub-Group, Income)
│       ├── 4000221 DELIVERY INCOME (Posting, Income Account)
│       └── 4000222 LOGISTICS INCOME (Posting, Income Account)
├── 4000230 FEES (Sub-Group, Income)
│   ├── 4000231 ROYALTY FEES (Posting, Income Account)
│   ├── 4000232 MANAGEMENT FEES (Posting, Income Account)
│   ├── 4000233 FRANCHISE FEES (Posting, Income Account)
│   ├── 4000234 MARKETING FEES (Posting, Income Account)
│   ├── 4000235 E-COMMERCE FEES (Posting, Income Account)
│   └── 4000236+ [RESERVED for new fees] ← Butch's expansion slot
├── 4000300-4000800 [RESERVED for future revenue streams] ← Butch: "company can use 4000300 group to 4000800 group"
└── 4000900 DISCOUNTS AND PROMO (Sub-Group, Income — contra-revenue, debit normal balance)
    ├── 4000901 SALES DISCOUNT DUE TO FREE HALOHALO
    ├── 4000902 SALES DISCOUNT OF SENIOR CITIZENS
    ├── 4000903 SALES DISCOUNTS OF PWDS
    ├── 4000904 SALES DISCOUNTS OF STAFFS AND EMPLOYEES
    ├── 4000905 SALES DISCOUNTS FROM VAT OF PWD
    ├── 4000906 SALES DISCOUNTS FROM VAT OF SENIOR CITIZENS
    ├── 4000907 SALES REFUNDS TO CUSTOMER
    └── 4000908 SALES DISCOUNTS - EMPLOYEE DISC
```

### A.2 Flat account table (for script generation)

| # | account_number | account_name | parent | is_group | root_type | account_type |
|---|---|---|---|---|---|---|
| 1 | 4000000 | SALES | — | 1 | Income | — |
| 2 | 4000100 | STORE SALES | 4000000 | 1 | Income | — |
| 3 | 4000110 | IN-STORE SALES | 4000100 | 0 | Income | Income Account |
| 4 | 4000120 | ONLINE SALES | 4000100 | 1 | Income | — |
| 5 | 4000121 | BEI WEBSITE | 4000120 | 0 | Income | Income Account |
| 6 | 4000122 | FOOD PANDA | 4000120 | 0 | Income | Income Account |
| 7 | 4000123 | GRAB | 4000120 | 0 | Income | Income Account |
| 8 | 4000200 | BKI SALES | 4000000 | 1 | Income | — |
| 9 | 4000210 | DELIVERIES | 4000200 | 0 | Income | Income Account |
| 10 | 4000220 | LOGISTICS | 4000200 | 1 | Income | — |
| 11 | 4000221 | DELIVERY INCOME | 4000220 | 0 | Income | Income Account |
| 12 | 4000222 | LOGISTICS INCOME | 4000220 | 0 | Income | Income Account |
| 13 | 4000230 | FEES | 4000000 | 1 | Income | — |
| 14 | 4000231 | ROYALTY FEES | 4000230 | 0 | Income | Income Account |
| 15 | 4000232 | MANAGEMENT FEES | 4000230 | 0 | Income | Income Account |
| 16 | 4000233 | FRANCHISE FEES | 4000230 | 0 | Income | Income Account |
| 17 | 4000234 | MARKETING FEES | 4000230 | 0 | Income | Income Account |
| 18 | 4000235 | E-COMMERCE FEES | 4000230 | 0 | Income | Income Account |
| 19 | 4000900 | DISCOUNTS AND PROMO | 4000000 | 1 | Income | — |
| 20 | 4000901 | SALES DISCOUNT DUE TO FREE HALOHALO | 4000900 | 0 | Income | Income Account |
| 21 | 4000902 | SALES DISCOUNT OF SENIOR CITIZENS | 4000900 | 0 | Income | Income Account |
| 22 | 4000903 | SALES DISCOUNTS OF PWDS | 4000900 | 0 | Income | Income Account |
| 23 | 4000904 | SALES DISCOUNTS OF STAFFS AND EMPLOYEES | 4000900 | 0 | Income | Income Account |
| 24 | 4000905 | SALES DISCOUNTS FROM VAT OF PWD | 4000900 | 0 | Income | Income Account |
| 25 | 4000906 | SALES DISCOUNTS FROM VAT OF SENIOR CITIZENS | 4000900 | 0 | Income | Income Account |
| 26 | 4000907 | SALES REFUNDS TO CUSTOMER | 4000900 | 0 | Income | Income Account |
| 27 | 4000908 | SALES DISCOUNTS - EMPLOYEE DISC | 4000900 | 0 | Income | Income Account |

**27 accounts.** Applied to every company.

---

## Section B: Fork 1 Intercompany Scaffolding

These are **NOT in the Sales tree** — they live in their entity's existing Current Liabilities (2xxxxxx) or Current Assets (1xxxxxx) trees. They enable the collection-agent accounting per `04_INTERCOMPANY_ACCOUNTING.md`.

### B.1 On BEI's books

| account_number | account_name | parent | is_group | root_type | account_type | purpose |
|---|---|---|---|---|---|---|
| 2104200 | DUE TO BFC | (BEI current liabilities parent TBD in Phase 0) | 0 | Liability | Payable | Cash collected on BFC's behalf, not recognized as BEI revenue |

**Phase 0 audit confirmed `2104100 SHORT TERM DEBT` and `2104101 LOANS PAYABLE - CURRENT` exist.** `2104200` is in the same range with no collision.

### B.2 On BFC's books

| account_number | account_name | parent | is_group | root_type | account_type | purpose |
|---|---|---|---|---|---|---|
| 1104200 | DUE FROM BEI | (BFC current assets parent — created by Phase 1 BFC COA build) | 0 | Asset | Receivable | Mirror of BEI's 2104200 — BFC's receivable from BEI |
| 2102205 | OUTPUT VAT PAYABLE | (BFC current liabilities parent) | 0 | Liability | Tax | 12% Output VAT on franchise fees invoiced by BFC during Fork 1 interim |

### B.3 On BFC's books (standard COA, not in Sales tree)

BFC is VAT-registered per BIR 2303. It needs a normal input VAT account + cash on hand + receivables hierarchy. These are created by Frappe's Standard Chart of Accounts template during Phase 1 Company creation.

---

## Section C: Butch's expansion slots (reserved ranges)

Per Butch's 2026-04-08 10:18 AM chat, the following ranges are **explicitly reserved for future use**. Execution scripts must NOT populate these, and audits must not flag them as missing.

| Range | Reserved for | Source quote |
|---|---|---|
| `4000124-4000199` | New online platforms (e.g., ShopeeFood, Kumu) | "4000124+ for new Online Platform" |
| `4000236-4000299` | New fees charged (e.g., training fees, equipment fees) | "4000236+ for new Fees to be charged" |
| `4000300-4000800` | New revenue streams | "the company can use the 4000300 group to 4000800 group" (2026-04-08 21:48 PHT) |

---

## Section D: Company-specific population rules

Every company gets the FULL 27-account structural tree from Section A. Only the posting leaves that a company actually uses will receive GL entries over time.

| Company | Populates (posts into) | Keeps empty (structural only) |
|---|---|---|
| **BEI** (Bebang Enterprise Inc.) | `4000100` tree (STORE SALES + ONLINE SALES) for BEI's direct retail, `4000900` tree (discounts), AND during Fork 1 interim: **no entries to `4000231-4000235`** (those are BFC's per collection-agent letter) | `4000200` tree (BKI-specific) |
| **BKI** (Bebang Kitchen Inc.) | `4000200` tree (DELIVERIES + LOGISTICS sub-groups) | `4000100`, `4000230`, `4000900` trees — BKI is commissary, no retail + no franchise income |
| **BFC** (Bebang Franchise Corp., new) | `4000230` tree (ROYALTY + MANAGEMENT + FRANCHISE + MARKETING + E-COMMERCE FEES) from day 1 via collection-agent model | `4000100`, `4000200`, `4000900` trees |
| **JV** (existing joint venture entity) | `4000100` tree (store retail) — JV fees flow to BEI per signed JV Agreement, not to JV itself | `4000200`, `4000230`, `4000900` trees |
| **Managed Franchise (MF)** | `4000100` tree (store retail under management) | `4000200`, `4000230`, `4000900` trees |
| **Triple I Holdings (TIH)** | Structural only — holdings entity, no direct sales | Everything |
| **DMD Holdings (DHI)** | Structural only — holdings entity, no direct sales | Everything |
| **32 individual store corps** (e.g., BEBANG SM BICUTAN INC.) | `4000100` tree (store's own retail + online) + `4000900` tree (store's own discounts) | `4000200`, `4000230` trees |

---

## Section E: Total accounts created across the Group

- **27 template accounts × 40 companies = 1,080 account-position-assertions**
- **Plus Fork 1 additions:** `2104200` on BEI + `1104200` on BFC + `2102205` on BFC = 3 extra
- **Grand total: 1,083 account positions** to create or verify

Any script that runs fewer assertions is incomplete.

---

## Section F: What must NEVER exist on BEI after S175

1. `4000231 ROYALTY FEES - BEI` populated with GL entries (they belong to BFC per Fork 1)
2. `4000232 MANAGEMENT FEES - BEI` populated with GL entries
3. `4000233 FRANCHISE FEES - BEI` populated with GL entries
4. `4000234 MARKETING FEES - BEI` populated with GL entries — EXCEPT JV 5% marketing from Grand Central Gabaldon, which contractually flows to BEI per signed JV §8.1
5. `4000235 E-COMMERCE FEES - BEI` populated with GL entries — EXCEPT JV 5% e-comm per signed JV §9.1

**JV caveat:** The JV's 5% marketing + 5% e-comm are contractually BEI revenue (signed agreement). These ARE posted to BEI's `4000234`/`4000235` during Fork 1 and permanently. Only BFC franchisee fees are collection-agent-only.

This creates one asymmetry worth flagging: BEI's `4000234`/`4000235` will have entries (from JV), while BEI's `4000231`/`4000232`/`4000233` must stay empty (BFC franchise-only fees). Finance reports filtering by Customer Group (`JV Partners` vs `BFC Franchisees`) can separate them cleanly.
