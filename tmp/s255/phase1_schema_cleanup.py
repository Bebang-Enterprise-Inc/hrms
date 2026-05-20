"""S255 Phase 1 — Schema cleanup on entry tabs + v3.9 source build.

Tasks (all in one transaction-like sequence; Cloud Scheduler paused so no race):
  1.1 Read Suppliers SOA row 355 INVOICE DATE; if blank, migrate Remarks value as Date
  1.2 Delete Suppliers SOA col 20 (Remarks)
  1.3-1.5 Resize grids: SOA 19, HO 19, CAPEX 20
  1.6 Rename CLASSIFICATION → GOODS/SERVICES headers (SOA/HO row 17; CAPEX row 19) +
      build v3.9 source from v3.8 backup with 4-line rename
  1.7 Rename Payment Plan col 15 to BILLED ENTITY (avoid duplicate with col 23 GOODS/SERVICES)
  1.8 Verify row 18 col 15 (SOA/HO) preserved data
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path
from datetime import datetime

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

ROOT = Path(__file__).resolve().parents[2]
CREDS_PATH = "F:/Dropbox/Projects/BEI-ERP/credentials/task-manager-service.json"
AP_MASTER_ID = "1bQ6mO1FXD4VYcLt8m-yklkV7pyYhSWqU7b8K0bVgG7c"

V38_PATH = ROOT / "output" / "s255" / "script_source_backup_v38.gs"
V39_PATH = ROOT / "scripts" / "google_apps" / "s255_ap_view_hourly_sync_v39.gs"


def get_sheets(impersonate="sam@bebang.ph"):
    creds = service_account.Credentials.from_service_account_file(
        CREDS_PATH,
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    ).with_subject(impersonate)
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def get_sheet_id(sheets, ss_id, name):
    meta = sheets.spreadsheets().get(spreadsheetId=ss_id, fields="sheets(properties(sheetId,title,gridProperties))").execute()
    for s in meta["sheets"]:
        if s["properties"]["title"] == name:
            return s["properties"]["sheetId"], s["properties"]["gridProperties"]
    raise SystemExit(f"sheet {name!r} not found")


def main():
    sheets = get_sheets()
    log: dict = {
        "phase": "1",
        "started_at": datetime.now().astimezone().isoformat(),
        "tasks": {},
    }

    # ─────────────────────────────────────────────────────────────
    # 1.6a — Build v3.9 source from v3.8 with DISPLAY-only rename
    # ─────────────────────────────────────────────────────────────
    print("[1.6a] Building v3.9 source from v3.8 backup with CLASSIFICATION rename...")
    v38_src = V38_PATH.read_text(encoding="utf-8")
    v39_src = v38_src

    # Verify exact line 70/506/668/1035 match before editing (defense against drift)
    lines = v39_src.split("\n")
    assert "CLASSIFICATION" in lines[69], f"Line 70 expected to contain CLASSIFICATION; got: {lines[69]!r}"
    assert "hi('CLASSIFICATION')" in lines[505], f"Line 506 expected hi('CLASSIFICATION'); got: {lines[505]!r}"
    assert "hi('CLASSIFICATION')" in lines[667], f"Line 668 expected hi('CLASSIFICATION'); got: {lines[667]!r}"
    assert "CLASSIFICATION" in lines[1034], f"Line 1035 expected CLASSIFICATION; got: {lines[1034]!r}"

    # DISPLAY-only rename: change the 4 string occurrences, leave internal `classification` field key alone
    # Line 70: header definition string in COL_NAMES
    # Line 506: hi('CLASSIFICATION') lookup → hi('GOODS/SERVICES')
    # Line 668: hi('CLASSIFICATION') lookup → hi('GOODS/SERVICES')
    # Line 1035: buildGrid header push string
    new_lines = lines.copy()
    new_lines[69] = lines[69].replace("'CLASSIFICATION'", "'GOODS/SERVICES'")
    new_lines[505] = lines[505].replace("hi('CLASSIFICATION')", "hi('GOODS/SERVICES')")
    new_lines[667] = lines[667].replace("hi('CLASSIFICATION')", "hi('GOODS/SERVICES')")
    new_lines[1034] = lines[1034].replace("'CLASSIFICATION'", "'GOODS/SERVICES'")
    v39_src = "\n".join(new_lines)

    # Sanity: no internal lowercase `classification` was touched
    lower_before = sum(1 for ln in lines if "r.classification" in ln or "'classification'" in ln or '"classification"' in ln)
    lower_after = sum(1 for ln in new_lines if "r.classification" in ln or "'classification'" in ln or '"classification"' in ln)
    assert lower_before == lower_after, f"display-only rename broke internal field key: before={lower_before}, after={lower_after}"

    # Also verify 4 uppercase CLASSIFICATION → GOODS/SERVICES occurred
    # Count uppercase occurrences BEFORE and AFTER
    upper_before = v38_src.count("CLASSIFICATION")
    upper_after_v39 = v39_src.count("CLASSIFICATION")
    assert upper_before - upper_after_v39 == 4, f"expected exactly 4 uppercase renames; got delta {upper_before - upper_after_v39}"

    V39_PATH.parent.mkdir(parents=True, exist_ok=True)
    V39_PATH.write_text(v39_src, encoding="utf-8")
    log["tasks"]["1.6a"] = {
        "status": "DONE",
        "v39_size_bytes": len(v39_src.encode("utf-8")),
        "v38_size_bytes": len(v38_src.encode("utf-8")),
        "renames": 4,
        "internal_classification_preserved": True,
        "remaining_uppercase_CLASSIFICATION": upper_after_v39,  # comments + the BILLED TO ref at line 67
    }
    print(f"  v3.9 = {len(v39_src.encode('utf-8'))} bytes; 4 renames; {upper_after_v39} CLASSIFICATION remain (header comments)")

    # ─────────────────────────────────────────────────────────────
    # 1.1 Read Suppliers SOA row 355 INVOICE DATE
    # ─────────────────────────────────────────────────────────────
    print("[1.1] Reading Suppliers SOA row 355 INVOICE DATE (col D)...")
    res = sheets.spreadsheets().values().get(
        spreadsheetId=AP_MASTER_ID,
        range="'Suppliers SOA'!D355",
        valueRenderOption="UNFORMATTED_VALUE",
    ).execute()
    inv_date_val = res.get("values", [[]])[0][0] if res.get("values") else None
    # Also read col 20 (T) row 355
    res_remarks = sheets.spreadsheets().values().get(
        spreadsheetId=AP_MASTER_ID,
        range="'Suppliers SOA'!T355",
        valueRenderOption="UNFORMATTED_VALUE",
    ).execute()
    remarks_val = res_remarks.get("values", [[]])[0][0] if res_remarks.get("values") else None

    log["tasks"]["1.1"] = {
        "row_355_col_D_invoice_date_pre": inv_date_val,
        "row_355_col_T_remarks_pre": remarks_val,
    }

    # If INVOICE DATE blank AND Remarks contains "received:" date, migrate
    if (inv_date_val in (None, "") and remarks_val and "received" in str(remarks_val).lower()):
        # Parse date "received: 5/16/2026" → 2026-05-16
        m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", str(remarks_val))
        if m:
            month, day, year = m.groups()
            date_iso = f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
            # Write as Date (Sheets accepts ISO date string with explicit number format)
            sheets.spreadsheets().values().update(
                spreadsheetId=AP_MASTER_ID,
                range="'Suppliers SOA'!D355",
                valueInputOption="USER_ENTERED",
                body={"values": [[date_iso]]},
            ).execute()
            # Set as date format
            sheet_id_soa, _ = get_sheet_id(sheets, AP_MASTER_ID, "Suppliers SOA")
            sheets.spreadsheets().batchUpdate(spreadsheetId=AP_MASTER_ID, body={
                "requests": [{
                    "repeatCell": {
                        "range": {"sheetId": sheet_id_soa, "startRowIndex": 354, "endRowIndex": 355, "startColumnIndex": 3, "endColumnIndex": 4},
                        "cell": {"userEnteredFormat": {"numberFormat": {"type": "DATE", "pattern": "yyyy-mm-dd"}}},
                        "fields": "userEnteredFormat.numberFormat",
                    }
                }]
            }).execute()
            log["tasks"]["1.1"]["migrated"] = True
            log["tasks"]["1.1"]["new_invoice_date"] = date_iso
            print(f"  MIGRATED: row 355 INVOICE DATE → {date_iso}")
        else:
            log["tasks"]["1.1"]["migrated"] = False
            log["tasks"]["1.1"]["reason"] = "Remarks didn't match m/d/yyyy pattern"
            print(f"  SKIP: Remarks didn't match date pattern: {remarks_val!r}")
    else:
        log["tasks"]["1.1"]["migrated"] = False
        log["tasks"]["1.1"]["reason"] = f"INVOICE DATE not blank (got {inv_date_val!r}) OR Remarks empty/missing"
        print(f"  SKIP: INVOICE DATE={inv_date_val!r}, Remarks={remarks_val!r}")

    # ─────────────────────────────────────────────────────────────
    # 1.8 Capture row 18 col 15 (CLASSIFICATION) PRE-rename for SOA/HO
    # ─────────────────────────────────────────────────────────────
    pre_soa_18_15 = sheets.spreadsheets().values().get(
        spreadsheetId=AP_MASTER_ID, range="'Suppliers SOA'!O18", valueRenderOption="UNFORMATTED_VALUE"
    ).execute().get("values", [[]])
    pre_ho_18_15 = sheets.spreadsheets().values().get(
        spreadsheetId=AP_MASTER_ID, range="'Head Office'!O18", valueRenderOption="UNFORMATTED_VALUE"
    ).execute().get("values", [[]])
    log["tasks"]["1.8_pre"] = {
        "suppliers_soa_row18_col15": pre_soa_18_15[0][0] if pre_soa_18_15 and pre_soa_18_15[0] else None,
        "head_office_row18_col15": pre_ho_18_15[0][0] if pre_ho_18_15 and pre_ho_18_15[0] else None,
    }
    print(f"[1.8 pre-capture] SOA O18={log['tasks']['1.8_pre']['suppliers_soa_row18_col15']!r}, HO O18={log['tasks']['1.8_pre']['head_office_row18_col15']!r}")

    # ─────────────────────────────────────────────────────────────
    # 1.2 Delete col 20 (Remarks) from Suppliers SOA  +
    # 1.3 Resize Suppliers SOA grid to 19 cols
    # 1.4 Resize Head Office grid to 19 cols
    # 1.5 Resize CAPEX grid to 20 cols
    # 1.6b Rename headers on SOA, HO row 17 col 15 + CAPEX row 19 col 15
    # 1.7 Rename Payment Plan row 3 col 15 to BILLED ENTITY
    # ─────────────────────────────────────────────────────────────
    sheet_id_soa, soa_grid = get_sheet_id(sheets, AP_MASTER_ID, "Suppliers SOA")
    sheet_id_ho, ho_grid = get_sheet_id(sheets, AP_MASTER_ID, "Head Office")
    sheet_id_capex, capex_grid = get_sheet_id(sheets, AP_MASTER_ID, "CAPEX")
    sheet_id_pp, pp_grid = get_sheet_id(sheets, AP_MASTER_ID, "Payment Plan")

    print(f"[grid pre] SOA cols={soa_grid['columnCount']}, HO cols={ho_grid['columnCount']}, CAPEX cols={capex_grid['columnCount']}, PP cols={pp_grid['columnCount']}")

    requests = [
        # 1.2 Delete col 20 of Suppliers SOA (zero-indexed: index 19, delete one column)
        {"deleteDimension": {"range": {"sheetId": sheet_id_soa, "dimension": "COLUMNS", "startIndex": 19, "endIndex": 20}}},
        # 1.3 Resize SOA grid to 19 cols (was 22, -1 from delete = 21, resize to 19)
        {"updateSheetProperties": {"properties": {"sheetId": sheet_id_soa, "gridProperties": {"columnCount": 19}}, "fields": "gridProperties.columnCount"}},
        # 1.4 Resize HO grid 22 → 19
        {"updateSheetProperties": {"properties": {"sheetId": sheet_id_ho, "gridProperties": {"columnCount": 19}}, "fields": "gridProperties.columnCount"}},
        # 1.5 Resize CAPEX 22 → 20
        {"updateSheetProperties": {"properties": {"sheetId": sheet_id_capex, "gridProperties": {"columnCount": 20}}, "fields": "gridProperties.columnCount"}},
        # 1.6b Rename SOA row 17 col 15 (O17)
        {"updateCells": {
            "range": {"sheetId": sheet_id_soa, "startRowIndex": 16, "endRowIndex": 17, "startColumnIndex": 14, "endColumnIndex": 15},
            "rows": [{"values": [{"userEnteredValue": {"stringValue": "GOODS/SERVICES"}}]}],
            "fields": "userEnteredValue",
        }},
        # 1.6b Rename HO row 17 col 15 (O17)
        {"updateCells": {
            "range": {"sheetId": sheet_id_ho, "startRowIndex": 16, "endRowIndex": 17, "startColumnIndex": 14, "endColumnIndex": 15},
            "rows": [{"values": [{"userEnteredValue": {"stringValue": "GOODS/SERVICES"}}]}],
            "fields": "userEnteredValue",
        }},
        # 1.6b Rename CAPEX row 19 col 15 (O19)
        {"updateCells": {
            "range": {"sheetId": sheet_id_capex, "startRowIndex": 18, "endRowIndex": 19, "startColumnIndex": 14, "endColumnIndex": 15},
            "rows": [{"values": [{"userEnteredValue": {"stringValue": "GOODS/SERVICES"}}]}],
            "fields": "userEnteredValue",
        }},
        # 1.7 Rename PP row 3 col 15 (O3) to BILLED ENTITY (NOT GOODS/SERVICES — avoid duplicate)
        {"updateCells": {
            "range": {"sheetId": sheet_id_pp, "startRowIndex": 2, "endRowIndex": 3, "startColumnIndex": 14, "endColumnIndex": 15},
            "rows": [{"values": [{"userEnteredValue": {"stringValue": "BILLED ENTITY"}}]}],
            "fields": "userEnteredValue",
        }},
    ]

    print(f"[1.2-1.7] Executing {len(requests)} batchUpdate requests...")
    resp = sheets.spreadsheets().batchUpdate(spreadsheetId=AP_MASTER_ID, body={"requests": requests}).execute()
    log["tasks"]["batch_update_replies"] = len(resp.get("replies", []))
    print(f"  batchUpdate OK; {len(resp.get('replies', []))} replies")

    # ─────────────────────────────────────────────────────────────
    # 1.8 Post-verify: read grids + headers + row 18 col 15 (should be unchanged)
    # ─────────────────────────────────────────────────────────────
    print("[1.8 post] Verifying post-change state...")
    meta = sheets.spreadsheets().get(spreadsheetId=AP_MASTER_ID, fields="sheets(properties(sheetId,title,gridProperties))").execute()
    new_grids = {s["properties"]["title"]: s["properties"]["gridProperties"]["columnCount"] for s in meta["sheets"] if s["properties"]["title"] in ("Suppliers SOA", "Head Office", "CAPEX", "Payment Plan")}

    # Read post-change headers
    headers_post = {}
    for tab, header_row in [("Suppliers SOA", "O17"), ("Head Office", "O17"), ("CAPEX", "O19"), ("Payment Plan", "O3")]:
        res = sheets.spreadsheets().values().get(spreadsheetId=AP_MASTER_ID, range=f"'{tab}'!{header_row}").execute()
        headers_post[tab] = res.get("values", [[]])[0][0] if res.get("values") and res["values"][0] else None

    # Read post row 18 col 15 (should be unchanged)
    post_soa_18_15 = sheets.spreadsheets().values().get(spreadsheetId=AP_MASTER_ID, range="'Suppliers SOA'!O18", valueRenderOption="UNFORMATTED_VALUE").execute().get("values", [[]])
    post_ho_18_15 = sheets.spreadsheets().values().get(spreadsheetId=AP_MASTER_ID, range="'Head Office'!O18", valueRenderOption="UNFORMATTED_VALUE").execute().get("values", [[]])

    log["tasks"]["1.8_post"] = {
        "grids": new_grids,
        "headers": headers_post,
        "suppliers_soa_row18_col15_post": post_soa_18_15[0][0] if post_soa_18_15 and post_soa_18_15[0] else None,
        "head_office_row18_col15_post": post_ho_18_15[0][0] if post_ho_18_15 and post_ho_18_15[0] else None,
        "data_preserved_soa": (pre_soa_18_15 and pre_soa_18_15[0] and post_soa_18_15 and post_soa_18_15[0] and pre_soa_18_15[0][0] == post_soa_18_15[0][0]),
        "data_preserved_ho": (pre_ho_18_15 and pre_ho_18_15[0] and post_ho_18_15 and post_ho_18_15[0] and pre_ho_18_15[0][0] == post_ho_18_15[0][0]),
    }
    log["finished_at"] = datetime.now().astimezone().isoformat()

    log_path = ROOT / "output" / "s255" / "phase1_log.json"
    log_path.write_text(json.dumps(log, indent=2, default=str), encoding="utf-8")
    print(f"\nPhase 1 log: {log_path}")
    print(f"  Grids: {new_grids}")
    print(f"  Headers: {headers_post}")
    print(f"  Data preserved (SOA row18 col15): {log['tasks']['1.8_post']['data_preserved_soa']}")
    print(f"  Data preserved (HO row18 col15): {log['tasks']['1.8_post']['data_preserved_ho']}")


if __name__ == "__main__":
    main()
