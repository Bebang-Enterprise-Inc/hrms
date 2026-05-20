# Payment Plan Cutover Runbook

Created by S255 Phase 7.4 — 2026-05-20

## When to use this runbook

Denise tells Sam: "I'm ready to switch off my standalone Project: 2-Week Payment Plan sheet and use AP Master Payment Plan as my primary tracker."

## Pre-cutover state

- `payment_plan_mirror_disabled = false` (default in v3.9)
- Every hourly cycle: `mirrorDenisePaymentPlanTab_` WIPES + REBUILDS Payment Plan from Denise's standalone sheet
- `syncStatusFieldsFromFPM_` skips Payment Plan (mirror handles it)
- Denise works in her standalone sheet; AP Master Payment Plan is a read-only mirror she can preview

## Post-cutover state

- `payment_plan_mirror_disabled = true`
- `mirrorDenisePaymentPlanTab_` early-exits with `{ mirror_disabled: true }` — no rebuild
- `syncStatusFieldsFromFPM_` INCLUDES Payment Plan in its tab iteration — writes STATUS, RFP No., METHOD, CHECK NO. into PP cols from FPM
- Denise works directly in AP Master Payment Plan; FPM stays the upstream source for status

## Cutover procedure

### Step 1: Confirm Denise is ready

Chat Denise: "Ready to switch off your standalone sheet to AP Master? After this, your sheet becomes read-only (you'll still see history; AP Master Payment Plan is where you'll edit new rows)."

### Step 2: Take a backup of current PP state

```bash
python -c "
from google.oauth2 import service_account
from googleapiclient.discovery import build
import json, sys
creds = service_account.Credentials.from_service_account_file('credentials/task-manager-service.json', scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']).with_subject('sam@bebang.ph')
s = build('sheets', 'v4', credentials=creds, cache_discovery=False)
data = s.spreadsheets().values().get(spreadsheetId='1bQ6mO1FXD4VYcLt8m-yklkV7pyYhSWqU7b8K0bVgG7c', range=\"'Payment Plan'!A1:AD\", valueRenderOption='UNFORMATTED_VALUE').execute()
json.dump(data, open('output/pp_cutover_backup.json', 'w'), indent=2, default=str)
print('Saved', len(data.get('values', [])), 'rows')
"
```

### Step 3: Edit v3.9 source

Change line ~62 from:
```javascript
const payment_plan_mirror_disabled = false;
```
to:
```javascript
const payment_plan_mirror_disabled = true;
```

### Step 4: Pause Cloud Scheduler (avoid mid-flight)

```bash
gcloud scheduler jobs pause ap-auto-view-hourly-refresh \
  --project=quiet-walker-475722-s2 --location=asia-southeast1
```

### Step 5: Deploy as v3.10 (or v3.9.X)

Push updated source via Apps Script API; promote to new version.

### Step 6: Resume scheduler

```bash
gcloud scheduler jobs resume ap-auto-view-hourly-refresh \
  --project=quiet-walker-475722-s2 --location=asia-southeast1
```

### Step 7: Trigger one cycle manually and verify

```bash
curl 'https://script.google.com/macros/s/AKfycbw-Auq.../exec?key=bei-ap-sync-2026-04&fn=refreshAllTabs'
```

Verify:
- mirror_disabled: true appears in `_sync_log_v3` mirror_stats
- syncStatusFieldsFromFPM_ stats show Payment Plan in `tabs_seen`
- Sample 5 PP rows; verify col I (STATUS) reflects latest FPM status

### Step 8: Announce + lock Denise's standalone sheet

Change Denise's ACL on her standalone sheet from "writer" to "commenter" for her and the team (Sam keeps writer). Sheet becomes read-only history.

### Step 9: Chat the team

"Cutover complete. Edit Payment Plan rows in AP Master from now on. Denise PP standalone sheet is read-only history."

## Rollback (if cutover breaks something)

1. Pause scheduler
2. Edit v3.9 source: `payment_plan_mirror_disabled = false`
3. Deploy
4. Resume scheduler
5. Trigger cycle; mirror takes over again

## Verification checklist (after cutover)

- [ ] `_sync_log_v3` shows mirror_disabled: true in latest hourly stats
- [ ] PP col I values match what FPM has for the corresponding BEI-FIN
- [ ] Denise can edit PP rows (writer access on AP Master)
- [ ] Bridge can read PP rows for DD audit
- [ ] Banner refreshes correctly on PP tab (row 4 total)
