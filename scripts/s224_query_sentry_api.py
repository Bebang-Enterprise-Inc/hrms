#!/usr/bin/env python3
"""S224 - query Sentry REST API directly during S223 L3 sweep window.

Uses SENTRY_API_TOKEN from Doppler. Bypasses the (currently failing) Sentry MCP server.

Sweep window: 2026-04-26T05:19:52Z -> 2026-04-26T06:05:07Z UTC

Outputs:
- output/s223/verification/sentry_events_during_sweep.json
- Console summary by issue, by module, by store
"""
from __future__ import annotations
import json
import pathlib
import subprocess
import sys
import time
import urllib.parse
import urllib.request

OUT = pathlib.Path(__file__).resolve().parent.parent / "output" / "s223" / "verification" / "sentry_events_during_sweep.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

ORG = "bebang-enterprise-inc"
PROJECTS = ["bei-hrms", "bei-tasks"]
WINDOW_START = "2026-04-26T05:19:52Z"
WINDOW_END = "2026-04-26T06:05:07Z"


def doppler_get(secret: str) -> str:
    return subprocess.check_output(
        ["C:/Users/Sam/bin/doppler.exe", "secrets", "get", secret, "--plain", "--project", "bei-erp", "--config", "dev"],
        text=True,
    ).strip()


def sentry_get(path: str, token: str, params: dict | None = None) -> dict:
    url = f"https://sentry.io{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def main() -> int:
    token = doppler_get("SENTRY_API_TOKEN")
    print(f"Got SENTRY_API_TOKEN: {token[:10]}...{token[-4:]}", flush=True)

    result: dict = {
        "window_start_utc": WINDOW_START,
        "window_end_utc": WINDOW_END,
        "by_project": {},
    }

    for project_slug in PROJECTS:
        print(f"\n=== {project_slug} ===", flush=True)
        try:
            events = sentry_get(
                f"/api/0/projects/{ORG}/{project_slug}/events/",
                token,
                params={
                    "start": WINDOW_START,
                    "end": WINDOW_END,
                    "full": "true",
                    "limit": 100,
                },
            )
        except urllib.error.HTTPError as e:
            print(f"  HTTPError {e.code}: {e.read().decode()[:200]}", flush=True)
            result["by_project"][project_slug] = {"error": f"{e.code}: {e.reason}"}
            continue
        except Exception as e:
            print(f"  Error: {e}", flush=True)
            result["by_project"][project_slug] = {"error": str(e)}
            continue

        # Sentry returns a list of events directly for this endpoint
        proj_data: dict = {"event_count": len(events) if isinstance(events, list) else 0, "events": []}
        events_iter = events if isinstance(events, list) else []
        for ev in events_iter[:100]:
            entry = {
                "id": ev.get("id"),
                "eventID": ev.get("eventID"),
                "title": ev.get("title", "")[:200],
                "type": ev.get("type"),
                "level": ev.get("level"),
                "platform": ev.get("platform"),
                "dateCreated": ev.get("dateCreated"),
                "culprit": ev.get("culprit", "")[:200],
                "tags": {t["key"]: t["value"] for t in ev.get("tags", []) if "key" in t and "value" in t},
                "user": ev.get("user", {}).get("username") if ev.get("user") else None,
                "groupID": ev.get("groupID"),
                "message": (ev.get("message") or "")[:400],
            }
            proj_data["events"].append(entry)

        result["by_project"][project_slug] = proj_data

        print(f"  Total events: {proj_data['event_count']}", flush=True)
        # Bucket by tag.module + action
        from collections import Counter
        bucket = Counter()
        store_bucket = Counter()
        title_bucket = Counter()
        for e in proj_data["events"]:
            mod = e["tags"].get("module", "?")
            act = e["tags"].get("action", e["tags"].get("route_action", "?"))
            bucket[f"{mod}/{act}"] += 1
            for k, v in e["tags"].items():
                if "store" in k.lower() or "warehouse" in k.lower() or k == "destination":
                    store_bucket[v] += 1
            title_bucket[e["title"][:80]] += 1
        print(f"  Top module/action buckets:")
        for k, c in bucket.most_common(10):
            print(f"    {c:3d}  {k}")
        if store_bucket:
            print(f"  Top store/warehouse tags:")
            for k, c in store_bucket.most_common(8):
                print(f"    {c:3d}  {k}")
        print(f"  Top issue titles:")
        for k, c in title_bucket.most_common(8):
            print(f"    {c:3d}  {k[:80]}")

    OUT.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
