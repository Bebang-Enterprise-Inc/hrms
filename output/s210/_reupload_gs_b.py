"""Re-upload .gs + manifest from the -s210b worktree."""
import json, pathlib, sys
sys.stdout.reconfigure(encoding='utf-8')
from google.oauth2 import service_account
from googleapiclient.discovery import build

ROOT = pathlib.Path(r'F:\Dropbox\Projects\BEI-ERP-s210b')
ids = json.loads((ROOT / 'output/s210/SHEET_IDS.json').read_text())
gs = (ROOT / 'scripts/google_apps/s210_master_handler.gs').read_text(encoding='utf-8')
manifest = (ROOT / 'scripts/google_apps/s210_appsscript.json').read_text(encoding='utf-8')

creds = service_account.Credentials.from_service_account_file(
    r'F:\Dropbox\Projects\BEI-ERP\credentials\task-manager-service.json',
    scopes=['https://www.googleapis.com/auth/script.projects'],
).with_subject('sam@bebang.ph')
api = build('script', 'v1', credentials=creds, cache_discovery=False)

cur = api.projects().getContent(scriptId=ids['apps_script_id']).execute()
files = []
for f in cur.get('files', []):
    if f['name'] == 'appsscript':
        files.append({'name': 'appsscript', 'type': 'JSON', 'source': manifest})
    elif f['name'] == 's210_master_handler':
        files.append({'name': 's210_master_handler', 'type': 'SERVER_JS', 'source': gs})
    else:
        files.append({'name': f['name'], 'type': f['type'], 'source': f['source']})

api.projects().updateContent(scriptId=ids['apps_script_id'], body={'files': files}).execute()

resp = api.projects().getContent(scriptId=ids['apps_script_id']).execute()
for f in resp.get('files', []):
    print(f'  {f["name"]}: {len(f.get("source", ""))} chars')
