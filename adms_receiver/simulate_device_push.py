from __future__ import annotations

import argparse
from datetime import datetime

import requests


def main() -> int:
    ap = argparse.ArgumentParser(description="Simulate ADMS/iClock device handshake + ATTLOG push")
    ap.add_argument("--base", required=True, help="Receiver base URL, e.g. http://localhost:8008")
    ap.add_argument("--sn", required=True, help="Device serial number")
    ap.add_argument("--pin", required=True, help="PIN / attendance_device_id")
    ap.add_argument("--status", default="1", help="ATTLOG status code")
    ap.add_argument("--verify", default="1", help="ATTLOG verify code")
    ap.add_argument("--stamp", default="9999", help="Stamp")
    args = ap.parse_args()

    base = args.base.rstrip("/")

    # Handshake
    r = requests.get(
        base + "/iclock/cdata",
        params={"SN": args.sn, "options": "all", "language": "73", "pushver": "2.4.0"},
        timeout=30,
    )
    print("handshake_status:", r.status_code)
    print(r.text[:300])

    # ATTLOG post
    ts = datetime.now().replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
    line = f"{args.pin}\t{ts}\t{args.status}\t{args.verify}\t\t0\t0\t\n"

    r2 = requests.post(
        base + "/iclock/cdata",
        params={"SN": args.sn, "table": "ATTLOG", "Stamp": args.stamp},
        data=line.encode("utf-8"),
        timeout=30,
    )
    print("attlog_status:", r2.status_code)
    print(r2.text[:200])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
