# Phase 1 Checklist — INVESTIGATION GATE

| Task | Status | Evidence | Skipped? |
|---|---|---|---|
| 1.1 Locate Procurement App | DONE | 13 candidates found; Compliance AppSheet Database selected (23 tabs, active as of 2026-05-25) | NO |
| 1.2 Read tab structures | DONE | "Purchase Order" (994 rows, 49 cols), "Goods Receipts" (1458 rows), "Suppliers" (1000 rows) identified | NO |
| 1.3 Locate 05-AP Opening Balance HO | DONE | Known ID `1jSwZRyIPisU4jiKS-Tn9VFoLukQI8UNoW13Hoov-75Y` — "Detailed HEAD OFFICE" tab, 2560 rows, 35 cols | NO |
| 1.4 Locate CAPEX File | DONE | "BGF, INVESTMENTS and CAPEX" (`1dfIyAeGH_5ga_mjA1o-WWN9xM6VO3v7XKKoU1Jtq1eI`) — Angela's sheet | NO |
| 1.5 DECISION GATE | **PROCEED = TRUE** | Both Procurement App and HO Opening Balance found with substantial data | NO |
| 1.6 verify_phase1.py | DONE | Exit 0 | NO |

## Gate Decision

**PROCEED WITH SOURCE REDESIGN** — Phases 4a/4b/4c will execute in this sprint.

## Key IDs for Phase 4

| Source | ID | Tab | Rows |
|---|---|---|---|
| Procurement App (Compliance AppSheet) | `1QWdoZlT7XWLppfVKpJ2VRXhbMkYtE5TbUwg4lMbO03Q` | TBD at Phase 4a (likely "Purchase Order" 49 cols) | ~994+ |
| 05-AP Opening Balance HO | `1jSwZRyIPisU4jiKS-Tn9VFoLukQI8UNoW13Hoov-75Y` | "Detailed HEAD OFFICE" | 2560 |
| CAPEX File (BGF, INVESTMENTS) | `1dfIyAeGH_5ga_mjA1o-WWN9xM6VO3v7XKKoU1Jtq1eI` | TBD | TBD |
