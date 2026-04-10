# Butch Formoso Questionnaire Answers (2026-04-10)

**Source:** `F:\Downloads\butch_s175_questionnaire.docx` (returned with inline annotations marked "ARRF :")
**Respondent:** Butch Formoso, Senior Accountant / CFO
**All 5 questions answered + overall fork choice.**

---

## Overall Fork Decision: FORK 1 (Collection-Agent from day 1) — LOCKED

Butch's verbatim: *"I would humbly recommend Option A to consider that this matches the signed contract with our Franchisee, BIR Compliant, Low Risk of Audit Findings and no need for financials to be restated. The companies just need to execute a Collection-Agent Agreement between BFC and BEI. Then, BEI is only the agent so BFC BIR-Registered documents will be issued for this revenue streams."*

---

## OQ-1: BFC BIR OR Booklet Status — NOT READY (BLOCKER for first collection)

**Answer:** BFC is NOT BIR-ready for OR issuance. Sir Noel (in charge of this task) has NOT yet applied the Authority to Print for BIR-registered Invoices and Official Receipts of BFC.

**Action taken by Butch:** Already asked Noel to apply the Authority to Print in favor of BFC now.

**Impact on S178:** Fork 1 structural setup proceeds (GL accounts, Collection Agent Letter, SI template config). First real franchise fee collection is BLOCKED until BFC OR booklet is printed + registered at RDO 044. Timeline: typically 2-4 weeks from BIR application.

**Butch's recommendation:** Fork 1 is the correct path. Get the OR booklet printed ASAP.

---

## OQ-2: BFC Output VAT Payment Mechanism — OPTION B (Partial Sweep)

**Answer:** Option B — partial sweep of DUE TO BFC cash for BFC's VAT payment to BIR.

**Additional info from Butch:** BFC needs to open bank accounts:
- **BDO** as Depository Bank
- **UnionBank** as Disbursing Bank (handles all BIR-related payments)
- As confirmed with Ma'am Rox of BDO: **no BFC bank account exists yet.**

**Impact on S178:** No new intercompany advance accounts needed (Option A's `1104300 ADVANCES TO BFC` and `2104300 DUE TO BEI - BFC` are NOT created). The existing `2104200 DUE TO BFC - BEI` and `1104200 DUE FROM BEI - BFC` are sufficient.

---

## OQ-3: BFC Bank "Fully Operational" Cutover Trigger — OPTION C (Full Cycle)

**Answer:** Option C — full receive-AND-pay cycle completed (inbound deposit + outbound BIR payment both tested).

**Additional info:** Same BDO (depository) + UnionBank (disbursing) pattern as OQ-2. Cutover = BFC can receive cash from franchisees AND disburse BIR payments through its own accounts.

**Impact on S178:** Collection Agent Letter §5 termination clause uses "fully opened and tested" = Option C definition. No ambiguity on cutover day.

---

## OQ-4: BEI Settings input_vat_goods_account — FIX NOW

**Answer:** Fix now. Link `INPUT VAT - GOODS - Bebang Enterprise Inc.` to BEI Settings.

**Impact on S178:** Execute in Phase 1 (zero dependencies). One SSM `set_single_value` call.

---

## OQ-5: JV Fee GL Routing — Customer Group Filter + Brand Growth Fee Clarification

**Answer:** Customer Group filter on `4000234 MARKETING FEES` / `4000235 E-COMMERCE FEES`.

**Butch's Brand Growth Fee clarification:** Butch says Brand Growth Fee / Franchise Fees should be on `4000233 FRANCHISE FEES`, not legacy `4000005`. He recommends: if we want to separate JV Brand Growth Fee from BFC Franchise Fees, create `4000236 BRAND GROWTH FEE` for JV stores, keeping `4000233` clean for franchise-store franchise fees.

**Sam's decision (2026-04-10):** Butch decides the specific GL for Brand Growth Fee; all that matters is it stays on BEI. Current `4000005` preserved as-is (0 GL entries). Butch can relocate it to `4000233` or `4000236` at his discretion in a future session. Not a blocker for S178.

---

## Summary Table

| OQ | Question | Answer | Status |
|---|---|---|---|
| Overall | Fork 1 or Fork 2? | **Fork 1** (collection-agent from day 1) | LOCKED |
| OQ-1 | BFC OR booklet? | **Not ready** — Noel applying Authority to Print now | BLOCKER for first collection (not for GL setup) |
| OQ-2 | VAT payment mechanism? | **Option B** (partial sweep) | LOCKED |
| OQ-3 | Cutover trigger? | **Option C** (full receive + pay cycle) | LOCKED |
| OQ-4 | input_vat_goods_account? | **Fix now** | EXECUTE in S178 Phase 1 |
| OQ-5 | JV fee routing? | **Customer Group filter** + Brand Growth Fee at Butch's discretion | LOCKED (minor GL placement TBD) |

---

## New dependencies surfaced by Butch's answers

1. **BFC Authority to Print** — Sir Noel applying now. Track with Noel for timeline (~2-4 weeks estimated).
2. **BFC bank accounts** — BDO (depository) + UnionBank (disbursing). Ma'am Rox confirmed none exist yet. Track with Juanna Alcober.
3. **Collection-Agent Agreement** — draft exists in cleanroom. Needs Sam's signature on both sides + board resolutions. Can sign as soon as BFC OR booklet is confirmed.
