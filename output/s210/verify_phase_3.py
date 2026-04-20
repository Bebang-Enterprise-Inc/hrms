"""S210 Phase 3 verifier. Exit 0 = PASS.

Checks:
- scripts/google_apps/s210_master_handler.gs exists
- .gs contains function names: validateReceipt, handleNewReceipt_3MD,
  handleNewReceipt_Pinnacle, handleNewReceipt_Shaw, postChatNotification,
  ageVarianceQueue, setup, handleSiUpload
- .gs contains both Chat space IDs (SCM + Procurement Notifications)
- scripts/google_apps/s210_appsscript.json manifest exists with V8 runtime
- output/s210/TRIGGERS_INSTALLED.json lists >=4 triggers
- SHEET_IDS.json contains apps_script_id
"""
import json, sys, pathlib
sys.stdout.reconfigure(encoding='utf-8')

ROOT = pathlib.Path(r'F:\Dropbox\Projects\BEI-ERP-s210')

GS_PATH = ROOT / 'scripts/google_apps/s210_master_handler.gs'
MANIFEST_PATH = ROOT / 'scripts/google_apps/s210_appsscript.json'
TRIGGERS_PATH = ROOT / 'output/s210/TRIGGERS_INSTALLED.json'
SHEET_IDS_PATH = ROOT / 'output/s210/SHEET_IDS.json'

REQUIRED_FUNCTIONS = [
    'validateReceipt',
    'handleNewReceipt_3MD',
    'handleNewReceipt_Pinnacle',
    'handleNewReceipt_Shaw',
    'postChatNotification',
    'ageVarianceQueue',
    'refreshMasters',
    'sendCeoDailyEmail',
    'handleSiUpload',
    'setup',
]

REQUIRED_SPACE_IDS = [
    'spaces/AAQArCi8zjE',    # SCM
    'spaces/AAQAYAYwPPk',    # Procurement App Notifications
]


def main():
    failures = []

    if not GS_PATH.exists():
        print(f'[FAIL] {GS_PATH} missing')
        sys.exit(1)
    if not MANIFEST_PATH.exists():
        print(f'[FAIL] {MANIFEST_PATH} missing')
        sys.exit(1)

    gs = GS_PATH.read_text(encoding='utf-8')
    for fn in REQUIRED_FUNCTIONS:
        if f'function {fn}' not in gs and f'function {fn}(' not in gs:
            failures.append(f'.gs missing function: {fn}')

    for space in REQUIRED_SPACE_IDS:
        if space not in gs:
            failures.append(f'.gs missing Chat space ID: {space}')

    # Manifest checks
    try:
        manifest = json.loads(MANIFEST_PATH.read_text())
        if manifest.get('runtimeVersion') != 'V8':
            failures.append(f'manifest runtimeVersion != V8 (got {manifest.get("runtimeVersion")})')
        scopes = manifest.get('oauthScopes', [])
        required_scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/script.external_request',
            'https://www.googleapis.com/auth/script.scriptapp',
        ]
        missing_scopes = [s for s in required_scopes if s not in scopes]
        if missing_scopes:
            failures.append(f'manifest missing scopes: {missing_scopes}')
    except Exception as e:
        failures.append(f'manifest parse failed: {e}')

    # Triggers spec
    if not TRIGGERS_PATH.exists():
        failures.append(f'{TRIGGERS_PATH} missing')
    else:
        try:
            triggers = json.loads(TRIGGERS_PATH.read_text())
            trigger_list = triggers.get('triggers', [])
            if len(trigger_list) < 4:
                failures.append(f'TRIGGERS_INSTALLED.json lists {len(trigger_list)} triggers (need >=4)')
            # Require at least onEdit A + onEdit B + 1 CLOCK
            handlers = [t.get('handler') for t in trigger_list]
            if 'handleNewReceipt_3MD' not in handlers:
                failures.append('TRIGGERS_INSTALLED.json missing handleNewReceipt_3MD')
            if 'handleNewReceipt_Pinnacle' not in handlers:
                failures.append('TRIGGERS_INSTALLED.json missing handleNewReceipt_Pinnacle')
            if 'ageVarianceQueue' not in handlers:
                failures.append('TRIGGERS_INSTALLED.json missing ageVarianceQueue')
        except Exception as e:
            failures.append(f'TRIGGERS_INSTALLED.json parse failed: {e}')

    # Apps Script project ID present
    if not SHEET_IDS_PATH.exists():
        failures.append(f'{SHEET_IDS_PATH} missing')
    else:
        ids = json.loads(SHEET_IDS_PATH.read_text())
        if not ids.get('apps_script_id'):
            failures.append('SHEET_IDS.json missing apps_script_id')

    print('\n=== S210 Phase 3 Verifier ===\n')
    if failures:
        for f in failures:
            print(f'[FAIL] {f}')
        print(f'\n{len(failures)} failures')
        sys.exit(1)

    print(f'[PASS] {GS_PATH.name} exists')
    print(f'[PASS] {MANIFEST_PATH.name} exists with V8 runtime')
    print(f'[PASS] All {len(REQUIRED_FUNCTIONS)} required functions present in .gs')
    print(f'[PASS] Both Chat space IDs in .gs')
    print(f'[PASS] TRIGGERS_INSTALLED.json lists {len(json.loads(TRIGGERS_PATH.read_text()).get("triggers", []))} triggers')
    print(f'[PASS] Apps Script project ID captured in SHEET_IDS.json')
    print('\nAll checks passed.')
    sys.exit(0)


if __name__ == '__main__':
    main()
