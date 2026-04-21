# BEI Receipt-Based Payment — Finance Reconciliation Guide

**Audience:** Denise (takes over Finance 2026-04-27 after Juanna leaves)
**Prerequisites:** Read `ONBOARDING_3PL_COMMS.md` first for the overall
architecture. This guide assumes you understand the data flow.

---

## Your role in this pipeline

You don't OPERATE the receiving pipeline — Ian does that. Your role is
RECONCILIATION: making sure what Sheet C says got received matches what
ends up in the Frappe ERP as GRs and RFPs, and that payments release on
the correct dates.

---

## Daily reconciliation flow (30 min)

### 1. Morning: confirm yesterday's pipeline closed

Open Sheet C `02_All_Receipts_Consolidated`. Filter Timestamp = yesterday.
Count rows.

Then open Frappe Purchase Receipt list. Filter by Posting Date = yesterday.
Count rows.

**Expected:** Frappe Purchase Receipt count = Sheet C yesterday count
(minus rows where the supplier/PO was invalid and went to Variance Queue).

**Discrepancy >5%:** means Ashish's Procurement AppSheet didn't pick up
some rows from `06_Pending_GR`. Flag for Ashish. Don't manually fix in
Frappe; fix the upstream by identifying why `Pending_GR` rows weren't
claimed.

### 2. Match SI uploads to payments queue

For each row in Sheet C `02_All_Receipts_Consolidated` where
`SI_Matched=TRUE` and the DR is >1 day old:

- Does the corresponding RFP exist in Frappe (by PO Number + Supplier)?
- Is the RFP `Amount = SI Amount` (the value from the supplier's upload)?
- Is the RFP scheduled payment date = `DR date + Supplier.Payment_Terms`?

Any mismatch = reconciliation issue. Correct the RFP, note the reason in
the RFP's internal note, and Slack the change to Luwi for awareness.

### 3. Chase unmatched DRs (SI_Matched=FALSE, age >3 days)

Export from Sheet C:
```
Filter: SI_Matched=FALSE AND Timestamp < (today - 3 days)
```

For each row:
- Check if the supplier has an upload in `03_Supplier_SI_Uploads` that
  just didn't auto-match (typo in PO# or SI#) — review Match Queue
- If no upload at all: email the supplier (cc Cayla) with the SI upload
  form URL
- Do NOT release payment on a DR without a matching SI — BIR input VAT
  requires the SI

---

## Weekly reconciliation (Monday 10:00)

### 1. Sheet C vs Frappe GL reconciliation

Sum of `Amount` column in last week's `02_All_Receipts_Consolidated`
(where `SI_Matched=TRUE`) should equal sum of GR entries posted to the
`Stock in Hand` account in Frappe for the same suppliers.

### 2. EWT and VAT check

For each supplier in the week's receipts:
- Open Procurement AppSheet Suppliers tab
- Read `EWT Rate` and `VAT Registered` fields
- Spot-check 3 RFPs in Frappe — confirm EWT computed at the right rate
  and VAT input claimed correctly

### 3. Tier classification review

Pull `07_Full_Suppliers_Master` rows where `Tier` is blank or incorrect.
Compare against latest volume (from GL). Tier A is typically > ₱2M/year
purchases. Update Procurement AppSheet where reassignment makes sense.

---

## Monthly (first 3 business days of the month)

### 1. BIR Form 2307 reconciliation

For each supplier where you paid in the previous month:
- Total EWT withheld per Frappe
- Total on BIR Form 2307 issued to supplier
- These must match. Discrepancies usually come from manual RFP overrides
  — trace back in Frappe's activity log.

### 2. Paper SI audit

Every SI upload in `03_Supplier_SI_Uploads` should eventually have a
physical paper SI in your files (BIR 3-year retention). Spot-check 10
random uploads from the prior month:
- Drive link from the upload opens a PDF (click it in the Uploads tab)
- The PDF matches the paper SI in your physical file
- If paper SI missing: email the supplier to re-send paper

### 3. Pending GR age audit

Any row in Sheet C `06_Pending_GR` with `Status=PENDING` and
`Picked_Up_By_AppSheet=FALSE` for >7 days indicates Ashish's AppSheet
isn't polling. Escalate to Ashish.

---

## Key principles (locked by CEO 2026-04-20)

1. **Payment is NOT gated by paper SI.** It's gated by (DR received +
   supplier upload). Paper is BIR retention only.

2. **The OR is not a payment gate.** Per BIR EoPT Act (RA 11976), SI is
   the single principal document for both goods and services since 2024.
   The OR is demoted to supplementary and is NOT valid for input VAT
   substantiation.

3. **Disputes happen AFTER payment.** If a supplier under-delivers or
   delivers defective goods, we pay per the DR + SI, then raise a dispute
   with the supplier. Never withhold payment to force the dispute.

4. **Approval chain (locked while CFO seat vacant):**
   - RFPs ≤ ₱1M: Luwi (prepare) → Mae (approve)
   - RFPs > ₱1M: Luwi → Mae → Sam
   - No "CFO approval" step exists until Sam refills the seat

5. **Internal Customer SIs (S206 labor cost-sharing) are NOT the same as
   supplier SIs.** Never use an Internal Customer record for a regular
   supplier invoice. See `docs/STORE_COMPANY_CANONICAL.md` for the
   Company/Customer model.

---

## Tools you need access to

- Frappe (`hq.bebang.ph`) — Finance role ✓ via your employee account
- Sheet C (BEI Receiving Master) — Cayla or Ian will share with you
- Procurement AppSheet — read access from Ashish
- Cloud Scheduler console (read-only) — not needed day-1, get it from
  Sam later
- BIR eFPS credentials — get from Juanna during handover before 04-27

---

## Escalation matrix

| Issue | Contact |
|---|---|
| Frappe GR missing for a receipt I see in Sheet C | Ashish |
| RFP amount doesn't match SI upload amount | Luwi |
| Payment terms look wrong | Cayla (supplier master) |
| BIR / compliance question | Sam (while CFO seat vacant) |
| Automation stopped working | Sam + Ian |

---

_Version 2026-04-21 (S210 Phase 11 guide pack). Scheduled handover from
Juanna 2026-04-27._
