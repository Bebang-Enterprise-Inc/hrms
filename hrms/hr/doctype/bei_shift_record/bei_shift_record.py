# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import get_datetime, time_diff_in_hours, getdate


class BEIShiftRecord(Document):
	def validate(self):
		"""Calculate derived fields and run fraud detection checks"""
		self._calculate_total_hours()
		self._check_overtime()
		self._check_cross_day()
		self._update_status()

		if self.punch_out_time and self.punch_out_latitude and self.punch_out_longitude:
			self._check_velocity()

	def _calculate_total_hours(self):
		"""Calculate total hours worked from punch-in to punch-out"""
		if self.punch_in_time and self.punch_out_time:
			punch_in_dt = get_datetime(self.punch_in_time)
			punch_out_dt = get_datetime(self.punch_out_time)

			if punch_out_dt <= punch_in_dt:
				frappe.throw("Punch-out time must be after punch-in time")

			self.total_hours = time_diff_in_hours(punch_out_dt, punch_in_dt)

	def _check_overtime(self):
		"""Flag shifts exceeding 8 hours as potential overtime"""
		if self.total_hours and self.total_hours > 8:
			self.overtime_flag = 1
		elif self.punch_out_time:
			# Only reset if shift is completed (has punch-out)
			self.overtime_flag = 0

	def _check_cross_day(self):
		"""Flag shifts that span midnight"""
		if self.punch_in_time and self.punch_out_time:
			if getdate(get_datetime(self.punch_in_time)) != getdate(get_datetime(self.punch_out_time)):
				self.cross_day_flag = 1
			else:
				self.cross_day_flag = 0

	def _update_status(self):
		"""Set status based on whether punch-out has been recorded"""
		if self.punch_out_time:
			self.status = "Completed"
		else:
			self.status = "In Progress"

	def _check_velocity(self):
		"""Flag if employee moved impossibly fast between consecutive punches

		Compares the punch-in GPS of this record against the punch-out GPS of
		the employee's most recent previous completed shift. If the implied
		travel speed exceeds 200 km/h, the record is flagged for review.
		"""
		# Get last completed shift for this employee
		last_records = frappe.get_all(
			"BEI Shift Record",
			filters={
				"employee": self.employee,
				"name": ["!=", self.name],
				"punch_out_time": ["is", "set"],
				"status": "Completed",
			},
			fields=["punch_out_time", "punch_out_latitude", "punch_out_longitude"],
			order_by="punch_out_time desc",
			limit=1,
		)

		if not last_records:
			return

		last = last_records[0]
		if not last.punch_out_latitude or not last.punch_out_longitude:
			return

		# Use shared Haversine utility
		from hrms.utils.geo import calculate_haversine_distance

		distance_km = calculate_haversine_distance(
			last.punch_out_latitude,
			last.punch_out_longitude,
			self.punch_in_latitude,
			self.punch_in_longitude,
		) / 1000

		# Calculate time difference in hours
		time_hours = time_diff_in_hours(
			get_datetime(self.punch_in_time),
			get_datetime(last.punch_out_time),
		)

		# Flag if speed > 200 km/h (impossible without flying)
		if time_hours > 0 and distance_km / time_hours > 200:
			self.velocity_flag = 1
