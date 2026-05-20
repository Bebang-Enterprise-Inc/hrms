# S255 Phase 2 — FPM Intercompany Routing Checklist

**Completed:** 2026-05-20 PHT

| Task | Status | Evidence | Notes |
|---|---|---|---|
| 2.1 Create Intercompany tab (19 cols, strict-locked) | DONE | sheetId=1519913072; protectedRange "S255 — Intercompany tab strict-lock (sam@ only)" | 19-col SOA-like schema, header row at row 17, banner row 1 placeholder |
| 2.2 Tight predicate in v3.9 FPM seed | DONE | 3 regex literals confirmed in v3.9 source | PAYEE + transfer-keyword AND NOT govt-keyword |
| 2.3 One-time migration HO → Intercompany | DONE | `output/s255/intercompany_routing_log.json` — 331 migrated, 25 ambiguous | Far exceeded plan's "30+" target — 331 is the true count of intercompany rows |
| 2.4 Banner unchanged for Intercompany | DONE | (script-level — no change needed in v3.9; recomputeBanners_ in Phase 3 will skip Intercompany) | |
| **2.5 v3.9 existingIndex + status sync + FPM seed routing extended** (Phase 2.5 amendment for zero-defect) | DONE | v3.9 line 290 + 428 both have 4-tab forEach; line 1144 has 4-key newRowsByTab; FPM routing has isIntercompany block | **Amendment:** plan v1.1 specified line 428; for zero-defect also patched line 290 (status sync) + line 1144 (FPM seed routing) — same architectural concern |
| 2.6 Smoke test (dryRun=1) | DEFERRED → 9b.3 | (smoke test runs against staging deployment in Phase 9b.3) | Plan v1.1 ordering issue: 2.6 expects dryRun against v3.9 but deploy happens in 9b — defer to dry-run gate |

## v3.9 source changes (this phase)

| Line | Before | After |
|---|---|---|
| 290 | `['Suppliers SOA', 'Head Office', 'CAPEX'].forEach(tabName => {` | `['Suppliers SOA', 'Head Office', 'CAPEX', 'Intercompany'].forEach(tabName => {` |
| 428 | `['Suppliers SOA', 'Head Office', 'CAPEX'].forEach(tabName => {` | `['Suppliers SOA', 'Head Office', 'CAPEX', 'Intercompany'].forEach(tabName => {` |
| 1144 | `{ 'Suppliers SOA': [], 'Head Office': [], 'CAPEX': [] }` | `{ 'Suppliers SOA': [], 'Head Office': [], 'CAPEX': [], 'Intercompany': [] }` |
| 1100 stats init | `capex_count: 0, ho_count: 0, soa_count: 0,` | `capex_count: 0, ho_count: 0, soa_count: 0, intercompany_count: 0,` |
| ~1189 FPM routing | (only CAPEX/SOA/HO classification) | New `isIntercompany` block with 3-regex predicate BEFORE CAPEX check; `targetTab='Intercompany'` branch added |

v3.9 source: 86,445 bytes (was 85,734) — net +711 bytes from Intercompany block.

## Migration insights

- **331 rows migrated** to Intercompany (mostly "Cash Sweep" Bebang Enterprise rows from FPM)
- **25 ambiguous rows** stay on HO:
  - ~18 govt-remittance rows (HDMF/SSS/PHIC/PHILHEALTH Contributions) correctly excluded by govt-keyword negative filter
  - ~5 rental / OJT allowance rows (PAYEE matches Bebang but particulars are payroll/rental, not transfer)
  - ~2 "Transfer to BPI" / "Transfer of Fund" variants where phrasing didn't match the strict regex (legitimate intercompany missed by predicate — flagged for human review in S256 if Sam wants to migrate)

## Defect flagged (non-blocking)

**D1 — Predicate phrasing gap:** 2-3 ambiguous rows look like legitimate intercompany transfers but use phrasing the regex doesn't match (e.g. "RFP 1801 Fund Transfer From UB - Snack House to BEI"; "Trasnfer of Fund from UB Snackhousr"; "Transfer to BPI BEI to facilitate check clearing adjustment"). These stay on HO. Sam can review `intercompany_ambiguous.json` and optionally amend the regex in S256.

Phase 2 → DONE. Proceeding to Phase 3 (banner refresh).
