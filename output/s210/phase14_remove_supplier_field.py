"""S210 Phase 14: remove Supplier Name field entirely; derive from PO.

CEO feedback (2026-04-21): the Supplier Name dropdown was a confidentiality
leak — it exposed the full 98-supplier roster to every supplier who opened
the form. Suppliers compete with each other; we don't give them our list.

Fix: remove Supplier Name from the form entirely. The supplier types only
what they already know from their own PO + SI. handleSiUpload derives the
supplier name by looking up the PO Number in Sheet C 08_Full_Open_POs.
If the PO isn't in the master (closed, typo, etc.), orphan to Match
Queue with supplier='UNKNOWN — PO lookup failed'.

Form after this phase (7 items, no Supplier Name):
  1. Warehouse (RADIO: 3MD, Pinnacle, Shaw BLVD)
  2. PO Number (text)
  3. SI Number (text)
  4. SI Date (date)
  5. Amount (PHP) (text)
  6. Upload SI Copy (file upload)
  7. Notes (paragraph)

SUPPLIER_URLS.csv is obsolete — one generic URL for all suppliers replaces
per-supplier pre-filled URLs. File kept in repo for audit but marked
deprecated.

Run:
    python output/s210/phase14_remove_supplier_field.py
"""
import json, pathlib, sys
sys.stdout.reconfigure(encoding='utf-8')
from google.oauth2 import service_account
from googleapiclient.discovery import build

ROOT = pathlib.Path(__file__).resolve().parents[2]
SA = pathlib.Path(r'F:\Dropbox\Projects\BEI-ERP\credentials\task-manager-service.json')

SHEET_IDS_PATH = ROOT / 'output/s210/SHEET_IDS.json'
FORM_ID_PATH = ROOT / 'output/s210/SI_UPLOAD_FORM_ID.json'
URLS_CSV_PATH = ROOT / 'output/s210/SUPPLIER_URLS.csv'


def creds_dwd(scopes, subject='sam@bebang.ph'):
    return service_account.Credentials.from_service_account_file(
        str(SA), scopes=scopes).with_subject(subject)


def main():
    print('=== S210 Phase 14: Remove Supplier Name field ===\n')
    ids = json.loads(SHEET_IDS_PATH.read_text())
    form_id = ids['si_upload_form_id']

    forms = build('forms', 'v1',
                  credentials=creds_dwd(['https://www.googleapis.com/auth/forms.body']),
                  cache_discovery=False)

    # Find the Supplier Name item index
    print('[1/3] Locate + delete Supplier Name field')
    form = forms.forms().get(formId=form_id).execute()
    supplier_idx = None
    for i, item in enumerate(form.get('items', [])):
        if item.get('title') == 'Supplier Name':
            supplier_idx = i
            break

    if supplier_idx is None:
        print('  (no Supplier Name item found — already removed)')
    else:
        forms.forms().batchUpdate(formId=form_id, body={
            'requests': [{'deleteItem': {'location': {'index': supplier_idx}}}],
        }).execute()
        print(f'  Deleted Supplier Name item at index {supplier_idx}')

    # Capture fresh item IDs
    print('\n[2/3] Refresh SI_UPLOAD_FORM_ID.json with live state')
    form = forms.forms().get(formId=form_id).execute()
    item_ids = {}
    for item in form.get('items', []):
        title = item.get('title')
        qid = item.get('questionItem', {}).get('question', {}).get('questionId', '')
        item_ids[title] = qid
        print(f'  {title}: {qid}')

    meta = json.loads(FORM_ID_PATH.read_text())
    meta['item_ids'] = item_ids
    meta.pop('supplier_name_field_type', None)
    meta['phase14_notes'] = (
        'Supplier Name field removed 2026-04-21 — CEO directive: dropdown '
        'exposed supplier roster (confidentiality leak). Supplier name is '
        'now derived from PO Number via Sheet C 08_Full_Open_POs lookup in '
        'handleSiUpload.'
    )
    FORM_ID_PATH.write_text(json.dumps(meta, indent=2), encoding='utf-8')

    # Mark SUPPLIER_URLS.csv deprecated
    print('\n[3/3] Mark SUPPLIER_URLS.csv deprecated')
    if URLS_CSV_PATH.exists():
        content = URLS_CSV_PATH.read_text(encoding='utf-8')
        new_header = (
            '# DEPRECATED 2026-04-21 — one generic form URL replaces per-supplier pre-filled URLs.\n'
            '# Use this single link for all suppliers:\n'
            f'# {form.get("responderUri", "")}\n'
            '# File retained for audit trail only.\n'
        )
        if not content.startswith('# DEPRECATED'):
            URLS_CSV_PATH.write_text(new_header + content, encoding='utf-8')
            print(f'  Prepended DEPRECATED header to SUPPLIER_URLS.csv')
        else:
            print(f'  SUPPLIER_URLS.csv already marked deprecated')

    print(f'\nForm URL for all suppliers: {form.get("responderUri", "")}')
    print('Done. Phase 15 (.gs handler + redeploy) next.')


if __name__ == '__main__':
    main()
