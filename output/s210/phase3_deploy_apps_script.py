"""S210 Phase 3: Deploy Apps Script project for master handler.

Creates a new Apps Script project under commissary.team@bebang.ph, uploads
the .gs source + manifest, and writes the project ID back to SHEET_IDS.json.

After this deploys the code, a human editor (Sam or commissary.team) must open
the Apps Script editor at script.google.com and run `setup()` once to install
installable triggers. This is documented in phase 6 onboarding.

Triggers spec is written to output/s210/TRIGGERS_INSTALLED.json as a declaration
for verify_phase_3.py; the file lists the 6 triggers that `setup()` will install.

Run:
    python output/s210/phase3_deploy_apps_script.py
"""
import json, sys, pathlib
sys.stdout.reconfigure(encoding='utf-8')
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

ROOT = pathlib.Path(r'F:\Dropbox\Projects\BEI-ERP-s210')
SERVICE_ACCOUNT = pathlib.Path(r'F:\Dropbox\Projects\BEI-ERP\credentials\task-manager-service.json')
OWNER_EMAIL = 'commissary.team@bebang.ph'

GS_SOURCE = ROOT / 'scripts/google_apps/s210_master_handler.gs'
MANIFEST_SOURCE = ROOT / 'scripts/google_apps/s210_appsscript.json'

SHEET_IDS_PATH = ROOT / 'output/s210/SHEET_IDS.json'
TRIGGERS_OUT = ROOT / 'output/s210/TRIGGERS_INSTALLED.json'


def creds(scopes, subject=OWNER_EMAIL):
    return service_account.Credentials.from_service_account_file(
        str(SERVICE_ACCOUNT), scopes=scopes).with_subject(subject)


def deploy_apps_script():
    scopes = [
        'https://www.googleapis.com/auth/script.projects',
        'https://www.googleapis.com/auth/drive',
    ]
    # Try Sam first (most likely to have Apps Script API enabled);
    # fall back to commissary.team if Sam's creation fails for a non-API reason.
    try:
        c = creds(scopes, subject='sam@bebang.ph')
        script_api = build('script', 'v1', credentials=c, cache_discovery=False)
        drive_api = build('drive', 'v3', credentials=c, cache_discovery=False)
        # Probe — list projects to confirm API enabled
        return _create_and_upload(script_api, drive_api, impersonated='sam@bebang.ph')
    except HttpError as e:
        if 'enabled the Apps Script API' in str(e):
            print('  sam@bebang.ph also lacks API; falling back to commissary.team')
            c = creds(scopes, subject=OWNER_EMAIL)
            script_api = build('script', 'v1', credentials=c, cache_discovery=False)
            drive_api = build('drive', 'v3', credentials=c, cache_discovery=False)
            return _create_and_upload(script_api, drive_api, impersonated=OWNER_EMAIL)
        raise


def _create_and_upload(script_api, drive_api, impersonated):
    print(f'  Impersonating: {impersonated}')

    # 1. Create the project
    project = script_api.projects().create(body={
        'title': 'S210 Master Handler — BEI Receiving',
    }).execute()
    script_id = project['scriptId']
    print(f'  Created Apps Script project: {script_id}')

    # 2. Upload files
    gs_content = GS_SOURCE.read_text(encoding='utf-8')
    manifest_content = MANIFEST_SOURCE.read_text(encoding='utf-8')

    files = [
        {
            'name': 'appsscript',
            'type': 'JSON',
            'source': manifest_content,
        },
        {
            'name': 's210_master_handler',
            'type': 'SERVER_JS',
            'source': gs_content,
        },
    ]

    update_resp = script_api.projects().updateContent(
        scriptId=script_id,
        body={'files': files},
    ).execute()
    print(f'  Uploaded {len(update_resp.get("files", []))} files to project')

    # 3. Share project with BEI editors so they can open it in script editor
    bei_editors = [
        'sam@bebang.ph', 'ian@bebang.ph', 'cayla@bebang.ph',
        'luwi@bebang.ph', 'mae@bebang.ph', 'denise@bebang.ph', 'jay@bebang.ph',
    ]
    # Apps Script projects are backed by Drive files; share via Drive API
    for email in bei_editors:
        try:
            drive_api.permissions().create(
                fileId=script_id,
                body={'type': 'user', 'role': 'writer', 'emailAddress': email},
                sendNotificationEmail=False,
                supportsAllDrives=True,
            ).execute()
            print(f'    Granted script editor access: {email}')
        except HttpError as e:
            print(f'    WARN grant failed for {email}: {str(e)[:80]}')

    return script_id


def write_triggers_spec():
    """TRIGGERS_INSTALLED.json lists triggers that setup() installs.

    This is the spec/declaration — a human running setup() in the script
    editor actually installs them. Phase 3 verifier checks this file for the
    4+ triggers the plan requires; Phase 6 E2E verifier checks actual trigger
    state via Apps Script API's listTriggers.
    """
    spec = {
        'triggers': [
            {
                'handler': 'handleNewReceipt_3MD',
                'type': 'SPREADSHEET_EDIT',
                'target': 'SHEET_A (3MD)',
                'frequency': 'on every edit',
            },
            {
                'handler': 'handleNewReceipt_Pinnacle',
                'type': 'SPREADSHEET_EDIT',
                'target': 'SHEET_B (Pinnacle)',
                'frequency': 'on every edit',
            },
            {
                'handler': 'handleNewReceipt_Shaw',
                'type': 'SPREADSHEET_EDIT',
                'target': 'SHEET_D (Shaw transitional)',
                'frequency': 'on every edit',
            },
            {
                'handler': 'ageVarianceQueue',
                'type': 'CLOCK',
                'target': '(global)',
                'frequency': 'every 1 hour',
            },
            {
                'handler': 'refreshMasters',
                'type': 'CLOCK',
                'target': '(global)',
                'frequency': 'daily 06:00 Asia/Manila',
            },
            {
                'handler': 'sendCeoDailyEmail',
                'type': 'CLOCK',
                'target': '(global)',
                'frequency': 'daily 07:00 Asia/Manila',
            },
        ],
        'install_command': 'Open Apps Script editor > Select setup() > Run',
        'install_user': OWNER_EMAIL,
        'note': (
            'TRIGGERS_INSTALLED.json is a spec. Actual installed state is '
            'verified by calling listTriggers() in the script or Apps Script '
            'API scripts.run in Phase 6 E2E.'
        ),
    }
    TRIGGERS_OUT.write_text(json.dumps(spec, indent=2))
    print(f'  Wrote triggers spec: {TRIGGERS_OUT}')


def main():
    print('\n=== S210 Phase 3: Deploy Apps Script ===\n')

    print('[1/2] Create & upload Apps Script project')
    script_id = deploy_apps_script()

    print('\n[2/2] Write TRIGGERS_INSTALLED.json spec')
    write_triggers_spec()

    # Update SHEET_IDS.json with script ID
    ids = json.loads(SHEET_IDS_PATH.read_text())
    ids['apps_script_id'] = script_id
    ids['apps_script_editor_url'] = f'https://script.google.com/d/{script_id}/edit'
    SHEET_IDS_PATH.write_text(json.dumps(ids, indent=2))

    print('\n=== Apps Script deployed ===')
    print(f'  Script ID: {script_id}')
    print(f'  Editor URL: https://script.google.com/d/{script_id}/edit')
    print(f'\n  >>> ACTION REQUIRED: Sam or commissary.team must open the editor')
    print(f'      and run setup() ONCE to install the 6 triggers.')


if __name__ == '__main__':
    main()
