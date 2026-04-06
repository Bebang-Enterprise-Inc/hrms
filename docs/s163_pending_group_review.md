# S163 — 3 Product Groups Pending SCM Review

**Context:** S163 Phase 4.4 seeded 6 of the 9 groups identified in the S161 product group audit (`output/s161_product_group_audit.txt`). These 3 were deliberately skipped because they contain mixed UOMs. Using `conversion_to_display = 1.0` for mixed UOMs would silently break aggregated stock math (e.g., 1 BOX of 120 thermal bags would be counted as 1 piece).

SCM needs to confirm member conversion factors before these groups are seeded.

---

## GRP-BANANA-CINNAMON

From audit: 3 SKUs sharing "Banana Cinnamon" name.

| Item Code | Item Name | Stock UOM | Notes |
|---|---|---|---|
| FG002 | BANANA CINNAMON | KG | Finished Goods |
| FG002-A | BANANA CINNAMON | KG | Finished Goods (variant) |
| MN004 | BANANA CINNAMON | CUP | Finished Goods |

**Questions for SCM:**
- Display UOM — KG or CUP?
- If KG display: what is the CUP → KG conversion? (a single halo-halo serving weighs roughly how much?)
- Priority order for auto-resolution — FG002 first, or FG002-A first?
- Delivery lane — Frozen?

---

## GRP-FROZEN-ICE-MILK

From audit: 3 SKUs.

| Item Code | Item Name | Stock UOM |
|---|---|---|
| FG020 | FROZEN ICE MILK | BARREL |
| FG020-GRIFFITH | FROZEN ICE MILK (GRIFFITH POWDER) | KG |
| FG020-ORIGINAL | FROZEN ICE MILK (TRADITIONAL) | KG |

**Questions for SCM:**
- Display UOM — KG or BARREL?
- Are GRIFFITH and ORIGINAL variants of the same thing, or genuinely different products that should NOT be aggregated under one order line?
- If KG: how many KG per BARREL?
- Priority order?

---

## GRP-THERMAL

From audit: 2 SKUs.

| Item Code | Item Name | Stock UOM |
|---|---|---|
| PM006 | THERMAL BAG | PIECE |
| PM006-1 | THERMAL BAG (120) | BOX |

**Questions for SCM:**
- "(120)" in the name suggests 120 pieces per BOX — is that correct, or is the box size different?
- Display UOM — PIECE or BOX?
- Priority order?

---

## How to seed the remaining 3

Once SCM confirms the details, update `scripts/s163_seed_item_groups.py` with a second `GROUPS_PENDING` list and run:

```bash
python scripts/s163_run_seed.py
```

The seed script is idempotent, so the 6 already-seeded groups will be skipped on re-run.
