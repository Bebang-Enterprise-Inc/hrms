"""S210 Phase 1: create Sheet A (3MD) + Sheet B (Pinnacle) with standardized schema."""
import json, os, sys, pathlib
sys.stdout.reconfigure(encoding='utf-8')
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

ROOT = pathlib.Path(r'F:\Dropbox\Projects\BEI-ERP')
SERVICE_ACCOUNT = ROOT / 'credentials/task-manager-service.json'
OWNER_EMAIL = 'commissary.team@bebang.ph'
BEI_EDITORS = ['ian@bebang.ph', 'cayla@bebang.ph', 'sam@bebang.ph', 'jay@bebang.ph', 'luwi@bebang.ph']

RECEIPTS_HEADERS = [
    'Timestamp', '3PL', 'RR Number', 'PO Number', 'Supplier', 'Material Code',
    'Material Description', 'Qty Received', 'UoM', 'SI Number', 'SI Photo',
    'Delivery Photo', "Trucker's Name", 'Plate Number', 'Production Date',
    'Expiration Date', 'Received By', 'Notes',
]

OPEN_POS_HEADERS = ['PO Number', 'Supplier Code', 'Supplier Name', 'Destination 3PL', 'Total Amount', 'Balance', 'PO Date', 'Delivery Needed By']
SUPPLIERS_VISIBLE_HEADERS = ['Supplier Code', 'Supplier Name', 'TIN', 'Contact Person', 'Contact No']
MATERIALS_HEADERS = ['Item Code', 'Item Name', 'UoM', 'Category']
INSTRUCTIONS_LINES = [
    'BEI Receiving Log — How to use (1-minute read)',
    '',
    '1. Each time a supplier delivers goods, open this sheet on your phone or laptop.',
    '2. Click the "Receipts" tab at the bottom.',
    '3. Scroll to the first empty row and click the row number to insert a row.',
    '4. Column D (PO Number): click and pick from the dropdown. Only open POs routed to your warehouse will show.',
    '5. Column E (Supplier): pick from the dropdown. Must match the supplier on the PO.',
    '6. Column F (Material Code): pick from the dropdown. Only items on the selected PO will show.',
    '7. Column G (Material Description): auto-fills — do not edit.',
    '8. Column H (Qty Received): type the actual quantity that arrived.',
    '9. Column I (UoM): auto-fills from the item master — do not edit.',
    '10. Column J (SI Number): type the supplier SI number exactly as written on their paper invoice.',
    '11. Column K (SI Photo): upload a clear photo of the paper SI (use your phone camera; Insert → Image → Upload).',
    '12. Column L (Delivery Photo): optional but recommended for cold chain.',
    '13. Columns M-P: optional — trucker name, plate, production/expiration dates if available.',
    '14. Column Q (Received By): auto-fills with your email.',
    '15. Column R (Notes): any issues or remarks.',
    '',
    'Common issues:',
    '- If the PO you expect is not in the dropdown, contact Ian (ian@bebang.ph) — it may be closed or not routed to this warehouse.',
    '- If the supplier on the paper SI does not match the PO, contact procurement — do NOT submit a mismatched receipt.',
    '- If quantity exceeds the PO balance, do NOT submit — contact procurement first.',
    '',
    'Questions: Ian Dionisio (ian@bebang.ph) or Jay Sumagui (jay@bebang.ph).',
]

def creds(scopes, subject=OWNER_EMAIL):
    return service_account.Credentials.from_service_account_file(
        str(SERVICE_ACCOUNT), scopes=scopes).with_subject(subject)

def create_sheet(sheets_api, drive_api, title, tabs_spec, protect_tabs, external_editor, bei_editors):
    # Step 1: Create via Sheets API
    body = {
        'properties': {'title': title, 'locale': 'en_US', 'timeZone': 'Asia/Manila'},
        'sheets': [{'properties': {'title': t['name']}} for t in tabs_spec],
    }
    created = sheets_api.spreadsheets().create(body=body).execute()
    sheet_id = created['spreadsheetId']
    print(f'  Created: {title}  id={sheet_id}')

    # Step 2: Write headers + seed rows per tab
    data_updates = []
    for t in tabs_spec:
        data_updates.append({
            'range': f"'{t['name']}'!A1:{chr(ord('A')+len(t['headers'])-1)}1",
            'values': [t['headers']],
        })
        if t.get('extra_rows'):
            # Write extra rows starting at row 2
            last_col = chr(ord('A') + len(t['headers']) - 1)
            for i, row in enumerate(t['extra_rows']):
                data_updates.append({
                    'range': f"'{t['name']}'!A{i+2}:{last_col}{i+2}",
                    'values': [row],
                })
        if t.get('freeze_first_row'):
            pass  # handled via batchUpdate below
    sheets_api.spreadsheets().values().batchUpdate(
        spreadsheetId=sheet_id,
        body={'valueInputOption': 'USER_ENTERED', 'data': data_updates},
    ).execute()

    # Step 3: batchUpdate for formatting (freeze, bold headers, column widths, protected ranges)
    requests = []
    sheet_name_to_id = {s['properties']['title']: s['properties']['sheetId'] for s in sheets_api.spreadsheets().get(spreadsheetId=sheet_id).execute()['sheets']}

    for t in tabs_spec:
        tab_id = sheet_name_to_id[t['name']]
        # Freeze row 1
        requests.append({
            'updateSheetProperties': {
                'properties': {'sheetId': tab_id, 'gridProperties': {'frozenRowCount': 1}},
                'fields': 'gridProperties.frozenRowCount',
            }
        })
        # Bold headers
        requests.append({
            'repeatCell': {
                'range': {'sheetId': tab_id, 'startRowIndex': 0, 'endRowIndex': 1},
                'cell': {'userEnteredFormat': {'textFormat': {'bold': True}, 'backgroundColor': {'red': 0.9, 'green': 0.93, 'blue': 1.0}}},
                'fields': 'userEnteredFormat(textFormat,backgroundColor)',
            }
        })

    # Protected ranges: lock non-Receipts tabs for external editor (Receipts stays open)
    for tab_name in protect_tabs:
        if tab_name in sheet_name_to_id:
            requests.append({
                'addProtectedRange': {
                    'protectedRange': {
                        'range': {'sheetId': sheet_name_to_id[tab_name]},
                        'description': f'BEI-locked: {tab_name} (managed by BEI staff only)',
                        'warningOnly': False,
                        'editors': {'users': bei_editors},  # External editor NOT in this list
                    }
                }
            })

    sheets_api.spreadsheets().batchUpdate(
        spreadsheetId=sheet_id,
        body={'requests': requests},
    ).execute()

    # Step 4: Share with editors (external + BEI)
    all_editors = bei_editors + ([external_editor] if external_editor else [])
    for email in all_editors:
        try:
            drive_api.files().create(  # Wait - wrong method
                body={}
            )
        except Exception:
            pass
    # Correct: use permissions().create
    for email in all_editors:
        try:
            drive_api.permissions().create(
                fileId=sheet_id,
                body={'type': 'user', 'role': 'writer', 'emailAddress': email},
                sendNotificationEmail=False,
                supportsAllDrives=True,
            ).execute()
            print(f'    Granted editor: {email}')
        except HttpError as e:
            print(f'    WARN grant failed for {email}: {str(e)[:100]}')

    return sheet_id


def main():
    sheets_creds = creds(['https://www.googleapis.com/auth/spreadsheets'])
    drive_creds = creds(['https://www.googleapis.com/auth/drive'])
    sheets_api = build('sheets', 'v4', credentials=sheets_creds, cache_discovery=False)
    drive_api = build('drive', 'v3', credentials=drive_creds, cache_discovery=False)

    tabs_spec_template = lambda three_pl_name, open_pos_tab: [
        {'name': 'Receipts', 'headers': RECEIPTS_HEADERS},
        {'name': open_pos_tab, 'headers': OPEN_POS_HEADERS},
        {'name': 'Suppliers_Visible', 'headers': SUPPLIERS_VISIBLE_HEADERS},
        {'name': 'Materials', 'headers': MATERIALS_HEADERS},
        {'name': '_Instructions', 'headers': ['Instructions'], 'extra_rows': [[line] for line in INSTRUCTIONS_LINES]},
    ]

    results = {}

    # Sheet A - 3MD
    title_a = 'BEI 3MD Receiving Log 2026'
    protect_tabs_a = ['Open_POs_3MD_Only', 'Suppliers_Visible', 'Materials', '_Instructions']
    external_editor_a = None  # Will be added later when Ian provides Martin's email
    sheet_a_id = create_sheet(
        sheets_api, drive_api,
        title_a,
        tabs_spec_template('3MD', 'Open_POs_3MD_Only'),
        protect_tabs_a,
        external_editor_a,
        BEI_EDITORS,
    )
    results['sheet_a_id'] = sheet_a_id

    # Sheet B - Pinnacle
    title_b = 'BEI Pinnacle Receiving Log 2026'
    protect_tabs_b = ['Open_POs_Pinnacle_Only', 'Suppliers_Visible', 'Materials', '_Instructions']
    external_editor_b = None  # Will be added by Jay
    sheet_b_id = create_sheet(
        sheets_api, drive_api,
        title_b,
        tabs_spec_template('Pinnacle', 'Open_POs_Pinnacle_Only'),
        protect_tabs_b,
        external_editor_b,
        BEI_EDITORS,
    )
    results['sheet_b_id'] = sheet_b_id

    # Save sheet IDs
    sheet_ids_path = ROOT / 'output/s210/SHEET_IDS.json'
    existing = {}
    if sheet_ids_path.exists():
        existing = json.loads(sheet_ids_path.read_text())
    existing.update(results)
    existing['owner'] = OWNER_EMAIL
    existing['bei_editors'] = BEI_EDITORS
    existing['external_editor_3md_pending'] = True
    existing['external_editor_pinnacle_pending'] = True
    sheet_ids_path.write_text(json.dumps(existing, indent=2))

    print('\n=== SHEET IDS ===')
    print(json.dumps(existing, indent=2))


if __name__ == '__main__':
    main()
