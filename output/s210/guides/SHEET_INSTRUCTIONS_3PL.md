# Source text for Sheet A `_Instructions` tab AND Sheet B `_Instructions` tab

This file is the canonical source for the instruction tab that 3MD (Sheet A)
and Pinnacle (Sheet B) editors see when they open the sheet. Use this to
push into both sheets' `_Instructions` tab.

The same content works for both sheets — only the references to "3MD" or
"Pinnacle" differ. The push script parameterises the `_3PL_NAME_`
placeholder.

---

## Canonical content (parameterised)

```
BEI _3PL_NAME_ Receiving Log 2026 — How to use (2-minute read)

Your job: log every supplier delivery that arrives at your warehouse.
No photo uploads needed. The supplier uploads their SI PDF separately
via their own form.

─── SIMPLE DELIVERY (1 item) ───

1. Click the "Receipts" tab at the bottom of this sheet.
2. Scroll to the first empty row.
3. Fill left-to-right:
   A. Timestamp (REQUIRED — type date+time of arrival; row is skipped if blank)
   B. 3PL (your warehouse: _3PL_NAME_)
   C. RR Number (your own receipt number, e.g. RR-0041)
   D. PO Number (exactly as printed on the BEI PO)
   E. Supplier (pick from dropdown — must match the PO)
   F. Material Code (pick from dropdown — must be on the PO)
   G. Material Description (auto-fills)
   H. Qty Received (actual quantity)
   I. UoM (auto-fills)
   J. SI Number (exactly as printed on supplier paper SI)
   K. Trucker's Name (optional)
   L. Plate Number (optional)
   M. Production Date (if on packaging)
   N. Expiration Date (if on packaging)
   O. Received By (your name or initials)
   P. Notes (only if issue to flag)
4. Press Enter.

Within ~1 minute the BEI system logs this delivery.

─── MULTI-ITEM DELIVERY (1 truck, 1 SI, multiple materials) ───

Type header fields on the FIRST line of the delivery only. Leave them
BLANK on subsequent lines — the system inherits them automatically.

Header fields (type once per delivery):
  RR Number, PO Number, Supplier, SI Number,
  Trucker, Plate, Received By

Per-line fields (type every row):
  Material Code, Material Description, Qty Received,
  UoM, Production Date, Expiration Date, Notes

Example — 3 materials on 1 truck:

  Row 1: RR-0041 | PO-1234 | DIMAX | FLOUR | 10 | BAG | SI-8877 | Juan
  Row 2:         |         |       | SUGAR |  5 | BAG |         |
  Row 3:         |         |       | YEAST |  2 | PC  |         |

─── WHAT NOT TO DO ───

- Don't try to type in the other tabs (Open_POs_*, Suppliers_Visible,
  Materials, _Instructions). They're locked and you can't edit them.
- Don't try to upload photos. This sheet has no photo column.
- Don't delete rows after saving. If you made a typo, add a correction
  row with a Note explaining, or contact Ian.
- Don't invent PO numbers. If the PO you expect is not in the dropdown,
  the PO may be closed or routed elsewhere — contact Ian.

─── COMMON ISSUES ───

- PO dropdown missing the PO you expect → Contact Ian.
- Supplier on paper SI doesn't match the PO supplier → STOP. Call
  procurement before logging. Do NOT submit a mismatched receipt.
- Qty exceeds PO balance → STOP. Call procurement first.
- Multiple production dates for same material → log as separate rows
  (one row per batch).

─── WHO TO CONTACT ───

- Ian Dionisio: ian@bebang.ph
- Jay Sumagui: jay@bebang.ph

─── VERSION ───

2026-04-21 (Phase 11 — multi-line delivery support + photo columns removed).
Supersedes all prior instructions.
```

---

## How to push this into the sheets

Use the Sheets API to write lines into `_Instructions!A:A` starting at
row 2 (row 1 stays as the "Instructions" header cell).

Pseudocode:

```python
lines = SHEET_INSTRUCTIONS_3PL_TEXT.split('\n')
# Replace _3PL_NAME_ with '3MD' for Sheet A, 'Pinnacle' for Sheet B
values_a = [[line.replace('_3PL_NAME_', '3MD')] for line in lines]
values_b = [[line.replace('_3PL_NAME_', 'Pinnacle')] for line in lines]

sheets.spreadsheets().values().update(
    spreadsheetId=SHEET_A_ID,
    range="'_Instructions'!A2:A" + str(len(lines) + 1),
    valueInputOption='RAW',
    body={'values': values_a},
).execute()
# Same for Sheet B
```

The push is a one-shot operation per release. A Python script
`output/s210/push_instructions_tab.py` handles it.
