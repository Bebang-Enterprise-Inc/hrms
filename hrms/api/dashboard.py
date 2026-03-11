# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
Dashboard API
Provides KPIs and metrics for store, area, and ops dashboards
"""

import json

import frappe
from frappe import _
from frappe.utils import add_days, nowdate


@frappe.whitelist()
def get_store_dashboard(store: str | None = None, period: str = "week") -> dict:
	"""Get dashboard KPIs for a store."""
	if not store:
		return {"store": None, "period": period, "kpis": {}}

	today = nowdate()
	if period == "week":
		start_date = add_days(today, -7)
	elif period == "month":
		start_date = add_days(today, -30)
	else:
		start_date = add_days(today, -7)

	# Orders
	orders = frappe.db.count("BEI Store Order", filters={"store": store, "order_date": [">=", start_date]})
	pending_orders = frappe.db.count(
		"BEI Store Order", filters={"store": store, "status": "Pending Approval"}
	)

	# FQI
	fqi_count = frappe.db.count("BEI FQI Report", filters={"store": store, "reported_at": [">=", start_date]})
	open_fqi = frappe.db.count("BEI FQI Report", filters={"store": store, "status": "Open"})

	# Receiving
	receiving_count = frappe.db.count(
		"BEI Store Receiving", filters={"store": store, "receiving_date": [">=", start_date]}
	)

	# Checklists
	opening_count = frappe.db.count(
		"BEI Store Opening Report", filters={"store": store, "report_date": [">=", start_date]}
	)
	closing_count = frappe.db.count(
		"BEI Store Closing Report", filters={"store": store, "report_date": [">=", start_date]}
	)

	return {
		"store": store,
		"period": period,
		"kpis": {
			"total_orders": orders,
			"pending_approvals": pending_orders,
			"fqi_incidents": fqi_count,
			"open_fqi": open_fqi,
			"deliveries_received": receiving_count,
			"opening_reports": opening_count,
			"closing_reports": closing_count,
		},
	}


@frappe.whitelist()
def get_area_dashboard(area_supervisor: str | None = None, period: str = "week") -> dict:
	"""Get aggregated dashboard for area supervisor's stores."""
	if not area_supervisor:
		area_supervisor = frappe.session.user

	# Get stores managed by this supervisor
	try:
		stores = frappe.get_all(
			"Warehouse", filters={"custom_area_supervisor": area_supervisor}, pluck="name"
		)
	except Exception:
		# custom_area_supervisor field may not exist in this environment
		stores = []

	if not stores:
		return {"stores": [], "kpis": {}}

	today = nowdate()
	start_date = add_days(today, -7) if period == "week" else add_days(today, -30)

	total_orders = 0
	total_pending = 0
	total_fqi = 0

	for store in stores:
		total_orders += frappe.db.count(
			"BEI Store Order", filters={"store": store, "order_date": [">=", start_date]}
		)
		total_pending += frappe.db.count(
			"BEI Store Order", filters={"store": store, "status": "Pending Approval"}
		)
		total_fqi += frappe.db.count(
			"BEI FQI Report", filters={"store": store, "reported_at": [">=", start_date]}
		)

	return {
		"stores": stores,
		"store_count": len(stores),
		"kpis": {"total_orders": total_orders, "pending_approvals": total_pending, "total_fqi": total_fqi},
	}


@frappe.whitelist()
def get_ops_dashboard(period: str = "week") -> dict:
	"""Get company-wide operations dashboard."""
	today = nowdate()
	start_date = add_days(today, -7) if period == "week" else add_days(today, -30)

	return {
		"period": period,
		"kpis": {
			"total_orders": frappe.db.count("BEI Store Order", filters={"order_date": [">=", start_date]}),
			"pending_approvals": frappe.db.count("BEI Store Order", filters={"status": "Pending Approval"}),
			"total_fqi": frappe.db.count("BEI FQI Report", filters={"reported_at": [">=", start_date]}),
			"open_fqi": frappe.db.count("BEI FQI Report", filters={"status": "Open"}),
			"trips_today": frappe.db.count("BEI Distribution Trip", filters={"trip_date": today}),
			"support_tickets_open": frappe.db.count("BEI Support Ticket", filters={"status": "Open"}),
		},
	}


@frappe.whitelist()
def get_sales_trend(store: str | None = None, period: str = "week") -> dict:
	"""Get sales trend from the API-backed daily sales source with legacy fallback."""
	if not store:
		return {"trend": []}
	today = nowdate()
	start_date = add_days(today, -7) if period == "week" else add_days(today, -30)

	data = frappe.get_all(
		"BEI Store Sales Day",
		filters={"store": store, "business_date": [">=", start_date]},
		fields=[
			"business_date as pos_date",
			"gross_sales",
			"net_sales",
			"cups_sold as transaction_count",
			"source_system",
		],
		order_by="business_date asc",
	)
	if data:
		return {"trend": data, "source": "BEI Store Sales Day"}

	legacy_data = frappe.get_all(
		"BEI POS Upload",
		filters={"store": store, "pos_date": [">=", start_date]},
		fields=["pos_date", "gross_sales", "net_sales", "transaction_count"],
		order_by="pos_date asc",
	)
	return {"trend": legacy_data, "source": "BEI POS Upload"}


@frappe.whitelist()
def get_fqi_trend(store: str | None = None, period: str = "week") -> dict:
	"""Get FQI incident trend."""
	today = nowdate()
	start_date = add_days(today, -7) if period == "week" else add_days(today, -30)

	filters = {"reported_at": [">=", start_date]}
	if store:
		filters["store"] = store

	# Group by issue type
	if store:
		sql = """
            SELECT issue_type, COUNT(*) as count
            FROM `tabBEI FQI Report`
            WHERE reported_at >= %s AND store = %s
            GROUP BY issue_type
        """
		by_type = frappe.db.sql(sql, [start_date, store], as_dict=True)
	else:
		sql = """
            SELECT issue_type, COUNT(*) as count
            FROM `tabBEI FQI Report`
            WHERE reported_at >= %s
            GROUP BY issue_type
        """
		by_type = frappe.db.sql(sql, [start_date], as_dict=True)

	return {"by_type": by_type}


@frappe.whitelist()
def get_order_fulfillment_rate(store: str | None = None, period: str = "week") -> dict:
	"""Get order fulfillment statistics."""
	today = nowdate()
	start_date = add_days(today, -7) if period == "week" else add_days(today, -30)

	filters = {"order_date": [">=", start_date]}
	if store:
		filters["store"] = store

	total = frappe.db.count("BEI Store Order", filters=filters)

	delivered_filters = {**filters, "status": "Delivered"}
	delivered = frappe.db.count("BEI Store Order", filters=delivered_filters)

	return {
		"total_orders": total,
		"delivered": delivered,
		"fulfillment_rate": round((delivered / total * 100), 1) if total > 0 else 0,
	}
