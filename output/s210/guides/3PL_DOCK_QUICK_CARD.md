# BEI Receiving Quick Card — 3MD / Pinnacle dock staff

Print this on a single page. Laminate. Keep near the receiving area.

---

## What this sheet is for

Every time a supplier delivers goods to this warehouse, log **one row per
item** in the `Receipts` tab.

No photos needed. The supplier uploads the SI PDF separately through their
own form. Your job is the delivery record only.

---

## How to log a delivery (≤30 seconds for a single-item drop)

1. Open the Google Sheet you were invited to as editor.
2. Click the **Receipts** tab at the bottom.
3. Scroll to the first empty row.
4. Fill these 16 columns left to right:

| # | Column | What to type |
|---|---|---|
| A | Timestamp | Now (auto-fills if you leave blank) |
| B | 3PL | Your warehouse name (3MD or Pinnacle) |
| C | RR Number | Your own receipt number (e.g. `RR-0041`) |
| D | PO Number | Exactly as printed on the BEI PO (e.g. `PO-2026-1234`) |
| E | Supplier | Pick from dropdown — must match the PO |
| F | Material Code | Pick from dropdown — must be on the PO |
| G | Material Description | Auto-fills from code |
| H | Qty Received | Actual quantity that arrived |
| I | UoM | Auto-fills from master |
| J | SI Number | Exactly as printed on supplier's paper SI |
| K | Trucker's Name | Optional but recommended |
| L | Plate Number | Optional but recommended |
| M | Production Date | If printed on packaging |
| N | Expiration Date | If printed on packaging |
| O | Received By | Your name or initials |
| P | Notes | Only if there's an issue worth flagging |

5. Press Enter to save. Done.

Within ~1 minute BEI's system picks up the row and processes it.

---

## Multi-item delivery (1 PO, 1 SI, multiple materials)

Type the **header fields** (RR Number, PO Number, Supplier, SI Number,
Trucker, Plate, Received By) on the **first line** of the delivery only.
Leave them blank on the second, third, etc. The system auto-fills them
from your first line.

**Example — 1 truck, 3 items:**

| RR# | PO# | Supplier | Material | Qty | UoM | SI# | Trucker |
|---|---|---|---|---|---|---|---|
| RR-0041 | PO-2026-1234 | DIMAX | FLOUR-25KG | 10 | BAG | SI-8877 | Juan |
| _(blank)_ | _(blank)_ | _(blank)_ | SUGAR-50KG | 5 | BAG | _(blank)_ | _(blank)_ |
| _(blank)_ | _(blank)_ | _(blank)_ | YEAST-1KG | 2 | PC | _(blank)_ | _(blank)_ |

**Never leave blank:** Material Code, Qty, UoM, Production Date, Expiration
Date. Those must be typed for every row.

---

## What NOT to do

- ❌ Don't type in the locked tabs (`Open_POs_*`, `Suppliers_Visible`,
  `Materials`, `_Instructions`) — you cannot edit them anyway.
- ❌ Don't try to upload SI photos. This sheet has no photo column.
- ❌ Don't delete rows after you've saved them. If you made a typo, add a
  correction row with a Note explaining, or contact Ian.
- ❌ Don't invent PO numbers. If the PO you expect is not in the dropdown,
  contact Ian — the PO may be closed or routed to a different warehouse.
- ❌ Don't mix deliveries. Each delivery gets its own block of rows
  (header + lines), separated by a new header row for the next drop.

---

## Common issues and what to do

| Problem | Action |
|---|---|
| PO dropdown doesn't show my PO | Contact Ian — PO may not be routed here |
| Supplier on paper SI doesn't match PO | **Stop.** Call procurement. Do NOT submit a mismatched receipt. |
| Qty delivered exceeds PO balance | **Stop.** Call procurement first. |
| Multiple production dates for same material | Log as separate rows — one row per batch |
| Cold chain item arriving without temp log | Log normally; add `"cold chain broken — no temp log"` in Notes |

---

## Contacts (BEI team)

- **Ian Dionisio** (primary): `ian@bebang.ph`
- **Jay Sumagui** (backup): `jay@bebang.ph`

---

_Version 2026-04-21. Supersedes all prior dock instructions. Keep this
card with the receiving terminal — this is a living document and may be
reissued; check with Ian for the latest version._
