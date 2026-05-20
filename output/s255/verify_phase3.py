"""verify_phase3.py — S255 Phase 3 gate."""
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


def to_num(v):
    try: return float(v) if v not in (None, "") else 0.0
    except (TypeError, ValueError): return 0.0


def main():
    # 1) v3.9 has recomputeBanners_ function + wired into doRefreshAllTabs_v3_
    src = V39_PATH.read_text(encoding="utf-8")
    if "function recomputeBanners_" not in src: fail("recomputeBanners_ function missing")
    if "stats.banners = recomputeBanners_(ss)" not in src: fail("recomputeBanners_ not wired into doRefreshAllTabs_v3_")
    ok("v3.9 has recomputeBanners_ + wired into doRefreshAllTabs_v3_")

    # 2) Banner totals match data sum (±₱1 tolerance for FP rounding)
    creds = service_account.Credentials.from_service_account_file(
        CREDS_PATH, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
    ).with_subject("sam@bebang.ph")
    sheets = build("sheets", "v4", credentials=creds, cache_discovery=False)

    HEADER_ROWS = {"Payment Plan": 3, "CAPEX": 19}
    for tab in ("Suppliers SOA", "Head Office", "CAPEX", "Payment Plan", "Intercompany"):
        header_row = HEADER_ROWS.get(tab, 17)
        banner_b4 = sheets.spreadsheets().values().get(
            spreadsheetId=AP_MASTER_ID, range=f"'{tab}'!B4", valueRenderOption="UNFORMATTED_VALUE",
        ).execute().get("values", [[]])
        banner_total = to_num(banner_b4[0][0] if banner_b4 and banner_b4[0] else 0)

        # Read data, sum OUTSTANDING
        res = sheets.spreadsheets().values().get(
            spreadsheetId=AP_MASTER_ID, range=f"'{tab}'!A{header_row}:Z", valueRenderOption="UNFORMATTED_VALUE",
        ).execute()
        rows = res.get("values", [])
        if len(rows) < 2:
            ok(f"{tab}: no data (banner={banner_total})")
            continue
        hdr = rows[0]
        data = rows[1:]
        try:
            iOut = hdr.index("OUTSTANDING")
        except ValueError:
            fail(f"{tab}: no OUTSTANDING column in header row {header_row}")
        data_sum = sum(to_num(r[iOut] if iOut < len(r) else 0) for r in data if to_num(r[iOut] if iOut < len(r) else 0) > 0)
        delta = abs(banner_total - data_sum)
        if delta > 1.0:
            fail(f"{tab}: banner={banner_total:,.2f}, data_sum={data_sum:,.2f}, delta=₱{delta:,.2f} > ₱1 tolerance")
        ok(f"{tab}: banner=PHP {banner_total:,.2f} matches data sum (delta=PHP {delta:.4f})")

    print("\n[PASS] Phase 3 gate — all banner totals match data sums (within PHP 1)")


if __name__ == "__main__":
    main()
