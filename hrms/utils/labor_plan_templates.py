from __future__ import annotations

from copy import deepcopy
from datetime import date
from typing import Any

DAY_NAMES = [
	"Monday",
	"Tuesday",
	"Wednesday",
	"Thursday",
	"Friday",
	"Saturday",
	"Sunday",
]

SURFACE_STORE = "store_schedule"
SURFACE_COMMISSARY = "commissary_schedule"


def _template(
	template_key: str,
	label: str,
	description: str,
	surface: str,
	patterns: dict[str, list[list[str]]],
	highlights: list[str] | None = None,
):
	return {
		"template_key": template_key,
		"label": label,
		"description": description,
		"surface": surface,
		"patterns": patterns,
		"highlights": highlights or [],
		"role_buckets": sorted(patterns.keys()),
	}


STORE_TEMPLATES = [
	_template(
		"retail_balanced",
		"Retail Balanced",
		"Balanced five-day coverage with lead opening ownership and rotating cashier or crew support.",
		SURFACE_STORE,
		{
			"lead": [["Opening", "Opening", "Opening", "Opening", "Opening", "Off", "Off"]],
			"cashier": [
				["Opening", "Mid", "Off", "Closing", "Closing", "Off", "Off"],
				["Mid", "Closing", "Closing", "Off", "Opening", "Off", "Off"],
			],
			"team": [
				["Opening", "Opening", "Off", "Mid", "Mid", "Off", "Closing"],
				["Mid", "Closing", "Closing", "Off", "Opening", "Off", "Off"],
				["Closing", "Off", "Opening", "Opening", "Mid", "Closing", "Off"],
				["Off", "Mid", "Mid", "Closing", "Off", "Opening", "Opening"],
			],
		},
		["5-day rotation", "weekday lead opening"],
	),
	_template(
		"retail_weekend_push",
		"Retail Weekend Push",
		"Heavier Friday-to-Sunday coverage for stores that spike on weekends.",
		SURFACE_STORE,
		{
			"lead": [["Opening", "Opening", "Mid", "Opening", "Opening", "Opening", "Off"]],
			"cashier": [
				["Mid", "Off", "Closing", "Closing", "Opening", "Opening", "Off"],
				["Opening", "Mid", "Off", "Closing", "Mid", "Closing", "Off"],
			],
			"team": [
				["Off", "Opening", "Mid", "Mid", "Closing", "Closing", "Off"],
				["Opening", "Mid", "Off", "Opening", "Mid", "Closing", "Off"],
				["Mid", "Closing", "Opening", "Off", "Opening", "Mid", "Off"],
				["Closing", "Off", "Opening", "Mid", "Off", "Opening", "Closing"],
			],
		},
		["weekend coverage", "weekday-light"],
	),
]

COMMISSARY_TEMPLATES = [
	_template(
		"commissary_four_wave",
		"Commissary Four-Wave",
		"Round-robin Dawn, Morning, Afternoon, and Night coverage with overnight-safe rotation.",
		SURFACE_COMMISSARY,
		{
			"lead": [["Commissary - Morning", "Commissary - Morning", "Off", "Commissary - Afternoon", "Commissary - Morning", "Off", "Off"]],
			"team": [
				["Commissary - Dawn", "Commissary - Dawn", "Off", "Commissary - Morning", "Commissary - Morning", "Off", "Commissary - Afternoon"],
				["Commissary - Morning", "Commissary - Afternoon", "Commissary - Afternoon", "Off", "Commissary - Dawn", "Off", "Off"],
				["Commissary - Afternoon", "Commissary - Night", "Off", "Commissary - Dawn", "Commissary - Dawn", "Off", "Commissary - Morning"],
				["Commissary - Night", "Off", "Commissary - Morning", "Commissary - Morning", "Off", "Commissary - Afternoon", "Commissary - Afternoon"],
			],
		},
		["overnight-safe", "four-wave"],
	),
	_template(
		"commissary_weekend_packout",
		"Commissary Weekend Packout",
		"Extra late-week and weekend production coverage for high-volume dispatch cycles.",
		SURFACE_COMMISSARY,
		{
			"lead": [["Commissary - Dawn", "Commissary - Morning", "Off", "Commissary - Morning", "Commissary - Afternoon", "Off", "Off"]],
			"team": [
				["Commissary - Dawn", "Off", "Commissary - Morning", "Commissary - Morning", "Commissary - Afternoon", "Commissary - Afternoon", "Off"],
				["Commissary - Morning", "Commissary - Afternoon", "Off", "Commissary - Dawn", "Commissary - Night", "Off", "Commissary - Morning"],
				["Commissary - Afternoon", "Commissary - Night", "Commissary - Night", "Off", "Commissary - Dawn", "Commissary - Dawn", "Off"],
				["Commissary - Night", "Commissary - Dawn", "Off", "Commissary - Afternoon", "Off", "Commissary - Morning", "Commissary - Afternoon"],
			],
		},
		["late-week support", "overnight-safe"],
	),
]


def get_template_definitions(surface: str) -> list[dict[str, Any]]:
	if surface == SURFACE_COMMISSARY:
		return deepcopy(COMMISSARY_TEMPLATES)
	return deepcopy(STORE_TEMPLATES)


def get_template_metadata(surface: str) -> list[dict[str, Any]]:
	return [
		{
			"template_key": template["template_key"],
			"label": template["label"],
			"description": template["description"],
			"surface": template["surface"],
			"role_buckets": list(template["role_buckets"]),
			"highlights": list(template["highlights"]),
		}
		for template in get_template_definitions(surface)
	]


def classify_role_bucket(designation: str | None, surface: str) -> str:
	label = str(designation or "").strip().upper()
	if "SUPERVISOR" in label or "OIC" in label:
		return "lead"
	if surface == SURFACE_STORE and "CASHIER" in label:
		return "cashier"
	return "team"


def _warning(code: str, level: str, message: str, **extra: Any) -> dict[str, Any]:
	row = {"code": code, "level": level, "message": message}
	row.update({key: value for key, value in extra.items() if value is not None})
	return row


def _rotation_week_offset(week_start: str | None, cycle_length: int) -> int:
	if not week_start or cycle_length <= 0:
		return 0
	try:
		start = date.fromisoformat(str(week_start))
	except ValueError:
		return 0
	return (start.toordinal() // 7) % cycle_length


def apply_template_to_employees(
	template_key: str,
	surface: str,
	employees: list[dict[str, Any]],
	shift_options: list[dict[str, Any]],
	week_start: str | None = None,
) -> dict[str, Any]:
	templates = {template["template_key"]: template for template in get_template_definitions(surface)}
	template = templates.get(template_key)
	if not template:
		raise KeyError(template_key)

	shift_map = {str(option.get("shift_type_name") or ""): option for option in shift_options}
	warnings: list[dict[str, Any]] = []
	grouped: dict[str, list[dict[str, Any]]] = {}
	for employee in employees:
		bucket = classify_role_bucket(employee.get("designation"), surface)
		grouped.setdefault(bucket, []).append(employee)

	shifts: list[dict[str, Any]] = []
	unassigned = 0
	for bucket, bucket_employees in grouped.items():
		patterns = (
			template["patterns"].get(bucket)
			or template["patterns"].get("team")
			or template["patterns"].get("all")
			or []
		)
		if not patterns:
			for employee in bucket_employees:
				unassigned += 1
				warnings.append(
					_warning(
						"no_template_pattern",
						"warning",
						f"No template pattern exists for {employee.get('employee_name') or employee.get('name')}.",
						employee=employee.get("name"),
						role_bucket=bucket,
					)
				)
			continue

		rotation_offset = _rotation_week_offset(week_start, len(patterns)) if surface == SURFACE_COMMISSARY else 0

		for employee_index, employee in enumerate(bucket_employees):
			pattern_index = (employee_index + rotation_offset) % len(patterns)
			slot = patterns[pattern_index]
			rotation_group = None
			if surface == SURFACE_COMMISSARY and bucket == "team":
				rotation_group = f"Team {chr(65 + (employee_index % len(patterns)))}"
			for day_name, shift_name in zip(DAY_NAMES, slot, strict=False):
				option = shift_map.get(shift_name)
				if not option:
					warnings.append(
						_warning(
							"missing_shift_option",
							"error",
							f"Shift option {shift_name} is not configured for this location.",
							employee=employee.get("name"),
							day_of_week=day_name,
							shift_type_name=shift_name,
						)
					)
					continue
				shifts.append(
					{
						"employee": employee.get("name"),
						"employee_name": employee.get("employee_name"),
						"day_of_week": day_name,
						"shift_type_name": option.get("shift_type_name"),
						"shift_start": option.get("shift_start") or None,
						"shift_end": option.get("shift_end") or None,
						"is_off": bool(option.get("is_off")),
						"ends_next_day": bool(option.get("ends_next_day")),
						"hours": option.get("hours") or 0,
						"notes": f"Rotation group: {rotation_group}" if rotation_group else None,
						"rotation_group": rotation_group,
					}
				)

	if not employees:
		warnings.append(
			_warning(
				"empty_roster",
				"warning",
				"There are no active employees mapped to this location yet.",
			)
		)
	elif unassigned:
		warnings.append(
			_warning(
				"partial_assignment",
				"warning",
				f"{unassigned} employee(s) could not be assigned by this template.",
				employee_count=unassigned,
			)
		)

	return {
		"template": {
			"template_key": template["template_key"],
			"label": template["label"],
			"description": template["description"],
			"surface": template["surface"],
			"role_buckets": list(template["role_buckets"]),
			"highlights": list(template["highlights"]),
		},
		"shifts": shifts,
		"warnings": warnings,
	}
