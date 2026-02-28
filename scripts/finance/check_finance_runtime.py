#!/usr/bin/env python3
"""Finance runtime checker for Sprint A evidence closeout.

Exit codes:
  0 = all checks passed
  1 = checks passed with warnings (non-strict mode only)
  2 = one or more checks failed, or warnings were escalated by --strict
  3 = runtime/argument error
"""

from __future__ import annotations

import argparse
import json
import py_compile
import re
import sys
import tempfile
from datetime import datetime, timezone
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


def read_text(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def compile_python(path: Path) -> tuple[bool, str]:
	try:
		with tempfile.NamedTemporaryFile(prefix="finance_runtime_", suffix=".pyc", delete=False) as tmp:
			cfile = tmp.name
		py_compile.compile(str(path), cfile=cfile, doraise=True)
		Path(cfile).unlink(missing_ok=True)
		return True, "syntax_ok"
	except py_compile.PyCompileError as exc:
		return False, str(exc)


def determine_exit_code(pass_count: int, warn_count: int, fail_count: int, strict: bool) -> int:
	if fail_count > 0:
		return EXIT_FAILED
	if strict and warn_count > 0:
		return EXIT_FAILED
	if warn_count > 0:
		return EXIT_WARNINGS
	return EXIT_ALL_PASS


def build_report(root: Path, strict: bool) -> dict[str, Any]:
	checks: list[dict[str, Any]] = []

	required_paths = [
		"hrms/api/procurement.py",
		"hrms/hr/doctype/bei_billing_schedule/bei_billing_schedule.json",
		"hrms/hr/doctype/bei_store_type/bei_store_type.json",
		"hrms/hr/doctype/bei_payment_request/bei_payment_request.py",
	]

	for rel in required_paths:
		target = root / rel
		if target.exists():
			add_check(checks, f"file_exists:{rel}", f"File exists: {rel}", "pass", "found")
		else:
			add_check(checks, f"file_exists:{rel}", f"File exists: {rel}", "fail", "missing")

	procurement_path = root / "hrms/api/procurement.py"
	if procurement_path.exists():
		procurement_text = read_text(procurement_path)
		required_endpoints = [
			"apply_franchise_payment",
			"generate_monthly_billing",
			"get_ap_aging_report",
		]
		missing = [
			name
			for name in required_endpoints
			if not re.search(rf"^def\s+{re.escape(name)}\s*\(", procurement_text, flags=re.MULTILINE)
		]
		if missing:
			add_check(
				checks,
				"procurement_required_endpoints",
				"Required finance endpoints are present in hrms/api/procurement.py",
				"fail",
				f"missing_endpoints={missing}",
			)
		else:
			add_check(
				checks,
				"procurement_required_endpoints",
				"Required finance endpoints are present in hrms/api/procurement.py",
				"pass",
				"all_required_endpoints_found",
			)
	else:
		add_check(
			checks,
			"procurement_required_endpoints",
			"Required finance endpoints are present in hrms/api/procurement.py",
			"fail",
			"file_missing",
		)

	billing_json_path = root / "hrms/hr/doctype/bei_billing_schedule/bei_billing_schedule.json"
	if billing_json_path.exists():
		try:
			billing_data = json.loads(read_text(billing_json_path))
			status_field = next(
				(
					f
					for f in billing_data.get("fields", [])
					if isinstance(f, dict) and f.get("fieldname") == "status"
				),
				None,
			)
			options = str((status_field or {}).get("options", ""))
			if "Partially Paid" in options:
				add_check(
					checks,
					"billing_status_options",
					"BEI Billing Schedule status includes 'Partially Paid'",
					"pass",
					"status_option_present",
				)
			else:
				add_check(
					checks,
					"billing_status_options",
					"BEI Billing Schedule status includes 'Partially Paid'",
					"fail",
					"status_option_missing",
				)
		except json.JSONDecodeError as exc:
			add_check(
				checks,
				"billing_status_options",
				"BEI Billing Schedule status includes 'Partially Paid'",
				"fail",
				f"invalid_json={exc}",
			)
	else:
		add_check(
			checks,
			"billing_status_options",
			"BEI Billing Schedule status includes 'Partially Paid'",
			"fail",
			"file_missing",
		)

	payment_request_path = root / "hrms/hr/doctype/bei_payment_request/bei_payment_request.py"
	if payment_request_path.exists():
		payment_request_text = read_text(payment_request_path)
		if re.search(r"^def\s+_get_account_by_code\s*\(", payment_request_text, flags=re.MULTILINE):
			add_check(
				checks,
				"payment_request_gl_lookup",
				"Payment Request has _get_account_by_code helper",
				"pass",
				"helper_found",
			)
		else:
			add_check(
				checks,
				"payment_request_gl_lookup",
				"Payment Request has _get_account_by_code helper",
				"warn",
				"helper_not_found",
			)
	else:
		add_check(
			checks,
			"payment_request_gl_lookup",
			"Payment Request has _get_account_by_code helper",
			"fail",
			"file_missing",
		)

	syntax_targets = [procurement_path, payment_request_path]
	syntax_failures: list[str] = []
	missing_targets: list[str] = []
	for target in syntax_targets:
		if not target.exists():
			missing_targets.append(str(target.relative_to(root)))
			continue
		ok, detail = compile_python(target)
		if not ok:
			syntax_failures.append(f"{target.relative_to(root)}: {detail}")

	if missing_targets:
		add_check(
			checks,
			"python_syntax_finance_modules",
			"Python syntax validation for finance modules",
			"fail",
			f"missing_targets={missing_targets}",
		)
	elif syntax_failures:
		add_check(
			checks,
			"python_syntax_finance_modules",
			"Python syntax validation for finance modules",
			"fail",
			"; ".join(syntax_failures),
		)
	else:
		add_check(
			checks,
			"python_syntax_finance_modules",
			"Python syntax validation for finance modules",
			"pass",
			"all_targets_compile",
		)

	pass_count = sum(1 for c in checks if c["status"] == "pass")
	warn_count = sum(1 for c in checks if c["status"] == "warn")
	fail_count = sum(1 for c in checks if c["status"] == "fail")
	exit_code = determine_exit_code(pass_count, warn_count, fail_count, strict)

	report = {
		"script": "scripts/finance/check_finance_runtime.py",
		"generated_at_utc": now_utc_iso(),
		"strict": strict,
		"workspace_root": str(root),
		"checks": checks,
		"summary": {
			"pass": pass_count,
			"warn": warn_count,
			"fail": fail_count,
			"exit_code": exit_code,
			"exit_label": EXIT_LABELS[exit_code],
		},
	}
	return report


def main() -> int:
	parser = argparse.ArgumentParser(description="Check finance runtime evidence and output JSON report.")
	parser.add_argument("--strict", action="store_true", help="Treat warnings as failures.")
	parser.add_argument("--out", required=True, help="Path to JSON output report.")
	args = parser.parse_args()

	try:
		root = Path(__file__).resolve().parents[2]
		report = build_report(root=root, strict=args.strict)
		out_path = Path(args.out)
		out_path.parent.mkdir(parents=True, exist_ok=True)
		out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

		summary = report["summary"]
		print(
			f"[check_finance_runtime] pass={summary['pass']} warn={summary['warn']} "
			f"fail={summary['fail']} exit_code={summary['exit_code']}"
		)
		return int(summary["exit_code"])
	except Exception as exc:  # pragma: no cover - defensive wrapper
		print(f"[check_finance_runtime] runtime_error: {exc}", file=sys.stderr)
		return EXIT_ERROR


if __name__ == "__main__":
	sys.exit(main())
