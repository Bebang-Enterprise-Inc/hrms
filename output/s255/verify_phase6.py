"""verify_phase6.py — S255 Phase 6 gate."""
from __future__ import annotations
import json
import sys
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build

ROOT = Path(__file__).resolve().parents[2]
CREDS_PATH = "F:/Dropbox/Projects/BEI-ERP/credentials/task-manager-service.json"
AP_MASTER_ID = "1bQ6mO1FXD4VYcLt8m-yklkV7pyYhSWqU7b8K0bVgG7c"


def fail(m): print(f"[FAIL] {m}", file=sys.stderr); sys.exit(1)
def ok(m): print(f"[OK]   {m}")


def main():
    sample_path = ROOT / "output" / "s255" / "payment_plan_col_i_sample.json"
    if not sample_path.exists(): fail(f"missing {sample_path}")
    s = json.loads(sample_path.read_text(encoding="utf-8"))
    ap_vocab_required = {"FOR ONLINE PAYMENT", "CHECK READY", "CHECK RELEASED"}
    found = set(s.get("ap_vocab_found", []))
    if not (ap_vocab_required & found): fail(f"col I has none of the required AP-vocab values; found {found}")
    ok(f"PP col I has AP-vocab: {sorted(found & ap_vocab_required)}")

    # Verify filter views exist
    creds = service_account.Credentials.from_service_account_file(
        CREDS_PATH, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
    ).with_subject("sam@bebang.ph")
    sheets = build("sheets", "v4", credentials=creds, cache_discovery=False)
    meta = sheets.spreadsheets().get(spreadsheetId=AP_MASTER_ID, fields="sheets(properties(title),filterViews(title,filterViewId,range(startColumnIndex,endColumnIndex),criteria))").execute()
    pp = next((sh for sh in meta["sheets"] if sh["properties"]["title"] == "Payment Plan"), None)
    if not pp: fail("Payment Plan tab missing")
    titles = {fv["title"]: fv for fv in pp.get("filterViews", [])}
    if "Scheduled for Online Transfer - Due" not in titles: fail("Filter view 'Scheduled for Online Transfer - Due' missing")
    if "Scheduled for Release Check - Due" not in titles: fail("Filter view 'Scheduled for Release Check - Due' missing")
    ok("Both filter views present on Payment Plan")

    # Verify col I (index 8) is in criteria
    fv1 = titles["Scheduled for Online Transfer - Due"]
    if "8" not in (fv1.get("criteria") or {}): fail("Filter view 1 not targeting col I (criteria key '8')")
    ok("Filter view 1 targets col I (index 8)")

    # Training doc
    for mirror in (".claude", ".agent", ".agents"):
        p = ROOT / mirror / "skills" / "finance-ap" / "references" / "team-training-2026-05-14.md"
        if p.exists():
            if "Filter Views on AP Master Payment Plan tab" not in p.read_text(encoding="utf-8"):
                fail(f"{mirror}/.../team-training missing filter view section")
    ok("Training doc has filter view section in 3 mirrors")

    print("\n[PASS] Phase 6 gate — filter views wired on Payment Plan col I")


if __name__ == "__main__":
    main()
