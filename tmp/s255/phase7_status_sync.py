"""S255 Phase 7 — Status sync wiring to Payment Plan tab (gated).

7.1 Add payment_plan_mirror_disabled = false constant
7.2 mirrorDenisePaymentPlanTab_ early-exit when flag is true
7.3 syncStatusFieldsFromFPM_ adds 'Payment Plan' to its iteration WHEN flag is true
7.4 Write payment_plan_cutover_runbook.md
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[2]
V39_PATH = ROOT / "scripts" / "google_apps" / "s255_ap_view_hourly_sync_v39.gs"


def main():
    log = {"phase": "7", "started_at": datetime.now().astimezone().isoformat(), "tasks": {}}

    src = V39_PATH.read_text(encoding="utf-8")

    # ─────────────────────────────────────────────────────────────
    # 7.1 — Add flag constant
    # ─────────────────────────────────────────────────────────────
    if "const payment_plan_mirror_disabled" not in src:
        anchor = "const ALERT_EMAIL = 'sam@bebang.ph';"
        new_block = anchor + """

// ───────────────────────────────────────────────────────────────────────────
// v3.9 (S255 Phase 7) — Payment Plan cutover gate
// When false (default): mirrorDenisePaymentPlanTab_ runs hourly; syncStatusFieldsFromFPM_
//   skips Payment Plan tab (mirror handles it).
// When true: mirror stops; syncStatusFieldsFromFPM_ writes STATUS/RFP/METHOD/CHECK NO. into
//   Payment Plan col I (STATUS) etc. This is the cutover path Denise will use when she's
//   ready to make AP Master Payment Plan her primary tracker.
//
// To flip: edit this line, push v3.10, promote deployment. (Or use PropertiesService
// later for toggle-without-redeploy — S256.)
// ───────────────────────────────────────────────────────────────────────────
const payment_plan_mirror_disabled = false;"""
        assert anchor in src, "Could not find ALERT_EMAIL anchor for flag insertion"
        src = src.replace(anchor, new_block)
        log["tasks"]["7.1"] = {"status": "DONE", "constant_added": "payment_plan_mirror_disabled = false"}
        print("[7.1] flag constant added")
    else:
        log["tasks"]["7.1"] = {"status": "ALREADY_PRESENT"}
        print("[7.1] flag already present")

    # ─────────────────────────────────────────────────────────────
    # 7.2 — mirrorDenisePaymentPlanTab_ early-exit when flag is true
    # ─────────────────────────────────────────────────────────────
    anchor72 = "function mirrorDenisePaymentPlanTab_(ss, dryRun) {\n  const stats = {"
    new_block72 = """function mirrorDenisePaymentPlanTab_(ss, dryRun) {
  // v3.9 (S255 Phase 7.2): early-exit when cutover flag is set; sync path takes over
  if (payment_plan_mirror_disabled) {
    return { mirror_disabled: true, by_tab: {} };
  }
  const stats = {"""
    if "mirror_disabled: true" not in src and anchor72 in src:
        src = src.replace(anchor72, new_block72)
        log["tasks"]["7.2"] = {"status": "DONE", "patch": "early-exit in mirrorDenisePaymentPlanTab_"}
        print("[7.2] mirror early-exit added")
    elif "mirror_disabled: true" in src:
        log["tasks"]["7.2"] = {"status": "ALREADY_PRESENT"}
        print("[7.2] mirror early-exit already present")
    else:
        log["tasks"]["7.2"] = {"status": "ANCHOR_NOT_FOUND"}
        print("[7.2] WARN: could not find anchor for mirror early-exit")

    # ─────────────────────────────────────────────────────────────
    # 7.3 — syncStatusFieldsFromFPM_ conditional Payment Plan inclusion
    # ─────────────────────────────────────────────────────────────
    # Find the existing 4-tab forEach (from Phase 2.5)
    anchor73 = "['Suppliers SOA', 'Head Office', 'CAPEX', 'Intercompany'].forEach(tabName => {\n    const t = readEditTabRows_(ss, tabName);\n    if (!t.sheet) return;\n    stats.tabs_seen[tabName] = t.rows.length;"
    new_block73 = """(payment_plan_mirror_disabled
    ? ['Suppliers SOA', 'Head Office', 'CAPEX', 'Intercompany', 'Payment Plan']
    : ['Suppliers SOA', 'Head Office', 'CAPEX', 'Intercompany']
  ).forEach(tabName => {
    const t = readEditTabRows_(ss, tabName);
    if (!t.sheet) return;
    stats.tabs_seen[tabName] = t.rows.length;"""
    if anchor73 in src:
        src = src.replace(anchor73, new_block73)
        log["tasks"]["7.3"] = {"status": "DONE", "patch": "conditional Payment Plan in syncStatusFieldsFromFPM_"}
        print("[7.3] status sync conditional PP added")
    elif "payment_plan_mirror_disabled\n    ? ['Suppliers SOA'" in src:
        log["tasks"]["7.3"] = {"status": "ALREADY_PRESENT"}
        print("[7.3] status sync conditional PP already present")
    else:
        log["tasks"]["7.3"] = {"status": "ANCHOR_NOT_FOUND"}
        print("[7.3] WARN: could not find anchor for status sync conditional PP")

    V39_PATH.write_text(src, encoding="utf-8")

    # ─────────────────────────────────────────────────────────────
    # 7.4 — Cutover runbook
    # ─────────────────────────────────────────────────────────────
    runbook = """# Payment Plan Cutover Runbook

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
data = s.spreadsheets().values().get(spreadsheetId='1bQ6mO1FXD4VYcLt8m-yklkV7pyYhSWqU7b8K0bVgG7c', range=\\\"'Payment Plan'!A1:AD\\\", valueRenderOption='UNFORMATTED_VALUE').execute()
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
gcloud scheduler jobs pause ap-auto-view-hourly-refresh \\
  --project=quiet-walker-475722-s2 --location=asia-southeast1
```

### Step 5: Deploy as v3.10 (or v3.9.X)

Push updated source via Apps Script API; promote to new version.

### Step 6: Resume scheduler

```bash
gcloud scheduler jobs resume ap-auto-view-hourly-refresh \\
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
"""
    runbook_path = ROOT / "output" / "s255" / "payment_plan_cutover_runbook.md"
    runbook_path.write_text(runbook, encoding="utf-8")
    log["tasks"]["7.4"] = {"status": "DONE", "path": str(runbook_path)}
    print(f"[7.4] cutover runbook written")

    log["finished_at"] = datetime.now().astimezone().isoformat()
    (ROOT / "output" / "s255" / "phase7_log.json").write_text(json.dumps(log, indent=2, default=str), encoding="utf-8")
    print(f"\nPhase 7 done. v3.9 size = {len(src.encode('utf-8'))} bytes")


if __name__ == "__main__":
    main()
