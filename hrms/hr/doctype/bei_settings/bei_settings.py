# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt, cint


class BEISettings(Document):
	def on_update(self):
		"""Clear cached procurement settings when BEI Settings is updated."""
		frappe.cache().delete_value("bei_procurement_settings")


_PROCUREMENT_FIELDS = (
	"dual_approval_threshold",
	"tin_requirement_threshold",
	"new_supplier_window_days",
	"price_variance_block_pct",
	"price_variance_lookback_days",
	"default_vat_rate",
	"default_ewt_rate",
	"fg_low_stock_threshold",
	"non_fg_low_stock_fallback",
	"shelf_life_dispatch_buffer_days",
	"gr_ir_clearing_account",
	"input_vat_goods_account",
	"input_vat_services_account",
	"input_vat_capital_goods_account",
	"advances_to_suppliers_account",
	"ewt_payable_account",
	"ap_trade_account",
	"default_cost_center",
	"cpo_approver_email",
	"cfo_approver_email",
	"ceo_approver_email",
)

# Defaults that match current hardcoded values — used when BEI Settings fields are empty
_DEFAULTS = {
	"dual_approval_threshold": 500000,
	"tin_requirement_threshold": 250000,
	"new_supplier_window_days": 30,
	"price_variance_block_pct": 10,
	"price_variance_lookback_days": 90,
	"default_vat_rate": 12,
	"default_ewt_rate": 1,
	"fg_low_stock_threshold": 7,
	"non_fg_low_stock_fallback": 10,
	"shelf_life_dispatch_buffer_days": 1,
	"gr_ir_clearing_account": "1104005 - GR/IR CLEARING - BEI",
	"input_vat_goods_account": "1105103 - INPUT VAT-GOODS - BEI",
	"input_vat_services_account": "1105103 - INPUT VAT-GOODS - BEI",
	"input_vat_capital_goods_account": "1105103 - INPUT VAT-GOODS - BEI",
	"advances_to_suppliers_account": "1105203 - ADVANCES TO SUPPLIERS - BEI",
	"ewt_payable_account": "2102202 - EWT PAYABLE - BEI",
	"ap_trade_account": "2101000 - ACCOUNTS PAYABLE - TRADE - BEI",
	"default_cost_center": "Main - BEI",
	"cpo_approver_email": "mae@bebang.ph",
	"cfo_approver_email": "butch@bebang.ph",
	"ceo_approver_email": "sam@bebang.ph",
}

# Fields that should be treated as numeric (Currency/Percent/Int)
_NUMERIC_FIELDS = {
	"dual_approval_threshold",
	"tin_requirement_threshold",
	"new_supplier_window_days",
	"price_variance_block_pct",
	"price_variance_lookback_days",
	"default_vat_rate",
	"default_ewt_rate",
	"fg_low_stock_threshold",
	"non_fg_low_stock_fallback",
	"shelf_life_dispatch_buffer_days",
}


def get_procurement_settings():
	"""
	Return a dict of all procurement settings from BEI Settings.
	Cached in Redis — cleared on BEI Settings update.
	Falls back to hardcoded defaults if fields are empty.
	"""
	cached = frappe.cache().get_value("bei_procurement_settings")
	if cached:
		return cached

	settings = {}
	try:
		doc = frappe.get_single("BEI Settings")
		for field in _PROCUREMENT_FIELDS:
			val = getattr(doc, field, None)
			if val is None or val == "" or val == 0:
				val = _DEFAULTS.get(field)
			if field in _NUMERIC_FIELDS:
				val = flt(val) if "." in str(val or "") else cint(val)
			settings[field] = val
	except Exception:
		# BEI Settings not yet created — use all defaults
		settings = dict(_DEFAULTS)

	frappe.cache().set_value("bei_procurement_settings", settings)
	return settings
