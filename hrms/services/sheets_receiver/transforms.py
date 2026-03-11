"""
Sheet-specific transformation helpers for Sheets Receiver.

Some operational Google Sheets are matrix reports instead of clean row-based tables.
These helpers normalize those reports into row payloads the Frappe sync endpoints can
consume reliably.
"""

from __future__ import annotations

from typing import Any

INVENTORY_SUMMARY_MATRIX_TRANSFORMER = "inventory_summary_matrix"

INVENTORY_SUMMARY_WAREHOUSE_MAP = {
	"3MD": "3MD Logistics - Camangyanan - BEI",
	"JENTEC": "Jentec Storage Inc. - BEI",
	"RCS": "Royal Cold Storage - Taytay - BEI",
	"PINNACLE": "Pinnacle Cold Storage - BEI",
	"SHAW": "Shaw BLVD - BEI",
}

_INVENTORY_SECTION_MARKERS = {"DRY", "COLD", "FROZEN", "CHILLED"}


def transform_sheet_rows(transformer_name: str, raw_rows: list[list[Any]]) -> list[dict[str, Any]]:
	"""Transform raw sheet rows using a named transformer."""
	if transformer_name == INVENTORY_SUMMARY_MATRIX_TRANSFORMER:
		return _transform_inventory_summary_matrix(raw_rows)
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
