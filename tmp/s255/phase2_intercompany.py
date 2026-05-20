"""S255 Phase 2 — FPM Intercompany routing fix + new tab + migration + v3.9 patches.

Tasks:
  2.1 Create Intercompany tab (19 cols, strict-locked sam@ only)
  2.2 Patch v3.9 FPM seed routing with tight predicate
  2.3 One-time migration: HO → Intercompany for matching rows; log ambiguous
  2.4 Banner unchanged for Intercompany (script-level — no Phase 2 action)
  2.5 Extend existingIndex line 428 AND status sync line 290 AND FPM seed newRowsByTab line 1144

In-line plan amendment (during execution): Phase 2.5 also touches line 290 + line 1144,
not just line 428, to fully wire Intercompany into the seed/sync system. This achieves
the Phase 2.5 goal (no unbounded growth) and goes further (status sync + FPM seed routing).
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path
from datetime import datetime

from google.oauth2 import service_account
from googleapiclient.discovery import build

ROOT = Path(__file__).resolve().parents[2]
CREDS_PATH = "F:/Dropbox/Projects/BEI-ERP/credentials/task-manager-service.json"
AP_MASTER_ID = "1bQ6mO1FXD4VYcLt8m-yklkV7pyYhSWqU7b8K0bVgG7c"
V39_PATH = ROOT / "scripts" / "google_apps" / "s255_ap_view_hourly_sync_v39.gs"

# Tight Intercompany predicate (must match v3.9 source exactly)
RX_PAYEE_BEBANG = re.compile(r"^Bebang\s+(Enterprise|Kitchen|Shaw)\s+Inc\.?", re.IGNORECASE)
RX_TRANSFER_KEYWORD = re.compile(r"(transfer (of )?fund|cash sweep|intercompany)", re.IGNORECASE)
RX_GOVT_NEG = re.compile(r"HDMF|SSS|PHIC|PHILHEALTH|BIR|PAG-?IBIG|CONTRIBUTION|RENTAL|FINAL PAY", re.IGNORECASE)


def get_sheets(impersonate="sam@bebang.ph"):
    creds = service_account.Credentials.from_service_account_file(
        CREDS_PATH,
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"],
    ).with_subject(impersonate)
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def get_sheet_id(sheets, ss_id, name):
    meta = sheets.spreadsheets().get(spreadsheetId=ss_id, fields="sheets(properties(sheetId,title,gridProperties))").execute()
    for s in meta["sheets"]:
        if s["properties"]["title"] == name:
            return s["properties"]["sheetId"], s["properties"]["gridProperties"]
    return None, None


def main():
    log = {"phase": "2", "started_at": datetime.now().astimezone().isoformat(), "tasks": {}}
    sheets = get_sheets()

    # ─────────────────────────────────────────────────────────────
    # 2.5a — Patch v3.9 source for Intercompany awareness (3 sites)
    # ─────────────────────────────────────────────────────────────
    print("[2.5a] Patching v3.9 source — existingIndex (line 428), status sync (line 290), FPM seed newRowsByTab (line 1144), FPM routing classification...")
    src = V39_PATH.read_text(encoding="utf-8")
    lines = src.split("\n")

    # Patch 1: line 290 status sync iteration — add Intercompany
    assert "['Suppliers SOA', 'Head Office', 'CAPEX']" in lines[289], f"Line 290 unexpected: {lines[289]!r}"
    lines[289] = lines[289].replace(
        "['Suppliers SOA', 'Head Office', 'CAPEX']",
        "['Suppliers SOA', 'Head Office', 'CAPEX', 'Intercompany']",
    )

    # Patch 2: line 428 existingIndex iteration — add Intercompany
    assert "['Suppliers SOA', 'Head Office', 'CAPEX']" in lines[427], f"Line 428 unexpected: {lines[427]!r}"
    lines[427] = lines[427].replace(
        "['Suppliers SOA', 'Head Office', 'CAPEX']",
        "['Suppliers SOA', 'Head Office', 'CAPEX', 'Intercompany']",
    )

    # Patch 3: FPM seed newRowsByTab at line 1144 — add Intercompany key
    assert "{ 'Suppliers SOA': [], 'Head Office': [], 'CAPEX': [] }" in lines[1143], f"Line 1144 unexpected: {lines[1143]!r}"
    lines[1143] = lines[1143].replace(
        "{ 'Suppliers SOA': [], 'Head Office': [], 'CAPEX': [] }",
        "{ 'Suppliers SOA': [], 'Head Office': [], 'CAPEX': [], 'Intercompany': [] }",
    )

    # Patch 4: stats init for intercompany_count (line ~1100, where stats object is created)
    # We're looking for the FPM seed stats init line.
    for idx, ln in enumerate(lines):
        if "stats = { scanned: 0, appended: 0, skipped_paid_old: 0" in ln and idx > 1095 and idx < 1110:
            # Add intercompany_count: 0 before sample_appended
            lines[idx] = ln.replace(
                "capex_count: 0, ho_count: 0, soa_count: 0,",
                "capex_count: 0, ho_count: 0, soa_count: 0, intercompany_count: 0,",
            )
            break

    # Patch 5: FPM routing — insert Intercompany detection BEFORE the CAPEX check
    # Find the "Classify → which AP Master tab" comment line and the targetTab=Head Office line
    routing_anchor_idx = None
    for idx, ln in enumerate(lines):
        if idx >= 1180 and idx <= 1230 and "var targetTab = 'Head Office';" in ln:
            routing_anchor_idx = idx
            break
    assert routing_anchor_idx is not None, "Could not find FPM routing targetTab anchor"

    intercompany_block = [
        "    // v3.9 (S255 Phase 2.2): Intercompany routing — Bebang entity payee + transfer keyword in CLASSIFICATION",
        "    // Tight predicate prevents misrouting govt-remittance rows (e.g. 'Bebang Enterprise Inc.' + 'SSS/HDMF/PHIC Contribution')",
        "    var isIntercompany = false;",
        "    if (/^Bebang\\s+(Enterprise|Kitchen|Shaw)\\s+Inc\\.?/i.test(payee)",
        "        && /(transfer (of )?fund|cash sweep|intercompany)/i.test(particulars)",
        "        && !/HDMF|SSS|PHIC|PHILHEALTH|BIR|PAG-?IBIG|CONTRIBUTION|RENTAL|FINAL PAY/i.test(particulars)) {",
        "      isIntercompany = true;",
        "    }",
        "",
    ]

    # Insert block right before the targetTab line
    new_lines = lines[:routing_anchor_idx] + intercompany_block + lines[routing_anchor_idx:]
    # Also update the if/else chain — find it after the insert
    # The chain is: if (isCapex) ... else if (supplierSet[payeeKey]) ... else ...
    # We want: if (isIntercompany) ... else if (isCapex) ... else if (supplierSet) ... else ...
    for idx in range(routing_anchor_idx, len(new_lines)):
        if "if (isCapex) {" in new_lines[idx]:
            new_lines[idx] = new_lines[idx].replace(
                "if (isCapex) {",
                "if (isIntercompany) {\n      targetTab = 'Intercompany';\n      stats.intercompany_count++;\n    } else if (isCapex) {",
            )
            break

    new_src = "\n".join(new_lines)

    # Sanity checks: count occurrences
    assert new_src.count("'Intercompany'") >= 4, f"Expected >=4 'Intercompany' string occurrences in v3.9, got {new_src.count(chr(39) + 'Intercompany' + chr(39))}"
    assert "intercompany_count" in new_src, "intercompany_count missing from v3.9 patched source"
    assert "isIntercompany = true" in new_src, "isIntercompany detection missing from v3.9 patched source"
    assert "'Suppliers SOA', 'Head Office', 'CAPEX', 'Intercompany'" in new_src, "existingIndex 4-tab forEach missing"

    V39_PATH.write_text(new_src, encoding="utf-8")
    log["tasks"]["2.5a_v39_patches"] = {
        "status": "DONE",
        "v39_size_bytes": len(new_src.encode("utf-8")),
        "patches_applied": ["line 290 status sync", "line 428 existingIndex", "line 1144 newRowsByTab", "stats.intercompany_count init", "FPM routing isIntercompany block + if-else extension"],
        "intercompany_string_occurrences": new_src.count("'Intercompany'"),
    }
    print(f"  v3.9 patched: {len(new_src.encode('utf-8'))} bytes; {new_src.count(chr(39) + 'Intercompany' + chr(39))} 'Intercompany' references")

    # ─────────────────────────────────────────────────────────────
    # 2.1 Create Intercompany tab on AP Master (19 cols)
    # ─────────────────────────────────────────────────────────────
    print("[2.1] Creating Intercompany tab on AP Master (19 cols, strict-locked)...")
    existing_id, _ = get_sheet_id(sheets, AP_MASTER_ID, "Intercompany")
    if existing_id is not None:
        print(f"  Tab already exists (id={existing_id}); skipping addSheet")
        log["tasks"]["2.1"] = {"status": "ALREADY_EXISTS", "sheet_id": existing_id}
    else:
        resp = sheets.spreadsheets().batchUpdate(spreadsheetId=AP_MASTER_ID, body={
            "requests": [{
                "addSheet": {
                    "properties": {
                        "title": "Intercompany",
                        "gridProperties": {"rowCount": 1000, "columnCount": 19, "frozenRowCount": 17},
                    }
                }
            }]
        }).execute()
        new_tab_props = resp["replies"][0]["addSheet"]["properties"]
        sheet_id_inter = new_tab_props["sheetId"]
        log["tasks"]["2.1"] = {"status": "CREATED", "sheet_id": sheet_id_inter}
        print(f"  Created (id={sheet_id_inter})")

        # Add header row at row 17 (matching SOA convention)
        SOA_HEADERS = ['SOURCE', 'PAYEE', 'INVOICE NO.', 'INVOICE DATE', 'AMOUNT', 'OUTSTANDING', 'AGING', 'AGING BUCKET', 'STATUS', 'BEI-FIN No.', 'RFP No.', 'METHOD', 'CHECK NO.', 'CATEGORY', 'GOODS/SERVICES', 'BILLED TO', 'VATABLE', 'VAT', 'EWT']
        sheets.spreadsheets().values().update(
            spreadsheetId=AP_MASTER_ID,
            range="'Intercompany'!A17:S17",
            valueInputOption="RAW",
            body={"values": [SOA_HEADERS]},
        ).execute()

        # Add banner placeholder rows 1-16 (will be populated by recomputeBanners_ in Phase 3)
        sheets.spreadsheets().values().update(
            spreadsheetId=AP_MASTER_ID,
            range="'Intercompany'!A1",
            valueInputOption="RAW",
            body={"values": [["INTERCOMPANY TRANSFERS — outstanding (Bebang Enterprise/Kitchen/Shaw)"]]},
        ).execute()

        # Strict-lock the tab to sam@bebang.ph only
        sheets.spreadsheets().batchUpdate(spreadsheetId=AP_MASTER_ID, body={
            "requests": [{
                "addProtectedRange": {
                    "protectedRange": {
                        "range": {"sheetId": sheet_id_inter},
                        "description": "S255 — Intercompany tab strict-lock (sam@ only)",
                        "warningOnly": False,
                        "editors": {"users": ["sam@bebang.ph"]},
                    }
                }
            }]
        }).execute()
        print("  Header row written (row 17); strict-lock applied")

    # ─────────────────────────────────────────────────────────────
    # 2.3 One-time migration: scan HO tab, find Intercompany rows, MOVE to Intercompany
    # ─────────────────────────────────────────────────────────────
    print("[2.3] Scanning Head Office for Intercompany rows...")
    ho_data = sheets.spreadsheets().values().get(
        spreadsheetId=AP_MASTER_ID,
        range="'Head Office'!A17:S",  # rows 17+ = header + data
        valueRenderOption="UNFORMATTED_VALUE",
    ).execute().get("values", [])
    if not ho_data:
        print("  HO tab returned no data!")
        sys.exit(1)
    ho_headers = ho_data[0]
    ho_rows = ho_data[1:]  # data rows start at sheet row 18
    print(f"  HO has {len(ho_rows)} data rows (header at row 17)")

    # Find column indices
    col_payee = ho_headers.index("PAYEE")
    col_classification = ho_headers.index("GOODS/SERVICES") if "GOODS/SERVICES" in ho_headers else ho_headers.index("CLASSIFICATION")
    col_source = ho_headers.index("SOURCE")

    matched_rows = []  # rows to migrate
    ambiguous_rows = []  # PAYEE matches Bebang but predicate fails

    for ridx, row in enumerate(ho_rows):
        if len(row) <= max(col_payee, col_classification, col_source):
            row = row + [""] * (max(col_payee, col_classification, col_source) + 1 - len(row))
        payee = str(row[col_payee] if col_payee < len(row) else "").strip()
        classification = str(row[col_classification] if col_classification < len(row) else "").strip()
        source = str(row[col_source] if col_source < len(row) else "").strip()
        sheet_row = ridx + 18  # 1-indexed sheet row

        # Apply predicate: PAYEE matches Bebang
        if not RX_PAYEE_BEBANG.search(payee):
            continue
        # If PAYEE matches Bebang, check the OTHER criteria
        transfer_match = bool(RX_TRANSFER_KEYWORD.search(classification))
        govt_match = bool(RX_GOVT_NEG.search(classification))

        if transfer_match and not govt_match:
            matched_rows.append({"sheet_row": sheet_row, "payee": payee, "classification": classification, "source": source, "row_data": row})
        else:
            ambiguous_rows.append({
                "sheet_row": sheet_row,
                "payee": payee,
                "classification": classification,
                "source": source,
                "transfer_keyword_match": transfer_match,
                "govt_keyword_match": govt_match,
                "reason": "matches PAYEE but " + ("contains govt keyword" if govt_match else "no transfer keyword"),
            })

    print(f"  Matched (will MIGRATE): {len(matched_rows)}")
    print(f"  Ambiguous (stays on HO; logged): {len(ambiguous_rows)}")

    if matched_rows:
        print("  Sample migrated rows:")
        for r in matched_rows[:5]:
            print(f"    row {r['sheet_row']}: PAYEE={r['payee']!r} | CLASS={r['classification'][:50]!r}")

    # Append matched rows to Intercompany tab (at end)
    if matched_rows:
        # Find next available row on Intercompany tab
        inter_data = sheets.spreadsheets().values().get(
            spreadsheetId=AP_MASTER_ID, range="'Intercompany'!A18:A"
        ).execute().get("values", [])
        next_row = 18 + len(inter_data)

        values_to_append = [r["row_data"] for r in matched_rows]
        # Pad rows to 19 cols
        for v in values_to_append:
            while len(v) < 19:
                v.append("")
        sheets.spreadsheets().values().update(
            spreadsheetId=AP_MASTER_ID,
            range=f"'Intercompany'!A{next_row}",
            valueInputOption="USER_ENTERED",
            body={"values": values_to_append},
        ).execute()
        print(f"  Appended {len(values_to_append)} rows to Intercompany starting at row {next_row}")

        # Delete those rows from HO (highest-row-first to preserve indices)
        sheet_id_ho, _ = get_sheet_id(sheets, AP_MASTER_ID, "Head Office")
        delete_requests = []
        for r in sorted(matched_rows, key=lambda x: x["sheet_row"], reverse=True):
            row = r["sheet_row"]
            # deleteDimension is 0-indexed
            delete_requests.append({
                "deleteDimension": {
                    "range": {"sheetId": sheet_id_ho, "dimension": "ROWS", "startIndex": row - 1, "endIndex": row},
                }
            })
        sheets.spreadsheets().batchUpdate(spreadsheetId=AP_MASTER_ID, body={"requests": delete_requests}).execute()
        print(f"  Deleted {len(delete_requests)} rows from Head Office (highest-first)")

    # Write logs
    routing_log = {
        "captured_at": datetime.now().astimezone().isoformat(),
        "phase": "2.3",
        "migrated_rows": len(matched_rows),
        "ambiguous_rows_count": len(ambiguous_rows),
        "predicate": "PAYEE matches /^Bebang\\s+(Enterprise|Kitchen|Shaw)\\s+Inc\\.?/i AND CLASSIFICATION matches /(transfer (of )?fund|cash sweep|intercompany)/i AND NOT matches /HDMF|SSS|PHIC|PHILHEALTH|BIR|PAG-?IBIG|CONTRIBUTION|RENTAL|FINAL PAY/i",
        "sample_migrated": [{"sheet_row": r["sheet_row"], "payee": r["payee"], "classification": r["classification"][:80], "source": r["source"]} for r in matched_rows[:10]],
    }
    (ROOT / "output" / "s255" / "intercompany_routing_log.json").write_text(json.dumps(routing_log, indent=2, default=str), encoding="utf-8")
    (ROOT / "output" / "s255" / "intercompany_ambiguous.json").write_text(json.dumps({
        "captured_at": datetime.now().astimezone().isoformat(),
        "phase": "2.3",
        "ambiguous_count": len(ambiguous_rows),
        "criteria": "PAYEE matches Bebang Enterprise/Kitchen/Shaw BUT CLASSIFICATION fails transfer-keyword OR contains govt-keyword. These rows STAY on HO.",
        "rows": ambiguous_rows[:50],  # cap for readability
    }, indent=2, default=str), encoding="utf-8")

    log["tasks"]["2.3"] = {
        "status": "DONE",
        "migrated": len(matched_rows),
        "ambiguous": len(ambiguous_rows),
        "log_path": "output/s255/intercompany_routing_log.json",
        "ambiguous_path": "output/s255/intercompany_ambiguous.json",
    }
    log["finished_at"] = datetime.now().astimezone().isoformat()
    (ROOT / "output" / "s255" / "phase2_log.json").write_text(json.dumps(log, indent=2, default=str), encoding="utf-8")
    print(f"\nPhase 2 log: {ROOT / 'output' / 's255' / 'phase2_log.json'}")


if __name__ == "__main__":
    main()
