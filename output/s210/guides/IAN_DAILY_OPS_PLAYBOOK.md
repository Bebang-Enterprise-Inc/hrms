# BEI Receiving — Daily Ops Playbook (Ian)

**Audience:** Ian Dionisio — BEI Procurement operations lead
**Cadence:** 15 minutes every morning, 10 minutes late afternoon
**Goal:** Keep the Tier A Receipt-Based Payment pipeline healthy; suppliers paid on time; 3PL warehouses happy.

---

## Morning checklist (07:30-07:45 PHT)

### 1. Read the CEO daily email

Subject: `[BEI Receiving] Daily KPI digest — YYYY-MM-DD`
Lands in your inbox at 07:00 PHT.

Scan these numbers:

| KPI | Healthy | Yellow flag | Red flag — act now |
|---|---|---|---|
| Today's receipts (3MD + Pinnacle + Shaw) | Matches your expected arrivals | 1-2 fewer than expected | Zero receipts — check scheduler + 3PL access |
| SI match rate | > 80% | 60-80% | < 60% — chase Tier A suppliers |
| Stale DR count (>72h no SI) | < 5 | 5-20 | > 20 — structural issue |
| Pending GR depth | < 10 | 10-30 | > 30 — Ashish's AppSheet may be stuck |
| Orphan SI count | < 5 | 5-15 | > 15 — check Match Queue tab |

### 2. Open Sheet C Dashboard

https://docs.google.com/spreadsheets/d/1_Ir5O5AW7hOjcvCTXsP06cF3sai9hcefDFrBOTRHOh0/edit

Click the `01_Dashboard` tab. All values are live formulas that recompute
on open. If anything shows `#N/A` or `#ERROR`, Apps Script is broken —
escalate to Sam immediately.

### 3. Clear the Match Queue (`04_Match_Queue`)

Each row = a supplier uploaded an SI that didn't auto-match to a delivery
receipt. The `Warehouse` column tells you which 3PL to chase first.
Reasons are usually:
- Supplier uploaded before 3PL logged the delivery → wait 10 min; if still
  unmatched after 30 min, investigate (check the matching 3PL sheet by
  Warehouse)
- Typo in PO# or SI# on EITHER side → identify whose error, fix, mark resolved
- Supplier uploaded an SI that belongs to a different BEI company (BKI,
  franchise) → mark as "wrong recipient" in Resolution column and dismiss

For each orphan:
1. Find the matching DR in `02_All_Receipts_Consolidated` (search by PO
   number or supplier name)
2. If found → fix the typo in whichever side was wrong, manually set
   `SI_Matched=TRUE` on the DR row, tag the Match Queue row `Resolution=Matched to RR-XXXX` and `Status=CLOSED`
3. If truly orphan → tag `Status=DISMISSED` with reason

### 4. Resolve Variance Queue (`05_Variance_Queue`)

Each row = a DR that had a validation failure OR aged >72h without an SI.

Common reasons:
- Supplier-mismatch (3PL typed "DIMAX" but PO says "Dimax Food Wholesaling")
  → check which name is authoritative, fix in source sheet if needed
- PO not found in Open POs master → PO may have been closed before
  delivery; talk to procurement
- Qty exceeds PO balance → over-delivery; need procurement approval or
  return policy
- Stale DR >72h → escalate to the supplier; their SI hasn't arrived

For each row: note the reason in the `Resolution` column, mark `Status=CLOSED` when resolved. Do NOT delete — it's an audit trail.

---

## Afternoon checklist (16:30-16:40 PHT)

### 1. Expected deliveries landed?

Open `08_Full_Open_POs`. Filter by `Delivery Needed By = today`. Check
against `02_All_Receipts_Consolidated` for matching POs.

Missing deliveries → WhatsApp/call the supplier, log the call in a
parking-lot note (not the sheet).

### 2. Chat spaces review

Open the SCM Chat space (`spaces/AAQArCi8zjE`) and scan the day's
automated receipt notifications. Look for:
- Unusually high quantities (may indicate supplier over-shipping)
- Off-hours deliveries (should be rare)
- Repeated "validation failed" notifications (pattern → systemic issue)

### 3. Verify scheduler health

Open https://console.cloud.google.com/cloudscheduler?project=quiet-walker-475722-s2
Check that 4 jobs show `ENABLED` and recent success:

- `s210-poll-all` — should fire every minute
- `s210-age-variance-hourly` — should fire every hour
- `s210-refresh-masters-06` — should fire at 06:00 PHT (check tomorrow morning)
- `s210-ceo-email-07` — should fire at 07:00 PHT (check tomorrow morning)

Any red/failure indicator → check logs, escalate to Sam.

---

## Weekly (Monday 09:00 PHT)

### 1. Supplier adoption review

Pull `02_All_Receipts_Consolidated` for the previous 7 days. Compute per-
supplier SI match rate. List the top 5 non-adopters and give to Cayla.

### 2. Scheduler job report

GCP Console → Cloud Scheduler → each s210-* job → History tab. Verify:
- Zero AttemptFailed in the last 7 days
- Median response time < 10s for pollAll
- All hourly variance aging runs completed

### 3. Sheet C growth check

Count rows in `02_All_Receipts_Consolidated`. If > 5000, we're approaching
Sheet performance limits for 2026 — plan end-of-year rotation to
`BEI Receiving Master 2027`.

---

## Escalations

| Issue | Owner | Contact |
|---|---|---|
| Apps Script error (Chat spam, Variance flood, Dashboard #ERROR) | Sam | `sam@bebang.ph` |
| Supplier resistance to uploading | Cayla | `cayla@bebang.ph` |
| PO issues (wrong balance, closed POs, routing) | Mae → Luwi | via Google Chat |
| 3PL not logging receipts | Jay (Pinnacle), you (3MD) | direct call |
| BIR / compliance question | Ashish + Denise | via Chat |

---

## Emergency rollback

If the automation is doing damage (mass incorrect notifications, wrong
rows appearing):

1. GCP Console → Cloud Scheduler → **Pause all 4 `s210-*` jobs**.
2. Automation halts immediately. No data loss — Sheets A/B/D still accept
   3PL entries; they just don't flow to Sheet C until resumed.
3. Notify Sam via Chat.
4. Do NOT delete anything in Sheets A/B/C/D. Once the issue is fixed,
   resume the jobs and `pollAll` catches up on all unprocessed rows.

---

## Source-of-truth links

- Sheet A (3MD): https://docs.google.com/spreadsheets/d/1dambmiLzSMWOQun7MCymK4nHpuqrarFCAOK0G9-6oIU/edit
- Sheet B (Pinnacle): https://docs.google.com/spreadsheets/d/10fqnvF_uDl5ky3MkvXUmWvZ1fYat_p6XFGmVFc3vqrw/edit
- Sheet C (BEI master): https://docs.google.com/spreadsheets/d/1_Ir5O5AW7hOjcvCTXsP06cF3sai9hcefDFrBOTRHOh0/edit
- Sheet D (Shaw transitional): https://docs.google.com/spreadsheets/d/1mbJiLW9M9e-AmrXSRRTtbRP-xKI16ah5rakOt6qv2As/edit
- Supplier SI Upload Form: https://docs.google.com/forms/d/1gyijOzmjXJHlyil7wraQ8xjmPMu0q1eoqUcjwHXogPg/edit
- Apps Script editor: https://script.google.com/d/1lsvOlv1rGEvXl_1zms4SURlsLUZk7CxRhg2NyBDrDHh4fDjuioFZhi2S/edit
- Cloud Scheduler console: https://console.cloud.google.com/cloudscheduler?project=quiet-walker-475722-s2

---

_Version 2026-04-21._
