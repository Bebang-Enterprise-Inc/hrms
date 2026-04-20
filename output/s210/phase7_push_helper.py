"""Push updated s210_phase7_form_rebuild helper to the deployed Apps Script
project. The helper persists the result into Sheet C 09_Audit_Log so the
Python side can pick it up after a human clicks Run.
"""
import json, pathlib, sys, re
sys.stdout.reconfigure(encoding='utf-8')
from google.oauth2 import service_account
from googleapiclient.discovery import build

ROOT = pathlib.Path(r'F:\Dropbox\Projects\BEI-ERP-s210b')
SA = pathlib.Path(r'F:\Dropbox\Projects\BEI-ERP\credentials\task-manager-service.json')
ids = json.loads((ROOT / 'output/s210/SHEET_IDS.json').read_text())

# Extract the helper source from phase7_patch_ux.py
patch_src = (ROOT / 'output/s210/phase7_patch_ux.py').read_text(encoding='utf-8')
m = re.search(
    r"form_setup_src = '''\s*(/\*\*[\s\S]*?^}\s*)'''",
    patch_src,
    flags=re.MULTILINE,
)
if not m:
    print('FAILED to extract helper source from phase7_patch_ux.py')
    sys.exit(1)
helper_src = m.group(1)
print(f'helper source: {len(helper_src)} chars')

creds = service_account.Credentials.from_service_account_file(
    str(SA), scopes=['https://www.googleapis.com/auth/script.projects']
).with_subject('sam@bebang.ph')
api = build('script', 'v1', credentials=creds, cache_discovery=False)

cur = api.projects().getContent(scriptId=ids['apps_script_id']).execute()
files = []
replaced = False
for f in cur.get('files', []):
    if f['name'] == 's210_phase7_form_rebuild':
        files.append({'name': f['name'], 'type': 'SERVER_JS', 'source': helper_src})
        replaced = True
    else:
        files.append({'name': f['name'], 'type': f['type'], 'source': f['source']})
if not replaced:
    files.append({'name': 's210_phase7_form_rebuild', 'type': 'SERVER_JS', 'source': helper_src})

api.projects().updateContent(scriptId=ids['apps_script_id'], body={'files': files}).execute()
print(f'Pushed updated helper to script {ids["apps_script_id"]}')
print(f'Editor URL: https://script.google.com/d/{ids["apps_script_id"]}/edit')
