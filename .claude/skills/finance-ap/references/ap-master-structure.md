# BEI AP Master Structure

The single accounts payable register. Google Sheets ID: `1bQ6mO1FXD4VYcLt8m-yklkV7pyYhSWqU7b8K0bVgG7c`.
Display name in Drive: **"AP Suppliers - Payment Status (Auto-View)"** (planned rename to "BEI AP Master" in S211 Phase 4 — confirm before assuming the new name is live).

URL: https://docs.google.com/spreadsheets/d/1bQ6mO1FXD4VYcLt8m-yklkV7pyYhSWqU7b8K0bVgG7c/edit

## 17 Tabs

### Data-entry tabs (HUMAN typed — script never overwrites)

| Tab | Rows | Cols | Who types | What |
|---|---:|---:|---|---|
| `Suppliers SOA` | 766 | 22 | Ms. Mel | Inventory supplier invoices (ingredients, packaging, cold storage, kitchen equipment) |
| `Head Office` | 5000 | 22 | Ms. Mel | Head office operating expenses (parking, rent, utilities, service providers, reimbursements) |
| `CAPEX` | 172 | 22 | Ms. Mel | Contractor / project-cost invoices (fit-outs, construction, equipment). Store dropdown REQUIRED |

### Summary tabs (SCRIPT generated — read-only for team; only Sam edits manually)

| Tab | Rows | Cols | Purpose |
|---|---:|---:|---|
| `All Liabilities` | 5000 | 19 | Every open invoice across all 3 entry tabs |
| `Needs RFP` | 5000 | 19 | Flagged `NO RFP YET` with outstanding balance — action required |
| `With Finance (No RFP)` | 5000 | 19 | Received by Finance; RFP not yet created |
| `Check Released` | 5000 | 19 | Checks signed; bank debit pending |
| `In Pipeline` | 5000 | 19 | For Review / For Approval / For Funding / Ready for Online |
| `VAT Gaps` | 5000 | 19 | Invoices > PHP 50,000 with VAT = 0 (BIR input VAT review) |
| `PAID` | 5000 | 19 | Settled invoices |

### Auxiliary summary tabs

| Tab | Rows | Cols | Purpose |
|---|---:|---:|---|
| `Summary` | 999 | 26 | Roll-up totals (top-of-stack KPI summary) |
| `Commissary` | 1000 | 26 | Commissary-only liability slice |
| `Head Office (BEI)` | 1000 | 26 | BEI-side-only HO slice (separate from BKI) |
| `Needs Attention` | 1000 | 26 | Critical action items |

### Internal/log tabs (do not edit)

| Tab | Rows | Cols | Purpose |
|---|---:|---:|---|
| `_sync_log_v3` | 1000 | 26 | Per-cell audit log of every v3 sync write |
| `_sync_log` | 1000 | 26 | Legacy v2 sync log (still written by v2 wipe-rebuild mode) |
| `_dry_run_preview` | 1000 | 26 | Preview of changes when `?dryRun=1` is hit on the web app |

## 19-Column Schema (all 3 data-entry tabs)

The data-entry tabs (`Suppliers SOA`, `Head Office`, `CAPEX`) share the same 19-column schema.
**A=1 is leftmost; positions are 1-indexed for the Sheets API.**

| Col | Letter | Header | Type | Owner | Notes |
|---:|:---:|---|---|---|---|
| 1 | A | `SOURCE` | Text | Human | Source label (free text, usually filename or "Manual") |
| 2 | B | `PAYEE` | Text | Human | Supplier / vendor name (no enforced dropdown) |
| 3 | C | `INVOICE NO.` | Text | Human | Supplier's invoice number (free text, normalized for matching) |
| 4 | D | `INVOICE DATE` | Date | Human | Original invoice issue date |
| 5 | E | `AMOUNT` | Number | Human | Gross invoice amount (VAT inclusive) |
| 6 | F | `OUTSTANDING` | Number | Human | Open balance (typically same as AMOUNT until partially/fully paid) |
| 7 | G | `AGING` | Number | **Script** | Days since invoice date — computed by script |
| 8 | H | `AGING BUCKET` | Text | **Script** | NOT YET DUE / 0-30 / 31-60 / 61-90 / 91-120 / over 120 |
| 9 | I | `STATUS` | Text | **Script** (from FPM) | Payment pipeline status (e.g. WITH FINANCE, FOR APPROVAL, CHECK RELEASED, PAID, CLEARED) |
| 10 | J | `BEI-FIN No.` | Text | Human | The BEI-internal RFP request reference (the primary join key to FPM) |
| 11 | K | `RFP No.` | Text | **Script** (from FPM) | RFP number assigned by Juanna/Denise in FPM |
| 12 | L | `METHOD` | Text | **Script** (from FPM) | Check / PESONet / GCash / etc. |
| 13 | M | `CHECK NO.` | Text | **Script** (from FPM) | Check number once issued |
| 14 | N | `CATEGORY` | Text | Human | Free-text classification (e.g. "Ingredients", "Packaging", "Utilities") |
| 15 | O | `CLASSIFICATION` | Text | Human | Secondary classification |
| 16 | P | `BILLED TO` | Text | Human | Which BEI entity is billed (BEI / BKI / Shaw / etc.) |
| 17 | Q | `VATABLE` | Number | **Script** (from Compliance) | Net VATable amount |
| 18 | R | `VAT` | Number | **Script** (from Compliance) | VAT amount |
| 19 | S | `EWT` | Number | **Script** (from Compliance) | Expanded Withholding Tax |

## Ownership Rules (encoded in script as constants)

```javascript
const HUMAN_OWNED_COLS = ['source', 'payee', 'invoice_no', 'invoice_date',
                          'amount', 'outstanding', 'category', 'classification', 'billed_to'];
const SCRIPT_OWNED_COLS = ['status', 'rfp_no', 'method', 'check', 'proc_date',
                           'vatable', 'vat', 'ewt', 'aging', 'aging_bucket'];
```

**Three explicit rules in code:**
1. If a SCRIPT_OWNED cell is blank on **both** sides (sheet AND source), leave blank.
2. If a SCRIPT_OWNED cell has a human-typed value but the source (FPM/Compliance) is blank, **leave the human value** (never overwrite with blank).
3. If a SCRIPT_OWNED cell has a human-typed value AND the source has a non-blank conflicting value, **log to `_sync_conflicts` tab and keep the human value**. Sam reviews.

**HUMAN_OWNED_COLS are never touched by the script under any condition.**

## Banner rows (script behavior)

The script looks for a header row by finding the first row where column A = `'SOURCE'` (case-insensitive). Everything above that row is treated as the banner (title, summary KPIs, frozen rows) and is left untouched. Everything below is treated as data.

If the banner gets messed up (e.g., someone deletes the `SOURCE` header), the script will fail silently — it sees no header, so it processes zero rows. Symptom: sync log shows `tabs_seen[<name>]=0`.

## Join keys

**Primary join (`Suppliers SOA` → FPM):**
- `BEI-FIN No.` (col J on AP Master) → `BEI-FIN No. (if applicable)` (in FPM `RFP Summary` tab)
- Normalized via `nk(s)`: strip non-alphanumeric, uppercase.

**Secondary join (`Head Office` and `CAPEX` → FPM):**
- (Payee uppercase + '|' + amount rounded to 2 decimals) → same composite key in FPM
- Used when BEI-FIN No. is not in the source (HO/CAPEX rows typically don't have an RFP ID).

**Tax join (all 3 tabs → Compliance):**
- `INVOICE NO.` (col C) → `Invoice No` in Compliance `Advance Invoices` tab
- Normalized via `invKey(s)`: same as `nk`.

**Variant matches that all collide to the same key:** `INV-2026-1234`, `2026-1234`, `20261234`, `inv 2026-1234`, `INV.2026.1234`, ` inv-2026-1234 ` — by design, so suppliers and Ms. Mel can type any format.

## What "data disappearing" actually means

If you see entries in the data-entry tabs vanish, it's one of three things:

1. **v2 wipe-rebuild mode is still running** (legacy, pre-2026-04-20). v2 wipes the tab and rebuilds every hour, overwriting any human edits. Check the script deployment — `?fn=refreshAllTabs&mode=v2` is the legacy path; the new default is `?fn=refreshAllTabs` which runs v3 field-sync (preserves human cells). If you see v2 logs, switch to v3.

2. **Someone deleted rows manually.** Check the sheet's revision history (File → Version history) to identify who and when. Likely candidates: the team thought it was the old archived sheet and started "cleaning up" — they were on the wrong file.

3. **Banner rows shifted and the script can't find the SOURCE header anymore.** Symptom: data is still there, but the script appears to be ignoring updates. Fix: scroll to where the data starts and check that column A says `SOURCE` exactly.

If neither applies, capture a `_sync_conflicts` snapshot + an `_sync_log_v3` excerpt and escalate to Sam.

## The 4 hidden tabs in v2 (informational)

These tabs exist on the AP Master from the v2 era but the team is told not to touch them:
- `_sync_log_v3` — the v3 audit log (current, useful for debugging)
- `_sync_log` — the v2 audit log (kept for back-compat; v2 wipe-rebuild still writes here)
- `_dry_run_preview` — populated only when `?dryRun=1` is hit
- `_sync_conflicts` — written when a SCRIPT_OWNED column has a human value that disagrees with the source

If you need to test changes safely, **always hit dryRun=1 first** and review `_dry_run_preview` before letting the live sync write.
