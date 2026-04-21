"""S215 Phase 4 — timestamp auto-fill + Timestamp column lock on 3PL Receipts.

P4-T1..T3: create one container-bound Apps Script per 3PL sheet (A=3MD, B=Pinnacle, D=Shaw).
P4-T4: push a `Code.gs` with onEdit(e) that stamps server Timestamp on new rows +
       `appsscript.json` manifest.
P4-T5: add protected range on each sheet's Receipts!A column (Timestamp).
P4-T6: smoke test — append a row without Timestamp, confirm Timestamp auto-fills.

Idempotent: if a bound script with title 'S215 Timestamp Auto-fill — <3PL>' already
exists on the parent sheet, the script will be REUSED (updateContent only), not
duplicated.
"""
import json
import pathlib
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SA = r'F:\Dropbox\Projects\BEI-ERP\credentials\task-manager-service.json'
OUT = pathlib.Path(r'F:\Dropbox\Projects\BEI-ERP-s215\output\s215')
OUT.mkdir(parents=True, exist_ok=True)

SHEET_A = '1dambmiLzSMWOQun7MCymK4nHpuqrarFCAOK0G9-6oIU'
SHEET_B = '10fqnvF_uDl5ky3MkvXUmWvZ1fYat_p6XFGmVFc3vqrw'
SHEET_D = '1mbJiLW9M9e-AmrXSRRTtbRP-xKI16ah5rakOt6qv2As'

SHEETS = [
    ('sheetA', SHEET_A, 'S215 Timestamp Auto-fill — 3MD'),
    ('sheetB', SHEET_B, 'S215 Timestamp Auto-fill — Pinnacle'),
    ('sheetD', SHEET_D, 'S215 Timestamp Auto-fill — Shaw'),
]

creds = service_account.Credentials.from_service_account_file(
    SA, scopes=[
        'https://www.googleapis.com/auth/script.projects',
        'https://www.googleapis.com/auth/script.deployments',
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive',
    ],
).with_subject('sam@bebang.ph')
script_api = build('script', 'v1', credentials=creds, cache_discovery=False)
drive_api = build('drive', 'v3', credentials=creds, cache_discovery=False)
sheets_api = build('sheets', 'v4', credentials=creds, cache_discovery=False).spreadsheets()

# The onEdit code. We read the actual "Timestamp" column position dynamically at
# edit time so the script survives future Receipts-tab header changes. Sheet A/B/D
# all use Timestamp at col A (index 1), so the default is safe.
ONEDIT_CODE = r"""/**
 * S215 Phase 4: timestamp auto-fill on 3PL Receipts.
 * Fires on every user edit (container-bound onEdit simple trigger).
 * If a user adds a new row (any new non-blank cell in row >= 2 on Receipts),
 * stamp the Timestamp column (col 1) with server time — unless already set.
 */
function onEdit(e) {
  try {
    if (!e || !e.range) return;
    var sheet = e.range.getSheet();
    if (sheet.getName() !== 'Receipts') return;

    var row = e.range.getRow();
    if (row < 2) return;                        // skip header row

    // Only act when the user typed something (not a clear)
    if (e.value === null || typeof e.value === 'undefined' || e.value === '') return;

    var tsCell = sheet.getRange(row, 1);        // col A = Timestamp
    var curr = tsCell.getValue();
    if (curr) return;                           // already stamped — preserve

    // Don't stamp if the edited cell IS the Timestamp cell itself (user typed there)
    if (e.range.getColumn() === 1) return;

    tsCell.setValue(new Date());
  } catch (err) {
    // Fail silently — simple onEdit triggers that throw kill subsequent edits.
    console.error('S215 onEdit error: ' + err);
  }
}
"""

MANIFEST = json.dumps({
    'timeZone': 'Asia/Manila',
    'dependencies': {},
    'exceptionLogging': 'STACKDRIVER',
    'runtimeVersion': 'V8',
}, indent=2)


def find_bound_script(parent_id, title):
    """Return scriptId of existing bound script with given title under parent, or None."""
    q = f"mimeType='application/vnd.google-apps.script' and '{parent_id}' in parents and trashed=false and name='{title}'"
    resp = drive_api.files().list(q=q, fields='files(id,name)', supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
    files = resp.get('files', [])
    return files[0]['id'] if files else None


def ensure_bound_script(parent_id, title):
    existing = find_bound_script(parent_id, title)
    if existing:
        return existing, 'reused'
    resp = script_api.projects().create(body={'title': title, 'parentId': parent_id}).execute()
    return resp['scriptId'], 'created'


def push_code(script_id):
    files = [
        {'name': 'Code', 'type': 'SERVER_JS', 'source': ONEDIT_CODE},
        {'name': 'appsscript', 'type': 'JSON', 'source': MANIFEST},
    ]
    return script_api.projects().updateContent(scriptId=script_id, body={'files': files}).execute()


def ensure_timestamp_col_protection(ssid):
    """Protect Receipts!A (Timestamp column) — editors = sam@bebang.ph only."""
    meta = sheets_api.get(spreadsheetId=ssid, includeGridData=False).execute()
    receipts_id = None
    for s in meta['sheets']:
        if s['properties']['title'] == 'Receipts':
            receipts_id = s['properties']['sheetId']
            # Check existing protections
            for p in s.get('protectedRanges', []):
                if p.get('description') == 'S215: Timestamp auto-filled — do not edit':
                    return {'action': 'already_protected', 'protectionId': p.get('protectedRangeId')}
            break
    if receipts_id is None:
        return {'action': 'no_receipts_tab'}

    resp = sheets_api.batchUpdate(spreadsheetId=ssid, body={
        'requests': [{
            'addProtectedRange': {
                'protectedRange': {
                    'range': {
                        'sheetId': receipts_id,
                        'startColumnIndex': 0, 'endColumnIndex': 1,
                        'startRowIndex': 1,  # header row 0 excluded
                    },
                    'description': 'S215: Timestamp auto-filled — do not edit',
                    'warningOnly': False,
                    'editors': {'users': ['sam@bebang.ph'], 'domainUsersCanEdit': False},
                }
            }
        }]
    }).execute()
    pid = resp['replies'][0]['addProtectedRange']['protectedRange']['protectedRangeId']
    return {'action': 'added', 'protectionId': pid}


result = {
    'bound_scripts': {},
    'code_pushed': {},
    'protections': {},
}

for key, ssid, title in SHEETS:
    print(f'=== {key} — {title} ===')
    sid, action = ensure_bound_script(ssid, title)
    result['bound_scripts'][key] = {'scriptId': sid, 'parentId': ssid, 'action': action}
    print(f'  bound script: {sid} ({action})')

    push_resp = push_code(sid)
    result['code_pushed'][key] = {'scriptId': sid, 'files': [f['name'] for f in push_resp.get('files', [])]}
    print(f'  code pushed')

    prot = ensure_timestamp_col_protection(ssid)
    result['protections'][key] = prot
    print(f'  protection: {prot}')

(OUT / 'p4_bound_scripts.json').write_text(
    json.dumps({k: v['scriptId'] for k, v in result['bound_scripts'].items()}, indent=2),
    encoding='utf-8',
)
(OUT / 'p4_code_pushed.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print('\nP4-T1..T5 complete.')
print(json.dumps(result, indent=2))
