from __future__ import annotations

import re
from typing import TypedDict

EMAIL_PATTERN = re.compile(r"^[^\s@]+@(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,63}$")

FOUR_DIGIT_MOBILE_PREFIXES = {
	"0813",
	"0817",
	"0895",
	"0896",
	"0897",
	"0898",
	"0900",
	"0904",
	"0905",
	"0906",
	"0907",
	"0908",
	"0909",
	"0910",
	"0911",
	"0912",
	"0913",
	"0914",
	"0915",
	"0916",
	"0917",
	"0918",
	"0919",
	"0920",
	"0921",
	"0922",
	"0923",
	"0924",
	"0925",
	"0926",
	"0927",
	"0928",
	"0929",
	"0930",
	"0931",
	"0932",
	"0933",
	"0934",
	"0935",
	"0936",
	"0937",
	"0938",
	"0939",
	"0940",
	"0941",
	"0942",
	"0943",
	"0944",
	"0945",
	"0946",
	"0947",
	"0948",
	"0949",
	"0950",
	"0951",
	"0952",
	"0953",
	"0954",
	"0955",
	"0956",
	"0957",
	"0958",
	"0959",
	"0960",
	"0961",
	"0962",
	"0963",
	"0964",
	"0965",
	"0966",
	"0967",
	"0968",
	"0969",
	"0970",
	"0971",
	"0972",
	"0973",
	"0974",
	"0975",
	"0976",
	"0977",
	"0978",
	"0979",
	"0980",
	"0981",
	"0982",
	"0983",
	"0984",
	"0985",
	"0986",
	"0987",
	"0988",
	"0989",
	"0990",
	"0991",
	"0992",
	"0993",
	"0994",
	"0995",
	"0996",
	"0997",
	"0998",
	"0999",
}

FIVE_DIGIT_MOBILE_PREFIXES = {"09253", "09255", "09256", "09257", "09258"}
PH_MOBILE_PREFIXES = FOUR_DIGIT_MOBILE_PREFIXES | FIVE_DIGIT_MOBILE_PREFIXES


class ValidationResult(TypedDict, total=False):
	normalized: str
	display: str
	e164: str
	valid: bool
	error: str


def _digits_only(value: str) -> str:
	return re.sub(r"\D", "", value or "")


def normalize_subscriber_digits(raw_value: str) -> str:
	trimmed = (raw_value or "").strip()
	prefixed = trimmed.startswith("+63")
	digits = _digits_only(trimmed)

	if prefixed and digits.startswith("63"):
		return digits[2:12]
	if digits.startswith("63") and len(digits) > 10:
		return digits[2:12]
	if digits.startswith("0"):
		return digits[1:11]
	return digits[:10]


def normalize_ph_mobile_draft_value(raw_value: str) -> str:
	subscriber = normalize_subscriber_digits(raw_value)
	return f"0{subscriber}" if subscriber else ""


def validate_email_address(raw_value: str) -> ValidationResult:
	normalized = (raw_value or "").strip()
	if not normalized:
		return {"normalized": "", "valid": False, "error": "Email is required."}
	if not EMAIL_PATTERN.match(normalized):
		return {
			"normalized": normalized,
			"valid": False,
			"error": "Enter a valid email address like name@example.com.",
		}
	return {"normalized": normalized, "valid": True}


def validate_ph_mobile_number(raw_value: str) -> ValidationResult:
	subscriber = normalize_subscriber_digits(raw_value)
	normalized = f"0{subscriber}" if subscriber else ""

	if not normalized:
		return {
			"normalized": "",
			"display": "",
			"e164": "",
			"valid": False,
			"error": "Mobile number is required.",
		}

	if not re.match(r"^0(?:8|9)\d{9}$", normalized):
		return {
			"normalized": normalized,
			"display": subscriber,
			"e164": f"+63{subscriber}" if subscriber else "",
			"valid": False,
			"error": "Enter an 11-digit Philippine mobile number.",
		}

	if normalized[:5] not in PH_MOBILE_PREFIXES and normalized[:4] not in PH_MOBILE_PREFIXES:
		return {
			"normalized": normalized,
			"display": subscriber,
			"e164": f"+63{subscriber}",
			"valid": False,
			"error": "Enter a valid Philippine mobile prefix.",
		}

	return {
		"normalized": normalized,
		"display": subscriber,
		"e164": f"+63{subscriber}",
		"valid": True,
	}
