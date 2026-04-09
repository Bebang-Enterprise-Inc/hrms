# Fork 1 Intercompany Accounting (Collection-Agent Model)

**Based on:** COA-175-013 (Fork 1 — collection-agent from day 1) + Collection Agent Letter at `data/_CLEANROOM/2026-04-09_franchise_agreements/04_BEI_BFC_Collection_Agent_Letter_DRAFT.md`

This file is the authoritative journal-entry reference for every BEI↔BFC interaction during the Fork 1 interim period and at cutover.

---

## Section A: The Fork 1 Model in One Diagram

```
     FRANCHISEE
         │
         │  pays franchise fee + VAT (cash or bank transfer)
         │
         ▼
       BEI (collection agent, disclosed)
         │
         │  cash physically received
         │  books: Dr Cash / Cr 2104200 DUE TO BFC - BEI
         │  (NO revenue recognized, NO output VAT)
         │
         ▼
     holds in trust for BFC until cutover
         │
         ▼  [at cutover: BFC bank account opens]
         │
         │  BEI sweeps cash to BFC's new bank
         │  BEI books: Dr 2104200 DUE TO BFC / Cr Cash
         │
         ▼
       BFC (principal)
         │
         │  during Fork 1, BFC has already been accruing the fee each month:
         │  books: Dr 1104200 DUE FROM BEI - BFC
         │         Cr 4000231-235 (appropriate fee)
         │         Cr 2102205 OUTPUT VAT PAYABLE - BFC (12%)
         │
         │  at cutover: Dr Cash / Cr 1104200 DUE FROM BEI - BFC
         │
         ▼
       BIR
         │  BFC files 2550Q under BFC TIN, pays 12% Output VAT
         │  BFC files 1702Q under BFC TIN, pays corporate income tax
```

---

## Section B: Journal Entries by Event

### B.1 Franchisee is invoiced for monthly royalty (e.g., 7% of ₱500,000 = ₱35,000 + 12% VAT)

**Sales Invoice issued by BFC (not BEI), with BFC's BIR OR.**

Franchisee's books (not our concern, but for reference):
```
Dr Royalty Fee Expense                35,000
Dr Input VAT                           4,200
   Cr Accounts Payable - BFC                      37,100
   Cr CWT Payable (2%)                               700
```

**BFC's books (principal):**
```
Dr 1104200 DUE FROM BEI - BFC         39,200    ← Receivable net (BEI will collect)
Dr (CWT receivable - BFC)                700    ← 2% creditable withholding credit
   Cr 4000231 ROYALTY FEES - BFC                 35,000
   Cr 2102205 OUTPUT VAT PAYABLE - BFC            4,200   ← BFC owes VAT to BIR
```

**BEI's books (agent): NO ENTRY.** BEI hasn't touched cash yet.

### B.2 Franchisee pays BEI the ₱39,200 (BEI acts as collection agent)

**BEI's books (agent):**
```
Dr Cash on Hand - BEI                 39,200
   Cr 2104200 DUE TO BFC - BEI                   39,200
```

**BFC's books (principal): NO ENTRY.** The receivable stays on BFC's books until actual cash arrives from BEI. BFC's DUE FROM BEI went up in B.1 when the fee was earned, not in B.2 when BEI collected.

### B.3 Franchisee sends CWT certificate (Form 2307) naming BFC

No entry on BEI. On BFC: the Dr (CWT receivable) booked in B.1 is now supported by the certificate. BFC carries the CWT credit as an asset to offset against BFC's own income tax liability at year-end.

### B.4 BFC pays its 12% Output VAT to BIR (quarterly, e.g., 2550Q)

**This is the VAT cash timing problem.** BFC has recognized Output VAT liability but has no bank account.

**Option A — BEI advances VAT payment to BIR on BFC's behalf:**
```
BEI's books:
Dr 1104300 ADVANCES TO BFC - BEI       4,200    ← new account, optional
   Cr Cash on Hand - BEI                           4,200

BFC's books:
Dr 2102205 OUTPUT VAT PAYABLE - BFC    4,200    ← clears VAT payable
   Cr 2104300 DUE TO BEI - BFC                    4,200    ← owed back to BEI
```

**Option B — BEI releases a partial sweep of `2104200 DUE TO BFC` cash specifically for VAT:**
```
BEI's books:
Dr 2104200 DUE TO BFC - BEI            4,200    ← reduce the liability by VAT amount
   Cr Cash on Hand - BEI                           4,200

BFC's books:
Dr 2102205 OUTPUT VAT PAYABLE - BFC    4,200
   Cr 1104200 DUE FROM BEI - BFC                   4,200    ← reduce the receivable
```

Option B is simpler (no new accounts) and economically cleaner (it's BFC's own money being used to pay BFC's own VAT). **Option B is the default unless Butch prefers Option A.** See OQ-2 in `05_OPEN_QUESTIONS_FOR_BUTCH.md`.

### B.5 Cutover Day — BFC's operating bank account opens and is tested

BEI has been accumulating cash under `2104200 DUE TO BFC - BEI`. Say the balance is ₱1,200,000 after 3 months.

**BEI's books:**
```
Dr 2104200 DUE TO BFC - BEI        1,200,000
   Cr Cash on Hand - BEI                     1,200,000
```

BEI wires ₱1,200,000 to BFC's new bank account.

**BFC's books:**
```
Dr Cash on Hand - BFC              1,200,000
   Cr 1104200 DUE FROM BEI - BFC             1,200,000
```

Both intercompany accounts now zero. Both entities balance. Collection-agent letter auto-terminates per §5.3.

### B.6 Post-cutover — franchisee pays BFC directly

**BFC's books:**
```
Dr Cash on Hand - BFC                 39,200
Dr CWT Receivable - BFC                  700
   Cr 4000231 ROYALTY FEES - BFC                 35,000
   Cr 2102205 OUTPUT VAT PAYABLE - BFC            4,200
```

**BEI's books: NO ENTRY.** BEI is no longer involved in any franchise fee cash flow.

---

## Section C: JV Flows (for contrast — permanently BEI, not collection-agent)

The Grand Central Gabaldon JV Agreement routes fees permanently to BEI. Fork 1 collection-agent rules do NOT apply to JV fees.

### C.1 JV store pays 5% marketing to BEI (per JV §8.1)

**BEI's books (BEI is the principal here, not an agent):**
```
Dr Cash on Hand - BEI                 28,000    ← 5% × ₱500,000 + 12% VAT = ₱28,000
   Cr 4000234 MARKETING FEES - BEI               25,000
   Cr 2102205 OUTPUT VAT PAYABLE - BEI            3,000
```

BEI's OR, BEI's VAT return, BEI's revenue. Permanent. No BFC involvement.

### C.2 JV store pays ₱2M Brand Growth Fee to BEI (per JV §2 / §3.4)

Point-in-time recognition per PFRS 15.B58 (right-to-use license).

**BEI's books:**
```
Dr Cash on Hand - BEI              2,240,000
   Cr 4000005 BRAND GROWTH FEE INCOME - BEI   2,000,000    ← legacy account kept per COA-175-016
   Cr 2102205 OUTPUT VAT PAYABLE - BEI          240,000
```

Recognized in full on the execution date of the JV Agreement. Not amortized.

---

## Section D: Accounts required for Fork 1 to work

| Account | Company | Status |
|---|---|---|
| `2104200 DUE TO BFC - BEI` | BEI | **NEW** — create in Phase 6 |
| `1104200 DUE FROM BEI - BFC` | BFC | **NEW** — create in Phase 1 (during BFC Company setup) |
| `2102205 OUTPUT VAT PAYABLE - BFC` | BFC | **NEW** — create in Phase 1 (pulled forward from original Phase 2 per COA-175-014) |
| `4000231 ROYALTY FEES - BFC` | BFC | **NEW** — Phase 2 template creates |
| `4000232 MANAGEMENT FEES - BFC` | BFC | **NEW** — Phase 2 template |
| `4000233 FRANCHISE FEES - BFC` | BFC | **NEW** — Phase 2 template |
| `4000234 MARKETING FEES - BFC` | BFC | **NEW** — Phase 2 template |
| `4000235 E-COMMERCE FEES - BFC` | BFC | **NEW** — Phase 2 template |
| `1101xxx Cash on Hand - BFC` | BFC | Frappe Standard CoA creates during Phase 1 Company insert |
| `CWT Receivable - BFC` | BFC | Check Frappe Standard CoA; add if missing |
| **Optional** (Option A in B.4): `1104300 ADVANCES TO BFC - BEI` | BEI | Only if Butch chooses VAT advance route |
| **Optional** (Option A in B.4): `2104300 DUE TO BEI - BFC` | BFC | Only if Butch chooses VAT advance route |

---

## Section E: Extraction Query for Any Future Restatement

Even with Fork 1, we still want to be able to extract every Fork-1-era transaction cleanly. The query for `2104200 DUE TO BFC - BEI` GL entries gives the full picture:

```sql
-- All cash BEI collected on BFC's behalf during Fork 1
SELECT
    ge.posting_date,
    ge.account,
    ge.voucher_type,
    ge.voucher_no,
    ge.party,
    ge.party_type,
    ge.debit,
    ge.credit,
    ge.remarks,
    ge.cost_center
FROM `tabGL Entry` ge
WHERE ge.company = 'Bebang Enterprise Inc.'
  AND ge.account = '2104200 - DUE TO BFC - BEI'
  AND ge.is_cancelled = 0
ORDER BY ge.posting_date, ge.party;
```

Mirror query on BFC's `1104200` gives BFC's side.

Both sides should **always balance**. If the two totals diverge, the collection-agent reconciliation per letter §6.2 must resolve the discrepancy within 5 business days.

---

## Section F: Frappe Implementation Notes

1. **Sales Invoice by BFC** — BFC issues SIs to franchisees. The SI's "Income Account" is `4000231-235` (per fee type), and the SI template must force the "Debit To" receivable to be `1104200 DUE FROM BEI - BFC` rather than BFC's normal `Debtors` account. This requires either a custom SI type or a Customer-level override on each BFC Franchisee customer. **This is the main operational complexity of Fork 1** — the SI doesn't post cash directly to BFC; it posts a receivable against BEI.

2. **Payment Entry by BEI** — When BEI receives cash, BEI creates a Payment Entry with `party_type=Supplier` or a dedicated `party_type=Intercompany` where the party is "BFC" and the "Paid To" account is `2104200 DUE TO BFC - BEI`. Alternative: a plain Journal Entry (no party, just accounts) which is simpler but loses the traceability that Payment Entry gives.

3. **Reconciliation** — The letter §6.2 requires monthly reconciliation between BEI's `2104200` and BFC's `1104200`. Frappe's Intercompany Reconciliation module (or a custom script) can automate this.

4. **Output VAT timing** — BFC recognizes Output VAT on invoice date (per standard VAT accrual), not on cash receipt. This is already how Frappe handles SIs with standard VAT templates. BFC needs its own `Sales Taxes and Charges Template` with `2102205 OUTPUT VAT PAYABLE - BFC` as the account head.

5. **CWT treatment** — 2% CWT is withheld by the franchisee. BFC's receivable from BEI is the **gross** fee (before CWT), not the net. BEI collects the **net** cash (post-CWT). The difference (2%) is the CWT credit that BFC claims against its own income tax. Reconciliation should match BEI's cash receipt against BFC's receivable LESS CWT.

---

## Section G: What this model does NOT handle

1. **Refunds / credits** to franchisees — if a franchisee overpays and BEI refunds, the JE is:
   - BEI: `Dr 2104200 DUE TO BFC - BEI / Cr Cash on Hand - BEI`
   - BFC: `Dr 1104200 DUE FROM BEI - BFC (credit) / Cr 4000231-235 (debit, contra)`
   - Must be coordinated between both sets of books.

2. **Franchisee bounced checks** — if franchisee pays by check that bounces, BEI reverses the cash receipt, BFC keeps the receivable (fee was still earned, just unpaid).

3. **Multi-period accruals** — if BFC's OR is issued in month 1 but BEI doesn't collect until month 2, BFC's `1104200` is already booked in month 1. BEI's `2104200` only posts in month 2 when cash arrives. For the intervening period the two books won't balance — this is normal timing difference, resolved in the monthly reconciliation.

4. **Franchisee direct-to-BFC payments before cutover** — if any franchisee ever tries to pay BFC directly during the interim, BFC has no bank to receive it. Either the franchisee gets rerouted to BEI's account, or a temporary hold account is used.

These edge cases are documented here for Phase 10 verification and for Butch's reference, not for Phase 1 initial implementation.
