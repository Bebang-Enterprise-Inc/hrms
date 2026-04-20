"""S210 Phase 2: create Sheet C (BEI Receiving Master) + Sheet D (Shaw Transitional).

Sheet C: BEI-internal only, 9 tabs (Dashboard, Consolidated Receipts, Supplier SI Uploads,
Match Queue, Variance Queue, Pending GR, Full Suppliers Master, Full Open POs, Audit Log).
Seeds 07_Full_Suppliers_Master + 08_Full_Open_POs from Procurement AppSheet source sheet.

Sheet D: BEI-only, same 18-col Receipts schema as Sheet A (Shaw fallback while Shaw→3MD
storage migration completes).

Run:
    python output/s210/phase2_create_sheets_cd.py
"""
import json, sys, pathlib
sys.stdout.reconfigure(encoding='utf-8')
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

ROOT = pathlib.Path(r'F:\Dropbox\Projects\BEI-ERP-s210')
# Credentials live only in the main repo (gitignored); reference the absolute path
SERVICE_ACCOUNT = pathlib.Path(r'F:\Dropbox\Projects\BEI-ERP\credentials\task-manager-service.json')
OWNER_EMAIL = 'commissary.team@bebang.ph'

# Per plan task 2.1: Sam, Ian, Cayla, Luwi, Mae, Denise, Jay — NO external
SHEET_C_EDITORS = [
    'sam@bebang.ph',
    'ian@bebang.ph',
    'cayla@bebang.ph',
    'luwi@bebang.ph',
    'mae@bebang.ph',
    'denise@bebang.ph',
    'jay@bebang.ph',
]

# Sheet D: BEI-only, same set
SHEET_D_EDITORS = SHEET_C_EDITORS

# Source: Procurement AppSheet sheet ID (read-only seed for Suppliers + Open POs)
PROCUREMENT_APPSHEET_ID = '1QWdoZlT7XWLppfVKpJ2VRXhbMkYtE5TbUwg4lMbO03Q'

# ============================================================
# Sheet C tab schemas
# ============================================================
# 01_Dashboard — KPI labels in col A, formulas in col B
DASHBOARD_ROWS = [
    ['BEI RECEIVING MASTER — DASHBOARD', ''],
    ['Last refresh', '=NOW()'],
    ["Today's receipts — 3MD", "=IFERROR(COUNTIFS('02_All_Receipts_Consolidated'!B:B,\"3MD\",'02_All_Receipts_Consolidated'!A:A,\">=\"&TEXT(TODAY(),\"yyyy-mm-dd\")),0)"],
    ["Today's receipts — Pinnacle", "=IFERROR(COUNTIFS('02_All_Receipts_Consolidated'!B:B,\"Pinnacle\",'02_All_Receipts_Consolidated'!A:A,\">=\"&TEXT(TODAY(),\"yyyy-mm-dd\")),0)"],
    ["Today's receipts — Shaw (transitional)", "=IFERROR(COUNTIFS('02_All_Receipts_Consolidated'!B:B,\"Shaw\",'02_All_Receipts_Consolidated'!A:A,\">=\"&TEXT(TODAY(),\"yyyy-mm-dd\")),0)"],
    ["SI match rate (today's receipts)", "=IFERROR(COUNTIFS('02_All_Receipts_Consolidated'!T:T,TRUE,'02_All_Receipts_Consolidated'!A:A,\">=\"&TEXT(TODAY(),\"yyyy-mm-dd\"))/MAX(1,COUNTIF('02_All_Receipts_Consolidated'!A:A,\">=\"&TEXT(TODAY(),\"yyyy-mm-dd\"))),0)"],
    ['Stale DR count (>72h, no SI match)', "=IFERROR(COUNTA('05_Variance_Queue'!A2:A),0)"],
    ['Pending GR depth', "=IFERROR(COUNTA('06_Pending_GR'!A2:A),0)"],
    ['Orphan SI count (Match Queue)', "=IFERROR(COUNTA('04_Match_Queue'!A2:A),0)"],
    ['Full Suppliers Master — rows', "=IFERROR(COUNTA('07_Full_Suppliers_Master'!A2:A),0)"],
    ['Full Open POs — rows', "=IFERROR(COUNTA('08_Full_Open_POs'!A2:A),0)"],
    ['Audit log events today', "=IFERROR(COUNTIF('09_Audit_Log'!A:A,\">=\"&TEXT(TODAY(),\"yyyy-mm-dd\")),0)"],
]

# 02_All_Receipts_Consolidated — 22 cols: 18 base + 4 SI-match metadata
CONSOLIDATED_HEADERS = [
    'Timestamp', 'Source_Sheet', '3PL', 'RR Number', 'PO Number', 'Supplier',
    'Material Code', 'Material Description', 'Qty Received', 'UoM', 'SI Number',
    'SI Photo', 'Delivery Photo', "Trucker's Name", 'Plate Number',
    'Production Date', 'Expiration Date', 'Received By', 'Notes',
    'SI_Matched',        # col T (20) — TRUE/FALSE set by handleSiUpload
    'SI_Upload_Link',    # col U (21) — Drive link once supplier uploads SI PDF
    'SI_Match_Timestamp', # col V (22) — when match happened
]
# NOTE: dashboard formulas reference col U (21st) for SI_Matched via 0-indexed? Let me recount.
# A=1 B=2 C=3 D=4 E=5 F=6 G=7 H=8 I=9 J=10 K=11 L=12 M=13 N=14 O=15 P=16 Q=17 R=18 S=19 T=20 U=21 V=22
# SI_Matched is col T (index 20), SI_Upload_Link col U (21), SI_Match_Timestamp col V (22).
# Dashboard B6 references !U:U — which is SI_Upload_Link. Should be T (SI_Matched). Fix this.

# 03_Supplier_SI_Uploads — from Google Form (filled by Phase 4)
SI_UPLOADS_HEADERS = [
    'Timestamp', 'Supplier Name', 'PO Number', 'SI Number', 'SI Date',
    'Amount', 'SI PDF Link', 'Notes', 'Match_Status', 'Matched_RR_Number',
    'Match_Timestamp',
]

# 04_Match_Queue — orphan SI uploads
MATCH_QUEUE_HEADERS = [
    'Timestamp', 'Reason', 'Supplier', 'PO Number', 'SI Number', 'SI Date',
    'Amount', 'SI PDF Link', 'Assigned To', 'Status', 'Resolution',
]

# 05_Variance_Queue — stale DRs and validation issues
VARIANCE_QUEUE_HEADERS = [
    'Timestamp', 'RR Number', 'Reason', '3PL', 'PO Number', 'Supplier',
    'Material Code', 'Qty', 'Age (hrs)', 'SI Status', 'Assigned To',
    'Status', 'Resolution',
]

# 06_Pending_GR — staging for Ashish's AppSheet to consume
PENDING_GR_HEADERS = [
    'Timestamp', 'RR Number', '3PL', 'PO Number', 'Supplier', 'Material Code',
    'Material Description', 'Qty Received', 'UoM', 'SI Number', 'SI PDF Link',
    'Status', 'Picked_Up_By_AppSheet',
]

# 07_Full_Suppliers_Master — seeded from Procurement AppSheet Suppliers tab
SUPPLIERS_MASTER_HEADERS = [
    'Supplier Code', 'Supplier Name', 'Contact No', 'Contact Person',
    'Email ID', 'Address', 'Bank Name', 'Bank Account Name',
    'Bank Account No', 'VAT Registered', 'TIN', 'EWT Rate',
    'Payment Terms', 'Tier',
]

# 08_Full_Open_POs — seeded from Procurement AppSheet
OPEN_POS_HEADERS = [
    'PO Number', 'PO Date', 'Supplier Code', 'Supplier Name',
    'Destination 3PL', 'Total Amount', 'Balance',
    'Delivery Needed By', 'Status',
]

# 09_Audit_Log — every automation action
AUDIT_LOG_HEADERS = [
    'Timestamp', 'Trigger', 'Sheet', 'Row', 'Action', 'Outcome', 'Details',
]

# Sheet D: same 18-col Receipts schema as Sheet A
SHAW_RECEIPTS_HEADERS = [
    'Timestamp', '3PL', 'RR Number', 'PO Number', 'Supplier', 'Material Code',
    'Material Description', 'Qty Received', 'UoM', 'SI Number', 'SI Photo',
    'Delivery Photo', "Trucker's Name", 'Plate Number', 'Production Date',
    'Expiration Date', 'Received By', 'Notes',
]
SHAW_INSTRUCTIONS_LINES = [
    'BEI Shaw Transitional Receiving — INTERNAL ONLY',
    '',
    'This sheet captures deliveries still routed to Shaw warehouse while the',
    'Shaw→3MD storage migration is in progress. No external 3PL has access.',
    '',
    '1. When a supplier delivers to Shaw, Bryan (or his backup) records in Receipts.',
    '2. Use the same column structure as Sheet A (3MD) — pre-filled dropdowns coming.',
    '3. When Shaw storage transfers fully to 3MD, this sheet will be archived.',
    '4. Questions: Ian Dionisio (ian@bebang.ph) or Jay Sumagui (jay@bebang.ph).',
]


def creds(scopes, subject=OWNER_EMAIL):
    return service_account.Credentials.from_service_account_file(
        str(SERVICE_ACCOUNT), scopes=scopes).with_subject(subject)


def fetch_suppliers_from_source(source_sheets_api):
    """Read Suppliers tab from Procurement AppSheet and map to master schema.

    Uses sam@bebang.ph-impersonated client because commissary.team may not have
    read access to the sam-owned Procurement AppSheet.
    """
    result = source_sheets_api.spreadsheets().values().get(
        spreadsheetId=PROCUREMENT_APPSHEET_ID,
        range="'Suppliers'!A1:AB",
    ).execute()
    rows = result.get('values', [])
    if not rows:
        return []
    headers = rows[0]

    def col(name):
        try:
            return headers.index(name)
        except ValueError:
            return None

    idx = {
        'Supplier Code': col('Supplier Code'),
        'Supplier Name': col('Supplier Name'),
        'Contact No': col('Contact No'),
        'Contact Person': col('Contact Person'),
        'Email ID': col('Email ID'),
        'Address': col('Address'),
        'Bank Name': col('Bank Name'),
        'Bank Account Name': col('Bank Account Name'),
        'Bank Account No': col('Bank Account No'),
        'VAT Registered': col('VAT Registered'),
        'TIN': col('TIN'),
        'EWT Rate': col('EWT Rate'),
        'Payment Terms': col('Payment Terms'),
        'Tier': col('Tier'),
    }

    out = []
    for row in rows[1:]:
        if not any(row):  # skip empty rows
            continue

        def safe(name):
            i = idx.get(name)
            if i is None or i >= len(row):
                return ''
            return row[i]

        # require at least a supplier name
        if not safe('Supplier Name'):
            continue
        out.append([
            safe('Supplier Code'),
            safe('Supplier Name'),
            safe('Contact No'),
            safe('Contact Person'),
            safe('Email ID'),
            safe('Address'),
            safe('Bank Name'),
            safe('Bank Account Name'),
            safe('Bank Account No'),
            safe('VAT Registered'),
            safe('TIN'),
            safe('EWT Rate'),
            safe('Payment Terms'),
            safe('Tier'),
        ])
    return out


def fetch_open_pos_from_source(source_sheets_api):
    """Read Purchase Order tab from Procurement AppSheet.

    Filter: Status indicates open (not Closed/Cancelled); Balance > 0 if available.
    Returns rows in OPEN_POS_HEADERS order.
    """
    # First, peek at the PO tab to find actual column names
    meta = source_sheets_api.spreadsheets().get(spreadsheetId=PROCUREMENT_APPSHEET_ID).execute()
    po_tab_name = None
    for sheet in meta['sheets']:
        title = sheet['properties']['title']
        if 'purchase order' in title.lower() and 'item' not in title.lower():
            po_tab_name = title
            break

    if not po_tab_name:
        print('  WARN: Purchase Order tab not found in Procurement AppSheet — skipping PO seed')
        return []

    print(f'  Reading POs from tab: {po_tab_name}')
    result = source_sheets_api.spreadsheets().values().get(
        spreadsheetId=PROCUREMENT_APPSHEET_ID,
        range=f"'{po_tab_name}'!A1:AZ",
    ).execute()
    rows = result.get('values', [])
    if not rows:
        return []
    headers = rows[0]

    def col(*candidates):
        for name in candidates:
            if name in headers:
                return headers.index(name)
        return None

    idx = {
        'PO Number': col('PO Number', 'PO No', 'PO#'),
        'PO Date': col('PO Date', 'Date', 'Timestamp'),
        'Supplier Code': col('Supplier Code'),
        'Supplier Name': col('Supplier Name', 'Supplier'),
        'Destination 3PL': col('Destination 3PL', 'Destination', 'Delivery to', 'Deliver To', 'Delivery Location'),
        'Total Amount': col('Total Amount', 'Grand Total', 'Total'),
        'Balance': col('Balance', 'Outstanding Balance'),
        'Delivery Needed By': col('Delivery Needed By', 'Delivery Date', 'Required Date', 'Date Required'),
        'Status': col('Status', 'PO Status', 'Approval'),
    }

    out = []
    for row in rows[1:]:
        if not any(row):
            continue

        def safe(name):
            i = idx.get(name)
            if i is None or i >= len(row):
                return ''
            return row[i]

        if not safe('PO Number'):
            continue

        status = str(safe('Status')).strip().lower()
        if status in ('closed', 'cancelled', 'canceled', 'rejected', 'void'):
            continue

        out.append([
            safe('PO Number'),
            safe('PO Date'),
            safe('Supplier Code'),
            safe('Supplier Name'),
            safe('Destination 3PL'),
            safe('Total Amount'),
            safe('Balance'),
            safe('Delivery Needed By'),
            safe('Status'),
        ])
    return out


def create_sheet_c(sheets_api, drive_api):
    tabs_spec = [
        {'name': '01_Dashboard', 'rows': DASHBOARD_ROWS, 'is_dashboard': True},
        {'name': '02_All_Receipts_Consolidated', 'headers': CONSOLIDATED_HEADERS},
        {'name': '03_Supplier_SI_Uploads', 'headers': SI_UPLOADS_HEADERS},
        {'name': '04_Match_Queue', 'headers': MATCH_QUEUE_HEADERS},
        {'name': '05_Variance_Queue', 'headers': VARIANCE_QUEUE_HEADERS},
        {'name': '06_Pending_GR', 'headers': PENDING_GR_HEADERS},
        {'name': '07_Full_Suppliers_Master', 'headers': SUPPLIERS_MASTER_HEADERS},
        {'name': '08_Full_Open_POs', 'headers': OPEN_POS_HEADERS},
        {'name': '09_Audit_Log', 'headers': AUDIT_LOG_HEADERS},
    ]

    # Create spreadsheet
    body = {
        'properties': {'title': 'BEI Receiving Master 2026', 'locale': 'en_US', 'timeZone': 'Asia/Manila'},
        'sheets': [{'properties': {'title': t['name']}} for t in tabs_spec],
    }
    created = sheets_api.spreadsheets().create(body=body).execute()
    sheet_id = created['spreadsheetId']
    print(f'  Created Sheet C: BEI Receiving Master 2026  id={sheet_id}')

    # Write headers / dashboard rows
    data_updates = []
    for t in tabs_spec:
        if t.get('is_dashboard'):
            # Dashboard: 2 cols × N rows
            data_updates.append({
                'range': f"'{t['name']}'!A1:B{len(t['rows'])}",
                'values': t['rows'],
            })
        else:
            last_col = chr(ord('A') + len(t['headers']) - 1)
            if len(t['headers']) > 26:
                # Handle column beyond Z (e.g., AA)
                n = len(t['headers'])
                last_col = col_letter(n)
            data_updates.append({
                'range': f"'{t['name']}'!A1:{last_col}1",
                'values': [t['headers']],
            })

    sheets_api.spreadsheets().values().batchUpdate(
        spreadsheetId=sheet_id,
        body={'valueInputOption': 'USER_ENTERED', 'data': data_updates},
    ).execute()

    # Format: freeze row 1, bold headers
    meta = sheets_api.spreadsheets().get(spreadsheetId=sheet_id).execute()
    name_to_id = {s['properties']['title']: s['properties']['sheetId'] for s in meta['sheets']}
    format_requests = []
    for t in tabs_spec:
        tid = name_to_id[t['name']]
        # Freeze row 1 on non-dashboard tabs; dashboard no freeze
        if not t.get('is_dashboard'):
            format_requests.append({
                'updateSheetProperties': {
                    'properties': {'sheetId': tid, 'gridProperties': {'frozenRowCount': 1}},
                    'fields': 'gridProperties.frozenRowCount',
                }
            })
            format_requests.append({
                'repeatCell': {
                    'range': {'sheetId': tid, 'startRowIndex': 0, 'endRowIndex': 1},
                    'cell': {'userEnteredFormat': {'textFormat': {'bold': True}, 'backgroundColor': {'red': 0.9, 'green': 0.93, 'blue': 1.0}}},
                    'fields': 'userEnteredFormat(textFormat,backgroundColor)',
                }
            })
        else:
            # Dashboard: bold title row, larger font
            format_requests.append({
                'repeatCell': {
                    'range': {'sheetId': tid, 'startRowIndex': 0, 'endRowIndex': 1, 'startColumnIndex': 0, 'endColumnIndex': 2},
                    'cell': {'userEnteredFormat': {'textFormat': {'bold': True, 'fontSize': 14}, 'backgroundColor': {'red': 0.85, 'green': 0.88, 'blue': 1.0}}},
                    'fields': 'userEnteredFormat(textFormat,backgroundColor)',
                }
            })

    sheets_api.spreadsheets().batchUpdate(
        spreadsheetId=sheet_id,
        body={'requests': format_requests},
    ).execute()

    # Share with BEI editors only (no external)
    for email in SHEET_C_EDITORS:
        try:
            drive_api.permissions().create(
                fileId=sheet_id,
                body={'type': 'user', 'role': 'writer', 'emailAddress': email},
                sendNotificationEmail=False,
                supportsAllDrives=True,
            ).execute()
            print(f'    Granted editor (Sheet C): {email}')
        except HttpError as e:
            print(f'    WARN grant failed for {email}: {str(e)[:100]}')

    return sheet_id


def col_letter(n):
    """Convert 1-indexed column number to letter(s). 1=A, 26=Z, 27=AA."""
    result = ''
    while n > 0:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result


def create_sheet_d(sheets_api, drive_api):
    tabs_spec = [
        {'name': 'Receipts', 'headers': SHAW_RECEIPTS_HEADERS},
        {'name': '_Instructions', 'headers': ['Instructions'], 'extra_rows': [[line] for line in SHAW_INSTRUCTIONS_LINES]},
    ]

    body = {
        'properties': {'title': 'BEI Shaw Transitional Receiving', 'locale': 'en_US', 'timeZone': 'Asia/Manila'},
        'sheets': [{'properties': {'title': t['name']}} for t in tabs_spec],
    }
    created = sheets_api.spreadsheets().create(body=body).execute()
    sheet_id = created['spreadsheetId']
    print(f'  Created Sheet D: BEI Shaw Transitional Receiving  id={sheet_id}')

    data_updates = []
    for t in tabs_spec:
        last_col = col_letter(len(t['headers']))
        data_updates.append({
            'range': f"'{t['name']}'!A1:{last_col}1",
            'values': [t['headers']],
        })
        if t.get('extra_rows'):
            last_col_rows = col_letter(len(t['headers']))
            for i, row in enumerate(t['extra_rows']):
                data_updates.append({
                    'range': f"'{t['name']}'!A{i+2}:{last_col_rows}{i+2}",
                    'values': [row],
                })

    sheets_api.spreadsheets().values().batchUpdate(
        spreadsheetId=sheet_id,
        body={'valueInputOption': 'USER_ENTERED', 'data': data_updates},
    ).execute()

    # Format
    meta = sheets_api.spreadsheets().get(spreadsheetId=sheet_id).execute()
    name_to_id = {s['properties']['title']: s['properties']['sheetId'] for s in meta['sheets']}
    format_requests = []
    for t in tabs_spec:
        tid = name_to_id[t['name']]
        format_requests.append({
            'updateSheetProperties': {
                'properties': {'sheetId': tid, 'gridProperties': {'frozenRowCount': 1}},
                'fields': 'gridProperties.frozenRowCount',
            }
        })
        format_requests.append({
            'repeatCell': {
                'range': {'sheetId': tid, 'startRowIndex': 0, 'endRowIndex': 1},
                'cell': {'userEnteredFormat': {'textFormat': {'bold': True}, 'backgroundColor': {'red': 0.9, 'green': 0.93, 'blue': 1.0}}},
                'fields': 'userEnteredFormat(textFormat,backgroundColor)',
            }
        })

    sheets_api.spreadsheets().batchUpdate(
        spreadsheetId=sheet_id,
        body={'requests': format_requests},
    ).execute()

    # Share with BEI-only editors
    for email in SHEET_D_EDITORS:
        try:
            drive_api.permissions().create(
                fileId=sheet_id,
                body={'type': 'user', 'role': 'writer', 'emailAddress': email},
                sendNotificationEmail=False,
                supportsAllDrives=True,
            ).execute()
            print(f'    Granted editor (Sheet D): {email}')
        except HttpError as e:
            print(f'    WARN grant failed for {email}: {str(e)[:100]}')

    return sheet_id


def seed_masters(sheets_api, source_sheets_api, sheet_c_id):
    """Pull Suppliers + Open POs from Procurement AppSheet, write into Sheet C."""
    suppliers = fetch_suppliers_from_source(source_sheets_api)
    open_pos = fetch_open_pos_from_source(source_sheets_api)
    print(f'  Seed: {len(suppliers)} suppliers, {len(open_pos)} open POs')

    data_updates = []
    if suppliers:
        last_col = col_letter(len(SUPPLIERS_MASTER_HEADERS))
        data_updates.append({
            'range': f"'07_Full_Suppliers_Master'!A2:{last_col}{len(suppliers)+1}",
            'values': suppliers,
        })
    if open_pos:
        last_col = col_letter(len(OPEN_POS_HEADERS))
        data_updates.append({
            'range': f"'08_Full_Open_POs'!A2:{last_col}{len(open_pos)+1}",
            'values': open_pos,
        })

    if data_updates:
        sheets_api.spreadsheets().values().batchUpdate(
            spreadsheetId=sheet_c_id,
            body={'valueInputOption': 'RAW', 'data': data_updates},
        ).execute()

    return len(suppliers), len(open_pos)


def main():
    # Commissary-team-impersonated clients create + own new sheets
    sheets_creds = creds(['https://www.googleapis.com/auth/spreadsheets'])
    drive_creds = creds(['https://www.googleapis.com/auth/drive'])
    sheets_api = build('sheets', 'v4', credentials=sheets_creds, cache_discovery=False)
    drive_api = build('drive', 'v3', credentials=drive_creds, cache_discovery=False)

    # Sam-impersonated client reads the Procurement AppSheet (owned by sam)
    source_sheets_creds = creds(['https://www.googleapis.com/auth/spreadsheets.readonly'], subject='sam@bebang.ph')
    source_sheets_api = build('sheets', 'v4', credentials=source_sheets_creds, cache_discovery=False)

    print('\n=== S210 Phase 2: Create Sheet C + Sheet D ===\n')

    print('[1/3] Create Sheet C — BEI Receiving Master 2026')
    sheet_c_id = create_sheet_c(sheets_api, drive_api)

    print('\n[2/3] Create Sheet D — BEI Shaw Transitional Receiving')
    sheet_d_id = create_sheet_d(sheets_api, drive_api)

    print('\n[3/3] Seed Sheet C masters from Procurement AppSheet')
    suppliers_count, pos_count = seed_masters(sheets_api, source_sheets_api, sheet_c_id)

    # Persist IDs
    sheet_ids_path = ROOT / 'output/s210/SHEET_IDS.json'
    existing = {}
    if sheet_ids_path.exists():
        existing = json.loads(sheet_ids_path.read_text())
    existing['sheet_c_id'] = sheet_c_id
    existing['sheet_d_id'] = sheet_d_id
    existing['sheet_c_editors'] = SHEET_C_EDITORS
    existing['sheet_d_editors'] = SHEET_D_EDITORS
    existing['sheet_c_external_access'] = False
    existing['sheet_d_external_access'] = False
    existing['seed_suppliers_count'] = suppliers_count
    existing['seed_open_pos_count'] = pos_count
    sheet_ids_path.write_text(json.dumps(existing, indent=2))

    print('\n=== SHEET IDS (after Phase 2) ===')
    print(json.dumps(existing, indent=2))


if __name__ == '__main__':
    main()
