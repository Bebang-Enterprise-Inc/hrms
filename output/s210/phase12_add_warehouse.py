"""S210 Phase 12: add Warehouse dropdown to Supplier SI Upload form.

Ian's request (2026-04-21): suppliers often deliver to multiple BEI
warehouses. Asking them which warehouse they delivered to makes it easier
to chase the right 3PL when an SI goes orphan or a DR is missing.

Changes:
  1. Add "Warehouse" radio question to the Google Form, inserted between
     Supplier Name (item 0) and PO Number (item 1). Options: 3MD, Pinnacle,
     Shaw BLVD. Required.
  2. Widen Sheet C `03_Supplier_SI_Uploads` from 11 to 12 cols — insert
     "Warehouse" column after Supplier Name (column C).
  3. Widen Sheet C `04_Match_Queue` from 11 to 12 cols — insert "Warehouse"
     column after Supplier (column D).
  4. Update SI_UPLOAD_FORM_ID.json with the new item ID.

Does NOT touch:
  - Sheet A/B/D Receipts tabs — 3PL already types their own warehouse in
    the "3PL" column. This is the SUPPLIER side.
  - SUPPLIER_URLS.csv — Warehouse is NOT pre-filled because suppliers vary
    per delivery.

Run:
    python output/s210/phase12_add_warehouse.py
"""
import json, pathlib, sys
sys.stdout.reconfigure(encoding='utf-8')
from google.oauth2 import service_account
from googleapiclient.discovery import build

ROOT = pathlib.Path(__file__).resolve().parents[2]
SA = pathlib.Path(r'F:\Dropbox\Projects\BEI-ERP\credentials\task-manager-service.json')

SHEET_IDS_PATH = ROOT / 'output/s210/SHEET_IDS.json'
FORM_ID_PATH = ROOT / 'output/s210/SI_UPLOAD_FORM_ID.json'

WAREHOUSE_OPTIONS = ['3MD', 'Pinnacle', 'Shaw BLVD']


def creds_dwd(scopes, subject='sam@bebang.ph'):
    return service_account.Credentials.from_service_account_file(
        str(SA), scopes=scopes).with_subject(subject)


def add_warehouse_to_form(ids):
    print('[1/4] Add Warehouse radio question to Form')
    api = build('forms', 'v1',
                credentials=creds_dwd(['https://www.googleapis.com/auth/forms.body']),
                cache_discovery=False)

    form_id = ids['si_upload_form_id']

    # Insert at position 1 (between Supplier Name and PO Number)
    request = {
        'requests': [{
            'createItem': {
                'item': {
                    'title': 'Warehouse',
                    'description': 'Which BEI warehouse did you deliver to? '
                                   'Pick one — required.',
                    'questionItem': {
                        'question': {
                            'required': True,
                            'choiceQuestion': {
                                'type': 'RADIO',
                                'options': [{'value': w} for w in WAREHOUSE_OPTIONS],
                                'shuffle': False,
                            },
                        }
                    },
                },
                'location': {'index': 1},
            }
        }]
    }
    api.forms().batchUpdate(formId=form_id, body=request).execute()

    # Read back to capture the question ID
    form = api.forms().get(formId=form_id).execute()
    warehouse_item = None
    for item in form.get('items', []):
        if item.get('title') == 'Warehouse':
            warehouse_item = item
            break
    if not warehouse_item:
        print('  WARN: could not find Warehouse item after creation')
        return None

    qid = warehouse_item['questionItem']['question']['questionId']
    print(f'  Warehouse item created, questionId={qid}')
    return qid


def widen_sheet_c_tabs(ids):
    print('\n[2/4] Widen Sheet C 03_Supplier_SI_Uploads + 04_Match_Queue')
    api = build('sheets', 'v4',
                credentials=creds_dwd(
                    ['https://www.googleapis.com/auth/spreadsheets'],
                    subject='commissary.team@bebang.ph'),
                cache_discovery=False)

    sheet_c_id = ids['sheet_c_id']

    # --- 03_Supplier_SI_Uploads: insert "Warehouse" after Supplier Name (col C) ---
    new_uploads_header = [
        'Timestamp', 'Supplier Name', 'Warehouse', 'PO Number', 'SI Number',
        'SI Date', 'Amount', 'SI PDF Link', 'Notes', 'Match_Status',
        'Matched_RR_Number', 'Match_Timestamp',
    ]
    # Read existing data
    resp = api.spreadsheets().values().get(
        spreadsheetId=sheet_c_id,
        range="'03_Supplier_SI_Uploads'!A1:K",
    ).execute()
    existing = resp.get('values', [])
    migrated = [new_uploads_header]
    if len(existing) > 1:
        # Shift existing rows: insert '' at new Warehouse position (index 2)
        for row in existing[1:]:
            new_row = list(row)
            # Pad to length 11 if shorter
            while len(new_row) < 11:
                new_row.append('')
            # Insert empty Warehouse at position 2
            shifted = new_row[:2] + [''] + new_row[2:]
            migrated.append(shifted)

    # Clear + rewrite
    api.spreadsheets().values().clear(
        spreadsheetId=sheet_c_id,
        range="'03_Supplier_SI_Uploads'!A1:L",
    ).execute()
    api.spreadsheets().values().update(
        spreadsheetId=sheet_c_id,
        range=f"'03_Supplier_SI_Uploads'!A1:L{len(migrated)}",
        valueInputOption='USER_ENTERED',
        body={'values': migrated},
    ).execute()
    print(f'  03_Supplier_SI_Uploads: {len(migrated) - 1} data rows migrated to 12 cols')

    # --- 04_Match_Queue: insert "Warehouse" after Supplier (col D) ---
    new_mq_header = [
        'Timestamp', 'Reason', 'Supplier', 'Warehouse', 'PO Number',
        'SI Number', 'SI Date', 'Amount', 'SI PDF Link', 'Assigned To',
        'Status', 'Resolution',
    ]
    resp = api.spreadsheets().values().get(
        spreadsheetId=sheet_c_id,
        range="'04_Match_Queue'!A1:K",
    ).execute()
    existing = resp.get('values', [])
    migrated = [new_mq_header]
    if len(existing) > 1:
        for row in existing[1:]:
            new_row = list(row)
            while len(new_row) < 11:
                new_row.append('')
            # Insert empty Warehouse at position 3 (after Supplier)
            shifted = new_row[:3] + [''] + new_row[3:]
            migrated.append(shifted)

    api.spreadsheets().values().clear(
        spreadsheetId=sheet_c_id,
        range="'04_Match_Queue'!A1:L",
    ).execute()
    api.spreadsheets().values().update(
        spreadsheetId=sheet_c_id,
        range=f"'04_Match_Queue'!A1:L{len(migrated)}",
        valueInputOption='USER_ENTERED',
        body={'values': migrated},
    ).execute()
    print(f'  04_Match_Queue: {len(migrated) - 1} data rows migrated to 12 cols')

    # Re-bold headers on both
    meta = api.spreadsheets().get(spreadsheetId=sheet_c_id).execute()
    name_to_id = {s['properties']['title']: s['properties']['sheetId']
                  for s in meta['sheets']}
    format_requests = []
    for tab in ('03_Supplier_SI_Uploads', '04_Match_Queue'):
        tid = name_to_id[tab]
        format_requests.append({
            'repeatCell': {
                'range': {'sheetId': tid, 'startRowIndex': 0, 'endRowIndex': 1},
                'cell': {'userEnteredFormat': {
                    'textFormat': {'bold': True},
                    'backgroundColor': {'red': 0.9, 'green': 0.93, 'blue': 1.0},
                }},
                'fields': 'userEnteredFormat(textFormat,backgroundColor)',
            }
        })
    api.spreadsheets().batchUpdate(
        spreadsheetId=sheet_c_id, body={'requests': format_requests},
    ).execute()


def update_form_metadata(ids, warehouse_qid):
    print('\n[3/4] Update SI_UPLOAD_FORM_ID.json')
    meta = json.loads(FORM_ID_PATH.read_text())
    meta['item_ids']['Warehouse'] = warehouse_qid
    FORM_ID_PATH.write_text(json.dumps(meta, indent=2), encoding='utf-8')
    print(f'  Added Warehouse item_id={warehouse_qid} to SI_UPLOAD_FORM_ID.json')


def print_summary(warehouse_qid):
    print('\n[4/4] Summary')
    print('  Form now asks supplier which warehouse they delivered to.')
    print('  Sheet C 03_Supplier_SI_Uploads + 04_Match_Queue now have Warehouse column.')
    print('  .gs handler will be updated + redeployed in next step (phase12_redeploy).')
    print(f'  New question ID: {warehouse_qid}')


def main():
    print('=== S210 Phase 12: Add Warehouse field ===\n')
    ids = json.loads(SHEET_IDS_PATH.read_text())

    warehouse_qid = add_warehouse_to_form(ids)
    if not warehouse_qid:
        print('Aborting — Warehouse item creation failed')
        sys.exit(1)

    widen_sheet_c_tabs(ids)
    update_form_metadata(ids, warehouse_qid)
    print_summary(warehouse_qid)


if __name__ == '__main__':
    main()
