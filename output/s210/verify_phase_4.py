"""S210 Phase 4 verifier. Exit 0 = PASS.

Checks per plan tasks 4.1-4.7:
- SI_UPLOAD_FORM_ID.json exists with form_id + responder_uri + item_ids
- SHEET_IDS.json contains si_upload_form_id
- SUPPLIER_URLS.csv exists with >=30 rows
- .gs contains function handleSiUpload (non-stub body)
- .gs contains function generateSupplierUrls
- TRIGGERS_INSTALLED.json lists handleSiUpload with FORM_SUBMIT type
"""
import csv, json, sys, pathlib
sys.stdout.reconfigure(encoding='utf-8')

ROOT = pathlib.Path(r'F:\Dropbox\Projects\BEI-ERP-s210')

GS_PATH = ROOT / 'scripts/google_apps/s210_master_handler.gs'
FORM_ID_PATH = ROOT / 'output/s210/SI_UPLOAD_FORM_ID.json'
URLS_CSV_PATH = ROOT / 'output/s210/SUPPLIER_URLS.csv'
TRIGGERS_PATH = ROOT / 'output/s210/TRIGGERS_INSTALLED.json'
SHEET_IDS_PATH = ROOT / 'output/s210/SHEET_IDS.json'


def main():
    failures = []

    # Form metadata
    if not FORM_ID_PATH.exists():
        failures.append(f'{FORM_ID_PATH} missing')
    else:
        meta = json.loads(FORM_ID_PATH.read_text())
        if not meta.get('form_id'):
            failures.append('SI_UPLOAD_FORM_ID.json missing form_id')
        if not meta.get('responder_uri'):
            failures.append('SI_UPLOAD_FORM_ID.json missing responder_uri')
        item_ids = meta.get('item_ids', {})
        required_items = ['Supplier Name', 'PO Number', 'SI Number', 'SI Date',
                          'Amount (PHP)', 'Notes']
        for name in required_items:
            if name not in item_ids:
                failures.append(f'item_ids missing {name}')

    # SHEET_IDS.json updated
    ids = json.loads(SHEET_IDS_PATH.read_text())
    if not ids.get('si_upload_form_id'):
        failures.append('SHEET_IDS.json missing si_upload_form_id')

    # Supplier URLs CSV
    if not URLS_CSV_PATH.exists():
        failures.append(f'{URLS_CSV_PATH} missing')
    else:
        with URLS_CSV_PATH.open(encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        if len(rows) < 30:
            failures.append(f'SUPPLIER_URLS.csv has {len(rows)} rows (need >=30)')
        # Spot-check URL shape
        if rows:
            sample = rows[0]
            if 'prefill_url' not in sample or not sample['prefill_url']:
                failures.append('SUPPLIER_URLS.csv prefill_url column empty')
            elif 'docs.google.com/forms' not in sample['prefill_url']:
                failures.append('SUPPLIER_URLS.csv prefill_url not a Forms URL')

    # .gs contents
    gs = GS_PATH.read_text(encoding='utf-8')
    if 'function handleSiUpload' not in gs:
        failures.append('.gs missing function handleSiUpload')
    elif "'Phase_4_stub'" in gs.split('function handleSiUpload')[1].split('function ')[0]:
        # Ensure handleSiUpload body is not just the stub
        failures.append('.gs handleSiUpload still a stub')
    if 'function generateSupplierUrls' not in gs:
        failures.append('.gs missing function generateSupplierUrls')

    # handleSiUpload must do matching + tagging
    handle_body = ''
    if 'function handleSiUpload' in gs:
        start = gs.find('function handleSiUpload')
        end = gs.find('\nfunction ', start + 10)
        handle_body = gs[start:end if end > 0 else len(gs)]
        required_snippets = [
            '03_Supplier_SI_Uploads',
            '04_Match_Queue',
            '02_All_Receipts_Consolidated',
            'SI_Matched',  # tagging logic reference
            'matchStatus',
        ]
        for snippet in required_snippets:
            if snippet not in handle_body:
                failures.append(f'handleSiUpload missing reference: {snippet}')

    # Triggers spec
    triggers = json.loads(TRIGGERS_PATH.read_text())
    handlers = {t.get('handler'): t for t in triggers.get('triggers', [])}
    if 'handleSiUpload' not in handlers:
        failures.append('TRIGGERS_INSTALLED.json missing handleSiUpload')
    elif handlers['handleSiUpload'].get('type') != 'FORM_SUBMIT':
        failures.append(f'handleSiUpload type != FORM_SUBMIT (got {handlers["handleSiUpload"].get("type")})')

    print('\n=== S210 Phase 4 Verifier ===\n')
    if failures:
        for f in failures:
            print(f'[FAIL] {f}')
        print(f'\n{len(failures)} failures')
        sys.exit(1)

    print(f'[PASS] SI_UPLOAD_FORM_ID.json has form_id={meta["form_id"][:20]}...')
    print(f'[PASS] Form has {len(item_ids)} question IDs captured')
    print(f'[PASS] SHEET_IDS.json.si_upload_form_id set')
    print(f'[PASS] SUPPLIER_URLS.csv has {len(rows)} rows')
    print(f'[PASS] .gs handleSiUpload has full body ({len(handle_body)} chars)')
    print(f'[PASS] .gs generateSupplierUrls present')
    print(f'[PASS] TRIGGERS_INSTALLED.json lists handleSiUpload (FORM_SUBMIT)')
    print('\nAll checks passed.')
    sys.exit(0)


if __name__ == '__main__':
    main()
