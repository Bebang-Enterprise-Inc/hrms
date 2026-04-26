#!/usr/bin/env python3
"""S224 - hunt for Pattern C (MR creation stalls) errors in Sentry.

Looks at a wider 7-day window for events tagged with NAIA T3, ORTIGAS ESTANCIA,
ORTIGAS GREENHILLS, or with module=ordering action=submit_order /
_create_mr_for_store_order.
"""
from __future__ import annotations
import json
import pathlib
import subprocess
import sys
import urllib.parse
import urllib.request

OUT = pathlib.Path(__file__).resolve().parent.parent / "output" / "s223" / "verification" / "sentry_pattern_c_hunt.json"
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
    print(f"Got token: {token[:10]}...{token[-4:]}", flush=True)

    queries = [
        ("submit_order errors 7d", {"query": 'action:submit_order', "statsPeriod": "7d"}),
        ("approve_order errors 7d", {"query": 'action:approve_order', "statsPeriod": "7d"}),
        ("MR Creation Error 7d", {"query": 'message:"MR Creation Error"', "statsPeriod": "7d"}),
        ("NAIA T3 7d", {"query": '"NAIA T3"', "statsPeriod": "7d"}),
        ("ORTIGAS ESTANCIA 7d", {"query": '"ORTIGAS ESTANCIA"', "statsPeriod": "7d"}),
        ("ORTIGAS GREENHILLS 7d", {"query": '"ORTIGAS GREENHILLS"', "statsPeriod": "7d"}),
        ("create_mr_for_store_order 7d", {"query": 'create_mr_for_store_order', "statsPeriod": "7d"}),
        ("module:ordering 24h", {"query": 'module:ordering', "statsPeriod": "24h"}),
    ]

    result: dict = {}
    for label, params in queries:
        result[label] = {}
        for project_slug in ("bei-hrms", "bei-tasks"):
            try:
                # Use issues endpoint instead of events for grouped view
                issues = sentry_get(
                    f"/api/0/projects/{ORG}/{project_slug}/issues/",
                    token,
                    params=dict(params, **{"limit": 25}),
                )
            except Exception as e:
                result[label][project_slug] = {"error": str(e)[:200]}
                continue
            simplified = []
            issues_iter = issues if isinstance(issues, list) else []
            for iss in issues_iter[:25]:
                simplified.append({
                    "id": iss.get("id"),
                    "title": (iss.get("title") or "")[:200],
                    "level": iss.get("level"),
                    "count": iss.get("count"),
                    "userCount": iss.get("userCount"),
                    "firstSeen": iss.get("firstSeen"),
                    "lastSeen": iss.get("lastSeen"),
                    "metadata": iss.get("metadata", {}),
                    "permalink": iss.get("permalink"),
                })
            result[label][project_slug] = simplified
            print(f"\n[{label}] {project_slug}: {len(simplified)} issues")
            for s in simplified[:6]:
                print(f"  {s['count']:>4}× {s['title'][:120]}")
                if s.get("userCount"):
                    print(f"        users: {s['userCount']}, last: {s.get('lastSeen', '?')[:19]}")

    OUT.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
