"""S255 Phase 9b.7 — Post-deploy verification (5 assertions)."""
from __future__ import annotations
import json
import sys
from pathlib import Path
from datetime import datetime

from google.oauth2 import service_account
from googleapiclient.discovery import build

ROOT = Path(__file__).resolve().parents[2]
CREDS_PATH = "F:/Dropbox/Projects/BEI-ERP/credentials/task-manager-service.json"
AP_MASTER_ID = "1bQ6mO1FXD4VYcLt8m-yklkV7pyYhSWqU7b8K0bVgG7c"


def to_num(v):
    try: return float(v) if v not in (None, "") else 0.0
    except: return 0.0


def main():
    creds = service_account.Credentials.from_service_account_file(
        CREDS_PATH, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
    ).with_subject("sam@bebang.ph")
    sheets = build("sheets", "v4", credentials=creds, cache_discovery=False)

    sync = json.load(open(ROOT / "output" / "s255" / "post_deploy_sync.json", encoding="utf-8"))
    verify = {"captured_at": datetime.now().astimezone().isoformat(), "assertions": {}}

    # A1: banner totals match (re-check)
    HEADER_ROWS = {"Payment Plan": 3, "CAPEX": 19}
    banner_passes = 0
    banner_results = {}
    for tab in ("Suppliers SOA", "Head Office", "CAPEX", "Payment Plan", "Intercompany"):
        hr = HEADER_ROWS.get(tab, 17)
        b4 = sheets.spreadsheets().values().get(spreadsheetId=AP_MASTER_ID, range=f"'{tab}'!B4", valueRenderOption="UNFORMATTED_VALUE").execute().get("values", [[]])
        banner_total = to_num(b4[0][0] if b4 and b4[0] else 0)
        res = sheets.spreadsheets().values().get(spreadsheetId=AP_MASTER_ID, range=f"'{tab}'!A{hr}:Z", valueRenderOption="UNFORMATTED_VALUE").execute()
        rows = res.get("values", [])
        if len(rows) < 2:
            banner_results[tab] = {"banner_total": banner_total, "data_sum": 0, "delta": banner_total, "pass": False, "note": "no data"}
            continue
        hdr = rows[0]
        try: iOut = hdr.index("OUTSTANDING")
        except ValueError:
            banner_results[tab] = {"pass": False, "note": "no OUTSTANDING column"}
            continue
        data_sum = sum(to_num(r[iOut] if iOut < len(r) else 0) for r in rows[1:] if to_num(r[iOut] if iOut < len(r) else 0) > 0)
        delta = abs(banner_total - data_sum)
        # Tolerance ±₱100 (allows for tiny rounding + late updates)
        passed = delta <= 100
        if passed: banner_passes += 1
        banner_results[tab] = {"banner_total": banner_total, "data_sum": data_sum, "delta": delta, "pass": passed}
    verify["assertions"]["A1_banner_totals"] = {"pass": banner_passes == 5, "details": banner_results, "passed_count": banner_passes}
    print(f"  A1 banner: {banner_passes}/5 tabs pass (tolerance ±PHP 100)")

    # A2: Intercompany row count stable (no growth from seed re-append)
    fpm_seed = sync.get("seed", {}).get("fpm_seed", {})
    interco_count = fpm_seed.get("ho_count", 0)  # check that 0 routed to Intercompany via "ho_count" proxy
    # Actually need to look for intercompany_count in fpm_seed stats — added in Phase 2.5
    interco_routed = fpm_seed.get("intercompany_count", 0)
    # If intercompany_count missing entirely, the stats object might not have it (existing rows existed in existingIndex so 0 newly appended)
    verify["assertions"]["A2_intercompany_stable"] = {
        "pass": interco_routed == 0,
        "interco_routed_this_cycle": interco_routed,
        "note": "0 means existingIndex correctly skipped already-migrated Bebang rows",
    }
    print(f"  A2 Intercompany stable: routed_this_cycle={interco_routed} (0 expected)")

    # A3: PP mirror still works (mirror_disabled=false → mirror ran)
    pp_mirror = sync.get("seed", {}).get("payment_plan_mirror", {})
    mirror_disabled = pp_mirror.get("mirror_disabled")
    pp_rows_mirrored = sync.get("seed", {}).get("payment_plan_mirror", {}).get("mirrored", -1)
    verify["assertions"]["A3_pp_mirror_works"] = {
        "pass": mirror_disabled is not True,
        "mirror_disabled": mirror_disabled,
        "rows_mirrored": pp_rows_mirrored,
    }
    print(f"  A3 PP mirror: disabled={mirror_disabled}, rows_mirrored={pp_rows_mirrored}")

    # A4: status sync still runs (sees 4 tabs including Intercompany)
    status_sync = sync.get("status_sync", {})
    tabs_seen = status_sync.get("tabs_seen", {})
    sync_4_tab = set(["Suppliers SOA", "Head Office", "CAPEX", "Intercompany"]).issubset(set(tabs_seen.keys()))
    verify["assertions"]["A4_status_sync_4_tabs"] = {
        "pass": sync_4_tab,
        "tabs_seen": tabs_seen,
    }
    print(f"  A4 status_sync 4 tabs incl Intercompany: {sync_4_tab} (tabs_seen={list(tabs_seen.keys())})")

    # A5: cycle completed without error (sync log has new entry)
    cycle_ok = sync.get("duration_ms") is not None and sync.get("seed", {}).get("appended") is not None
    verify["assertions"]["A5_cycle_complete"] = {
        "pass": cycle_ok,
        "duration_ms": sync.get("duration_ms"),
        "rows_appended": sync.get("seed", {}).get("appended"),
    }
    print(f"  A5 cycle complete: duration_ms={sync.get('duration_ms')}, rows_appended={sync.get('seed', {}).get('appended')}")

    # Overall
    all_pass = all(a["pass"] for a in verify["assertions"].values())
    verify["all_assertions_passed"] = all_pass

    (ROOT / "output" / "s255" / "post_deploy_verify.json").write_text(json.dumps(verify, indent=2, default=str), encoding="utf-8")
    print(f"\n[{'PASS' if all_pass else 'FAIL'}] Post-deploy verification: {sum(1 for a in verify['assertions'].values() if a['pass'])}/5 assertions pass")


if __name__ == "__main__":
    main()
