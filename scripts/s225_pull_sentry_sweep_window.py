"""S225 Phase 6+ — pull all Sentry events from bei-hrms + bei-tasks during sweep windows.

Per Sam directive (2026-04-27): no out-of-scope defects. Pull every error in both
projects across the sweep windows to inform remediation.

Windows queried (UTC):
  - Phase 1 sweep (post-S226): ~2026-04-27T08:00Z → 2026-04-27T09:00Z (best-effort)
  - Phase 5 stress + Phase 6 sweep: 2026-04-27T08:48:27Z → 2026-04-27T09:45:00Z

Output:
  output/s225/verification/sentry_events_sweep.json (full per-event detail)
  output/s225/verification/sentry_events_summary.md (human-readable bucketing)
"""
from __future__ import annotations
import json
import pathlib
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT_JSON = ROOT / "output" / "s225" / "verification" / "sentry_events_sweep.json"
OUT_MD = ROOT / "output" / "s225" / "verification" / "sentry_events_summary.md"
OUT_JSON.parent.mkdir(parents=True, exist_ok=True)

ORG = "bebang-enterprise-inc"
PROJECTS = ["bei-hrms", "bei-tasks"]


def doppler_get(secret: str) -> str:
    return subprocess.check_output(
        ["C:/Users/Sam/bin/doppler.exe", "secrets", "get", secret, "--plain", "--project", "bei-erp", "--config", "dev"],
        text=True,
        creationflags=0x08000000 if sys.platform == "win32" else 0,
    ).strip()


def sentry_get(path: str, token: str, params: dict | None = None) -> object:
    url = f"https://sentry.io{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def main() -> int:
    token = doppler_get("SENTRY_API_TOKEN")
    print(f"Got SENTRY_API_TOKEN ({len(token)} chars)", flush=True)

    # Query window: today's full day so we catch all sweep activity
    today = datetime.now(timezone.utc).date()
    start = datetime(today.year, today.month, today.day, 0, 0, 0, tzinfo=timezone.utc)
    end = datetime.now(timezone.utc) + timedelta(minutes=5)

    payload: dict = {
        "window_start_utc": start.isoformat(),
        "window_end_utc": end.isoformat(),
        "by_project": {},
    }

    for project in PROJECTS:
        print(f"\n=== {project} ===", flush=True)
        try:
            events = sentry_get(
                f"/api/0/projects/{ORG}/{project}/events/",
                token,
                params={
                    "start": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "end": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "full": "true",
                    "limit": 200,
                },
            )
        except urllib.error.HTTPError as e:
            print(f"  HTTPError {e.code}: {e.read().decode()[:200]}", flush=True)
            payload["by_project"][project] = {"error": f"{e.code}: {e.reason}"}
            continue
        except Exception as e:
            print(f"  Error: {e}", flush=True)
            payload["by_project"][project] = {"error": str(e)}
            continue

        ev_list = events if isinstance(events, list) else []
        proj = {
            "event_count": len(ev_list),
            "events": [],
            "by_title": Counter(),
            "by_culprit": Counter(),
            "by_level": Counter(),
        }
        for ev in ev_list:
            entry = {
                "id": ev.get("id"),
                "eventID": ev.get("eventID"),
                "title": (ev.get("title") or "")[:300],
                "type": ev.get("type"),
                "level": ev.get("level"),
                "platform": ev.get("platform"),
                "dateCreated": ev.get("dateCreated"),
                "culprit": (ev.get("culprit") or "")[:300],
                "tags": {t["key"]: t["value"] for t in ev.get("tags", []) if "key" in t and "value" in t},
                "user": ev.get("user", {}).get("username") if ev.get("user") else None,
                "groupID": ev.get("groupID"),
                "message": (ev.get("message") or "")[:500],
            }
            # bucket key (strip volatile IDs/dates from title for cleaner buckets)
            import re
            bucket = re.sub(r"BEI-[A-Z]+-\d{4}-\d+", "<ID>", entry["title"])
            bucket = re.sub(r"MAT-[A-Z]+-\d{4}-\d+", "<MR>", bucket)
            bucket = re.sub(r"\d{4}-\d{2}-\d{2}", "<DATE>", bucket)
            entry["bucket"] = bucket[:200]
            proj["events"].append(entry)
            proj["by_title"][bucket[:200]] += 1
            if entry["culprit"]:
                proj["by_culprit"][entry["culprit"][:200]] += 1
            if entry["level"]:
                proj["by_level"][entry["level"]] += 1

        # Convert Counters to lists for JSON
        proj["by_title"] = dict(proj["by_title"])
        proj["by_culprit"] = dict(proj["by_culprit"])
        proj["by_level"] = dict(proj["by_level"])
        payload["by_project"][project] = proj

        print(f"  Total events: {proj['event_count']}", flush=True)
        print(f"  Top buckets:")
        for k, v in sorted(proj["by_title"].items(), key=lambda x: -x[1])[:8]:
            print(f"    {v}× {k[:120]}")

    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    # Build summary MD
    md = []
    md.append("# Sentry Events — S225 Sweep Window")
    md.append("")
    md.append(f"Window UTC: {payload['window_start_utc']} → {payload['window_end_utc']}")
    md.append("")
    for project, data in payload["by_project"].items():
        md.append(f"## Project: `{project}`")
        md.append("")
        if isinstance(data, dict) and "error" in data:
            md.append(f"Error: {data['error']}")
            md.append("")
            continue
        md.append(f"Total events: {data['event_count']}")
        md.append("")
        md.append("### By level")
        md.append("")
        for k, v in sorted(data.get("by_level", {}).items(), key=lambda x: -x[1]):
            md.append(f"- **{k}**: {v}")
        md.append("")
        md.append("### Top buckets (title-normalized)")
        md.append("")
        md.append("| Count | Bucket |")
        md.append("|---|---|")
        for k, v in sorted(data.get("by_title", {}).items(), key=lambda x: -x[1])[:25]:
            md.append(f"| {v} | `{k[:200]}` |")
        md.append("")
        md.append("### Top culprits (file:line)")
        md.append("")
        md.append("| Count | Culprit |")
        md.append("|---|---|")
        for k, v in sorted(data.get("by_culprit", {}).items(), key=lambda x: -x[1])[:15]:
            md.append(f"| {v} | `{k[:200]}` |")
        md.append("")
        md.append("### First 30 events (chronological)")
        md.append("")
        sorted_events = sorted(data.get("events", []), key=lambda e: e.get("dateCreated") or "")
        for ev in sorted_events[:30]:
            md.append(f"- [{ev.get('dateCreated')}] **{ev.get('level','-')}** `{ev.get('culprit','-')}` — {ev.get('title','')[:200]}")
        md.append("")

    OUT_MD.write_text("\n".join(md), encoding="utf-8")
    print(f"\nWrote {OUT_JSON}")
    print(f"Wrote {OUT_MD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
