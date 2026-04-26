#!/usr/bin/env python3
"""S224 - fetch FULL traceback + tags for a specific Sentry event.

Pulls the most-recent N events from bei-hrms during the S223 sweep window with
their FULL exception data (traceback frames, breadcrumbs, tags) so we can read
the exact failure state for Pattern A and Pattern B events.

Outputs: output/s223/verification/sentry_event_details.json
"""
from __future__ import annotations
import json
import pathlib
import subprocess
import sys
import urllib.parse
import urllib.request

OUT = pathlib.Path(__file__).resolve().parent.parent / "output" / "s223" / "verification" / "sentry_event_details.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

ORG = "bebang-enterprise-inc"
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
    print(f"Got token: {token[:10]}...{token[-4:]}", flush=True)

    result: dict = {"events": []}

    for project_slug in ("bei-hrms", "bei-tasks"):
        events = sentry_get(
            f"/api/0/projects/{ORG}/{project_slug}/events/",
            token,
            params={"start": WINDOW_START, "end": WINDOW_END, "limit": 50, "full": "true"},
        )
        if not isinstance(events, list):
            continue
        # Pull detail for first 6 events that look like Pattern A/B/C
        keepers = []
        for e in events:
            title = (e.get("title") or "").lower()
            if any(kw in title for kw in [
                "create_stock_transfer", "approve_material_request", "already been approved",
                "stock decreased", "batch", "material request", "create transfer",
                "approve_mr", "create_mr_for_store_order", "submit_order",
            ]):
                keepers.append(e)
            if len(keepers) >= 8:
                break
        # Get full details
        for ev in keepers:
            ev_id = ev.get("eventID") or ev.get("id")
            if not ev_id:
                continue
            try:
                detail = sentry_get(f"/api/0/projects/{ORG}/{project_slug}/events/{ev_id}/", token)
            except Exception as exc:
                detail = {"_fetch_error": str(exc)}

            # Compress to relevant fields
            entries = detail.get("entries", []) or []
            exception_entry = next((e for e in entries if e.get("type") == "exception"), {})
            exc_values = (exception_entry.get("data") or {}).get("values", [])
            traceback = []
            for ev_x in exc_values:
                stack = (ev_x.get("stacktrace") or {}).get("frames") or []
                for f in stack[-6:]:  # last 6 frames most relevant
                    traceback.append({
                        "filename": (f.get("filename") or "")[-80:],
                        "function": f.get("function"),
                        "lineNo": f.get("lineNo"),
                        "context": (f.get("context") or [])[:3],
                    })
                traceback.append({"_exception": ev_x.get("type"), "_value": (ev_x.get("value") or "")[:300]})

            breadcrumbs_entry = next((e for e in entries if e.get("type") == "breadcrumbs"), {})
            breadcrumbs = []
            bvals = (breadcrumbs_entry.get("data") or {}).get("values", []) or []
            for b in bvals[-10:]:  # last 10 breadcrumbs
                breadcrumbs.append({
                    "category": b.get("category"),
                    "message": (b.get("message") or "")[:200],
                    "level": b.get("level"),
                    "data": {k: str(v)[:120] for k, v in (b.get("data") or {}).items()},
                })

            request_entry = next((e for e in entries if e.get("type") == "request"), {})
            req_data = request_entry.get("data") or {}

            result["events"].append({
                "project": project_slug,
                "eventID": ev_id,
                "title": detail.get("title", "")[:200],
                "culprit": detail.get("culprit", "")[:200],
                "dateCreated": detail.get("dateCreated"),
                "level": detail.get("level"),
                "tags": {t["key"]: t["value"] for t in detail.get("tags", []) if "key" in t},
                "user": (detail.get("user") or {}).get("username"),
                "request_url": req_data.get("url", "")[:200],
                "request_method": req_data.get("method"),
                "request_data": str(req_data.get("data", ""))[:500],
                "traceback": traceback,
                "breadcrumbs": breadcrumbs,
            })

    OUT.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote: {OUT}\n")
    print(f"Captured {len(result['events'])} events with full detail.")
    print("\n=== KEY EVENTS ===")
    for e in result["events"]:
        print(f"\n[{e['project']}] {e['title']}")
        print(f"  user: {e.get('user')} | url: {e.get('request_url')}")
        print(f"  tags.module={e['tags'].get('module')} tags.action={e['tags'].get('action')}")
        for k, v in e["tags"].items():
            if "store" in k.lower() or "warehouse" in k.lower() or "destination" in k.lower() or "mr_name" in k.lower():
                print(f"    {k}: {v}")
        # Last exception value
        for f in e["traceback"][-3:]:
            if "_exception" in f:
                print(f"  >> {f['_exception']}: {f['_value'][:200]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
