"""S255 Phase 9b — Dry-run gate + promote + post-deploy verify + closeout prep.

9b.1 Push v3.9 to HEAD + versions.create + deployments.create (staging URL)
9b.2 Invoke ?dryRun=1 against staging URL; capture output
9b.3 Verify dry-run assertions
9b.4 Promote production deployment to v3.9 versionNumber (if dryRun passed)
9b.5 RESUME Cloud Scheduler
9b.6 Trigger one live cycle
9b.7 Post-deploy verification (5 assertions)
9b.8-14 Closeout artifacts (SUMMARY.md, DEFECTS.md, plan/registry updates, PR creation)
"""
from __future__ import annotations
import json
import sys
import time
import urllib.request
from pathlib import Path
from datetime import datetime

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

ROOT = Path(__file__).resolve().parents[2]
CREDS_PATH = "F:/Dropbox/Projects/BEI-ERP/credentials/task-manager-service.json"
SCRIPT_ID = "1pE8wt_z8NA9q__PNbUilJ72UE0_EI3DmurJekkw6mbgtHr8hosnKsNRF"
PRODUCTION_DEPLOYMENT_ID = "AKfycbw-AuqJq6OyMV6DGarGWEruDoez04OETlWFQoeppNjvzoeSOJOomPOZNsVPE9iuV6ZC_Q"
AP_MASTER_ID = "1bQ6mO1FXD4VYcLt8m-yklkV7pyYhSWqU7b8K0bVgG7c"
WEB_APP_TOKEN = "bei-ap-sync-2026-04"

V39_PATH = ROOT / "scripts" / "google_apps" / "s255_ap_view_hourly_sync_v39.gs"


def get_script_api():
    creds = service_account.Credentials.from_service_account_file(
        CREDS_PATH, scopes=["https://www.googleapis.com/auth/script.deployments", "https://www.googleapis.com/auth/script.projects"]
    ).with_subject("sam@bebang.ph")
    return build("script", "v1", credentials=creds, cache_discovery=False)


def get_sheets_api():
    creds = service_account.Credentials.from_service_account_file(
        CREDS_PATH, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
    ).with_subject("sam@bebang.ph")
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def http_get(url, timeout=300):
    """GET with longer timeout for dry-run calls."""
    req = urllib.request.Request(url, headers={"User-Agent": "S255-agent/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8")


def main():
    log = {"phase": "9b", "started_at": datetime.now().astimezone().isoformat(), "tasks": {}}
    script_api = get_script_api()

    # ─────────────────────────────────────────────────────────────
    # 9b.1 — Push v3.9 to HEAD + versions.create + create staging deployment
    # ─────────────────────────────────────────────────────────────
    print("[9b.1] Pushing v3.9 to Apps Script HEAD + creating new version...")
    v39_src = V39_PATH.read_text(encoding="utf-8")
    print(f"  v3.9 size: {len(v39_src.encode('utf-8'))} bytes")

    # Get the current content to find the existing files (we want to preserve appsscript.json + replace Code.gs)
    current = script_api.projects().getContent(scriptId=SCRIPT_ID).execute()
    files_out = []
    code_replaced = False
    for f in current["files"]:
        if f["name"] == "Code":
            f = {**f, "source": v39_src}
            code_replaced = True
        files_out.append(f)
    if not code_replaced:
        print("  WARN: 'Code' file not found in project — adding new")
        files_out.append({"name": "Code", "type": "SERVER_JS", "source": v39_src})

    # updateContent
    update_resp = script_api.projects().updateContent(scriptId=SCRIPT_ID, body={"files": files_out}).execute()
    print(f"  updateContent OK (project at HEAD = v3.9)")

    # versions.create — snapshot HEAD as version N+1
    version_resp = script_api.projects().versions().create(scriptId=SCRIPT_ID, body={
        "description": "S255 v3.9 — Intercompany routing + recomputeBanners_ + Denise PP - Manual + mirror gate + DD section",
    }).execute()
    new_version_number = version_resp["versionNumber"]
    print(f"  versions.create OK — versionNumber = {new_version_number}")
    log["tasks"]["9b.1"] = {"status": "DONE", "version_number": new_version_number, "v39_size": len(v39_src.encode("utf-8"))}

    # Create staging deployment pinned to new version
    staging_dep = script_api.projects().deployments().create(scriptId=SCRIPT_ID, body={
        "versionNumber": new_version_number,
        "manifestFileName": "appsscript",
        "description": "S255 staging — dry-run gate before promote to production",
    }).execute()
    staging_deployment_id = staging_dep["deploymentId"]
    staging_url = next((e.get("webApp", {}).get("url") for e in staging_dep.get("entryPoints", []) if e.get("entryPointType") == "WEB_APP"), None)
    if not staging_url:
        print(f"  WARN: staging deployment created but no webApp URL — entryPoints: {staging_dep.get('entryPoints')}")
        # Construct URL manually
        staging_url = f"https://script.google.com/macros/s/{staging_deployment_id}/exec"
    print(f"  staging deployment created: {staging_deployment_id}")
    print(f"  staging URL: {staging_url[:80]}...")
    (ROOT / "output" / "s255" / "v39_dryrun_deployment.json").write_text(json.dumps({
        "deploymentId": staging_deployment_id,
        "versionNumber": new_version_number,
        "url": staging_url,
        "created_at": datetime.now().astimezone().isoformat(),
    }, indent=2, default=str), encoding="utf-8")

    # ─────────────────────────────────────────────────────────────
    # 9b.2 — Invoke ?dryRun=1 against staging URL
    # ─────────────────────────────────────────────────────────────
    print("[9b.2] Invoking ?dryRun=1 against staging deployment...")
    dryrun_url = f"{staging_url}?key={WEB_APP_TOKEN}&fn=refreshAllTabs&dryRun=1"
    try:
        # Apps Script web apps can take time on cold-start
        dryrun_text = http_get(dryrun_url, timeout=300)
        try:
            dryrun_json = json.loads(dryrun_text)
        except json.JSONDecodeError:
            dryrun_json = {"raw_text": dryrun_text[:500]}
        print(f"  dryRun response received ({len(dryrun_text)} chars)")
        (ROOT / "output" / "s255" / "v39_dryrun.json").write_text(json.dumps(dryrun_json, indent=2, default=str), encoding="utf-8")
    except Exception as e:
        print(f"  ERROR invoking staging dryRun: {e}")
        dryrun_json = {"error": str(e)}
        (ROOT / "output" / "s255" / "v39_dryrun.json").write_text(json.dumps(dryrun_json, indent=2, default=str), encoding="utf-8")

    log["tasks"]["9b.2"] = {"status": "DONE" if "error" not in dryrun_json else "ERROR", "response_keys": list(dryrun_json.keys())[:10] if isinstance(dryrun_json, dict) else None}

    # ─────────────────────────────────────────────────────────────
    # 9b.3 — Verify dry-run assertions
    # ─────────────────────────────────────────────────────────────
    print("[9b.3] Verifying dry-run output...")
    verify = {"all_assertions_passed": True, "assertions": {}}

    def check(name, predicate, detail=""):
        ok = bool(predicate)
        verify["assertions"][name] = {"pass": ok, "detail": detail}
        if not ok:
            verify["all_assertions_passed"] = False
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}")

    if isinstance(dryrun_json, dict) and "error" not in dryrun_json:
        # The dryRun response should be a stats object (from doRefreshAllTabs_v3_)
        check("dryrun_returned_stats", "dry_run" in dryrun_json or "duration_ms" in dryrun_json or "seed" in dryrun_json,
              f"keys: {list(dryrun_json.keys())[:10]}")
        # Sentence: dry_run=true expected
        check("dryRun_mode_was_set", dryrun_json.get("dry_run") is True or "dry_run" in str(dryrun_json),
              f"dry_run flag: {dryrun_json.get('dry_run')}")
        # Sentence: no errors in seed
        seed_stats = dryrun_json.get("seed", {})
        check("no_seed_errors", seed_stats.get("error") is None,
              f"seed stats: {list(seed_stats.keys())[:8] if seed_stats else 'empty'}")
        # Sentence: stats has new structure (intercompany_count or banners or similar)
        whole_str = json.dumps(dryrun_json)
        check("v39_logic_active", "Intercompany" in whole_str or "intercompany" in whole_str or "banners" in whole_str.lower() or "recomputeBanners" in whole_str,
              "new v3.9 logic visible in output" if ("Intercompany" in whole_str or "intercompany" in whole_str or "banners" in whole_str.lower()) else "no v3.9 markers found")
    else:
        check("dryrun_succeeded", False, f"dryrun call failed or returned error: {dryrun_json.get('error', 'unknown')}")

    (ROOT / "output" / "s255" / "v39_dryrun_verify.json").write_text(json.dumps(verify, indent=2, default=str), encoding="utf-8")
    log["tasks"]["9b.3"] = {"status": "PASS" if verify["all_assertions_passed"] else "FAIL", "verify": verify}

    if not verify["all_assertions_passed"]:
        print("\n[!] Dry-run gate FAILED. NOT promoting to production. Staging deployment kept for inspection.")
        print(f"    Inspect: {staging_url}")
        print(f"    Delete staging when done: gcloud / Apps Script API deployments.delete deploymentId={staging_deployment_id}")
        log["finished_at"] = datetime.now().astimezone().isoformat()
        (ROOT / "output" / "s255" / "phase9b_log.json").write_text(json.dumps(log, indent=2, default=str), encoding="utf-8")
        # Don't proceed with deploy — exit signaling failure (but cleanly)
        print("\n=== PHASE 9b ABORTED at dry-run gate ===")
        return 1

    # ─────────────────────────────────────────────────────────────
    # 9b.4 — Promote production deployment to v3.9 version
    # ─────────────────────────────────────────────────────────────
    print(f"[9b.4] Promoting production deployment to versionNumber={new_version_number}...")
    promote_resp = script_api.projects().deployments().update(scriptId=SCRIPT_ID, deploymentId=PRODUCTION_DEPLOYMENT_ID, body={
        "deploymentConfig": {
            "versionNumber": new_version_number,
            "manifestFileName": "appsscript",
            "description": "S255 v3.9 — Intercompany + recomputeBanners_ + Denise PP - Manual + mirror gate",
        }
    }).execute()
    print(f"  Production now on versionNumber={promote_resp.get('deploymentConfig', {}).get('versionNumber')}")
    (ROOT / "output" / "s255" / "v39_deployment.json").write_text(json.dumps({
        "deploymentId": PRODUCTION_DEPLOYMENT_ID,
        "versionNumber": new_version_number,
        "promoted_at": datetime.now().astimezone().isoformat(),
        "promote_response": promote_resp,
    }, indent=2, default=str), encoding="utf-8")
    log["tasks"]["9b.4"] = {"status": "DONE", "versionNumber": new_version_number}

    # Clean up staging deployment now that production has v3.9
    try:
        script_api.projects().deployments().delete(scriptId=SCRIPT_ID, deploymentId=staging_deployment_id).execute()
        print(f"  staging deployment {staging_deployment_id} cleaned up")
    except Exception as e:
        print(f"  WARN: failed to delete staging deployment: {e}")

    log["finished_at"] = datetime.now().astimezone().isoformat()
    (ROOT / "output" / "s255" / "phase9b_log.json").write_text(json.dumps(log, indent=2, default=str), encoding="utf-8")
    print("\n=== Phase 9b.1-9b.4 done — production now on v3.9 ===\nNext: 9b.5 resume scheduler + 9b.6 trigger live sync + 9b.7 verify")


if __name__ == "__main__":
    sys.exit(main() or 0)
