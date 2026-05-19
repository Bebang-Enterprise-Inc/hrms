# Troubleshooting

Common operational issues with the BEI AP system and how to diagnose them.

## "Entries I typed disappeared" — REVISED 2026-05-12

**Most likely cause: typed in the wrong TAB (not wrong SHEET).** Validated via the Commissary incident — see below.

### Commissary Incident (2026-05-12) — case study

Ms. Angela (Angelamel Letada / Ms. Mel) typed `ICON PRINTING SOLUTIONS Invoice 00183` directly into the `Commissary` tab on BEI AP Master. Within the hour the script's auto-refresh rebuilt the Commissary tab from sources and her entry was gone.

**Why:** `Commissary`, `Summary`, `Head Office (BEI)`, `Needs Attention` are SUMMARY tabs — auto-rebuilt by the hourly script from FPM + Suppliers SOA. They look editable but aren't. The original Team Guide (2026-04-21) only documented 10 tabs; these 4 were added later and never made it into training.

**Fix applied 2026-05-12:**
1. All 14 auto-rebuilt tabs are now STRICT-locked (editors=sam@bebang.ph only). Team gets a hard "Cannot edit this tab" block now, not a warning popup they can dismiss.
2. Team Guide doc updated with the complete 17-tab map (see Section 8 of the Team Guide).

### Diagnostic flow for "entries disappear"

1. **Check which TAB they typed in.** If it's one of the 14 locked tabs, they got the strict block now. If pre-2026-05-12, that's the answer.
2. **Check `_sync_log_v3` tab** — last entry should be from the current hour. If it shows `cell_updated` events, the script is operating correctly on the entry tabs.
3. **Check `_sync_conflicts` tab** — should be empty. If rows present, the script overwrote a SCRIPT_OWNED cell value (team edited STATUS/RFP/VAT on entry tab — those should go in FPM/Compliance instead).
4. **Verify they're on BEI AP Master `1bQ6mO...`, not the archived `1ZHe...` sheet** — the archived sheet still receives edits but doesn't feed AP Master for new rows.

## "Wrong sheet — I edited the archived one and now I can't find my entry on the new one"

The four archived sheets (A1–A4 in `sheets-inventory.md`) are still accessible. People who used them daily for months haven't broken the habit. Sometimes they type new entries on the archived sheet instead of the AP Master.

**Diagnostic:**
- If the entry exists on `1ZHe...` (archived A1) but NOT on `1bQ6mO...` (live AP Master), the team typed on the wrong sheet.

**Fix:**
- Copy the row from the archived sheet to AP Master `Suppliers SOA` (or `Head Office` / `CAPEX` as appropriate)
- Delete from the archived sheet to prevent double-counting
- Remind the team to bookmark the AP Master URL: https://docs.google.com/spreadsheets/d/1bQ6mO1FXD4VYcLt8m-yklkV7pyYhSWqU7b8K0bVgG7c/edit
- Consider: the only safe permanent fix is to revoke Writer access on the archived sheets (turn them read-only). The team will then have to use AP Master.

## "I can't access the AP Master / I'm blocked"

**Diagnostic:**
1. Confirm which email the team member is logged into Google with. If they're signed into a non-bebang.ph account, they'll get blocked on a domain-restricted sheet.
2. Check the AP Master permissions matrix in `permissions.md`. Find their email.
3. If they're not on the list, that's the fix — add them as Editor.

**Avis specifically (current incident):**
- She's a writer on the *receiving* sheets (per `/dr-gr-rfp` skill) but NOT on AP Master, FPM, or the archived AP sheets
- Fix: add `avislyndelle@bebang.ph` as Editor to all 6 sheets listed in `permissions.md` → "Why Avis is currently locked out" section

## "Sync didn't fire — no recent _sync_log_v3 entry"

**Diagnostic:**
1. Check Cloud Scheduler logs in GCP Console for project `quiet-walker-475722-s2`. The job is named something like `bei-ap-master-hourly-sync`. Last successful run timestamp = baseline.
2. If Cloud Scheduler ran but the script returned an error, check Apps Script editor → Executions tab.
3. If the web app URL returns HTTP 401/403, the token may have been rotated or the deployment expired.
4. The script self-heals via `ensureTriggerHealthy_()` but only when invoked — if no invocation happens, no self-heal.

**Fix:**
- For a token mismatch: redeploy the web app from the Apps Script editor and update Cloud Scheduler with the new URL.
- For an expired deployment: in Apps Script editor, Deploy → Manage Deployments → New Version → Save. Update Cloud Scheduler.
- For permissions on the script itself: rare, but if the deployer (Sam) lost OAuth consent, re-authorize via the Apps Script editor.

## "VAT showing as 0 on AP Master but Compliance has a value"

**Diagnostic:**
1. Check the `INVOICE NO.` value on AP Master. The script normalizes via `invKey()` (strip non-alphanumeric, uppercase). So `INV-2026-1234` should match `inv2026/1234`. But typos or extra characters (newlines, hidden whitespace, similar Unicode characters) will miss.
2. Open Compliance `Advance Invoices` and confirm the invoice is present.
3. Look at AP Master `_sync_log_v3` for the row to see if a tax sync happened.

**Fix:**
- Normalize the invoice number on AP Master to match Compliance exactly.
- If the supplier is consistently miswriting, consider adding an alias map in the script (`invKey` enhancement).

## "Status not updating from FPM"

**Diagnostic:**
1. Check that the AP Master row has a `BEI-FIN No.` populated. This is the primary join key for Suppliers SOA.
2. For Head Office / CAPEX (which usually don't have BEI-FIN No.), check that PAYEE + AMOUNT match FPM exactly.
3. Verify the FPM row has a populated Status column. Empty source = no update (per the "leave human value" rule).

**Fix:**
- If BEI-FIN No. mismatch: type the correct number on AP Master.
- If FPM is missing the BEI-FIN No.: Denise needs to fill it in FPM (not on AP Master).
- If both have it but they don't match: spelling error — fix on whichever side is wrong.

## "_sync_conflicts is growing too large"

**Diagnostic:**
- Open the `_sync_conflicts` tab. Each row says: which tab, which row, what human value, what source value, when.

**Common causes:**
- Team is editing SCRIPT_OWNED columns directly on AP Master (e.g., changing the status from `WITH FINANCE` to `CHECK RELEASED` on the AP Master itself, when they should be doing it in FPM).
- FPM was bulk-edited (e.g., post-BDO catchup) and now disagrees with what humans had typed on AP Master months ago.

**Fix:**
- Train the team: status changes happen in FPM, never on AP Master.
- For one-off cleanups: review the conflicts in batches, decide which side wins, manually correct one side.

## "TOTAL PAYABLES on AP AGING PER SUPPLIER doesn't match AP Master All Liabilities"

The legacy `AP AGING PER SUPPLIER` tab on archived `1ZHe...` is computed by manual SUMIFs against the SUPPLIERS SOA tab on that same archived sheet. It does NOT read AP Master.

So there can be a delta if:
- New invoices on AP Master `Suppliers SOA` were NOT also added to archived SUPPLIERS SOA (which they shouldn't be, but the team sometimes does both)
- Old invoices were marked PAID on AP Master but the archived sheet's manual SUMIF is still summing them

**The truth source going forward:** AP Master `All Liabilities` tab.
**The legacy reference (still being maintained):** archived `AP AGING PER SUPPLIER` tab.

When they disagree, AP Master is correct.

## "Avis says entries that she/Accounting are typing keep disappearing"

This is the current incident (2026-05-12). Three possible roots:

1. **Avis doesn't have access to AP Master** — so she's typing on the archived `1ZHe...` instead. The script doesn't read that sheet (for new edits), so her work stays in the archived sheet. When she then opens AP Master to verify, she sees no entry → "it disappeared." **Fix: grant her access to AP Master.**

2. **Avis IS on AP Master but is typing in SCRIPT_OWNED columns** — those get overwritten by the hourly sync if FPM/Compliance has a different value. **Fix: train her to only edit HUMAN_OWNED columns (Source, Payee, Invoice No., Invoice Date, Amount, Outstanding, Category, Classification, Billed To).**

3. **v2 wipe-rebuild is still firing** — see top of this file. **Fix: verify Cloud Scheduler is calling v3 (no `mode=v2` parameter).**

Run all three diagnostics in parallel; the actual fix may be a combination.

## "How to test changes before letting them go live"

Use the v3 dry-run mode:
```
GET https://script.google.com/macros/s/AKfycbw-AuqJq6OyMV6DGarGWEruDoez04OETlWFQoeppNjvzoeSOJOomPOZNsVPE9iuV6ZC_Q/exec?key=bei-ap-sync-2026-04&fn=refreshAllTabs&dryRun=1
```

Results write to `_dry_run_preview` tab. Review what would have changed before letting the next hourly run touch live cells.

## "How to manually trigger a sync (skip waiting for the hourly cron)"

```bash
curl 'https://script.google.com/macros/s/AKfycbw-AuqJq6OyMV6DGarGWEruDoez04OETlWFQoeppNjvzoeSOJOomPOZNsVPE9iuV6ZC_Q/exec?key=bei-ap-sync-2026-04&fn=refreshAllTabs'
```

Returns a JSON response with the cycle stats. Takes ~30-60 seconds on a typical load.
