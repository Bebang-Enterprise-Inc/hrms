# S256 Rollback Runbook — v3.10 to v3.9

## Trigger Conditions (any one fires)

- Banner shows wrong totals (delta > PHP 100 vs data sum)
- `_sync_log_v3` shows error rate > 0 in first 2 cycles after promote
- Procurement App seed writes bad data (wrong supplier, wrong amount)
- Sam reports broken behavior

## Rollback Steps

1. **Pause Cloud Scheduler:**
   ```bash
   gcloud scheduler jobs pause ap-auto-view-hourly-refresh --project=quiet-walker-475722-s2 --location=asia-southeast1
   ```

2. **Read v3.9 backup from committed evidence:**
   - File: `output/s256/script_source_backup_v39.gs` (95,031 bytes)
   - This file is committed to git — survives worktree removal

3. **Push v3.9 source back to Apps Script:**
   ```python
   from google.oauth2 import service_account
   from googleapiclient.discovery import build
   SA_FILE = 'credentials/task-manager-service.json'
   creds = service_account.Credentials.from_service_account_file(SA_FILE, scopes=['https://www.googleapis.com/auth/script.projects']).with_subject('sam@bebang.ph')
   svc = build('script', 'v1', credentials=creds)
   v39_code = open('output/s256/script_source_backup_v39.gs').read()
   svc.projects().updateContent(scriptId='1pE8wt_z8NA9q__PNbUilJ72UE0_EI3DmurJekkw6mbgtHr8hosnKsNRF', body={'files': [{'name': 'ap_view_hourly_sync_v3', 'type': 'SERVER_JS', 'source': v39_code}]}).execute()
   v = svc.projects().versions().create(scriptId='1pE8wt_z8NA9q__PNbUilJ72UE0_EI3DmurJekkw6mbgtHr8hosnKsNRF', body={'description': 'ROLLBACK to v3.9 from S256'}).execute()
   print(f"Rollback version: {v['versionNumber']}")
   ```

4. **Promote rollback version to production deployment:**
   ```python
   svc.projects().deployments().update(
       scriptId='1pE8wt_z8NA9q__PNbUilJ72UE0_EI3DmurJekkw6mbgtHr8hosnKsNRF',
       deploymentId='AKfycbw-AuqJq6OyMV6DGarGWEruDoez04OETlWFQoeppNjvzoeSOJOomPOZNsVPE9iuV6ZC_Q',
       body={'deploymentConfig': {'versionNumber': v['versionNumber'], 'description': 'ROLLBACK v3.9'}}
   ).execute()
   ```

5. **Verify rollback works** (dry-run):
   ```bash
   curl "https://script.google.com/macros/s/AKfycbw-AuqJq6OyMV6DGarGWEruDoez04OETlWFQoeppNjvzoeSOJOomPOZNsVPE9iuV6ZC_Q/exec?key=bei-ap-sync-2026-04&fn=refreshAllTabs&dryRun=1"
   ```
   Confirm: no `INTERCO_AFFILIATE_PATTERNS`, no `BYPASS_3PL_PATTERNS`, no `procurement_seed` in output.

6. **Resume scheduler:**
   ```bash
   gcloud scheduler jobs resume ap-auto-view-hourly-refresh --project=quiet-walker-475722-s2 --location=asia-southeast1
   ```

## Success Criteria

- v3.9 behavior confirmed (no v3.10 features in dry-run output)
- Next hourly cycle completes without errors
- No new Procurement App-sourced rows appear
- Existing Procurement App-sourced rows remain (they're already in AP Master — rollback doesn't remove data)
