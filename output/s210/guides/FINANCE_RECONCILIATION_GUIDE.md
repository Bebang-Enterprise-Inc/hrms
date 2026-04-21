# BEI Receiving Pipeline — Finance Reconciliation Playbook

**Audience:** Denise (effective Finance lead **2026-04-28**; Juanna's last day is 2026-04-27)
**Prerequisites:** Read `ONBOARDING_3PL_COMMS.md` for the data flow.

---

## Your role

You don't OPERATE the receiving pipeline — Ian does. Your job is
RECONCILIATION: confirm what Sheet C says got received matches what ends
up in Frappe as GRs and RFPs, and that payments release on the right
dates for the right amounts.

---

## Daily (30 min)

### 1. Confirm yesterday's pipeline closed (morning)

Open Sheet C `02_All_Receipts_Consolidated`. Filter Timestamp = yesterday.
Count rows.

Then open Frappe Purchase Receipt list. Filter Posting Date = yesterday.
Count rows.

**Expected:** Frappe count = Sheet C count minus rows in Sheet C
`05_Variance_Queue` with yesterday's timestamp.

**Discrepancy >5%:** Ashish's Procurement AppSheet didn't pick up some
`06_Pending_GR` rows. Ping Ashish. Don't hand-fix in Frappe — fix the
upstream by finding why rows weren't claimed.

### 2. Check RFPs match SI uploads

For each row in Sheet C `02_All_Receipts_Consolidated` where
`SI_Matched=TRUE` and DR is >1 day old, verify in Frappe:

- RFP exists for the (PO Number, Supplier) pair
- RFP Amount = SI Amount (from the supplier's upload — see
  `03_Supplier_SI_Uploads` row)
- RFP scheduled payment date = DR date + Supplier.Payment_Terms

Any mismatch: correct the RFP, note the reason in the RFP's internal
note, ping Luwi.

### 3. Chase DRs older than 3 days with no SI match

Filter Sheet C `02_All_Receipts_Consolidated` for `SI_Matched=FALSE` AND
`Timestamp < today - 3 days`.

For each:
- Check `04_Match_Queue` — maybe the supplier uploaded but it didn't
  auto-match (typo on either side). Ian should be handling these;
  coordinate if there's a backlog.
- If no upload at all: email the supplier (cc Cayla) with the upload
  form URL.
- Do NOT release payment on a DR without a matching SI.

---

## Weekly (Monday 10:00)

### 1. Sheet C vs Frappe GL reconciliation

Sum `Amount` in last week's `02_All_Receipts_Consolidated` rows where
`SI_Matched=TRUE`. Should equal sum of GR entries posted to `Stock in
Hand` in Frappe for the same suppliers.

### 2. EWT + VAT spot-check

Pick 3 RFPs from the week at random. For each:
- Open Procurement AppSheet Suppliers tab — read `EWT Rate` and
  `VAT Registered`
- Confirm Frappe RFP applied the right EWT rate + input VAT handling

### 3. Tier classification check

Pull Sheet C `07_Full_Suppliers_Master` rows where `Tier` is blank or
looks wrong (high-volume suppliers marked Tier B, etc.). Tier A rule of
thumb: > ₱2M/year purchases. Update Procurement AppSheet where
reassignment makes sense.

---

## Monthly (first 3 business days)

### 1. BIR Form 2307 reconciliation

For each supplier paid in the prior month:
- Total EWT withheld per Frappe
- Total on BIR Form 2307 issued to the supplier
- Numbers must match. Discrepancies usually = manual RFP overrides.
  Trace in Frappe's activity log.

### 2. Paper SI spot-check (10 random uploads)

Pick 10 random rows from `03_Supplier_SI_Uploads` from the prior month.
- Drive link opens the uploaded PDF (click from Uploads tab)
- PDF matches the paper SI in your physical file
- If no paper on file: email the supplier for a re-send

### 3. Stale Pending GR audit

Any row in Sheet C `06_Pending_GR` with `Status=PENDING` and
`Picked_Up_By_AppSheet=FALSE` for >7 days means Ashish's AppSheet isn't
polling. Escalate to Ashish.

---

## Hard rules (will bite you otherwise)

1. **Payment releases on DR + SI upload.** Don't wait for paper SI to
   arrive before queuing payment — that's the old workflow we're
   replacing.

2. **Disputes happen AFTER payment.** Under-delivery or defective goods
   → pay the DR + SI, raise dispute with supplier afterward. Do NOT
   withhold payment to force the issue.

3. **Approval chain (while CFO seat is vacant):**
   - RFPs ≤ ₱1M: **Luwi prepares → Mae approves**
   - RFPs > ₱1M: **Luwi → Mae → Sam**
   - There is no CFO step until Sam fills the seat.

4. **Never use an Internal Customer record for a supplier invoice.**
   Internal Customers exist for inter-BEI-entity labor cost-sharing
   journals only — never for outside supplier transactions. If you see
   "Internal Customer" as the recipient on what should be a supplier SI,
   stop and ping Sam.

---

## Tools you'll need

- Frappe (`hq.bebang.ph`) — Finance role via your employee account
- Sheet C BEI Receiving Master — Cayla or Ian will share
- Procurement AppSheet — read access from Ashish
- BIR eFPS credentials — get from Juanna during handover on or before
  2026-04-27

---

## Escalation

| Issue | Contact |
|---|---|
| Frappe GR missing for a receipt I see in Sheet C | Ashish |
| RFP amount doesn't match the supplier's upload | Luwi |
| Payment terms look wrong | Cayla (owns supplier master) |
| Automation broken (Scheduler job red, Chat spam, etc.) | Sam + Ian |
| BIR interpretation question | Sam (temporarily; proper CFO when hired) |

---

_Version 2026-04-21. Juanna's last day 2026-04-27; Denise effective 2026-04-28._
