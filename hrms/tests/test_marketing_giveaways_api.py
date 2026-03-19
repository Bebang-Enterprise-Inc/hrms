from __future__ import annotations

import importlib.util
import sys
import types
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _ensure_package(name: str) -> types.ModuleType:
	module = sys.modules.get(name)
	if module is None:
		module = types.ModuleType(name)
		module.__path__ = []
		sys.modules[name] = module
		if "." in name:
			parent_name, child_name = name.rsplit(".", 1)
			parent = _ensure_package(parent_name)
			setattr(parent, child_name, module)
	return module


def _register_module(name: str, module: types.ModuleType) -> None:
	sys.modules[name] = module
	if "." in name:
		parent_name, child_name = name.rsplit(".", 1)
		parent = _ensure_package(parent_name)
		setattr(parent, child_name, module)


def _install_fake_dependencies(user_roles: list[str] | None = None):
	user_roles = user_roles or ["System Manager"]

	frappe = types.ModuleType("frappe")

	def _db_get_value(doctype, name=None, fields=None, as_dict=False, *args, **kwargs):
		if doctype == "Item":
			payload = {
				"name": str(name or "ITEM-001"),
				"item_name": "Presidential",
				"stock_uom": "Nos",
				"valuation_rate": 12.5,
				"item_group": "Finished Goods",
				"is_stock_item": 1,
				"disabled": 0,
			}
			if as_dict:
				return payload
			if isinstance(fields, (list, tuple)):
				return [payload.get(field) for field in fields]
			return payload.get(str(fields or "name"))
		return None

	class PermissionError(Exception):
		pass

	class ValidationError(Exception):
		pass

	def whitelist(*args, **kwargs):
		if args and callable(args[0]) and len(args) == 1 and not kwargs:
			return args[0]

		def decorator(fn):
			return fn

		return decorator

	def throw(message, exc=None):
		err_cls = exc if isinstance(exc, type) else ValidationError
		raise err_cls(message)

	def __getattr__(name: str):
		if name == "db":
			return frappe.local.db
		if name == "session":
			return frappe.local.session
		raise AttributeError(name)

	frappe.local = types.SimpleNamespace(
		db=types.SimpleNamespace(
			get_value=_db_get_value,
			exists=lambda *args, **kwargs: None,
			count=lambda *args, **kwargs: 0,
			savepoint=lambda *args, **kwargs: None,
			release_savepoint=lambda *args, **kwargs: None,
			rollback=lambda *args, **kwargs: None,
			commit=lambda *args, **kwargs: None,
		),
		session=types.SimpleNamespace(user="tester@bebang.ph"),
	)
	frappe.whitelist = whitelist
	frappe.throw = throw
	frappe.PermissionError = PermissionError
	frappe.ValidationError = ValidationError
	frappe.get_roles = lambda user=None: list(user_roles)
	frappe.get_all = lambda *args, **kwargs: []
	frappe.get_doc = lambda *args, **kwargs: None
	frappe.new_doc = lambda *args, **kwargs: None
	frappe.conf = {}
	frappe._ = lambda text: text
	frappe.__getattr__ = __getattr__

	utils = types.ModuleType("frappe.utils")
	utils.cint = lambda value: int(value or 0)

	def _flt(value, precision=None):
		number = float(value or 0)
		return round(number, precision) if precision is not None else number

	def _getdate(value=None):
		if value in (None, ""):
			return date(2026, 3, 18)
		if isinstance(value, date):
			return value
		return datetime.strptime(str(value), "%Y-%m-%d").date()

	utils.flt = _flt
	utils.getdate = _getdate
	utils.now_datetime = lambda: datetime(2026, 3, 18, 9, 30, 0)
	utils.nowdate = lambda: "2026-03-18"
	frappe.utils = utils

	_register_module("frappe", frappe)
	_register_module("frappe.utils", utils)

	_ensure_package("hrms.utils")
	bei_config = types.ModuleType("hrms.utils.bei_config")
	bei_config.get_company = lambda: "Bebang Enterprise Inc."
	_register_module("hrms.utils.bei_config", bei_config)

	sales_location_mapping = types.ModuleType("hrms.utils.sales_location_mapping")
	sales_location_mapping.load_sales_location_mapping = lambda: {
		"sm megamall": {
			"location_id": 2338,
			"warehouse_name": "SM Megamall",
			"warehouse_record_name": "SM Megamall - Bebang Enterprise Inc.",
		},
		"ayala solenad": {
			"location_id": 2112,
			"warehouse_name": "Ayala Solenad",
			"warehouse_record_name": "Ayala Solenad - Bebang Enterprise Inc.",
		},
		"ayala evo": {
			"location_id": 2339,
			"warehouse_name": "Ayala Evo",
			"warehouse_record_name": "Ayala Evo - Bebang Enterprise Inc.",
		},
	}
	_register_module("hrms.utils.sales_location_mapping", sales_location_mapping)

	sentry_mod = types.ModuleType("hrms.utils.sentry")
	sentry_mod.capture_backend_message = lambda *args, **kwargs: None
	sentry_mod.set_backend_observability_context = lambda *args, **kwargs: None
	_register_module("hrms.utils.sentry", sentry_mod)

	supply_chain_contracts = types.ModuleType("hrms.utils.supply_chain_contracts")
	supply_chain_contracts.resolve_warehouse_company = lambda warehouse: "Bebang Enterprise Inc."
	_register_module("hrms.utils.supply_chain_contracts", supply_chain_contracts)

	return frappe


def _load_module(alias: str, user_roles: list[str] | None = None):
	_install_fake_dependencies(user_roles=user_roles)
	spec = importlib.util.spec_from_file_location(alias, ROOT / "hrms" / "api" / "marketing_giveaways.py")
	module = importlib.util.module_from_spec(spec)
	assert spec and spec.loader
	spec.loader.exec_module(module)
	return module


@dataclass
class FakeItemRow:
	item_code: str
	item_name: str = ""
	uom: str = "Nos"
	approved_quantity: float = 0.0
	remaining_quantity: float = 0.0
	estimated_unit_cost: float = 0.0
	served_quantity: float = 0.0


@dataclass
class FakeCampaignDoc:
	name: str = "CMP-0001"
	campaign_name: str = "Golf Tournament Sponsorship"
	campaign_code: str = "GOLF-2026"
	status: str = "Approved / Active"
	workflow_state: str = "Approved / Active"
	start_date: str = "2026-03-10"
	end_date: str = "2026-03-20"
	daily_cap_quantity: float = 0.0
	estimated_peso_value: float = 100.0
	approved_value_tolerance_pct: float = 0.0
	finance_expense_account: str = "6005001 - MARKETING GIVEAWAYS - Bebang Enterprise Inc."
	cost_center: str = "Main - BEI"
	budget_owner: str = "Marketing"
	requester_user: str = "marketing@bebang.ph"
	source_locations_json: str = "[\"SM Megamall - Bebang Enterprise Inc.\"]"
	schedule_json: str = "[]"
	items: list[FakeItemRow] = field(default_factory=list)
	total_approved_quantity: float = 10.0
	quantity_served: float = 0.0
	remaining_quantity: float = 10.0
	remaining_days: int = 0
	required_daily_pace: float = 0.0
	latest_issue_date: str | None = None

	def save(self, ignore_permissions=True):
		return None


class FakeIssueDoc:
	def __init__(self):
		self.name = "CGI-0001"
		self.campaign = None
		self.status = "Draft"
		self.issue_date = None
		self.idempotency_key = None
		self.source_location = None
		self.item_code = None
		self.item_name = None
		self.uom = None
		self.quantity = 0.0
		self.actual_unit_cost = 0.0
		self.actual_total_cost = 0.0
		self.finance_expense_account = None
		self.cost_center = None
		self.budget_owner = None
		self.notes = None
		self.stock_entry = None
		self.insert_calls = 0
		self.save_calls = 0

	def insert(self, ignore_permissions=True):
		self.insert_calls += 1

	def save(self, ignore_permissions=True):
		self.save_calls += 1


def test_validate_issue_request_blocks_quantity_overrun(monkeypatch):
	module = _load_module("marketing_giveaways_quantity_overrun")
	campaign = FakeCampaignDoc(
		items=[FakeItemRow(item_code="ITEM-001", approved_quantity=10, remaining_quantity=2, estimated_unit_cost=5)]
	)
	exceptions: list[dict] = []

	def _capture_exception(**kwargs):
		exceptions.append(kwargs)
		return "EXC-001"

	monkeypatch.setattr(module, "_create_exception", _capture_exception)

	with pytest.raises(module.frappe.ValidationError) as excinfo:
		module._validate_issue_request(
			campaign,
			"SM Megamall - Bebang Enterprise Inc.",
			"ITEM-001",
			3,
			date(2026, 3, 18),
		)

	assert "quantity exceeds remaining balance" in str(excinfo.value).lower()
	assert exceptions[0]["exception_type"] == "Quantity Overrun"


def test_validate_issue_request_blocks_non_approved_source(monkeypatch):
	module = _load_module("marketing_giveaways_source_block")
	campaign = FakeCampaignDoc(
		items=[FakeItemRow(item_code="ITEM-001", approved_quantity=10, remaining_quantity=10, estimated_unit_cost=5)]
	)
	exceptions: list[dict] = []

	def _capture_exception(**kwargs):
		exceptions.append(kwargs)
		return "EXC-002"

	monkeypatch.setattr(module, "_create_exception", _capture_exception)

	with pytest.raises(module.frappe.ValidationError) as excinfo:
		module._validate_issue_request(
			campaign,
			"Ayala Solenad - Bebang Enterprise Inc.",
			"ITEM-001",
			2,
			date(2026, 3, 18),
		)

	assert "source not approved" in str(excinfo.value).lower()
	assert exceptions[0]["exception_type"] == "Source Not Approved"


def test_validate_issue_request_blocks_daily_cap(monkeypatch):
	module = _load_module("marketing_giveaways_daily_cap")
	campaign = FakeCampaignDoc(
		daily_cap_quantity=5,
		items=[FakeItemRow(item_code="ITEM-001", approved_quantity=10, remaining_quantity=10, estimated_unit_cost=5)],
	)
	exceptions: list[dict] = []

	monkeypatch.setattr(module, "_sum_issued_quantity", lambda *args, **kwargs: 4)
	monkeypatch.setattr(module, "_resolve_available_qty", lambda *args, **kwargs: 100)
	monkeypatch.setattr(module, "_resolve_item_cost", lambda *args, **kwargs: 5)
	monkeypatch.setattr(module.frappe, "get_all", lambda *args, **kwargs: [])

	def _capture_exception(**kwargs):
		exceptions.append(kwargs)
		return "EXC-003"

	monkeypatch.setattr(module, "_create_exception", _capture_exception)

	with pytest.raises(module.frappe.ValidationError) as excinfo:
		module._validate_issue_request(
			campaign,
			"SM Megamall - Bebang Enterprise Inc.",
			"ITEM-001",
			2,
			date(2026, 3, 18),
		)

	assert "daily cap exceeded" in str(excinfo.value).lower()
	assert exceptions[0]["exception_type"] == "Daily Cap Exceeded"


def test_validate_issue_request_blocks_value_tolerance_breach(monkeypatch):
	module = _load_module("marketing_giveaways_value_breach")
	campaign = FakeCampaignDoc(
		estimated_peso_value=100,
		approved_value_tolerance_pct=10,
		items=[FakeItemRow(item_code="ITEM-001", approved_quantity=10, remaining_quantity=10, estimated_unit_cost=10)],
	)
	exceptions: list[dict] = []

	monkeypatch.setattr(module, "_sum_issued_quantity", lambda *args, **kwargs: 0)
	monkeypatch.setattr(module, "_resolve_available_qty", lambda *args, **kwargs: 100)
	monkeypatch.setattr(module, "_resolve_item_cost", lambda *args, **kwargs: 20)
	monkeypatch.setattr(
		module.frappe,
		"get_all",
		lambda doctype, filters=None, fields=None, limit_page_length=None: [{"actual_total_cost": 95}]
		if doctype == module.ISSUE_DT
		else [],
	)

	def _capture_exception(**kwargs):
		exceptions.append(kwargs)
		return "EXC-004"

	monkeypatch.setattr(module, "_create_exception", _capture_exception)

	with pytest.raises(module.frappe.ValidationError) as excinfo:
		module._validate_issue_request(
			campaign,
			"SM Megamall - Bebang Enterprise Inc.",
			"ITEM-001",
			1,
			date(2026, 3, 18),
		)

	assert "value tolerance breached" in str(excinfo.value).lower()
	assert exceptions[0]["exception_type"] == "Value Tolerance Breach"
	assert exceptions[0]["attempted_value"] == 20


def test_post_campaign_giveaway_issue_returns_idempotent_replay(monkeypatch):
	module = _load_module("marketing_giveaways_idempotent", user_roles=["Store Supervisor"])
	existing_issue = types.SimpleNamespace(
		name="CGI-EXISTING-0001",
		status="Posted",
		stock_entry="STE-EXISTING-0001",
		actual_total_cost=37.5,
	)

	def _get_value(doctype, filters=None, fieldname=None, *args, **kwargs):
		if doctype == module.ISSUE_DT and isinstance(filters, dict) and filters.get("idempotency_key") == "dup-key":
			return existing_issue.name
		return None

	monkeypatch.setattr(module.frappe.db, "get_value", _get_value)
	monkeypatch.setattr(module, "_issue_doc", lambda name: existing_issue)

	result = module.post_campaign_giveaway_issue(
		campaign="CMP-0001",
		source_location="SM Megamall - Bebang Enterprise Inc.",
		item_code="ITEM-001",
		quantity=2,
		issue_date="2026-03-18",
		idempotency_key="dup-key",
	)

	assert result["success"] is True
	assert result["idempotent_replay"] is True
	assert result["issue"]["name"] == existing_issue.name
	assert result["issue"]["stock_entry"] == existing_issue.stock_entry


def test_post_campaign_giveaway_issue_posts_stock_entry_and_updates_campaign(monkeypatch):
	module = _load_module("marketing_giveaways_happy_path", user_roles=["Store Supervisor"])
	campaign = FakeCampaignDoc(
		items=[FakeItemRow(item_code="ITEM-001", item_name="Presidential", uom="Cup", approved_quantity=10, remaining_quantity=10, estimated_unit_cost=12.5)]
	)
	issue_doc = FakeIssueDoc()
	savepoints: list[str] = []
	commits: list[bool] = []

	def _get_value(doctype, filters=None, fieldname=None, *args, **kwargs):
		return None

	def _new_doc(doctype):
		assert doctype == module.ISSUE_DT
		return issue_doc

	monkeypatch.setattr(module.frappe.db, "get_value", _get_value)
	monkeypatch.setattr(module.frappe.db, "savepoint", lambda name: savepoints.append(name))
	monkeypatch.setattr(module.frappe.db, "rollback", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("rollback should not be called")))
	monkeypatch.setattr(module.frappe.db, "commit", lambda: commits.append(True))
	monkeypatch.setattr(module.frappe, "new_doc", _new_doc)
	monkeypatch.setattr(module, "_campaign_doc", lambda name: campaign)
	monkeypatch.setattr(
		module,
		"_validate_issue_request",
		lambda *args, **kwargs: (campaign.items[0], 12.5),
	)
	monkeypatch.setattr(module, "_post_stock_entry_for_issue", lambda campaign_doc, issue: "STE-0001")
	monkeypatch.setattr(module, "_update_campaign_tracking", lambda campaign_doc: 875.0)
	monkeypatch.setattr(module, "_serialize_campaign_row", lambda campaign_doc: {"name": campaign_doc.name, "status": campaign_doc.status})

	result = module.post_campaign_giveaway_issue(
		campaign=campaign.name,
		source_location="SM Megamall - Bebang Enterprise Inc.",
		item_code="ITEM-001",
		quantity=2,
		issue_date="2026-03-18",
		idempotency_key="happy-key",
		notes="Day 1 issue",
	)

	assert savepoints == [f"campaign_issue_{campaign.name.replace('-', '_')}"]
	assert commits == [True]
	assert issue_doc.insert_calls == 1
	assert issue_doc.save_calls == 1
	assert issue_doc.status == "Posted"
	assert issue_doc.actual_total_cost == 25.0
	assert issue_doc.finance_expense_account == campaign.finance_expense_account
	assert issue_doc.cost_center == campaign.cost_center
	assert issue_doc.budget_owner == campaign.budget_owner
	assert issue_doc.stock_entry == "STE-0001"
	assert result["success"] is True
	assert result["issue"]["stock_entry"] == "STE-0001"


def test_update_campaign_tracking_computes_multi_day_progress(monkeypatch):
	module = _load_module("marketing_giveaways_tracking_progress")
	campaign = FakeCampaignDoc(
		start_date="2026-03-15",
		end_date="2026-03-20",
		estimated_peso_value=500,
		total_approved_quantity=20,
		items=[
			FakeItemRow(item_code="ITEM-001", approved_quantity=12, remaining_quantity=12),
			FakeItemRow(item_code="ITEM-002", approved_quantity=8, remaining_quantity=8),
		],
	)

	def _get_all(doctype, filters=None, fields=None, limit_page_length=None):
		assert doctype == module.ISSUE_DT
		return [
			{"name": "CGI-0001", "issue_date": "2026-03-18", "item_code": "ITEM-001", "quantity": 5, "actual_total_cost": 60},
			{"name": "CGI-0002", "issue_date": "2026-03-19", "item_code": "ITEM-002", "quantity": 3, "actual_total_cost": 36},
		]

	monkeypatch.setattr(module.frappe, "get_all", _get_all)
	monkeypatch.setattr(module, "_manila_today", lambda: date(2026, 3, 18))

	remaining_value = module._update_campaign_tracking(campaign)

	assert campaign.status == "Partially Fulfilled"
	assert campaign.quantity_served == 8.0
	assert campaign.remaining_quantity == 12.0
	assert campaign.remaining_days == 3
	assert campaign.required_daily_pace == 4.0
	assert campaign.latest_issue_date == "2026-03-19"
	assert campaign.items[0].served_quantity == 5.0
	assert campaign.items[0].remaining_quantity == 7.0
	assert campaign.items[1].served_quantity == 3.0
	assert campaign.items[1].remaining_quantity == 5.0
	assert remaining_value == 404.0


def test_query_probable_giveaway_leakage_flags_marketing_and_effectively_free_orders(monkeypatch):
	module = _load_module("marketing_giveaways_leakage_query")
	order_queries: list[list[tuple[str, object]]] = []

	def _supabase_get(resource, params=None):
		if resource == "pos_orders":
			order_queries.append(list(params or []))
			return [
				{
					"id": 101,
					"location_id": 2338,
					"store_name": "SM Megamall",
					"business_date": "2026-03-18",
					"bill_number": "BILL-101",
					"original_gross_sales": 500.0,
					"total_discounts": 500.0,
					"payment_status": "PAID",
				},
				{
					"id": 102,
					"location_id": 2112,
					"store_name": "Ayala Solenad",
					"business_date": "2026-03-17",
					"bill_number": "BILL-102",
					"original_gross_sales": 300.0,
					"total_discounts": 290.0,
					"payment_status": "PAID",
				},
				{
					"id": 103,
					"location_id": 2339,
					"store_name": "Ayala Evo",
					"business_date": "2026-03-16",
					"bill_number": "BILL-103",
					"original_gross_sales": 400.0,
					"total_discounts": 20.0,
					"payment_status": "PAID",
				},
			]
		raise AssertionError(resource)

	def _supabase_get_all(resource, params=None, page_size=1000):
		if resource == "pos_order_items":
			return [
				{
					"order_id": 101,
					"product_name": "Presidential",
					"quantity": 200,
					"discount_amount": 500.0,
					"discount_name": "Marketing Discount 100%",
					"discount_name_normalized": "marketing discount 100%",
				},
				{
					"order_id": 102,
					"product_name": "Presidential",
					"quantity": 50,
					"discount_amount": 290.0,
					"discount_name": "Bulk Freebies",
					"discount_name_normalized": "bulk freebies",
				},
				{
					"order_id": 103,
					"product_name": "Halo-Halo",
					"quantity": 2,
					"discount_amount": 20.0,
					"discount_name": "Regular Promo",
					"discount_name_normalized": "regular promo",
				},
			]
		raise AssertionError(resource)

	monkeypatch.setattr(module, "_supabase_get", _supabase_get)
	monkeypatch.setattr(module, "_supabase_get_all", _supabase_get_all)
	monkeypatch.setattr(
		module.frappe,
		"get_all",
		lambda doctype, filters=None, fields=None, limit_page_length=None: [{"campaign": "CMP-0001", "status": "Linked"}]
		if doctype == module.EXCEPTION_DT and filters and filters.get("linked_alert_reference") == "pos-order:101"
		else [],
	)

	rows = module._query_probable_giveaway_leakage(date(2026, 3, 1), date(2026, 3, 18))

	assert [row["order_id"] for row in rows] == [101, 102]
	assert rows[0]["is_marketing_discount"] is True
	assert rows[0]["is_effectively_free"] is True
	assert rows[0]["linked_campaigns"] == [{"campaign": "CMP-0001", "status": "Linked"}]
	assert rows[1]["is_marketing_discount"] is False
	assert rows[1]["is_effectively_free"] is True
	assert order_queries, "pos_orders query was not issued"
	assert ("total_discounts", "gt.0") in order_queries[0]
	assert ("limit", str(module.LEAKAGE_CANDIDATE_ORDER_LIMIT)) in order_queries[0]
