"""S215 — push updated handler to Apps Script project + bump web-app version.

Pushes `scripts/google_apps/s210_master_handler.gs` + `scripts/google_apps/s210_appsscript.json`
to Apps Script project 1lsvOlv1rGEvXl_1zms4SURlsLUZk7CxRhg2NyBDrDHh4fDjuioFZhi2S.
Creates a new version + updates the existing HEAD deployment to point to it.
"""
import json
import pathlib
import sys
sys.stdout.reconfigure(encoding='utf-8')

from google.oauth2 import service_account
from googleapiclient.discovery import build

SA = r'F:\Dropbox\Projects\BEI-ERP\credentials\task-manager-service.json'
OUT = pathlib.Path(r'F:\Dropbox\Projects\BEI-ERP-s215\output\s215')
OUT.mkdir(parents=True, exist_ok=True)

APPS_SCRIPT_ID = '1lsvOlv1rGEvXl_1zms4SURlsLUZk7CxRhg2NyBDrDHh4fDjuioFZhi2S'
DEPLOYMENT_ID = 'AKfycbwHhE8wesatwrXdw8SYOFjm30zqG62wNgFUyC_GIB14zFQb1CHU4ov-jVm1wjGfqFj2'
SRC_DIR = pathlib.Path(r'F:\Dropbox\Projects\BEI-ERP-s215\scripts\google_apps')

creds = service_account.Credentials.from_service_account_file(
    SA,
    scopes=['https://www.googleapis.com/auth/script.projects',
            'https://www.googleapis.com/auth/script.deployments'],
).with_subject('sam@bebang.ph')
script = build('script', 'v1', credentials=creds, cache_discovery=False)

handler = (SRC_DIR / 's210_master_handler.gs').read_text(encoding='utf-8')
manifest = (SRC_DIR / 's210_appsscript.json').read_text(encoding='utf-8')

# Push new content
files = [
    {'name': 's210_master_handler', 'type': 'SERVER_JS', 'source': handler},
    {'name': 'appsscript', 'type': 'JSON', 'source': manifest},
]
content_resp = script.projects().updateContent(
    scriptId=APPS_SCRIPT_ID,
    body={'files': files},
).execute()
print(f'[OK] updateContent — scriptId={content_resp.get("scriptId")}')

# Create a new version
version_resp = script.projects().versions().create(
    scriptId=APPS_SCRIPT_ID,
    body={'description': 'S215 Phase 1+2: materials master + PO lines + per-3PL filter'},
).execute()
new_version = version_resp.get('versionNumber')
print(f'[OK] versions.create — version={new_version}')

# Find the existing deployment that serves the web app
deployments = script.projects().deployments().list(scriptId=APPS_SCRIPT_ID).execute().get('deployments', [])
target = None
for d in deployments:
    dc = d.get('deploymentConfig', {})
    # entry points include WEB_APP — find the one whose URL prefix matches DEPLOYMENT_ID
    entry_points = d.get('entryPoints', [])
    for ep in entry_points:
        if ep.get('entryPointType') == 'WEB_APP':
            wa = ep.get('webApp', {})
            if DEPLOYMENT_ID in (wa.get('url') or ''):
                target = d
                break
    if target:
        break

if target is None:
    print('[ERROR] Could not find web-app deployment matching DEPLOYMENT_ID')
    print('Deployments found:')
    print(json.dumps(deployments, indent=2)[:2000])
    sys.exit(1)

dep_id = target['deploymentId']
print(f'[OK] target deployment id={dep_id}')

# Update the deployment to point at the new version
update_resp = script.projects().deployments().update(
    scriptId=APPS_SCRIPT_ID,
    deploymentId=dep_id,
    body={
        'deploymentConfig': {
            'scriptId': APPS_SCRIPT_ID,
            'versionNumber': new_version,
            'manifestFileName': 'appsscript',
            'description': 'S215 Phase 1+2 ' + str(new_version),
        }
    },
).execute()
print(f'[OK] deployments.update — version now={update_resp.get("deploymentConfig", {}).get("versionNumber")}')

summary = {
    'apps_script_id': APPS_SCRIPT_ID,
    'deployment_id': dep_id,
    'new_version': new_version,
    'files_pushed': [f['name'] for f in files],
}
(OUT / 'p1_p2_deploy.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
print('\nDeploy complete. New version live on:')
print(f'  https://script.google.com/macros/s/{DEPLOYMENT_ID}/exec')
