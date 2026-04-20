# S210 Onboarding — 3PL Receiving Sheets (3MD + Pinnacle)

**Audience:** Ian Dionisio, Jay Sumagui, Cayla — the internal team who handles
all communication with 3MD and Pinnacle. Names of external contacts are
deliberately out of this document; the team decides who at the 3PL gets
editor access and how to message them.

**Objective:** Enable each 3PL warehouse to log every supplier delivery
directly into its dedicated Google Sheet so BEI can generate DRs + draft
RFPs automatically. Supplier SI upload is a separate parallel stream (§5).

---

## 0. Automation state — already live (Phase 8 Cloud Scheduler)

No manual click required. All cron + polling runs on **Google Cloud
Scheduler** hitting an Apps Script web app. Four jobs in `asia-southeast1`,
Asia/Manila cron:

| Job | Cron | What it does |
|---|---|---|
| `s210-poll-all` | `*/1 * * * *` | Polls Sheets A/B/D Receipts + Supplier SI Upload form; writes to Sheet C consolidated + Pending GR / Variance Queue |
| `s210-age-variance-hourly` | `0 * * * *` | Moves DRs >72h without SI match into Variance Queue |
| `s210-refresh-masters-06` | `0 6 * * *` | Pulls Procurement AppSheet -> Sheet C suppliers + open POs masters |
| `s210-ceo-email-07` | `0 7 * * *` | Sends KPI digest email to sam+ian |

GCP Console: `quiet-walker-475722-s2` -> Cloud Scheduler -> `asia-southeast1`.
Status is visible there; jobs auto-retry on failure with exponential backoff.

---

## 1. Sheets deployed

| Role | Sheet | ID | External editor |
|---|---|---|---|
| 3MD | BEI 3MD Receiving Log 2026 | `1dambmiLzSMWOQun7MCymK4nHpuqrarFCAOK0G9-6oIU` | 3MD contact (Ian to invite) |
| Pinnacle | BEI Pinnacle Receiving Log 2026 | `10fqnvF_uDl5ky3MkvXUmWvZ1fYat_p6XFGmVFc3vqrw` | Pinnacle contact (Jay to invite) |
| BEI master | BEI Receiving Master 2026 | `1_Ir5O5AW7hOjcvCTXsP06cF3sai9hcefDFrBOTRHOh0` | NONE - BEI-only |
| Shaw transitional | BEI Shaw Transitional Receiving | `1mbJiLW9M9e-AmrXSRRTtbRP-xKI16ah5rakOt6qv2As` | NONE - BEI-only |

Access isolation: the 3MD editor cannot see Pinnacle data and vice versa.
Sheet C is internal BEI only.

---

## 2. How the 3PL submits a delivery

One row per delivery, typed into the **Receipts** tab of their own sheet.

**Data is a running log - rows persist forever.** The 3PL sees every
historical delivery they've ever logged (their audit trail). BEI keeps a
parallel copy in Sheet C `02_All_Receipts_Consolidated`.

Every minute, Cloud Scheduler's `s210-poll-all` job reads rows NEWER than
the last-processed timestamp for that sheet (tracked in Apps Script
Properties per-sheet). Each row is processed **exactly once**.

### Columns the 3PL fills (16 total, no photos)

```
Timestamp | 3PL | RR Number | PO Number | Supplier | Material Code |
Material Description | Qty Received | UoM | SI Number | Trucker's Name |
Plate Number | Production Date | Expiration Date | Received By | Notes
```

### Edit behaviour gotchas

| Action | Effect |
|---|---|
| Add a new row | Processed within <=60s by the scheduler |
| Delete an already-processed row | No effect on BEI - Sheet C keeps its copy |
| Edit an already-processed row (fix typo) | Will NOT be re-processed (timestamp unchanged). Workaround: delete the row and retype it |
| Add the same delivery twice by accident | Both rows processed as separate receipts; SCM gets 2 Chat posts; variance-queue logic will flag if no matching supplier SI arrives |

### Sheet rotation (years 2, 3, ...)

Sheets A and B hold all deliveries for 2026. When they become unwieldy we
cut `BEI 3MD Receiving Log 2027` etc. and re-invite the 3PL editor. No
row-level archiving; year-over-year rotation only.

---

## 3. Inviting 3PL editors (team-led)

### 3MD (Ian owns)

1. Confirm the 3MD point-of-contact's Google account email internally.
2. Open Sheet A -> Share -> add their email -> **Editor**.
3. Protected ranges on `Open_POs_3MD_Only`, `Suppliers_Visible`,
   `Materials`, `_Instructions` keep them out of tabs they shouldn't edit.
4. Send them a short message with:
   - The sheet link
   - Instructions to open the `Receipts` tab
   - "Add one row per delivery. Type the SI Number exactly from the paper
     SI. No photo uploads needed - the supplier uploads the PDF via a
     separate form."
   - Ian as the contact if any PO is missing.

### Pinnacle (Jay owns)

Pinnacle is currently on the `Pinnacle x Bebang PH` Viber group (15 people).
Migration path:

1. Jay asks via Viber for one contact email to onboard as editor.
2. Share Sheet B -> Editor on that email.
3. Same messaging template as 3MD.
4. Until migration completes, Pinnacle continues on Viber and Ian manually
   logs rows into Sheet B on their behalf (short-term bridge).

Keep external names out of documentation; store them in the team's own
contact list. This doc stays generic.

---

## 4. End-to-end pipeline

```
Supplier delivers goods to 3MD or Pinnacle
   |
   v
3PL logs row in Sheet A/B Receipts tab
   |
   v  (within 60 sec, Cloud Scheduler s210-poll-all fires)
Apps Script web app (/exec?fn=pollAll):
   - Reads rows newer than last-seen-ts (per-sheet timestamp in Script Props)
   - Validates each against 08_Full_Open_POs (PO exists, supplier matches, qty<=balance)
   - Writes to Sheet C 02_All_Receipts_Consolidated (always)
   - Valid   -> writes to Sheet C 06_Pending_GR (for Ashish AppSheet pickup)
              + posts Chat notification (SCM + Procurement Notifications)
   - Invalid -> writes to Sheet C 05_Variance_Queue for Ian resolution
   - Every outcome logged to Sheet C 09_Audit_Log
   |
   v
Ashish's Procurement AppSheet polls 06_Pending_GR (separate sprint)
   - Creates Frappe GR + RFP draft
   - RFP routes Luwi -> Mae -> (CEO if > P1M)
   - Payment schedules for: DR date + Supplier.Payment_Terms
```

SI is a separate compliance stream - payment does NOT wait for it:

```
Supplier uploads SI via Google Form (per-supplier pre-filled URL)
   |
   v  (within 60 sec, Cloud Scheduler s210-poll-all polls FormApp.getResponses)
handleSiUpload:
   - Writes to Sheet C 03_Supplier_SI_Uploads
   - Attempts match against 02_All_Receipts_Consolidated by (PO#, SI#)
   - MATCH  -> tags DR with SI_Matched=TRUE + Drive link + timestamp
   - ORPHAN -> writes to 04_Match_Queue for manual resolution
```

---

## 5. Supplier SI Upload form - rollout (Cayla owns)

- **Form ID:** `1gyijOzmjXJHlyil7wraQ8xjmPMu0q1eoqUcjwHXogPg`
- **Public responder URL:**
  https://docs.google.com/forms/d/e/1FAIpQLSc3UC9f_3gefDYNgpOqNx7UCw_5BDrRh9T8-GQeyHHWSxdITw/viewform
- **Pre-filled per-supplier URLs:** `output/s210/SUPPLIER_URLS.csv`
  (98 rows; columns: supplier_code, supplier_name, tin, email, tier,
  prefill_url, qr_url)
- **Form fields:** Supplier Name (pre-filled), PO Number, SI Number, SI Date,
  Amount (PHP), **Upload SI Copy** (native file upload, PDF or image, max 10MB),
  Notes

Rollout plan:

1. Email each supplier their dedicated `prefill_url` - URL auto-fills
   Supplier Name so they don't mistype it.
2. Template: "For every delivery you make to BEI or our 3PL warehouses,
   upload your SI PDF here: [prefill_url]. Tap Upload SI Copy, pick the
   file from your phone or computer, submit. This is the fastest path to
   payment - we process DR-based draft RFPs within the hour and release
   payment on your contracted net terms (15/30/45/60). The SI copy speeds
   compliance but doesn't gate payment."
3. Monitor 04_Match_Queue for orphan uploads - Ian reviews daily until
   suppliers settle into the pattern.

---

## 6. Daily ops for Ian and Cayla

1. Open Sheet C 01_Dashboard. Verify:
   - Today's receipts aligned with what 3PLs reported
   - SI match rate > 60% (below: chase Top 10 Tier A suppliers who
     haven't uploaded)
   - Pending GR depth < 20 (above: Ashish AppSheet may be stuck)
   - Variance Queue depth < 10 (above: triage)
2. Open Sheet C 04_Match_Queue. Assign orphan SI uploads to the right DR
   or dismiss if a supplier submitted by mistake.
3. Open Sheet C 05_Variance_Queue. Resolve stale DRs (usually by
   contacting the 3PL for the missing SI number).
4. The daily 07:00 PHT CEO digest email is automatic. Use it as a
   standing reference.

---

## 7. When something breaks

| Symptom | Likely cause | Action |
|---|---|---|
| No rows flowing from Sheet A/B into Sheet C | Cloud Scheduler job `s210-poll-all` paused/errored | GCP Console -> Scheduler -> Run job manually; check logs under resource.type=cloud_scheduler_job |
| Chat notifications not posting | Service-account Chat app not a member of the target space | Ian invites the BEI chat bot into both `spaces/AAQArCi8zjE` (SCM) and `spaces/AAQAYAYwPPk` (Procurement Notifications) |
| Dashboard formulas show 0 even with receipts | Timestamp format mismatch on new 3PL entries | Open Dashboard row 3 formula, adjust TEXT() format if needed |
| Supplier SI form errors on upload | File >10MB OR disallowed type | Ask supplier to compress or re-scan as PDF |
| refreshMasters not firing at 06:00 | Scheduler job `s210-refresh-masters-06` disabled | GCP Console -> re-enable + run manually |
| CEO daily email missing | GmailApp quota OR web-app execution limit | Check Apps Script executions log |

---

## 8. Emergency rollback

If automation misbehaves:

1. GCP Console -> Cloud Scheduler -> pause all 4 `s210-*` jobs.
2. Automation halts immediately. No data loss - Sheets A/B/D still accept
   3PL entries; they simply don't propagate to Sheet C until resumed.
3. Notify Sam, file [BUG] in the sprint registry, do NOT delete sheet data.
4. Resume jobs once root cause is resolved - `s210-poll-all` will catch up
   on all unprocessed rows (it uses `last_processed_<sheetId>` timestamps,
   not job state).

---

## 9. Source of truth

- Sprint plan: `docs/plans/2026-04-20-sprint-210-tier-a-receipt-payment-infrastructure.md`
- Apps Script canonical source: `scripts/google_apps/s210_master_handler.gs`
- Apps Script project ID: `1lsvOlv1rGEvXl_1zms4SURlsLUZk7CxRhg2NyBDrDHh4fDjuioFZhi2S`
- Web-app deployment (Cloud Scheduler target):
  `https://script.google.com/macros/s/AKfycbwHhE8wesatwrXdw8SYOFjm30zqG62wNgFUyC_GIB14zFQb1CHU4ov-jVm1wjGfqFj2/exec`
- Cloud Scheduler state: `output/s210/CLOUD_SCHEDULER.json`
- Sheet + form IDs: `output/s210/SHEET_IDS.json`
- Run state: `output/s210/RUN_STATUS.json`

---

_Last updated: 2026-04-20 PM (Phase 8 Cloud Scheduler migration + external
names removed - team handles all 3PL communication)._
