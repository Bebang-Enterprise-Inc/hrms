# Finance — Confirmed Decisions

**Last Updated:** 2026-05-07
**Total Decisions:** 108

> **🔴 IMPORTANT — Finance Leadership Status (2026-05-07)**
>
> All three original finance leaders who authored / countersigned decisions in this document have **resigned and are no longer with BEI**:
> - **Butch Formoso (CFO)** — last day 2026-04-15. CFO seat is **VACANT INDEFINITELY**.
> - **Alyssa Dimaano (Accounting Manager / Head Accountant)** — last day 2026-04-15.
> - **Juanna Alcober (Finance Manager / Head of Finance)** — last day 2026-04-27 (finalized in all systems on 2026-05-07).
>
> **Decision authority going forward:** Sam Karazi (CEO) approves alone for any matter that previously required CFO/finance-leadership sign-off. **Denise Almario** (Finance Supervisor → finance lead from 2026-04-28) owns operational follow-through.
>
> **Existing decisions still binding:** Every CFO-locked decision below (especially ICT-001..006 / inter-company; CS-001..007 / company structure; transfer-pricing rates) remains in force as the policy of record. The fact that the original signer has departed does **NOT** invalidate the decision. Future supersession requires Sam (CEO) sign-off and a new dated row added to this file.
>
> **Do not list Butch / Alyssa / Juanna as approver, contact, or DRI** in any new plan, audit, sprint registry row, or document. The author / signer columns below are preserved as a historical audit trail of WHO MADE THE DECISION AT THE TIME — they are not contact information for current routing.

**Sources:**
- `data/_CONSOLIDATED/phase3_p1_decisions.md` (P1)
- `data/_CONSOLIDATED/phase3_p2_decisions.md` (P2)
- `data/_CONSOLIDATED/phase3_p3_decisions.md` (P3)
- `data/_CONSOLIDATED/01_FINANCE/questionnaires/CFO_INTERCOMPANY_Butch_Formoso_2026-02-20.md` (Inter-company Q&A)
- `data/_CONSOLIDATED/01_FINANCE/questionnaires/CFO_BKI_TOLL_MFG_REVIEW_Butch_Formoso_2026-02-21.md` (Toll mfg review + rejection analysis)
- `data/_CONSOLIDATED/01_FINANCE/questionnaires/FINANCE_PROCUREMENT_AUDIT_QUESTIONNAIRE_2026-02-19.md` (Audit questionnaire — Butch/Alyssa/Mae responses)

---

## Company Structure

| # | Decision | Value | Confirmed By | Date | Source |
|---|----------|-------|-------------|------|--------|
| CS-001 | Legal entity model for ERPNext | One Company per legal entity (per-store corporation) to support BIR/SEC financial statements. Head Office, Commissary, JV, and Managed Franchise are in scope for go-live. | Butch Formoso (CFO) | 2026-01-05 | P1/P3 — `FINANCE_Butch_Formoso_ERPNext_Policy_Decisions_Answered_2026-01-05.md` |
| CS-002 | Commissary entity treatment | Commissary treated as separate legal entity — Bebang Kitchen Inc. — with its own inventory, manufacturing activity, and P&L. | CFO / CEO | 2026-01-14 | P1 — `CONTEXT.md`, `erp-migration.md` |
| CS-003 | Intercompany flow direction | Suppliers → Bebang Kitchen Inc. (Commissary) → Bebang Enterprise Inc. (Stores). Commissary-to-store movements recorded as intercompany flow and must reconcile. | CFO / CEO | 2026-01-14 | P1 — `CONTEXT.md` |
| CS-004 | Holding company | Irrisistable Infusions Inc. (Triple I) — holding company, no employees, Is Group Company = Yes | Setup Checklist | 2025-12-08 | P3 — `HRMS_Setup_Checklist.md` |
| CS-005 | Entities in-scope for go-live | Head Office, Commissary, JV, Managed Franchise | Butch Formoso (CFO) | 2026-01-05 | P1/P3 |
| CS-006 | All company processes to move to ERP | CEO decision: ALL company processes (supply chain, operations, commissary) must move to ERP — overrides any team marking them For_ERP_Transfer = FALSE. | CEO | 2026-01-21 | P1 — `CONTEXT.md` |
| CS-007 | Master data ownership — salary, bank, loans, statutory | Finance (+ HR) owns salary, bank, loans, statutory rules | ERP Department Plans | 2025-12-28 | P3 — `ERP_DEPARTMENT_PLANS_2025-12-28.md` |

---

## Chart of Accounts

| # | Decision | Value | Confirmed By | Date | Source |
|---|----------|-------|-------------|------|--------|
| COA-001 | COA structure and account count | 297 GL accounts uploaded to ERPNext on Jan 30. Current COA file has 310 accounts (post-upload additions by Alyssa per Butch's review): 117 Asset, 25 Liability, 4 Equity, 24 Revenue/Income, 136 Expense, 4 Cost of Sales. Source: `01 - Chart of Accounts (217).xlsx` (3 sheets: COA, Income Streams, Fund Details). | Butch Formoso (CFO) / Alyssa Dimaano (Acct Mgr) | 2026-01-30 | P1 — `CONTEXT.md`, `01 - Chart of Accounts (217).xlsx` |
| COA-002 | New account: Advances to Suppliers | Create 1105203 — Advances to Suppliers under 1105200 Prepaid Expenses (PFRS-compliant). Account 1103102 (AR-Others) stays under Trade Receivables and is NOT used for supplier advances. | Butch Formoso (CFO) | 2026-02-10 | P1 — `finance-apex.md`, `CFO_PROCUREMENT_SPRINT_2026-02-09.md` |
| COA-003 | 7 new franchise income GL accounts | Create accounts 4000300–4000306 (Franchise Income grouping) before go-live: FRANCHISE INCOME (group), ROYALTIES INCOME, MARKETING FEE INCOME, MANAGEMENT FEE INCOME, ECOMMERCE FEE INCOME, DELIVERY INCOME, LOGISTICS INCOME. Import-ready CSV: `docs/questionnaires/FRANCHISE_GL_ACCOUNTS_PROPOSED.csv`. Action owner: Alyssa. | Butch Formoso (CFO) + Billing redesign | 2026-02-14 | P1/P2 — `finance-apex.md`, `BILLING_REDESIGN_2026-02-13.md` |
| COA-004 | Confirmed GL accounts for daily POS JV | Cash on Hand: 1101100; AR-GCash/PayMongo: 1103103; Sales Revenue (Vatable + VAT Exempt): 4000000; Output VAT Payable: 2102205; COGS–Food & Bev: 5000001; Inventory–Raw Materials: 1104003; Sales Discounts: 4000201–4000207; Employee Benefit Expense: 4000208 | Butch Formoso (CFO) | 2026-02-12 | P1 — `POS_DAILY_SYNC_AUDIT_2026-02-12.md` |
| COA-005 | Input VAT accounts (3 separate) | 1105103 (Goods), 1105104 (Services), 1105105 (Importation) | Butch Formoso (CFO) | 2026-02-09 | P1 — `CFO_PROCUREMENT_SPRINT_2026-02-09.md` |
| COA-006 | EWT Payable accounts | 2102202 (Expanded), 2102203 (Compensation), 2102204 (Final). All Subsidiary Ledger Managed. | Butch Formoso (CFO) | 2026-02-09 | P1 — `CFO_PROCUREMENT_SPRINT_2026-02-09.md` |
| COA-007 | Undeliverable advance reclassification GL | Advances that become undeliverable reclassified from 1105203 (Advances to Suppliers) → 1103102 (AR-Others / Trade Receivables). | Butch Formoso (CFO) | 2026-02-10 | P1 — `finance-apex.md`, `procurement-suppliers.md` |
| COA-008 | Output VAT and AR clearing accounts | Output VAT account: 2102205. AR clearing for GCash/PayMongo: 1103103. | Butch Formoso (CFO) | 2026-02-12 | P1 — `POS_DAILY_SYNC_AUDIT_2026-02-12.md` |
| COA-009 | COA preparation file | `docs/erp/CHART_OF_ACCOUNTS_ERP_COA_2025-12-23.csv` — ready for import | Finance team | 2025-12-23 | P3 — `DEPARTMENT_STATUS_Frappe_Readiness_2025-12-31.md` |
| COA-010 | GR/IR Clearing account | Create **1104005 — GR/IR Clearing** under Current Assets. GL flow: (1) Advance payment: Dr 1105203 Advances to Suppliers / Cr Cash in Bank; (2) Goods Receipt: Dr 1104005 GR/IR Clearing / Cr 1105203 Advances to Suppliers; (3) Invoice Receipt + 3-way match: Dr 1104002 Inventory / Cr 1104005 GR/IR Clearing. | Butch Formoso (CFO) | 2026-02-19 | `FINANCE_PROCUREMENT_AUDIT_QUESTIONNAIRE_2026-02-19.md` Q4 |

### COA-175 — Canonical Sales Tree Locks (Ratified into canonical DECISIONS.md 2026-06-04 from S175 Cleanroom; ratification commit Sam-CEO-signed)

| COA-175-001 | Master COA template source | Canonical GL Sales Accounts Set-up = Butch's 2026-04-08 10:18 AM PHT chat table; scope = 4000000 Sales tree (27-account structural tree). Source: cleanroom chat_evidence/2026-04-08_butch_gl_sales/. Verification: chat harvest 2026-04-09. | Butch Formoso (CFO) | 2026-04-08 | `data/_CLEANROOM/2026-04-09_s175_coa_restructure/02_LOCKED_DECISIONS.md` |
| COA-175-002 | DISCOUNTS AND PROMO renumber | DISCOUNTS AND PROMO moves from 4000200 (which becomes BKI SALES) to 4000900 as contra-revenue range. Children renumber to 4000901-4000908. Butch verbatim 2026-04-08 21:48 PHT. Supersedes 2026-02-12 COA-004. | Butch Formoso (CFO) | 2026-04-08 | `data/_CLEANROOM/2026-04-09_s175_coa_restructure/02_LOCKED_DECISIONS.md` |
| COA-175-003 | Uniform COA across all 40 companies | Every Frappe Company in Bebang Group gets the FULL 27-account structural Sales tree. Each populates only its relevant sub-tree. Sam architectural decision 2026-04-08; no Butch veto. Enables PFRS 10 consolidation + intercompany eliminations + comparability. | Sam Karazi (CEO) | 2026-04-08 | `data/_CLEANROOM/2026-04-09_s175_coa_restructure/02_LOCKED_DECISIONS.md` |
| COA-175-004 | INTERIM revenue recognition policy — SUPERSEDED BY COA-175-013 | Original: all franchise fees settle to BEI until BFC has bank account; BFC FEES sub-tree empty as hot standby. SUPERSEDED by COA-175-013 (Fork 1 chosen — liability accounting from day 1, not revenue). | Sam Karazi (CEO) — SUPERSEDED 2026-04-10 | 2026-04-09 | `data/_CLEANROOM/2026-04-09_s175_coa_restructure/02_LOCKED_DECISIONS.md` |
| COA-175-005 | Phase 2 cutover pattern | When BFC operating bank account opens, franchisees pay BFC directly per signed contracts. BFC→BEI intercompany services agreement drafted separately (out of S175 scope). Butch verbatim 2026-04-09 10:37:14 PHT. Supersedes 2026-04-08 PM Royalty→BFC, Mgmt/Marketing/E-Comm→BEI directive. | Butch Formoso (CFO) | 2026-04-09 | `data/_CLEANROOM/2026-04-09_s175_coa_restructure/02_LOCKED_DECISIONS.md` |
| COA-175-006 | BFC legal entity facts | BFC = BEBANG FRANCHISE CORP. (not Inc.). SEC 2025030195371-03 (27 Mar 2025). BIR TIN 672-618-804-00000 (3 Apr 2025). RDO 044 Taguig. Domestic Corp VAT-registered. Auth cap PHP 6M (60K @ PHP 100 par). Paid PHP 1.5M. Ownership: BEI 79.97% via Daymae Karazi + Samer Karazi 20% + 4 qualifying. | Cleanroom legal extract (verified) | 2026-04-08 | `data/_CLEANROOM/2026-04-09_s175_coa_restructure/02_LOCKED_DECISIONS.md` |
| COA-175-007 | JV fees flow permanently to BEI | Grand Central Gabaldon JV Agreement routes all fees to BEI: 5% Brand Marketing (§8.1), 5% E-Commerce (§9.1), PHP 2M Brand Growth Fee (§2). PERMANENT (not interim). Posts to 4000234 MARKETING FEES + 4000235 E-COMMERCE FEES + 4000005 BRAND GROWTH FEE INCOME - BEI. Signed 3 Jan 2025. | Butch Formoso (CFO) | 2026-04-09 | `data/_CLEANROOM/2026-04-09_s175_coa_restructure/02_LOCKED_DECISIONS.md` |
| COA-175-008 | Franchise fees contractually flow to BFC (corrected) | Per signed Franchise Agreement (unexecuted): 4 fees to BFC — PHP 2M Franchise Fee+VAT (§I.A), 7% Continuing Royalty (§XIII.A), 5% Marketing Support (§XI.A), 5% E-Commerce (§XI.I/§XV.R). Plus 2.5% Management Fee (Mgmt §5.1). BEI named NOWHERE in either contract. | Sam Karazi (CEO) | 2026-04-09 | `data/_CLEANROOM/2026-04-09_s175_coa_restructure/02_LOCKED_DECISIONS.md` |
| COA-175-009 | Both BFC contracts are UNEXECUTED templates | Franchise Agreement template (2025-05-23) and Franchise Management Agreement template (undated) are DRAFTs with placeholder FRANCHISEE fields. No franchisees have signed either. Makes Fork 1 collection-agent routing SAFE — no live franchisee being overridden. | Sam Karazi (CEO) | 2026-04-09 | `data/_CLEANROOM/2026-04-09_s175_coa_restructure/02_LOCKED_DECISIONS.md` |
| COA-175-010 | COA-004 supersession | Butch's 2026-02-12 COA-004 lock (Sales Discounts 4000201-4000207 + Employee Benefit Expense 4000208) is SUPERSEDED by COA-175-002's renumber to 4000901-4000908. | Butch Formoso (CFO) | 2026-04-08 | `data/_CLEANROOM/2026-04-09_s175_coa_restructure/02_LOCKED_DECISIONS.md` |
| COA-175-011 | BKI population rules | BKI is the commissary. Populates ONLY 4000200 BKI SALES sub-tree (DELIVERIES + LOGISTICS). NO in-store sales, NO online sales, NO franchise income. Sam clarification 2026-04-08 'BKI doesn't have in store sales, online sales and franchise income.' 4000001/4000002 + 4000300 tree are DELETE targets on BKI (0 GL verified). | Sam Karazi (CEO) | 2026-04-08 | `data/_CLEANROOM/2026-04-09_s175_coa_restructure/02_LOCKED_DECISIONS.md` |
| COA-175-012 | BEI 6xxxxxx Income → Expense bulk fix (verified) | 134 of 136 BEI 6xxxxxx accounts have root_type='Income' (should be 'Expense'). Zero GL entries on any. Bulk SQL UPDATE is safe. LIVE-CONFIRMED via Phase A preflight audit. Single SQL UPDATE in Phase 7 after re-verifying 0 GL at execution time. | Phase A live audit | 2026-04-09 | `data/_CLEANROOM/2026-04-09_s175_coa_restructure/02_LOCKED_DECISIONS.md` |
| COA-175-013 | FORK 1 LOCKED (Butch answered 2026-04-10) | Fork 1 (collection-agent from day 1) CONFIRMED. Butch verbatim 'I would humbly recommend Option A...'. BEI as agent: Dr Cash on Hand / Cr 2104200 DUE TO BFC. BFC as principal: Dr 1104200 DUE FROM BEI / Cr 4000231-235 + 2102205 OUTPUT VAT PAYABLE. At cutover BEI sweeps DUE TO BFC. Pre-cond: BFC OR booklet (Sir Noel applying ATP). | Butch Formoso (CFO) | 2026-04-10 | `data/_CLEANROOM/2026-04-09_s175_coa_restructure/02_LOCKED_DECISIONS.md` |
| COA-175-014 | Interim OR/VAT issuer policy | During Fork 1 interim, every Official Receipt for franchise fee issued by BFC using BFC's own BIR-registered OR booklet at RDO 044. BFC files its own 2550Q. BEI NEVER issues an OR for a franchise fee. Pre-condition: BFC BIR OR booklet operational (BLOCKED on Authority to Print). | Butch Formoso (CFO) | 2026-04-10 | `data/_CLEANROOM/2026-04-09_s175_coa_restructure/02_LOCKED_DECISIONS.md` |
| COA-175-015 | Intercompany scaffolding accounts | Three new accounts for Fork 1: 2104200 DUE TO BFC - BEI (Liability/Payable on BEI), 1104200 DUE FROM BEI - BFC (Asset/Receivable on BFC), 2102205 OUTPUT VAT PAYABLE - BFC (Liability/Tax on BFC). 2104200 confirmed clean (2104100 + 2104101 exist on BEI; 2104200 unused). | Sam Karazi (CEO) | 2026-04-09 | `data/_CLEANROOM/2026-04-09_s175_coa_restructure/02_LOCKED_DECISIONS.md` |
| COA-175-016 | Brand Growth Fee treatment | 4000005 BRAND GROWTH FEE INCOME - BEI kept as BEI-specific extension OUTSIDE canonical template (legacy 6-digit number). Receives PHP 2M one-time JV Brand Growth Fee (JV §2). PFRS 15 recognition is point-in-time (license-granted model per JV §3.4) — full PHP 2M on JV execution date, NOT amortized. | Sam Karazi (CEO) + finance synthesis | 2026-04-09 | `data/_CLEANROOM/2026-04-09_s175_coa_restructure/02_LOCKED_DECISIONS.md` |
| COA-175-017 | VAT payment mechanism: Option B (partial sweep) — LOCKED | During Fork 1 interim, BFC's Output VAT funded by partial sweep of 2104200 DUE TO BFC - BEI cash held by BEI. BFC's own money pays BFC's own VAT to BIR. ZERO new intercompany advance accounts needed. Butch OQ-2 answer 2026-04-10. Additional: BFC needs BDO depository + UnionBank disbursing accounts opened. | Butch Formoso (CFO) | 2026-04-10 | `data/_CLEANROOM/2026-04-09_s175_coa_restructure/02_LOCKED_DECISIONS.md` |
| COA-175-018 | Cutover trigger: Option C (full receive + pay cycle) — LOCKED | Collection-agent letter auto-terminates when BFC has completed a full receive-AND-pay cycle through BFC's own bank accounts (BDO depository + UnionBank disbursing). 'Fully operational' = inbound deposit tested + outbound BIR payment tested. Butch OQ-3 answer. | Butch Formoso (CFO) | 2026-04-10 | `data/_CLEANROOM/2026-04-09_s175_coa_restructure/02_LOCKED_DECISIONS.md` |
| COA-175-019 | BEI Settings input_vat_goods_account: FIX NOW — LOCKED | Link INPUT VAT - GOODS - Bebang Enterprise Inc. to BEI Settings.input_vat_goods_account immediately. The account exists but was never wired. Butch OQ-4 answer 2026-04-10. | Butch Formoso (CFO) | 2026-04-10 | `data/_CLEANROOM/2026-04-09_s175_coa_restructure/02_LOCKED_DECISIONS.md` |
| COA-175-020 | JV fee GL routing: Customer Group filter — LOCKED | JV Marketing 5% posts to 4000234 MARKETING FEES - BEI. JV E-Commerce 5% posts to 4000235 E-COMMERCE FEES - BEI. Separated from BFC franchise fees by Customer Group filter (JV Partners vs BFC Franchisees). Brand Growth Fee placement: Butch discretion — 4000005 legacy ok, 4000233, or 4000236. Butch OQ-5 + Sam clarification. | Butch Formoso (CFO) + Sam Karazi (CEO) | 2026-04-10 | `data/_CLEANROOM/2026-04-09_s175_coa_restructure/02_LOCKED_DECISIONS.md` |

---

## Tax Policy

| # | Decision | Value | Confirmed By | Date | Source |
|---|----------|-------|-------------|------|--------|
| TAX-001 | BEI withholding agent status | Regular withholding agent (NOT Top 20,000 Taxpayer). **CORRECTED (Feb 19):** BEI/BKI/BEI Stores are NOT required to withhold 1% goods / 2% services. Only mandatory EWT: professional fees and rentals (see TAX-002). Do NOT store default ATC codes on Supplier Master now — but build the facility for future Top 20,000 tagging with override function. | Butch Formoso (CFO) | 2026-02-19 | `FINANCE_PROCUREMENT_AUDIT_QUESTIONNAIRE_2026-02-19.md` Q1, Q10 |
| TAX-002 | Mandatory EWT rates and ATC codes | **Professional (Individual):** 5% below PHP 3M (WI050 mgmt/tech, WI010 lawyers/CPAs), 10% above PHP 3M or VAT-registered (WI051, WI011). **Professional (Corp):** 10% below PHP 720K (WC050, WC010), 15% above PHP 720K (WC051, WC011). **Rentals:** 5% (WI100 individual lessor, WC100 corporate lessor). | Butch Formoso (CFO) | 2026-02-19 | `FINANCE_PROCUREMENT_AUDIT_QUESTIONNAIRE_2026-02-19.md` Q1, Q10 |
| TAX-003 | EWT on goods/services — NOT required | **CORRECTED (Feb 19):** 1% goods and 2% services EWT is NOT required since BEI is not Top 20,000 Taxpayer. Previous "optional if supplier agrees" guidance superseded. Facility must exist for future implementation if tagged. CUSA/utilities payments to lessors exempt from 5% rental EWT (override function needed). | Butch Formoso (CFO) | 2026-02-19 | `FINANCE_PROCUREMENT_AUDIT_QUESTIONNAIRE_2026-02-19.md` Q1 |
| TAX-004 | Form 2307 issuance timing | Auto-generate per payment. Monthly print option also required (not just quarterly) since BEI files and pays Withholding Taxes monthly with BIR. | Butch Formoso (CFO) | 2026-02-10 | P1 — `finance-apex.md`, `CFO_PROCUREMENT_SPRINT_2026-02-09.md` |
| TAX-005 | Input VAT claim timing (EOPT Law) | Input VAT claimed on GR date (when supplier's VAT Invoice is received at delivery), NOT at payment date. EOPT Law makes Invoice (not OR) the primary document. | Butch Formoso (CFO) | 2026-02-10 | P1/P2 — `finance-apex.md`, `BILLING_REDESIGN_2026-02-13.md` |
| TAX-006 | Missing Invoice escalation policy | Online payments: escalate after 5 days if Invoice not received. Check payments: Invoice must be received before check is released. OR tracking is secondary to Invoice tracking per EOPT Law. | Butch Formoso (CFO) | 2026-02-10 | P1 — `finance-apex.md`, `CFO_PROCUREMENT_SPRINT_2026-02-09.md` |
| TAX-007 | BIR compliance forms — full list | **CORRECTED (Feb 19):** Full BIR form suite: (1) **Form 2307** — per payment, auto-generate at payment time; (2) **Form 0619-E** — monthly, consolidated EWT data; (3) **Form 1601-EQ** — quarterly, consolidated EWT data; (4) **Form 2550Q** — quarterly, consolidated VAT (output + input); (5) **Form 1601C** — monthly, consolidated withholding tax on compensation; (6) **Form 1702Q** — quarterly, consolidated business transactions (revenue, cost, expenses). **Removed:** Form 2550M (no longer required by BIR). Butch will provide BIR form templates. Export format TBD. | Butch Formoso (CFO) | 2026-02-19 | `FINANCE_PROCUREMENT_AUDIT_QUESTIONNAIRE_2026-02-19.md` Q3 |
| TAX-008 | Supplier VAT registration data collection | Request BIR Certificate of Registration (COR) from each supplier to confirm VAT-registered vs non-VAT status. New fields required on Supplier Master: `vat_status`, `tin`, `ewt_exempt`, `ewt_applicable`. | Butch Formoso (CFO) | 2026-02-10 | P1 — `finance-apex.md`, `CFO_PROCUREMENT_SPRINT_2026-02-09.md` |
| TAX-009 | Income tax framework | TRAIN Law 2025 — annual brackets: 0% (≤₱250K), 15%, 20%, 25%, 30%, 35% (>₱8M) | HRMS Setup Checklist | 2025-12-08 | P3 — `HRMS_Setup_Checklist.md` |
| TAX-010 | Bonus exemption cap | ₱90,000 — 13th Month Pay + Other Benefits combined | HRMS Setup Checklist | 2025-12-08 | P3 — `HRMS_Setup_Checklist.md` |
| TAX-011 | Clothing allowance de minimis (2025) | ₱7,000/year per RR 004-2025 | HRMS Setup Checklist | 2025-12-08 | P3 — `HRMS_Setup_Checklist.md` |
| TAX-012 | Input VAT PHP 1M threshold — CAPEX only | **CORRECTED (Feb 19):** The BIR PHP 1,000,000/quarter Input VAT threshold applies **ONLY to Capital Expenditures (CAPEX)** — assets with economic benefit >1 year (land, building, machinery, equipment). Does NOT apply to Input VAT on goods, services, or importation of inventories. CAPEX Input VAT amortized over 60 months per BIR schedule (matches 5-year useful life). | Butch Formoso (CFO) | 2026-02-19 | `FINANCE_PROCUREMENT_AUDIT_QUESTIONNAIRE_2026-02-19.md` Q2 |
| TAX-013 | BIR filing deadlines (first filings) | **0619-E** (Feb 2026): Mar 10, 2026. **1601C** (Feb 2026): Mar 10, 2026. **2550Q** (Q1 2026): Apr 25, 2026. **1601-EQ** (Q1 2026): Apr 30, 2026. **1702Q** (Q1 2026): May 29, 2026. System must be ready before Mar 10 for monthly forms. | Butch Formoso (CFO) | 2026-02-19 | `FINANCE_PROCUREMENT_AUDIT_QUESTIONNAIRE_2026-02-19.md` Q3 |
| TAX-014 | EWT GL entry — setup and payment | **Setup (when EWT withheld):** Dr Accounts Payable / Cr 2102202 EWT Payable (reduces amount to settle). **Payment (when remitted to BIR):** Dr 2102202 EWT Payable / Cr Cash in Bank (per legal entity). | Butch Formoso (CFO) | 2026-02-19 | `FINANCE_PROCUREMENT_AUDIT_QUESTIONNAIRE_2026-02-19.md` Q1 |

---

## Cost Center

| # | Decision | Value | Confirmed By | Date | Source |
|---|----------|-------|-------------|------|--------|
| CC-001 | Cost center hierarchy | Level 1: BEI (controlling area). Level 2a: Stores (group) → Store Name (individual). Level 2b: Commissary (group) → Departments (group) → Department Name. No sub-cost centers for stores — use COA account titles instead. | Butch Formoso (CFO) | 2026-01-05 | P1/P3 — `FINANCE_Butch_Formoso_ERPNext_Policy_Decisions_Answered_2026-01-05.md`, `CONTEXT.md` |
| CC-002 | Commissary cost flow to stores | Transfer price = standard product cost (inventory valuation) + markup. Reviewed monthly for applicability; adjusted if product cost changes. | Butch Formoso (CFO) | 2026-01-05 | P1/P3 — `FINANCE_Butch_Formoso_ERPNext_Policy_Decisions_Answered_2026-01-05.md` |

---

## Accounting Policy

| # | Decision | Value | Confirmed By | Date | Source |
|---|----------|-------|-------------|------|--------|
| FAP-001 | Sales posting policy | Post daily summarized entries with supporting attachments. | Butch Formoso (CFO) | 2026-01-05 | P1/P3 |
| FAP-002 | Bank reconciliation cadence | Monthly | Butch Formoso (CFO) | 2026-01-05 | P1/P3 |
| FAP-003 | Go-live approach: Minimum Viable Data | Launch with minimum viable data; rectify accounting post-go-live. AP opening (PHP 66.2M) and AR opening (PHP 25.2M) loaded at go-live. Bank balances and full trial balance deferred to post-go-live. | CFO / CEO | 2026-02-01 | P1 — `CONTEXT.md`, `finance-apex.md` |
| FAP-004 | AP opening balance amount | NET PHP 66,246,146.84 (411 positive invoices at PHP 68,080,089.48 gross, minus PHP 1,833,942.64 credits). 39 unique suppliers. File: `data/Finance_AP_AR/extractions/2026-01-30/ERPNEXT_AP_OPENING_FINAL.csv`. | Verified row-by-row | 2026-01-30 | P1 — `finance-apex.md`, `CONTEXT.md` |
| FAP-005 | AR opening balance amount | PHP 25,235,614.96 (220 items, 49 customers). File: `data/ERP_Reprocessing/2026-01-30/AR_AGING/`. External B2C AR is minimal (retail model). | Extracted and verified | 2026-01-30 | P1 — `finance-apex.md`, `CONTEXT.md` |
| FAP-006 | Revenue recognition timing | Revenue recognized at point of sale (POS `billed_at` timestamp) — standard for QSR per PFRS 15. Determines posting date on daily Journal Vouchers and BIR VAT return timing. | CFO Office (Q1 answered — highlighted ✓ in returned questionnaire) | 2026-02-12 | P1 — `POS_DAILY_SYNC_AUDIT_QUESTIONNAIRE_2026-02-12.docx` (Q1, answered) |
| FAP-007 | GCash / PayMongo settlement timeline | Cash: same day. GCash via PayMongo: T+1 assumed. PayMongo/QRPH: 5 days processing + 1. Managed via daily sales monitoring and bank reconciliation. | Finance team | 2026-02-12 | P1 — `POS_DAILY_SYNC_AUDIT_2026-02-12.md` |

---

## AR / Collections

| # | Decision | Value | Confirmed By | Date | Source |
|---|----------|-------|-------------|------|--------|
| ARC-001 | Payment terms: JV stores | Net 2 (48 hours after Delivery Receipt). | CEO / CFO | 2026-01-24 | P1 — `erp-migration.md` |
| ARC-002 | Payment terms: Managed Franchise | Net 2 (48 hours after Delivery Receipt). | CEO / CFO | 2026-01-24 | P1 — `erp-migration.md` |
| ARC-003 | Payment terms: Full Franchise | Net 7 (7 days after Delivery Receipt). | CEO / CFO | 2026-01-24 | P1 — `erp-migration.md` |
| ARC-004 | ERP configuration for AR collections | 2 Payment Terms Templates: "JV/Managed - 48hr" and "Franchisee - 7 days". `store_type` field required on Customer DocType for auto-assignment. | Decided | 2026-01-24 | P1 — `erp-migration.md` |
| ARC-005 | Overdue AR — delivery block trigger (JV/Managed) | Block next delivery at +2 days overdue, escalate to Finance/Mae at +3. | CEO / CFO | 2026-01-24 | P1 — `erp-migration.md` |
| ARC-006 | Overdue AR — delivery block trigger (Franchisee) | Block at +7 days overdue, escalate at +10. | CEO / CFO | 2026-01-24 | P1 — `erp-migration.md` |
| ARC-007 | AP aging report — 6 buckets | AP Aging dashboard uses 6 aging buckets. Endpoint: `get_ap_aging_report` in `hrms/api/procurement.py`. | E2E verified | 2026-02-06 | P1 — `finance-apex.md` |
| ARC-008 | Undeliverable advance treatment | Reclassify from Advances to Suppliers (1105203) → AR-Others (1103102). New action: "Mark as Undeliverable" on procurement dashboard. | Butch Formoso (CFO) | 2026-02-10 | P1 — `finance-apex.md`, `procurement-suppliers.md` |
| ARC-009 | OR tracking migration | Existing "Paid" payments migrated to "Paid - Awaiting OR" status. Escalation tiers: 7-day, 14-day, 30-day via scheduler `check_overdue_or()`. | Implemented | 2026-02-09 | P1 — `procurement-suppliers.md` |

---

## P&L Structure

| # | Decision | Value | Confirmed By | Date | Source |
|---|----------|-------|-------------|------|--------|
| PNL-001 | Payroll P&L billing rule | Payroll billed to the P&L of the month it is PROCESSED (payout date), NOT the month work was performed. Each month's P&L includes exactly 2 payroll payouts: 10th and 25th of that month. | CFO Butch Formoso | 2026-02-17 | P2 — `PNL_DATA_ORGANIZATION_IMPLEMENTATION_PLAN_2026-02-17.md` |
| PNL-002 | Payroll payout schedule | Jan 10 (Dec 16-31 work) + Jan 25 (Jan 1-15 work) both bill to January P&L. Feb 10 (Jan 16-31 work) bills to February P&L. | CFO Butch Formoso | 2026-02-17 | P2 — `PNL_DATA_ORGANIZATION_IMPLEMENTATION_PLAN_2026-02-17.md` |
| PNL-003 | Online Sales VAT treatment for Apex matching | Online Sales = Stats API total_amount / 1.12 (VAT-exclusive). Matches Apex exactly (Oct 2025 verified: 0.00% variance). | Investigation team / Sam | 2026-02-17 | P2 — `PNL_DATA_ORGANIZATION_IMPLEMENTATION_PLAN_2026-02-17.md` |
| PNL-004 | COGS formula | COGS = Beginning Inventory + Purchases (from Ian's SI spreadsheets) - Wastage & Spoilage - Ending Inventory | Alyssa / ERP team | 2026-02-18 | P2 — `PNL_DATA_ORGANIZATION_IMPLEMENTATION_PLAN_2026-02-17.md` |
| PNL-005 | COS RECON validation rule | Alert if Beginning Inventory = Ending Inventory (stale data). Alyssa validates all COS RECON sheets before closing month. | Alyssa Dimaano | 2026-02-17 | P2 — `PNL_DATA_ORGANIZATION_IMPLEMENTATION_PLAN_2026-02-17.md` |
| PNL-006 | P&L Google Drive folder structure | `BEI Store P&L Master/{YYYY-MM}/{01_Revenue, 02_COGS, 03_Payroll, 04_OpEx, 05_Other, OUTPUT}/` | CFO Butch Formoso / Sam | 2026-02-17 | P2 — `PNL_DATA_ORGANIZATION_IMPLEMENTATION_PLAN_2026-02-17.md` |
| PNL-007 | Month-end folder lock date | Day 15 of the following month — folder set to View-only. No edits after Day 15. | Butch / Denise | 2026-02-17 | P2 — `PNL_DATA_ORGANIZATION_IMPLEMENTATION_PLAN_2026-02-17.md` |
| PNL-008 | P&L build owner | Alyssa Dimaano (Accounting Manager) — builds P&L for all 45 stores | Butch Formoso (CFO) | 2026-02-17 | P2 — `PNL_DATA_ORGANIZATION_IMPLEMENTATION_PLAN_2026-02-17.md` |
| PNL-009 | P&L final review | Denise Almario (Finance Sup) + Butch Formoso (CFO) by Day 15 | Butch Formoso (CFO) | 2026-02-17 | P2 — `PNL_DATA_ORGANIZATION_IMPLEMENTATION_PLAN_2026-02-17.md` |
| PNL-010 | Revenue data source (automated) | Supabase: `v_all_channel_daily` and `store_daily_closing` views. Filter `WHERE ws.status = 'Completed'`. NAIA (T3) NOT in Supabase — must add manually. | Sam / ERP team | 2026-02-17 | P2 — `PNL_DATA_ORGANIZATION_IMPLEMENTATION_PLAN_2026-02-17.md` |
| PNL-011 | COGS purchases data source | Ian Dionisio's 45 per-store Sales Invoice spreadsheets in his Google Drive (`2026 ORDERS > {MM} MONTH`). Folder ID: `1Z8pkxBu-pqxZg2NQzYkBx4nv23rBeHed` (Jan 2026). | Investigation / Sam | 2026-02-18 | P2 — `PNL_DATA_ORGANIZATION_IMPLEMENTATION_PLAN_2026-02-17.md` |
| PNL-012 | COGS SI spreadsheet AMOUNT column meaning | AMOUNT column = unit price per item (NOT line total). COGS line total = QTY × AMOUNT. | Sam / Investigation | 2026-02-18 | P2 — `PNL_DATA_ORGANIZATION_IMPLEMENTATION_PLAN_2026-02-17.md` |
| PNL-013 | P&L petty cash categories | 5 categories: (1) Operating Supplies, (2) Smallwares Expense, (3) Repairs & Maintenance, (4) Transportation & Travel, (5) Miscellaneous Expenses | Alyssa | 2026-02-17 | P2 — `PNL_DATA_ORGANIZATION_IMPLEMENTATION_PLAN_2026-02-17.md` |
| PNL-014 | SCM freight billing VAT treatment | SCM carrier costs reported VAT-inclusive. Apply /1.12 (VAT-exclusive) for P&L input. | SCM / Finance | 2026-02-17 | P2 — `PNL_DATA_ORGANIZATION_IMPLEMENTATION_PLAN_2026-02-17.md` |
| PNL-015 | In-store sales variance vs Apex — acceptable tolerance | 0.24–0.65% variance from SC/PWD VAT-exempt treatment differences. Acceptable. | Investigation / Alyssa | 2026-02-17 | P2 — `PNL_DATA_ORGANIZATION_IMPLEMENTATION_PLAN_2026-02-17.md` |
| PNL-016 | Pilot stores for Jan 2026 P&L | Market Market (full Q4 data), SM Megamall (high volume), Ayala Vermosa (smaller store) | Butch Formoso (CFO) / Sam | 2026-02-17 | P2 — `PNL_DATA_ORGANIZATION_IMPLEMENTATION_PLAN_2026-02-17.md` |
| PNL-017 | Goal: produce P&L independently from Apex | By March 15, 2026 — produce Feb P&L for all 45 stores using BEI data sources only | CFO Butch Formoso | 2026-02-17 | P2 — `PNL_DATA_ORGANIZATION_IMPLEMENTATION_PLAN_2026-02-17.md` |

---

## RBAC & Permissions (Finance-Owned)

| # | Decision | Value | Confirmed By | Date | Source |
|---|----------|-------|-------------|------|--------|
| RBAC-001 | Permission framework | Principle of least privilege. 5 principles: store-level = mobile-first limited; area/regional = territory read + approval write; HQ = domain full + cross-domain read; Finance/Audit = broad read; System Admin = full. | CEO (Sam) | 2026-01-15 | P2 — `PERMISSION_MATRIX_2026-01-15.md` |
| RBAC-002 | Accounting dashboard access role | "HQ User" role grants access to Accounting Dashboard at `my.bebang.ph/dashboard/accounting`. | E2E verified | 2026-02-06 | P1 — `finance-apex.md`, `CONTEXT.md` |
| RBAC-003 | Outstanding advances dashboard access role | "Finance - Advances" role for Butch (CFO), Mae (CPO), and designated Finance staff handling advances GL account. | Butch Formoso (CFO) | 2026-02-10 | P1 — `finance-apex.md` |
| RBAC-004 | Salary / compensation visibility | Restricted to HR Manager, CFO, System Manager only. Employee cannot see own salary in system. | CEO (Sam) | 2026-01-15 | P2 — `PERMISSION_MATRIX_2026-01-15.md` |
| RBAC-005 | Bank account number visibility | Restricted to Finance and CFO. Masked display for others. | CEO (Sam) | 2026-01-15 | P2 — `PERMISSION_MATRIX_2026-01-15.md` |
| RBAC-006 | Two-factor authentication — required roles | System Manager, CFO, HR Manager, Finance Manager, Audit Head = 2FA required. SCM Manager = recommended. | CEO (Sam) | 2026-01-15 | P2 — `PERMISSION_MATRIX_2026-01-15.md` |
| RBAC-007 | Finance approvals for Delivery Billing | Finance reviews and approves delivery billings (Pending → Approved → Sent) before emailing to franchisees. | CEO (Sam) / Billing design | 2026-02-14 | P2 — `BILLING_REDESIGN_2026-02-13.md` |
| RBAC-008 | BEI Delivery Rate — Finance role | Finance/Accounts Manager: Create, Write (set OR review rates). | CEO (Sam) | 2026-02-14 | P2 — `BILLING_REDESIGN_2026-02-13.md` |
| RBAC-009 | P&L Drive access — folder-level permissions | Finance shared drive members (sam, finance@, alyssa, accounting.bei, accounting.shaw) have full access. Ian Dionisio needs 02_COGS + 04_OpEx. Ronald/Melissa = 03_Payroll only. Noel/Jeson = 04_OpEx only. | Sam Nobleza (IT) | 2026-02-17 | P2 — `PNL_DATA_ORGANIZATION_IMPLEMENTATION_PLAN_2026-02-17.md` |
| RBAC-010 | Scope levels | Own / Store / Territory / Company / All | CEO (Sam) | 2026-01-15 | P2 — `PERMISSION_MATRIX_2026-01-15.md` |

---

## Gap Engineering (Finance-Owned)

| # | Decision | Value | Confirmed By | Date | Source |
|---|----------|-------|-------------|------|--------|
| GAP-F01 | Finance DocType fixes priority | G-021 (BEI Invoice JSON) and G-022 (Match Exception JSON) are MUST-HAVE quick wins (30 min and 15 min respectively) — blocks 3-way match | Gap Closure Roadmap | 2026-02-19 | P3 — `2026-02-19-master-gap-closure-roadmap.md` |
| GAP-F02 | Finance UI build priority | G-018 (Accounting Review UI) is highest-leverage Finance build — all 8 expense review APIs are live, Alyssa stuck in Frappe Desk | Gap Closure Roadmap | 2026-02-19 | P3 — `2026-02-19-master-gap-closure-roadmap.md` |
| GAP-F03 | Total active gaps — confirmed count | 19 MUST-HAVE, 29 SHOULD-HAVE, 20 NICE-TO-HAVE, 14 NOT-NEEDED, 4 ALREADY RESOLVED, 41 DUPLICATES (of 127 original) | Research (5 agents) | 2026-02-19 | P3 — `2026-02-19-master-gap-closure-roadmap.md` |

---

## Billing & Franchise Fees (Financial Aspects)

> *Rate-setting decisions are in `08_BUSINESS_DEV/DECISIONS.md`. This section covers financial structure and GL mapping only.*

| # | Decision | Value | Confirmed By | Date | Source |
|---|----------|-------|-------------|------|--------|
| BIL-001 | Billing stream structure | 3 streams: (A) Monthly Franchise Fees on 1st of month; (B) Delivery + Logistics + Goods Value per-stop real-time on delivery confirmation; (C) Other Charges (R&M, Payroll Allocation, Taxes) monthly/as-needed | CEO + CFO | 2026-02-13 | P1/P2 — `finance-apex.md`, `BILLING_REDESIGN_2026-02-13.md` |
| BIL-002 | Managed Franchise billing rates | Royalty: 7% gross + 12% VAT. Management fee: 2.5% gross + 12% VAT. Marketing: 5% gross + 12% VAT (**CORRECTED Feb 19: now VAT-inclusive**). eCommerce: **5%** of website-only online sales + 12% VAT (**CORRECTED Feb 19: was 4%, now 5%; VAT-inclusive; website only — not Foodpanda/GrabFood**). Delivery: (cost × 1.12) × 1.08. Logistics: (cost × 1.12) × 1.08. | CEO + CFO; corrections v1.3 + v1.4 | 2026-02-19 | P1/P2 + `FINANCE_PROCUREMENT_AUDIT_QUESTIONNAIRE_2026-02-19.md` Q6 |
| BIL-003 | JV stores — marketing fee | JV stores DO pay 5% Marketing fee. | CEO (Sam) — correction v1.3 | 2026-02-13 | P2 — `BILLING_REDESIGN_2026-02-13.md` |
| BIL-004 | Emailed billings — which store types | Only Full Franchise stores receive emailed billings/SOA. JV and Managed Franchise are BEI-operated — billing is internal accounting only. | CEO + CFO | 2026-02-14 | P1/P2 — `finance-apex.md`, `BILLING_REDESIGN_2026-02-13.md` |
| BIL-005 | Franchise handling fee markup | 8% "handling fee" on goods value for Full Franchise and Managed Franchise stores. JV stores pay at cost. | CEO (Sam) | 2026-02-14 | P1/P2 — `finance-apex.md`, `BILLING_REDESIGN_2026-02-13.md` |
| BIL-006 | POS data source for billing | Supabase (Mosaic API + Superadmin API nightly sync — already connected). | CEO + CFO | 2026-02-14 | P1/P2 — `finance-apex.md`, `BILLING_REDESIGN_2026-02-13.md` |
| BIL-007 | R&M billing cycle | Monthly for now. Future plan: charge per visit. | CEO (Sam) | 2026-02-13 | P2 — `BILLING_REDESIGN_2026-02-13.md` |
| BIL-008 | Warehouse-to-Department mapping approach | Maintain a SEPARATE mapping table (BEI Warehouse Department Mapping DocType with 52 store mappings). Not a field on Warehouse. | CEO (Sam) | 2026-02-14 | P2 — `BILLING_REDESIGN_2026-02-13.md` |
| BIL-009 | Marketing + eCommerce fees — VAT-inclusive | Both Marketing (5%) and eCommerce (5%) fees are **VAT-inclusive** (multiply by 1.12), same treatment as Royalty and Management fees. Butch rationale: "Safer for BIR as they might construe this as Revenue Stream by BEI and therefore subject to 12% Output VAT." | Butch Formoso (CFO) | 2026-02-19 | `FINANCE_PROCUREMENT_AUDIT_QUESTIONNAIRE_2026-02-19.md` Q6 |

---

## Inter-Company Transactions (BKI ↔ BEI)

| # | Decision | Value | Confirmed By | Date | Source |
|---|----------|-------|-------------|------|--------|
| ICT-001 | BKI-BEI VAT treatment | Hub transfers from BKI to BEI stores are taxable inter-company sales requiring 12% VAT. Currently charging VAT on deliveries/logistics/fees but VAT Sales Invoices not yet issued (compliance gap to close). | Butch Formoso (CFO) | 2026-02-20 | `CFO_INTERCOMPANY_Butch_Formoso_2026-02-20.md` Q1 |
| ICT-002 | Transfer pricing — JV vs Franchise | **JV stores: cost + 2.75% markup** (keeps BKI net taxable income ≤ PHP 5M for 20% CIT eligibility). Franchise stores: cost + 8% markup. Documented in Transfer Pricing Study using Cost Plus Method per RR 2-2013. Toll manufacturing evaluated 2026-02-22 and **rejected** — see ICT-006. | CEO (Sam) / CFO (Butch) | 2026-02-22 | `CFO_INTERCOMPANY_Butch_Formoso_2026-02-20.md` Q2; CEO decision 2026-02-21; toll mfg analysis 2026-02-22 |
| ICT-003 | Inter-company invoicing | BKI issues Sales Invoice (SI) and BEI receives Purchase Invoice (PI) for each hub transfer. Both documents required since separate legal entities. | Butch Formoso (CFO) | 2026-02-20 | `CFO_INTERCOMPANY_Butch_Formoso_2026-02-20.md` Q3 |
| ICT-004 | EWT on BKI payments — NOT required | BEI, BKI, and BEI Stores are NOT tagged as Top 20,000 Taxpayers under BIR Revenue District, so 1% EWT on goods and 2% EWT on services are not required for inter-company payments. Each entity files tax returns individually. | Butch Formoso (CFO) | 2026-02-20 | `CFO_INTERCOMPANY_Butch_Formoso_2026-02-20.md` Q4 |
| ICT-005 | BKI Frappe company setup | BKI must be created as a separate Company in Frappe to support inter-company SI/PI flow. | Butch Formoso (CFO) | 2026-02-20 | `CFO_INTERCOMPANY_Butch_Formoso_2026-02-20.md` Q5 |
| ICT-006 | Toll manufacturing — evaluated and rejected | Toll manufacturing (BEI buys RM, BKI processes for fee) would reduce BKI markup base from PHP 180M to PHP 44M, saving PHP 730K CIT/year. **Rejected** because JV stores are 51% BEI / 49% JV partner — the PHP 3.63M margin shift from BKI (100% BEI) to stores (51% BEI) results in PHP 1.78M/year leaking to JV partners, net -PHP 1.05M/year worse for BEI. Option A (merge BKI into BEI) also impractical — stores remain separate corps for liability isolation per CFO. **Final: BKI sells finished goods at cost + 2.75% (JV) / 8% (franchise).** | CEO (Sam) / CFO (Butch) | 2026-02-22 | `CFO_BKI_TOLL_MFG_REVIEW_Butch_Formoso_2026-02-21.md` (full Butch responses + post-review analysis) |
| ICT-007 | BKI → store revenue recognition timing (Incoterm) | **Destination terms.** BKI recognizes the sale (issues the Sales Invoice and books revenue) when the store signs the Delivery Receipt and accepts the goods — NOT on commissary dispatch. Control transfers on delivery + acceptance. Loss in transit is BKI's responsibility until the store accepts. Applies uniformly to all store corporations regardless of store type (JV, Managed Franchise, Full Franchise). Sales Invoice `posting_date` = receiving acceptance date. | CEO (Sam) | 2026-04-07 | CEO directive during S168 planning review |
| ICT-008 | BKI sales income GL account for store sales | Create new sub-account **`4000003 SALES — BKI TO STORES`** under the existing `4000000 SALES` group. Keeps BKI→store wholesale sales segregated from retail in-store sales (`4000001`) and online DTC sales (`4000002`) for clean P&L reporting and BIR return preparation. Configured via `BEI Settings.bki_sales_income_account`; Finance can rename or swap the account later without a code deploy. | CEO (Sam) | 2026-04-07 | CEO directive during S168 planning review; default choice from questionnaire Q4 |

---

## Procurement & AP Controls

| # | Decision | Value | Confirmed By | Date | Source |
|---|----------|-------|-------------|------|--------|
| PAP-001 | Match exception approval thresholds | Transactions **below PHP 500,000**: CPO (Mae) sole approval. Transactions **PHP 500,000 and above**: joint approval — CPO initial, CFO final. Per BEI Procurement Memo. | Butch Formoso (CFO) | 2026-02-19 | `FINANCE_PROCUREMENT_AUDIT_QUESTIONNAIRE_2026-02-19.md` Q7 |
| PAP-002 | PCF expense threshold policy | **No per-expense warning or block thresholds.** Threshold is based on total expenses incurred vs revolving fund and delivery fund — utilized at most 50%. The proposed PHP 3K warning / PHP 5K block thresholds are NOT adopted. | Butch Formoso (CFO) | 2026-02-19 | `FINANCE_PROCUREMENT_AUDIT_QUESTIONNAIRE_2026-02-19.md` Q10 |
| PAP-003 | PCF EWT categories | Since BEI not Top 20,000: Repairs/maintenance and delivery/courier services — see note (may require EWT if payee is professional). Professional services and rentals are NOT paid via PCF. Only mandatory EWT categories apply (professional fees 5-15%, rentals 5%). | Butch Formoso (CFO) | 2026-02-19 | `FINANCE_PROCUREMENT_AUDIT_QUESTIONNAIRE_2026-02-19.md` Q10 |
| PAP-004 | BIR filing format | **CSV/Excel** (manual upload to eBIRForms) AND **XML** (for BIR Alphalist) — both checked. Butch will provide BIR form templates. | Butch Formoso (CFO) | 2026-02-19 | `FINANCE_PROCUREMENT_AUDIT_QUESTIONNAIRE_2026-02-19.md` Q3 |
| PAP-005 | PCF auto-JV generation | **Yes — auto-generate JV per expense at approval time** (Dr Expense account, Cr 1113000 PCF Cash). Not batched daily/weekly, not manual monthly. | Butch Formoso (CFO) | 2026-02-19 | `FINANCE_PROCUREMENT_AUDIT_QUESTIONNAIRE_2026-02-19.md` Q5 |
| PAP-006 | PCF account structure | **One central 1113000** for all stores, differentiated by **Cost Center per store**. Not separate PCF accounts per store. | Butch Formoso (CFO) | 2026-02-19 | `FINANCE_PROCUREMENT_AUDIT_QUESTIONNAIRE_2026-02-19.md` Q5 |
| PAP-007 | Match exception expiry | **Yes — expire after 60 days.** Approved match exceptions must be re-requested if not used within 60 days. | Butch Formoso (CFO) | 2026-02-19 | `FINANCE_PROCUREMENT_AUDIT_QUESTIONNAIRE_2026-02-19.md` Q7 |
| PAP-008 | Price variance override — logging | **Yes — mandatory reason text** (logged with user ID and timestamp) when user acknowledges price variance >5% and proceeds. | Butch Formoso (CFO) | 2026-02-19 | `FINANCE_PROCUREMENT_AUDIT_QUESTIONNAIRE_2026-02-19.md` Q8 |
| PAP-009 | Price variance block threshold | **Block at >10% variance** — requires manager override. Below 10%: advisory warning only (with mandatory reason per PAP-008). | Butch Formoso (CFO) | 2026-02-19 | `FINANCE_PROCUREMENT_AUDIT_QUESTIONNAIRE_2026-02-19.md` Q8 |

---

## Revenue Recognition & SOA

| # | Decision | Value | Confirmed By | Date | Source |
|---|----------|-------|-------------|------|--------|
| REV-001 | Franchise fee revenue recognition (initial) | Billing approval timing **varies** — sometimes same month, sometimes next month. External auditor is **comfortable with current timing** (no accrual needed). Butch clarified: "Is this pertaining to Franchise Fee prior awarding of Store?" — yes, initial franchise fee. | Butch Formoso (CFO) | 2026-02-19 | `FINANCE_PROCUREMENT_AUDIT_QUESTIONNAIRE_2026-02-19.md` Q11 |
| REV-002 | Royalty fee revenue recognition (ongoing) | Billing approval **always completed within same month** as underlying sales period. System should **auto-accrue at month-end**, reverse when billing is approved. Butch clarified: "Is this pertaining to Royalty Fees based on Gross Sales?" — yes, ongoing monthly fees. | Butch Formoso (CFO) | 2026-02-19 | `FINANCE_PROCUREMENT_AUDIT_QUESTIONNAIRE_2026-02-19.md` Q11 |
| SOA-001 | SOA VAT line items | **Yes — show Net Amount \| VAT (12%) \| Total** per fee line on Statement of Account. BIR Sec. 113 compliant. | Butch Formoso (CFO) | 2026-02-19 | `FINANCE_PROCUREMENT_AUDIT_QUESTIONNAIRE_2026-02-19.md` Q12 |
| SOA-002 | SOA required information | **All 6 items checked:** (1) BEI TIN number, (2) Store TIN number, (3) Payment terms, (4) Bank details for payment, (5) Previous balance / running total, (6) Contact person for disputes. | Butch Formoso (CFO) | 2026-02-19 | `FINANCE_PROCUREMENT_AUDIT_QUESTIONNAIRE_2026-02-19.md` Q12 |
