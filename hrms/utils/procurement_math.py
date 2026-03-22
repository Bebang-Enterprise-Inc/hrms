from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from typing import Any

from frappe.utils import flt


def _accepted_qty(item: dict[str, Any]) -> float:
	if item.get("accepted_qty") is not None:
		return flt(item.get("accepted_qty"), 6)
	if item.get("received_qty") is not None:
		return flt(item.get("received_qty"), 6) - flt(item.get("rejected_qty"), 6)
	return flt(item.get("qty"), 6)


def _line_vat_rate(po_item: dict[str, Any]) -> float:
	explicit_rate = flt(po_item.get("vat_rate"), 6)
	if explicit_rate > 0:
		return explicit_rate

	base_qty = flt(po_item.get("qty"), 6)
	base_rate = flt(po_item.get("unit_cost") or po_item.get("rate"), 6)
	base_amount = base_qty * base_rate
	vat_amount = flt(po_item.get("vat_amount"), 6)

	if base_amount <= 0 or vat_amount <= 0:
		return 0

	return vat_amount / base_amount * 100


def _po_item_key(po_item: dict[str, Any]) -> tuple[str, float]:
	return (
		str(po_item.get("item_code") or ""),
		round(flt(po_item.get("unit_cost") or po_item.get("rate"), 6), 6),
	)


def _gr_item_key(gr_item: dict[str, Any]) -> tuple[str, float]:
	return (
		str(gr_item.get("item_code") or ""),
		round(flt(gr_item.get("unit_cost") or gr_item.get("rate"), 6), 6),
	)


def _build_po_index(
	po_items: Iterable[dict[str, Any]],
) -> tuple[dict[tuple[str, float], list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
	index: dict[tuple[str, float], list[dict[str, Any]]] = defaultdict(list)
	fallback_index: dict[str, list[dict[str, Any]]] = defaultdict(list)

	for po_item in po_items:
		index[_po_item_key(po_item)].append(po_item)
		fallback_index[str(po_item.get("item_code") or "")].append(po_item)

	return index, fallback_index


def _match_po_item(
	po_index: dict[tuple[str, float], list[dict[str, Any]]],
	fallback_index: dict[str, list[dict[str, Any]]],
	gr_item: dict[str, Any],
) -> dict[str, Any]:
	exact_key = _gr_item_key(gr_item)
	if po_index.get(exact_key):
		return po_index[exact_key][0]

	candidates = fallback_index.get(str(gr_item.get("item_code") or ""), [])
	return candidates[0] if candidates else {}


def calculate_goods_receipt_gross_total(
	gr_items: Iterable[dict[str, Any]],
	po_items: Iterable[dict[str, Any]],
) -> float:
	po_index, fallback_index = _build_po_index(po_items)
	total = 0.0

	for gr_item in gr_items:
		qty = _accepted_qty(gr_item)
		unit_cost = flt(gr_item.get("unit_cost") or gr_item.get("rate"), 6)
		net_amount = qty * unit_cost

		po_item = _match_po_item(po_index, fallback_index, gr_item)
		vat_rate = _line_vat_rate(po_item)
		vat_amount = net_amount * vat_rate / 100
		total += net_amount + vat_amount

	return flt(total, 2)
