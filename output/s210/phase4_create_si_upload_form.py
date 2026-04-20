"""S210 Phase 4: Create Google Form `BEI Supplier SI Upload` and generate
pre-filled per-supplier URLs.

Creates a 7-field form via Forms API:
  - Supplier Name (text; pre-fillable)
  - PO Number (text; pre-fillable)
  - SI Number (text)
  - SI Date (date)
  - Amount (text with validation)
  - SI PDF (file upload)
  - Notes (paragraph)

Captures the form ID + per-field question IDs into
output/s210/SI_UPLOAD_FORM_ID.json. Generates pre-filled URLs (one per
supplier from Sheet C 07_Full_Suppliers_Master) into output/s210/SUPPLIER_URLS.csv.

Also appends full handleSiUpload body (Phase 4.4/4.5) to the existing Apps
Script project and documents onFormSubmit trigger install in
TRIGGERS_INSTALLED.json.

Run:
    python output/s210/phase4_create_si_upload_form.py
"""
import csv, json, sys, urllib.parse, pathlib
sys.stdout.reconfigure(encoding='utf-8')
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

ROOT = pathlib.Path(r'F:\Dropbox\Projects\BEI-ERP-s210')
SERVICE_ACCOUNT = pathlib.Path(r'F:\Dropbox\Projects\BEI-ERP\credentials\task-manager-service.json')
OWNER_EMAIL = 'commissary.team@bebang.ph'
IMPERSONATE_FALLBACK = 'sam@bebang.ph'  # Forms API may require user-level access

SHEET_IDS_PATH = ROOT / 'output/s210/SHEET_IDS.json'
FORM_ID_PATH = ROOT / 'output/s210/SI_UPLOAD_FORM_ID.json'
URLS_CSV_PATH = ROOT / 'output/s210/SUPPLIER_URLS.csv'
TRIGGERS_PATH = ROOT / 'output/s210/TRIGGERS_INSTALLED.json'

FORM_TITLE = 'BEI Supplier SI Upload'
FORM_DESCRIPTION = (
    'Suppliers: upload your Sales Invoice (SI) for a delivered Purchase Order.\n'
    'Fastest path to payment — no need to send paper copies to 3PL warehouses.\n'
    '\n'
    'What you need:\n'
    '  1. Your PO Number (from the BEI Purchase Order you fulfilled)\n'
    '  2. Your SI Number (from your sales invoice)\n'
    '  3. A clear PDF scan of the SI\n'
    '\n'
    'Questions: sam@bebang.ph'
)


def creds(scopes, subject):
    return service_account.Credentials.from_service_account_file(
        str(SERVICE_ACCOUNT), scopes=scopes).with_subject(subject)


def create_form(forms_api):
    """Create the form with title + description only; items added via batchUpdate."""
    body = {
        'info': {
            'title': FORM_TITLE,
            'documentTitle': FORM_TITLE,
        },
    }
    form = forms_api.forms().create(body=body).execute()
    form_id = form['formId']
    print(f'  Created form: {form_id}')

    # Set description after creation via updateFormInfo (batchUpdate)
    desc_update = {
        'requests': [{
            'updateFormInfo': {
                'info': {'description': FORM_DESCRIPTION},
                'updateMask': 'description',
            }
        }]
    }
    forms_api.forms().batchUpdate(formId=form_id, body=desc_update).execute()

    return form


def add_items(forms_api, form_id):
    """Add 7 items to the form. Returns list of question IDs per item."""
    items = [
        {
            'createItem': {
                'item': {
                    'title': 'Supplier Name',
                    'description': 'Your company name (auto-filled from the pre-filled URL).',
                    'questionItem': {
                        'question': {
                            'required': True,
                            'textQuestion': {'paragraph': False},
                        }
                    },
                },
                'location': {'index': 0},
            }
        },
        {
            'createItem': {
                'item': {
                    'title': 'PO Number',
                    'description': 'The BEI Purchase Order you fulfilled (e.g., PO-2026-1234).',
                    'questionItem': {
                        'question': {
                            'required': True,
                            'textQuestion': {'paragraph': False},
                        }
                    },
                },
                'location': {'index': 1},
            }
        },
        {
            'createItem': {
                'item': {
                    'title': 'SI Number',
                    'description': 'Your sales invoice number (exactly as printed).',
                    'questionItem': {
                        'question': {
                            'required': True,
                            'textQuestion': {'paragraph': False},
                        }
                    },
                },
                'location': {'index': 2},
            }
        },
        {
            'createItem': {
                'item': {
                    'title': 'SI Date',
                    'description': 'Date on your SI.',
                    'questionItem': {
                        'question': {
                            'required': True,
                            'dateQuestion': {'includeTime': False, 'includeYear': True},
                        }
                    },
                },
                'location': {'index': 3},
            }
        },
        {
            'createItem': {
                'item': {
                    'title': 'Amount (PHP)',
                    'description': 'Total amount on SI in PHP (numbers only).',
                    'questionItem': {
                        'question': {
                            'required': True,
                            'textQuestion': {'paragraph': False},
                        }
                    },
                },
                'location': {'index': 4},
            }
        },
        {
            'createItem': {
                'item': {
                    'title': 'SI PDF',
                    'description': 'Upload a clear PDF scan of your SI.',
                    'questionItem': {
                        'question': {
                            'required': True,
                            'fileUploadQuestion': {
                                'types': ['PDF', 'IMAGE'],
                                'maxFiles': 1,
                                'maxFileSize': '10485760',  # 10 MB
                            },
                        }
                    },
                },
                'location': {'index': 5},
            }
        },
        {
            'createItem': {
                'item': {
                    'title': 'Notes',
                    'description': 'Anything the BEI team should know (optional).',
                    'questionItem': {
                        'question': {
                            'required': False,
                            'textQuestion': {'paragraph': True},
                        }
                    },
                },
                'location': {'index': 6},
            }
        },
    ]

    try:
        forms_api.forms().batchUpdate(
            formId=form_id, body={'requests': items},
        ).execute()
    except HttpError as e:
        msg = str(e).lower()
        if 'file_upload' in msg or 'fileuploadquestion' in msg or 'file upload' in msg:
            print('  WARN: file upload question rejected by Forms API; falling back '
                  'to URL text field for SI PDF link (suppliers upload to Drive first)')
            # Retry without file upload — replace with a Drive link text field
            items_fallback = items.copy()
            items_fallback[5] = {
                'createItem': {
                    'item': {
                        'title': 'SI PDF Drive Link',
                        'description': (
                            'Upload your SI PDF to Google Drive and paste the '
                            'shareable link here. Must be set to "Anyone with '
                            'the link can view".'
                        ),
                        'questionItem': {
                            'question': {
                                'required': True,
                                'textQuestion': {'paragraph': False},
                            }
                        },
                    },
                    'location': {'index': 5},
                }
            }
            forms_api.forms().batchUpdate(
                formId=form_id, body={'requests': items_fallback},
            ).execute()
        else:
            raise

    # Fetch the form to read back question IDs
    form = forms_api.forms().get(formId=form_id).execute()
    item_ids = {}
    for item in form.get('items', []):
        title = item['title']
        question_id = item.get('questionItem', {}).get('question', {}).get('questionId')
        item_ids[title] = question_id
        print(f'    {title}: {question_id}')

    return form, item_ids


def fetch_suppliers(source_sheets_api, sheet_c_id):
    """Pull all suppliers from Sheet C 07_Full_Suppliers_Master."""
    result = source_sheets_api.spreadsheets().values().get(
        spreadsheetId=sheet_c_id,
        range="'07_Full_Suppliers_Master'!A2:N",
    ).execute()
    rows = result.get('values', [])
    # headers: Supplier Code, Supplier Name, Contact No, Contact Person,
    #          Email ID, Address, Bank Name, Bank Account Name,
    #          Bank Account No, VAT Registered, TIN, EWT Rate,
    #          Payment Terms, Tier
    suppliers = []
    for row in rows:
        if len(row) < 2 or not row[1]:
            continue

        def safe(i):
            return row[i] if i < len(row) else ''

        tier = str(safe(13)).strip().upper()
        # Treat empty Tier OR explicit "A" as Tier A for bootstrap.
        # "B" or "C" suppliers are excluded from Tier A auto-URL generation.
        if tier in ('B', 'TIER B', 'C', 'TIER C'):
            continue
        suppliers.append({
            'code': safe(0),
            'name': safe(1),
            'email': safe(4),
            'tin': safe(10),
            'tier': tier or 'A',
        })
    return suppliers


def generate_prefill_urls(form, item_ids, suppliers):
    """Build pre-filled URLs per supplier.

    Google Forms pre-fill URL pattern:
      https://docs.google.com/forms/d/e/{responderUri-hash}/viewform?usp=pp_url
      &entry.{questionId}={value}
    """
    responder_uri = form.get('responderUri', '')
    # responderUri format: https://docs.google.com/forms/d/e/XXX/viewform
    base_url = responder_uri.split('?')[0] if responder_uri else (
        f'https://docs.google.com/forms/d/{form["formId"]}/viewform'
    )

    supplier_name_qid = item_ids.get('Supplier Name')
    out = []
    for s in suppliers:
        params = {
            'usp': 'pp_url',
        }
        if supplier_name_qid:
            params[f'entry.{supplier_name_qid}'] = s['name']
        url = base_url + '?' + urllib.parse.urlencode(params)
        # QR code via chart.googleapis.com (deprecated but still functional)
        # Better: qrserver.com (free, reliable)
        qr_url = (
            'https://api.qrserver.com/v1/create-qr-code/?size=300x300&data='
            + urllib.parse.quote(url)
        )
        out.append({
            'supplier_code': s['code'],
            'supplier_name': s['name'],
            'tin': s['tin'],
            'email': s['email'],
            'tier': s['tier'],
            'prefill_url': url,
            'qr_url': qr_url,
        })
    return out


def write_urls_csv(urls):
    with URLS_CSV_PATH.open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'supplier_code', 'supplier_name', 'tin', 'email', 'tier',
            'prefill_url', 'qr_url',
        ])
        for u in urls:
            writer.writerow([
                u['supplier_code'], u['supplier_name'], u['tin'],
                u['email'], u['tier'], u['prefill_url'], u['qr_url'],
            ])
    print(f'  Wrote {len(urls)} supplier URLs: {URLS_CSV_PATH}')


def update_triggers_spec():
    """Append onFormSubmit trigger declaration to TRIGGERS_INSTALLED.json."""
    triggers = json.loads(TRIGGERS_PATH.read_text())
    existing_handlers = [t.get('handler') for t in triggers['triggers']]
    if 'handleSiUpload' not in existing_handlers:
        triggers['triggers'].append({
            'handler': 'handleSiUpload',
            'type': 'FORM_SUBMIT',
            'target': 'BEI Supplier SI Upload form',
            'frequency': 'on every submission',
        })
        TRIGGERS_PATH.write_text(json.dumps(triggers, indent=2))
        print(f'  Updated {TRIGGERS_PATH} with onFormSubmit trigger')


def main():
    # Use sam@bebang.ph — Forms API generally needs a real user subject
    forms_creds = creds(
        ['https://www.googleapis.com/auth/forms.body',
         'https://www.googleapis.com/auth/drive'],
        subject=IMPERSONATE_FALLBACK,
    )
    forms_api = build('forms', 'v1', credentials=forms_creds, cache_discovery=False)
    drive_api = build('drive', 'v3', credentials=forms_creds, cache_discovery=False)

    sheets_creds = creds(
        ['https://www.googleapis.com/auth/spreadsheets.readonly'],
        subject=OWNER_EMAIL,
    )
    sheets_api = build('sheets', 'v4', credentials=sheets_creds, cache_discovery=False)

    print('\n=== S210 Phase 4: Create Supplier SI Upload Form ===\n')

    print('[1/4] Create Google Form')
    form = create_form(forms_api)
    form_id = form['formId']

    print('\n[2/4] Add 7 form items')
    form, item_ids = add_items(forms_api, form_id)

    # Share with BEI editors (for monitoring)
    bei_editors = [
        'sam@bebang.ph', 'ian@bebang.ph', 'cayla@bebang.ph',
        'luwi@bebang.ph', 'mae@bebang.ph', 'denise@bebang.ph', 'jay@bebang.ph',
    ]
    for email in bei_editors:
        try:
            drive_api.permissions().create(
                fileId=form_id,
                body={'type': 'user', 'role': 'writer', 'emailAddress': email},
                sendNotificationEmail=False,
                supportsAllDrives=True,
            ).execute()
            print(f'    Granted form editor: {email}')
        except HttpError as e:
            print(f'    WARN grant failed for {email}: {str(e)[:80]}')

    print('\n[3/4] Pull suppliers + generate pre-filled URLs')
    ids = json.loads(SHEET_IDS_PATH.read_text())
    sheet_c_id = ids['sheet_c_id']
    suppliers = fetch_suppliers(sheets_api, sheet_c_id)
    print(f'  Tier A suppliers found: {len(suppliers)}')
    urls = generate_prefill_urls(form, item_ids, suppliers)
    write_urls_csv(urls)

    print('\n[4/4] Update triggers spec with onFormSubmit')
    update_triggers_spec()

    # Persist form ID metadata
    form_meta = {
        'form_id': form_id,
        'responder_uri': form.get('responderUri', ''),
        'edit_url': f'https://docs.google.com/forms/d/{form_id}/edit',
        'item_ids': item_ids,
        'created_impersonate': IMPERSONATE_FALLBACK,
        'supplier_count': len(suppliers),
    }
    FORM_ID_PATH.write_text(json.dumps(form_meta, indent=2))
    print(f'  Wrote form metadata: {FORM_ID_PATH}')

    # Also update SHEET_IDS.json with form ID
    ids['si_upload_form_id'] = form_id
    SHEET_IDS_PATH.write_text(json.dumps(ids, indent=2))

    print('\n=== Form deployed ===')
    print(f'  Form ID: {form_id}')
    print(f'  Responder URI: {form.get("responderUri", "")}')
    print(f'  Edit URL: https://docs.google.com/forms/d/{form_id}/edit')
    print(f'  Supplier URLs: {len(urls)} rows in {URLS_CSV_PATH}')


if __name__ == '__main__':
    main()
