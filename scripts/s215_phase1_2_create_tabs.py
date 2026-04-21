"""S215 Phase 1 + 2 — create new tabs on Sheets A/B/C/D.

P1-T1: Sheet C `10_Full_Materials_Master` (11 cols)
P2-T1: Sheet C `11_Full_PO_Lines` (16 cols — adds Ship To join col)
P2-T3: Sheet A `PO_Lines_3MD_Only`, Sheet B `PO_Lines_Pinnacle_Only`, Sheet D `PO_Lines_Shaw_Only`
P1-T3 + P2-T4: add protected ranges (warning-level, editor=sam@bebang.ph)

Idempotent — safe to re-run.
"""
import json
import pathlib
import sys
sys.stdout.reconfigure(encoding='utf-8')

from google.oauth2 import service_account
from googleapiclient.discovery import build

SA = r'F:\Dropbox\Projects\BEI-ERP\credentials\task-manager-service.json'
OUT = pathlib.Path(r'F:\Dropbox\Projects\BEI-ERP-s215\output\s215')
OUT.mkdir(parents=True, exist_ok=True)

SHEET_A = '1dambmiLzSMWOQun7MCymK4nHpuqrarFCAOK0G9-6oIU'
SHEET_B = '10fqnvF_uDl5ky3MkvXUmWvZ1fYat_p6XFGmVFc3vqrw'
SHEET_C = '1_Ir5O5AW7hOjcvCTXsP06cF3sai9hcefDFrBOTRHOh0'
SHEET_D = '1mbJiLW9M9e-AmrXSRRTtbRP-xKI16ah5rakOt6qv2As'

creds = service_account.Credentials.from_service_account_file(
    SA, scopes=['https://www.googleapis.com/auth/spreadsheets']
).with_subject('sam@bebang.ph')
sheets = build('sheets', 'v4', credentials=creds, cache_discovery=False).spreadsheets()

MATERIALS_HEADER = [
    'Timestamp', 'Item Code', 'Item Name', 'UOM',
    'Unit Price (Vat Inc)', 'Unit Price (Vat ex)', 'VAT', 'REMARKS',
    'Category', 'Packaging size', 'Added By',
]
PO_LINES_HEADER = [
    'Timestamp', 'PR No', 'PO No', 'Uniqueid', 'Item No',
    'Item Code', 'Item Name', 'Packaging size', 'Qty', 'UOM',
    'Unit Cost', 'VAT', 'Amount', 'Delivery Schedule', 'Added By', 'Ship To',
]


def get_tab_map(ssid):
    meta = sheets.get(spreadsheetId=ssid).execute()
    return {s['properties']['title']: s['properties']['sheetId'] for s in meta['sheets']}


def ensure_tab(ssid, tab_name, header):
    tabs = get_tab_map(ssid)
    if tab_name in tabs:
        # verify header row matches — if not, rewrite it
        cur_header = sheets.values().get(
            spreadsheetId=ssid,
            range=f'{tab_name}!A1:{chr(ord("A") + len(header) - 1)}1'
        ).execute().get('values', [[]])
        if cur_header and cur_header[0] == header:
            return tabs[tab_name], 'existed'
        # rewrite header only
        sheets.values().update(
            spreadsheetId=ssid,
            range=f'{tab_name}!A1',
            valueInputOption='RAW',
            body={'values': [header]}
        ).execute()
        return tabs[tab_name], 'existed_header_fixed'

    # Create the tab + write the header
    resp = sheets.batchUpdate(spreadsheetId=ssid, body={
        'requests': [{
            'addSheet': {
                'properties': {
                    'title': tab_name,
                    'gridProperties': {'rowCount': 2000, 'columnCount': len(header) + 4},
                }
            }
        }]
    }).execute()
    new_id = resp['replies'][0]['addSheet']['properties']['sheetId']
    # Write header row
    sheets.values().update(
        spreadsheetId=ssid,
        range=f'{tab_name}!A1',
        valueInputOption='RAW',
        body={'values': [header]}
    ).execute()
    # Freeze header row + bold formatting
    sheets.batchUpdate(spreadsheetId=ssid, body={
        'requests': [
            {'updateSheetProperties': {
                'properties': {'sheetId': new_id, 'gridProperties': {'frozenRowCount': 1}},
                'fields': 'gridProperties.frozenRowCount'
            }},
            {'repeatCell': {
                'range': {'sheetId': new_id, 'startRowIndex': 0, 'endRowIndex': 1},
                'cell': {'userEnteredFormat': {
                    'backgroundColor': {'red': 0.02, 'green': 0.27, 'blue': 0.04},  # BEI green
                    'textFormat': {'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}, 'bold': True},
                }},
                'fields': 'userEnteredFormat(backgroundColor,textFormat)'
            }}
        ]
    }).execute()
    return new_id, 'created'


def ensure_protection(ssid, tab_name, description, editors_emails):
    """Idempotent — only adds protection if not already present for the tab."""
    meta = sheets.get(spreadsheetId=ssid, includeGridData=False).execute()
    # Find tab id
    tab_id = None
    for s in meta['sheets']:
        if s['properties']['title'] == tab_name:
            tab_id = s['properties']['sheetId']
            break
    if tab_id is None:
        return {'action': 'no_such_tab', 'tab': tab_name}

    # Check existing protections — if one already covers this tab with our description, skip
    protections = []
    for s in meta['sheets']:
        for p in s.get('protectedRanges', []):
            if p.get('range', {}).get('sheetId') == tab_id and p.get('description') == description:
                protections.append(p)
    if protections:
        return {'action': 'already_protected', 'tab': tab_name, 'protectionId': protections[0].get('protectedRangeId')}

    resp = sheets.batchUpdate(spreadsheetId=ssid, body={
        'requests': [{
            'addProtectedRange': {
                'protectedRange': {
                    'range': {'sheetId': tab_id},
                    'description': description,
                    'warningOnly': False,
                    'editors': {'users': editors_emails, 'domainUsersCanEdit': False},
                }
            }
        }]
    }).execute()
    pid = resp['replies'][0]['addProtectedRange']['protectedRange']['protectedRangeId']
    return {'action': 'added', 'tab': tab_name, 'protectionId': pid}


log = {
    'tabs_ensured': [],
    'protections': [],
}

# P1-T1: Sheet C 10_Full_Materials_Master
tab_id, action = ensure_tab(SHEET_C, '10_Full_Materials_Master', MATERIALS_HEADER)
log['tabs_ensured'].append({'sheet': 'C', 'tab': '10_Full_Materials_Master', 'sheetId': tab_id, 'action': action})
log['protections'].append(ensure_protection(
    SHEET_C, '10_Full_Materials_Master',
    'S215: script-maintained — manual edits overwritten on next refresh',
    ['sam@bebang.ph'],
))

# P2-T1: Sheet C 11_Full_PO_Lines
tab_id, action = ensure_tab(SHEET_C, '11_Full_PO_Lines', PO_LINES_HEADER)
log['tabs_ensured'].append({'sheet': 'C', 'tab': '11_Full_PO_Lines', 'sheetId': tab_id, 'action': action})
log['protections'].append(ensure_protection(
    SHEET_C, '11_Full_PO_Lines',
    'S215: script-maintained — manual edits overwritten on next refresh',
    ['sam@bebang.ph'],
))

# P2-T3: per-3PL filtered tabs
for (ssid, tab_name, sheet_label) in [
    (SHEET_A, 'PO_Lines_3MD_Only', 'A'),
    (SHEET_B, 'PO_Lines_Pinnacle_Only', 'B'),
    (SHEET_D, 'PO_Lines_Shaw_Only', 'D'),
]:
    tab_id, action = ensure_tab(ssid, tab_name, PO_LINES_HEADER)
    log['tabs_ensured'].append({'sheet': sheet_label, 'tab': tab_name, 'sheetId': tab_id, 'action': action})
    log['protections'].append(ensure_protection(
        ssid, tab_name,
        'S215: script-maintained — manual edits overwritten on next refresh',
        ['sam@bebang.ph'],
    ))

(OUT / 'p1_p2_tabs_created.json').write_text(json.dumps(log, indent=2), encoding='utf-8')
print(json.dumps(log, indent=2))
print('\nDone. Tabs + protections ensured.')
