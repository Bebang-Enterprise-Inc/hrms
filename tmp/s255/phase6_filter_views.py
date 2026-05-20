"""S255 Phase 6 — Filter views on Payment Plan tab col I (mapped STATUS).

6.0 Sanity-check col I has AP-vocab (mapped by mapDeniseToApStatus_)
6.1 Create filter view "Scheduled for Online Transfer - Due"
6.2 Create filter view "Scheduled for Release Check - Due"
6.3 Document in team-training
6.4 Chat draft
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
from datetime import datetime
from collections import Counter

from google.oauth2 import service_account
from googleapiclient.discovery import build

ROOT = Path(__file__).resolve().parents[2]
CREDS_PATH = "F:/Dropbox/Projects/BEI-ERP/credentials/task-manager-service.json"
AP_MASTER_ID = "1bQ6mO1FXD4VYcLt8m-yklkV7pyYhSWqU7b8K0bVgG7c"


def get_sheets():
    creds = service_account.Credentials.from_service_account_file(
        CREDS_PATH, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    ).with_subject("sam@bebang.ph")
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def get_pp_sheet_id(sheets):
    meta = sheets.spreadsheets().get(spreadsheetId=AP_MASTER_ID, fields="sheets(properties(sheetId,title))").execute()
    for s in meta["sheets"]:
        if s["properties"]["title"] == "Payment Plan":
            return s["properties"]["sheetId"]
    return None


def main():
    log = {"phase": "6", "started_at": datetime.now().astimezone().isoformat(), "tasks": {}}
    sheets = get_sheets()
    pp_sheet_id = get_pp_sheet_id(sheets)
    if pp_sheet_id is None:
        sys.exit("Payment Plan tab not found")

    # 6.0 Sanity check col I
    print("[6.0] Sanity-checking Payment Plan col I (STATUS — mapped)...")
    res = sheets.spreadsheets().values().get(
        spreadsheetId=AP_MASTER_ID, range="'Payment Plan'!I4:I100", valueRenderOption="UNFORMATTED_VALUE",
    ).execute()
    vals = [str(r[0]).strip() if r and r[0] else "" for r in res.get("values", [])]
    counts = Counter(v for v in vals if v)
    print(f"  Sampled {len(vals)} rows; distinct STATUS values: {dict(counts)}")
    ap_vocab = {"FOR ONLINE PAYMENT", "CHECK READY", "CHECK RELEASED", "IN PIPELINE", "WITH FINANCE", "PAID", "NO RFP YET"}
    found_ap = {v for v in counts if v in ap_vocab}
    if not found_ap:
        # Just warn — filter views may still be useful even if no current matches
        print(f"  [warn] no AP-vocab values found in 100-row sample of col I; filter views may show 0 rows initially")
    else:
        print(f"  AP-vocab present in col I: {found_ap}")
    (ROOT / "output" / "s255" / "payment_plan_col_i_sample.json").write_text(json.dumps({
        "phase": "6.0", "sampled_rows": len(vals), "counts": dict(counts), "ap_vocab_found": list(found_ap),
    }, indent=2, default=str), encoding="utf-8")
    log["tasks"]["6.0"] = {"status": "DONE", "ap_vocab_found": list(found_ap), "sample_size": len(vals)}

    # Check existing filter views to avoid duplicates
    meta = sheets.spreadsheets().get(spreadsheetId=AP_MASTER_ID, fields="sheets(properties(sheetId,title),filterViews(title,filterViewId))").execute()
    pp_meta = next(s for s in meta["sheets"] if s["properties"]["title"] == "Payment Plan")
    existing_filter_titles = {fv["title"]: fv["filterViewId"] for fv in pp_meta.get("filterViews", [])}
    print(f"  Existing filter views on PP: {list(existing_filter_titles.keys())}")

    # 6.1 + 6.2 — Add filter views
    requests = []
    if "Scheduled for Online Transfer - Due" not in existing_filter_titles:
        requests.append({
            "addFilterView": {
                "filter": {
                    "title": "Scheduled for Online Transfer - Due",
                    "range": {"sheetId": pp_sheet_id, "startRowIndex": 2, "startColumnIndex": 0, "endColumnIndex": 30},  # header at row 3 (0-idx 2)
                    "criteria": {
                        "8": {  # col I (0-indexed = 8)
                            "condition": {
                                "type": "TEXT_EQ",
                                "values": [{"userEnteredValue": "FOR ONLINE PAYMENT"}]
                            }
                        }
                    }
                }
            }
        })
    if "Scheduled for Release Check - Due" not in existing_filter_titles:
        requests.append({
            "addFilterView": {
                "filter": {
                    "title": "Scheduled for Release Check - Due",
                    "range": {"sheetId": pp_sheet_id, "startRowIndex": 2, "startColumnIndex": 0, "endColumnIndex": 30},
                    "criteria": {
                        "8": {  # col I
                            # Use hiddenValues to keep only CHECK READY + CHECK RELEASED visible (inverted: hide everything else)
                            # Actually addFilterView with TEXT_EQ only supports one value. Use ONE_OF_LIST via condition type CUSTOM_FORMULA or list approach.
                            # Simplest: use condition TEXT_NOT_CONTAINS to keep both; or use FILTER_TEXT_IS via hiddenValues approach
                            # Best approach: ONE_OF_TEXT condition isn't a direct enum; use TEXT_EQ + a condition that matches multiple via formula
                            "condition": {
                                "type": "CUSTOM_FORMULA",
                                "values": [{"userEnteredValue": '=OR(I3="CHECK READY", I3="CHECK RELEASED")'}]
                            }
                        }
                    }
                }
            }
        })

    if requests:
        resp = sheets.spreadsheets().batchUpdate(spreadsheetId=AP_MASTER_ID, body={"requests": requests}).execute()
        print(f"  Created {len(resp['replies'])} filter view(s)")
        for r in resp["replies"]:
            fv = r["addFilterView"]["filter"]
            print(f"    - {fv['title']!r} (filterViewId={fv['filterViewId']})")
            log["tasks"][f"6.{1 + len(log['tasks'])}"] = {"status": "CREATED", "title": fv["title"], "filterViewId": fv["filterViewId"]}
    else:
        print("  Both filter views already exist; skipping")
        log["tasks"]["6.1+6.2"] = {"status": "ALREADY_EXIST"}

    # 6.4 Chat draft (don't auto-send)
    draft = """Hi Denise + Angela —

Quick heads up: S255 (AP system hardening) added two **filter views** on AP Master Payment Plan tab that mirror Angela's "Scheduled for Online Transfer - Due" and "Scheduled for Release Check - Due" tabs from your Project: 2-Week Payment Plan sheet.

These are LIVE filter views directly on Payment Plan — no data duplication, no manual refresh. They filter on col I (STATUS — the mapped AP-vocab version, which the script maintains from your raw STATUS):

- **Scheduled for Online Transfer - Due** → rows where STATUS = "FOR ONLINE PAYMENT"
- **Scheduled for Release Check - Due** → rows where STATUS = "CHECK READY" OR "CHECK RELEASED"

To use: open the AP Master sheet → Payment Plan tab → click the filter funnel icon (top-left) → "Filter views" → pick the view you want.

Whenever you're ready to transition off your standalone sheet into AP Master, these views are waiting. Sam will toggle the mirror flag when you say go.

— S255 closeout
"""
    (ROOT / "output" / "s255" / "angela_denise_chat_draft.md").write_text(draft, encoding="utf-8")
    log["tasks"]["6.4"] = {"status": "DONE", "path": "output/s255/angela_denise_chat_draft.md"}

    log["finished_at"] = datetime.now().astimezone().isoformat()
    (ROOT / "output" / "s255" / "phase6_log.json").write_text(json.dumps(log, indent=2, default=str), encoding="utf-8")
    print(f"\nPhase 6 done. Logs: phase6_log.json, payment_plan_col_i_sample.json, angela_denise_chat_draft.md")


if __name__ == "__main__":
    main()
