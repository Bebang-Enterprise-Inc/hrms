"""verify_phase2.py — S255 Phase 2 gate."""
from __future__ import annotations
import json
import sys
from pathlib import Path
from google.oauth2 import service_account
from googleapiclient.discovery import build

ROOT = Path(__file__).resolve().parents[2]
CREDS_PATH = "F:/Dropbox/Projects/BEI-ERP/credentials/task-manager-service.json"
AP_MASTER_ID = "1bQ6mO1FXD4VYcLt8m-yklkV7pyYhSWqU7b8K0bVgG7c"
V39_PATH = ROOT / "scripts" / "google_apps" / "s255_ap_view_hourly_sync_v39.gs"


def fail(m): print(f"[FAIL] {m}", file=sys.stderr); sys.exit(1)
def ok(m): print(f"[OK]   {m}")


def main():
    creds = service_account.Credentials.from_service_account_file(
        CREDS_PATH, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
    ).with_subject("sam@bebang.ph")
    sheets = build("sheets", "v4", credentials=creds, cache_discovery=False)

    # 1) Intercompany tab exists with protectedRangeId + 19 cols
    meta = sheets.spreadsheets().get(spreadsheetId=AP_MASTER_ID, fields="sheets(properties(sheetId,title,gridProperties),protectedRanges(protectedRangeId,description))").execute()
    inter = next((s for s in meta["sheets"] if s["properties"]["title"] == "Intercompany"), None)
    if not inter: fail("Intercompany tab missing")
    if inter["properties"]["gridProperties"]["columnCount"] != 19:
        fail(f"Intercompany cols = {inter['properties']['gridProperties']['columnCount']}, expected 19")
    if not inter.get("protectedRanges") or not any("S255" in (pr.get("description") or "") for pr in inter["protectedRanges"]):
        fail("Intercompany not strict-locked (no S255 protectedRange)")
    ok(f"Intercompany tab exists with 19 cols + protectedRange")

    # 2) routing log
    log_path = ROOT / "output" / "s255" / "intercompany_routing_log.json"
    if not log_path.exists(): fail(f"missing {log_path}")
    log = json.loads(log_path.read_text(encoding="utf-8"))
    if log["migrated_rows"] < 15: fail(f"migrated only {log['migrated_rows']} rows, < 15 (plan requirement)")
    ok(f"migrated {log['migrated_rows']} rows; {log['ambiguous_rows_count']} ambiguous logged")

    # 3) ambiguous log exists
    amb_path = ROOT / "output" / "s255" / "intercompany_ambiguous.json"
    if not amb_path.exists(): fail(f"missing {amb_path}")
    ok(f"ambiguous log present: {amb_path.name}")

    # 4) v3.9 has 3 predicate regexes
    src = V39_PATH.read_text(encoding="utf-8")
    if "/^Bebang\\s+(Enterprise|Kitchen|Shaw)\\s+Inc\\.?/i" not in src: fail("PAYEE Bebang regex missing in v3.9")
    if "/(transfer (of )?fund|cash sweep|intercompany)/i" not in src: fail("transfer-keyword regex missing in v3.9")
    if "/HDMF|SSS|PHIC|PHILHEALTH|BIR|PAG-?IBIG|CONTRIBUTION|RENTAL|FINAL PAY/i" not in src: fail("govt-keyword negative regex missing in v3.9")
    ok("v3.9 has all 3 predicate regexes")

    # 5) v3.9 has existingIndex 4-tab forEach AND status sync 4-tab AND FPM seed newRowsByTab Intercompany key
    if "'Suppliers SOA', 'Head Office', 'CAPEX', 'Intercompany'" not in src:
        fail("v3.9 existingIndex / sync iteration not extended to 4 tabs")
    occ = src.count("'Suppliers SOA', 'Head Office', 'CAPEX', 'Intercompany'")
    if occ < 2: fail(f"v3.9 4-tab forEach only appears {occ}x, expected >=2 (existingIndex + status sync)")
    ok(f"v3.9 4-tab forEach appears {occ}x (existingIndex + status sync)")

    if "'Suppliers SOA': [], 'Head Office': [], 'CAPEX': [], 'Intercompany': []" not in src:
        fail("v3.9 FPM seed newRowsByTab missing Intercompany key")
    ok("v3.9 FPM seed newRowsByTab includes Intercompany")

    # 6) v3.9 has isIntercompany detection + targetTab routing
    if "isIntercompany = true" not in src: fail("v3.9 isIntercompany detection missing")
    if "targetTab = 'Intercompany'" not in src: fail("v3.9 targetTab=Intercompany routing missing")
    if "intercompany_count" not in src: fail("v3.9 intercompany_count stats missing")
    ok("v3.9 Intercompany routing block + stats wired")

    print("\n[PASS] Phase 2 gate — all assertions met")


if __name__ == "__main__":
    main()
