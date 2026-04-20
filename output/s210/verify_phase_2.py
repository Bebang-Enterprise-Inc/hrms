"""S210 Phase 2 verifier. Exit 0 = PASS.

Checks per plan task 2.7 (with reasonable extension):
- SHEET_IDS.json contains sheet_c_id and sheet_d_id
- Sheet C has exactly 9 tabs with expected names
- Sheet C 01_Dashboard row 3 column B is a formula (starts with '=')
- Sheet C 07_Full_Suppliers_Master has > 50 rows (excluding header)
- Sheet C 08_Full_Open_POs has rows (excluding header)
- Sheet C external access = False (no non-BEI editors)
- Sheet D has 18-col Receipts tab
- Sheet D external access = False
"""
import json, sys, pathlib
sys.stdout.reconfigure(encoding='utf-8')
from google.oauth2 import service_account
from googleapiclient.discovery import build

ROOT = pathlib.Path(r'F:\Dropbox\Projects\BEI-ERP-s210')
SERVICE_ACCOUNT = pathlib.Path(r'F:\Dropbox\Projects\BEI-ERP\credentials\task-manager-service.json')
OWNER_EMAIL = 'commissary.team@bebang.ph'

EXPECTED_SHEET_C_TABS = [
    '01_Dashboard', '02_All_Receipts_Consolidated', '03_Supplier_SI_Uploads',
    '04_Match_Queue', '05_Variance_Queue', '06_Pending_GR',
    '07_Full_Suppliers_Master', '08_Full_Open_POs', '09_Audit_Log',
]


def creds(scopes):
    return service_account.Credentials.from_service_account_file(
        str(SERVICE_ACCOUNT), scopes=scopes).with_subject(OWNER_EMAIL)


def main():
    failures = []
    sheet_ids_path = ROOT / 'output/s210/SHEET_IDS.json'
    if not sheet_ids_path.exists():
        print('[FAIL] SHEET_IDS.json missing')
        sys.exit(1)

    ids = json.loads(sheet_ids_path.read_text())
    for key in ('sheet_c_id', 'sheet_d_id'):
        if key not in ids or not ids[key]:
            failures.append(f'SHEET_IDS.json missing {key}')
    if failures:
        for f in failures:
            print(f'[FAIL] {f}')
        sys.exit(1)

    sheet_c_id = ids['sheet_c_id']
    sheet_d_id = ids['sheet_d_id']

    sheets_creds = creds(['https://www.googleapis.com/auth/spreadsheets.readonly'])
    drive_creds = creds(['https://www.googleapis.com/auth/drive.readonly'])
    sheets_api = build('sheets', 'v4', credentials=sheets_creds, cache_discovery=False)
    drive_api = build('drive', 'v3', credentials=drive_creds, cache_discovery=False)

    # ---- Sheet C tabs ----
    meta_c = sheets_api.spreadsheets().get(spreadsheetId=sheet_c_id).execute()
    tab_names_c = [s['properties']['title'] for s in meta_c['sheets']]
    if sorted(tab_names_c) != sorted(EXPECTED_SHEET_C_TABS):
        failures.append(f'Sheet C tabs mismatch. got={tab_names_c} expected={EXPECTED_SHEET_C_TABS}')

    # ---- Sheet C dashboard formula ----
    # Row 3 is labeled "Today's receipts — 3MD", formula in B3
    dash = sheets_api.spreadsheets().values().get(
        spreadsheetId=sheet_c_id,
        range="'01_Dashboard'!B3:B10",
        valueRenderOption='FORMULA',
    ).execute()
    dash_vals = [row[0] if row else '' for row in dash.get('values', [])]
    formulas_found = sum(1 for v in dash_vals if isinstance(v, str) and v.startswith('='))
    if formulas_found < 6:
        failures.append(f'Sheet C Dashboard B3:B10 has only {formulas_found} formulas (need >=6)')

    # ---- Sheet C suppliers master row count ----
    sup = sheets_api.spreadsheets().values().get(
        spreadsheetId=sheet_c_id,
        range="'07_Full_Suppliers_Master'!A2:A",
    ).execute()
    sup_rows = len(sup.get('values', []))
    if sup_rows <= 50:
        failures.append(f'Sheet C 07_Full_Suppliers_Master has {sup_rows} rows (need >50)')

    # ---- Sheet C open POs row count ----
    pos = sheets_api.spreadsheets().values().get(
        spreadsheetId=sheet_c_id,
        range="'08_Full_Open_POs'!A2:A",
    ).execute()
    pos_rows = len(pos.get('values', []))
    if pos_rows < 1:
        failures.append(f'Sheet C 08_Full_Open_POs has {pos_rows} rows (need >=1)')

    # ---- Sheet C permissions: no non-BEI editors ----
    perms_c = drive_api.permissions().list(
        fileId=sheet_c_id,
        fields='permissions(emailAddress,role,type)',
        supportsAllDrives=True,
    ).execute()
    non_bei_c = [p for p in perms_c.get('permissions', [])
                 if p.get('emailAddress') and not p['emailAddress'].endswith('@bebang.ph')]
    if non_bei_c:
        failures.append(f'Sheet C has non-@bebang.ph editors: {[p["emailAddress"] for p in non_bei_c]}')

    # ---- Sheet D ----
    meta_d = sheets_api.spreadsheets().get(spreadsheetId=sheet_d_id).execute()
    tab_names_d = [s['properties']['title'] for s in meta_d['sheets']]
    if 'Receipts' not in tab_names_d:
        failures.append(f'Sheet D missing Receipts tab. got={tab_names_d}')

    # Sheet D 18-col header
    hdr_d = sheets_api.spreadsheets().values().get(
        spreadsheetId=sheet_d_id,
        range="'Receipts'!A1:R1",
    ).execute()
    hdr_d_vals = hdr_d.get('values', [[]])[0]
    if len(hdr_d_vals) < 18:
        failures.append(f'Sheet D Receipts has {len(hdr_d_vals)} cols (need >=18)')

    # Sheet D no non-BEI
    perms_d = drive_api.permissions().list(
        fileId=sheet_d_id,
        fields='permissions(emailAddress,role,type)',
        supportsAllDrives=True,
    ).execute()
    non_bei_d = [p for p in perms_d.get('permissions', [])
                 if p.get('emailAddress') and not p['emailAddress'].endswith('@bebang.ph')]
    if non_bei_d:
        failures.append(f'Sheet D has non-@bebang.ph editors: {[p["emailAddress"] for p in non_bei_d]}')

    # ---- Report ----
    print('\n=== S210 Phase 2 Verifier ===\n')
    if failures:
        for f in failures:
            print(f'[FAIL] {f}')
        print(f'\n{len(failures)} failures')
        sys.exit(1)

    print('[PASS] Sheet C tabs (9 expected)')
    print(f'[PASS] Sheet C Dashboard formulas: {formulas_found} in B3:B10')
    print(f'[PASS] Sheet C 07_Full_Suppliers_Master: {sup_rows} rows')
    print(f'[PASS] Sheet C 08_Full_Open_POs: {pos_rows} rows')
    print('[PASS] Sheet C external access: none (all @bebang.ph)')
    print(f'[PASS] Sheet D Receipts header cols: {len(hdr_d_vals)}')
    print('[PASS] Sheet D external access: none (all @bebang.ph)')
    print('\nAll checks passed.')
    sys.exit(0)


if __name__ == '__main__':
    main()
