# Bridge Due-Diligence Readiness Checklist

**Audit date:** 2026-05-20 PHT (S255 Phase 9a)
**Bridge engaged:** ~2026-05-14 (fractional CFO + DD auditor)

## Bridge access across ecosystem (audit results)

| Sheet | Bridge access | Notes |
|---|---|---|
| BEI AP Master | ✗ no Bridge access | Sam to decide if needed for DD |
| FPM | ✓ 5 writer(s) (anna.r, kim.c, flor.a, accountant.outsource, erica.d) | DD-ready |
| Compliance AppSheet | ✗ no Bridge access | Sam to decide if needed for DD |
| PCM | ✗ no Bridge access | Sam to decide if needed for DD |
| BGF | ✗ no Bridge access | Sam to decide if needed for DD |
| Bank Balances LIVE | ✗ no Bridge access | Sam to decide if needed for DD |
| Cashflow Tracker - CEO | ✗ no Bridge access | Sam to decide if needed for DD |
| Project: 2-Week Payment Plan (Denise) | ✓ 3 writer(s) (anna.r, flor.a, bea.p) | DD-ready |


## DD-package contents (what Bridge needs)

| # | Artifact | Source | Bridge access | Action |
|---|---|---|---|---|
| 1 | AP outstanding by payee + aging | AP Master Suppliers SOA + Head Office + CAPEX + Intercompany | ✗ grant access | Sam grants Bridge reader on AP Master |
| 2 | Payment plan (next 2 weeks) | AP Master Payment Plan tab OR Denise PP sheet | ✓ via Denise PP (3 Bridge users writer) | none — Bridge already has access |
| 3 | RFP processing pipeline | FPM (RFP Summary tab) | ✓ | none |
| 4 | Supplier compliance (TIN, VAT, EWT) | Compliance AppSheet | ✗ | Sam grants Bridge reader on Compliance |
| 5 | Bank balances + reconciliation | Bank Balances LIVE | ✗ | Sam grants Bridge reader on Bank Balances |
| 6 | Cashflow forecast | Cashflow Tracker - CEO | ✗ | Sam grants Bridge reader on Cashflow |
| 7 | Petty cash + per-store ops | PCM | ✗ | Sam grants Bridge reader on PCM (if DD needs it) |
| 8 | Manual-entry AP (3M Dragon etc) | AP Master Suppliers SOA — filter `SOURCE='Denise PP - Manual'` (forward-looking; 6 Masterlist 3M Dragon rows can be re-tagged if Sam wants) | ✓ via AP Master access | none (or 1-time re-tag) |

## Audit trail Bridge can pull

- `_sync_log_v3` tab on AP Master — every script action, timestamped
- `_sync_log` tab — legacy operations (pre-v3)
- Git history of `scripts/google_apps/s248_ap_view_hourly_sync_*.gs` (v3.6 → v3.9)
- `output/s255/*` — full S255 phase logs (this sprint's actions)
- `output/s248/*` if exists — S248 Phase 5-6 setup
- Plan files in `docs/plans/` — design intent

## Sam-approved-or-not for Bridge access expansion (S256+)

The 3 Bridge users currently in Denise PP are sufficient for DD on the AP side. Whether to grant Bridge access to FPM/Compliance/Bank/Cashflow is Sam's call:
- FPM: contains supplier financial data — Bridge would need this for DD
- Compliance: VAT/EWT codes — BIR-compliance audit
- Bank Balances: real-time bank positions — DD financial health
- Cashflow Tracker: forward forecast — DD valuation

Recommended: grant Bridge READER access on FPM + Compliance + Bank Balances; defer Cashflow + PCM.
