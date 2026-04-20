"""Helper: re-upload .gs + manifest to Apps Script project."""
import json, pathlib, sys
sys.stdout.reconfigure(encoding='utf-8')
from google.oauth2 import service_account
from googleapiclient.discovery import build

ROOT = pathlib.Path(r'F:\Dropbox\Projects\BEI-ERP-s210')
ids = json.loads((ROOT / 'output/s210/SHEET_IDS.json').read_text())
gs = (ROOT / 'scripts/google_apps/s210_master_handler.gs').read_text(encoding='utf-8')
manifest = (ROOT / 'scripts/google_apps/s210_appsscript.json').read_text(encoding='utf-8')

creds = service_account.Credentials.from_service_account_file(
    r'F:\Dropbox\Projects\BEI-ERP\credentials\task-manager-service.json',
    scopes=['https://www.googleapis.com/auth/script.projects'],
).with_subject('sam@bebang.ph')
api = build('script', 'v1', credentials=creds, cache_discovery=False)

api.projects().updateContent(scriptId=ids['apps_script_id'], body={'files': [
    {'name': 'appsscript', 'type': 'JSON', 'source': manifest},
    {'name': 's210_master_handler', 'type': 'SERVER_JS', 'source': gs},
]}).execute()

resp = api.projects().getContent(scriptId=ids['apps_script_id']).execute()
for f in resp.get('files', []):
    print(f'  {f["name"]}: {len(f.get("source", ""))} chars')
