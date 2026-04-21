# Supplier SI Upload — Rollout Playbook

**Owner:** Cayla
**Audience:** Cayla + any backup on the procurement/supplier-relations side
**Goal:** Get all 98 BEI suppliers uploading their SIs through the form
instead of relying on 3PL warehouse paper-SI forwarding.

---

## 0. What you have

- **Single form URL for all suppliers** (no per-supplier links):
  https://docs.google.com/forms/d/e/1FAIpQLSc3UC9f_3gefDYNgpOqNx7UCw_5BDrRh9T8-GQeyHHWSxdITw/viewform
- `output/s210/guides/SUPPLIER_FAQ.docx` — attach to every rollout email

We identify the supplier automatically from the PO Number they type on
the form, so the URL doesn't need to carry company identity. Same URL for
everyone — simpler comms + no confidentiality exposure.

---

## 1. Rollout waves (recommended cadence)

Don't email all 98 at once. Phase in waves to handle confusion at pace.

### Wave 1 — Top 10 Tier A by volume (week 1)

The 10 suppliers we pay the most. They have the most incentive to adopt.
Identify them by pulling top 10 PO totals from Procurement AppSheet:

```
Sort Sheet C 08_Full_Open_POs by Total Amount desc, take top 10 distinct suppliers.
```

Email each individually. Watch for 48 hours — confirm each sends at
least one test SI. Call any who don't respond.

### Wave 2 — Rest of Tier A (week 2)

Remaining Tier A suppliers (likely 50-70 more). Batch email — same
template. Expect 60-70% response rate.

### Wave 3 — Tier B/C (week 3-4)

Lower-volume suppliers. Can batch. Follow-up once after 1 week.

### Wave 4 — Stragglers (week 5+)

Anyone who hasn't uploaded a single SI. Direct call.

---

## 2. Email template

Subject: `BEI Supplier SI Upload — fastest path to payment`

```
Hi [Supplier Contact Name],

BEI has moved to a new process that will get your invoices paid faster.
Starting now, for every delivery you make to BEI or our 3PL warehouses
(3MD, Pinnacle), please upload your Sales Invoice at the link below
right after delivery.

Upload link (bookmark this — same link for every delivery):
https://docs.google.com/forms/d/e/1FAIpQLSc3UC9f_3gefDYNgpOqNx7UCw_5BDrRh9T8-GQeyHHWSxdITw/viewform

What to do:
1. Tap the link
2. Pick which BEI warehouse you delivered to (3MD, Pinnacle, or Shaw BLVD)
3. Type the PO Number, SI Number, SI Date, Amount
4. Tap "Upload SI Copy" — pick your PDF or photo from your phone
5. Submit

That's it. Our system identifies you from the PO Number automatically,
matches your upload to the warehouse's delivery record, and queues
payment for release on your contracted terms (e.g. Net 30 from delivery).

Keep sending the paper SI to us as you do today — that's separate and
unchanged. The upload is what speeds up your payment.

Attached FAQ answers common questions. Contact me if anything is unclear.

Thanks,
Cayla
cayla@bebang.ph

[ATTACH: SUPPLIER_FAQ.docx]
```

---

## 3. QR code for the dock

Print one QR code once; the same QR works for every supplier and every
delivery. Print large on the receiving area wall so truckers can scan
with their phone while the 3PL is signing off.

Generate the QR:
```
https://api.qrserver.com/v1/create-qr-code/?size=600x600&data=https%3A//docs.google.com/forms/d/e/1FAIpQLSc3UC9f_3gefDYNgpOqNx7UCw_5BDrRh9T8-GQeyHHWSxdITw/viewform
```

Save → print A5 → laminate → post at each of 3MD, Pinnacle, and Shaw
receiving stations.

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
| "Our accounts staff don't use Gmail" | Form is public — works with any browser. No Google account needed. |
| "Can I still send paper SI?" | Yes, keep doing that. Upload is in addition, not instead. |
| "My PO number is long / has dashes" | Copy-paste from the PO exactly as printed. The form accepts any string. |
| "What if I make a typo after submitting?" | Upload again — the form allows repeat submissions. Add "Correction for PO-xxxx SI-yyyy" in Notes so we know to dismiss the bad one. |
| "I'm worried about my PDF being seen by others" | Only BEI staff have access. Not public, not indexed. |
| "How do you know it's my company uploading?" | We match the PO Number you type to your PO in our system. No company name in the form means no list of other suppliers to worry about. |

---

## 6. Escalation

- Tier A supplier who refuses → Cayla → Ian (procurement context) → Sam
- Form/technical issue → Sam (sprint owner)
- Supplier reporting we're not paying after upload → Luwi (Accounts Payable)

---

## 7. After rollout — steady state

- **New supplier onboarding:** as part of supplier onboarding, Cayla
  adds their email + contract to the Procurement AppSheet Suppliers
  tab. They get the same form URL in their welcome email. No per-
  supplier generation needed.
- **Retired supplier:** mark as Tier C or disabled in Procurement
  AppSheet. Their old POs stop matching once you close them. No URL
  housekeeping needed.

---

_Version 2026-04-21._
