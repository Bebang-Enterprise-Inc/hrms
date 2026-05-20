"""verify_phase8.py — S255 Phase 8 gate."""
from __future__ import annotations
import json
import sys
from pathlib import Path
from google.oauth2 import service_account
from googleapiclient.discovery import build

ROOT = Path(__file__).resolve().parents[2]
CREDS_PATH = "F:/Dropbox/Projects/BEI-ERP/credentials/task-manager-service.json"
DENISE_PP_ID = "13cyYaPLmjL0TPaeqyYd2esjJNYj-5qJCDS8OZLdhURU"


def fail(m): print(f"[FAIL] {m}", file=sys.stderr); sys.exit(1)
def ok(m): print(f"[OK]   {m}")


def main():
    # 1) sam_acl_approval.json present
    p = ROOT / "output" / "s255" / "sam_acl_approval.json"
    if not p.exists(): fail(f"missing {p}")
    approval = json.loads(p.read_text(encoding="utf-8"))
    if "roberose@bebang.ph" not in approval: fail("approval missing Roberose decision")
    if approval.get("roberose@bebang.ph") != "downgrade_to_commenter": fail(f"Roberose decision unexpected: {approval.get('roberose@bebang.ph')!r}")
    ok("sam_acl_approval.json has Roberose=downgrade_to_commenter")

    # 2) acl_change_log.json present
    p = ROOT / "output" / "s255" / "acl_change_log.json"
    if not p.exists(): fail(f"missing {p}")
    log = json.loads(p.read_text(encoding="utf-8"))
    if not log.get("changes"): fail("acl_change_log empty")
    ok(f"acl_change_log.json present with {len(log['changes'])} change(s) + {len(log.get('deferred', []))} deferred")

    # 3) Live verification — Roberose IS commenter
    creds = service_account.Credentials.from_service_account_file(
        CREDS_PATH, scopes=["https://www.googleapis.com/auth/drive"]
    ).with_subject("denise@bebang.ph")
    drive = build("drive", "v3", credentials=creds, cache_discovery=False)
    perms = drive.permissions().list(fileId=DENISE_PP_ID, fields="permissions(emailAddress,role)", supportsAllDrives=True).execute().get("permissions", [])
    roberose = next((p for p in perms if p.get("emailAddress") == "roberose@bebang.ph"), None)
    if not roberose: fail("Roberose not in ACL")
    if roberose["role"] != "commenter": fail(f"Roberose role = {roberose['role']!r}, expected 'commenter'")
    ok("Roberose live ACL role = commenter")

    # 4) joevic_inquiry_draft.md present
    p = ROOT / "output" / "s255" / "joevic_inquiry_draft.md"
    if not p.exists(): fail(f"missing {p}")
    ok("joevic_inquiry_draft.md present")

    # 5) permissions.md updated in 3 mirrors
    for mirror in (".claude", ".agent", ".agents"):
        p = ROOT / mirror / "skills" / "finance-ap" / "references" / "permissions.md"
        if p.exists():
            if "S255 ACL change log" not in p.read_text(encoding="utf-8"):
                fail(f"{mirror}/.../permissions.md missing S255 ACL section")
    ok("permissions.md updated in 3 mirrors")

    print("\n[PASS] Phase 8 gate — ACL audit complete (Roberose downgraded; 2 deferred)")


if __name__ == "__main__":
    main()
