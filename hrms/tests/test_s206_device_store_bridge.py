"""S206 Phase 1 — device_store_bridge unit tests."""

import unittest
from unittest.mock import patch

from hrms.utils import device_store_bridge
from hrms.utils.device_mapping import DEVICE_TO_STORE
from hrms.utils.device_store_bridge import (
	DEVICE_STORE_BRIDGE,
	UnknownDeviceCompany,
	resolve_device_company,
)


class DeviceStoreBridgeTests(unittest.TestCase):
	def test_every_device_has_a_bridge_entry(self):
		"""Every DEVICE_TO_STORE store value must be in DEVICE_STORE_BRIDGE."""
		missing = []
		for sn, store in DEVICE_TO_STORE.items():
			if store not in DEVICE_STORE_BRIDGE:
				missing.append(f"{sn} -> {store}")
		self.assertEqual(
			missing,
			[],
			f"Devices without bridge entries: {missing}",
		)

	def test_ho_device_routes_to_bei_parent(self):
		"""Brittany Office (BRITTANY OFFICE) -> BEI parent."""
		mock_idx = {}  # stores only; HO has no store entry
		from hrms.utils import company_lookup

		with patch.object(company_lookup, "_load_store_company_index", return_value=mock_idx):
			company_lookup.clear_cache()
			# UDP3251600245 = BRITTANY OFFICE per DEVICE_TO_STORE
			result = resolve_device_company("UDP3251600245")
			self.assertEqual(result, "BEBANG ENTERPRISE INC.")

	def test_capital_house_device_routes_to_bei_parent_via_bridge(self):
		"""BGC CAPITAL HOUSE device -> CAPITAL HOUSE branch -> BEI parent."""
		from hrms.utils import company_lookup

		with patch.object(company_lookup, "_load_store_company_index", return_value={}):
			company_lookup.clear_cache()
			# UDP3235200625 = BGC CAPITAL HOUSE
			result = resolve_device_company("UDP3235200625")
			self.assertEqual(result, "BEBANG ENTERPRISE INC.")

	def test_store_device_routes_to_store_company(self):
		"""SM MEGAMALL device -> store prefix SM MEGAMALL -> full Company."""
		from hrms.utils import company_lookup

		mock_idx = {
			"SM MEGAMALL": "SM MEGAMALL - BEBANG ENTERPRISE INC.",
		}
		with patch.object(company_lookup, "_load_store_company_index", return_value=mock_idx):
			company_lookup.clear_cache()
			# UDP3235200631 = SM MEGAMALL
			result = resolve_device_company("UDP3235200631")
			self.assertEqual(result, "SM MEGAMALL - BEBANG ENTERPRISE INC.")

	def test_name_mismatch_bridge_works(self):
		"""LCT -> LUCKY CHINATOWN via bridge."""
		from hrms.utils import company_lookup

		mock_idx = {
			"LUCKY CHINATOWN": "LUCKY CHINATOWN - BEBANG LCT INC.",
		}
		with patch.object(company_lookup, "_load_store_company_index", return_value=mock_idx):
			company_lookup.clear_cache()
			# UDP3235200526 = LCT
			result = resolve_device_company("UDP3235200526")
			self.assertEqual(result, "LUCKY CHINATOWN - BEBANG LCT INC.")

	def test_shaw_commissary_dept_commissary_routes_to_bki(self):
		from hrms.utils import company_lookup

		with patch.object(company_lookup, "_load_store_company_index", return_value={}):
			company_lookup.clear_cache()
			# UDP3235200629 = SHAW COMMISSARY
			result = resolve_device_company("UDP3235200629", department="Commissary")
			self.assertEqual(result, "BEBANG KITCHEN INC.")

	def test_shaw_commissary_dept_scm_routes_to_bei(self):
		from hrms.utils import company_lookup

		with patch.object(company_lookup, "_load_store_company_index", return_value={}):
			company_lookup.clear_cache()
			result = resolve_device_company("UDP3235200629", department="SCM")
			self.assertEqual(result, "BEBANG ENTERPRISE INC.")

	def test_unknown_device_raises(self):
		with self.assertRaises(UnknownDeviceCompany):
			resolve_device_company("NOT_A_REAL_SN")

	def test_empty_device_raises(self):
		with self.assertRaises(UnknownDeviceCompany):
			resolve_device_company("")


if __name__ == "__main__":
	unittest.main()
