"""Phase A — One-time BDO clearance catchup.

Takes the 202 BDO-matched checks already produced and writes clearance tags to:
  1. FPM RFP Summary  (1t4wJLiAfIMJm6fe-x6h4eZn_S_Lx1AGN5ORd5Ywhcyw)
  2. Suppliers SOA    (1ZHe2VoAFa94ET4I68C1jWM7nMzTdTCvttwZbICaLtB4)
  3. HO AP            (1jSwZRyIPisU4jiKS-Tn9VFoLukQI8UNoW13Hoov-75Y)

Safety:
  - Creates dated backup copy of each sheet BEFORE any write
  - Dry-run by default; pass --apply to actually write
  - Never hardcodes column letters — reads header row each time

Inputs (already produced today):
  - CEO/CashFlow/bdo_statements/matched_bdo_to_fpm.csv  (202 rows)
  - CEO/CashFlow/bdo_statements/ap_invoices_to_clear.csv  (39 rows for SOA/HO AP)
"""
import argparse
import json
from pathlib import Path
from datetime import datetime
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build

CREDS = 'credentials/task-manager-service.json'
OWNER = 'sam@bebang.ph'

FPM_ID = '1t4wJLiAfIMJm6fe-x6h4eZn_S_Lx1AGN5ORd5Ywhcyw'
SOA_ID = '1ZHe2VoAFa94ET4I68C1jWM7nMzTdTCvttwZbICaLtB4'
HO_ID = '1jSwZRyIPisU4jiKS-Tn9VFoLukQI8UNoW13Hoov-75Y'

# Intercompany entities to skip (treasury moves, not supplier liability)
INTERCOMPANY_PAYEES = [
    'BEBANG ENTERPRISE', 'BEBANG KITCHEN', 'BEBANG SHAW',
    'BEBANG HALO-HALO', 'BEBANG HALOHALO', 'BKI', 'BSI', 'BHH',
]


def is_intercompany(payee):
    if not payee:
        return False
    p = str(payee).upper()
    return any(tag in p for tag in INTERCOMPANY_PAYEES)


def get_services():
    creds = service_account.Credentials.from_service_account_file(
        CREDS,
        scopes=[
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive',
        ],
    ).with_subject(OWNER)
    sheets = build('sheets', 'v4', credentials=creds, cache_discovery=False)
    drive = build('drive', 'v3', credentials=creds, cache_discovery=False)
    return sheets, drive


def backup_sheet(drive, sheet_id, label):
    """Make a dated backup copy."""
    today = datetime.now().strftime('%Y-%m-%d')
    original = drive.files().get(fileId=sheet_id, fields='name,parents', supportsAllDrives=True).execute()
    backup_name = f"BACKUP — {original['name']} (pre-BDO-catchup {today})"
    # Check if already exists
    r = drive.files().list(
        q=f"name='{backup_name}' and trashed=false", fields='files(id,name)',
        supportsAllDrives=True, includeItemsFromAllDrives=True,
    ).execute()
    existing = r.get('files', [])
    if existing:
        print(f"  [{label}] Backup already exists: {existing[0]['id']}")
        return existing[0]['id']
    copied = drive.files().copy(fileId=sheet_id, body={'name': backup_name}, supportsAllDrives=True).execute()
    print(f"  [{label}] Backup created: {copied['id']} ({backup_name})")
    return copied['id']


def find_or_append_col(sheets, spreadsheet_id, sheet_name, col_name, header_row=1, apply_writes=False):
    """Return 0-indexed column position for col_name, appending if missing.

    Expands grid if needed. If apply_writes=False, returns the target index without actually writing.
    """
    meta = sheets.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    sheet_info = None
    for s in meta['sheets']:
        if s['properties']['title'] == sheet_name:
            sheet_info = s['properties']
            break
    if sheet_info is None:
        raise ValueError(f"Sheet '{sheet_name}' not found")
    sheet_gid = sheet_info['sheetId']
    current_cols = sheet_info['gridProperties']['columnCount']

    hdr_resp = sheets.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id, range=f"'{sheet_name}'!{header_row}:{header_row}",
        valueRenderOption='UNFORMATTED_VALUE',
    ).execute()
    headers = hdr_resp.get('values', [[]])[0]
    for i, h in enumerate(headers):
        if str(h).strip().lower() == col_name.lower():
            return i

    new_idx = len(headers)
    col_letter = a1_col(new_idx)

    if not apply_writes:
        print(f"    [dry-run] Would append '{col_name}' at position {new_idx} ({col_letter})")
        return new_idx

    if new_idx >= current_cols:
        cols_to_add = new_idx - current_cols + 2
        sheets.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={'requests': [{
                'appendDimension': {
                    'sheetId': sheet_gid,
                    'dimension': 'COLUMNS',
                    'length': cols_to_add,
                }
            }]},
        ).execute()
        print(f"    Grid expanded by {cols_to_add} columns (now {current_cols + cols_to_add})")

    sheets.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id, range=f"'{sheet_name}'!{col_letter}{header_row}",
        valueInputOption='USER_ENTERED',
        body={'values': [[col_name]]},
    ).execute()
    print(f"    Appended column '{col_name}' at position {new_idx} ({col_letter})")
    return new_idx


def a1_col(idx):
    """0-indexed column → A1 letter."""
    letters = ''
    n = idx
    while True:
        letters = chr(ord('A') + (n % 26)) + letters
        n = n // 26 - 1
        if n < 0:
            break
    return letters


def update_fpm(sheets, apply_writes):
    """Phase A step 3: Update FPM RFP Summary."""
    print('\n── FPM RFP Summary ──')
    # Load matched data
    matched = pd.read_csv('CEO/CashFlow/bdo_statements/matched_bdo_to_fpm.csv')
    matched['debit'] = pd.to_numeric(matched['debit'], errors='coerce').fillna(0)

    # Fetch FPM headers + data
    resp = sheets.spreadsheets().values().get(
        spreadsheetId=FPM_ID, range="RFP Summary",
        valueRenderOption='UNFORMATTED_VALUE',
    ).execute()
    vals = resp.get('values', [])
    headers = vals[0]
    rfp_col = headers.index('RFP NO.')
    status_col = headers.index('Status')
    chk_col = headers.index('Check No./Ref No.')

    # Locate or create new columns (header row 1 for FPM)
    cleared_date_col = find_or_append_col(sheets, FPM_ID, 'RFP Summary', 'BDO Cleared Date', header_row=1, apply_writes=apply_writes)
    cleared_amt_col = find_or_append_col(sheets, FPM_ID, 'RFP Summary', 'BDO Cleared Amount', header_row=1, apply_writes=apply_writes)

    # Build RFP -> row index lookup
    rfp_to_row = {}
    for r_idx, row in enumerate(vals[1:], 2):  # row 1 is header, data starts row 2
        if len(row) <= rfp_col:
            continue
        rfp = str(row[rfp_col]).strip()
        if rfp and rfp != 'nan':
            rfp_to_row[rfp] = (r_idx, row)

    # Build check -> row index as fallback
    chk_to_row = {}
    for r_idx, row in enumerate(vals[1:], 2):
        if len(row) <= chk_col:
            continue
        chk = str(row[chk_col]).strip().lstrip('0')
        if chk:
            chk_to_row[chk] = (r_idx, row)

    # Plan writes
    updates = []  # list of (range, value)
    changed_status = 0
    added_cleared_date = 0
    skipped_intercompany = 0

    for _, m in matched.iterrows():
        rfp = str(m.get('RFP NO.', '')).strip()
        chk = str(m['check_clean']).strip()
        # Locate row
        target = rfp_to_row.get(rfp) or chk_to_row.get(chk)
        if not target:
            continue
        r_idx, row = target
        payee = row[headers.index('Payee')] if headers.index('Payee') < len(row) else ''
        current_status = row[status_col] if status_col < len(row) else ''
        debit = float(m['debit'])
        bdo_date = m['date']

        # Always write cleared date + amount
        updates.append((f"'RFP Summary'!{a1_col(cleared_date_col)}{r_idx}", bdo_date))
        updates.append((f"'RFP Summary'!{a1_col(cleared_amt_col)}{r_idx}", debit))
        added_cleared_date += 1

        # Only flip Status → Paid/Cleared for non-intercompany AND not already Paid
        if is_intercompany(payee):
            skipped_intercompany += 1
            continue
        if str(current_status).strip() == 'Paid/ Cleared':
            continue
        updates.append((f"'RFP Summary'!{a1_col(status_col)}{r_idx}", 'Paid/ Cleared'))
        changed_status += 1

    print(f'  Planned updates: {len(updates)} cells')
    print(f'  Status flipped to Paid/Cleared: {changed_status}')
    print(f'  Intercompany skipped (status kept): {skipped_intercompany}')
    print(f'  BDO Cleared Date/Amount written: {added_cleared_date}')

    if apply_writes and updates:
        # Batch in chunks
        CHUNK = 500
        for i in range(0, len(updates), CHUNK):
            batch = updates[i:i+CHUNK]
            data = [{'range': rng, 'values': [[val]]} for rng, val in batch]
            sheets.spreadsheets().values().batchUpdate(
                spreadsheetId=FPM_ID,
                body={'data': data, 'valueInputOption': 'USER_ENTERED'},
            ).execute()
            print(f'    Applied batch {i//CHUNK + 1}: {len(batch)} cells')

    return {
        'total_updates': len(updates),
        'status_flipped': changed_status,
        'intercompany_skipped': skipped_intercompany,
        'cleared_metadata_written': added_cleared_date,
    }


def update_ap_sheet(sheets, sheet_id, sheet_name, label, apply_writes, header_row, match_source_tag):
    """Phase A step 4: Update Suppliers SOA or HO AP.

    header_row: 1-indexed header row (SOA + HO AP use row 2)
    match_source_tag: 'Suppliers SOA' or 'Head Office AP' — used to filter ap_invoices_to_clear.csv
    """
    print(f'\n── {label} ──')
    ap_rows = pd.read_csv('CEO/CashFlow/bdo_statements/ap_invoices_to_clear.csv')
    ap_rows_src = ap_rows[ap_rows['source'] == match_source_tag]
    print(f'  Candidate rows (ap_invoices_to_clear.csv source={match_source_tag!r}): {len(ap_rows_src)}')

    meta = sheets.spreadsheets().get(spreadsheetId=sheet_id).execute()
    first_sheet = meta['sheets'][0]['properties']['title']
    resp = sheets.spreadsheets().values().get(
        spreadsheetId=sheet_id, range=first_sheet,
        valueRenderOption='UNFORMATTED_VALUE',
    ).execute()
    vals = resp.get('values', [])
    if len(vals) <= header_row:
        print(f'  {label}: insufficient data, skipping')
        return {}
    headers = vals[header_row - 1]

    # Find Invoice No. column (SOA col G = "INVOICE NO.", HO AP col G = "OR/SI NUMBER")
    invoice_col = None
    for i, h in enumerate(headers):
        hu = str(h).upper().strip()
        if hu in ('INVOICE NO.', 'OR/SI NUMBER', 'INVOICE_NO') or 'INVOICE NO' in hu or 'OR/SI' in hu:
            invoice_col = i
            break
    if invoice_col is None:
        print(f'  {label}: cannot find invoice column in row {header_row}. Headers: {headers[:15]}')
        return {}
    print(f'  Match column: "{headers[invoice_col]}" (idx {invoice_col})')

    cleared_date_col = find_or_append_col(sheets, sheet_id, first_sheet, 'BDO Cleared Date', header_row=header_row, apply_writes=apply_writes)
    cleared_amt_col = find_or_append_col(sheets, sheet_id, first_sheet, 'BDO Cleared Amount', header_row=header_row, apply_writes=apply_writes)

    # Map invoice → row data for lookup
    inv_map = {str(r['invoice_no']).strip(): r for _, r in ap_rows_src.iterrows() if pd.notna(r['invoice_no'])}

    updates = []
    matched_count = 0
    for r_idx, row in enumerate(vals[header_row:], header_row + 1):
        if len(row) <= invoice_col:
            continue
        inv = str(row[invoice_col]).strip()
        if inv in inv_map:
            row_data = inv_map[inv]
            cleared_date = str(row_data.get('proc_date', '')) if pd.notna(row_data.get('proc_date')) else ''
            updates.append((f"'{first_sheet}'!{a1_col(cleared_date_col)}{r_idx}", cleared_date))
            updates.append((f"'{first_sheet}'!{a1_col(cleared_amt_col)}{r_idx}", float(row_data['outstanding'])))
            matched_count += 1

    print(f'  Matched {matched_count} rows, {len(updates)} cells to update')

    if apply_writes and updates:
        CHUNK = 500
        for i in range(0, len(updates), CHUNK):
            batch = updates[i:i+CHUNK]
            data = [{'range': rng, 'values': [[val]]} for rng, val in batch]
            sheets.spreadsheets().values().batchUpdate(
                spreadsheetId=sheet_id,
                body={'data': data, 'valueInputOption': 'USER_ENTERED'},
            ).execute()
            print(f'    Applied batch {i//CHUNK + 1}: {len(batch)} cells')

    return {'rows_matched': matched_count, 'cells_updated': len(updates)}


def write_report(phase_a_results):
    """Generate CATCHUP_REPORT_2026-04-17.md."""
    today = datetime.now().strftime('%Y-%m-%d')
    path = Path(f'CEO/CashFlow/bdo_statements/CATCHUP_REPORT_{today}.md')
    body = f"""# BDO Clearance Catch-Up Report — {today}

## Summary
One-time catch-up processed the 202 BDO-matched checks (Jan 16 – Apr 17, 2026) against FPM, Suppliers SOA, and HO AP ledgers.

## Results

### FPM RFP Summary
- Total cells updated: **{phase_a_results['fpm']['total_updates']}**
- Rows flipped to "Paid/ Cleared": **{phase_a_results['fpm']['status_flipped']}**
- Intercompany rows skipped (status preserved): **{phase_a_results['fpm']['intercompany_skipped']}**
- BDO Cleared Date + Amount written: **{phase_a_results['fpm']['cleared_metadata_written']}**

### Suppliers SOA
- Rows matched: **{phase_a_results['soa'].get('rows_matched', 0)}**
- Cells updated: **{phase_a_results['soa'].get('cells_updated', 0)}**

### HO AP
- Rows matched: **{phase_a_results['ho'].get('rows_matched', 0)}**
- Cells updated: **{phase_a_results['ho'].get('cells_updated', 0)}**

## Backup Locations
Dated backups created before writes. Check Drive for files named `BACKUP — [original name] (pre-BDO-catchup {today})`.

## Next Steps
1. Refresh Cashflow Tracker via Extensions → Apps Script → Run refreshAll
2. Verify Tab 1 AP drops from ~₱90.82M to ~₱83.12M
3. Phase B weekly automation will handle future BDO uploads automatically

## Sources
- `CEO/CashFlow/bdo_statements/matched_bdo_to_fpm.csv` — 202 matches, ₱115.11M
- `CEO/CashFlow/bdo_statements/ap_invoices_to_clear.csv` — 39 real-liability rows, ₱7.70M
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding='utf-8')
    print(f'\nReport written: {path}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='Actually write to sheets (default: dry-run)')
    ap.add_argument('--skip-backup', action='store_true', help='Skip backup creation (use with caution)')
    args = ap.parse_args()

    mode = 'APPLY' if args.apply else 'DRY-RUN'
    print(f'=== BDO Clearance Catch-Up — {mode} ===')

    sheets, drive = get_services()

    # Step 1: Backups
    if args.apply and not args.skip_backup:
        print('\nStep 1: Creating backups')
        backup_sheet(drive, FPM_ID, 'FPM')
        backup_sheet(drive, SOA_ID, 'SOA')
        backup_sheet(drive, HO_ID, 'HO AP')
    else:
        print('\nStep 1: SKIPPED (dry-run or --skip-backup)')

    # Step 2-3: FPM
    fpm_results = update_fpm(sheets, args.apply)

    # Step 4: Suppliers SOA
    soa_results = update_ap_sheet(sheets, SOA_ID, 'SUPPLIERS SOA', 'Suppliers SOA', args.apply,
                                  header_row=2, match_source_tag='Suppliers SOA')

    # Step 4: HO AP
    ho_results = update_ap_sheet(sheets, HO_ID, 'Detailed HEAD OFFICE', 'Head Office AP', args.apply,
                                 header_row=2, match_source_tag='Head Office AP')

    # Step 5: Report
    if args.apply:
        write_report({'fpm': fpm_results, 'soa': soa_results, 'ho': ho_results})

    print('\n' + '=' * 60)
    print(f'Done ({mode}).')
    if not args.apply:
        print('\nThis was a DRY-RUN. To apply changes, run:')
        print('  python scripts/catchup_bdo_clearance.py --apply')


if __name__ == '__main__':
    main()
