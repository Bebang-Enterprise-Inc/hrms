from hrms.api.contact_validation import (
	normalize_ph_mobile_draft_value,
	validate_email_address,
	validate_ph_mobile_number,
)
from hrms.api.profile_policy import classify_employee_policy, is_reports_to_candidate


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
