"""S210 Phase 8 — switch from Apps Script triggers to Cloud Scheduler.

Per the google skill (section "Cloud Scheduler pattern", line 283+), the
preferred production pattern for Apps Script cron is:
  deploy script as web app + Cloud Scheduler HTTP-pings the web-app URL

This script:
  1. Re-uploads s210_master_handler.gs + manifest (with webapp + executionApi)
  2. Creates an Apps Script version
  3. Creates a web-app deployment -> captures the public /exec URL
  4. Enables Cloud Scheduler API on quiet-walker-475722-s2 (if not already)
  5. Creates 4 Scheduler jobs in asia-southeast1 (Asia/Manila cron):
       - s210-poll-all              */1 * * * *    -> pollAll
       - s210-age-variance-hourly   0 * * * *      -> ageVarianceQueue
       - s210-refresh-masters-06    0 6 * * *      -> refreshMasters
       - s210-ceo-email-07          0 7 * * *      -> sendCeoDailyEmail
  6. Writes deployment URL + job names to SHEET_IDS.json + CLOUD_SCHEDULER.json

Run:
    python output/s210/phase8_cloud_scheduler.py
"""
import json, pathlib, sys, time
sys.stdout.reconfigure(encoding='utf-8')
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

ROOT = pathlib.Path(__file__).resolve().parents[2]
SA = pathlib.Path(r'F:\Dropbox\Projects\BEI-ERP\credentials\task-manager-service.json')

SHEET_IDS_PATH = ROOT / 'output/s210/SHEET_IDS.json'
CLOUD_SCHED_PATH = ROOT / 'output/s210/CLOUD_SCHEDULER.json'

GCP_PROJECT = 'quiet-walker-475722-s2'
SCHEDULER_LOCATION = 'asia-southeast1'
SHARED_TOKEN = 's210-b3i-a8F2kQ9mZv7RpYxLnCdT4wE6hG1jN5uH0sK3'

JOB_SPECS = [
    {
        'name': 's210-poll-all',
        'schedule': '*/1 * * * *',
        'fn': 'pollAll',
        'description': 'S210: poll Sheets A/B/D Receipts + SI Upload form every 1 min',
        'attempt_deadline_seconds': 120,
    },
    {
        'name': 's210-age-variance-hourly',
        'schedule': '0 * * * *',
        'fn': 'ageVarianceQueue',
        'description': 'S210: move DRs >72h without SI match into Variance Queue',
        'attempt_deadline_seconds': 180,
    },
    {
        'name': 's210-refresh-masters-06',
        'schedule': '0 6 * * *',
        'fn': 'refreshMasters',
        'description': 'S210: daily 06:00 PHT pull from Procurement AppSheet',
        'attempt_deadline_seconds': 300,
    },
    {
        'name': 's210-ceo-email-07',
        'schedule': '0 7 * * *',
        'fn': 'sendCeoDailyEmail',
        'description': 'S210: daily 07:00 PHT CEO KPI digest to sam+ian',
        'attempt_deadline_seconds': 120,
    },
]


def creds_dwd(scopes, subject='sam@bebang.ph'):
    return service_account.Credentials.from_service_account_file(
        str(SA), scopes=scopes).with_subject(subject)


def creds_gcp(scopes):
    # No .with_subject — GCP management uses service account's own IAM roles
    return service_account.Credentials.from_service_account_file(
        str(SA), scopes=scopes)


def reupload_script(ids):
    script_api = build('script', 'v1', credentials=creds_dwd(
        ['https://www.googleapis.com/auth/script.projects',
         'https://www.googleapis.com/auth/script.deployments']
    ), cache_discovery=False)

    gs = (ROOT / 'scripts/google_apps/s210_master_handler.gs').read_text(encoding='utf-8')
    manifest = (ROOT / 'scripts/google_apps/s210_appsscript.json').read_text(encoding='utf-8')

    cur = script_api.projects().getContent(scriptId=ids['apps_script_id']).execute()
    new_files = []
    for f in cur.get('files', []):
        if f['name'] == 'appsscript':
            new_files.append({'name': 'appsscript', 'type': 'JSON', 'source': manifest})
        elif f['name'] == 's210_master_handler':
            new_files.append({'name': 's210_master_handler', 'type': 'SERVER_JS', 'source': gs})
        else:
            new_files.append({'name': f['name'], 'type': f['type'], 'source': f['source']})

    script_api.projects().updateContent(
        scriptId=ids['apps_script_id'], body={'files': new_files},
    ).execute()
    print(f'  Re-uploaded .gs + manifest to {ids["apps_script_id"]}')
    return script_api


def create_version_and_deployment(script_api, script_id):
    # Create a new version
    v = script_api.projects().versions().create(
        scriptId=script_id,
        body={'description': 'S210 Phase 8 — web app + Cloud Scheduler'},
    ).execute()
    version_num = v['versionNumber']
    print(f'  Created version {version_num}')

    # Create deployment
    d = script_api.projects().deployments().create(
        scriptId=script_id,
        body={
            'versionNumber': version_num,
            'manifestFileName': 'appsscript',
            'description': f'S210 Phase 8 web app (v{version_num})',
        },
    ).execute()
    deployment_id = d['deploymentId']
    print(f'  Created deployment {deployment_id}')

    # Find the web-app URL
    web_url = None
    for ep in d.get('entryPoints', []):
        if ep.get('entryPointType') == 'WEB_APP':
            web_url = ep['webApp']['url']
            break

    if not web_url:
        # Fallback: construct from deployment id
        web_url = f'https://script.google.com/macros/s/{deployment_id}/exec'
        print(f'  WARN: web-app URL not in entryPoints; using fallback')

    return deployment_id, web_url


def enable_scheduler_api():
    creds = creds_gcp(['https://www.googleapis.com/auth/cloud-platform'])
    su = build('serviceusage', 'v1', credentials=creds, cache_discovery=False)

    # Check if already enabled
    svc_name = f'projects/{GCP_PROJECT}/services/cloudscheduler.googleapis.com'
    info = su.services().get(name=svc_name).execute()
    if info.get('state') == 'ENABLED':
        print('  Cloud Scheduler API already enabled')
        return

    print('  Enabling Cloud Scheduler API...')
    op = su.services().enable(name=svc_name).execute()
    for _ in range(20):
        time.sleep(3)
        status = su.operations().get(name=op['name']).execute()
        if status.get('done'):
            print('  Cloud Scheduler API enabled')
            return
    print('  WARN: enable op did not complete in 60s; proceeding anyway')


def create_or_update_job(sched, web_url, spec):
    parent = f'projects/{GCP_PROJECT}/locations/{SCHEDULER_LOCATION}'
    job_name = f'{parent}/jobs/{spec["name"]}'
    uri = f'{web_url}?key={SHARED_TOKEN}&fn={spec["fn"]}'

    body = {
        'name': job_name,
        'description': spec['description'],
        'schedule': spec['schedule'],
        'timeZone': 'Asia/Manila',
        'httpTarget': {
            'uri': uri,
            'httpMethod': 'GET',
        },
        'attemptDeadline': f'{spec["attempt_deadline_seconds"]}s',
        'retryConfig': {
            'retryCount': 3,
            'minBackoffDuration': '30s',
            'maxBackoffDuration': '300s',
        },
    }

    try:
        job = sched.projects().locations().jobs().create(parent=parent, body=body).execute()
        print(f'  Created job: {spec["name"]}')
        return job
    except HttpError as e:
        if e.resp.status == 409:  # already exists
            # Update instead
            job = sched.projects().locations().jobs().patch(
                name=job_name,
                updateMask='description,schedule,timeZone,httpTarget,attemptDeadline,retryConfig',
                body=body,
            ).execute()
            print(f'  Updated existing job: {spec["name"]}')
            return job
        raise


def main():
    print('\n=== S210 Phase 8: Cloud Scheduler migration ===\n')

    ids = json.loads(SHEET_IDS_PATH.read_text())

    print('[1/4] Re-upload .gs + manifest (webapp + executionApi)')
    script_api = reupload_script(ids)

    print('\n[2/4] Create version + web-app deployment')
    deployment_id, web_url = create_version_and_deployment(script_api, ids['apps_script_id'])
    print(f'  Web-app URL: {web_url}')

    # Smoke-test: ping?fn=ping
    import urllib.request, urllib.parse
    test_url = f'{web_url}?{urllib.parse.urlencode({"key": SHARED_TOKEN, "fn": "ping"})}'
    print(f'\n  Testing: {test_url[:120]}...')
    try:
        with urllib.request.urlopen(test_url, timeout=30) as r:
            body = r.read().decode('utf-8')
        print(f'  Ping response: {body[:200]}')
    except Exception as e:
        print(f'  WARN ping failed: {str(e)[:200]} (job creation continues)')

    print('\n[3/4] Enable Cloud Scheduler API')
    enable_scheduler_api()

    print('\n[4/4] Create Scheduler jobs')
    sched = build('cloudscheduler', 'v1', credentials=creds_gcp(
        ['https://www.googleapis.com/auth/cloud-platform']
    ), cache_discovery=False)

    created_jobs = []
    for spec in JOB_SPECS:
        j = create_or_update_job(sched, web_url, spec)
        created_jobs.append({
            'name': spec['name'],
            'full_name': j.get('name', ''),
            'schedule': spec['schedule'],
            'fn': spec['fn'],
            'state': j.get('state', ''),
        })

    # Persist
    cloud_meta = {
        'deployment_id': deployment_id,
        'web_app_url': web_url,
        'shared_token_masked': SHARED_TOKEN[:12] + '...' + SHARED_TOKEN[-4:],
        'gcp_project': GCP_PROJECT,
        'scheduler_location': SCHEDULER_LOCATION,
        'jobs': created_jobs,
    }
    CLOUD_SCHED_PATH.write_text(json.dumps(cloud_meta, indent=2), encoding='utf-8')
    print(f'\n  Wrote {CLOUD_SCHED_PATH}')

    ids['apps_script_deployment_id'] = deployment_id
    ids['apps_script_web_app_url'] = web_url
    ids['cloud_scheduler_jobs'] = [j['name'] for j in created_jobs]
    ids['si_upload_form_file_upload_pending_ui_step'] = False  # UI step done
    SHEET_IDS_PATH.write_text(json.dumps(ids, indent=2))

    print('\n=== Phase 8 complete ===')
    print(f'  {len(created_jobs)} Scheduler jobs live in {SCHEDULER_LOCATION}')
    for j in created_jobs:
        print(f'    {j["name"]:35} {j["schedule"]:15} -> {j["fn"]}')


if __name__ == '__main__':
    main()
