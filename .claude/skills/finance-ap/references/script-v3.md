# AP Master Apps Script v3 — Field-Sync Architecture

The hourly auto-sync that keeps the AP Master in agreement with FPM and Compliance.

## Source location

- **Live deployment:** Google Apps Script project bound to `1bQ6mO1FXD4VYcLt8m-yklkV7pyYhSWqU7b8K0bVgG7c` (the AP Master sheet itself). Open via Sheet → Extensions → Apps Script.
- **Repo copy (canonical):** `F:\Dropbox\Projects\BEI-ERP\CEO\CashFlow\intercompany_gl\ap_view_hourly_sync_v3.gs` (1,047 lines, committed 2026-04-20 18:47).
- **Legacy v2 in repo:** `CEO/CashFlow/intercompany_gl/ap_view_hourly_sync.gs` (538 lines, kept for back-compat / T1.8 baseline seed).

## Web-app deployment

| Item | Value |
|---|---|
| Web app URL | `https://script.google.com/macros/s/AKfycbw-AuqJq6OyMV6DGarGWEruDoez04OETlWFQoeppNjvzoeSOJOomPOZNsVPE9iuV6ZC_Q/exec` |
| Auth token (`?key=...`) | `bei-ap-sync-2026-04` |
| Runs as | Deployer (sam@bebang.ph) |
| Trigger | Cloud Scheduler — hourly cron (GCP project `quiet-walker-475722-s2`) |

## Routes

| Query | Behavior |
|---|---|
| `?key=bei-ap-sync-2026-04&fn=refreshAllTabs` | Default — runs v3 field-sync |
| `?key=...&fn=refreshAllTabs&mode=v2` | Legacy wipe-rebuild (DESTRUCTIVE — wipes human edits). Use only for the T1.8 baseline seed. |
| `?key=...&fn=refreshAllTabs&dryRun=1` | v3 in dry-run — writes preview to `_dry_run_preview` tab, no live writes |
| `?key=...&fn=runDiagnostics` | Health check |

## v3 vs v2 — the big difference

**v2 (wipe-rebuild):**
```javascript
// Clear every data row, then rewrite from source.
tab.getRange(headerRow+1, 1, lastRow-headerRow, NCOLS).clearContent();
tab.getRange(headerRow+1, 1, newRows.length, NCOLS).setValues(newRows);
```
**Side effect:** any cell a human typed got wiped every hour. This is why entries "disappeared" before v3.

**v3 (field-sync):**
```javascript
// Read existing rows. For each row, only update SCRIPT_OWNED columns where source has a non-blank value.
// Never touch HUMAN_OWNED columns. Log conflicts to _sync_conflicts.
syncStatusFieldsFromFPM_(ss, fpmLookup, dryRun);
syncTaxFieldsFromCompliance_(ss, taxLookup, dryRun);
seedNewInvoicesFromSources_(ss, fpmLookup, taxLookup, dryRun);  // APPEND-only for new invoices
```
**Net effect:** human edits are preserved indefinitely; only status/RFP/check/method/VAT/EWT/aging cells refresh hourly.

## The three sync functions (in order)

### 1. `syncStatusFieldsFromFPM_(ss, fpmLookup, dryRun)`
Updates columns I, K, L, M (status, RFP_no, method, check) on the 3 data-entry tabs from FPM `RFP Summary` tab.

- **Lookup:** `byFin` map keyed on `BEI-FIN No.` (primary key for Suppliers SOA), `byPayeeAmt` map keyed on `PAYEE|AMOUNT` (fallback for HO and CAPEX which don't carry BEI-FIN No.).
- **Per-tab strategy:**
  - `Suppliers SOA` → `byFin` only (RFP ID is the join key)
  - `Head Office` → `byPayeeAmt` only
  - `CAPEX` → `byPayeeAmt` only
- **Conflict rule:** If FPM has a non-blank value that disagrees with the existing AP Master value for the same row, **log to `_sync_conflicts` and keep the AP Master value**. Sam reviews periodically.

### 2. `syncTaxFieldsFromCompliance_(ss, taxLookup, dryRun)`
Updates columns Q, R, S (vatable, vat, ewt) on the 3 data-entry tabs from Compliance AppSheet `PO Items` + `Advance Invoices` tabs.

- **Lookup:** `byInvKey` keyed on normalized invoice number → `{vatable, vat, ewt}`.
- **VAT math:** Compliance has VAT at the PO level. The script splits each PO's total VAT proportionally across multiple invoices by `invoice_amount / po_total_amount`. (This was the **2026-04-16 23:42 proportional VAT fix** — see history.)

### 3. `seedNewInvoicesFromSources_(ss, fpmLookup, taxLookup, dryRun)`
**APPEND ONLY** — adds new rows to the data-entry tabs for invoices that exist in FPM or the archived AP Opening sheets but don't yet exist on the AP Master.

- Never touches existing rows.
- Used during the initial S211 cutover and ongoing for invoices that come in via FPM before Ms. Mel types them.

## Key helpers

```javascript
function toNum(v)            // robust number coercion (handles commas, currency symbols, "1,234.56")
function nk(s)               // normalize a key — strip non-alphanumeric, uppercase
function invKey(s)           // same as nk — used for invoice number matching
function serialToDate(v)     // Google Sheets serial date → JS Date
function logEvent_(level, type, data)        // write to _sync_log_v3 tab
function maybeSendAlert_(subject, body)      // email Sam if last alert > 6h ago
function ensureTriggerHealthy_()             // self-heal: install/reinstall hourly trigger
```

## Logging

Every cycle writes one row to `_sync_log_v3` with:
- `timestamp`
- `level` (INFO / WARN / ERROR)
- `type` (`refresh_success_v3`, `refresh_failed_v3`, `v3_cycle_complete`, etc.)
- `duration_ms`
- `v3_stats` JSON blob with per-tab counts of updates/conflicts/no-change

For finer-grained per-cell logging, an entry is written for every SCRIPT_OWNED column that the script actually changed (rare — only when source had a newer value).

## Email alerts

If a sync fails, the script emails `sam@bebang.ph` with the error and stack trace. Alert rate-limited to once every 6 hours (`ALERT_MIN_INTERVAL_HOURS = 6`).

## Self-heal

`ensureTriggerHealthy_()` runs at the top of every cycle. If the hourly trigger has been deleted (Google sometimes cleans up triggers under certain conditions), it reinstalls itself. **But** with Cloud Scheduler as the primary trigger, this is mostly belt-and-suspenders.

## Source data dependencies

| Source | Sheet ID | Tab | What we read |
|---|---|---|---|
| FPM | `1t4wJLiAfIMJm6fe-x6h4eZn_S_Lx1AGN5ORd5Ywhcyw` | `RFP Summary` | Payee, Amount Due, Status, RFP NO., Payment Method, Check No./Ref No., Processed Date, BEI-FIN No. |
| Compliance AppSheet | `1QWdoZlT7XWLppfVKpJ2VRXhbMkYtE5TbUwg4lMbO03Q` | `PO Items` | PO No, VAT, Amount (for VAT proportional split) |
| Compliance AppSheet | `1QWdoZlT7XWLppfVKpJ2VRXhbMkYtE5TbUwg4lMbO03Q` | `Advance Invoices` | Invoice No, PO No, Invoice Amount, EWT Amount |
| Archived SOA | `1ZHe2VoAFa94ET4I68C1jWM7nMzTdTCvttwZbICaLtB4` | `SUPPLIERS SOA` | One-time seed for invoices not in FPM |
| Archived HO | `1jSwZRyIPisU4jiKS-Tn9VFoLukQI8UNoW13Hoov-75Y` | `Detailed HEAD OFFICE` | One-time seed for HO/CAPEX |

## Operational notes

1. **The script runs as Sam's identity** (deployer = sam@bebang.ph). All audit log entries in Sheets → File → Version history show as Sam. To attribute changes to humans, check the `_sync_log_v3` tab content (not the Sheets revision history).

2. **Cloud Scheduler job lives in GCP project `quiet-walker-475722-s2`** (same project as the BEI service account `task-manager-service`). Region: `asia-southeast1`.

3. **No container-bound triggers are required.** Cloud Scheduler hitting the web-app URL is the entire trigger path. If the Apps Script editor shows installed triggers, they're leftovers from v1 and can be removed via `removeAllTriggers()` (defined in the v2 source).

4. **Token rotation:** `WEBAPP_TOKEN` is hardcoded in the script as `bei-ap-sync-2026-04`. If rotated, update Cloud Scheduler job URLs in tandem.

5. **The script does NOT delete rows.** It only updates cells and appends new ones. If you see rows missing, it wasn't the script — check sheet revision history.

## Common gotchas

| Symptom | Likely cause | Fix |
|---|---|---|
| `_sync_log_v3` shows "tabs_seen[Suppliers SOA]=0" | The `SOURCE` header row was deleted or moved | Re-add `SOURCE` as the column A header above the data block |
| `_sync_conflicts` grows quickly | Humans editing SCRIPT_OWNED columns directly | Train team to make status changes in FPM, not AP Master |
| Sync emails arrive 6h apart with same error | Alert rate-limited; underlying issue not fixed | Check Cloud Scheduler logs + script execution log in Apps Script editor |
| New invoices not appearing on AP Master | They never made it into FPM AND aren't in the archived seed sheets | Either (a) Ms. Mel types them directly, or (b) the source upstream of FPM has the issue |
| VAT showing as 0 but Compliance has a value | Invoice number on AP Master doesn't match Compliance's format | Check `invKey` normalization — strip dashes/spaces and try again |

## Future cleanup work (per the script's comments)

- T1.8: Final baseline seed via `?mode=v2` then permanently flip default to v3 (already done — `mode=v3` is now the default).
- Phase 4 (Sam decision pending): rename the sheet from "AP Suppliers - Payment Status (Auto-View)" to "BEI AP Master" in the actual Drive metadata.
- Remove all references to "`Suppliers SOA`" archived sheet once Ms. Mel's data entry is 30 days clean — no more new seeds needed.
