import importlib.util
import pathlib
import sys
import types


class _FakeDB:
	def __init__(self, warehouse_rows):
		self.warehouse_rows = warehouse_rows
		self.set_calls = []

	def exists(self, doctype, filters=None):
		if doctype == "Warehouse":
			if isinstance(filters, str):
				return filters in self.warehouse_rows
			if isinstance(filters, dict):
				name = filters.get("name") or filters.get("warehouse_name")
				return bool(name and name in self.warehouse_rows)
		return False

	def get_single_value(self, *args, **kwargs):
		return None

	def get_value(self, doctype, filters_or_name, fieldname=None, as_dict=False):
		if doctype != "Warehouse":
			return None
		if isinstance(filters_or_name, dict):
			key = filters_or_name.get("name")
		else:
			key = filters_or_name
		row = self.warehouse_rows.get(key) or {}
		if isinstance(fieldname, list | tuple):
			payload = {field: row.get(field) for field in fieldname}
			return payload if as_dict else payload
		return row.get(fieldname)

	def set_value(self, doctype, name, fieldname, value, **kwargs):
		self.set_calls.append((doctype, name, fieldname, value))
		if doctype == "Warehouse" and name in self.warehouse_rows:
			self.warehouse_rows[name][fieldname] = value
		return value


def _install_stubs():
	warehouse_rows = {
		"AYALA EVO - BEI": {
			"name": "AYALA EVO - BEI",
			"warehouse_name": "AYALA EVO",
			"custom_area_supervisor": "store.supervisor@bebang.ph",
			"parent_warehouse": None,
		},
		"UNMAPPED - BEI": {
			"name": "UNMAPPED - BEI",
			"warehouse_name": "UNMAPPED",
			"custom_area_supervisor": None,
			"parent_warehouse": None,
		},
	}
	db = _FakeDB(warehouse_rows)

	role_map = {
		"store.supervisor@bebang.ph": ["Store Supervisor"],
		"area.supervisor@bebang.ph": ["Area Supervisor"],
		"sam@bebang.ph": ["Area Supervisor"],
		"test.area@bebang.ph": ["Area Supervisor"],
	}
	role_rows = [
		{"parent": "area.supervisor@bebang.ph", "role": "Area Supervisor"},
		{"parent": "sam@bebang.ph", "role": "Area Supervisor"},
		{"parent": "test.area@bebang.ph", "role": "Area Supervisor"},
	]
	user_rows = {
		"area.supervisor@bebang.ph": {"name": "area.supervisor@bebang.ph", "enabled": 1},
		"sam@bebang.ph": {"name": "sam@bebang.ph", "enabled": 1},
		"test.area@bebang.ph": {"name": "test.area@bebang.ph", "enabled": 1},
	}

	employees = [
		{
			"name": "EMP-SUP-001",
			"user_id": "store.supervisor@bebang.ph",
			"designation": "Store Supervisor",
			"branch": "AYALA EVO",
			"reports_to": "EMP-AREA-001",
		},
		{
			"name": "EMP-AREA-001",
			"user_id": "area.supervisor@bebang.ph",
			"designation": "Area Supervisor",
			"branch": "AYALA EVO",
			"reports_to": None,
		},
	]

	frappe = types.ModuleType("frappe")
	frappe.local = types.SimpleNamespace(
		db=db,
		session=types.SimpleNamespace(user="test.supervisor@bebang.ph"),
	)
	frappe.__dict__["db"] = db
	frappe.__dict__["session"] = frappe.local.session
	frappe.PermissionError = RuntimeError
	frappe.log_error = lambda *args, **kwargs: None
	frappe._ = lambda msg: msg
	frappe.throw = lambda msg, *args, **kwargs: (_ for _ in ()).throw(RuntimeError(msg))
	frappe.parse_json = lambda payload: payload
	frappe.get_meta = lambda _doctype: types.SimpleNamespace(has_field=lambda _field: False)
	frappe.get_roles = lambda user=None: role_map.get(user or "test.supervisor@bebang.ph", [])
	def _get_all(doctype, **kwargs):
		if doctype == "Employee":
			return employees
		if doctype == "Has Role":
			filters = kwargs.get("filters") or {}
			role = filters.get("role")
			if role:
				return [row for row in role_rows if row.get("role") == role]
			return list(role_rows)
		if doctype == "User":
			filters = kwargs.get("filters") or {}
			names_filter = filters.get("name")
			names = []
			if isinstance(names_filter, list) and len(names_filter) == 2 and names_filter[0] == "in":
				names = names_filter[1]
			elif isinstance(names_filter, str):
				names = [names_filter]
			enabled_required = filters.get("enabled")
			result = []
			for name in names:
				row = user_rows.get(name)
				if not row:
					continue
				if enabled_required is not None and int(row.get("enabled", 0)) != int(enabled_required):
					continue
				result.append({"name": row["name"]})
			return result
		return []

	frappe.get_all = _get_all
	frappe.whitelist = lambda fn=None, **kwargs: fn if fn else (lambda inner: inner)

	def _new_doc(_doctype):
		return types.SimpleNamespace(insert=lambda **kwargs: None)

	frappe.new_doc = _new_doc

	utils = types.ModuleType("frappe.utils")
	utils.nowdate = lambda: "2026-03-02"
	utils.add_days = lambda _d, _n: "2026-03-03"
	utils.now_datetime = lambda: "2026-03-02 10:00:00"
	utils.flt = lambda value, precision=None: float(value or 0)
	utils.cint = lambda value: int(float(value or 0))
	utils.getdate = lambda value=None: value or "2026-03-02"

	sys.modules["frappe"] = frappe
	sys.modules["frappe.utils"] = utils

	hrms_pkg = types.ModuleType("hrms")
	hrms_pkg.__path__ = []
	sys.modules["hrms"] = hrms_pkg

	utils_pkg = types.ModuleType("hrms.utils")
	utils_pkg.__path__ = []
	sys.modules["hrms.utils"] = utils_pkg

	bei_config = types.ModuleType("hrms.utils.bei_config")
	bei_config.get_company = lambda: "Bebang Enterprise Inc."
	sys.modules["hrms.utils.bei_config"] = bei_config

	scm_roles = types.ModuleType("hrms.utils.scm_roles")
	scm_roles.SCM_APPROVAL_ROLES = []
	scm_roles.check_scm_permission = lambda *args, **kwargs: None
	sys.modules["hrms.utils.scm_roles"] = scm_roles

	return db, warehouse_rows


def _load_store_module():
	db, warehouse_rows = _install_stubs()
	file_path = pathlib.Path(__file__).resolve().parents[1] / "api" / "store.py"
	spec = importlib.util.spec_from_file_location("s19_store_mapping_under_test", file_path)
	module = importlib.util.module_from_spec(spec)
	assert spec and spec.loader
	spec.loader.exec_module(module)
	return module, db, warehouse_rows


def test_invalid_store_supervisor_mapping_is_replaced_by_area_supervisor():
	store_mod, db, warehouse_rows = _load_store_module()

	approver = store_mod._get_area_supervisor_for_store("AYALA EVO - BEI")
	assert approver == "area.supervisor@bebang.ph"
	assert warehouse_rows["AYALA EVO - BEI"]["custom_area_supervisor"] == "area.supervisor@bebang.ph"
	assert any(
		call == ("Warehouse", "AYALA EVO - BEI", "custom_area_supervisor", "area.supervisor@bebang.ph")
		for call in db.set_calls
	)


def test_unmapped_store_returns_none_when_no_area_supervisor_can_be_inferred():
	store_mod, _db, _rows = _load_store_module()

	# Remove branch-linked area supervisor signals so inference cannot resolve.
	store_mod.frappe.get_all = (
		lambda doctype, **kwargs: [] if doctype in {"Employee", "Has Role", "User"} else []
	)

	approver = store_mod._get_area_supervisor_for_store("UNMAPPED - BEI")
	assert approver is None


def test_unmapped_store_uses_default_area_supervisor_fallback():
	store_mod, _db, _rows = _load_store_module()

	# Remove branch-linked employee signals; fallback should use default Area Supervisor role mapping.
	store_mod.frappe.get_all = (
		lambda doctype, **kwargs: []
		if doctype == "Employee"
		else (
			[
				{"parent": "test.area@bebang.ph", "role": "Area Supervisor"},
				{"parent": "sam@bebang.ph", "role": "Area Supervisor"},
			]
			if doctype == "Has Role"
			else [{"name": "test.area@bebang.ph"}, {"name": "sam@bebang.ph"}]
			if doctype == "User"
			else []
		)
	)

	approver = store_mod._get_area_supervisor_for_store("UNMAPPED - BEI")
	assert approver == "sam@bebang.ph"
