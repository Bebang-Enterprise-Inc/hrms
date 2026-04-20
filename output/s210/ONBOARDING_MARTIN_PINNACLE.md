# S210 Onboarding — Martin (3MD) & Pinnacle (via Jay)

**Audience:** Ian Dionisio, Jay Sumagui — internal coordinators who will share
this with Martin Axel Pistan (3MD) and with the Pinnacle Bebang contact.

**Objective:** Enable the 3PL warehouses to log each supplier delivery directly
into their dedicated Google Sheet so BEI can generate DRs + draft RFPs
automatically. Supplier SI upload is a separate parallel stream (see §5).

---

## 0. One-time setup — DO THIS FIRST (CEO / commissary.team only)

**Until this step is done, no onEdit automation will fire.** The 7 installable
triggers are defined but not yet installed.

1. Open the Apps Script editor: https://script.google.com/d/1lsvOlv1rGEvXl_1zms4SURlsLUZk7CxRhg2NyBDrDHh4fDjuioFZhi2S/edit
2. In the left file panel, click **s210_master_handler.gs**.
3. In the function dropdown at the top of the editor, select **setup**.
4. Click **Run**.
5. First run triggers an OAuth consent screen — approve. Scopes requested:
   - View/edit Google Sheets
   - Send mail as yourself
   - Access Google Drive (for SI uploads)
   - Manage triggers
   - Make external HTTP requests (for Chat notifications)
6. After `setup complete: 7 triggers installed` appears in the execution log,
   open any of the 4 sheets, add a test row to Receipts, and confirm within
   30 seconds that a row appears in Sheet C `02_All_Receipts_Consolidated`
   and a Chat post lands in the SCM space.
7. If setup() finishes without errors but no Chat post appears, the service
   account Chat app may need to be invited to both `spaces/AAQArCi8zjE` (SCM)
   and `spaces/AAQAYAYwPPk` (Procurement App Notifications). Ian to verify.

---

## 1. Sheets deployed

| Role | Sheet | ID | Owner | External editor |
|---|---|---|---|---|
| 3MD | BEI 3MD Receiving Log 2026 | `1dambmiLzSMWOQun7MCymK4nHpuqrarFCAOK0G9-6oIU` | commissary.team | **Martin Pistan** (pending Ian) |
| Pinnacle | BEI Pinnacle Receiving Log 2026 | `10fqnvF_uDl5ky3MkvXUmWvZ1fYat_p6XFGmVFc3vqrw` | commissary.team | **Pinnacle contact** (pending Jay) |
| BEI master | BEI Receiving Master 2026 | `1_Ir5O5AW7hOjcvCTXsP06cF3sai9hcefDFrBOTRHOh0` | commissary.team | NONE (BEI-only) |
| Shaw transitional | BEI Shaw Transitional Receiving | `1mbJiLW9M9e-AmrXSRRTtbRP-xKI16ah5rakOt6qv2As` | commissary.team | NONE (BEI-only) |

Access isolation is the whole point — Martin never sees Pinnacle data, and
vice versa. Sheet C is internal BEI only.

---

## 2. What Ian sends to Martin (3MD)

1. Copy the link: `https://docs.google.com/spreadsheets/d/1dambmiLzSMWOQun7MCymK4nHpuqrarFCAOK0G9-6oIU/edit`
2. Send to Martin (`martin.axel.pistan@3mdlogistics.com` or confirmed channel)
   with this message template:

> Hi Martin,
>
> Starting today, please log each supplier delivery to your warehouse into
> the sheet below. This replaces the daily email + paper SI forwarding we
> previously did.
>
> Link: https://docs.google.com/spreadsheets/d/1dambmiLzSMWOQun7MCymK4nHpuqrarFCAOK0G9-6oIU/edit
>
> Open the **Receipts** tab. Add one row per delivery. Dropdown fields will
> only show suppliers + POs routed to 3MD — if the PO you expect is missing,
> message me (ian@bebang.ph).
>
> Upload a photo of the supplier SI in the "SI Photo" column (phone → Insert
> Image → Upload). Photo must be clear enough to read the SI number and total.
>
> For anything not routed to your warehouse, ignore. You will not be able to
> see other warehouses' data.

3. Add Martin as editor with access restricted to the Receipts tab.
   - Open the sheet → Share → add martin's email → set role to **Editor**.
   - The protected ranges on Open_POs_3MD_Only, Suppliers_Visible, Materials,
     _Instructions prevent edits to those tabs.

---

## 3. What Jay sends to Pinnacle

Pinnacle is currently only reachable via the Viber group
`Pinnacle x Bebang PH` (15 participants). Migration path:

1. Jay asks Pinnacle on Viber for one contact email for a Google account we
   can invite as an editor.
2. Once email received, Jay shares the Pinnacle sheet:
   `https://docs.google.com/spreadsheets/d/10fqnvF_uDl5ky3MkvXUmWvZ1fYat_p6XFGmVFc3vqrw/edit`
   and invites that email as editor.
3. Jay sends the same template as §2 (substituting "Pinnacle" for "3MD" and
   pointing to the Open_POs_Pinnacle_Only tab for reference).
4. Until the migration completes, Pinnacle continues sending via Viber + Ian
   manually logs rows into the sheet on Pinnacle's behalf (short-term bridge).

---

## 4. How the pipeline works end-to-end

```
Supplier delivers goods to 3MD or Pinnacle
   │
   ▼
3PL logs row in Sheet A (3MD) or Sheet B (Pinnacle) Receipts tab
   │
   ▼  (within 30 sec, onEdit installable trigger fires)
Apps Script:
   • Reads the new row
   • Validates against 08_Full_Open_POs (PO exists, supplier matches, qty ≤ balance)
   • Writes to Sheet C 02_All_Receipts_Consolidated  (always)
   • Valid   → writes to Sheet C 06_Pending_GR (for Ashish AppSheet pickup)
              + posts Chat notification (SCM + Procurement Notifications)
   • Invalid → writes to Sheet C 05_Variance_Queue for Ian resolution
   • Every outcome logged to Sheet C 09_Audit_Log
   │
   ▼
Ashish's Procurement AppSheet polls 06_Pending_GR (separate sprint)
   • Creates Frappe GR + RFP draft
   • RFP routes Luwi → Mae → (CEO if > ₱1M)
   • Payment schedules for: DR date + Supplier.Payment_Terms
```

No payment waits for SI copy — SI is the parallel compliance stream:

```
Supplier uploads SI via Google Form (per-supplier pre-filled URL)
   │
   ▼  (onFormSubmit trigger)
handleSiUpload:
   • Writes to Sheet C 03_Supplier_SI_Uploads
   • Attempts match against 02_All_Receipts_Consolidated by (PO#, SI#)
   • MATCH   → tags DR with SI_Matched=TRUE + Drive link + timestamp
   • ORPHAN  → writes to 04_Match_Queue for manual resolution
```

---

## 5. Supplier SI Upload form — rollout checklist

- **Form:** https://docs.google.com/forms/d/1DsT-IdDpW_p3XfpSevkyCZ7S-YVu3EWEK3SxD1lJ940/edit
- **Public responder URL:** https://docs.google.com/forms/d/e/1FAIpQLSdsifYasH8h8_iBGkbsZyhssSmRQX-zXzvxeNVSfwhA2yPvTw/viewform
- **Pre-filled per-supplier URLs:** 98 rows in `output/s210/SUPPLIER_URLS.csv`
  (supplier_code, supplier_name, tin, email, tier, prefill_url, qr_url)

Rollout plan (Cayla owns):

1. Email each supplier their dedicated `prefill_url` from
   `output/s210/SUPPLIER_URLS.csv` — the URL auto-fills their Supplier Name so
   they don't mistype it.
2. Template: "For every delivery you make to BEI or our 3PL warehouses, upload
   your SI PDF here: [prefill_url]. This is the fastest path to payment — we
   process DR-based draft RFPs within the hour and release payment on your
   contracted net terms (15/30/45/60). The SI copy speeds compliance but
   doesn't gate payment."
3. Suppliers who can't scan to PDF: give them the same URL, they upload a
   JPEG from phone to Drive first, share the link, paste in the form. Document
   in the form's description.
4. Monitor 04_Match_Queue for orphan uploads — Ian reviews daily until
   suppliers settle into the pattern.

---

## 6. What Ian and Cayla do each morning

1. Open Sheet C 01_Dashboard — verify:
   - Today's receipts aligned with what 3PLs reported
   - SI match rate > 60% (below 60%: chase Top 10 Tier A suppliers who haven't uploaded)
   - Pending GR depth < 20 (above 20: Ashish AppSheet may be stuck)
   - Variance Queue depth < 10 (above 10: triage)
2. Open Sheet C 04_Match_Queue — assign orphan SI uploads to the right DR or
   dismiss if supplier submitted by mistake.
3. Open Sheet C 05_Variance_Queue — resolve stale DRs (usually by contacting
   the 3PL for the missing SI number or photo).
4. The daily 07:00 CEO digest email lands in Sam and Ian's inboxes with the
   same KPI snapshot — use it as a standing reference.

---

## 7. When something breaks

| Symptom | Likely cause | Action |
|---|---|---|
| No rows flowing from Sheet A/B into Sheet C | setup() not run OR onEdit trigger disabled | Re-run setup() in editor |
| Chat notifications not posting | Service account Chat app not a member of the target space | Ian invites `bei-erp-chat-bot@...` to both spaces |
| Dashboard formulas show 0 even with receipts | Timestamp format mismatch (Sheet A uses local time, formulas use TEXT) | Open Dashboard row 3 formula, adjust TEXT() format if needed |
| SI upload form errors "file_upload not supported" | Suppliers trying UI file upload — we use text link field | Point them to the form description: upload PDF to Drive first |
| refreshMasters didn't run at 06:00 | Script API quota exceeded OR Apps Script outage | Manual run from editor: select refreshMasters → Run |
| CEO daily email missing | GmailApp scope not granted during setup() OAuth consent | Re-run setup(), grant all scopes when prompted |

---

## 8. Emergency rollback

If the automation causes issues:

1. Open editor → select `setup` → replace with:
   ```
   function setup() {
     const existing = ScriptApp.getProjectTriggers();
     for (const t of existing) ScriptApp.deleteTrigger(t);
   }
   ```
2. Run it — all triggers removed, automation halted.
3. BEI reverts to the prior manual paper-SI-forwarding process temporarily.
4. Notify Sam, file [BUG] in the sprint registry, do NOT delete sheet data.

---

## 9. Source of truth

- Sprint plan: `docs/plans/2026-04-20-sprint-210-tier-a-receipt-payment-infrastructure.md`
- Apps Script canonical source: `scripts/google_apps/s210_master_handler.gs`
- Run state: `output/s210/RUN_STATUS.json`
- Deployed resources inventory: `output/s210/SHEET_IDS.json`

---

_Last updated: 2026-04-20 (sprint S210 Phase 6 closeout)_
