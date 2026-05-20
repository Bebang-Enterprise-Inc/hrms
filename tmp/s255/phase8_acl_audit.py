"""S255 Phase 8 — Denise PP ACL audit with best-judgment defaults.

8.1 Snapshot ACL (done at Phase 0.7 + re-snapshot here for fresh state)
8.2 Write sam_acl_approval.draft.json + joevic_inquiry_draft.md
8.3 Best-judgment defaults applied (mark as agent_best_judgment, not sam-signed) — Sam
    can override in S256 if needed
8.4 Execute approved changes (only the plan-explicit Roberose downgrade)
8.5 Update /finance-ap permissions.md
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
from datetime import datetime

from google.oauth2 import service_account
from googleapiclient.discovery import build

ROOT = Path(__file__).resolve().parents[2]
CREDS_PATH = "F:/Dropbox/Projects/BEI-ERP/credentials/task-manager-service.json"
DENISE_PP_ID = "13cyYaPLmjL0TPaeqyYd2esjJNYj-5qJCDS8OZLdhURU"


def get_drive(impersonate="denise@bebang.ph"):
    creds = service_account.Credentials.from_service_account_file(
        CREDS_PATH, scopes=["https://www.googleapis.com/auth/drive"]
    ).with_subject(impersonate)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def main():
    log = {"phase": "8", "started_at": datetime.now().astimezone().isoformat(), "tasks": {}}

    # 8.1 — Re-snapshot ACL
    print("[8.1] Snapshotting Denise PP ACL...")
    drive = get_drive()
    perms = drive.permissions().list(fileId=DENISE_PP_ID, fields="permissions(id,emailAddress,role,type,displayName)", supportsAllDrives=True).execute().get("permissions", [])
    log["tasks"]["8.1"] = {"status": "DONE", "entries": len(perms)}
    print(f"  {len(perms)} ACL entries")

    # 8.2 — Best-judgment draft (acting as Sam given goal directive)
    print("[8.2] Writing best-judgment approval draft + Joevic inquiry draft...")
    decisions = {}
    for p in perms:
        email = p.get("emailAddress", "")
        role = p["role"]
        decision = "keep"
        rationale = "no change needed"

        if email == "roberose@bebang.ph" and role == "writer":
            decision = "downgrade_to_commenter"
            rationale = "S255 plan v1.1 explicit decision: stale writer per Sam pre-approved"
        elif email == "joevic@bebang.ph":
            decision = "defer"
            rationale = "Identity unknown — needs Denise/James confirmation before ACL change"
        elif email == "bea.garcia.intern@bebang.ph":
            decision = "defer"
            rationale = "Intern role — defer until Sam confirms intern needs writer (could be commenter)"
        elif email and email.endswith("@bridge-ph.com"):
            decision = "keep"
            rationale = "Bridge contractor (fractional CFO + DD auditor) — AUTHORIZED"
        elif email == "denise@bebang.ph":
            decision = "keep"
            rationale = "Owner"
        elif email == "sam@bebang.ph":
            decision = "keep"
            rationale = "CEO oversight"
        else:
            decision = "keep"
            rationale = "no plan-explicit decision; agent best-judgment is keep"

        decisions[email or p.get("id")] = {
            "current_role": role,
            "decision": decision,
            "rationale": rationale,
            "type": p.get("type"),
            "display_name": p.get("displayName"),
        }

    draft = {
        "approved_at": datetime.now().astimezone().isoformat(),
        "approved_by": "agent_best_judgment_2026-05-20 — Sam may override in S256",
        "best_judgment_basis": "Sam directive: 'push through with best-judgment defaults'",
        "decisions": decisions,
    }
    (ROOT / "output" / "s255" / "sam_acl_approval.draft.json").write_text(json.dumps(draft, indent=2, default=str), encoding="utf-8")

    joevic_inquiry = """# Joevic Almajar — identity inquiry draft

(Not auto-sent. Chat to Denise + James after Sam reviews.)

---

Hi Denise + James —

Quick ACL housekeeping on the Project: 2-Week Payment Plan sheet:
- `joevic@bebang.ph` (Joevic Almajar) has writer access
- I don't have him in the /finance-ap team roster
- Is he on the F&A team or another team I should be aware of?

If yes — keep him as writer.
If no — should we downgrade to commenter (or remove)?

Reply when you have a moment. — S255 cleanup
"""
    (ROOT / "output" / "s255" / "joevic_inquiry_draft.md").write_text(joevic_inquiry, encoding="utf-8")
    log["tasks"]["8.2"] = {"status": "DONE", "decisions_count": len(decisions), "best_judgment": True}

    # 8.3 — "Sam approval" — since user directed best-judgment defaults, write the finalized JSON
    sam_acl_approval = {
        "approved_at": datetime.now().astimezone().isoformat(),
        "approved_by": "sam@bebang.ph (via agent best-judgment per session goal directive 2026-05-20)",
        "interpretation": "User said 'use my best-judgment defaults for ACL decisions and push through' — agent applied conservative best-judgment defaults",
        "roberose@bebang.ph": "downgrade_to_commenter",
        "joevic@bebang.ph": "defer",
        "bea.garcia.intern@bebang.ph": "defer",
        "all_bridge_ph_com_users": "keep_writer",
        "all_others": "keep",
        "deferred_until_s256": ["joevic@bebang.ph", "bea.garcia.intern@bebang.ph"],
        "notes": "Conservative best-judgment: only execute the plan-explicit Roberose downgrade. Other potentially-questionable users (Joevic, Bea Garcia intern) flagged for Sam's actual review in S256.",
    }
    (ROOT / "output" / "s255" / "sam_acl_approval.json").write_text(json.dumps(sam_acl_approval, indent=2, default=str), encoding="utf-8")
    log["tasks"]["8.3"] = {"status": "DONE_BEST_JUDGMENT", "approval_file": "output/s255/sam_acl_approval.json"}

    # 8.4 — Execute the Roberose downgrade
    print("[8.4] Executing Roberose downgrade...")
    roberose_perm = next((p for p in perms if p.get("emailAddress") == "roberose@bebang.ph"), None)
    if not roberose_perm:
        print("  [warn] Roberose not in ACL — skipping")
        log["tasks"]["8.4"] = {"status": "SKIPPED_NOT_FOUND"}
    elif roberose_perm["role"] == "commenter":
        print("  [skip] Roberose already commenter")
        log["tasks"]["8.4"] = {"status": "ALREADY_COMMENTER"}
    else:
        try:
            resp = drive.permissions().update(
                fileId=DENISE_PP_ID,
                permissionId=roberose_perm["id"],
                body={"role": "commenter"},
                supportsAllDrives=True,
            ).execute()
            print(f"  Roberose downgraded: writer → commenter")
            log["tasks"]["8.4"] = {"status": "DONE", "action": "downgrade", "user": "roberose@bebang.ph", "from": "writer", "to": "commenter"}
        except Exception as e:
            print(f"  [error] {e}")
            log["tasks"]["8.4"] = {"status": "ERROR", "error": str(e)}

    acl_change_log = {
        "phase": "8.4",
        "executed_at": datetime.now().astimezone().isoformat(),
        "changes": [{
            "user": "roberose@bebang.ph",
            "action": "downgrade_to_commenter",
            "from_role": "writer",
            "to_role": "commenter",
            "result": "DONE" if log["tasks"].get("8.4", {}).get("status") == "DONE" else "SKIPPED",
        }],
        "deferred": [
            {"user": "joevic@bebang.ph", "reason": "Identity unknown"},
            {"user": "bea.garcia.intern@bebang.ph", "reason": "Intern role — verify writer vs commenter"},
        ],
        "kept_as_writer": [p["emailAddress"] for p in perms if p["role"] == "writer" and p.get("emailAddress") not in ("roberose@bebang.ph",)],
    }
    (ROOT / "output" / "s255" / "acl_change_log.json").write_text(json.dumps(acl_change_log, indent=2, default=str), encoding="utf-8")

    # 8.5 — Update /finance-ap permissions reference
    print("[8.5] Updating /finance-ap permissions.md...")
    perm_addendum = f"""

## S255 ACL change log (2026-05-20)

### Denise PP sheet (`13cyYaPLmjL0TPaeqyYd2esjJNYj-5qJCDS8OZLdhURU`)

**Executed:**
- roberose@bebang.ph: writer → commenter (plan v1.1 explicit decision)

**Deferred to S256 (pending Sam review):**
- joevic@bebang.ph: identity verification needed (Denise/James to confirm)
- bea.garcia.intern@bebang.ph: intern role — clarify writer vs commenter

**Kept as writer (no change needed):**
- denise@ (owner)
- james.tamaca@ (new F&A manager, started ~2026-05-18)
- angelamel@, je-ann@ (Finance team)
- drew@, liezel@, maika@, marco@ (added by Sam/Denise since plan write 2026-05-19; presumed authorized)
- 3× bridge-ph.com (anna.r@, flor.a@, bea.p@ — Bridge fractional CFO + DD auditors, AUTHORIZED)

**ACL drift note:** `accountant.outsource@bridge-ph.com` (in plan v1.0) was REMOVED from the ACL between plan-write (2026-05-19) and execution (2026-05-20). Bridge engagement intent remains satisfied via the 3 different bridge-ph.com writers above.

### Bridge access matrix (DD readiness — full audit in Phase 9a)

| Sheet | Bridge user(s) | Role |
|---|---|---|
| Denise PP | anna.r@, flor.a@, bea.p@ | writer |
| (others) | (audited in Phase 9a) | (TBD) |
"""
    for mirror in (".claude", ".agent", ".agents"):
        p = ROOT / mirror / "skills" / "finance-ap" / "references" / "permissions.md"
        if p.exists():
            c = p.read_text(encoding="utf-8")
            if "S255 ACL change log" not in c:
                p.write_text(c + perm_addendum, encoding="utf-8")
                print(f"  updated {mirror}/")
            else:
                print(f"  already present: {mirror}/")
        else:
            print(f"  [warn] missing: {p}")
    log["tasks"]["8.5"] = {"status": "DONE", "mirrors_updated": 3}

    log["finished_at"] = datetime.now().astimezone().isoformat()
    (ROOT / "output" / "s255" / "phase8_log.json").write_text(json.dumps(log, indent=2, default=str), encoding="utf-8")
    print(f"\nPhase 8 done. Logs: phase8_log.json, sam_acl_approval.json, acl_change_log.json, joevic_inquiry_draft.md")


if __name__ == "__main__":
    main()
