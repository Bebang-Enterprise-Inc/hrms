"""S099: Populate BEI Settings with procurement defaults and seed supplier ATC codes.

Ensures existing behavior is unchanged by writing current hardcoded values
into the new configurable fields.
"""

import frappe


def execute():
	# --- 1. Seed BEI Settings procurement fields ---
	if not frappe.db.exists("DocType", "BEI Settings"):
		return

	settings_defaults = {
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

	for field, value in settings_defaults.items():
		try:
			current = frappe.db.get_single_value("BEI Settings", field)
			if not current:
				frappe.db.set_single_value("BEI Settings", field, value)
		except Exception:
			# Field may not exist yet if migrate hasn't run — skip silently
			pass

	# --- 2. Seed supplier ATC codes and input VAT category ---
	if not frappe.db.exists("DocType", "BEI Supplier"):
		return

	# Set atc_code=WI100 for all suppliers without one
	frappe.db.sql("""
		UPDATE `tabBEI Supplier`
		SET atc_code = 'WI100'
		WHERE atc_code IS NULL OR atc_code = ''
	""")

	# Set input_vat_category=Goods for all suppliers without one
	frappe.db.sql("""
		UPDATE `tabBEI Supplier`
		SET input_vat_category = 'Goods'
		WHERE input_vat_category IS NULL OR input_vat_category = ''
	""")

	frappe.db.commit()
