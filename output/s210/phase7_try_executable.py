"""Attempt to deploy the script as API Executable, then invoke
s210_rebuildSupplierForm via scripts.run."""
import json, pathlib, sys, time
sys.stdout.reconfigure(encoding='utf-8')
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

ROOT = pathlib.Path(r'F:\Dropbox\Projects\BEI-ERP-s210b')
SA = pathlib.Path(r'F:\Dropbox\Projects\BEI-ERP\credentials\task-manager-service.json')
ids = json.loads((ROOT / 'output/s210/SHEET_IDS.json').read_text())
SCRIPT_ID = ids['apps_script_id']

SCOPES = [
    'https://www.googleapis.com/auth/script.projects',
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/spreadsheets',
]

creds = service_account.Credentials.from_service_account_file(
    str(SA), scopes=SCOPES,
).with_subject('sam@bebang.ph')
api = build('script', 'v1', credentials=creds, cache_discovery=False)

# Push updated manifest
gs = (ROOT / 'scripts/google_apps/s210_master_handler.gs').read_text(encoding='utf-8')
manifest = (ROOT / 'scripts/google_apps/s210_appsscript.json').read_text(encoding='utf-8')

current = api.projects().getContent(scriptId=SCRIPT_ID).execute()
files = current.get('files', [])
# Replace appsscript + s210_master_handler, keep other files (eg the phase7 helper)
new_files = []
seen = set()
for f in files:
    name = f['name']
    if name == 'appsscript':
        new_files.append({'name': 'appsscript', 'type': 'JSON', 'source': manifest})
    elif name == 's210_master_handler':
        new_files.append({'name': 's210_master_handler', 'type': 'SERVER_JS', 'source': gs})
    else:
        new_files.append({'name': name, 'type': f['type'], 'source': f['source']})
    seen.add(name)
# Ensure at least these two exist
if 'appsscript' not in seen:
    new_files.append({'name': 'appsscript', 'type': 'JSON', 'source': manifest})
if 's210_master_handler' not in seen:
    new_files.append({'name': 's210_master_handler', 'type': 'SERVER_JS', 'source': gs})

api.projects().updateContent(scriptId=SCRIPT_ID, body={'files': new_files}).execute()
print('manifest + source pushed with executionApi.access=DOMAIN')

# Try to create a version + deployment
try:
    ver = api.projects().versions().create(
        scriptId=SCRIPT_ID,
        body={'description': 'S210 Phase 7 exec enabled'},
    ).execute()
    version_num = ver.get('versionNumber')
    print(f'created version {version_num}')
except HttpError as e:
    print(f'version create error: {str(e)[:200]}')
    version_num = None

if version_num:
    try:
        dep = api.projects().deployments().create(
            scriptId=SCRIPT_ID,
            body={
                'versionNumber': version_num,
                'manifestFileName': 'appsscript',
                'description': 'S210 Phase 7 API Executable',
            },
        ).execute()
        print(f'created deployment {dep.get("deploymentId")}')
    except HttpError as e:
        print(f'deployment create error: {str(e)[:200]}')

# Try scripts.run
time.sleep(3)
try:
    result = api.scripts().run(
        scriptId=SCRIPT_ID,
        body={'function': 's210_rebuildSupplierForm', 'devMode': True},
    ).execute()
    print('scripts.run result:')
    print(json.dumps(result, indent=2)[:2000])
    if 'response' in result and 'result' in result['response']:
        data = result['response']['result']
        (ROOT / 'output/s210/_FORM_REBUILD_RESULT.json').write_text(
            json.dumps(data, indent=2),
            encoding='utf-8',
        )
        print('SAVED result to _FORM_REBUILD_RESULT.json')
except HttpError as e:
    print(f'scripts.run error: {str(e)[:400]}')
