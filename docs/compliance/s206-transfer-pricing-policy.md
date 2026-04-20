# BEI Group — Labor Cost-Sharing Transfer Pricing Policy

**Effective date:** 2026-04-01
**Policy owner:** Finance (Denise)
**Approved by:** Sam Karazi (CEO, BEI Holding Group)
**BIR regulatory basis:** RR 2-2013 (Transfer Pricing Guidelines), RR 19-2020 (Contemporaneous Documentation)
**Document version:** v1.2 — 2026-04-20 (Bimonthly cadence + CFO PNL-001 payout-month posting + gross_pay scope clarification; CEO approval for first apply per `docs/compliance/s207-ceo-approval-2026-04-19.md`)

**Supersedes:** v1.1 (2026-04-18)

**v1.2 changes:**
- § 4.2 — gross_pay scope clarified (earnings only, not ER statutory contributions; see below).
- § 5.1 — posting_date for paired JE is the **payout date** per CFO PNL-001 (not the slip's end_date). Cross-month example added.
- § 5.2 — intercompany balance cadence updated to **twice a month** (Bimonthly / "semi-monthly") instead of monthly; quarterly settlement unchanged.
- § 6 — BIR Form 1709 disclosure approach updated for 24 postings/year.
- § 10 — Denise countersign gate waived by CEO (S207 Q4, 2026-04-19). See `docs/compliance/s207-ceo-approval-2026-04-19.md`.

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
- **Cost base:** actual Salary Slip `gross_pay` — **earnings components only** (basic pay, overtime, allowances, holiday premium, less tardiness deductions). This does NOT include employer-side SSS / PhilHealth / HDMF contributions, which accrue separately on each Company's books and are not allocated by S206/S207. The zero-margin characterization holds because `gross_pay` IS the operator-facing labor cost of the employee's time at the covered store — the employer-side statutory accrual is a separate, legally-distinct obligation tied to the home Company's SSS / PhilHealth / HDMF employer-number-of-record.
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

For each reliever shift covered at a non-home store, the following pair of Journal Entries is posted automatically by `hrms.api.labor_allocation.post_allocation(period_start, period_end, confirm=True)` (S207 signature — replaces the S206 `post_monthly_allocation(year, month)` form):

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
- `user_remark = "S206/S207 cost-sharing recharge: <employee>, period <start>..<end>, posting_date=<payout_date>, shift_share=<X%>, slip=<slip_name>"`
- `reference_type = "Salary Slip"`, `reference_name = <slip name>`
- `cost_center` set to each Company's default cost center

**posting_date = payout date (CFO PNL-001):**

Per CFO PNL-001 (Butch Formoso, 2026-02-17), payroll expense hits the P&L of the month in which it is **paid**, not the month the work was performed. The S207 engine computes the posting_date as follows:

- Slip ending on or before the 15th → posting_date = the 25th of the same month.
- Slip ending on the 16th or later → posting_date = the 10th of the next month.

**Cross-month example (March 16-31 → April 10):** a second-half slip with period 2026-03-16 through 2026-03-31 pays on 2026-04-10. Its paired JEs post on 2026-04-10 and therefore hit each Company's **April** P&L, not March. This is correct per CFO PNL-001 and may surprise reviewers who expect March work to appear in March books. The `user_remark` on each JE explicitly carries both `period` and `posting_date` so the offset is auditable.

### 5.2 Intercompany balance settlement

The Due From / Due To balances accrue **twice a month (Bimonthly in Frappe — same semantic as industry "semi-monthly")** in lockstep with BEI's Bimonthly payroll cadence (10th + 25th payouts). Settlement happens **quarterly via a non-cash clearing Journal Entry** that nets off bilateral balances between Company pairs. No cash movement means no payment entry, no EWT, no bank transfer.

Any residual imbalance after quarterly clearing is carried to the next quarter. Balances on the group consolidated financial statements eliminate to zero under PFRS 10 consolidation.

## 6. BIR reporting implications

- **VAT:** None. No sale of services (Section 108 NIRC not applicable).
- **EWT:** None. No cash payment of service fees (RR 2-98 withholding not applicable).
- **Income tax (BIR Form 1702):** Each Company's deductible Salaries Expense reflects the allocated amount. Home Company's expense decreases; covered Company's expense increases. Net group expense unchanged.
- **BIR Form 1709 (Related Party Transactions):** Annual disclosure required. The per-Company Due From / Due To balances at year-end, plus the annual transaction volume per counterparty, are disclosed. Under the Bimonthly cadence the engine can generate ~24 postings per reliever pair per year (vs. the original monthly ~12). Per RR 19-2020 materiality thresholds, the Form 1709 disclosure may list **aggregate transaction volume per counterparty** rather than each individual posting — this is explicitly permitted and matches the practice of other multi-entity groups.
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
| CEO | Sam Karazi | /s/ Sam Karazi — 2026-04-18 (v1.1); see `docs/compliance/s207-ceo-approval-2026-04-19.md` Q1–Q7 for v1.2 authority | 2026-04-18 (v1.1) / 2026-04-19 (v1.2 authority) |
| Finance Head | Denise Gumatay | — waived for v1.2 by CEO 2026-04-19 (see `docs/compliance/s207-ceo-approval-2026-04-19.md` Q4) — | n/a |

**Gating notes:**
- The CEO signature and the S207 CEO approval artifact together authorize: the seeder (`hrms.on_demand.s206_seed_intercompany_accounts.execute`), the daily day-guard preview cron (`hrms.api.labor_allocation.preview_scheduled`), and the first and subsequent applies via `docker exec -e S206_APPLY=1 ... post_allocation`. **No separate Finance Head countersignature is required for v1.2.** This is a departure from v1.1, which required Denise's countersign before first apply — CEO rescinded that gate in the 2026-04-19 chat (captured in `docs/compliance/s207-ceo-approval-2026-04-19.md` Q4).
- Document versioning: this file is Git-tracked. Any signature change creates a new version per section 9 rules.

---

*Document prepared by automated system (Claude Code) based on BEI Group operational facts as of 2026-04-20. External tax counsel should review for Philippine-specific regulatory nuance before first `post_allocation` apply. The CEO authority for v1.2 is captured as a committed artifact in `docs/compliance/s207-ceo-approval-2026-04-19.md` so cold-start agents can cite it without chat-log access.*
