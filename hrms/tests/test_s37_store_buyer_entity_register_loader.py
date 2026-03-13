import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class _FakeFrappe(types.ModuleType):
	def __getattr__(self, name):
		if name == "db":
			return self.local.db
		raise AttributeError(name)


def _install_fake_frappe() -> None:
	frappe = _FakeFrappe("frappe")
	frappe.local = types.SimpleNamespace(
		db=types.SimpleNamespace(
			has_column=lambda doctype, fieldname: True,
			get_value=lambda *args, **kwargs: None,
		)
	)
	sys.modules["frappe"] = frappe


_install_fake_frappe()

module_spec = importlib.util.spec_from_file_location(
	"supply_chain_contracts_under_test",
	ROOT / "utils" / "supply_chain_contracts.py",
)
supply_chain_contracts = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(supply_chain_contracts)


def _write_register(path: Path, store_name: str, buyer_entity_name: str) -> None:
	header = (
		"store_name,buyer_entity_name,buyer_entity_status,buyer_entity_source,billing_policy,"
		"billing_post_policy,store_type,store_type_status,store_allocation_required,"
		"markup_rule_mode,markup_rule_source,active_fulfillment_status,warehouse_docname,"
		"evidence_primary,evidence_secondary,notes"
	)
	row = (
		f"{store_name},{buyer_entity_name},confirmed_legal_entity,test-source,"
		f"BKI_TO_STORE_INTERCOMPANY,AUTO_POST_ALLOWED,JV,confirmed,0,CONFIG_BY_STORE_TYPE,"
		f"test-source,active,{store_name} - Bebang Enterprise Inc.,test-source,test-source,"
	)
	path.write_text(
		"\n".join([header, row]),
		encoding="utf-8",
	)


class StoreBuyerEntityRegisterLoaderTests(unittest.TestCase):
	def tearDown(self) -> None:
		supply_chain_contracts.load_store_buyer_entity_register.cache_clear()

	def test_loads_register_from_first_available_candidate_path(self) -> None:
		with tempfile.TemporaryDirectory() as temp_dir:
			register_path = Path(temp_dir) / "store_buyer_entity_register_2026-03-12.csv"
			_write_register(register_path, "Araneta Gateway", "Tungsten Capital Holdings Inc.")

			with patch.object(
				supply_chain_contracts,
				"_candidate_register_paths",
				return_value=(register_path,),
			):
				supply_chain_contracts.load_store_buyer_entity_register.cache_clear()
				rows = supply_chain_contracts.load_store_buyer_entity_register()

		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["buyer_entity_name"], "Tungsten Capital Holdings Inc.")
		self.assertEqual(rows[0]["_store_name_key"], "araneta gateway")

	def test_resolve_store_buyer_entity_matches_runtime_dispatch_lookup(self) -> None:
		with tempfile.TemporaryDirectory() as temp_dir:
			register_path = Path(temp_dir) / "store_buyer_entity_register_2026-03-12.csv"
			_write_register(register_path, "Araneta Gateway", "Tungsten Capital Holdings Inc.")

			with patch.object(
				supply_chain_contracts,
				"_candidate_register_paths",
				return_value=(register_path,),
			):
				supply_chain_contracts.load_store_buyer_entity_register.cache_clear()
				row = supply_chain_contracts.resolve_store_buyer_entity(
					warehouse_docname="Araneta Gateway - Bebang Enterprise Inc.",
					store_name="Araneta Gateway",
				)

		self.assertEqual(row["buyer_entity_name"], "Tungsten Capital Holdings Inc.")
		self.assertEqual(row["buyer_entity_status"], "confirmed_legal_entity")

	def test_resolve_markup_percent_prefers_finance_store_type_configuration(self) -> None:
		with patch.object(
			supply_chain_contracts.frappe.db,
			"get_value",
			return_value={"price_list_multiplier": 2.5, "store_type": "JV"},
		):
			markup = supply_chain_contracts.resolve_markup_percent(
				"JV",
				store_name="SM Manila",
				entity_row={"store_name": "SM Manila"},
			)

		self.assertEqual(markup, 0.025)

	def test_resolve_markup_percent_falls_back_to_store_type_defaults(self) -> None:
		with patch.object(supply_chain_contracts.frappe.db, "get_value", return_value=None):
			self.assertEqual(supply_chain_contracts.resolve_markup_percent("JV"), 0.025)
			self.assertEqual(supply_chain_contracts.resolve_markup_percent("Managed Franchise"), 0.08)


if __name__ == "__main__":
	unittest.main()
