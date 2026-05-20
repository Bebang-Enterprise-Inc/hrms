"""S255 Phase 5 — 3M Dragon manual-invoice handling.

5.1 Patch v3.9 seedFromDenisePaymentPlan_ to detect "Invoice No." prefix → sourceTag = 'Denise PP - Manual'
5.2 One-time backfill: SOURCE='Denise PP*' AND INVOICE NO. starts with "Invoice No." → SOURCE='Denise PP - Manual'
5.3 Update /finance-ap team training doc
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


def get_sheets():
    creds = service_account.Credentials.from_service_account_file(
        CREDS_PATH, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    ).with_subject("sam@bebang.ph")
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def main():
    log = {"phase": "5", "started_at": datetime.now().astimezone().isoformat(), "tasks": {}}

    # 5.1 — patch v3.9 source
    print("[5.1] Patching v3.9 seedFromDenisePaymentPlan_ to detect 'Invoice No.' prefix...")
    src = V39_PATH.read_text(encoding="utf-8")
    if "Denise PP - Manual" in src:
        print("  [skip] 'Denise PP - Manual' already in v3.9")
    else:
        # Find the row builder anchor: "var rowValues = [\n        cfg.sourceTag, ..."
        # Insert sourceTag override just before the rowValues block
        anchor = "      var rowValues = [\n        cfg.sourceTag,                          // SOURCE"
        replacement = """      // v3.9 (S255 Phase 5): 3M Dragon manual-invoice detection — INVOICE NO starting with "INVOICE NO" prefix
      // overrides cfg.sourceTag to 'Denise PP - Manual' so Sam can filter procurement-bypass entries
      var sourceTag = cfg.sourceTag;
      if (/^INVOICE\\s*NO/i.test(invoiceNo)) {
        sourceTag = 'Denise PP - Manual';
      }
      var rowValues = [
        sourceTag,                              // SOURCE"""
        assert anchor in src, "Could not find row-builder anchor in v3.9 source"
        src = src.replace(anchor, replacement)
        V39_PATH.write_text(src, encoding="utf-8")
        print(f"  v3.9 patched ({len(src.encode('utf-8'))} bytes)")
    log["tasks"]["5.1"] = {"status": "DONE", "patches": "sourceTag override in seedFromDenisePaymentPlan_"}

    # 5.2 — one-time backfill on Suppliers SOA
    print("[5.2] One-time backfill: SOA rows with SOURCE='Denise PP*' AND INVOICE NO. starting with 'Invoice No.'...")
    sheets = get_sheets()
    res = sheets.spreadsheets().values().get(
        spreadsheetId=AP_MASTER_ID, range="'Suppliers SOA'!A17:S", valueRenderOption="UNFORMATTED_VALUE",
    ).execute()
    rows = res.get("values", [])
    if not rows: sys.exit("SOA returned no data")
    hdr = rows[0]
    data = rows[1:]
    ncols = len(hdr)
    for r in data:
        while len(r) < ncols: r.append("")

    iSource = hdr.index("SOURCE")
    iInvNo = hdr.index("INVOICE NO.")

    reclassified = []
    for ridx, r in enumerate(data):
        source = str(r[iSource] or "").strip()
        inv = str(r[iInvNo] or "").strip().upper()
        if source.startswith("Denise PP") and re.match(r"^INVOICE\s*NO", inv):
            sheet_row = ridx + 18  # 1-indexed; row 17 is header
            reclassified.append({"sheet_row": sheet_row, "source_pre": source, "invoice": str(r[iInvNo]).strip()})

    print(f"  Found {len(reclassified)} rows to reclassify to 'Denise PP - Manual'")
    for r in reclassified[:5]:
        print(f"    row {r['sheet_row']}: SOURCE={r['source_pre']!r}, INV={r['invoice']!r}")

    if reclassified:
        # Batch update SOURCE column (col A) for each row
        data_updates = [{
            "range": f"'Suppliers SOA'!A{r['sheet_row']}",
            "values": [["Denise PP - Manual"]],
        } for r in reclassified]
        sheets.spreadsheets().values().batchUpdate(spreadsheetId=AP_MASTER_ID, body={
            "valueInputOption": "USER_ENTERED",
            "data": data_updates,
        }).execute()
        print(f"  Reclassified {len(reclassified)} rows")
    log["tasks"]["5.2"] = {"status": "DONE", "reclassified_count": len(reclassified), "sample": reclassified[:10]}

    # 5.3 — append 3M Dragon SOURCE class note to team training doc
    print("[5.3] Adding SOURCE class to team-training doc...")
    training_path = ROOT / ".claude" / "skills" / "finance-ap" / "references" / "team-training-2026-05-14.md"
    if not training_path.exists():
        print(f"  [warn] training doc missing: {training_path} — Phase 9a will rebuild")
        log["tasks"]["5.3"] = {"status": "DEFERRED_TO_PHASE_9A", "reason": "training doc not on origin/production"}
    else:
        content = training_path.read_text(encoding="utf-8")
        addendum = "\n\n## SOURCE class additions (S255 — 2026-05-20)\n\nWhen filtering or reading AP Master rows by SOURCE column, recognize:\n\n- **`Denise PP - Manual`** — invoices that bypass the procurement AppSheet (e.g. 3M Dragon). Detect by INVOICE NO. starting with `Invoice No.` text. These rows skipped the standard PR/PO/GR/RFP flow; Bridge will want them tagged separately during DD audit.\n"
        if "Denise PP - Manual" not in content:
            # Sync to all 3 mirrors
            for mirror in (".claude", ".agent", ".agents"):
                p = ROOT / mirror / "skills" / "finance-ap" / "references" / "team-training-2026-05-14.md"
                if p.exists():
                    p.write_text(content + addendum, encoding="utf-8")
            print("  team-training doc updated in 3 mirrors")
            log["tasks"]["5.3"] = {"status": "DONE", "mirrors_updated": 3}
        else:
            print("  team-training already has the SOURCE class section")
            log["tasks"]["5.3"] = {"status": "ALREADY_PRESENT"}

    log["finished_at"] = datetime.now().astimezone().isoformat()
    (ROOT / "output" / "s255" / "3m_dragon_reclassification_log.json").write_text(json.dumps(log, indent=2, default=str), encoding="utf-8")
    (ROOT / "output" / "s255" / "phase5_log.json").write_text(json.dumps(log, indent=2, default=str), encoding="utf-8")
    print(f"\nPhase 5 logs written")


if __name__ == "__main__":
    main()
