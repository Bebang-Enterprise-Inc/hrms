from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _load_mapping_module():
	spec = importlib.util.spec_from_file_location(
		"sales_location_mapping_under_test",
		ROOT / "hrms" / "utils" / "sales_location_mapping.py",
	)
	module = importlib.util.module_from_spec(spec)
	assert spec and spec.loader
	spec.loader.exec_module(module)
	return module


def test_lookup_location_id_accepts_record_name_base_without_company_suffix():
	module = _load_mapping_module()

	assert module.lookup_location_id("Robisons Galleria South") == 2515
