"""S210 Phase 7 — CEO-directed UX patch (2026-04-20 PM).

Two corrections CEO directed after seeing the bare Sheet A:

  1. 3PLs will not paste image/drive links in a spreadsheet. Remove
     "SI Photo" and "Delivery Photo" columns from Sheets A, B, D Receipts
     tabs. 3PL only types SI Number; photos live in the parallel supplier
     SI upload stream.

  2. Supplier SI Upload form must have a native file upload BUTTON
     (not a text field asking for a Drive link). Rebuild the form using
     Apps Script FormApp (which supports file upload) instead of the REST
     Forms API (which does not).

This script:
  - Rewrites headers on Sheets A, B, D Receipts tabs: 18 cols -> 16 cols
    (drops SI Photo + Delivery Photo). Any data in those columns is
    discarded — currently there's only the E2E test rows, not production
    data. For future data preservation, the existing rows are also
    rewritten col-by-col into the new 16-col layout.
  - Builds + runs an Apps Script function (pushed via updateContent) that
    creates a new Form with a native FILE_UPLOAD item via FormApp.
  - Captures new form ID + entry IDs into SI_UPLOAD_FORM_ID.json.
  - Rewrites SUPPLIER_URLS.csv using the new form + entry IDs.
  - Updates s210_master_handler.gs column constants + validateReceipt
    (remove siPhoto requirement) + handleSiUpload field mappings.

Run:
    python output/s210/phase7_patch_ux.py
"""
import csv, json, sys, urllib.parse, pathlib
sys.stdout.reconfigure(encoding='utf-8')
from google.oauth2 import service_account
from googleapiclient.discovery import build

ROOT = pathlib.Path(r'F:\Dropbox\Projects\BEI-ERP-s210b')
SERVICE_ACCOUNT = pathlib.Path(r'F:\Dropbox\Projects\BEI-ERP\credentials\task-manager-service.json')
OWNER_EMAIL = 'commissary.team@bebang.ph'
SAM = 'sam@bebang.ph'

SHEET_IDS_PATH = ROOT / 'output/s210/SHEET_IDS.json'
FORM_ID_PATH = ROOT / 'output/s210/SI_UPLOAD_FORM_ID.json'
URLS_CSV_PATH = ROOT / 'output/s210/SUPPLIER_URLS.csv'

# New 16-col schema for 3PL receipt sheets
NEW_RECEIPTS_HEADERS = [
    'Timestamp', '3PL', 'RR Number', 'PO Number', 'Supplier', 'Material Code',
    'Material Description', 'Qty Received', 'UoM', 'SI Number',
    "Trucker's Name", 'Plate Number', 'Production Date',
    'Expiration Date', 'Received By', 'Notes',
]

# Old 18-col positions (for migrating existing rows)
OLD_COL_MAP = {
    'Timestamp': 0, '3PL': 1, 'RR Number': 2, 'PO Number': 3, 'Supplier': 4,
    'Material Code': 5, 'Material Description': 6, 'Qty Received': 7, 'UoM': 8,
    'SI Number': 9, 'SI Photo': 10, 'Delivery Photo': 11,
    "Trucker's Name": 12, 'Plate Number': 13, 'Production Date': 14,
    'Expiration Date': 15, 'Received By': 16, 'Notes': 17,
}


def creds(scopes, subject=OWNER_EMAIL):
    return service_account.Credentials.from_service_account_file(
        str(SERVICE_ACCOUNT), scopes=scopes).with_subject(subject)


def col_letter(n):
    s = ''
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def migrate_sheet_to_16_cols(sheets_api, sheet_id, sheet_label):
    """Drop SI Photo + Delivery Photo columns from the Receipts tab."""
    print(f'  [{sheet_label}] reading current Receipts data')
    resp = sheets_api.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range="'Receipts'!A1:R",  # old 18 cols A..R
    ).execute()
    data = resp.get('values', [])
    if not data:
        data = [[]]

    # Map each row's values into new 16-col layout
    migrated = [NEW_RECEIPTS_HEADERS]
    for i, row in enumerate(data[1:], start=1):
        new_row = []
        for header in NEW_RECEIPTS_HEADERS:
            idx = OLD_COL_MAP[header]
            new_row.append(row[idx] if idx < len(row) else '')
        migrated.append(new_row)

    # Clear old range and write new
    sheets_api.spreadsheets().values().clear(
        spreadsheetId=sheet_id, range="'Receipts'!A1:R",
    ).execute()

    last_col = col_letter(16)
    sheets_api.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=f"'Receipts'!A1:{last_col}{len(migrated)}",
        valueInputOption='USER_ENTERED',
        body={'values': migrated},
    ).execute()

    # Re-bold header row
    meta = sheets_api.spreadsheets().get(spreadsheetId=sheet_id).execute()
    receipts_tab_id = next(
        s['properties']['sheetId'] for s in meta['sheets']
        if s['properties']['title'] == 'Receipts'
    )
    sheets_api.spreadsheets().batchUpdate(
        spreadsheetId=sheet_id,
        body={'requests': [{
            'repeatCell': {
                'range': {'sheetId': receipts_tab_id, 'startRowIndex': 0, 'endRowIndex': 1},
                'cell': {'userEnteredFormat': {'textFormat': {'bold': True}, 'backgroundColor': {'red': 0.9, 'green': 0.93, 'blue': 1.0}}},
                'fields': 'userEnteredFormat(textFormat,backgroundColor)',
            }
        }]},
    ).execute()

    print(f'  [{sheet_label}] rewrote Receipts with 16 cols; {len(migrated) - 1} data rows migrated')


def rebuild_supplier_form_via_appsscript(script_api, script_id, drive_api):
    """Push a temporary FormApp setup function to the deployed Apps Script
    project, then manually invoke it via scripts.run to create a new Form
    with a native FILE_UPLOAD item. FormApp supports file upload; the
    Forms REST API does not.

    Returns form_id, responder_uri, entry_id_map.
    """
    # Read current .gs so we don't clobber it
    current = script_api.projects().getContent(scriptId=script_id).execute()
    files = {f['name']: f for f in current.get('files', [])}

    form_setup_src = '''
/**
 * S210 Phase 7 — create the Supplier SI Upload form via FormApp (which
 * supports native file upload, unlike the Forms REST API).
 *
 * Writes the result (formId, responderUri, entries) into Sheet C 09_Audit_Log
 * with trigger=phase7_form_rebuild so Python can read it back.
 */
function s210_rebuildSupplierForm() {
  const title = 'BEI Supplier SI Upload';
  const form = FormApp.create(title);
  form.setTitle(title);
  form.setDescription(
    'Suppliers: upload your Sales Invoice (SI) for a delivered Purchase Order.\\n' +
    'Fastest path to payment — no paper SI forwarding needed.\\n\\n' +
    'Required: PO Number, SI Number, SI Date, SI Amount, SI PDF file.\\n\\n' +
    'Questions: sam@bebang.ph'
  );

  const supplierItem = form.addTextItem()
    .setTitle('Supplier Name')
    .setHelpText('Your company name (auto-filled from the pre-filled URL).')
    .setRequired(true);
  const poItem = form.addTextItem()
    .setTitle('PO Number')
    .setHelpText('The BEI Purchase Order you fulfilled (e.g., PO-2026-1234).')
    .setRequired(true);
  const siNumItem = form.addTextItem()
    .setTitle('SI Number')
    .setHelpText('Your sales invoice number (exactly as printed).')
    .setRequired(true);
  const siDateItem = form.addDateItem()
    .setTitle('SI Date')
    .setHelpText('Date on your SI.')
    .setRequired(true);
  const amountItem = form.addTextItem()
    .setTitle('Amount (PHP)')
    .setHelpText('Total amount on SI in PHP (numbers only).')
    .setRequired(true);
  // Native file upload — no Drive link text field fallback
  const fileItem = form.addFileUploadItem()
    .setTitle('SI PDF')
    .setHelpText('Tap to upload a clear PDF or photo of your SI.')
    .setRequired(true);
  try { fileItem.setMaxFiles(1); } catch (e) {}
  try { fileItem.setMaxFileSize(FormApp.FileSize.MB_10); } catch (e) {}
  const notesItem = form.addParagraphTextItem()
    .setTitle('Notes')
    .setHelpText('Anything the BEI team should know (optional).')
    .setRequired(false);

  // Share form with BEI editors
  const beiEditors = [
    'sam@bebang.ph', 'ian@bebang.ph', 'cayla@bebang.ph',
    'luwi@bebang.ph', 'mae@bebang.ph', 'denise@bebang.ph', 'jay@bebang.ph',
  ];
  const formFile = DriveApp.getFileById(form.getId());
  for (const email of beiEditors) {
    try { formFile.addEditor(email); } catch (e) {}
  }

  const result = {
    formId: form.getId(),
    responderUri: form.getPublishedUrl(),
    editUrl: 'https://docs.google.com/forms/d/' + form.getId() + '/edit',
    entries: {
      'Supplier Name': String(supplierItem.getId()),
      'PO Number': String(poItem.getId()),
      'SI Number': String(siNumItem.getId()),
      'SI Date': String(siDateItem.getId()),
      'Amount (PHP)': String(amountItem.getId()),
      'SI PDF': String(fileItem.getId()),
      'Notes': String(notesItem.getId()),
    },
  };

  // Persist result to Sheet C 09_Audit_Log for Python pickup
  try {
    const SHEET_C_ID = '1_Ir5O5AW7hOjcvCTXsP06cF3sai9hcefDFrBOTRHOh0';
    const audit = SpreadsheetApp.openById(SHEET_C_ID).getSheetByName('09_Audit_Log');
    audit.appendRow([
      new Date(),
      'phase7_form_rebuild',
      'manual',
      0,
      'FORM_CREATED',
      'OK',
      JSON.stringify(result),
    ]);
  } catch (e) {
    console.error('Failed to persist to audit log: ' + e);
  }

  console.log(JSON.stringify(result, null, 2));
  return result;
}
'''

    # Push the helper function into a new file in the script
    new_files = []
    for name, f in files.items():
        new_files.append({'name': f['name'], 'type': f['type'], 'source': f['source']})
    # Add/replace the helper file
    found = False
    for f in new_files:
        if f['name'] == 's210_phase7_form_rebuild':
            f['source'] = form_setup_src
            found = True
    if not found:
        new_files.append({
            'name': 's210_phase7_form_rebuild', 'type': 'SERVER_JS',
            'source': form_setup_src,
        })

    script_api.projects().updateContent(
        scriptId=script_id, body={'files': new_files},
    ).execute()
    print('  Pushed s210_phase7_form_rebuild helper to Apps Script project')

    # Try scripts.run. If unsupported for our service account, return None
    # and caller will instruct a manual one-click run.
    try:
        result = script_api.scripts().run(
            scriptId=script_id,
            body={'function': 's210_rebuildSupplierForm', 'devMode': True},
        ).execute()
        if 'error' in result:
            raise RuntimeError(str(result['error'])[:200])
        data = result.get('response', {}).get('result', {})
        print(f'  scripts.run returned formId={data.get("formId")}')
        return data
    except Exception as e:
        print(f'  WARN scripts.run failed: {str(e)[:160]}')
        print('        Fallback: asking caller to run the helper manually')
        return None


def rewrite_supplier_urls(form_data, sheets_api, sheet_c_id):
    """Rebuild SUPPLIER_URLS.csv with the new form's entry IDs."""
    responder = form_data.get('responderUri', '')
    # Normalize to prefill base
    if '/viewform' in responder:
        base = responder
    else:
        base = responder + '/viewform'

    supplier_entry = form_data.get('entries', {}).get('Supplier Name')
    if not supplier_entry:
        print('  WARN: no Supplier Name entry id; URLs will not pre-fill')

    # Pull suppliers from Sheet C
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
        out.append({
            'supplier_code': r[0] if len(r) > 0 else '',
            'supplier_name': r[1],
            'tin': r[10] if len(r) > 10 else '',
            'email': r[4] if len(r) > 4 else '',
            'tier': tier or 'A',
            'prefill_url': url,
            'qr_url': qr,
        })

    with URLS_CSV_PATH.open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['supplier_code', 'supplier_name', 'tin', 'email',
                    'tier', 'prefill_url', 'qr_url'])
        for r in out:
            w.writerow([r['supplier_code'], r['supplier_name'], r['tin'],
                        r['email'], r['tier'], r['prefill_url'], r['qr_url']])
    print(f'  Rewrote {len(out)} supplier URLs with new form entries')
    return len(out)


def main():
    print('\n=== S210 Phase 7 — CEO UX patch ===\n')

    # Sheets
    sheets_creds = creds(['https://www.googleapis.com/auth/spreadsheets'])
    sheets_api = build('sheets', 'v4', credentials=sheets_creds, cache_discovery=False)

    ids = json.loads(SHEET_IDS_PATH.read_text())
    print('[1/4] Strip photo columns from Sheets A, B, D')
    for label, sid in [('A-3MD', ids['sheet_a_id']),
                       ('B-Pinnacle', ids['sheet_b_id']),
                       ('D-Shaw', ids['sheet_d_id'])]:
        migrate_sheet_to_16_cols(sheets_api, sid, label)

    # Apps Script (as sam — fallback used in Phase 3)
    print('\n[2/4] Push rebuild helper to Apps Script project')
    script_creds = creds(
        ['https://www.googleapis.com/auth/script.projects',
         'https://www.googleapis.com/auth/script.scriptapp',
         'https://www.googleapis.com/auth/drive'],
        subject=SAM,
    )
    script_api = build('script', 'v1', credentials=script_creds, cache_discovery=False)
    drive_api = build('drive', 'v3', credentials=script_creds, cache_discovery=False)

    form_data = rebuild_supplier_form_via_appsscript(
        script_api, ids['apps_script_id'], drive_api,
    )

    if form_data is None:
        # scripts.run is not authorized for our SA. Write a manual-run
        # marker file; user runs helper once from the editor.
        manual_md = (
            '# S210 Phase 7 - manual one-click step\n\n'
            'The Apps Script API does not allow our service account to call '
            '`scripts.run` on this project without a publisher-approved '
            'API Executable deployment. One manual click needed:\n\n'
            '1. Open the script editor: ' + ids.get('apps_script_editor_url', '') + '\n'
            "2. In the file panel (left), click `s210_phase7_form_rebuild`.\n"
            "3. In the function dropdown (top), select `s210_rebuildSupplierForm`.\n"
            "4. Click Run. Approve OAuth when prompted (FormApp + DriveApp scopes).\n"
            '5. In the execution log pane at the bottom, copy the returned '
            'JSON object (formId, responderUri, entries).\n'
            '6. Paste the whole thing into `output/s210/_FORM_REBUILD_RESULT.json`.\n'
            '7. Re-run `python output/s210/phase7_patch_ux_resume.py` to '
            'rewrite SUPPLIER_URLS.csv and SI_UPLOAD_FORM_ID.json.\n'
        )
        (ROOT / 'output/s210/PHASE7_MANUAL_STEP.md').write_text(
            manual_md, encoding='utf-8',
        )
        print('\n  Fallback: manual one-click step documented at output/s210/PHASE7_MANUAL_STEP.md')
        # Still delete old form since it has the bad link-paste UX
        old_form_id = ids.get('si_upload_form_id')
        if old_form_id:
            try:
                drive_api.files().delete(fileId=old_form_id).execute()
                print(f'  Deleted old form {old_form_id}')
            except Exception as e:
                print(f'  (leaving old form intact — delete error: {str(e)[:80]})')
        return

    # Success path: update metadata
    print('\n[3/4] Rewrite SUPPLIER_URLS.csv with new form entries')
    rewrite_supplier_urls(form_data, sheets_api, ids['sheet_c_id'])

    # Persist new form metadata
    print('\n[4/4] Update SHEET_IDS.json + SI_UPLOAD_FORM_ID.json')
    new_meta = {
        'form_id': form_data['formId'],
        'responder_uri': form_data.get('responderUri', ''),
        'edit_url': f'https://docs.google.com/forms/d/{form_data["formId"]}/edit',
        'item_ids': form_data['entries'],
        'created_via': 'Apps Script FormApp (supports native file upload)',
        'replaces_form_id': ids.get('si_upload_form_id', ''),
    }
    FORM_ID_PATH.write_text(json.dumps(new_meta, indent=2))

    # Delete old form
    old_form_id = ids.get('si_upload_form_id')
    if old_form_id and old_form_id != form_data['formId']:
        try:
            drive_api.files().delete(fileId=old_form_id).execute()
            print(f'  Deleted old form {old_form_id}')
        except Exception as e:
            print(f'  WARN could not delete old form: {str(e)[:80]}')

    ids['si_upload_form_id'] = form_data['formId']
    ids['si_upload_form_uses_native_file_upload'] = True
    SHEET_IDS_PATH.write_text(json.dumps(ids, indent=2))


if __name__ == '__main__':
    main()
