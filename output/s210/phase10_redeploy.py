"""S210 Phase 10 — redeploy updated .gs to the existing web-app URL.

Why: we added multi-line delivery support to _handleNewReceipts
(header-field inheritance) and fixed the SI-match bug in handleSiUpload
(tag ALL matching consolidated rows, not just the first). Cloud Scheduler
jobs already point to the existing web-app URL, so we:

  1. Re-upload .gs via Apps Script API
  2. Create a new version (snapshot of the updated source)
  3. PATCH the existing deployment to point to the new version -
     URL stays the same, Scheduler jobs require no changes.
  4. Smoke-test /exec?fn=ping to confirm the new code is live.

Run:
    python output/s210/phase10_redeploy.py
"""
import json, pathlib, sys, urllib.parse, urllib.request
sys.stdout.reconfigure(encoding='utf-8')
from google.oauth2 import service_account
from googleapiclient.discovery import build

ROOT = pathlib.Path(__file__).resolve().parents[2]
SA = pathlib.Path(r'F:\Dropbox\Projects\BEI-ERP\credentials\task-manager-service.json')
ids = json.loads((ROOT / 'output/s210/SHEET_IDS.json').read_text())
cloud = json.loads((ROOT / 'output/s210/CLOUD_SCHEDULER.json').read_text())

SHARED_TOKEN = 's210-b3i-a8F2kQ9mZv7RpYxLnCdT4wE6hG1jN5uH0sK3'

creds = service_account.Credentials.from_service_account_file(
    str(SA),
    scopes=[
        'https://www.googleapis.com/auth/script.projects',
        'https://www.googleapis.com/auth/script.deployments',
    ],
).with_subject('sam@bebang.ph')
api = build('script', 'v1', credentials=creds, cache_discovery=False)

gs = (ROOT / 'scripts/google_apps/s210_master_handler.gs').read_text(encoding='utf-8')
manifest = (ROOT / 'scripts/google_apps/s210_appsscript.json').read_text(encoding='utf-8')

script_id = ids['apps_script_id']
deployment_id = cloud['deployment_id']

print(f'[1/4] Pushing updated source to {script_id}')
cur = api.projects().getContent(scriptId=script_id).execute()
new_files = []
for f in cur.get('files', []):
    if f['name'] == 'appsscript':
        new_files.append({'name': 'appsscript', 'type': 'JSON', 'source': manifest})
    elif f['name'] == 's210_master_handler':
        new_files.append({'name': 's210_master_handler', 'type': 'SERVER_JS', 'source': gs})
    else:
        new_files.append({'name': f['name'], 'type': f['type'], 'source': f['source']})

api.projects().updateContent(scriptId=script_id, body={'files': new_files}).execute()

print(f'[2/4] Creating new version')
v = api.projects().versions().create(
    scriptId=script_id,
    body={'description': 'S210 Phase 10: multi-line delivery support + SI match fix'},
).execute()
version_num = v['versionNumber']
print(f'  Version {version_num}')

print(f'[3/4] Updating deployment {deployment_id} to new version')
updated = api.projects().deployments().update(
    scriptId=script_id,
    deploymentId=deployment_id,
    body={
        'deploymentConfig': {
            'versionNumber': version_num,
            'manifestFileName': 'appsscript',
            'description': f'S210 Phase 10 (v{version_num})',
        },
    },
).execute()
web_url = None
for ep in updated.get('entryPoints', []):
    if ep.get('entryPointType') == 'WEB_APP':
        web_url = ep['webApp']['url']
        break
web_url = web_url or cloud['web_app_url']
print(f'  URL unchanged: {web_url}')

print('[4/4] Smoke-test')
test_url = f'{web_url}?{urllib.parse.urlencode({"key": SHARED_TOKEN, "fn": "ping"})}'
with urllib.request.urlopen(test_url, timeout=30) as r:
    print(f'  Ping: {r.read().decode()[:200]}')

poll_url = f'{web_url}?{urllib.parse.urlencode({"key": SHARED_TOKEN, "fn": "pollAll"})}'
with urllib.request.urlopen(poll_url, timeout=120) as r:
    print(f'  pollAll: {r.read().decode()[:400]}')

print('\nDone. Cloud Scheduler jobs continue hitting the same URL; they pick up the new code on next fire.')
