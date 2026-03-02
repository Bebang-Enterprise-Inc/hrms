from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _declared_functions(path: Path) -> set[str]:
	source = path.read_text(encoding="utf-8")
	names: set[str] = set()
	for line in source.splitlines():
		line = line.strip()
		if line.startswith("def "):
			name = line.split("def ", 1)[1].split("(", 1)[0].strip()
			names.add(name)
	return names


def test_s18_finance_contract_methods_are_declared():
	finance_path = ROOT / "hrms" / "api" / "finance.py"
	methods = _declared_functions(finance_path)

	assert {
		"get_consolidated_summary",
		"get_finance_kpis",
		"get_store_pnl_summary",
		"generate_monthly_report",
	}.issubset(methods)


def test_s18_finance_module_is_registered_in_api_init():
	init_source = (ROOT / "hrms" / "api" / "__init__.py").read_text(encoding="utf-8")
	assert "import hrms.api.finance" in init_source
