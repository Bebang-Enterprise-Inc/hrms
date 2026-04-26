#!/usr/bin/env python3
"""S224 - get the full traceback for 'Could not find Store: Estancia' to find exact code path."""
from __future__ import annotations
import json
import pathlib
import subprocess
import sys
import urllib.parse
import urllib.request

OUT = pathlib.Path(__file__).resolve().parent.parent / "output" / "s223" / "verification" / "sentry_estancia_traceback.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

ORG = "bebang-enterprise-inc"


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

    # Find issues with module:ordering — Sentry issues endpoint only accepts 14d max
    issues = sentry_get(
        f"/api/0/projects/{ORG}/bei-hrms/issues/",
        token,
        params={"query": "module:ordering", "statsPeriod": "14d", "limit": 25},
    )
    if not isinstance(issues, list):
        print(f"Unexpected response: {issues}")
        return 1

    result: dict = {"issues": []}
    for iss in issues:
        iss_id = iss.get("id")
        title = iss.get("title", "")[:150]
        print(f"\n=== ISSUE {iss_id}: {title} ===")
        # Get latest event for this issue
        try:
            ev = sentry_get(f"/api/0/issues/{iss_id}/events/latest/", token)
        except Exception as e:
            print(f"  Failed to fetch event: {e}")
            continue

        entries = ev.get("entries", [])
        # Find exception entry
        exc_entry = next((e for e in entries if e.get("type") == "exception"), {})
        exc_values = (exc_entry.get("data") or {}).get("values", [])

        sample = {
            "id": iss_id,
            "title": title,
            "lastSeen": iss.get("lastSeen"),
            "count": iss.get("count"),
            "permalink": iss.get("permalink"),
            "event": {
                "eventID": ev.get("eventID"),
                "dateCreated": ev.get("dateCreated"),
                "tags": {t["key"]: t["value"] for t in ev.get("tags", []) if "key" in t},
                "user": (ev.get("user") or {}).get("username"),
                "exceptions": [],
            },
        }

        for exc in exc_values:
            stack = (exc.get("stacktrace") or {}).get("frames") or []
            sample["event"]["exceptions"].append({
                "type": exc.get("type"),
                "value": (exc.get("value") or "")[:400],
                "frames_tail": [
                    {
                        "file": (f.get("filename") or "")[-100:],
                        "func": f.get("function"),
                        "line": f.get("lineNo"),
                        "context": (f.get("context") or [])[-3:],  # only last 3 lines
                    }
                    for f in stack[-15:]  # last 15 frames
                ],
            })

        result["issues"].append(sample)

        # Print
        print(f"  count={sample['count']} last={sample.get('lastSeen', '?')[:19]}")
        print(f"  permalink: {sample.get('permalink')}")
        for k, v in sample["event"]["tags"].items():
            if k in ("module", "action", "endpoint_or_job", "phase", "store_warehouse", "order_name"):
                print(f"    tag.{k}: {v}")
        for exc in sample["event"]["exceptions"]:
            print(f"  >> {exc['type']}: {exc['value'][:200]}")
            print(f"  Stack tail (last 8 frames):")
            for f in exc["frames_tail"][-8:]:
                print(f"    {f['file']}:{f.get('line')} {f.get('func')}()")

    OUT.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
