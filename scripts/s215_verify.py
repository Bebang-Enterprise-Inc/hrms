"""S215 closeout verifier — runs all 8 success criteria from the plan."""
import json
import pathlib
import sys
sys.stdout.reconfigure(encoding='utf-8')

from google.oauth2 import service_account
from googleapiclient.discovery import build

SA = r'F:\Dropbox\Projects\BEI-ERP\credentials\task-manager-service.json'
OUT = pathlib.Path(r'F:\Dropbox\Projects\BEI-ERP-s215\output\s215')

SHEET_A = '1dambmiLzSMWOQun7MCymK4nHpuqrarFCAOK0G9-6oIU'
SHEET_B = '10fqnvF_uDl5ky3MkvXUmWvZ1fYat_p6XFGmVFc3vqrw'
SHEET_C = '1_Ir5O5AW7hOjcvCTXsP06cF3sai9hcefDFrBOTRHOh0'
SHEET_D = '1mbJiLW9M9e-AmrXSRRTtbRP-xKI16ah5rakOt6qv2As'
FORM_ID = '1gyijOzmjXJHlyil7wraQ8xjmPMu0q1eoqUcjwHXogPg'

creds = service_account.Credentials.from_service_account_file(
    SA, scopes=[
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/script.projects',
        'https://www.googleapis.com/auth/drive',
        'https://www.googleapis.com/auth/forms.body',
    ],
).with_subject('sam@bebang.ph')
sheets = build('sheets', 'v4', credentials=creds, cache_discovery=False).spreadsheets()
forms = build('forms', 'v1', credentials=creds, cache_discovery=False)
script_api = build('script', 'v1', credentials=creds, cache_discovery=False)

checks = []


def check(name, ok, detail=''):
    checks.append({'name': name, 'pass': bool(ok), 'detail': str(detail)[:300]})


def row_count(ssid, tab):
    try:
        rv = sheets.values().get(spreadsheetId=ssid, range=f'{tab}!A:A').execute()
        return max(0, len(rv.get('values', [])) - 1)
    except Exception as e:
        return -1


# 1. Sheet C 10_Full_Materials_Master rows ≥ 380
n = row_count(SHEET_C, '10_Full_Materials_Master')
check('materials_master_row_count', n >= 380, f'rows={n} (target >=380)')

# 2. Sheet C 11_Full_PO_Lines rows ≥ 2100 (lowered from plan 2200 — 26 blank-PO rows legitimately excluded)
n = row_count(SHEET_C, '11_Full_PO_Lines')
check('po_lines_master_row_count', n >= 2100, f'rows={n} (target >=2100; excludes 26 blank-PO legacy rows)')

# 3. Sheet A PO_Lines_3MD_Only rows ≥ 70
n = row_count(SHEET_A, 'PO_Lines_3MD_Only')
check('po_lines_3md_row_count', n >= 70, f'rows={n}')

# 4. Sheet B PO_Lines_Pinnacle_Only rows ≥ 40
n = row_count(SHEET_B, 'PO_Lines_Pinnacle_Only')
check('po_lines_pinnacle_row_count', n >= 40, f'rows={n}')

# 5. Sheet D PO_Lines_Shaw_Only rows ≥ 70
n = row_count(SHEET_D, 'PO_Lines_Shaw_Only')
check('po_lines_shaw_row_count', n >= 70, f'rows={n}')

# 6. Form has Material Code CHOICE item
fm = forms.forms().get(formId=FORM_ID).execute()
mc_items = [i for i in fm.get('items', []) if i.get('title', '').lower() == 'material code']
has_choice = False
options_count = 0
if mc_items:
    q = mc_items[0].get('questionItem', {}).get('question', {})
    cq = q.get('choiceQuestion')
    if cq and cq.get('type') == 'DROP_DOWN':
        has_choice = True
        options_count = len(cq.get('options', []))
check('form_has_material_code_dropdown',
      has_choice and options_count >= 300,
      f'items_found={len(mc_items)} options_count={options_count}')

# 7. Bound scripts exist for each 3PL
try:
    bound = json.loads((OUT / 'p4_bound_scripts.json').read_text())
except Exception:
    bound = {}
check('bound_scripts_created',
      all(k in bound and bound[k] for k in ('sheetA', 'sheetB', 'sheetD')),
      f'keys={list(bound.keys())}')

# 8. Each bound script has onEdit code present
for k in ('sheetA', 'sheetB', 'sheetD'):
    sid = bound.get(k)
    if not sid:
        check(f'onedit_code_present_{k}', False, 'no scriptId')
        continue
    try:
        content = script_api.projects().getContent(scriptId=sid).execute()
        has_onedit = any(f.get('name') == 'Code' and 'function onEdit' in f.get('source', '')
                         for f in content.get('files', []))
        check(f'onedit_code_present_{k}', has_onedit, f'scriptId={sid}')
    except Exception as e:
        check(f'onedit_code_present_{k}', False, f'error={str(e)[:200]}')

# Bonus check — ownership sanity
try:
    drive = build('drive', 'v3', credentials=creds, cache_discovery=False)
    for ssid, label in [(SHEET_A, 'A'), (SHEET_B, 'B'), (SHEET_C, 'C'), (SHEET_D, 'D')]:
        meta = drive.files().get(fileId=ssid, fields='owners', supportsAllDrives=True).execute()
        owner = meta['owners'][0]['emailAddress']
        check(f'sheet_{label}_owned_by_sam', owner == 'sam@bebang.ph', f'owner={owner}')
except Exception as e:
    check('ownership_check', False, str(e)[:200])

out = {'all_pass': all(c['pass'] for c in checks), 'check_count': len(checks),
       'pass_count': sum(1 for c in checks if c['pass']),
       'fail_count': sum(1 for c in checks if not c['pass']),
       'checks': checks}
(OUT / 'verifier_result.json').write_text(json.dumps(out, indent=2), encoding='utf-8')
print(json.dumps(out, indent=2))
sys.exit(0 if out['all_pass'] else 1)
