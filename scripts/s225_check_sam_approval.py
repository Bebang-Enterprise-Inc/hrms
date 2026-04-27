"""S225 Phase 2→3 gate — poll PR comments for Sam's approval token.

Audit B-11 fix: removes ambiguity. Reads PR# from sam_consolidation_pr.txt, polls
`gh pr view <pr> --comments` for one of the canonical approval tokens, and writes
the canonical authority file `output/s225/verification/sam_consolidation_approval.md`.

Approval tokens (Sam writes one in a PR comment):
  - `S225 Phase 3 APPROVED ALL`
  - `S225 Phase 3 APPROVED: <cluster_id1>, <cluster_id2>`
  - `S225 Phase 3 APPROVED INTERCOMPANY: <cluster_id>`
  - `S225 Phase 3 SKIP: <cluster_id>`

Run from worktree:
    python scripts/s225_check_sam_approval.py [--once] [--max-wait-min N]

Default: poll every 5min for up to 4 hours.
With --once: single check, exit 0 if approval found, exit 1 otherwise.
"""
from __future__ import annotations
import argparse
import json
import os
import pathlib
import re
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
PR_FILE = ROOT / "output" / "s225" / "verification" / "sam_consolidation_pr.txt"
APPROVAL_FILE = ROOT / "output" / "s225" / "verification" / "sam_consolidation_approval.md"
APPROVAL_FILE.parent.mkdir(parents=True, exist_ok=True)

TOKEN_PATTERNS = [
    (re.compile(r"S225\s+Phase\s+3\s+APPROVED\s+INTERCOMPANY\s*:\s*(?P<clusters>.+?)(?=\n\n|\Z)", re.IGNORECASE | re.DOTALL), "APPROVED_INTERCOMPANY"),
    (re.compile(r"S225\s+Phase\s+3\s+APPROVED\s+ALL", re.IGNORECASE), "APPROVED_ALL"),
    (re.compile(r"S225\s+Phase\s+3\s+APPROVED\s*:\s*(?P<clusters>.+?)(?=\n\n|\Z)", re.IGNORECASE | re.DOTALL), "APPROVED_LIST"),
    (re.compile(r"S225\s+Phase\s+3\s+SKIP\s*:\s*(?P<clusters>.+?)(?=\n\n|\Z)", re.IGNORECASE | re.DOTALL), "SKIP"),
]


def gh_pr_comments(pr_num: str) -> list[dict]:
    env = os.environ.copy()
    env["GH_TOKEN"] = ""  # force keyring auth per CLAUDE.md
    out = subprocess.check_output(
        ["gh", "pr", "view", pr_num, "--repo", "Bebang-Enterprise-Inc/hrms", "--json", "comments"],
        text=True,
        env=env,
        creationflags=0x08000000 if sys.platform == "win32" else 0,
    )
    data = json.loads(out)
    return data.get("comments", [])


def parse_clusters(s: str) -> list[str]:
    parts = re.split(r"[,\s]+", s.strip())
    return [p for p in parts if p.startswith("cluster-")]


def detect_approval(comments: list[dict]) -> dict | None:
    """Scan all comments newest-first; first matching token wins."""
    for c in sorted(comments, key=lambda x: x.get("createdAt", ""), reverse=True):
        body = c.get("body", "") or ""
        author = (c.get("author") or {}).get("login", "")
        for pattern, kind in TOKEN_PATTERNS:
            m = pattern.search(body)
            if m:
                clusters = []
                if "clusters" in m.groupdict():
                    clusters = parse_clusters(m.group("clusters"))
                return {
                    "kind": kind,
                    "comment_author": author,
                    "comment_created_at": c.get("createdAt"),
                    "comment_body_excerpt": body[:500],
                    "clusters": clusters,
                    "raw_match": m.group(0)[:200],
                }
    return None


def write_approval_file(approval: dict, pr_num: str):
    md = []
    md.append("# S225 Phase 3 — Sam's Consolidation Approval (canonical)")
    md.append("")
    md.append(f"PR: #{pr_num}")
    md.append(f"Approval kind: **{approval['kind']}**")
    md.append(f"Author: {approval['comment_author']}")
    md.append(f"Detected at: {time.strftime('%Y-%m-%dT%H:%M:%S%z')}")
    md.append(f"Comment created at: {approval['comment_created_at']}")
    md.append("")
    if approval["kind"] == "APPROVED_ALL":
        md.append("**Action:** apply ALL clusters in audit (excluding INTERCOMPANY-flagged ones).")
    elif approval["kind"] == "APPROVED_LIST":
        md.append(f"**Action:** apply only listed clusters: {', '.join(approval['clusters'])}")
    elif approval["kind"] == "APPROVED_INTERCOMPANY":
        md.append(f"**Action:** explicit intercompany authorization for: {', '.join(approval['clusters'])}")
    elif approval["kind"] == "SKIP":
        md.append(f"**Action:** skip these clusters: {', '.join(approval['clusters'])}")
    md.append("")
    md.append("## Raw matched token")
    md.append("")
    md.append("```")
    md.append(approval["raw_match"])
    md.append("```")
    md.append("")
    md.append("## Comment excerpt")
    md.append("")
    md.append("```")
    md.append(approval["comment_body_excerpt"])
    md.append("```")
    md.append("")
    md.append("## Machine-readable JSON")
    md.append("")
    md.append("```json")
    md.append(json.dumps(approval, indent=2))
    md.append("```")
    APPROVAL_FILE.write_text("\n".join(md), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="Single check then exit")
    ap.add_argument("--max-wait-min", type=int, default=240, help="Max minutes to poll (default 240)")
    args = ap.parse_args()

    if not PR_FILE.exists():
        print(f"FATAL: {PR_FILE} not found. Phase 2 must create the PR first.", flush=True)
        return 2
    pr_num = PR_FILE.read_text(encoding="utf-8").strip()
    pr_num = re.search(r"\d+", pr_num)
    if not pr_num:
        print(f"FATAL: cannot extract PR number from {PR_FILE}", flush=True)
        return 2
    pr_num = pr_num.group(0)

    deadline = time.time() + args.max_wait_min * 60
    poll_interval = 60 if args.once else 300

    while True:
        try:
            comments = gh_pr_comments(pr_num)
        except Exception as e:
            print(f"  gh pr view failed: {e}", flush=True)
            comments = []

        approval = detect_approval(comments)
        if approval:
            print(f"\nFOUND APPROVAL: {approval['kind']} at {approval['comment_created_at']}", flush=True)
            write_approval_file(approval, pr_num)
            print(f"Wrote {APPROVAL_FILE}", flush=True)
            return 0

        if args.once or time.time() > deadline:
            print(f"No approval token found in {len(comments)} comments on PR #{pr_num}", flush=True)
            return 1

        remaining = int((deadline - time.time()) / 60)
        print(f"  No approval yet. Polling again in {poll_interval//60}min... ({remaining}min budget left)", flush=True)
        time.sleep(poll_interval)


if __name__ == "__main__":
    sys.exit(main())
