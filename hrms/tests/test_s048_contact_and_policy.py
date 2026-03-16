import importlib
import sys
import types

from hrms.api.contact_validation import (
	normalize_ph_mobile_draft_value,
	validate_email_address,
	validate_ph_mobile_number,
)
from hrms.api.profile_policy import (
	classify_employee_policy,
	is_reports_to_candidate,
	matches_reports_to_query,
	resolve_reports_to_display_name,
)


def test_contact_validation_normalizes_ph_numbers_and_rejects_bad_prefixes():
	assert normalize_ph_mobile_draft_value("+639171234567") == "09171234567"
	assert normalize_ph_mobile_draft_value("9171234567") == "09171234567"

	assert validate_ph_mobile_number("09171234567")["valid"] is True
	invalid = validate_ph_mobile_number("09011234567")
	assert invalid["valid"] is False
	assert invalid["error"] == "Enter a valid Philippine mobile prefix."


def test_contact_validation_enforces_real_email_shape():
	assert validate_email_address("sam@bebang.ph") == {
		"normalized": "sam@bebang.ph",
		"valid": True,
	}
	invalid = validate_email_address("sambebang.ph")
	assert invalid["valid"] is False
	assert invalid["error"] == "Enter a valid email address like name@example.com."


def test_profile_policy_handles_exec_store_and_commissary_cohorts():
	executive = classify_employee_policy(
		{
			"branch": "Brittany Office",
			"department": "Executive",
			"designation": "Chief Executive Officer",
		}
	)
	assert executive["cohort"] == "office_supervisor_manager"
	assert executive["has_office_email_fields"] is True
	assert executive["has_supervisor_phone_fields"] is True
	assert executive["has_uniform_size"] is False
	assert executive["should_collect_reports_to"] is False

	store = classify_employee_policy(
		{
			"branch": "SM North",
			"department": "Operations",
			"designation": "Store Crew",
		}
	)
	assert store["cohort"] == "store_employee"
	assert store["uses_store_contact_policy"] is True
	assert store["has_uniform_size"] is True

	commissary = classify_employee_policy(
		{
			"branch": "Commissary",
			"department": "Commissary",
			"designation": "Production Team Leader",
		}
	)
	assert commissary["is_commissary_production"] is True
	assert commissary["has_uniform_size"] is True


def test_reports_to_candidates_only_include_leadership_roles():
	assert (
		is_reports_to_candidate(
			{
				"designation": "HR Manager",
				"department": "HR",
			}
		)
		is True
	)
	assert (
		is_reports_to_candidate(
			{
				"designation": "Store Crew",
				"department": "Operations",
			}
		)
		is False
	)


def test_reports_to_query_matches_linked_user_full_name():
	employee_row = {
		"name": "HR-EMP-00020",
		"employee_name": "Sam Admin",
		"first_name": "Sam",
		"last_name": "Admin",
		"designation": "Hr Manager",
		"department": "Operations - BEI",
		"branch": "ARANETA GATEWAY",
		"user_id": "sam@bebang.ph",
	}
	user_row = {
		"name": "sam@bebang.ph",
		"full_name": "Sam Karazi",
		"first_name": "Sam",
		"last_name": "Karazi",
	}

	assert matches_reports_to_query(employee_row, user_row, "Karazi") is True
	assert matches_reports_to_query(employee_row, user_row, "sam@bebang.ph") is True
	assert matches_reports_to_query(employee_row, user_row, "Crew") is False


def test_reports_to_display_name_prefers_user_full_name_for_admin_aliases():
	assert resolve_reports_to_display_name("Sam Admin", "Sam Karazi") == "Sam Karazi"
	assert resolve_reports_to_display_name("CARINGAL, RONALD H.", "Ronald Caringal") == "CARINGAL, RONALD H."


def test_enrichment_employee_row_fetches_requested_snapshot_fields(monkeypatch):
	import frappe.utils

	captured = {}
	utils_data = types.ModuleType("frappe.utils.data")
	utils_data.add_to_date = lambda *args, **kwargs: None

	def fake_get_value(doctype, name, fields, as_dict=False):
		captured["doctype"] = doctype
		captured["name"] = name
		captured["fields"] = list(fields)
		captured["as_dict"] = as_dict
		return {
			"name": name,
			"employee_name": "Test Crew",
			"branch": "TEST-STORE-BGC",
			"department": "Operations",
			"designation": "Store Staff",
			"custom_nickname": "Crew Nick",
			"current_address": "123 Test Street",
			"reports_to": "TEST-AREA-001",
		}

	monkeypatch.setattr(frappe.utils, "today", lambda: "2026-03-16", raising=False)
	monkeypatch.setattr("frappe.db.get_value", fake_get_value)
	monkeypatch.setitem(sys.modules, "frappe.utils.data", utils_data)
	onboarding = importlib.import_module("hrms.api.onboarding")

	row = onboarding._get_enrichment_employee_row(
		"TEST-CREW-001",
		["custom_nickname", "current_address", "reports_to"],
	)

	assert captured["doctype"] == "Employee"
	assert captured["name"] == "TEST-CREW-001"
	assert captured["as_dict"] is True
	assert set(captured["fields"]) == {
		"name",
		"employee_name",
		"branch",
		"department",
		"designation",
		"custom_nickname",
		"current_address",
		"reports_to",
	}
	assert row["custom_nickname"] == "Crew Nick"
	assert row["current_address"] == "123 Test Street"
	assert row["reports_to"] == "TEST-AREA-001"
