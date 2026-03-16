from __future__ import annotations

from typing import Any

OFFICE_LIKE_BRANCHES = {"BRITTANY OFFICE", "CAPITAL HOUSE"}
SUPERVISOR_TITLE_KEYWORDS = (
	"SUPERVISOR",
	"MANAGER",
	"HEAD",
	"OFFICER",
	"CHIEF",
	"DIRECTOR",
	"LEAD",
	"ARCHITECT",
	"OIC",
)
EXECUTIVE_TITLE_KEYWORDS = (
	"CEO",
	"PRESIDENT",
	"FOUNDER",
	"OWNER",
	"CHAIRMAN",
	"VICE PRESIDENT",
	"VP",
	"AVP",
	"CHIEF EXECUTIVE",
)
OFFICE_LIKE_DEPARTMENT_KEYWORDS = (
	"EXECUTIVE",
	"HR",
	"FINANCE",
	"ACCOUNT",
	"PROCUREMENT",
	"PROJECT",
	"IT",
	"SUPPLY CHAIN",
)
OPERATIONS_SUPPORT_KEYWORDS = ("COMMISSARY", "WAREHOUSE", "LOGISTICS", "SUPPLY CHAIN")
COMMISSARY_PRODUCTION_KEYWORDS = (
	"PRODUCTION",
	"COMMISSARY CREW",
	"COMMISSARY SUPERVISOR",
	"TEAM LEADER",
	"TEAM MEMBER",
)


def normalize_text(value: Any) -> str:
	return str(value or "").strip().upper()


def includes_any(text: str, keywords: tuple[str, ...]) -> bool:
	return any(keyword in text for keyword in keywords)


def classify_employee_policy(employee_row: dict[str, Any]) -> dict[str, Any]:
	branch = normalize_text(employee_row.get("branch"))
	department = normalize_text(employee_row.get("department"))
	designation = normalize_text(employee_row.get("designation"))

	is_executive_leadership = includes_any(designation, EXECUTIVE_TITLE_KEYWORDS) or "EXECUTIVE" in department
	is_area_supervisor = "AREA SUPERVISOR" in designation
	is_store_oic = (
		"STORE OIC" in designation or "STORE SUPERVISOR" in designation or designation.endswith(" OIC")
	)
	is_office_like = (
		branch in OFFICE_LIKE_BRANCHES
		or includes_any(department, OFFICE_LIKE_DEPARTMENT_KEYWORDS)
		or is_executive_leadership
	)
	is_supervisor_grade = is_executive_leadership or includes_any(designation, SUPERVISOR_TITLE_KEYWORDS)
	is_operations_support = (
		includes_any(branch, OPERATIONS_SUPPORT_KEYWORDS)
		or includes_any(department, OPERATIONS_SUPPORT_KEYWORDS)
		or includes_any(designation, OPERATIONS_SUPPORT_KEYWORDS)
	)
	is_commissary_production = ("COMMISSARY" in branch or "COMMISSARY" in department) and includes_any(
		designation, COMMISSARY_PRODUCTION_KEYWORDS
	)

	if is_area_supervisor:
		cohort = "area_supervisor"
	elif is_executive_leadership or (is_office_like and is_supervisor_grade):
		cohort = "office_supervisor_manager"
	elif is_operations_support:
		cohort = "operations_support"
	elif is_store_oic:
		cohort = "store_oic"
	elif is_office_like:
		cohort = "office_staff"
	else:
		cohort = "store_employee"

	return {
		"cohort": cohort,
		"is_office_like": is_office_like,
		"is_supervisor_grade": is_supervisor_grade,
		"is_area_supervisor": is_area_supervisor,
		"is_executive_leadership": is_executive_leadership,
		"is_commissary_production": is_commissary_production,
		"uses_store_contact_policy": cohort in {"store_employee", "store_oic"},
		"has_office_email_fields": (is_office_like and not is_operations_support)
		or is_area_supervisor
		or is_executive_leadership,
		"has_supervisor_phone_fields": is_executive_leadership
		or (is_office_like and is_supervisor_grade)
		or is_area_supervisor,
		"has_uniform_size": cohort in {"store_employee", "store_oic"} or is_commissary_production,
		"should_collect_reports_to": not is_executive_leadership,
	}


def is_reports_to_candidate(employee_row: dict[str, Any]) -> bool:
	designation = normalize_text(employee_row.get("designation"))
	department = normalize_text(employee_row.get("department"))

	if includes_any(designation, SUPERVISOR_TITLE_KEYWORDS):
		return True
	if includes_any(designation, EXECUTIVE_TITLE_KEYWORDS):
		return True
	if "EXECUTIVE" in department:
		return True
	return False
