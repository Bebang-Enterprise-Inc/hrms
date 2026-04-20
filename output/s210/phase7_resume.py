"""S210 Phase 7 resume — run after Sam clicks Run on
s210_rebuildSupplierForm in the Apps Script editor.

Polls Sheet C 09_Audit_Log for a row tagged `phase7_form_rebuild`, parses
the JSON result from its details column, and:
  - writes SI_UPLOAD_FORM_ID.json
  - rewrites SUPPLIER_URLS.csv with the new form + entry IDs
  - updates SHEET_IDS.json
"""
import csv, json, pathlib, sys, time, urllib.parse
sys.stdout.reconfigure(encoding='utf-8')
from google.oauth2 import service_account
from googleapiclient.discovery import build

ROOT = pathlib.Path(__file__).resolve().parents[2]
SA = pathlib.Path(r'F:\Dropbox\Projects\BEI-ERP\credentials\task-manager-service.json')

SHEET_IDS_PATH = ROOT / 'output/s210/SHEET_IDS.json'
FORM_ID_PATH = ROOT / 'output/s210/SI_UPLOAD_FORM_ID.json'
URLS_CSV_PATH = ROOT / 'output/s210/SUPPLIER_URLS.csv'


def creds(scopes, subject='commissary.team@bebang.ph'):
    return service_account.Credentials.from_service_account_file(
        str(SA), scopes=scopes).with_subject(subject)


def poll_audit_log_for_result(sheets_api, sheet_c_id, timeout_sec=600):
    """Look for a row with trigger='phase7_form_rebuild' in 09_Audit_Log.
    If not found, prints instructions and polls every 10 sec up to timeout.
    """
    print('Polling Sheet C 09_Audit_Log for phase7_form_rebuild entry...')
    start = time.time()
    while time.time() - start < timeout_sec:
        resp = sheets_api.spreadsheets().values().get(
            spreadsheetId=sheet_c_id,
            range="'09_Audit_Log'!A:G",
        ).execute()
        rows = resp.get('values', [])
        # rows: Timestamp, Trigger, Sheet, Row, Action, Outcome, Details
        for r in reversed(rows):  # newest first
            if len(r) >= 7 and r[1] == 'phase7_form_rebuild':
                print(f'  Found: {r[4]} @ {r[0]}')
                try:
                    return json.loads(r[6])
                except Exception as e:
                    print(f'  WARN could not parse details: {e}')
                    continue
        print('  Not found yet — waiting 10s. Sam, please go to:')
        print(f'  https://script.google.com/d/{json.loads(SHEET_IDS_PATH.read_text())["apps_script_id"]}/edit')
        print('  Select function `s210_rebuildSupplierForm` -> Run. Approve OAuth if prompted.')
        time.sleep(10)
    return None


def rewrite_supplier_urls(sheets_api, sheet_c_id, form_data):
    responder = form_data.get('responderUri', '')
    base = responder if '/viewform' in responder else responder + '/viewform'
    supplier_entry = form_data.get('entries', {}).get('Supplier Name')

    resp = sheets_api.spreadsheets().values().get(
        spreadsheetId=sheet_c_id,
        range="'07_Full_Suppliers_Master'!A2:N",
    ).execute()
    rows = resp.get('values', [])

    out = []
    for r in rows:
        if len(r) < 2 or not r[1]:
            continue
        tier = str(r[13] if len(r) > 13 else '').strip().upper()
        if tier in ('B', 'TIER B', 'C', 'TIER C'):
            continue
        params = {'usp': 'pp_url'}
        if supplier_entry:
            params[f'entry.{supplier_entry}'] = r[1]
        url = base + '?' + urllib.parse.urlencode(params)
        qr = ('https://api.qrserver.com/v1/create-qr-code/?size=300x300&data='
              + urllib.parse.quote(url))
        out.append([
            r[0] if len(r) > 0 else '',
            r[1],
            r[10] if len(r) > 10 else '',
            r[4] if len(r) > 4 else '',
            tier or 'A',
            url,
            qr,
        ])

    with URLS_CSV_PATH.open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['supplier_code', 'supplier_name', 'tin', 'email',
                    'tier', 'prefill_url', 'qr_url'])
        for row in out:
            w.writerow(row)
    return len(out)


def main():
    ids = json.loads(SHEET_IDS_PATH.read_text())
    sheets_creds = creds(['https://www.googleapis.com/auth/spreadsheets'])
    sheets_api = build('sheets', 'v4', credentials=sheets_creds, cache_discovery=False)

    form_data = poll_audit_log_for_result(sheets_api, ids['sheet_c_id'])
    if form_data is None:
        print('\nTimeout. Re-run this script when ready.')
        sys.exit(1)

    print('\nForm data received:')
    print(json.dumps(form_data, indent=2))

    # Persist
    meta = {
        'form_id': form_data['formId'],
        'responder_uri': form_data.get('responderUri', ''),
        'edit_url': form_data.get('editUrl', f'https://docs.google.com/forms/d/{form_data["formId"]}/edit'),
        'item_ids': form_data.get('entries', {}),
        'created_via': 'Apps Script FormApp (native file upload)',
    }
    FORM_ID_PATH.write_text(json.dumps(meta, indent=2), encoding='utf-8')

    ids['si_upload_form_id'] = form_data['formId']
    ids['si_upload_form_uses_native_file_upload'] = True
    SHEET_IDS_PATH.write_text(json.dumps(ids, indent=2), encoding='utf-8')

    n = rewrite_supplier_urls(sheets_api, ids['sheet_c_id'], form_data)
    print(f'\nWrote {n} supplier URLs to {URLS_CSV_PATH}')
    print(f'Form ID saved to {FORM_ID_PATH}')
    print(f'Form URL: {meta["responder_uri"]}')


if __name__ == '__main__':
    main()
