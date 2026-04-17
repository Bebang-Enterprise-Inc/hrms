# S201 Per-Store Employee Billing Foundation — PH Finance & Compliance Audit

**Audited by:** PH Finance & Compliance Domain Auditor
**Date:** 2026-04-17 PHT
**Plan file:** `docs/plans/2026-04-17-sprint-201-per-store-employee-billing-foundation.md`
**Plan status at audit time:** GO

---

## Finding 1 — SSS / PhilHealth / Pag-IBIG Remittance Split Across 49+ Employers

**Severity:** [CRITICAL]

**Evidence from plan:**
LD-1 moves ~510 store employees from `BEBANG ENTERPRISE INC.` (one employer) to 49 per-store child Companies. Each child Company in ERPNext has its own `branch_tin` and `bir_rdo_code` (created by S188). The plan's Phase 7 backfill patch will execute this change with direct SQL on Active employees.

**Issue:**
SSS, PhilHealth, and Pag-IBIG statutory filings are employer-account-specific:
- SSS R-3 (Monthly Contribution Collection List), SSS R-5 (remittance), PhilHealth RF-1, and Pag-IBIG MCRF are all filed per-employer. Each employer has its own SSS Employer Number, PhilHealth Employer Number, and HDMF Employer ID.
- Moving 510 employees across 49 new "employers" mid-year (April 17, 2026) means:
  - Each of the 49 store Companies needs to register as a NEW employer with SSS, PhilHealth, and HDMF — or the remittances will post against invalid/unfiled employer accounts.
  - Monthly filings that were already submitted for Q1 2026 under `BEBANG ENTERPRISE INC.` cannot be retroactively split — those employees' contributions are already on the parent employer's record.
  - Any APRIL 2026 contribution filings (due May 10–31) must decide: does `SM MEGAMALL - BEBANG ENTERPRISE INC.` file its own R-3/RF-1, or does the parent still remit? The plan has no answer.
- The plan's design rationale (Design Rationale section) correctly rejects Option C (shift-level payslip splitting) for this statutory reason, but does NOT address that Option A itself creates 49 new "employers of record" for statutory purposes.

**Recommended amendment:**
Add a Phase 0.5 or pre-requisite gate:
1. Verify whether the 49 child Companies have SSS, PhilHealth, and HDMF employer registration numbers. If they do NOT, the backfill must be BLOCKED until registration is complete — payroll processed under an unregistered employer account is a statutory violation.
2. If BEI's intent is to keep ONE employer for statutory remittances (the parent `BEBANG ENTERPRISE INC.`) and use child Companies only for P&L cost-center allocation (not legal employment), then `Employee.company` must NOT change for payroll purposes — only cost center attribution changes. In that case, re-evaluate whether changing Employee.company at all is the right mechanism, or whether inter-Company JE at month-end (S202 approach) should apply to labor costs too.
3. Add an explicit decision record: "Are the 49 store Companies registered employers for SSS/PhilHealth/HDMF? YES/NO. If NO, backfill is deferred until registration complete."

---

## Finding 2 — BIR Form 2316 Employer Change Mid-Year

**Severity:** [CRITICAL]

**Evidence from plan:**
LD-6 says data starts April 1, 2026. Backfill runs April 17, 2026. S188 gave each store Company its own `branch_tin` and `bir_rdo_code`. Phase 7 will change `Employee.company` (the ERPNext employer) for ~510 employees mid-tax-year.

**Issue:**
BIR Form 2316 (Certificate of Compensation Payment / Tax Withheld) is issued by the employer of record at year-end (or upon separation). For 2026:
- January 1 – April 17: employer of record = `BEBANG ENTERPRISE INC.` (TIN/RDO of the parent)
- April 17 onwards: employer of record = `<STORE> - BEBANG ENTERPRISE INC.` (store TIN/RDO)
- This creates a **dual-employer 2316 situation for calendar year 2026**: two 2316s must be issued per affected employee (one from parent for Jan–Apr, one from store Company for May–Dec). This is legal but requires the receiving employer (store Company) to properly account for prior-employer withholding when computing annualized WT.
- The alphanumeric tax code (ATC) for the withholding agent changes when the employer's TIN changes. The receiving employer's ATC 1601-C filing must reflect only the months they were employer of record.
- Additionally: BIR RMC (Revenue Memorandum Circular) practice requires the new employer to request a Certificate of Prior Employment Compensation (essentially informal transfer of 2316 data) so the annualized withholding is not recomputed from zero in April.
- The plan has NO mention of dual-2316 handling, annualized WT re-computation upon company change, or ATC 1601-C impact.

**Recommended amendment:**
1. Add a Finance/HR action item: for every employee whose `Employee.company` changes in the backfill, the payroll system must record "prior employer compensation" (total taxable compensation Jan–Apr from the parent Company) into the new employer's payroll record to avoid over-withholding in the second half of the year.
2. Add a note that the parent `BEBANG ENTERPRISE INC.` must issue interim 2316 certificates for April 2026 cutoff to all transferred employees, and the store Companies must accept and incorporate those certificates for annualized WT computation.
3. State explicitly in the plan whether ERPNext HRMS handles dual-employer 2316 within one system (it can, since both Companies are in the same ERPNext instance — but this must be verified and documented).

---

## Finding 3 — BIR 1905 / Certificate of Registration Update Not Addressed

**Severity:** [WARNING]

**Evidence from plan:**
S188 created 49 Companies each with `branch_tin` and `bir_rdo_code`. Plan does not mention BIR registration obligations for those Companies as employers.

**Issue:**
When a Company begins withholding employee compensation (becomes an employer), BIR requires:
- The Company must be registered as a withholding agent (BIR Form 1903 — Application for Registration for Corporations/Partnerships).
- If already registered but not yet a withholding-agent employer, BIR Form 1905 (Update of Registration Information) is required to add "Withholding Agent" as a tax type.
- Monthly/quarterly 1601-C (Monthly Remittance Return of Income Taxes Withheld on Compensation) filings begin from the first month the Company has employees.
- If any of the 49 store Companies are NOT yet registered as withholding agents, withholding compensation taxes before registration is a BIR compliance violation.

**Recommended amendment:**
Add a Pre-backfill Compliance Checklist item: "Confirm all 49 store Companies are registered with BIR as withholding agents (1601-C filers). Block backfill for any Company not yet registered."

---

## Finding 4 — Draft Salary Slips for April 2026 Pre-Backfill

**Severity:** [CRITICAL]

**Evidence from plan:**
Phase 7 (Employee.company backfill) runs on April 17, 2026. The plan's completion requirement (Requirements Regression Checklist item 8) checks that a NEW Salary Slip posts to the store Company — but does not address Salary Slips already in Draft/Submitted state for the April 2026 payroll period.

**Issue:**
Frappe HRMS Salary Slip stores `company` at creation time. If a payroll run was already started for April 1–15 (semi-monthly cutoff) before April 17:
- All Draft Salary Slips created pre-backfill will have `company = BEBANG ENTERPRISE INC.`
- The backfill changes `Employee.company` but does NOT retroactively update existing Draft/Submitted Salary Slips
- Submitting those pre-existing Draft Slips AFTER the backfill will post GL entries to the PARENT company's books, not the store Company — silently defeating the entire purpose of S201 for April 2026
- Salary Slips in Submitted state cannot be amended without cancellation — any already-submitted April slips on parent Company will require cancel → repost cycle

**Recommended amendment:**
Add a mandatory Phase 6.5 (pre-backfill audit):
1. Query: `SELECT name, employee, company FROM tabSalary Slip WHERE docstatus IN (0,1) AND start_date >= '2026-04-01'`
2. If ANY Draft (docstatus=0) slips exist for April: CANCEL THEM before running backfill. Do not submit until Employee.company is updated.
3. If ANY Submitted (docstatus=1) slips exist for April on the parent Company: flag to Sam for a decision — cancel/repost or accept that April's first cutoff stays on parent.
4. Add this to the Requirements Regression Checklist.

---

## Finding 5 — BIR Form 2307 (Creditable Withholding Tax Certificate) — Cross-Company Impact

**Severity:** [INFO]

**Evidence from plan:**
Plan does not address supplier-facing withholding. The change affects Employee.company only.

**Issue:**
BIR Form 2307 (Certificate of Creditable Tax Withheld at Source) is issued by the withholding agent (the buyer/payor Company) to suppliers. When a store Company is the employer, any purchases or expense reimbursements originating from that store Company must issue 2307 from the store Company's TIN — not the parent's TIN.

However, S201 only changes Employee.company for payroll purposes. Purchase Invoices, Expense Claims, and supplier payments remain on whatever Company the Purchase Invoice was created against. There is no cross-Company 2307 impact from S201 alone. The impact would arise if expense claims by store employees are re-routed to their new Company in a future sprint.

**Recommended amendment:**
No immediate action needed for S201 scope. Document as a known follow-up: "Expense Claims by store employees currently post to BEI parent. When expense management is brought into S202+ scope, 2307 issuance must shift to the store Company TIN."

---

## Finding 6 — Leave Balance Carryover When Employee.company Changes

**Severity:** [WARNING]

**Evidence from plan:**
Phase 4 sets Employee.validate() to derive Company from branch/department. Phase 7 bulk-updates Employee.company via direct SQL. Neither phase mentions Leave Allocations or Leave Balances.

**Issue:**
In ERPNext/HRMS, Leave Allocation records are linked to Employee (by `employee` name field) and to `company` (in some versions). Critically:
- Leave Policies and Leave Period are defined at the Company level in ERPNext — when `Employee.company` changes, the Leave Policy assignment may reference the old Company's Leave Period.
- Annual Leave allocations for 2026 were created when all employees were under `BEBANG ENTERPRISE INC.`. If the Leave Period for the store Companies is different (or not yet created), leave balance lookups may return zero or throw errors for store employees.
- The backfill uses direct SQL (bypassing `validate()`), which means the `derive_company_from_branch` hook will NOT fire for historical Leave Allocation records — they remain on the parent Company.
- DOLE Republic Act 9292 and the Labor Code mandate that accrued leave credits survive employer entity changes for the same economic unit — they cannot be reset to zero simply because the billing Company changed.

**Recommended amendment:**
1. Before backfill, run: `SELECT employee, company, leave_type, total_leaves_allocated, total_leaves_taken FROM tabLeave Allocation WHERE docstatus=1 AND from_date >= '2026-01-01'`
2. Verify that Leave Period records exist for all 49 store Companies (or confirm ERPNext resolves leave balance from Employee rather than Company-level period).
3. If store Companies do not have Leave Period records, create them before backfill or freeze leave for affected employees during transition.
4. Add to Requirements Regression Checklist: "Leave balance for a transferred store employee returns the correct accrued balance post-backfill."

---

## Finding 7 — Cost Center Assignment on Salary Slips After Company Change

**Severity:** [WARNING]

**Evidence from plan:**
Requirements Regression Checklist item 8 states: "Salary Slip generated against a store employee posts to the store's Company (not parent)." L3-6 verifies `Slip.company = store's Company` and "Journal Entry posts to that Company's books." However, Cost Center is NOT verified.

**Issue:**
In ERPNext HRMS, Salary Slip GL entries (debit: Salary Expense, credit: Payable Account) use Cost Center from `Employee.payroll_cost_center` or the Company's default Cost Center. When `Employee.company` changes:
- The store Company's Cost Center tree may not include the same Cost Center as was previously assigned to the employee.
- `Employee.payroll_cost_center` may still point to a BEI parent Cost Center (e.g., `Main - BEI`), not a store-level Cost Center (e.g., `SM Megamall - SMBL`).
- A Salary Slip posting to `SM MEGAMALL - BEBANG ENTERPRISE INC.` company but with Cost Center `Main - BEI` will fail GL validation or post to the wrong Cost Center tree.
- The plan's design rationale (Phase 7) mentions cost center stamping in S202 (from punch data), but does not address the default Cost Center for the April 2026 payroll cycle which is the FIRST payroll under the new Company structure.

**Recommended amendment:**
1. Add to Phase 7: check `Employee.payroll_cost_center` for all ~510 affected employees. If it references a BEI parent Cost Center, update to the store Company's default Cost Center as part of the backfill.
2. Add to L3-6 verification: explicitly check `Salary Slip.cost_center` (or the GL entry's `cost_center`) to confirm it maps to the store Company's cost center, not the parent.
3. Add to Requirements Regression Checklist: "Salary Slip for a store employee uses a Cost Center belonging to the store Company's Cost Center tree."

---

## Finding 8 — HDMF (Pag-IBIG) — 49 Employer Sub-Accounts Required

**Severity:** [CRITICAL]

**Evidence from plan:**
Plan moves 510 employees across 49 Companies. No mention of HDMF employer registration.

**Issue:**
HDMF (Home Development Mutual Fund / Pag-IBIG) employer accounts are per-Company. For BEI to remit Pag-IBIG contributions under each store Company:
- Each of the 49 store Companies needs a HDMF Employer Registration Number (ER Number).
- Monthly Contribution Collection List (MCCL) must be filed per employer.
- HDMF accepts batch remittance via HDMF I-Collect, but each batch must be tagged to the correct employer ER number.
- If the 49 store Companies do not yet have HDMF ER Numbers, Pag-IBIG contributions deducted from store employees cannot be legally remitted — the deductions would be "floating" with no registered employer to accept them.
- This is not a theoretical risk: HDMF MCRF audits have penalized companies for remitting under incorrect employer numbers.

**Recommended amendment:**
Add a Statutory Registration Pre-requisite gate (combine with Finding 1 recommendation):
1. List all 49 store Companies.
2. For each: verify SSS Employer Number, PhilHealth Employer Number, and HDMF ER Number.
3. Block the backfill for any Company without all three registrations active.
4. Escalate to Sam: registering 49 new employer accounts with SSS, PhilHealth, and HDMF is a significant operational undertaking — it may take weeks to months. If registrations are not in place, the S202 JE reclassification model (keeping ONE employer of record = BEI parent) may be the only legally safe path for statutory remittances, with S201's Company change limited to cost-center and P&L allocation only (no payroll-entity change).

---

## Finding 9 — Group HMO / Insurance Policy Coverage Break

**Severity:** [WARNING]

**Evidence from plan:**
Plan does not mention HMO, group life insurance, or benefits administration.

**Issue:**
BEI's group HMO policy (if any) is typically issued to the parent company `BEBANG ENTERPRISE INC.` as the sole policyholder. When `Employee.company` changes in ERPNext:
- Any ERPNext module or third-party integration that queries `Employee.company` to determine HMO eligibility or premium allocation may break for store employees.
- The HMO provider's employee census is typically submitted per policyholder (BEI parent). Moving employees to child Companies in ERPNext does NOT automatically update the HMO provider's records — a census amendment must be filed with the provider.
- If BEI uses ERPNext's Health Insurance module or a custom field to track HMO enrollment, those records reference the old Company.
- For group life insurance (SSS Flexi-Fund, BEI-sponsored), similar policy-level risks apply.

**Recommended amendment:**
1. Add a Phase 0 checklist item: "Confirm HMO and group insurance policies are issued to BEI parent only. Verify that ERPNext HMO/benefits configuration does not use Employee.company as an eligibility filter."
2. If ERPNext benefits modules ARE company-scoped, add a sub-task to clone/extend benefits configuration to all 49 store Companies before backfill.
3. Notify HMO/insurance provider that the employer of record for billing may change to 49 entities — or confirm that all employees remain under the parent policy regardless of ERPNext Company field.

---

## Finding 10 — Consolidated Financial Reporting During S201 Interim Period

**Severity:** [WARNING]

**Evidence from plan:**
Design Rationale notes: "Option B (monthly reclassification JE) delivers fair per-store P&L... Post inter-Company JE: debit covered-store Salaries, credit home-store Salaries by punch share. This is the standard accounting practice for shared services." S202 is deferred. Plan says S201 is "independently useful."

**Issue:**
In the S201 interim period (after backfill, before S202 JE engine):
- Labor costs for ~510 store employees post directly to 49 child Company P&Ls.
- Relievers' labor still posts to their home store Company (not punch location) — this is acknowledged as a known gap deferred to S202.
- Finance needs CONSOLIDATED labor reports. ERPNext's standard P&L report is per-Company. To view Group-level labor, Finance must either: (a) run reports for all 50 Companies (49 stores + BEI parent) separately and manually aggregate, or (b) use ERPNext's Consolidated Financial Statements feature.
- The plan does NOT confirm whether Consolidated Financial Statements are configured for the BEI group entity tree (TUNGSTEN CAPITAL HOLDINGS OPC → BEI parent → 49 store Companies).
- If the parent-child Company linkage is set correctly in ERPNext (which S188 should have established), ERPNext's Consolidated Balance Sheet / P&L should work — but this is untested.
- For April 2026 payroll (the first payroll under the new structure), Finance will need to confirm their reporting workflow before month-end close.

**Recommended amendment:**
1. Add a Phase 8 (Reporting Verification) sub-task: run ERPNext Consolidated Financial Statements for the BEI group for April 2026 and confirm that all 49 store Company labor costs roll up correctly to the parent.
2. Alert Finance team that April 2026 payroll reporting will require consolidated report runs — single-Company P&L is no longer sufficient.
3. If Consolidated Financial Statements are not configured (parent-child links broken), add that as a blocking dependency from S188/S190.

---

## Finding 11 — Retroactive Risk: April 1–16 Payroll Already Processed

**Severity:** [CRITICAL]

**Evidence from plan:**
LD-6 states "Data starts April 01, 2026 forward — no retroactive allocation to Feb 01." Backfill runs on April 17, 2026. The plan's Phase 7 note says "Data from April 01, 2026 forward" but does not address what happens to payroll transactions ALREADY processed for April 1–16 before the backfill runs.

**Issue:**
This is an extension of Finding 4 but specifically about the April semi-monthly payroll cycle:
- BEI's payroll cycle appears to be semi-monthly (April 1–15 cutoff, April 16–30 cutoff based on standard PH practice).
- If the April 1–15 payroll run was already processed (Salary Slips drafted or submitted) before April 17, those slips are on `BEBANG ENTERPRISE INC.`
- The plan implies that post-backfill, future payroll will correctly use the new Company — but the April 1–15 slips already processed are on the OLD Company.
- This creates a SPLIT WITHIN THE SAME MONTH: first half on parent, second half on store. This is not just a P&L cleanliness issue — it affects BIR 1601-C monthly remittance (which employer files for April compensation? Both?).
- LD-6 "no retro to Feb" covers historical periods — but the plan should explicitly state the April 1–15 handling decision: accept split-month (April 1–15 on parent, April 16–30 on store) OR delay backfill to May 1 to get a clean month-start cutover.

**Recommended amendment:**
Add to Locked Decisions: "LD-8: Backfill Timing — April 1–15 payroll slips already on BEI parent are accepted as-is (not re-posted). Backfill applies from April 16, 2026 forward. OR: Delay backfill to May 1 start for a clean month-start cutover." Sam must make this decision explicitly. The current plan has no decision recorded.

---

## Summary

**CRITICAL: 4, WARNING: 4, INFO: 1, N/A: 1**

| # | Finding | Severity |
|---|---------|----------|
| 1 | SSS/PhilHealth/HDMF employer accounts — 49 new employer registrations required before backfill | CRITICAL |
| 2 | BIR Form 2316 dual-employer mid-year — annualized WT re-computation not addressed | CRITICAL |
| 4 | Draft/Submitted April 2026 Salary Slips pre-backfill will silently remain on parent Company | CRITICAL |
| 11 | April 1–16 split-month retroactive risk — no LD decision recorded | CRITICAL |
| 3 | BIR 1905 / withholding agent registration for 49 store Companies | WARNING |
| 6 | Leave Balance carryover and Leave Period records for 49 store Companies | WARNING |
| 7 | Cost Center continuity — payroll_cost_center not updated in backfill | WARNING |
| 8 | HDMF 49 employer ER numbers (combined with Finding 1 — flagged separately for HDMF specifics) | CRITICAL |
| 9 | Group HMO/insurance policy coverage break — benefits eligibility lookup | WARNING |
| 10 | Consolidated reporting for Finance not verified or configured | WARNING |
| 5 | BIR 2307 cross-Company impact | INFO |

**CRITICAL: 5, WARNING: 5, INFO: 1, N/A: 0**

> Note: Finding 8 (HDMF) was assessed as CRITICAL upon review (not WARNING as initially indicated in the table above — the 49-employer registration gap is as severe as SSS/PhilHealth). The summary count reflects the revised severity.
