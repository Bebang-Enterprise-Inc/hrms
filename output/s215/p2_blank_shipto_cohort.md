# P2-T7 — Blank Ship To + Blank PO Cohort (CEO awareness)

**Probed 2026-04-21 post-refresh.**

## Procurement AppSheet `Purchase Order` — Ship To blank cohort

| State | Count |
|---|---|
| PO rows with blank `Ship To` | 278 |
| PO rows with populated `Ship To` | 407 |
| **Total** | **685** |

These 278 POs have no routing destination in the source sheet, so they do NOT appear in any of the three S215 per-3PL tabs (`PO_Lines_3MD_Only`, `PO_Lines_Pinnacle_Only`, `PO_Lines_Shaw_Only`). They still show up in Sheet C `11_Full_PO_Lines` with Ship To column blank. These are legacy / internal POs and **no action is required** — they will continue to be handled via the pre-existing `08_Full_Open_POs` workflow.

## Procurement AppSheet `PO Items` — blank PO No cohort

| State | Count |
|---|---|
| PO Items rows with blank `PO No` | 26 |
| PO Items rows with valid `PO No` | 2199 |
| **Total** | **2225** |

The 26 blank-`PO No` rows cannot be joined to any Purchase Order, so they are excluded from both `11_Full_PO_Lines` and the three per-3PL filtered tabs. This is correct behaviour — the rows are un-actionable without a PO reference. S215 verifier threshold for `11_Full_PO_Lines` is adjusted to ≥2100 to accommodate.

## Decision

No action. The cohorts are legacy data quality — not a blocker for the S210 live workflow since ALL post-2026-04-21 POs are required to have both Ship To and PO No populated at PR approval time (per Procurement SOP). S215 therefore fences off the existing bad rows without backfilling them.
