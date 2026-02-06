# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class BEIStoreClosingReport(Document):
	def before_insert(self):
		if not self.submitted_by:
			self.submitted_by = frappe.session.user

	def before_save(self):
		self.calculate_funds()
		self.calculate_denomination_total()
		self.calculate_cash_variance()
		self.calculate_fund_variances()
		self.check_cash_variance_alerts()
		self.calculate_inventory_variance()
		self.update_signoff_timestamps()
		self.update_stage_completed()
		self.update_status()

	def validate(self):
		self.validate_variance_explanation()
		self.validate_pos_down_mode()
		self.validate_maintenance_fields()

	def calculate_funds(self):
		"""Auto-calculate total funds from individual fund components."""
		self.total_funds = (
			(self.petty_cash_fund or 0) +
			(self.delivery_fund or 0) +
			(self.change_fund or 0)
		)

	def calculate_denomination_total(self):
		"""Auto-calculate total from bill/coin denominations."""
		self.denom_total = (
			(self.denom_1000 or 0) * 1000 +
			(self.denom_500 or 0) * 500 +
			(self.denom_200 or 0) * 200 +
			(self.denom_100 or 0) * 100 +
			(self.denom_50 or 0) * 50 +
			(self.denom_20 or 0) * 20 +
			(self.denom_coins or 0)
		)

	def calculate_cash_variance(self):
		"""Calculate cash variance from POS sales minus non-cash payments."""
		expected_cash = (self.pos_total_sales or 0) - (self.card_payments or 0) - (self.gcash_total or 0)
		self.cash_variance = (self.actual_cash_count or 0) - expected_cash

	def calculate_fund_variances(self):
		"""
		Calculate variances for PCF and Delivery Fund.

		For now, variance is calculated as actual vs expected (baseline).
		This will be enhanced once we have expected fund baselines per store.
		"""
		# PCF variance: actual fund vs expected baseline
		# TODO: Get expected PCF baseline from store configuration
		expected_pcf = 5000  # Placeholder - should be from store master
		if self.petty_cash_fund is not None:
			self.pcf_variance = self.petty_cash_fund - expected_pcf
		else:
			self.pcf_variance = 0

		# DF variance: actual fund vs expected baseline
		# TODO: Get expected DF baseline from store configuration
		expected_df = 10000  # Placeholder - should be from store master
		if self.delivery_fund is not None:
			self.df_variance = self.delivery_fund - expected_df
		else:
			self.df_variance = 0

	def check_cash_variance_alerts(self):
		"""
		Check if cash fund variances exceed thresholds and set alerts.

		Priority #2 from Finance & Accounting Automation: Cash variance monitoring
		Thresholds from Accounting questionnaire:
		- PCF: PHP 7,500
		- Delivery Fund: PHP 15,000
		"""
		# PCF variance check
		if self.pcf_variance is not None and self.pcf_variance_threshold:
			if abs(self.pcf_variance) > self.pcf_variance_threshold:
				self.pcf_variance_alert = 1
				# TODO: Send Google Chat notification to Accounting Manager
				# Space: Accounting Alerts (to be created)
				# Message: "PCF Variance Alert: {store} - PHP {variance:,.2f} (Threshold: PHP {threshold:,.2f})"
			else:
				self.pcf_variance_alert = 0

		# DF variance check
		if self.df_variance is not None and self.df_variance_threshold:
			if abs(self.df_variance) > self.df_variance_threshold:
				self.df_variance_alert = 1
				# TODO: Send Google Chat notification to Accounting Manager
				# Space: Accounting Alerts (to be created)
				# Message: "DF Variance Alert: {store} - PHP {variance:,.2f} (Threshold: PHP {threshold:,.2f})"
			else:
				self.df_variance_alert = 0

	def calculate_inventory_variance(self):
		"""Calculate total inventory variance from spot check items."""
		if self.inventory_spot_check:
			total_variance = 0
			variance_count = 0
			for item in self.inventory_spot_check:
				if item.variance is not None:
					total_variance += item.variance
					if item.variance != 0:
						variance_count += 1
			self.inventory_variance_total = total_variance
			self.inventory_variance_count = variance_count

	def update_signoff_timestamps(self):
		"""Set timestamps when signoffs are checked."""
		if self.cashier_signoff and not self.cashier_signoff_time:
			self.cashier_signoff_time = now_datetime()
		if self.production_signoff and not self.production_signoff_time:
			self.production_signoff_time = now_datetime()

	def update_stage_completed(self):
		"""Update stage_completed based on which sections are filled."""
		# Check Stage 1: Cash Count
		stage1_complete = bool(
			self.petty_cash_fund is not None or
			self.delivery_fund is not None or
			self.change_fund is not None
		)

		# Check Stage 2: Checklist (inventory spot check + signoffs)
		stage2_complete = bool(
			self.inventory_spot_check and
			len(self.inventory_spot_check) >= 12 and
			self.cashier_signoff and
			self.production_signoff
		)

		# Check Stage 3: Photos & Files (required photos from DocType)
		stage3_complete = bool(
			self.photo_zread and
			self.photo_xread_opening and
			self.photo_xread_closing
		)

		# Set stage_completed based on progress (lowercase to match DocType options)
		if stage3_complete and stage2_complete and stage1_complete:
			self.stage_completed = "complete"
		elif stage2_complete and stage1_complete:
			self.stage_completed = "photos"
		elif stage1_complete:
			self.stage_completed = "checklist"
		else:
			self.stage_completed = "cash"

	def update_status(self):
		"""Update status based on various conditions."""
		# POS Down takes priority
		if self.pos_down:
			self.status = "POS Down - Pending Review"
			return

		# Variance threshold check (±50 per plan)
		if self.cash_variance and abs(self.cash_variance) > 50:
			self.status = "Variance Flagged"
			return

		# Inventory variance check
		if self.get("inventory_variance_count") and self.inventory_variance_count > 0:
			self.status = "Inventory Variance"
			return

		# Maintenance pending
		if self.has_maintenance_today and not self.maintenance_verified:
			self.status = "Pending Maintenance Verification"
			return

		# All good
		if self.stage_completed == "complete":
			self.status = "Submitted"

	def validate_variance_explanation(self):
		"""Require explanation if variance exceeds threshold."""
		VARIANCE_THRESHOLD = 50

		if self.cash_variance and abs(self.cash_variance) > VARIANCE_THRESHOLD:
			if not self.variance_explanation:
				frappe.throw(
					_("Variance explanation is required when cash variance exceeds ±₱{0}. "
					  "Current variance: ₱{1}").format(VARIANCE_THRESHOLD, self.cash_variance)
				)

	def validate_pos_down_mode(self):
		"""Validate POS Down mode fields."""
		if self.pos_down:
			if not self.pos_down_estimated_sales:
				frappe.throw(_("Estimated sales is required when POS is down"))
			if not self.pos_down_notes:
				frappe.throw(_("Notes explaining the POS down situation are required"))

	def validate_maintenance_fields(self):
		"""Validate maintenance verification fields if maintenance was scheduled."""
		if self.has_maintenance_today and self.maintenance_verified:
			if not self.maintenance_technician:
				frappe.throw(_("Technician name is required for maintenance verification"))
			if not self.maintenance_work_done:
				frappe.throw(_("Work description is required for maintenance verification"))
