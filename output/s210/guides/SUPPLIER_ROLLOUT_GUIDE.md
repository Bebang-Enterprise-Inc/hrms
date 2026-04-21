# Supplier SI Upload — Rollout Playbook

**Owner:** Cayla
**Audience:** Cayla + any backup on the procurement/supplier-relations side
**Goal:** Onboard all 98 BEI suppliers to the new Supplier SI Upload form so
they stop sending paper SIs through the 3PL warehouses.

---

## 0. What you have

- `output/s210/SUPPLIER_URLS.csv` — 98 rows. Columns:
  `supplier_code, supplier_name, tin, email, tier, prefill_url, qr_url`
- The form itself:
  https://docs.google.com/forms/d/e/1FAIpQLSc3UC9f_3gefDYNgpOqNx7UCw_5BDrRh9T8-GQeyHHWSxdITw/viewform
- `output/s210/guides/SUPPLIER_FAQ.md` — attach to every rollout email

---

## 1. Rollout waves (recommended cadence)

Don't email all 98 at once. Phase in waves to handle confusion at pace.

### Wave 1 — Top 10 Tier A by volume (week 1)

The 10 suppliers we pay the most. They have the most incentive to adopt.
Identify them by pulling top 10 PO totals from Procurement AppSheet:

```
Sort Sheet C 08_Full_Open_POs by Total Amount desc, take top 10 distinct suppliers.
```

Email individually with their pre-filled URL. Watch for 48 hours — confirm
each sends at least one test SI. Call any who don't respond.

### Wave 2 — Rest of Tier A (week 2)

Remaining Tier A suppliers (likely 50-70 more). Batch email — same
template. Expect 60-70% response rate.

### Wave 3 — Tier B/C (week 3-4)

Lower-volume suppliers. Can batch. Follow-up once after 1 week.

### Wave 4 — Stragglers (week 5+)

Anyone who hasn't uploaded a single SI. Direct call.

---

## 2. Email template (per supplier)

Subject: `BEI Supplier SI Upload — fastest path to payment`

```
Hi [Supplier Contact Name],

BEI has moved to a new process that will get your invoices paid faster.
Starting now, for every delivery you make to BEI or our 3PL warehouses
(3MD, Pinnacle), please upload your Sales Invoice at the link below
right after delivery.

Your dedicated upload link (pre-fills your company name):
[SUPPLIER_PREFILL_URL]

What to do:
1. Tap the link
2. Fill PO Number, SI Number, SI Date, Amount
3. Tap "Upload SI Copy" — pick your PDF or photo from your phone
4. Submit

That's it. Our system matches your upload to the warehouse's delivery
record automatically, and payment queues for release on your contracted
terms (e.g. Net 30 from delivery date).

Keep sending the paper SI to us as you do today — that's separate and
unchanged. The upload is what speeds up your payment.

Attached FAQ answers common questions. Contact me if anything is unclear.

Thanks,
Cayla
cayla@bebang.ph

[ATTACH: SUPPLIER_FAQ.md or print-to-PDF equivalent]
```

---

## 3. QR codes for physical deliveries

Some truckers / supplier reps prefer scanning a QR at the dock instead of
fishing for a link. Each supplier's URL has a QR in
`SUPPLIER_URLS.csv:qr_url`.

### Print per-supplier QR sticker

1. Open `SUPPLIER_URLS.csv`
2. Filter to a specific supplier
3. Paste the `qr_url` into a browser → renders a 300×300 QR image
4. Right-click → Save image → print at postcard size (4×6") on a sticker
   sheet
5. Bundle the sticker with the supplier's onboarding email or hand to the
   trucker directly

### Bulk print

If you want a binder of all 98 QR codes for dock use:

```
Use a Google Sheets QR-rendering add-on (e.g. "QR Codes for Sheets") on
SUPPLIER_URLS — column H formula: =IMAGE("https://api.qrserver.com/v1/
create-qr-code/?size=200x200&data="&ENCODEURL(F2))
```

Then print-to-PDF, 2-up, color printer.

---

## 4. Tracking adoption — weekly check

Every Monday morning, open Sheet C 01_Dashboard. Check the KPI
"SI match rate (today's receipts)". Target > 60% by end of week 2,
> 80% by end of week 4.

For suppliers NOT yet uploading, cross-reference:
- `02_All_Receipts_Consolidated` rows where `SI_Matched = FALSE`
- Group by Supplier
- Call the top 5 non-adopters each week

---

## 5. Handling common resistance

| Objection | Response |
|---|---|
| "I don't have a scanner" | Phone photo is fine. The form accepts JPG/PNG. |
| "Our accounts staff don't use Gmail" | Form is public — works with any email. No Google account needed. |
| "Can I still send paper SI?" | Yes, keep doing that. Upload is in addition, not instead. |
| "My PO number is long / has dashes" | Copy-paste from the PO exactly as printed. The form accepts any string. |
| "What if I make a typo after submitting?" | Upload again — the form allows repeat submissions. Mark the bad one in Notes. |
| "I'm worried about my PDF being seen by others" | Only BEI staff have access. Not public, not indexed. |

---

## 6. Escalation

- Tier A supplier who refuses → Cayla → Ian (procurement context) → Sam
- Form/technical issue → Sam (sprint owner)
- Supplier reporting we're not paying after upload → Luwi (Accounts Payable)

---

## 7. After rollout — steady state

- **New supplier onboarding:** as part of supplier onboarding, Cayla adds
  their email to the Sheet C `07_Full_Suppliers_Master` tab so their
  pre-filled URL is generated on the next `s210-refresh-masters-06` daily
  run. Manually send the URL in the welcome email.
- **Changed supplier contact:** update `Email ID` in the Procurement
  AppSheet Suppliers tab — it flows into Sheet C on next daily refresh.
  Re-send pre-filled URL to the new email.
- **Retired supplier:** mark as Tier C or disable in Procurement AppSheet.
  They'll be excluded from `SUPPLIER_URLS.csv` on next regeneration.

---

_Version 2026-04-21._
