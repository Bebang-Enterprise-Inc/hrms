"""verify_phase1.py — S255 Phase 1 gate."""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build

ROOT = Path(__file__).resolve().parents[2]
CREDS_PATH = "F:/Dropbox/Projects/BEI-ERP/credentials/task-manager-service.json"
AP_MASTER_ID = "1bQ6mO1FXD4VYcLt8m-yklkV7pyYhSWqU7b8K0bVgG7c"
V39_PATH = ROOT / "scripts" / "google_apps" / "s255_ap_view_hourly_sync_v39.gs"


def fail(msg): print(f"[FAIL] {msg}", file=sys.stderr); sys.exit(1)
def ok(msg): print(f"[OK]   {msg}")


def main():
    creds = service_account.Credentials.from_service_account_file(
        CREDS_PATH, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
    ).with_subject("sam@bebang.ph")
    sheets = build("sheets", "v4", credentials=creds, cache_discovery=False)

    # Sheet assertions
    meta = sheets.spreadsheets().get(spreadsheetId=AP_MASTER_ID, fields="sheets(properties(title,gridProperties(columnCount)))").execute()
    grids = {s["properties"]["title"]: s["properties"]["gridProperties"]["columnCount"] for s in meta["sheets"]}

    if grids.get("Suppliers SOA") != 19: fail(f"SOA cols = {grids.get('Suppliers SOA')}, expected 19")
    ok("SOA cols = 19")
    if grids.get("Head Office") != 19: fail(f"HO cols = {grids.get('Head Office')}, expected 19")
    ok("HO cols = 19")
    if grids.get("CAPEX") != 20: fail(f"CAPEX cols = {grids.get('CAPEX')}, expected 20")
    ok("CAPEX cols = 20")
    if grids.get("Payment Plan") != 30: fail(f"PP cols = {grids.get('Payment Plan')}, expected 30 (unchanged)")
    ok("PP cols = 30 (unchanged)")

    # Header assertions
    for tab, cell, expected in [
        ("Suppliers SOA", "O17", "GOODS/SERVICES"),
        ("Head Office", "O17", "GOODS/SERVICES"),
        ("CAPEX", "O19", "GOODS/SERVICES"),
        ("Payment Plan", "O3", "BILLED ENTITY"),
        ("Payment Plan", "W3", "GOODS/SERVICES"),  # col 23 unchanged
    ]:
        v = sheets.spreadsheets().values().get(spreadsheetId=AP_MASTER_ID, range=f"'{tab}'!{cell}").execute().get("values", [[]])
        actual = v[0][0] if v and v[0] else None
        if actual != expected: fail(f"{tab} {cell} = {actual!r}, expected {expected!r}")
        ok(f"{tab} {cell} = {expected!r}")

    # v3.9 source assertions
    if not V39_PATH.exists(): fail(f"v3.9 source missing: {V39_PATH}")
    src = V39_PATH.read_text(encoding="utf-8")
    sz = len(src.encode("utf-8"))
    if not (84000 <= sz <= 90000): fail(f"v3.9 size {sz} unexpected (expected ~85K)")
    ok(f"v3.9 source size = {sz} bytes")

    lines = src.split("\n")
    if "GOODS/SERVICES" not in lines[69]: fail(f"v3.9 line 70 missing GOODS/SERVICES: {lines[69]!r}")
    if "hi('GOODS/SERVICES')" not in lines[505]: fail(f"v3.9 line 506 missing hi('GOODS/SERVICES'): {lines[505]!r}")
    if "hi('GOODS/SERVICES')" not in lines[667]: fail(f"v3.9 line 668 missing hi('GOODS/SERVICES'): {lines[667]!r}")
    if "GOODS/SERVICES" not in lines[1034]: fail(f"v3.9 line 1035 missing GOODS/SERVICES: {lines[1034]!r}")
    ok("v3.9 source has GOODS/SERVICES at all 4 rename targets")

    # Internal classification key preserved (>= 10 lowercase refs)
    lower_count = len(re.findall(r"\bclassification\b", src))
    if lower_count < 10: fail(f"v3.9 has only {lower_count} lowercase 'classification' refs, expected >=10 (internal field key)")
    ok(f"v3.9 internal classification field key: {lower_count} refs preserved")

    print("\n[PASS] Phase 1 gate — all assertions met")


if __name__ == "__main__":
    main()
