# S242 Phase 5.2 — Paseo 2026-04-21 POS XLSX vs Supabase post-migration

**Generated:** 2026-05-09 14:50 PHT (post-migration verification)
**Pre-migration baseline:** `output/s232/paseo_comparison_report.md` (2026-05-08)

## Side-by-side

| Metric | POS XLSX | Supabase (pre-S242) | Supabase (post-S242) | Δ |
|---|---:|---:|---:|---:|
| Order count | 176 | 175 | 176 | +1 ✓ |
| Sum gross (XLSX "Gross" col) | ₱121,722.00 | ₱121,494.00 | ₱121,722.00 | **0.00** ✓ |
| Sum net | ₱105,601.94 | ₱105,398.37 | ₱105,601.94 | **0.00** ✓ |
| Bill 39966 — POS Pickup row | ₱228 visible | ₱228 hidden (is_duplicate=true) | ₱228 visible (is_duplicate=false) | recovered ✓ |
| Bill 39966 — FoodPanda row | ₱704 visible | ₱704 visible | ₱704 visible | unchanged ✓ |

## Bill 39966 detail (post-migration)

```
| id       | channel   | gross  | is_duplicate |
|----------|-----------|--------|--------------|
| 51234223 | FoodPanda | 704.00 | false        |
| 51234586 | POS       | 228.00 | false        |  ← restored by S242 migration
```

Both rows now LIVE in `v_pos_orders_live` and contributing to dashboard totals.

## Verdict

**Supabase: ₱121,722 ↔ POS XLSX: ₱121,722 — MATCH TO THE CENTAVO**

The +₱228 delta (175 → 176 visible orders) corresponds exactly to the
restored Pickup terminal row of bill 39966. No other movement.

## Column-mapping note (per S232 paseo_comparison_report.md)

POS XLSX "Gross" column maps to Supabase `original_gross_sales` (pre-discount).
The Dashboard MV's `pos_gross_sales` tracks `gross_sales` (post-discount,
₱118,027.03) — both views are consistent with the XLSX after the column
mapping is applied.

## Source files

- POS XLSX: `data/Paseo - Sales Checking POS.xlsx`
  (referenced in `output/s232/paseo_comparison_report.md`)
- S232 baseline: `output/s232/paseo_comparison_report.md` (preserved intact;
  shows pre-migration state with the bill 39966 case)
- Post-migration row dump: `output/s242/verification/paseo_4_21_bill_39966_after.json`
- Post-migration dashboard view: `output/s242/verification/paseo_4_21_dashboard_after.json`
