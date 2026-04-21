"""Push the canonical instruction text from guides/SHEET_INSTRUCTIONS_3PL.md
into the `_Instructions` tab of Sheet A (3MD) and Sheet B (Pinnacle).

Replaces _3PL_NAME_ placeholder with "3MD" for Sheet A and "Pinnacle" for
Sheet B. Writes to column A starting row 2 (header row 1 preserved).

Run:
    python output/s210/push_instructions_tab.py
"""
import json, pathlib, re, sys
sys.stdout.reconfigure(encoding='utf-8')
from google.oauth2 import service_account
from googleapiclient.discovery import build

ROOT = pathlib.Path(__file__).resolve().parents[2]
SA = pathlib.Path(r'F:\Dropbox\Projects\BEI-ERP\credentials\task-manager-service.json')
SHEET_IDS_PATH = ROOT / 'output/s210/SHEET_IDS.json'
GUIDE_PATH = ROOT / 'output/s210/guides/SHEET_INSTRUCTIONS_3PL.md'

ids = json.loads(SHEET_IDS_PATH.read_text())
guide = GUIDE_PATH.read_text(encoding='utf-8')

# Extract the canonical fenced block
m = re.search(r'```\n(BEI _3PL_NAME_ Receiving Log 2026.*?)\n```', guide,
              flags=re.DOTALL)
if not m:
    print('FAILED: could not find canonical block in SHEET_INSTRUCTIONS_3PL.md')
    sys.exit(1)
canonical = m.group(1)
lines = canonical.split('\n')
print(f'  Extracted {len(lines)} instruction lines')

creds = service_account.Credentials.from_service_account_file(
    str(SA), scopes=['https://www.googleapis.com/auth/spreadsheets']
).with_subject('commissary.team@bebang.ph')
api = build('sheets', 'v4', credentials=creds, cache_discovery=False)


def push(sheet_id, three_pl_label):
    values = [[line.replace('_3PL_NAME_', three_pl_label)] for line in lines]
    # Clear existing rows 2 onwards
    api.spreadsheets().values().clear(
        spreadsheetId=sheet_id,
        range="'_Instructions'!A2:A",
    ).execute()
    # Write new instructions
    api.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=f"'_Instructions'!A2:A{len(values) + 1}",
        valueInputOption='RAW',
        body={'values': values},
    ).execute()
    print(f'  [{three_pl_label}] pushed {len(values)} lines to {sheet_id}')


print('\n=== Push instruction tab updates ===')
print('\n[1/2] Sheet A (3MD)')
push(ids['sheet_a_id'], '3MD')
print('\n[2/2] Sheet B (Pinnacle)')
push(ids['sheet_b_id'], 'Pinnacle')

print('\nDone. Open each sheet and click _Instructions tab to verify.')
