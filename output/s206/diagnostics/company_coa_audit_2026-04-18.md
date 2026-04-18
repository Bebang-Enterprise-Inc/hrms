# S206 Phase 0 — Company COA Audit (2026-04-18)

**Source:** live Frappe hq.bebang.ph via SSM
**Purpose:** verify each in-scope Company has the accounts needed for paired-JE cost-sharing

## In-scope Companies (51 total)

- 49 Store Companies (entity_category='Store')
- BEBANG ENTERPRISE INC. (parent/HO)
- BEBANG KITCHEN INC. (commissary/BKI)

## Findings

### ✅ Salaries Expense accounts
Every in-scope Company has at least 1 Salaries Expense account. Store Companies have exactly 1. Parent/BKI/Irresistible have 24-26 (legacy COA). Sufficient for S206.

### ✅ Default Cost Center
Every Company has `cost_center = 'Main - <abbr>'` set except 4 stores that post under BEI parent directly (ROBINSONS ANTIPOLO, SM MANILA, SM MEGAMALL, SM SOUTHMALL — their cost_center is NULL on Company doc). Phase 4 seeder will fall back to BEI parent's `Main - BEI` for those.

### ✅ Default Payroll Payable Account
Every Company has `default_payroll_payable_account` set to a concrete account (`Payroll Payable - <abbr>`), except the same 4 BEI-direct stores + BKI + BEBANG ENTERPRISE INC. parent. Not a blocker — S206 doesn't post to this account (it's a Salaries Expense allocation, not a payroll liability).

### ❌ Due From / Due To Group Entities accounts — **MOSTLY MISSING**

S175 seeded bilateral BEI-BFC accounts:
- BEI has `2104200 - DUE TO BFC - BEI` (Payable)
- BFC has `1104200 - DUE FROM BEI - BFC` (Receivable)

A few BEI-direct stores (ROBINSONS ANTIPOLO, SM MANILA, SM MEGAMALL, SM SOUTHMALL) also have a `2104200` code, but these are ambiguous and not the generic group account.

**Required before S206 first apply:** Phase 4 on_demand seeder must create:
- `2104200 - DUE TO GROUP ENTITIES - <abbr>` (Payable) on each of 51 Companies
- `1104200 - DUE FROM GROUP ENTITIES - <abbr>` (Receivable) on each of 51 Companies

Total new accounts: **102** (51 × 2).

## Gap summary

| Company class | Count | Salaries OK? | Due From/To? | Action needed |
|---|---|---|---|---|
| Store | 49 | ✅ all have | ❌ mostly missing | Seed 98 accounts (49 × 2) |
| BEI parent | 1 | ✅ 26 accounts | ⚠️ has 2104200 (bilateral BFC) | Seed 2 generic accounts alongside |
| BKI | 1 | ✅ 24 accounts | ❌ none | Seed 2 accounts |

No HARD BLOCKER (<10 Companies with gaps). Proceeding to Phase 1.

## Phase 0 HARD BLOCKER status

- TP Policy exists? **YES** (committed `docs/compliance/s206-transfer-pricing-policy.md`)
- TP Policy signed by Finance? **NO — pending Denise signoff before first apply**
- Account gaps <10 Companies? **PASS** (all 51 need seeding but seeder is ready in Phase 4)
