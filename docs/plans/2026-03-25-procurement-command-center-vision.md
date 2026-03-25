# Procurement Command Center Vision

**The Goal:** Luwi spends 80% of her time SOURCING (finding better suppliers, negotiating prices, building relationships) and 20% on processing. Right now it's flipped — she's drowning in data entry.

**Design philosophy:** Think Amazon "Buy Again" meets Shopify bulk operations meets a Bloomberg terminal for procurement.

---

## The Core Insight: Luwi's Job Has Two Modes

### Mode 1: Processing (low-value, repetitive, should be minimized)
- Creating POs for items she already knows she needs
- Recording GRs for deliveries she expected
- Typing invoice numbers from paper documents
- Creating payment requests for verified invoices
- Chasing ORs from suppliers

### Mode 2: Sourcing (high-value, strategic, should be maximized)
- Finding better prices for raw materials
- Evaluating new suppliers
- Negotiating payment terms
- Monitoring market price trends
- Managing supplier relationships and compliance

**Every feature should be evaluated by:** "Does this move time from Mode 1 to Mode 2?"

---

## Angle 1: E-Commerce Reorder Patterns

### "Buy Again" — Recurring PO Templates

**Inspiration:** Amazon's "Buy Again" button shows your purchase history and lets you reorder with one click.

**For Luwi:**
```
┌─────────────────────────────────────────────────────────────┐
│  REORDER CENTER                                    [+ New]  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  📋 Weekly Commissary Restock          Last: Mar 18         │
│     12 items · Orangepop + GLARA + UBE House                │
│     Avg total: P145,200                                     │
│     [Reorder Now]  [Edit Qty]  [View History]               │
│                                                             │
│  📋 Monthly Office Supplies            Last: Feb 28         │
│     8 items · National Bookstore                            │
│     Avg total: P12,400                                      │
│     [Reorder Now]  [Edit Qty]  [View History]               │
│                                                             │
│  📋 Sago Emergency Restock             Last: Mar 22         │
│     1 item · 3 suppliers rotated                            │
│     Avg total: P84,000                                      │
│     [Reorder Now]  [Edit Qty]  [View History]               │
│                                                             │
│  🔥 HOT ITEMS (ordered 5+ times this month)                 │
│     FG009 Sago · 14 POs · P1.2M total · Avg P84/kg         │
│     RM001 Rice · 8 POs · P890K total · Avg P195/kg          │
│     FG050 Cooked Sago · 6 POs · P340K                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**How "Reorder Now" works:**
1. System pre-fills a new PO with the same supplier, same items, same last-negotiated prices
2. Luwi adjusts quantities (maybe she needs 20% more sago this week)
3. One click → PO created and sent for approval
4. **Time saved:** 5-minute form fill → 30-second qty adjustment

**Smart reorder suggestions:**
- "You ordered Sago 3 weeks ago. Based on commissary consumption rate, you'll run out in 4 days. [Reorder Now]"
- "Rice price dropped 8% from your last PO supplier. [See cheaper options]"

---

## Angle 2: The Procurement Command Center (Bloomberg Terminal Style)

### Replace the Dashboard with an Ops Center

**Current dashboard:** Static KPI cards that show totals. Useful for executives, not for operators.

**What Luwi needs:** A command center that shows her what requires ACTION right now.

```
┌──────────────────────────────────────────────────────────────────────┐
│  PROCUREMENT COMMAND CENTER                     Wed, Mar 25 · Luwi  │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  🔴 URGENT (do now)                                          [4]     │
│  ├─ 3 deliveries arriving today (GLARA 10am, UBE House 2pm,         │
│  │   Orangepop 3pm) — GRs not yet created                           │
│  ├─ 1 invoice overdue for processing (INV from National, 5 days)    │
│  └─ [Process All →]                                                  │
│                                                                      │
│  🟡 NEEDS ATTENTION (today)                                  [12]    │
│  ├─ 8 PRs from stores waiting to become POs                         │
│  ├─ 2 suppliers with missing documents (tax compliance)              │
│  ├─ 1 PO delivery is 3 days late (Jovylyn, expected Mar 22)         │
│  ├─ 1 OR overdue 81 days (PAY-2026-00050, P250K)                   │
│  └─ [View Details →]                                                 │
│                                                                      │
│  🟢 WAITING ON OTHERS                                        [45]    │
│  ├─ 41 POs pending Mae's approval                                   │
│  │   └─ Oldest: 12 days (PO-2026-02801, P890K) ⚠️                  │
│  ├─ 3 payments pending Butch's approval                              │
│  ├─ 1 payment pending CEO approval (new supplier)                    │
│  └─ [Nudge Approver →]                                               │
│                                                                      │
│  ✅ COMPLETED TODAY                                           [7]     │
│  ├─ 4 GRs recorded                                                  │
│  ├─ 2 invoices processed                                            │
│  ├─ 1 payment request submitted                                      │
│                                                                      │
├──────────────────────────────────────────────────────────────────────┤
│  📊 LIVE PULSE                                                       │
│                                                                      │
│  Outstanding AP    │  This Month POs  │  Avg Approval    │  On-Time  │
│  ₱5,106,566       │  96 (₱37.5M)     │  Wait: 3.2 days  │  Rate: 0% │
│  🔴 98% overdue    │  ▲ 12% vs Feb    │  ⚠️ Target: 1d   │  🔴 Fix!  │
│                                                                      │
│  ┌─ OVERDUE PAYMENTS (color = severity) ──────────────────────────┐  │
│  │ ████████████████████  90+ days: ₱3.2M (4 suppliers)           │  │
│  │ ██████████           60-90 days: ₱1.1M (6 suppliers)          │  │
│  │ ████                 30-60 days: ₱0.5M (8 suppliers)          │  │
│  │ ██                   Current: ₱0.3M (12 suppliers)            │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

**Key differences from current dashboard:**
- **Action-oriented, not metric-oriented** — "3 deliveries today" not "1,026 total GRs"
- **Color-coded urgency** — red/yellow/green, not flat gray cards
- **Counts that matter to Luwi** — "8 PRs to convert" not "499 total PRs"
- **Waiting-on-others visibility** — Luwi can see who's blocking her
- **"Nudge Approver" button** — one click sends a reminder to Mae
- **Completed today** — sense of progress and accomplishment

---

## Angle 3: Bulk Operations (Gmail/Shopify Style)

### Every List Page Gets Bulk Actions

**Current:** Click PO → view → approve → back → click next PO → view → approve → back...

**New pattern:** Select multiple → bulk action

```
┌──────────────────────────────────────────────────────────────────────┐
│  PURCHASE ORDERS                          [☑ Select All] [New PO ▾] │
├──────────────────────────────────────────────────────────────────────┤
│  ☐  Bulk Actions: [Approve Selected] [Send to Suppliers] [Export]   │
├──────────────────────────────────────────────────────────────────────┤
│  ☑  PO-2026-02985  GLARA Foods       ₱2,784,096   Pending Mae  3d  │
│  ☑  PO-2026-02981  Orangepop         ₱246,400     Pending Mae  2d  │
│  ☑  PO-2026-02979  1 To 1 Marketing  ₱1,120       Pending Mae  1d  │
│  ☐  PO-2026-02975  National Book     ₱12,400      Pending Mae  1d  │
│  ☐  PO-2026-02970  UBE House         ₱44,604      Approved     ✓   │
│                                                                      │
│  ──── Selected: 3 POs · Total: ₱3,031,616 ─────────────────────── │
│  [✓ Approve All 3]  [📧 Send All 3 to Suppliers]  [Cancel]          │
└──────────────────────────────────────────────────────────────────────┘
```

**Bulk actions per page:**

| Page | Bulk Actions |
|------|-------------|
| **PRs** | Convert selected to POs, Approve selected, Reject selected |
| **POs** | Approve selected, Send selected to suppliers, Export selected as PDF |
| **GRs** | Accept selected, Flag selected for inspection |
| **Invoices** | Submit selected for verification, Mark selected as matched |
| **Payments** | Submit selected for approval, Export selected for bank upload |
| **Suppliers** | Request documents from selected, Flag selected for review |
| **OR Follow-up** | Send reminders to selected, Escalate selected |

**For Mae specifically:** "Approve All 41" button that shows a summary, then one confirmation click.

---

## Angle 4: Color-Coded Visibility (Heatmap Style)

### Status = Color Everywhere

Every piece of data should have instant visual meaning.

**PO Status Colors:**
```
🔴 Red      = Overdue / Blocked / Rejected
🟠 Orange   = Late delivery / Approaching deadline
🟡 Yellow   = Pending approval / Needs attention
🟢 Green    = On track / Approved / Completed
🔵 Blue     = Sent to supplier / In transit
⚪ Gray     = Draft / Not started
```

**Supplier Health Score (visible on every supplier mention):**
```
GLARA Foods         ●●●●○  4/5  On-time: 85%  Avg delay: 1.2d
Orangepop           ●●●○○  3/5  On-time: 60%  Avg delay: 4.5d  ⚠️
UBE House           ●●○○○  2/5  On-time: 30%  Avg delay: 8.1d  🔴
National Bookstore  ●●●●●  5/5  On-time: 98%  Avg delay: 0.2d
```

**Inventory-Linked PO Urgency:**
```
┌─ ITEMS RUNNING LOW (linked to inventory) ────────────────────────┐
│                                                                    │
│  🔴 FG009 Sago     Stock: 45 kg   Need: 200 kg/week   2.2 days   │
│     Last PO: Mar 18 (P84/kg from GLARA)                           │
│     [Reorder Now →]                                                │
│                                                                    │
│  🟠 RM001 Rice     Stock: 120 kg  Need: 300 kg/week   2.8 days   │
│     Last PO: Mar 20 (P195/kg from National)                        │
│     Price alert: Orangepop offers P188/kg (-3.6%)                  │
│     [Reorder →]  [Compare Prices →]                                │
│                                                                    │
│  🟡 FG050 Cooked   Stock: 80 kg   Need: 150 kg/week   3.7 days   │
│     [Reorder →]                                                    │
│                                                                    │
│  🟢 All other items: 7+ days stock                                 │
└────────────────────────────────────────────────────────────────────┘
```

**This is the ultimate sourcing tool:** Luwi doesn't just process POs — she sees what's running low, what the current prices are, and whether a cheaper supplier exists. THAT'S sourcing.

---

## Angle 5: Keyboard Shortcuts & Speed (Superhuman Style)

### For Power Users Processing 100+ Items/Day

```
GLOBAL SHORTCUTS:
  N P    → New PO (from anywhere)
  N R    → New PR
  N G    → New GR
  N I    → New Invoice
  /      → Search everything (POs, suppliers, items, invoices)
  ?      → Show all shortcuts

LIST PAGE SHORTCUTS:
  J/K    → Navigate up/down in list
  X      → Select/deselect row
  A      → Approve selected
  E      → Edit selected
  Enter  → Open detail
  Esc    → Back to list

FORM SHORTCUTS:
  Ctrl+Enter → Submit form
  Ctrl+S     → Save as draft
  Tab        → Next field (already works)
```

**Quick Search (like Spotlight/Alfred):**
```
Press / anywhere:

┌──────────────────────────────────────────────┐
│  🔍 GLARA                                    │
├──────────────────────────────────────────────┤
│  📦 GLARA Foods (Supplier) — 45 POs, ₱12M   │
│  📄 PO-2026-02985 — GLARA, ₱2.8M, Pending   │
│  📄 PO-2026-02710 — GLARA, ₱246K, Received  │
│  🧾 INV-2026-00042 — GLARA, ₱672K, Verified │
│  📋 GR-2026-02956 — GLARA, Mar 20           │
└──────────────────────────────────────────────┘
```

---

## Angle 6: Smart Automation (Reduce Clicks to Zero Where Possible)

### Things That Should Happen Automatically

| Trigger | Auto-Action | Current State |
|---------|-------------|---------------|
| PO fully approved | Email PDF to supplier | ✅ Works |
| Supplier delivers + Luwi records GR | Auto-create draft invoice from GR data | ❌ Manual |
| Invoice matches PO+GR perfectly (zero variance) | Auto-verify | ❌ Manual verification required |
| Invoice verified + supplier has payment terms | Auto-create payment request at due date | ❌ Manual |
| OR overdue 7/14/30 days | Auto-escalate notification | ✅ Works |
| Item stock falls below reorder point | Auto-create PR | ❌ Manual |
| PR approved + single-source supplier | Auto-create PO | ❌ Manual |
| Contracted price changes | Alert Luwi + auto-update templates | ❌ Manual |

**The "Zero-Touch PO" flow:**
```
Stock drops below reorder → Auto PR created
→ PR auto-approved (routine restock, established supplier)
→ PO auto-created from template (same supplier, same items)
→ Mae batch-approves 20 routine POs in one click
→ PO auto-emailed to supplier
→ Supplier delivers → Luwi records GR in 30 seconds (qty matches = one click "Received as Ordered")
→ Invoice auto-created from GR
→ 3-way match auto-verified (zero variance)
→ Payment request auto-created at supplier's Net 30 due date
→ Butch batch-approves payments weekly
```

**Luwi's involvement in this flow: 30 seconds** (the GR recording).
**Current involvement: 20-30 minutes** (PR + PO + GR + Invoice + Payment, each a separate form).

---

## Angle 7: Supplier Relationship Intelligence

### Turn Data Into Sourcing Power

**Supplier Scorecard (visible on supplier detail):**
```
┌─ GLARA FOODS · Supplier Scorecard ─────────────────────────────┐
│                                                                  │
│  RELIABILITY        ●●●●○  4.2/5                                │
│  ├─ On-time rate:    85% (34/40 deliveries)                     │
│  ├─ Avg delay:       1.2 days                                   │
│  ├─ Quality issues:  2 (both resolved)                          │
│  └─ OR compliance:   90% (9/10 ORs received)                    │
│                                                                  │
│  FINANCIAL           ₱12,450,000 total (12 months)              │
│  ├─ Avg PO size:     ₱276,667                                   │
│  ├─ Payment terms:   Net 30                                      │
│  ├─ EWT rate:        2%                                          │
│  ├─ VAT:             VAT Registered                              │
│  └─ Outstanding:     ₱890,000 (3 invoices)                      │
│                                                                  │
│  PRICE TREND (last 6 months)                                     │
│  ├─ FG009 Sago:  ₱84 → ₱84 → ₱88 → ₱84  (stable)             │
│  ├─ M003 Hantien: ₱2,200 → ₱2,200 → ₱2,350  (↑ 6.8%)  ⚠️    │
│  └─ [View All Items →]  [Compare with Other Suppliers →]         │
│                                                                  │
│  DOCUMENTS           ⚠️ 1 missing                               │
│  ├─ BIR 2307:       ✅ Valid until Dec 2026                      │
│  ├─ Business Permit: ✅ Valid until Dec 2026                     │
│  ├─ SEC Registration: ❌ Missing — [Request →]                   │
│  └─ DTI Certificate:  ✅ Valid                                    │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

**Price Comparison Tool:**
```
┌─ PRICE COMPARISON: FG009 Sago ──────────────────────────────────┐
│                                                                   │
│  Supplier              Last Price   Avg Price   Trend    Score    │
│  GLARA Foods           ₱84/kg      ₱84.50      →        ●●●●○   │
│  Orangepop             ₱82/kg      ₱83.00      ↓        ●●●○○   │
│  UBE House             ₱88/kg      ₱86.00      ↑        ●●○○○   │
│  Jovylyn Ube House     ₱80/kg      ₱81.00      →        ●●●●○   │
│                                                                   │
│  💡 Recommendation: Jovylyn offers best price (₱80/kg) with      │
│     good reliability (4/5). Save ₱4/kg vs current supplier.      │
│     Annual savings potential: ₱208,000 based on current volume.   │
│     [Create PO with Jovylyn →]                                    │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

**THIS is what turns Luwi from a data entry clerk into a strategic buyer.**

---

## Angle 8: The Delivery Dock View (Warehouse Integration)

### Real-Time Delivery Tracking

```
┌─ TODAY'S DELIVERIES · Wed Mar 25 ────────────────────────────────┐
│                                                                    │
│  🕐 10:00 AM  GLARA Foods                                         │
│     PO-2026-02985 · 12 items · ₱2.8M                              │
│     Status: 🟢 Confirmed by supplier                               │
│     [Record GR →]                                                  │
│                                                                    │
│  🕑 2:00 PM   UBE House                                           │
│     PO-2026-02970 · 3 items · ₱44K                                │
│     Status: 🟡 No supplier confirmation                            │
│     [Call Supplier]  [Record GR →]                                 │
│                                                                    │
│  🕒 3:00 PM   Orangepop Enterprise                                │
│     PO-2026-02738 · 1 item · ₱246K                                │
│     Status: 🔴 Was expected Mar 22 — 3 DAYS LATE                  │
│     [Send Follow-up →]  [Record GR →]                              │
│                                                                    │
│  ─── LATER THIS WEEK ──────────────────────────────────────────── │
│  Thu Mar 26: National Bookstore (PO-2026-02975, ₱12K)             │
│  Fri Mar 27: Jovylyn (PO-2026-02960, ₱180K)                      │
│                                                                    │
│  ─── OVERDUE ──────────────────────────────────────────────────── │
│  🔴 Orangepop PO-2026-02738 — 3 days late · Last contact: Mar 23 │
│  🔴 SM Supplier PO-2026-02699 — 8 days late · No contact ⚠️      │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

---

## Angle 9: Quick GR — "Received as Ordered"

### The One-Click GR for Complete Deliveries

Most deliveries match the PO exactly. Why fill every qty field?

```
┌─ QUICK RECEIVE: PO-2026-02985 (GLARA Foods) ─────────────────────┐
│                                                                     │
│  All items match PO quantities?                                     │
│                                                                     │
│  ☑ FG009 Sago         200 kg   ₱84/kg    ₱16,800                  │
│  ☑ M003 Hantien       100 box  ₱2,200    ₱220,000                 │
│  ☑ RM005 Sugar        50 kg    ₱65/kg    ₱3,250                   │
│  ... (12 items total)                                               │
│                                                                     │
│  📎 Delivery note: [Upload photo 📷]                                │
│                                                                     │
│  [✓ Received All as Ordered]     [Partial/Variance →]               │
│                                                                     │
│  "Received All as Ordered" = creates GR with all qty matching PO.   │
│  Use "Partial/Variance" only if something is different.             │
└─────────────────────────────────────────────────────────────────────┘
```

**Time saved per GR: 3 minutes → 10 seconds** (for matching deliveries)

---

## Angle 10: The Weekly Procurement Rhythm

### Structured Workflow for Predictable Operations

```
MONDAY MORNING ROUTINE (automated):
├─ System sends Luwi a morning digest:
│   "This week: 8 deliveries expected, 12 PRs to process,
│    3 invoices to verify, Mae has 41 POs in her queue."
├─ Luwi opens Command Center → sees red/yellow/green
├─ Batch-converts 12 PRs → 8 POs (using templates)
├─ Mae batch-approves 20 POs before lunch
└─ Auto-send 20 POs to suppliers

DAILY ROUTINE:
├─ Check delivery calendar → prep for today's arrivals
├─ Record GRs as deliveries come in (Quick Receive)
├─ Process invoices (auto-created from GRs)
├─ System auto-verifies matching invoices
└─ Check reorder alerts → create POs for low-stock items

FRIDAY AFTERNOON:
├─ Butch batch-approves weekly payments
├─ System processes all approved payments
├─ Auto-generate EWT journal entries
├─ Luwi reviews OR follow-ups
└─ Weekly procurement report auto-generated
```

---

## Implementation Priority Matrix

### Tier 1: "10x Luwi's Speed" (build first)

| Feature | Impact | Effort | Description |
|---------|--------|--------|-------------|
| **Command Center** | Massive | 15 units | Replace static dashboard with action-oriented ops center |
| **Bulk Approve for Mae** | Massive | 8 units | Select all → Approve — unblocks 41 POs immediately |
| **Quick Receive (1-click GR)** | High | 6 units | "Received as Ordered" button on matching deliveries |
| **Reorder Center / Templates** | High | 12 units | Save recurring POs, one-click reorder with qty edit |

### Tier 2: "Smart Automation" (build second)

| Feature | Impact | Effort | Description |
|---------|--------|--------|-------------|
| **Auto-create Invoice from GR** | High | 10 units | When GR is recorded, draft invoice pre-filled |
| **Auto-verify zero-variance invoices** | High | 5 units | If PO=GR=Invoice, skip manual verification |
| **Delivery Calendar** | Medium | 8 units | Weekly view of expected deliveries from PO dates |
| **Morning Digest (Chat/email)** | Medium | 5 units | Daily summary of what needs attention |

### Tier 3: "Strategic Sourcing Tools" (build third)

| Feature | Impact | Effort | Description |
|---------|--------|--------|-------------|
| **Price Comparison Tool** | High | 12 units | Compare item prices across suppliers with recommendation |
| **Supplier Scorecard** | Medium | 8 units | Reliability rating, price trend, compliance status |
| **Low Stock Alerts linked to POs** | High | 10 units | Connect inventory levels → auto-PR → auto-PO chain |
| **Keyboard Shortcuts** | Medium | 5 units | Superhuman-style speed for power users |

### Tier 4: "Full Automation" (build when ready)

| Feature | Impact | Effort | Description |
|---------|--------|--------|-------------|
| **Zero-Touch PO flow** | Massive | 25 units | Stock drop → auto PR → auto PO → auto email |
| **Invoice OCR** | High | 20 units | Scan → auto-extract fields |
| **Mobile GR at dock** | Medium | 15 units | Phone/tablet receiving with camera |
| **Auto payment at due date** | Medium | 10 units | Verified invoice → auto payment request at Net 30 |

---

## The Vision: Luwi's Day in 6 Months

```
8:00 AM — Luwi logs in. Command Center shows:
          🔴 2 urgent (late delivery, overdue invoice)
          🟡 5 needs attention (3 reorder alerts, 2 PR conversions)
          🟢 12 deliveries on track this week

8:05 AM — Clicks "Process Reorder Alerts" → system creates 3 POs
          from templates. Adjusts sago qty from 200 to 250 kg.
          Total time: 2 minutes (vs 15 minutes today)

8:10 AM — Mae opens her phone, sees "5 POs for approval" notification.
          Opens batch approval view. Reviews totals. Approves all 5.
          Total time: 1 minute (vs 10 minutes today)

8:15 AM — System auto-emails 5 PO PDFs to suppliers.
          Luwi doesn't touch anything.

10:00 AM — GLARA delivers. Warehouse scans delivery note with phone.
           All items match PO. Clicks "Received as Ordered."
           System auto-creates GR + draft Invoice.
           Total time: 30 seconds (vs 8 minutes today)

10:05 AM — Luwi attaches scanned invoice. 3-way match = zero variance.
           System auto-verifies. Payment request auto-queued for Friday.
           Total time: 1 minute (vs 10 minutes today)

2:00 PM — Luwi opens Price Comparison for sago. Sees Jovylyn offers
          P80/kg vs GLARA's P84/kg. Annual savings: P208K.
          Calls Jovylyn to negotiate a contract.
          THIS IS SOURCING. This is what Luwi should be doing.

4:00 PM — Reviews supplier scorecards. UBE House dropped to 2/5
          reliability (30% on-time). Flags for discussion with Mae.
          Starts looking for alternative ube suppliers.
          THIS IS STRATEGIC. Not data entry.

TOTAL PROCESSING TIME: ~30 minutes (vs 4+ hours today)
SOURCING TIME GAINED: 3.5+ hours/day
```

---

## Questions for Brainstorm

1. **Which Tier 1 feature is most urgent?** Command Center, Bulk Approve, Quick Receive, or Reorder Templates?

2. **How much automation is Mae comfortable with?** Would she accept auto-approve for routine POs under P50K with established suppliers?

3. **Does Luwi currently use Excel for any procurement tracking?** If so, what does the spreadsheet track that the system doesn't?

4. **What's the actual daily transaction volume?** POs/GRs/invoices per day — need real numbers to validate priority.

5. **Is supplier negotiation part of Luwi's job?** Or does Mae handle all supplier relationships? This determines how important the sourcing tools are for Luwi specifically.

6. **Would Cayla use the same features?** Or does she have a different role within procurement?

7. **Is there a procurement target?** E.g., "reduce cost per PO by 10%" or "process all invoices within 24 hours" — goals help prioritize features.

8. **Which suppliers deliver without notice?** This affects whether the delivery calendar is useful or if most deliveries are unscheduled.
