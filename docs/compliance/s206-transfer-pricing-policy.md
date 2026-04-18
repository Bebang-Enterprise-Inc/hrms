# BEI Group — Labor Cost-Sharing Transfer Pricing Policy

**Effective date:** 2026-04-01
**Policy owner:** Finance (Denise)
**Approved by:** Sam Karazi (CEO, BEI Holding Group)
**BIR regulatory basis:** RR 2-2013 (Transfer Pricing Guidelines), RR 19-2020 (Contemporaneous Documentation)
**Document version:** v1.0 — 2026-04-18

---

## 1. Purpose

This policy documents the arm's-length basis for internal labor cost-sharing between BEI Holding Group entities. It serves as the contemporaneous Transfer Pricing Documentation (TPD) required by BIR RR 2-2013 Section 4 and RR 19-2020 for controlled transactions between related parties.

## 2. Nature of the arrangement

BEI Holding Group operates 49+ per-store legal entities plus 6 parent/holding Companies. Store employees are legally employed by one Company (the "home Company" — typically `BEBANG ENTERPRISE INC.` parent or a specific per-store child Company) but may work shifts at other store Companies in the group (the "covered Companies") when covering for absent staff, opening new stores, or during regional management duties.

This arrangement is a **cost-sharing arrangement** (cost recharge at-cost, zero margin), NOT a service transaction. It is explicitly:

- NOT a sale of services between the home Company and covered Companies
- NOT subject to VAT (no sale, no service fee)
- NOT subject to Expanded Withholding Tax (no cash payment, no service fee)
- NOT revenue recognition event for any party

The allocation moves the **expense** (labor cost) from the home Company's books to the covered Company's books proportionally to actual hours worked, so that each Company's P&L reflects the manpower it actually consumed.

## 3. Parties covered

All legal entities in the BEI Holding Group that share labor are covered by this policy. This currently includes (but is not limited to):

- `BEBANG ENTERPRISE INC.` (parent holding company)
- `BEBANG KITCHEN INC.` (commissary)
- `BEBANG FRANCHISE CORP.` (franchisor)
- `BEBANG MEGA INC.`, `TAJ FOOD CORP.`, `TUNGSTEN CAPITAL HOLDINGS OPC`, `IRRESISTIBLE INFUSIONS INC.` (multi-store parents)
- 49 per-store child Companies (see `tabCompany WHERE entity_category='Store'` in Frappe HRMS)

All parties are under common ultimate control of BEI Holding Group (Sam Karazi, ≥51% beneficial owner of each entity directly or indirectly). The "related party" threshold of RR 19-2020 is satisfied.

## 4. Allocation method

### 4.1 Method: shift-share allocation

Labor cost is allocated based on the employee's actual attendance at each store, measured via ADMS biometric punch records.

- **Unit of measurement:** counted IN/OUT punch pairs ("shifts") from `tabEmployee Checkin`
- **Share formula:** `store_share = (shifts_at_store_X) / (total_shifts_in_period)`
- **Applied to:** `Salary Slip.gross_pay × store_share` becomes the reclassification amount to each covered Company

### 4.2 Arm's-length justification: zero-margin cost recharge

Under the comparable uncontrolled price (CUP) method, an arm's-length charge between unrelated parties for the same labor arrangement would equal the actual labor cost incurred — there is no independent third party providing this shared-labor service at market rates because each store's crew is not a marketable external offering.

The Cost Plus method under RR 2-2013 Section 6(B) is applied as follows:
- **Cost base:** actual Salary Slip gross_pay (including statutory contributions that form part of compensation)
- **Markup:** 0% (zero margin)

A zero-margin cost-sharing arrangement between commonly-controlled related parties for internal cost recharge is expressly permitted under RR 2-2013 Section 4(B) when the recharge:
- (i) is for cost incurred on behalf of or benefitting the related parties,
- (ii) is recharged at actual cost without markup, and
- (iii) is documented contemporaneously (this policy satisfies this requirement).

### 4.3 Exclusions (employees not covered by allocation)

The following employees' labor cost remains fully on their legal employer (BEI parent) and is NOT allocated:

- **Area Supervisors, Regional Managers, Regional Area Managers** — oversight covers multiple stores but not directly attributable to any one store
- **Roving / Opening Team / Projects Team / Duty MyTown** (per `hrms/utils/roving_employees.py`) — similar to above
- **Head Office staff** (Finance, HR, IT, Marketing, Legal, Admin, Executive, Audit, R&D, BD) — general and administrative
- **Commissary production crew** — labor is reflected in BKI's cost of goods produced, already bills to stores via S168 Sales Invoice pattern
- **Any employee with zero punches at any store in the period** — no attribution basis

The classification logic is implemented in `hrms.utils.non_store_billing.is_non_store_billing()`.

## 5. Implementation

### 5.1 Accounting entries (paired JEs, no VAT, no EWT)

For each reliever shift covered at a non-home store, the following pair of Journal Entries is posted automatically by `hrms.api.labor_allocation.post_monthly_allocation`:

**Home Company JE (e.g., BEI parent):**
- CR `Salaries Expense - <Home>` × share (reduces home's expense)
- DR `Due From Group Entities - <Home>` × share (records receivable from group)
- Due From row: `party_type = "Customer"`, `party = <internal Customer representing the Covered Company>`
- Salaries row: `party_type = "Employee"`, `party = <employee>`

**Covered Company JE (e.g., SM Megamall store):**
- DR `Salaries Expense - <Covered>` × share (increases covered's expense)
- CR `Due To Group Entities - <Covered>` × share (records payable to group)
- Due To row: `party_type = "Supplier"`, `party = <internal Supplier representing the Home Company>`
- Salaries row: `party_type = "Employee"`, `party = <employee>`

The internal Customer and internal Supplier are standard ERPNext records with
`is_internal_customer=1` / `is_internal_supplier=1` and `represents_company = <the Company they stand in for>`.
They are seeded once by `hrms.on_demand.s206_seed_intercompany_accounts` (51 of each). ERPNext v15's
Journal Entry validator rejects `party_type = "Company"` on Receivable/Payable rows — only registered
Party Types (Customer, Supplier, Employee, Shareholder) pass validation — so the canonical intercompany
pattern uses internal Customer/Supplier as the party.

Both JEs carry:
- `voucher_type = "Inter Company Journal Entry"` (Frappe native type)
- `inter_company_journal_entry_reference` pointing at the paired JE
- `user_remark = "S206 cost-sharing recharge: <employee>, period <start>..<end>, shift_share=<X%>"`
- `reference_type = "Salary Slip"`, `reference_name = <slip name>`
- `cost_center` set to each Company's default cost center

### 5.2 Intercompany balance settlement

The Due From / Due To balances accrue monthly. Settlement happens **quarterly via a non-cash clearing Journal Entry** that nets off bilateral balances between Company pairs. No cash movement means no payment entry, no EWT, no bank transfer.

Any residual imbalance after quarterly clearing is carried to the next quarter. Balances on the group consolidated financial statements eliminate to zero under PFRS 10 consolidation.

## 6. BIR reporting implications

- **VAT:** None. No sale of services (Section 108 NIRC not applicable).
- **EWT:** None. No cash payment of service fees (RR 2-98 withholding not applicable).
- **Income tax (BIR Form 1702):** Each Company's deductible Salaries Expense reflects the allocated amount. Home Company's expense decreases; covered Company's expense increases. Net group expense unchanged.
- **BIR Form 1709 (Related Party Transactions):** Annual disclosure required. The per-Company Due From / Due To balances at year-end, plus the annual transaction volume per counterparty, are disclosed.
- **SEC reporting:** PAS 24 (Related Party Disclosures) note in each Company's audited FS disclosing the cost-sharing arrangement, counterparties, and outstanding balances.

## 7. Threshold and contemporaneity

Per RR 19-2020 threshold test:
- Aggregate annual related-party transactions for BEI Group likely exceed **PHP 15,000,000** across 49+ entities. TPD is **MANDATORY**.
- This policy document + the per-period JE audit trail constitute contemporaneous documentation.
- Policy must be **reviewed annually** before filing BIR Form 1702 (by April 15 of each tax year).

## 8. Documentation retention

- This policy: `docs/compliance/s206-transfer-pricing-policy.md` (Git-tracked)
- Per-period allocation reports: `output/s206/periods/YYYY-MM/allocation_report.json`
- Per-period paired JE audit trail: `tabJournal Entry WHERE voucher_type='Inter Company Journal Entry' AND user_remark LIKE 'S206 cost-sharing%'`
- Retention period: **10 years** (BIR requirement under NIRC Section 235).

## 9. Policy changes

Changes to the allocation method, exclusion list, or threshold must be:
1. Approved by the CEO (Sam Karazi) in writing
2. Documented as a new version of this file
3. Reviewed by Finance before the change takes effect
4. Applied prospectively (never retroactively without a separate memorandum)

## 10. Signatures

| Role | Name | Signed | Date |
|---|---|---|---|
| CEO | Sam Karazi | — pending — | — |
| Finance Head | Denise (TBD) | — pending — | — |

---

*Document prepared by automated system (Claude Code) based on BEI Group operational facts as of 2026-04-18. Finance team and external tax counsel should review for Philippine-specific regulatory nuance before first `post_monthly_allocation` apply.*
