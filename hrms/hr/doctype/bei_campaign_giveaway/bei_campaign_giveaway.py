from __future__ import annotations

import json
from datetime import date

import frappe
from frappe.model.document import Document
from frappe.utils import flt, getdate


class BEICampaignGiveaway(Document):
	def before_insert(self):
		if not self.requester_user:
			self.requester_user = frappe.session.user

	def validate(self):
		self._validate_dates()
		self._normalize_json_fields()
		self._validate_items()
		self._compute_tracking_fields()
		self.workflow_state = self.status

	def approved_sources(self) -> list[str]:
		try:
			payload = json.loads(self.source_locations_json or "[]")
		except Exception:
			return []
		sources: list[str] = []
		for entry in payload if isinstance(payload, list) else []:
			if isinstance(entry, dict):
				candidate = str(entry.get("warehouse") or entry.get("source_location") or "").strip()
			else:
				candidate = str(entry or "").strip()
			if candidate and candidate not in sources:
				sources.append(candidate)
		return sources

	def fulfillment_schedule(self) -> list[dict]:
		try:
			payload = json.loads(self.schedule_json or "[]")
		except Exception:
			return []
		return [row for row in payload if isinstance(row, dict)]

	def _validate_dates(self):
		start_date = getdate(self.start_date) if self.start_date else None
		end_date = getdate(self.end_date) if self.end_date else None
		if start_date and end_date and end_date < start_date:
			frappe.throw("End date cannot be earlier than start date.")

	def _normalize_json_fields(self):
		for fieldname in ("source_locations_json", "schedule_json", "supporting_attachments_json"):
			value = self.get(fieldname)
			if value in (None, ""):
				self.set(fieldname, "[]")
				continue
			if isinstance(value, str):
				try:
					json.loads(value)
				except Exception as exc:  # pragma: no cover - defensive guard
					raise frappe.ValidationError(f"Invalid JSON for {fieldname}: {exc}") from exc
				continue
			self.set(fieldname, json.dumps(value))

	def _validate_items(self):
		if not self.items:
			frappe.throw("At least one giveaway item is required.")
		seen: set[str] = set()
		for row in self.items:
			if not row.item_code:
				frappe.throw("Each giveaway row requires an item code.")
			if row.item_code in seen:
				frappe.throw(f"Duplicate giveaway item: {row.item_code}")
			seen.add(row.item_code)
			if float(row.approved_quantity or 0) <= 0:
				frappe.throw(f"Approved quantity for {row.item_code} must be greater than 0.")
			row.served_quantity = flt(row.served_quantity or 0, 3)
			row.remaining_quantity = max(
				flt(row.approved_quantity or 0, 3) - flt(row.served_quantity or 0, 3),
				0.0,
			)
			row.estimated_total_cost = round(
				flt(row.approved_quantity or 0) * flt(row.estimated_unit_cost or 0),
				2,
			)

	def _compute_tracking_fields(self):
		today = getdate(date.today())
		total_approved = sum(flt(row.approved_quantity or 0, 3) for row in self.items or [])
		total_served = sum(flt(row.served_quantity or 0, 3) for row in self.items or [])
		remaining = max(total_approved - total_served, 0.0)

		self.total_approved_quantity = round(total_approved, 3)
		self.quantity_served = round(total_served, 3)
		self.remaining_quantity = round(remaining, 3)
		self.estimated_peso_value = round(
			sum(flt(row.estimated_total_cost or 0) for row in self.items or []),
			2,
		)

		end_date = getdate(self.end_date) if self.end_date else None
		start_date = getdate(self.start_date) if self.start_date else None
		if not end_date or not start_date:
			self.remaining_days = 0
			self.required_daily_pace = 0
			return

		if today < start_date:
			remaining_days = (end_date - start_date).days + 1
		elif today > end_date:
			remaining_days = 0
		else:
			remaining_days = (end_date - today).days + 1

		self.remaining_days = max(int(remaining_days), 0)
		self.required_daily_pace = round((remaining / remaining_days), 3) if remaining_days > 0 else 0
