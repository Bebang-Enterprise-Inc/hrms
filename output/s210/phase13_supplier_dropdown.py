"""S210 Phase 13: convert Supplier Name from free text to dropdown.

Fixes CEO-flagged UX bug: the Supplier Name field was a free text input
with help text 'auto-filled from pre-filled URL'. If a supplier opens the
form WITHOUT the pre-fill URL, they have to type their company name —
inviting typos that break (PO#, SI#) matching. Worse, even WITH the
pre-fill URL the field stays editable, so a supplier can accidentally
overwrite the auto-filled value.

Fix:
  1. Delete the existing Supplier Name text question (item index 0)
  2. Add a new Supplier Name DROPDOWN question at index 0, populated
     with all active supplier names from Sheet C 07_Full_Suppliers_Master
  3. Capture the new question ID
  4. Regenerate SUPPLIER_URLS.csv with the new entry ID
     (old pre-filled URLs stop working; suppliers need the new links)
  5. Update SI_UPLOAD_FORM_ID.json with new Supplier Name entry ID

handleSiUpload already reads by field title (`e.namedValues['Supplier Name']`)
so the .gs needs no change — dropdown value reads as a string, same as
text did.

Run:
    python output/s210/phase13_supplier_dropdown.py
"""
import csv, json, pathlib, sys, urllib.parse
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


def fetch_suppliers(sheet_c_id):
    """Pull all active suppliers from Sheet C 07_Full_Suppliers_Master."""
    sheets = build('sheets', 'v4',
                   credentials=creds_dwd(
                       ['https://www.googleapis.com/auth/spreadsheets.readonly'],
                       subject='commissary.team@bebang.ph'),
                   cache_discovery=False)
    resp = sheets.spreadsheets().values().get(
        spreadsheetId=sheet_c_id,
        range="'07_Full_Suppliers_Master'!A2:N",
    ).execute()
    rows = resp.get('values', [])
    suppliers = []
    for r in rows:
        if len(r) < 2 or not r[1]:
            continue
        tier = str(r[13] if len(r) > 13 else '').strip().upper()
        if tier in ('B', 'TIER B', 'C', 'TIER C'):
            continue
        suppliers.append({
            'code': r[0] if len(r) > 0 else '',
            'name': r[1].strip(),
            'tin': r[10] if len(r) > 10 else '',
            'email': r[4] if len(r) > 4 else '',
            'tier': tier or 'A',
        })
    # Dedup by name, preserve order
    seen = set()
    unique = []
    for s in suppliers:
        if s['name'] not in seen:
            seen.add(s['name'])
            unique.append(s)
    return sorted(unique, key=lambda s: s['name'].lower())


def replace_supplier_field(form_id, supplier_names):
    """Delete the existing Supplier Name text item (index 0) and create a
    new DROPDOWN item at index 0 populated with all supplier names.
    Returns the new question ID.
    """
    forms = build('forms', 'v1',
                  credentials=creds_dwd(['https://www.googleapis.com/auth/forms.body']),
                  cache_discovery=False)

    # Check if Supplier Name item still exists (prior run may have deleted it)
    existing = forms.forms().get(formId=form_id).execute()
    has_supplier_item = any(item.get('title') == 'Supplier Name'
                            for item in existing.get('items', []))
    if has_supplier_item:
        forms.forms().batchUpdate(formId=form_id, body={
            'requests': [{'deleteItem': {'location': {'index': 0}}}],
        }).execute()
        print(f'  Deleted old Supplier Name question (was index 0)')
    else:
        print(f'  No existing Supplier Name item found (prior run may have deleted it)')

    # Add new DROPDOWN at index 0
    forms.forms().batchUpdate(formId=form_id, body={
        'requests': [{
            'createItem': {
                'item': {
                    'title': 'Supplier Name',
                    'description': 'Pick your company from the dropdown. '
                                   'If you opened this via your BEI link, '
                                   'your company is pre-selected — just confirm.',
                    'questionItem': {
                        'question': {
                            'required': True,
                            'choiceQuestion': {
                                'type': 'DROP_DOWN',
                                'options': [{'value': name} for name in supplier_names],
                                'shuffle': False,
                            },
                        }
                    },
                },
                'location': {'index': 0},
            }
        }]
    }).execute()
    print(f'  Created Supplier Name DROPDOWN with {len(supplier_names)} options at index 0')

    # Read back to capture new question ID
    form = forms.forms().get(formId=form_id).execute()
    for item in form.get('items', []):
        if item.get('title') == 'Supplier Name':
            qid = item['questionItem']['question']['questionId']
            print(f'  New Supplier Name question ID: {qid}')
            return qid
    print('  WARN: could not locate new Supplier Name item')
    return None


def regenerate_urls(form_id, supplier_entry_id, suppliers):
    """Rewrite SUPPLIER_URLS.csv with the new Supplier Name entry ID."""
    # Get the responder URI from form metadata
    forms = build('forms', 'v1',
                  credentials=creds_dwd(['https://www.googleapis.com/auth/forms.body']),
                  cache_discovery=False)
    form = forms.forms().get(formId=form_id).execute()
    responder_uri = form.get('responderUri', '')
    base = responder_uri if '/viewform' in responder_uri else responder_uri + '/viewform'

    rows = []
    for s in suppliers:
        params = {'usp': 'pp_url', f'entry.{supplier_entry_id}': s['name']}
        url = base + '?' + urllib.parse.urlencode(params)
        qr = ('https://api.qrserver.com/v1/create-qr-code/?size=300x300&data='
              + urllib.parse.quote(url))
        rows.append([s['code'], s['name'], s['tin'], s['email'], s['tier'],
                     url, qr])

    with URLS_CSV_PATH.open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['supplier_code', 'supplier_name', 'tin', 'email',
                    'tier', 'prefill_url', 'qr_url'])
        for r in rows:
            w.writerow(r)
    print(f'  Rewrote {len(rows)} supplier URLs with new entry ID {supplier_entry_id}')


def main():
    print('=== S210 Phase 13: Supplier Name text -> dropdown ===\n')
    ids = json.loads(SHEET_IDS_PATH.read_text())
    form_id = ids['si_upload_form_id']

    print('[1/4] Pull suppliers from Sheet C 07_Full_Suppliers_Master')
    suppliers = fetch_suppliers(ids['sheet_c_id'])
    supplier_names = [s['name'] for s in suppliers]
    print(f'  Loaded {len(supplier_names)} unique active suppliers')

    print('\n[2/4] Replace Supplier Name field in form')
    new_qid = replace_supplier_field(form_id, supplier_names)
    if not new_qid:
        print('Aborting — new question ID not captured')
        sys.exit(1)

    print('\n[3/4] Regenerate SUPPLIER_URLS.csv with new entry ID')
    regenerate_urls(form_id, new_qid, suppliers)

    print('\n[4/4] Update SI_UPLOAD_FORM_ID.json')
    meta = json.loads(FORM_ID_PATH.read_text())
    old_qid = meta['item_ids'].get('Supplier Name', '(none)')
    meta['item_ids']['Supplier Name'] = new_qid
    meta['supplier_name_field_type'] = 'DROPDOWN'
    meta['phase13_notes'] = (
        'Supplier Name converted from free text to dropdown on 2026-04-21. '
        f'Old entry ID {old_qid} deprecated; new entry ID {new_qid}. '
        'All prior pre-filled URLs are now stale — use the regenerated '
        'SUPPLIER_URLS.csv for new supplier emails.'
    )
    FORM_ID_PATH.write_text(json.dumps(meta, indent=2), encoding='utf-8')

    print(f'\nDone. Old entry ID {old_qid} deprecated; new ID {new_qid}.')
    print('All pre-filled URLs regenerated in SUPPLIER_URLS.csv.')


if __name__ == '__main__':
    main()
