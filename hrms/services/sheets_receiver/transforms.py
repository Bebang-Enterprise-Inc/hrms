"""
Sheet-specific transformation helpers for Sheets Receiver.

Some operational Google Sheets are matrix reports instead of clean row-based tables.
These helpers normalize those reports into row payloads the Frappe sync endpoints can
consume reliably.
"""

from __future__ import annotations

from typing import Any

INVENTORY_SUMMARY_MATRIX_TRANSFORMER = "inventory_summary_matrix"
AR_AGING_TABLE_TRANSFORMER = "ar_aging_table"

INVENTORY_SUMMARY_WAREHOUSE_MAP = {
	"3MD": "3MD Logistics – Camangyanan",
	"JENTEC": "Jentec Storage Inc.",
	"RCS": "Royal Cold Storage – Taytay (RCS)",
	"PINNACLE": "Pinnacle Cold Storage Solutions",
	"SHAW": "Shaw BLVD - BKI",
}

_INVENTORY_SECTION_MARKERS = {"DRY", "COLD", "FROZEN", "CHILLED"}


def transform_sheet_rows(transformer_name: str, raw_rows: list[list[Any]]) -> list[dict[str, Any]]:
	"""Transform raw sheet rows using a named transformer."""
	if transformer_name == INVENTORY_SUMMARY_MATRIX_TRANSFORMER:
		return _transform_inventory_summary_matrix(raw_rows)
	if transformer_name == AR_AGING_TABLE_TRANSFORMER:
		return _transform_ar_aging_table(raw_rows)
	raise ValueError(f"Unknown sheet data transformer: {transformer_name}")


def _transform_inventory_summary_matrix(raw_rows: list[list[Any]]) -> list[dict[str, Any]]:
	"""
	Convert Ian's `SUMMARY 2026` matrix into row-wise inventory records.

	The source sheet has:
	- title/meta row
	- warehouse heading row
	- sub-header row
	- optional section marker rows like `DRY` / `COLD`
	- item rows with warehouse quantities spread across multiple columns
	"""
	if len(raw_rows) < 4:
		return []

	warehouse_columns = _discover_inventory_summary_warehouse_columns(raw_rows[1])
	section_name = ""
	transformed: list[dict[str, Any]] = []

	for source_row_number, row in enumerate(raw_rows[3:], start=4):
		category = _cell(row, 0)
		item_description = _cell(row, 1)
		item_code = _cell(row, 2)
		uom = _cell(row, 3)

		if not item_code:
			section_token = (item_description or category).strip().upper()
			if section_token in _INVENTORY_SECTION_MARKERS:
				section_name = section_token
			continue

		for warehouse_code, column_index in warehouse_columns.items():
			transformed.append(
				{
					"inventory_key": f"{warehouse_code}::{item_code}",
					"item_code": item_code,
					"item_description": item_description,
					"category": category or section_name,
					"uom": uom,
					"warehouse_source_code": warehouse_code,
					"warehouse": INVENTORY_SUMMARY_WAREHOUSE_MAP[warehouse_code],
					"qty": _coerce_qty(_cell(row, column_index)),
					"source_row_number": source_row_number,
				}
			)

	return transformed


def _discover_inventory_summary_warehouse_columns(header_row: list[Any]) -> dict[str, int]:
	"""Locate the warehouse quantity columns from the matrix header row."""
	columns: dict[str, int] = {}
	for index, value in enumerate(header_row):
		label = _normalize_token(value)
		if label in INVENTORY_SUMMARY_WAREHOUSE_MAP:
			columns[label] = index

	missing = [code for code in INVENTORY_SUMMARY_WAREHOUSE_MAP if code not in columns]
	if missing:
		raise ValueError(
			"Inventory summary matrix is missing expected warehouse columns: " + ", ".join(sorted(missing))
		)

	return columns


def _cell(row: list[Any], index: int) -> str:
	"""Return a string cell value with whitespace normalized."""
	if index >= len(row):
		return ""
	value = row[index]
	if value is None:
		return ""
	return str(value).strip()


def _coerce_qty(value: str) -> float:
	"""Normalize sheet quantity cells into float values with blanks treated as zero."""
	token = (value or "").strip()
	if not token or token == "-":
		return 0.0

	try:
		return float(token.replace(",", ""))
	except ValueError:
		return 0.0


def _normalize_token(value: Any) -> str:
	"""Normalize a header token for exact warehouse-code matching."""
	return str(value or "").strip().upper()


def _transform_ar_aging_table(raw_rows: list[list[Any]]) -> list[dict[str, Any]]:
	"""
	Convert the live AR matrix into stable receivables rows.

	The source sheet is a summary table, not an invoice ledger. We normalize it so
	the sync layer can recognize and skip it cleanly instead of failing every row.
	"""
	header_row_index = _find_ar_aging_header_row(raw_rows)
	if header_row_index is None:
		raise ValueError("AR aging sheet is missing the expected receivables header row")

	transformed: list[dict[str, Any]] = []
	for source_row_number, row in enumerate(raw_rows[header_row_index + 1 :], start=header_row_index + 2):
		if _row_is_blank(row):
			continue

		billed_by = _cell(row, 0)
		date_billed = _cell(row, 1)
		store = _cell(row, 2)
		type_billings = _cell(row, 3)
		particulars = _cell(row, 4)
		period = _cell(row, 5)
		billed_amount = _coerce_qty(_cell(row, 6))
		amount_paid = _coerce_qty(_cell(row, 7))
		net_receivables = _coerce_qty(_cell(row, 8))
		status = _cell(row, 9)
		overdue = _cell(row, 10)
		aging_days = _coerce_int(_cell(row, 11))
		remarks = _cell(row, 12)
		bucket_0_30 = _coerce_qty(_cell(row, 13))
		bucket_31_60 = _coerce_qty(_cell(row, 14))
		bucket_61_90 = _coerce_qty(_cell(row, 15))
		bucket_91_120 = _coerce_qty(_cell(row, 16))
		bucket_over_120 = _coerce_qty(_cell(row, 17))

		if not any([billed_by, date_billed, store, type_billings, particulars, billed_amount, net_receivables]):
			continue

		transformed.append(
			{
				"ar_entry_key": "::".join(
					filter(
						None,
						[
							date_billed,
							store,
							type_billings,
							particulars,
							str(billed_amount or ""),
						],
					)
				)
				or f"__ar_row_{source_row_number}",
				"billed_by": billed_by,
				"date_billed": date_billed,
				"store": store,
				"type_billings": type_billings,
				"particulars": particulars,
				"period": period,
				"billed_amount": billed_amount,
				"amount_paid": amount_paid,
				"net_receivables": net_receivables,
				"status": status,
				"overdue": overdue,
				"aging_days": aging_days,
				"remarks": remarks,
				"bucket_0_30": bucket_0_30,
				"bucket_31_60": bucket_31_60,
				"bucket_61_90": bucket_61_90,
				"bucket_91_120": bucket_91_120,
				"bucket_over_120": bucket_over_120,
				"source_row_number": source_row_number,
			}
		)

	return transformed


def _find_ar_aging_header_row(raw_rows: list[list[Any]]) -> int | None:
	"""Locate the receivables header row in the AR matrix."""
	for index, row in enumerate(raw_rows):
		tokens = {_normalize_token(value) for value in row if _normalize_token(value)}
		if "DATE BILLED" in tokens and "NET RECEIVABLES" in tokens:
			return index
	return None


def _row_is_blank(row: list[Any]) -> bool:
	"""Return True when a raw sheet row contains no meaningful values."""
	return not any(str(value or "").strip() for value in row)


def _coerce_int(value: str) -> int:
	"""Normalize integer-like cells with blanks treated as zero."""
	token = (value or "").strip()
	if not token or token == "-":
		return 0

	try:
		return int(float(token.replace(",", "")))
	except ValueError:
		return 0
