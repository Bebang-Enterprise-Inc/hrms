#!/usr/bin/env python3
"""S231: validate the new test modules import cleanly on production.

Production has `allow_tests=false` (correct security posture) so we can't
actually run unittest on the live site. The next-best validation is
confirming the modules import without error and contain the expected
test methods.

Output: output/s231/verification/test_module_imports.json
"""

from __future__ import annotations

import json
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from s231_ssm_helper import (  # noqa: E402
	PAYLOAD_PREAMBLE,
	decode_output,
	run_in_container,
)

OUT = REPO_ROOT / "output" / "s231" / "verification" / "test_module_imports.json"

CHECK_SCRIPT = (
	PAYLOAD_PREAMBLE
	+ """
import importlib
from unittest import TestCase

modules = [
    "hrms.tests.test_s231_atomicity",
    "hrms.tests.test_s231_pricing_coupling",
    "hrms.tests.test_s231_markup_coupling",
]

result = {}
for mod_name in modules:
    try:
        m = importlib.import_module(mod_name)
        test_methods = []
        test_classes = []
        for attr_name in dir(m):
            attr = getattr(m, attr_name)
            if isinstance(attr, type) and issubclass(attr, TestCase) and attr is not TestCase:
                test_classes.append(attr_name)
                methods = [n for n in dir(attr) if n.startswith("test_")]
                for method_name in methods:
                    test_methods.append(f"{attr_name}.{method_name}")
        result[mod_name] = {
            "imported": True,
            "test_class_count": len(test_classes),
            "test_classes": test_classes,
            "test_method_count": len(test_methods),
            "test_methods": test_methods,
        }
    except Exception as e:
        result[mod_name] = {"imported": False, "error": str(e), "error_type": type(e).__name__}

# Also count expected total
expected = {"test_s231_atomicity": 5, "test_s231_pricing_coupling": 12, "test_s231_markup_coupling": 6}
result["_summary"] = {
    "expected_total": sum(expected.values()),
    "actual_total": sum(
        v.get("test_method_count", 0) for k, v in result.items() if k != "_summary"
    ),
    "all_modules_imported": all(
        v.get("imported", False) for k, v in result.items() if k != "_summary"
    ),
}

_s231_emit(result)
frappe.destroy()
"""
)


def main() -> int:
	OUT.parent.mkdir(parents=True, exist_ok=True)
	stdout = run_in_container(CHECK_SCRIPT, timeout=120)
	data = decode_output(stdout)
	OUT.write_text(json.dumps(data, indent=2, default=str))
	print(f"Wrote {OUT}")
	summary = data.get("_summary", {})
	print(
		f"Modules imported: {summary.get('all_modules_imported')} | "
		f"tests found: {summary.get('actual_total')}/{summary.get('expected_total')}"
	)
	for mod, info in data.items():
		if mod == "_summary":
			continue
		status = "OK" if info.get("imported") else "FAIL"
		print(f"  {status} {mod}: {info.get('test_method_count', 0)} tests | classes={info.get('test_classes', [])}")
		if not info.get("imported"):
			print(f"    error: {info.get('error')}")
	return 0 if summary.get("all_modules_imported") else 1


if __name__ == "__main__":
	sys.exit(main())
