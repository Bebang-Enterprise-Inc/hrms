#!/usr/bin/env python3
"""Verify restore-drill readiness from backup-manifest evidence.

Exit codes:
  0 = all checks passed
  1 = checks passed with warnings (non-strict mode only)
  2 = one or more checks failed, or warnings were escalated by --strict
  3 = runtime/argument error
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

EXIT_ALL_PASS = 0
EXIT_WARNINGS = 1
EXIT_FAILED = 2
EXIT_ERROR = 3

EXIT_LABELS = {
    EXIT_ALL_PASS: "all_pass",
    EXIT_WARNINGS: "pass_with_warnings",
    EXIT_FAILED: "failed",
    EXIT_ERROR: "runtime_error",
}


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_timestamp(value: str) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = value.strip()
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def add_check(
    checks: list[dict[str, Any]],
    check_id: str,
    description: str,
    status: str,
    details: str,
) -> None:
    checks.append(
        {
            "id": check_id,
            "description": description,
            "status": status,
            "details": details,
        }
    )


def collect_status_value(manifest: dict[str, Any]) -> str | None:
    status_keys = ("status", "overall_status", "result")
    for key in status_keys:
        value = manifest.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    summary = manifest.get("summary")
    if isinstance(summary, dict):
        for key in status_keys:
            value = summary.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def determine_exit_code(pass_count: int, warn_count: int, fail_count: int, strict: bool) -> int:
    if fail_count > 0:
        return EXIT_FAILED
    if strict and warn_count > 0:
        return EXIT_FAILED
    if warn_count > 0:
        return EXIT_WARNINGS
    return EXIT_ALL_PASS


def build_report(run_id: str, backup_manifest_path: Path, strict: bool, max_age_hours: int) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    manifest_data: dict[str, Any] | None = None

    if backup_manifest_path.exists():
        add_check(
            checks,
            "backup_manifest_exists",
            "Backup manifest exists",
            "pass",
            "found",
        )
        try:
            loaded = json.loads(backup_manifest_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                manifest_data = loaded
                add_check(
                    checks,
                    "backup_manifest_json",
                    "Backup manifest is valid JSON object",
                    "pass",
                    "parsed",
                )
            else:
                add_check(
                    checks,
                    "backup_manifest_json",
                    "Backup manifest is valid JSON object",
                    "fail",
                    f"invalid_type={type(loaded).__name__}",
                )
        except json.JSONDecodeError as exc:
            add_check(
                checks,
                "backup_manifest_json",
                "Backup manifest is valid JSON object",
                "fail",
                f"json_decode_error={exc}",
            )
    else:
        add_check(
            checks,
            "backup_manifest_exists",
            "Backup manifest exists",
            "fail",
            "missing",
        )
        add_check(
            checks,
            "backup_manifest_json",
            "Backup manifest is valid JSON object",
            "fail",
            "skipped_manifest_missing",
        )

    if manifest_data is not None:
        status_value = collect_status_value(manifest_data)
        if status_value is None:
            add_check(
                checks,
                "manifest_status",
                "Manifest has an overall status marker",
                "warn",
                "status_field_not_found",
            )
        else:
            normalized = status_value.lower()
            pass_markers = {"pass", "passed", "ok", "success", "complete", "completed", "ready"}
            fail_markers = {"fail", "failed", "error", "blocked", "critical"}
            if normalized in pass_markers:
                add_check(
                    checks,
                    "manifest_status",
                    "Manifest has an overall status marker",
                    "pass",
                    f"status={status_value}",
                )
            elif normalized in fail_markers:
                add_check(
                    checks,
                    "manifest_status",
                    "Manifest has an overall status marker",
                    "fail",
                    f"status={status_value}",
                )
            else:
                add_check(
                    checks,
                    "manifest_status",
                    "Manifest has an overall status marker",
                    "warn",
                    f"status_unclassified={status_value}",
                )

        ts_candidates = (
            "generated_at",
            "generated_at_utc",
            "timestamp",
            "created_at",
            "run_at",
            "checked_at",
        )
        ts_value = None
        for key in ts_candidates:
            value = manifest_data.get(key)
            if isinstance(value, str) and value.strip():
                ts_value = value
                break
        if ts_value is None and isinstance(manifest_data.get("summary"), dict):
            summary = manifest_data["summary"]
            for key in ts_candidates:
                value = summary.get(key)
                if isinstance(value, str) and value.strip():
                    ts_value = value
                    break

        if ts_value is None:
            add_check(
                checks,
                "manifest_recency",
                f"Manifest timestamp is within {max_age_hours} hours",
                "warn",
                "timestamp_missing",
            )
        else:
            parsed_ts = parse_timestamp(ts_value)
            if parsed_ts is None:
                add_check(
                    checks,
                    "manifest_recency",
                    f"Manifest timestamp is within {max_age_hours} hours",
                    "warn",
                    f"timestamp_unparseable={ts_value}",
                )
            else:
                age = datetime.now(timezone.utc) - parsed_ts
                if age <= timedelta(hours=max_age_hours):
                    add_check(
                        checks,
                        "manifest_recency",
                        f"Manifest timestamp is within {max_age_hours} hours",
                        "pass",
                        f"age_hours={round(age.total_seconds() / 3600, 2)}",
                    )
                else:
                    add_check(
                        checks,
                        "manifest_recency",
                        f"Manifest timestamp is within {max_age_hours} hours",
                        "warn",
                        f"stale_age_hours={round(age.total_seconds() / 3600, 2)}",
                    )

        manifest_blob = json.dumps(manifest_data).lower()
        if "backup" in manifest_blob:
            add_check(
                checks,
                "manifest_backup_signal",
                "Manifest contains backup signal",
                "pass",
                "backup_keyword_found",
            )
        else:
            add_check(
                checks,
                "manifest_backup_signal",
                "Manifest contains backup signal",
                "warn",
                "backup_keyword_not_found",
            )

        if "restore" in manifest_blob:
            add_check(
                checks,
                "manifest_restore_signal",
                "Manifest contains restore signal",
                "pass",
                "restore_keyword_found",
            )
        else:
            add_check(
                checks,
                "manifest_restore_signal",
                "Manifest contains restore signal",
                "warn",
                "restore_keyword_not_found",
            )
    else:
        add_check(
            checks,
            "manifest_status",
            "Manifest has an overall status marker",
            "fail",
            "skipped_manifest_invalid_or_missing",
        )
        add_check(
            checks,
            "manifest_recency",
            f"Manifest timestamp is within {max_age_hours} hours",
            "fail",
            "skipped_manifest_invalid_or_missing",
        )
        add_check(
            checks,
            "manifest_backup_signal",
            "Manifest contains backup signal",
            "fail",
            "skipped_manifest_invalid_or_missing",
        )
        add_check(
            checks,
            "manifest_restore_signal",
            "Manifest contains restore signal",
            "fail",
            "skipped_manifest_invalid_or_missing",
        )

    pass_count = sum(1 for c in checks if c["status"] == "pass")
    warn_count = sum(1 for c in checks if c["status"] == "warn")
    fail_count = sum(1 for c in checks if c["status"] == "fail")
    exit_code = determine_exit_code(pass_count, warn_count, fail_count, strict)
    drill_verified = exit_code in (EXIT_ALL_PASS, EXIT_WARNINGS)

    return {
        "script": "scripts/finance/verify_restore_drill.py",
        "generated_at_utc": now_utc_iso(),
        "run_id": run_id,
        "strict": strict,
        "inputs": {
            "backup_manifest": str(backup_manifest_path),
            "max_age_hours": max_age_hours,
        },
        "checks": checks,
        "summary": {
            "pass": pass_count,
            "warn": warn_count,
            "fail": fail_count,
            "drill_verified": drill_verified,
            "exit_code": exit_code,
            "exit_label": EXIT_LABELS[exit_code],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify restore drill evidence from backup manifest.")
    parser.add_argument("--run-id", required=True, help="Run unit ID, e.g. 20260228-finance-config-a")
    parser.add_argument("--backup-manifest", required=True, help="Path to PRE_DEPLOY_DEPENDENCY_CHECK.json")
    parser.add_argument("--out", required=True, help="Path to output JSON report")
    parser.add_argument("--max-age-hours", type=int, default=72, help="Recency window for manifest timestamp")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures")
    args = parser.parse_args()

    try:
        report = build_report(
            run_id=args.run_id,
            backup_manifest_path=Path(args.backup_manifest),
            strict=args.strict,
            max_age_hours=args.max_age_hours,
        )

        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

        summary = report["summary"]
        print(
            f"[verify_restore_drill] pass={summary['pass']} warn={summary['warn']} "
            f"fail={summary['fail']} drill_verified={summary['drill_verified']} "
            f"exit_code={summary['exit_code']}"
        )
        return int(summary["exit_code"])
    except Exception as exc:  # pragma: no cover - defensive wrapper
        print(f"[verify_restore_drill] runtime_error: {exc}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
