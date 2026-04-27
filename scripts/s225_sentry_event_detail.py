"""S225 — pull full event detail (traceback, breadcrumbs) for specific Sentry event IDs."""
from __future__ import annotations
import argparse
import json
import pathlib
import subprocess
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
ORG = "bebang-enterprise-inc"


def doppler_get(secret: str) -> str:
    return subprocess.check_output(
        ["C:/Users/Sam/bin/doppler.exe", "secrets", "get", secret, "--plain", "--project", "bei-erp", "--config", "dev"],
        text=True,
        creationflags=0x08000000 if sys.platform == "win32" else 0,
    ).strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True, choices=["bei-hrms", "bei-tasks"])
    ap.add_argument("--event-id", required=True, action="append",
                    help="Sentry event ID(s). Repeat for multiple.")
    args = ap.parse_args()

    token = doppler_get("SENTRY_API_TOKEN")
    out_dir = ROOT / "output" / "s225" / "verification" / "sentry_event_detail"
    out_dir.mkdir(parents=True, exist_ok=True)

    for event_id in args.event_id:
        url = f"https://sentry.io/api/0/projects/{ORG}/{args.project}/events/{event_id}/"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
        except Exception as e:
            print(f"Event {event_id}: {e}")
            continue

        out_path = out_dir / f"{args.project}_{event_id}.json"
        out_path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        print(f"\n=== {args.project}/{event_id} ===")
        print(f"Title: {data.get('title')}")
        print(f"Date: {data.get('dateCreated')}")
        print(f"Culprit: {data.get('culprit')}")
        print(f"User: {(data.get('user') or {}).get('username')}")
        print(f"Tags: {[(t.get('key'), t.get('value')) for t in (data.get('tags') or [])][:8]}")
        # Print frames from the exception
        entries = data.get("entries") or []
        for e in entries:
            if e.get("type") == "exception":
                values = (e.get("data") or {}).get("values") or []
                for v in values:
                    print(f"\n  Exception: {v.get('type')}: {v.get('value')[:300]}")
                    frames = ((v.get("stacktrace") or {}).get("frames") or [])
                    for f in frames[-6:]:  # last 6 frames (closest to error)
                        fname = f.get("function") or "<unknown>"
                        loc = f.get("filename") or "<unknown>"
                        lineno = f.get("lineNo")
                        print(f"    at {fname} ({loc}:{lineno})")
                        ctx = f.get("context") or []
                        for line in ctx:
                            if isinstance(line, list) and len(line) >= 2 and line[0] == lineno:
                                print(f"      >>> {str(line[1])[:200]}")
                                break
        print(f"\n  Wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
