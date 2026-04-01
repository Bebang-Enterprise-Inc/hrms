# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, now_datetime

from hrms.utils.bei_config import get_company
from hrms.utils.standard_buying_bridge import apply_standard_buying_context, resolve_active_buying_warehouse
from hrms.utils.supply_chain_contracts import resolve_warehouse_company

# Approval threshold - PO above this needs both Mae AND Butch
DUAL_APPROVAL_THRESHOLD = 500000
FRAPPE_PO_SYNC_ALLOWED_STATUSES = {
	"Approved",
	"Sent to Supplier",
	"Partially Received",
	"Fully Received",
}


def _clean_csv_emails(value):
	if not value:
		return ""
	emails = [part.strip() for part in str(value).split(",") if part and part.strip()]
	return ", ".join(dict.fromkeys(emails))


class BEIPurchaseOrder(Document):
	def validate(self):
		self.calculate_totals()
		self.set_po_no()
		self.check_dual_approval_requirement()
		self.check_new_vendor_ceo_requirement()
		self.check_price_variance_blocks()

	def check_new_vendor_ceo_requirement(self):
		"""S099/E6: New vendor POs require CEO approval regardless of amount.
		FIX-D2 (S153): Clear requires_ceo_approval when supplier is no longer new.
		"""
		if not self.supplier:
			return

		from hrms.hr.doctype.bei_settings.bei_settings import get_procurement_settings
		settings = get_procurement_settings()
		window_days = cint(settings.get("new_supplier_window_days", 30))

		is_new = frappe.db.sql("""
			SELECT 1 FROM `tabBEI Supplier`
			WHERE name = %s
			AND creation >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
		""", (self.supplier, window_days))

		if is_new:
			self.requires_ceo_approval = 1
		else:
			# FIX-D2 (S153): Clear the one-way ratchet — supplier aged past window.
			# This only governs the new-vendor CEO gate. Other CEO requirements
			# (if any) would be set by their own method.
			self.requires_ceo_approval = 0

	def before_submit(self):
		"""Only fully approved POs can be submitted."""
		if self.status != "Approved":
			frappe.throw(_("Only Approved POs can be submitted. Current status: {0}").format(self.status))

		if self.mae_approval != "Approved":
			frappe.throw(_("Mae approval is required before PO submission"))

		if self.requires_dual_approval and self.butch_approval != "Approved":
			frappe.throw(_("CFO approval is required before PO submission"))

		if cint(self.get("requires_ceo_approval")) and self.get("ceo_approval") != "Approved":
			frappe.throw(_("CEO approval is required for new vendor POs"))

	def on_submit(self):
		"""Lock PO lifecycle and create downstream ERP artifacts."""
		self.on_fully_approved()

	def validate_update_after_submit(self):
		"""Freeze commercial fields after submit; only operational status can move."""
		previous = self.get_doc_before_save()
		if not previous:
			return

		immutable_fields = [
			"po_date",
			"supplier",
			"supplier_name",
			"supplier_email",
			"supplier_contact",
			"delivery_date",
			"ship_to",
			"payment_terms",
			"subtotal",
			"discount_amount",
			"delivery_fee",
			"vat_amount",
			"grand_total",
			"requires_dual_approval",
			"mae_approval",
			"mae_comment",
			"mae_approval_date",
			"butch_approval",
			"butch_comment",
			"butch_approval_date",
			"pr_reference",
		]

		changed = [
			fieldname for fieldname in immutable_fields if self.get(fieldname) != previous.get(fieldname)
		]

		if self._snapshot_items_for_lock(self.items) != self._snapshot_items_for_lock(previous.items):
			changed.append("items")

		if changed:
			frappe.throw(_("Submitted PO is immutable. Disallowed updates: {0}").format(", ".join(changed)))

	@staticmethod
	def _snapshot_items_for_lock(items):
		"""Normalize item rows for immutability comparison."""
		return [
			{
				"item_code": row.item_code,
				"qty": flt(row.qty, 4),
				"unit_cost": flt(row.unit_cost, 4),
				"amount": flt(row.amount, 4),
				"vat_rate": flt(row.vat_rate, 4),
				"vat_amount": flt(row.vat_amount, 4),
				"delivery_schedule": str(row.delivery_schedule) if row.delivery_schedule else None,
			}
			for row in items
		]

	def check_price_variance_blocks(self):
		"""Audit Control 2.6: Block PO if price variance >threshold.

		S104: Compare against contracted price first. Fall back to PO history average
		only when no contracted price exists for the item.
		"""
		from frappe.utils import flt, now_datetime
		from hrms.hr.doctype.bei_settings.bei_settings import get_procurement_settings
		from hrms.api.procurement import get_contracted_price

		settings = get_procurement_settings()
		variance_threshold = flt(settings.get("price_variance_block_pct", 10))
		lookback_days = cint(settings.get("price_variance_lookback_days", 90))

		for item in self.items:
			reference_price = 0
			reference_source = "none"

			# S104: Try contracted price first
			contracted = get_contracted_price(item.item_code, self.supplier)
			if contracted:
				reference_price = flt(contracted["contracted_rate"])
				reference_source = "contracted rate"
			else:
				# Fall back to PO history average
				avg_price = frappe.db.sql(
					"""
					SELECT AVG(poi.unit_cost)
					FROM `tabBEI PO Item` poi
					JOIN `tabBEI Purchase Order` po ON poi.parent = po.name
					WHERE poi.item_code = %s AND po.supplier = %s AND po.status NOT IN ('Draft', 'Cancelled')
					AND po.po_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
				""",
					(item.item_code, self.supplier, lookback_days),
				)
				reference_price = flt(avg_price[0][0]) if avg_price and avg_price[0][0] else 0
				reference_source = "historical average"

			if reference_price > 0:
				variance_pct = abs(flt(item.unit_cost) - reference_price) / reference_price * 100
				if variance_pct > variance_threshold:
					if not item.price_variance_override:
						frappe.throw(
							f"Price for item {item.item_code} (₱{flt(item.unit_cost, 2):,.2f}) exceeds "
							f"{variance_threshold}% variance from {reference_source} (₱{reference_price:,.2f}). "
							f"An override reason is required."
						)
					if not item.price_variance_override_by:
						item.price_variance_override_by = frappe.session.user
						item.price_variance_override_date = now_datetime()

	def set_po_no(self):
		"""Set PO number from name if not already set."""
		if not self.po_no and self.name:
			self.po_no = self.name

	def calculate_totals(self):
		"""Calculate all totals including VAT. S099: reads supplier vat_status."""
		from hrms.hr.doctype.bei_settings.bei_settings import get_procurement_settings
		settings = get_procurement_settings()

		# Determine default VAT rate from supplier's vat_status
		default_vat_rate = flt(settings.get("default_vat_rate", 12))
		if self.supplier:
			vat_status = frappe.db.get_value("BEI Supplier", self.supplier, "vat_status")
			if vat_status in ("Non-VAT", "Exempt"):
				default_vat_rate = 0

		subtotal = 0
		total_vat = 0

		for item in self.items:
			item_subtotal = flt(item.qty, 2) * flt(item.unit_cost, 2)
			item_vat = item_subtotal * flt(item.vat_rate if item.vat_rate is not None else default_vat_rate, 2) / 100

			item.vat_amount = flt(item_vat, 2)
			item.amount = flt(item_subtotal + item_vat, 2)

			subtotal += item_subtotal
			total_vat += item.vat_amount

		self.subtotal = flt(subtotal, 2)
		self.vat_amount = flt(total_vat, 2)
		self.grand_total = flt(
			self.subtotal + self.vat_amount - flt(self.discount_amount, 2) + flt(self.delivery_fee, 2),
			2,
		)

	def check_dual_approval_requirement(self):
		"""Check if PO requires dual approval (>threshold needs both CPO AND CFO)."""
		from hrms.hr.doctype.bei_settings.bei_settings import get_procurement_settings
		threshold = flt(get_procurement_settings().get("dual_approval_threshold", DUAL_APPROVAL_THRESHOLD))
		self.requires_dual_approval = 1 if self.grand_total > threshold else 0

	def after_insert(self):
		self.po_no = self.name
		self.db_set("po_no", self.name, update_modified=False)

	@frappe.whitelist()
	def submit_for_approval(self):
		"""Submit PO for approval workflow."""
		if self.status != "Draft":
			frappe.throw(_("Only Draft POs can be submitted for approval"))

		if not self.items:
			frappe.throw(_("Please add at least one item"))

		# Validate that items have prices — can't approve a ₱0 PO
		zero_price_items = [
			item.item_name or item.item_code
			for item in self.items
			if not flt(item.unit_cost)
		]
		if zero_price_items:
			frappe.throw(
				_("Cannot submit for approval: the following items have no price set: {0}. "
				  "Please enter unit prices before submitting.").format(
					", ".join(zero_price_items)
				),
				title=_("Missing Item Prices"),
			)

		self.status = "Pending Mae Approval"
		self.save()

		# Notify Mae
		self.notify_mae()

		return {"success": True, "message": _("PO submitted for Mae's approval")}

	def notify_mae(self):
		"""Send Google Chat notification to Mae (CPO) for PO approval."""
		self._send_approval_notification(self._get_approver_email("cpo"), "CPO (Mae)")

	def notify_butch(self):
		"""Send Google Chat notification to Butch (CFO) for PO approval."""
		self._send_approval_notification(self._get_approver_email("cfo"), "CFO (Butch)")

	def notify_ceo(self):
		"""Send Google Chat notification to CEO for new-vendor PO approval."""
		self._send_approval_notification(self._get_approver_email("ceo"), "CEO (Sam)")

	def _get_approver_email(self, role: str) -> str:
		"""Get approver email from BEI Settings, fall back to delivery_billing_policy constants."""
		field_map = {"cpo": "cpo_approver_email", "cfo": "cfo_approver_email", "ceo": "ceo_approver_email"}
		try:
			email = frappe.db.get_single_value("BEI Settings", field_map.get(role, ""))
			if email:
				return email
		except Exception:
			pass
		# Fall back to hardcoded constants (pre-S099)
		from hrms.utils.delivery_billing_policy import CPO_APPROVER_EMAIL, CFO_APPROVER_EMAIL
		if role == "ceo":
			return "sam@bebang.ph"
		return CPO_APPROVER_EMAIL if role == "cpo" else CFO_APPROVER_EMAIL

	def _send_approval_notification(self, approver_email: str, approver_label: str):
		"""Send PO approval notification via Google Chat DM."""
		try:
			from hrms.api.google_chat import send_notification_to_user

			items_summary = ", ".join(
				f"{row.item_code} x{flt(row.qty)}" for row in (self.items or [])[:5]
			)
			if len(self.items or []) > 5:
				items_summary += f" (+{len(self.items) - 5} more)"

			supplier_name = self.supplier_name or self.supplier or "Unknown"
			message = (
				f"*PO Approval Required*\n"
				f"PO: {self.po_no or self.name}\n"
				f"Supplier: {supplier_name}\n"
				f"Amount: PHP {flt(self.grand_total):,.2f}\n"
				f"Items: {items_summary}\n"
				f"Requested by: {self.owner}\n"
				f"View: https://my.bebang.ph/procurement/po/{self.name}"
			)
			send_notification_to_user(approver_email, message)
		except Exception as e:
			frappe.log_error(
				f"Failed to send PO approval notification for {self.name} to {approver_label}: {e}",
				"PO Approval Notification Error",
			)

	@frappe.whitelist()
	def approve_mae(self, comment: str | None = None):
		"""Mae (CPO) approves the PO. Only the configured CPO can call this."""
		if self.status != "Pending Mae Approval":
			frappe.throw(_("PO is not pending Mae's approval"))

		from hrms.hr.doctype.bei_settings.bei_settings import get_procurement_settings
		settings = get_procurement_settings()
		cpo_email = settings.get("cpo_approver_email")
		if cpo_email and frappe.session.user != cpo_email:
			frappe.throw(_("Only {0} can approve as CPO").format(cpo_email))

		self.mae_approval = "Approved"
		self.mae_comment = comment
		self.mae_approval_date = now_datetime()

		if self.requires_dual_approval:
			# Needs Butch's approval too
			self.status = "Pending Butch Approval"
			self.save()
			self.notify_butch()
			return {"success": True, "message": _("Mae approved. PO now pending Butch's approval (>500K)")}
		elif cint(self.get("requires_ceo_approval")) and self.get("ceo_approval") != "Approved":
			# New vendor — needs CEO approval
			self.status = "Pending CEO Approval"
			self.save()
			self.notify_ceo()
			return {"success": True, "message": _("Mae approved. PO now pending CEO approval (new vendor)")}
		else:
			# Single approval sufficient
			self.status = "Approved"
			self.save()
			if self.docstatus == 0:
				self.submit()
			return {"success": True, "message": _("PO approved by Mae")}

	@frappe.whitelist()
	def approve_butch(self, comment: str | None = None):
		"""Butch (CFO) approves the PO for >500K. Only the configured CFO can call this."""
		if self.status != "Pending Butch Approval":
			frappe.throw(_("PO is not pending Butch's approval"))

		if not self.requires_dual_approval:
			frappe.throw(_("This PO does not require CFO approval"))

		from hrms.hr.doctype.bei_settings.bei_settings import get_procurement_settings
		settings = get_procurement_settings()
		cfo_email = settings.get("cfo_approver_email")
		if cfo_email and frappe.session.user != cfo_email:
			frappe.throw(_("Only {0} can approve as CFO").format(cfo_email))

		self.butch_approval = "Approved"
		self.butch_comment = comment
		self.butch_approval_date = now_datetime()

		if cint(self.get("requires_ceo_approval")) and self.get("ceo_approval") != "Approved":
			self.status = "Pending CEO Approval"
			self.save()
			self.notify_ceo()
			return {"success": True, "message": _("CFO approved. PO now pending CEO approval (new vendor)")}

		self.status = "Approved"
		self.save()
		if self.docstatus == 0:
			self.submit()

		return {"success": True, "message": _("PO approved by Butch (CFO)")}

	@frappe.whitelist()
	def approve_ceo(self, comment: str | None = None):
		"""CEO approves the PO for new vendors. Only the configured CEO can call this."""
		if self.status != "Pending CEO Approval":
			frappe.throw(_("PO is not pending CEO approval"))

		if not cint(self.get("requires_ceo_approval")):
			frappe.throw(_("This PO does not require CEO approval"))

		from hrms.hr.doctype.bei_settings.bei_settings import get_procurement_settings
		settings = get_procurement_settings()
		ceo_email = settings.get("ceo_approver_email")
		if ceo_email and frappe.session.user != ceo_email:
			frappe.throw(_("Only {0} can approve as CEO").format(ceo_email))

		self.ceo_approval = "Approved"
		self.ceo_comment = comment
		self.ceo_approval_date = now_datetime()
		self.status = "Approved"
		self.save()
		if self.docstatus == 0:
			self.submit()

		return {"success": True, "message": _("PO approved by CEO")}

	def on_fully_approved(self):
		"""Actions when PO is fully approved."""
		# Create Frappe Purchase Order
		self.create_frappe_purchase_order()

		# Update supplier metrics
		self.update_supplier_metrics()

		# Auto-send PO to supplier if email on file
		supplier = frappe.get_doc("BEI Supplier", self.supplier)
		if supplier.email:
			from hrms.api.procurement import send_po_to_supplier

			send_po_to_supplier(self.name, send_mode="auto_approval")

	@frappe.whitelist()
	def reject(self, reason: str, rejector: str = "mae"):
		"""Reject the PO."""
		if self.status not in ["Pending Mae Approval", "Pending Butch Approval", "Pending CEO Approval"]:
			frappe.throw(_("PO is not pending approval"))

		if not reason:
			frappe.throw(_("Please provide a rejection reason"))

		if rejector == "ceo":
			self.ceo_approval = "Rejected"
			self.ceo_comment = reason
			self.ceo_approval_date = now_datetime()
		elif rejector == "mae":
			self.mae_approval = "Rejected"
			self.mae_comment = reason
			self.mae_approval_date = now_datetime()
		else:
			self.butch_approval = "Rejected"
			self.butch_comment = reason
			self.butch_approval_date = now_datetime()

		self.status = "Cancelled"
		self.save()

		return {"success": True, "message": _("PO rejected")}

	def has_required_procurement_approvals(self) -> bool:
		"""Return whether the commercial approval chain is complete."""
		if cint(self.get("requires_ceo_approval")) and self.get("ceo_approval") != "Approved":
			return False
		if self.requires_dual_approval:
			return self.mae_approval == "Approved" and self.butch_approval == "Approved"
		return self.mae_approval == "Approved"

	def can_create_frappe_purchase_order(self) -> bool:
		"""Allow ERP sync after approval even if operations already advanced the PO status."""
		return self.status in FRAPPE_PO_SYNC_ALLOWED_STATUSES and self.has_required_procurement_approvals()

	def create_frappe_purchase_order(self):
		"""
		Create corresponding Frappe Purchase Order.

		PREREQUISITES:
		- BEI PO must be commercially approved
		- For >500K: Both Mae AND Butch approval required
		- For <=500K: Mae approval sufficient

		FIELD MAPPING:
		- supplier -> frappe_supplier (via BEI Supplier link)
		- po_date -> transaction_date
		- delivery_date -> schedule_date
		- items -> items (with item validation/creation)
		- grand_total -> validated against calculated total
		- ship_to -> default warehouse for items

		Returns: Frappe Purchase Order name or None
		"""
		if self.frappe_po:
			frappe.msgprint(_("Already linked to Frappe PO: {0}").format(self.frappe_po), indicator="blue")
			return self.frappe_po

		# Validate approval status
		if self.status not in FRAPPE_PO_SYNC_ALLOWED_STATUSES:
			frappe.throw(
				_(
					"Cannot create Frappe PO - BEI PO must be commercially approved before ERP sync. "
					"Current status: {0}"
				).format(self.status)
			)

		# Validate dual approval for high-value POs
		if self.requires_dual_approval:
			if self.mae_approval != "Approved":
				frappe.throw(_("Mae approval required for PO > 500K"))
			if self.butch_approval != "Approved":
				frappe.throw(_("Butch (CFO) approval required for PO > 500K"))
		elif self.mae_approval != "Approved":
			frappe.throw(_("Mae approval required"))

		# Get or create Frappe Supplier
		bei_supplier = frappe.get_doc("BEI Supplier", self.supplier)
		frappe_supplier = bei_supplier.get_or_create_frappe_supplier()

		if not frappe_supplier:
			frappe.throw(_("Could not get or create Frappe Supplier for {0}").format(self.supplier))

		resolved_store_warehouse = resolve_active_buying_warehouse(self.ship_to, company=get_company())
		if not resolved_store_warehouse:
			# Fallback: use "Stores - BEI" as default warehouse when ship_to is empty
			resolved_store_warehouse = resolve_active_buying_warehouse("Stores", company=get_company())
		erp_company = resolve_warehouse_company(resolved_store_warehouse) or get_company()

		# Validate and prepare items
		po_items = []
		for item in self.items:
			frappe_item = self._get_or_create_item(item)

			po_row = {
				"item_code": frappe_item,
				"item_name": item.item_name or item.item_code,
				"description": item.description or item.item_name or item.item_code,
				"qty": flt(item.qty, 2),
				"uom": item.uom or "Nos",
				"stock_uom": item.uom or "Nos",
				"conversion_factor": 1,
				"rate": flt(item.unit_cost, 2),
				"schedule_date": self.delivery_date,
				"bei_po_item": item.name,  # Reference back to BEI item
			}
			if resolved_store_warehouse:
				po_row["warehouse"] = resolved_store_warehouse

			po_items.append(po_row)

		if not po_items:
			frappe.throw(_("No valid items to create Purchase Order"))

		# Create Frappe PO
		po = frappe.get_doc(
			{
				"doctype": "Purchase Order",
				"supplier": frappe_supplier,
				"transaction_date": self.po_date,
				"schedule_date": self.delivery_date,
				"company": erp_company,
				"currency": "PHP",
				"buying_price_list": "Standard Buying",
				"price_list_currency": "PHP",
				"plc_conversion_rate": 1,
				"conversion_rate": 1,
				"payment_terms_template": self.payment_terms,
				"bei_purchase_order": self.name,  # Reference back to BEI PO
				"items": po_items,
			}
		)
		apply_standard_buying_context(
			po, store_label=resolved_store_warehouse or self.ship_to, legal_entity=erp_company
		)

		# Apply discount if any
		if flt(self.discount_amount, 2) > 0:
			po.discount_amount = flt(self.discount_amount, 2)
			po.additional_discount_percentage = 0
			po.apply_discount_on = "Grand Total"

		try:
			po.insert(ignore_permissions=True)
			po.submit()

			self.frappe_po = po.name
			self.db_set("frappe_po", po.name, update_modified=False)

			frappe.msgprint(_("Created and submitted Frappe PO: {0}").format(po.name), indicator="green")

			return po.name

		except Exception as e:
			frappe.log_error(
				f"Failed to create Frappe PO for BEI PO {self.name}: {e}", "BEI PO Integration Error"
			)
			# Do NOT throw — Frappe PO sync is downstream of BEI approval.
			# The BEI PO approval must succeed even if Frappe PO creation fails.
			# The Frappe PO can be retried later via can_create_frappe_purchase_order().
			frappe.msgprint(
				_("BEI PO approved but Frappe PO sync failed: {0}. This can be retried later.").format(str(e)),
				indicator="orange",
			)

	def _get_or_create_item(self, bei_item):
		"""
		Get existing Frappe Item — S104: block auto-create for new items.

		Existing items (462 grandfathered) are returned as-is.
		New item codes that don't exist in Frappe are BLOCKED — they must go
		through the BEI Item Request approval workflow first.

		Returns: Item code (name)
		"""
		item_code = bei_item.item_code

		# Check if item exists — grandfathered items pass through
		if frappe.db.exists("Item", item_code):
			return item_code

		# S104: Block auto-creation of new items
		frappe.throw(
			_("Item {0} does not exist. Submit a New Item Request for CPO approval "
			  "before adding it to a Purchase Order.").format(item_code),
			title=_("Item Not Found")
		)

	def _determine_item_group(self, bei_item):
		"""
		Determine appropriate Item Group for a BEI item.

		Categories based on BEI item master:
		- Raw Materials: Ingredients, supplies
		- Finished Goods: Ready products
		- Packaging: Boxes, bags, containers
		- Consumables: Cleaning, office supplies
		- Fixed Assets: Equipment, furniture

		Returns: Item Group name
		"""
		item_name_lower = (bei_item.item_name or "").lower()
		item_code_lower = (bei_item.item_code or "").lower()

		# Check for packaging keywords
		packaging_keywords = ["box", "bag", "container", "wrapper", "pack", "cup", "lid"]
		if any(kw in item_name_lower or kw in item_code_lower for kw in packaging_keywords):
			return "Packaging Material"

		# Check for raw materials
		raw_keywords = ["flour", "sugar", "oil", "salt", "sauce", "powder", "ingredient"]
		if any(kw in item_name_lower for kw in raw_keywords):
			return "Raw Material"

		# Check for consumables
		consumable_keywords = ["cleaning", "soap", "sanitizer", "tissue", "paper", "office"]
		if any(kw in item_name_lower for kw in consumable_keywords):
			return "Consumable"

		# Check for fixed assets
		asset_keywords = ["equipment", "machine", "refrigerator", "freezer", "oven", "furniture"]
		if any(kw in item_name_lower for kw in asset_keywords):
			return "Fixed Asset"

		# Default to Products (general category)
		return "Products"

	def update_supplier_metrics(self):
		"""Update supplier metrics after PO approval."""
		if self.supplier:
			supplier = frappe.get_doc("BEI Supplier", self.supplier)
			supplier.update_metrics()
			supplier.save()

	@frappe.whitelist()
	def send_to_supplier(self):
		"""Record a supplier send event for legacy callers."""
		return self.record_distribution_event(
			action="send",
			outcome="success",
			recipient_email=self.supplier_email,
			send_mode="manual",
		)

	@frappe.whitelist()
	def record_distribution_event(
		self,
		action="send",
		outcome="success",
		recipient_email=None,
		cc_emails=None,
		send_mode="manual",
		message_id=None,
		error_message=None,
	):
		"""Persist PO distribution state separately from the core approval workflow."""
		if self.status not in ["Approved", "Sent to Supplier"]:
			if self.status not in ["Partially Received", "Fully Received"]:
				frappe.throw(_("PO must be approved before sending to supplier"))

		if not (recipient_email or self.supplier_email):
			frappe.throw(_("Supplier email is required"))

		recipient_email = (recipient_email or self.supplier_email or "").strip()
		cc_emails = _clean_csv_emails(cc_emails)
		action = (action or "send").strip().lower()
		send_mode = (send_mode or action or "manual").strip().lower()
		actor = frappe.session.user or "Guest"

		self.distribution_last_action = action
		self.distribution_send_mode = send_mode
		self.distribution_recipient_email = recipient_email
		self.distribution_cc_emails = cc_emails
		self.distribution_message_id = message_id or ""

		if outcome == "success":
			sent_at = now_datetime()
			self.distribution_delivery_count = cint(self.distribution_delivery_count) + 1
			self.distribution_last_sent_at = sent_at
			self.distribution_last_sent_by = actor
			self.distribution_last_error = ""
			if send_mode == "auto":
				self.distribution_status = "Auto-Sent"
			elif action == "resend":
				self.distribution_status = "Resent"
			else:
				self.distribution_status = "Sent"

			self.sent_to_supplier_date = sent_at
			self.sent_by = actor
			if self.status == "Approved":
				self.status = "Sent to Supplier"
		else:
			self.distribution_status = "Send Failed"
			self.distribution_last_error = (error_message or _("Unknown email delivery error")).strip()

		self.save(ignore_permissions=True)
		self._append_distribution_comment(
			action=action,
			outcome=outcome,
			recipient_email=recipient_email,
			cc_emails=cc_emails,
			send_mode=send_mode,
			error_message=error_message,
		)

		return {
			"success": outcome == "success",
			"distribution_status": self.distribution_status,
			"distribution_delivery_count": cint(self.distribution_delivery_count),
			"recipient_email": self.distribution_recipient_email,
			"cc_emails": self.distribution_cc_emails,
			"message_id": self.distribution_message_id,
			"message": _("PO distribution state updated"),
		}

	def _append_distribution_comment(
		self,
		*,
		action,
		outcome,
		recipient_email,
		cc_emails,
		send_mode,
		error_message=None,
	):
		if outcome == "success":
			message = _("PO {0} recorded via {1} to {2}.").format(action, send_mode, recipient_email)
			if cc_emails:
				message += " " + _("CC: {0}.").format(cc_emails)
		else:
			message = _("PO {0} failed via {1} to {2}. Error: {3}").format(
				action,
				send_mode,
				recipient_email,
				error_message or _("Unknown error"),
			)

		try:
			self.add_comment("Info", message)
		except Exception:
			frappe.log_error(message, "BEI PO Distribution Comment Failed")

	@frappe.whitelist()
	def update_received_qty(self, item_code: str, received_qty: float | int):
		"""Update received quantity for an item (called from GR)."""
		found = False
		for item in self.items:
			if item.item_code == item_code:
				found = True
				new_received_qty = flt(item.received_qty, 2) + flt(received_qty, 2)
				item.received_qty = new_received_qty
				if item.name:
					frappe.db.set_value(
						"BEI PO Item",
						item.name,
						"received_qty",
						new_received_qty,
						update_modified=False,
					)

		if not found:
			frappe.throw(_("Item {0} not found in PO").format(item_code))

		# Check if fully received
		fully_received = all(flt(item.received_qty, 2) >= flt(item.qty, 2) for item in self.items)

		new_status = self.status
		if fully_received:
			new_status = "Fully Received"
		else:
			partially_received = any(flt(item.received_qty, 2) > 0 for item in self.items)
			if partially_received:
				new_status = "Partially Received"

		if new_status != self.status:
			self.status = new_status
			if self.docstatus == 1:
				self.db_set("status", new_status, update_modified=False)
			else:
				self.save()
