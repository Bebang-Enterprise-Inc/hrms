# S256 Defects

## D1 — HO Opening Balance one-shot header detection (MINOR)

**Status:** DEFERRED (non-blocking; fix in v3.10.1 hotfix)

**Description:** `seedHoOpeningBalanceOnce_` failed with "Cannot find header row in opening balance file" because the `05 - AP Opening Balance Head Office` sheet's "Detailed HEAD OFFICE" tab has a merged banner title in row 1 ("Head Office/Project/Commi/Stores Monitoring") and the actual column headers (PAYEE, AMOUNT, etc.) are on a later row. The function scans first 25 rows for "PAYEE" or "SOURCE" but the sheet's layout doesn't match.

**Impact:** NONE on ongoing sync. The one-shot function was designed to run once and then no-op (via `_ho_opening_loaded` flag tab). Since the existing HO data is already in AP Master from prior FPM/Denise seeds, the opening balance import is supplementary. The hourly cycle continues normally without it.

**Fix plan:** Update `seedHoOpeningBalanceOnce_` to scan for a broader set of header keywords (AMOUNT, INVOICE, DATE) and handle multi-row headers. Push as v3.10.1 (versionNumber 18).

**Deferred to:** S257 or a quick v3.10.1 hotfix push.

---

## D2 — FPM-side bypass-supplier auto-tag deferred to S257

**Status:** DEFERRED BY DESIGN (per Phase 5.3 plan)

**Description:** `BYPASS_3PL_PATTERNS` auto-tag runs in `seedFromDenisePaymentPlan_` only. FPM-sourced bypass-supplier rows (e.g., 3M Dragon entries from FPM) do NOT get auto-tagged 'Denise PP - Manual' in `seedNewInvoicesFromFPM_`. This was explicitly deferred per Phase 5.3 because it requires discussion about whether FPM SOURCE should be overridden.

**Impact:** FPM-sourced bypass-supplier rows keep their 'FPM-SOA' SOURCE tag. The S256 Phase 5.4/5.5 backfill retagged 94 existing such rows on the HO tab, but new ones from future FPM cycles will get 'FPM-SOA' instead of 'Denise PP - Manual'.

**Deferred to:** S257 (Sam decides if FPM-side auto-tag is desired).

---

## Summary

| ID | Severity | Status | Block deploy? |
|---|---|---|---|
| D1 | MINOR | DEFERRED | NO |
| D2 | BY DESIGN | DEFERRED | NO |

**Deferred count: 2 (both non-blocking)**
