import importlib.util
import pathlib
import sys
import types
import unittest


def _install_frappe_stubs():
	frappe = types.ModuleType("frappe")
	frappe.db = types.SimpleNamespace(get_value=lambda *args, **kwargs: None)
	frappe.throw = lambda msg, *args, **kwargs: (_ for _ in ()).throw(RuntimeError(msg))

	model_mod = types.ModuleType("frappe.model")
	document_mod = types.ModuleType("frappe.model.document")

	class Document:
		pass

	document_mod.Document = Document

	utils = types.ModuleType("frappe.utils")
	utils.now_datetime = lambda: "2026-03-10 12:00:00"

	sys.modules["frappe"] = frappe
	sys.modules["frappe.model"] = model_mod
	sys.modules["frappe.model.document"] = document_mod
	sys.modules["frappe.utils"] = utils


def _load_doctype_module():
	_install_frappe_stubs()
	file_path = (
		pathlib.Path(__file__).resolve().parents[1]
		/ "hr"
		/ "doctype"
		/ "bei_distribution_trip"
		/ "bei_distribution_trip.py"
	)
	spec = importlib.util.spec_from_file_location("distribution_trip_doctype_under_test", file_path)
	module = importlib.util.module_from_spec(spec)
	assert spec and spec.loader
	spec.loader.exec_module(module)
	return module


def _stop(status):
	return types.SimpleNamespace(status=status)


class TestDistributionTripStatus(unittest.TestCase):
	def test_all_exception_stops_mark_trip_partial(self):
		module = _load_doctype_module()
		doc = module.BEIDistributionTrip()
		doc.departure_time = "2026-03-10 11:45:00"
		doc.status = "In Transit"
		doc.stops = [_stop("Store Closed"), _stop("Refused")]

		doc.update_status()

		self.assertEqual(doc.status, "Partial")

	def test_exception_with_pending_stop_stays_in_transit(self):
		module = _load_doctype_module()
		doc = module.BEIDistributionTrip()
		doc.departure_time = "2026-03-10 11:45:00"
		doc.status = "In Transit"
		doc.stops = [_stop("Store Closed"), _stop("Pending")]

		doc.update_status()

		self.assertEqual(doc.status, "In Transit")


if __name__ == "__main__":
	unittest.main()
