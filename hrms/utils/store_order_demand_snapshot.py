from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = REPO_ROOT / "hrms" / "fixtures" / "store_ordering"
COMPACT_CROSSWALK_PATH = FIXTURE_DIR / "bom_fg_to_pos_crosswalk_compact.csv"
COMPACT_BOM_PATH = FIXTURE_DIR / "bom_master_compact.csv"
PRODUCT_POLICY_PATH = FIXTURE_DIR / "store_order_product_policies.csv"
COMPONENT_RECIPE_PATH = FIXTURE_DIR / "store_order_component_recipes.csv"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "data" / "Big_Data_Refinery" / "_run_artifacts"

SUPABASE_URL_DEFAULT = "https://csnniykjrychgajfrgua.supabase.co"
SUPABASE_PROJECT_REF = "csnniykjrychgajfrgua"
SUPABASE_SQL_URL = f"https://api.supabase.com/v1/projects/{SUPABASE_PROJECT_REF}/database/query"
FOODPANDA_SPREADSHEET_ID = "1F9Zqn_5r42iLSWkHZqGaFr-a6-zXj5eOg52DJ3Oac78"
FOODPANDA_SHEET_NAME = "SALES_FACT_ITEM_DAILY"
GOOGLE_IMPERSONATE_USER_DEFAULT = "sam@bebang.ph"
GOOGLE_SHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

FG_NAME_ALIASES = {
	"BUKO FRUIT": "BUKO FRUIT SALAD",
	"HALUKAY UBE": "HALOKAY UBE",
	"MANGO GRAHAM": "MANGO GRAHAM CARAMEL",
	"SO CORNY!": "SO CORNY",
}


def _conf_get(key: str, default: Any = None) -> Any:
	try:
		import frappe  # type: ignore
	except Exception:
		return default

	conf = getattr(frappe, "conf", {}) or {}
	if hasattr(conf, "get"):
		return conf.get(key, default)
	return default


def _get_secret(env_name: str, doppler_name: str | None = None) -> str:
	value = os.environ.get(env_name, "").strip()
	if value:
		return value

	conf_value = _conf_get(env_name.lower(), "") or _conf_get(env_name, "")
	if isinstance(conf_value, str) and conf_value.strip():
		return conf_value.strip()

	doppler_key = doppler_name or env_name
	doppler_exe = shutil.which("doppler") or "C:/Users/Sam/bin/doppler.exe"
	if not Path(doppler_exe).exists() and doppler_exe != "doppler":
		raise RuntimeError(f"Missing required secret: {env_name}")

	try:
		result = subprocess.run(
			[
				doppler_exe,
				"secrets",
				"get",
				doppler_key,
				"--plain",
				"--project",
				"bei-erp",
				"--config",
				"dev",
			],
			capture_output=True,
			text=True,
			timeout=10,
			check=False,
		)
	except Exception as exc:
		raise RuntimeError(f"Missing required secret: {env_name}") from exc

	if result.returncode == 0 and result.stdout.strip():
		return result.stdout.strip()
	raise RuntimeError(f"Missing required secret: {env_name}")


def _get_optional_secret(env_name: str, doppler_name: str | None = None) -> str:
	try:
		return _get_secret(env_name, doppler_name)
	except RuntimeError:
		return ""


def _get_supabase_url() -> str:
	return (_get_secret("SUPABASE_URL") or SUPABASE_URL_DEFAULT).rstrip("/")


def _get_supabase_service_key() -> str:
	return _get_secret("SUPABASE_SERVICE_ROLE_KEY")


def _supabase_headers() -> dict[str, str]:
	key = _get_supabase_service_key()
	return {
		"apikey": key,
		"Authorization": f"Bearer {key}",
		"Content-Type": "application/json",
	}


def query_supabase(sql: str) -> list[dict[str, Any]]:
	token = _get_optional_secret("SUPABASE_MGMT_TOKEN", "SUPABASE_ACCESS_TOKEN")
	if not token:
		raise RuntimeError("SUPABASE_MGMT_TOKEN is not configured")

	response = requests.post(
		SUPABASE_SQL_URL,
		headers={
			"Authorization": f"Bearer {token}",
			"Content-Type": "application/json",
		},
		json={"query": sql},
		timeout=60,
	)
	response.raise_for_status()
	data = response.json()
	if isinstance(data, dict) and data.get("message"):
		raise RuntimeError(data["message"])
	return data


def _supabase_merge_params(
	params: dict[str, Any] | list[tuple[str, Any]] | None,
	extra: list[tuple[str, Any]],
) -> dict[str, Any] | list[tuple[str, Any]]:
	if params is None:
		return list(extra)
	if isinstance(params, dict):
		merged = dict(params)
		for key, value in extra:
			merged[key] = value
		return merged
	merged = [(key, value) for key, value in params if key not in {"limit", "offset"}]
	merged.extend(extra)
	return merged


def _supabase_get_all(
	resource: str,
	params: dict[str, Any] | list[tuple[str, Any]] | None = None,
	*,
	page_size: int = 5000,
) -> list[dict[str, Any]]:
	rows: list[dict[str, Any]] = []
	offset = 0

	while True:
		page_params = _supabase_merge_params(
			params,
			[("limit", str(page_size)), ("offset", str(offset))],
		)
		response = requests.get(
			f"{_get_supabase_url()}/rest/v1/{resource}",
			headers=_supabase_headers(),
			params=page_params,
			timeout=60,
		)
		if not response.ok:
			raise RuntimeError(
				f"Supabase GET failed for {resource}: {response.status_code} {response.text[:300]}"
			)

		payload = response.json()
		if not isinstance(payload, list):
			raise RuntimeError(f"Unexpected Supabase payload for {resource}")

		if not payload:
			break
		rows.extend(payload)
		offset += len(payload)

	return rows


def _get_service_account_path() -> str:
	env_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "").strip()
	if env_path and Path(env_path).exists():
		return env_path

	try:
		from hrms.utils.bei_config import get_service_account_path

		candidate = get_service_account_path()
		if candidate:
			return candidate
	except Exception:
		pass

	return str(REPO_ROOT / "credentials" / "task-manager-service.json")


def normalize_name(value: str) -> str:
	return "".join(char for char in str(value or "").upper() if char.isalnum())


def parse_float(value: Any) -> float:
	if value in (None, ""):
		return 0.0
	if isinstance(value, int | float):
		return float(value)
	text = str(value).strip().replace(",", "")
	if not text:
		return 0.0
	return float(text)


def parse_date_arg(value: str) -> date:
	return datetime.strptime(value, "%Y-%m-%d").date()


def _load_bom_catalog_from_frappe() -> tuple[dict[str, str], dict[str, str], dict[str, list[dict[str, Any]]]]:
	"""Load BOM catalog directly from Frappe BOM DocType (production SSOT).

	Returns the same three dicts as the CSV-based loader:
	  - fg_display_by_norm: normalized name -> display name
	  - crosswalk_by_norm: normalized POS name -> FG display name
	  - bom_rows_by_fg_norm: normalized name -> list of component dicts
	"""
	import frappe as _frappe

	fg_display_by_norm: dict[str, str] = {}
	crosswalk_by_norm: dict[str, str] = {}
	bom_rows_by_fg_norm: dict[str, list[dict[str, Any]]] = defaultdict(list)

	BEI = "Bebang Enterprise Inc."

	# POS name crosswalk: read from CSV config (maps POS display names to BOM names)
	# This is a stable configuration mapping, not runtime data.
	if COMPACT_CROSSWALK_PATH.exists():
		with COMPACT_CROSSWALK_PATH.open(encoding="utf-8-sig", newline="") as handle:
			for row in csv.DictReader(handle):
				fg_name = str(row.get("fg_name", "")).strip()
				fg_norm = normalize_name(row.get("fg_name_norm") or fg_name)
				pos_name = str(row.get("pos_item_name_top1", "")).strip()
				if fg_name and fg_norm:
					fg_display_by_norm.setdefault(fg_norm, fg_name)
				if fg_name and pos_name:
					crosswalk_by_norm[normalize_name(pos_name)] = fg_name

	# Fetch all active submitted MN-series BOMs (product BOMs under BEI)
	boms = _frappe.get_all(
		"BOM",
		filters={"item": ["like", "MN%"], "company": BEI, "is_active": 1, "docstatus": 1},
		fields=["name", "item", "item_name"],
		order_by="item asc",
	)

	for bom in boms:
		fg_name = (bom.item_name or "").strip().upper()
		if not fg_name:
			continue
		fg_norm = normalize_name(fg_name)
		fg_display_by_norm.setdefault(fg_norm, fg_name)
		# Also add BOM name as crosswalk entry (identity mapping for exact matches)
		crosswalk_by_norm.setdefault(fg_norm, fg_name)

		# Fetch child items
		items = _frappe.get_all(
			"BOM Item",
			filters={"parent": bom.name},
			fields=["item_code", "item_name", "qty"],
			order_by="idx asc",
		)
		for item in items:
			qty = parse_float(item.qty)
			if qty <= 0:
				continue
			bom_rows_by_fg_norm[fg_norm].append(
				{
					"component_item_code": item.item_code,
					"component_item_name": item.item_name or "",
					"qty_per_fg": qty,
				}
			)

	return fg_display_by_norm, crosswalk_by_norm, bom_rows_by_fg_norm


def _load_bom_catalog_from_csv() -> tuple[dict[str, str], dict[str, str], dict[str, list[dict[str, Any]]]]:
	"""Fallback: load BOM catalog from CSV fixtures (for local/offline use only)."""
	fg_display_by_norm: dict[str, str] = {}
	crosswalk_by_norm: dict[str, str] = {}
	bom_rows_by_fg_norm: dict[str, list[dict[str, Any]]] = defaultdict(list)

	with COMPACT_CROSSWALK_PATH.open(encoding="utf-8-sig", newline="") as handle:
		for row in csv.DictReader(handle):
			fg_name = str(row.get("fg_name", "")).strip()
			fg_norm = normalize_name(row.get("fg_name_norm") or fg_name)
			pos_name = str(row.get("pos_item_name_top1", "")).strip()
			if fg_name and fg_norm:
				fg_display_by_norm.setdefault(fg_norm, fg_name)
			if fg_name and pos_name:
				crosswalk_by_norm[normalize_name(pos_name)] = fg_name

	with COMPACT_BOM_PATH.open(encoding="utf-8-sig", newline="") as handle:
		for row in csv.DictReader(handle):
			fg_name = str(row.get("fg_name", "")).strip()
			fg_norm = normalize_name(row.get("fg_name_norm") or fg_name)
			component_item_code = str(row.get("component_item_code", "")).strip()
			component_item_name = str(row.get("component_item_name_bom", "")).strip()
			qty_per_fg = parse_float(row.get("qty_per_fg"))
			if not fg_name or not fg_norm or not component_item_code or qty_per_fg <= 0:
				continue
			fg_display_by_norm.setdefault(fg_norm, fg_name)
			bom_rows_by_fg_norm[fg_norm].append(
				{
					"component_item_code": component_item_code,
					"component_item_name": component_item_name,
					"qty_per_fg": qty_per_fg,
				}
			)

	return fg_display_by_norm, crosswalk_by_norm, bom_rows_by_fg_norm


def load_bom_catalog() -> tuple[dict[str, str], dict[str, str], dict[str, list[dict[str, Any]]]]:
	"""Load BOM catalog from Frappe DB (preferred) with CSV fallback for local/offline use."""
	try:
		import frappe as _frappe
		if _frappe.local and _frappe.local.site:
			return _load_bom_catalog_from_frappe()
	except Exception:
		pass
	return _load_bom_catalog_from_csv()


def load_product_policy_catalog() -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
	policies_by_code: dict[str, dict[str, str]] = {}
	policies_by_name: dict[str, dict[str, str]] = {}
	if not PRODUCT_POLICY_PATH.exists():
		return policies_by_code, policies_by_name

	with PRODUCT_POLICY_PATH.open(encoding="utf-8-sig", newline="") as handle:
		for row in csv.DictReader(handle):
			product_name = str(row.get("product_name", "")).strip()
			product_code = str(row.get("product_code", "")).strip()
			policy_type = str(row.get("policy_type", "")).strip()
			target_key = str(row.get("target_key", "")).strip()
			note = str(row.get("note", "")).strip()
			if not policy_type or not (product_name or product_code):
				continue
			policy = {
				"product_name": product_name,
				"product_code": product_code,
				"policy_type": policy_type,
				"target_key": target_key,
				"note": note,
			}
			if product_code:
				policies_by_code[product_code] = policy
			if product_name:
				policies_by_name[normalize_name(product_name)] = policy

	return policies_by_code, policies_by_name


def load_component_recipe_catalog() -> dict[str, list[dict[str, Any]]]:
	recipes_by_key: dict[str, list[dict[str, Any]]] = defaultdict(list)
	if not COMPONENT_RECIPE_PATH.exists():
		return recipes_by_key

	with COMPONENT_RECIPE_PATH.open(encoding="utf-8-sig", newline="") as handle:
		for row in csv.DictReader(handle):
			recipe_key = str(row.get("recipe_key", "")).strip()
			item_code = str(row.get("item_code", "")).strip()
			item_name = str(row.get("item_name", "")).strip()
			qty_per_unit = parse_float(row.get("qty_per_unit"))
			note = str(row.get("note", "")).strip()
			if not recipe_key or not item_code or qty_per_unit <= 0:
				continue
			recipes_by_key[recipe_key].append(
				{
					"component_item_code": item_code,
					"component_item_name": item_name,
					"qty_per_fg": qty_per_unit,
					"note": note,
				}
			)

	return recipes_by_key


def resolve_fg_name(
	product_name: str,
	fg_display_by_norm: dict[str, str],
	crosswalk_by_norm: dict[str, str],
) -> tuple[str | None, str]:
	raw = str(product_name or "").strip()
	norm = normalize_name(raw)
	if not norm:
		return None, ""

	alias_norm = normalize_name(FG_NAME_ALIASES.get(raw.upper(), ""))
	if alias_norm and alias_norm in fg_display_by_norm:
		return fg_display_by_norm[alias_norm], "explicit_alias"

	if norm in fg_display_by_norm:
		return fg_display_by_norm[norm], "exact_fg"

	if norm in crosswalk_by_norm:
		return crosswalk_by_norm[norm], "crosswalk_top1"

	return None, ""


def resolve_product_mapping(
	product_name: str,
	product_code: str,
	fg_display_by_norm: dict[str, str],
	crosswalk_by_norm: dict[str, str],
	policies_by_code: dict[str, dict[str, str]],
	policies_by_name: dict[str, dict[str, str]],
	component_recipes_by_key: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
	raw_name = str(product_name or "").strip()
	raw_code = str(product_code or "").strip()
	norm_name = normalize_name(raw_name)

	policy = None
	if raw_code and raw_code in policies_by_code:
		policy = policies_by_code[raw_code]
	elif norm_name and norm_name in policies_by_name:
		policy = policies_by_name[norm_name]

	if policy:
		policy_type = policy["policy_type"]
		target_key = policy["target_key"]
		if policy_type == "exclude":
			return {
				"status": "excluded",
				"target_type": "exclude",
				"target_key": target_key,
				"mapping_method": "explicit_exclusion",
				"note": policy["note"],
				"component_rows": [],
			}
		if policy_type == "component_recipe":
			component_rows = component_recipes_by_key.get(target_key, [])
			if not component_rows:
				raise RuntimeError(
					f"Policy for {raw_name or raw_code} references missing component recipe: {target_key}"
				)
			return {
				"status": "mapped",
				"target_type": "component_recipe",
				"target_key": target_key,
				"mapping_method": "explicit_component_recipe",
				"note": policy["note"],
				"component_rows": component_rows,
			}
		if policy_type == "fg_recipe":
			target_norm = normalize_name(target_key)
			if target_norm not in fg_display_by_norm:
				raise RuntimeError(
					f"Policy for {raw_name or raw_code} references missing FG recipe: {target_key}"
				)
			return {
				"status": "mapped",
				"target_type": "fg_recipe",
				"target_key": fg_display_by_norm[target_norm],
				"mapping_method": "explicit_fg_recipe",
				"note": policy["note"],
				"component_rows": [],
			}
		raise RuntimeError(f"Unsupported policy type: {policy_type}")

	fg_name, mapping_method = resolve_fg_name(
		raw_name,
		fg_display_by_norm=fg_display_by_norm,
		crosswalk_by_norm=crosswalk_by_norm,
	)
	if fg_name:
		return {
			"status": "mapped",
			"target_type": "fg_recipe",
			"target_key": fg_name,
			"mapping_method": mapping_method,
			"note": "",
			"component_rows": [],
		}

	return {
		"status": "unmapped",
		"target_type": "",
		"target_key": "",
		"mapping_method": "unmapped",
		"note": "",
		"component_rows": [],
	}


def _fetch_channel_product_rows_via_rest(
	*,
	resource: str,
	order_resource: str,
	order_status_field: str,
	order_status_value: str,
	channel: str,
	start_date: date,
	end_date: date,
) -> list[dict[str, Any]]:
	select = (
		"quantity,product_id,product_name,net_sales,"
		f"order:{order_resource}!inner("
		f"business_date,location_id,{order_status_field},"
		"store:stores(location_id,store_name)"
		")"
	)
	params: list[tuple[str, Any]] = [
		("select", select),
		("order.business_date", f"gte.{start_date.isoformat()}"),
		("order.business_date", f"lte.{end_date.isoformat()}"),
		(f"order.{order_status_field}", f"eq.{order_status_value}"),
	]
	rows = _supabase_get_all(resource, params)

	normalized_rows: list[dict[str, Any]] = []
	for row in rows:
		order = row.get("order") or {}
		store = order.get("store") or {}
		business_date = str(order.get("business_date") or "").strip()
		location_id = order.get("location_id")
		store_name = str(store.get("store_name") or f"Location {location_id or ''}").strip()
		if not business_date or not store_name:
			continue
		normalized_rows.append(
			{
				"business_date": business_date,
				"channel": channel,
				"store_name": store_name,
				"store_code": str(location_id or "").strip(),
				"product_code": str(row.get("product_id") or "").strip(),
				"product_name": str(row.get("product_name") or "").strip(),
				"qty_sold": parse_float(row.get("quantity")),
				"net_sales_amount": parse_float(row.get("net_sales")),
			}
		)

	return normalized_rows


def _fetch_pos_web_product_rows_via_rest(start_date: date, end_date: date) -> list[dict[str, Any]]:
	combined_rows = _fetch_channel_product_rows_via_rest(
		resource="pos_order_items",
		order_resource="pos_orders",
		order_status_field="payment_status",
		order_status_value="PAID",
		channel="POS",
		start_date=start_date,
		end_date=end_date,
	) + _fetch_channel_product_rows_via_rest(
		resource="web_order_items",
		order_resource="web_orders",
		order_status_field="order_status_raw",
		order_status_value="Completed",
		channel="Web",
		start_date=start_date,
		end_date=end_date,
	)

	grouped: dict[tuple[str, str, str, str, str, str], dict[str, Any]] = {}
	for row in combined_rows:
		key = (
			row["business_date"],
			row["channel"],
			row["store_name"],
			row["store_code"],
			row["product_code"],
			row["product_name"],
		)
		if key not in grouped:
			grouped[key] = {
				**row,
				"qty_sold": 0.0,
				"net_sales_amount": 0.0,
			}
		grouped[key]["qty_sold"] += parse_float(row.get("qty_sold"))
		grouped[key]["net_sales_amount"] += parse_float(row.get("net_sales_amount"))

	return sorted(
		grouped.values(),
		key=lambda row: (
			row["business_date"],
			row["channel"],
			row["store_name"],
			row["product_name"],
		),
	)


def _fetch_pos_web_product_rows_via_sql(start_date: date, end_date: date) -> list[dict[str, Any]]:
	sql = f"""
WITH pos AS (
    SELECT
        o.business_date,
        'POS' AS channel,
        COALESCE(s.store_name, CAST(o.location_id AS text)) AS store_name,
        CAST(o.location_id AS text) AS store_code,
        CAST(oi.product_id AS text) AS product_code,
        oi.product_name AS product_name,
        SUM(oi.quantity) AS qty_sold,
        SUM(oi.net_sales) AS net_sales_amount
    FROM pos_order_items oi
    INNER JOIN pos_orders o ON o.id = oi.order_id
    LEFT JOIN stores s ON s.location_id = o.location_id
    WHERE o.payment_status = 'PAID'
      AND o.business_date BETWEEN '{start_date.isoformat()}' AND '{end_date.isoformat()}'
    GROUP BY o.business_date, o.location_id, s.store_name, oi.product_id, oi.product_name
),
web AS (
    SELECT
        o.business_date,
        'Web' AS channel,
        COALESCE(s.store_name, CAST(o.location_id AS text)) AS store_name,
        CAST(o.location_id AS text) AS store_code,
        CAST(oi.product_id AS text) AS product_code,
        oi.product_name AS product_name,
        SUM(oi.quantity) AS qty_sold,
        SUM(oi.net_sales) AS net_sales_amount
    FROM web_order_items oi
    INNER JOIN web_orders o ON o.id = oi.order_id
    LEFT JOIN stores s ON s.location_id = o.location_id
    WHERE o.order_status_raw = 'Completed'
      AND o.business_date BETWEEN '{start_date.isoformat()}' AND '{end_date.isoformat()}'
    GROUP BY o.business_date, o.location_id, s.store_name, oi.product_id, oi.product_name
)
SELECT * FROM pos
UNION ALL
SELECT * FROM web
ORDER BY business_date, channel, store_name, product_name;
"""
	return query_supabase(sql)


def fetch_pos_web_product_rows(start_date: date, end_date: date) -> list[dict[str, Any]]:
	mgmt_token = _get_optional_secret("SUPABASE_MGMT_TOKEN", "SUPABASE_ACCESS_TOKEN")
	if mgmt_token:
		return _fetch_pos_web_product_rows_via_sql(start_date, end_date)
	return _fetch_pos_web_product_rows_via_rest(start_date, end_date)


def load_foodpanda_product_rows() -> list[dict[str, Any]]:
	from google.oauth2 import service_account
	from googleapiclient.discovery import build

	credentials = service_account.Credentials.from_service_account_file(
		_get_service_account_path(),
		scopes=GOOGLE_SHEETS_SCOPES,
	).with_subject(os.environ.get("GOOGLE_IMPERSONATE_USER", GOOGLE_IMPERSONATE_USER_DEFAULT))

	service = build("sheets", "v4", credentials=credentials, cache_discovery=False)
	result = (
		service.spreadsheets()
		.values()
		.get(
			spreadsheetId=FOODPANDA_SPREADSHEET_ID,
			range=f"'{FOODPANDA_SHEET_NAME}'!A2:K",
			valueRenderOption="UNFORMATTED_VALUE",
		)
		.execute()
	)
	values = result.get("values", [])
	if not values:
		return []

	headers = [str(cell).strip() for cell in values[0]]
	index = {header: idx for idx, header in enumerate(headers)}
	rows: list[dict[str, Any]] = []

	for raw_row in values[1:]:
		if not any(str(cell).strip() for cell in raw_row):
			continue

		def _cell(header: str) -> str:
			col = index.get(header)
			return str(raw_row[col]).strip() if col is not None and col < len(raw_row) else ""

		rows.append(
			{
				"business_date": _cell("business_date"),
				"channel": "FoodPanda",
				"store_name": _cell("store_name"),
				"store_code": _cell("store_code"),
				"product_code": _cell("product_code"),
				"product_name": _cell("canonical_product_name"),
				"qty_sold": parse_float(_cell("qty_sold")),
				"net_sales_amount": parse_float(_cell("net_sales_amount")),
			}
		)

	return rows


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	with path.open("w", encoding="utf-8", newline="") as handle:
		writer = csv.DictWriter(handle, fieldnames=fieldnames)
		writer.writeheader()
		writer.writerows(rows)


def _build_store_warehouse_map() -> dict[str, str]:
	"""Load store_name → Frappe warehouse DocName.

	Uses Frappe DB when available (production), falls back to registry CSV (local).
	The registry CSV docnames may have wrong company suffixes — Frappe DB is authoritative.
	"""
	mapping: dict[str, str] = {}

	# Try Frappe DB first (authoritative — handles BEI vs Bebang Enterprise Inc. suffix)
	try:
		import frappe as _frappe
		if _frappe.local and _frappe.local.site:
			warehouses = _frappe.get_all(
				"Warehouse",
				filters={"is_group": 0},
				fields=["name", "warehouse_name"],
				limit_page_length=200,
			)
			for wh in warehouses:
				# Map warehouse_name → DocName (e.g., "Araneta Gateway" → "Araneta Gateway - BEI")
				if wh.warehouse_name:
					mapping[wh.warehouse_name] = wh.name
				# Also map DocName → DocName (identity, for pre-resolved values)
				mapping[wh.name] = wh.name
	except Exception:
		pass

	# Fallback: registry CSV (for local/offline use)
	if not mapping:
		registry_path = FIXTURE_DIR.parent / "store_inventory_shadow_sync" / "store_inventory_shadow_sync_registry.csv"
		if registry_path.exists():
			with registry_path.open(encoding="utf-8-sig", newline="") as f:
				for row in csv.DictReader(f):
					store_name = (row.get("store_name") or "").strip()
					warehouse_name = (row.get("warehouse_name") or "").strip()
					docname = (row.get("warehouse_docname") or "").strip()
					if store_name and docname:
						mapping[store_name] = docname
					if warehouse_name and docname and warehouse_name != store_name:
						mapping[warehouse_name] = docname

	# POS store names that differ from Frappe warehouse_name
	pos_aliases = {
		"D'Verde Calamba": "D'verde Laguna",
		"NAIA Terminal 3": "NAIA T3",
		"Robinsons Galleria South": "Robisons Galleria South",
		"SM San Pablo": "SM San Pablo",
	}
	for alias, wh_name in pos_aliases.items():
		if alias not in mapping and wh_name in mapping:
			mapping[alias] = mapping[wh_name]
		elif alias not in mapping:
			# Try with common suffixes
			for suffix in [" - BEI", " - Bebang Enterprise Inc.", " - BKI"]:
				candidate = wh_name + suffix
				if candidate in mapping:
					mapping[alias] = candidate
					break

	return mapping


def build_outputs(snapshot_date: date, lookback_days: int) -> dict[str, Any]:
	start_date = snapshot_date - timedelta(days=lookback_days)
	end_date = snapshot_date - timedelta(days=1)

	fg_display_by_norm, crosswalk_by_norm, bom_rows_by_fg_norm = load_bom_catalog()
	policies_by_code, policies_by_name = load_product_policy_catalog()
	component_recipes_by_key = load_component_recipe_catalog()
	store_warehouse_map = _build_store_warehouse_map()
	pos_web_rows = fetch_pos_web_product_rows(start_date, end_date)
	foodpanda_rows = [
		row
		for row in load_foodpanda_product_rows()
		if start_date.isoformat() <= str(row.get("business_date")) <= end_date.isoformat()
	]

	product_daily_rows: list[dict[str, Any]] = []
	excluded_rows: list[dict[str, Any]] = []
	unmapped_rows: list[dict[str, Any]] = []
	mapping_audit_map: dict[tuple[str, str, str, str, str, str], dict[str, Any]] = {}
	item_daily_map: dict[tuple[str, str, str, str], dict[str, Any]] = {}
	snapshot_map: dict[tuple[str, str], dict[str, Any]] = {}

	all_product_rows = list(pos_web_rows) + list(foodpanda_rows)
	for row in all_product_rows:
		store_name = str(row.get("store_name") or "").strip()
		product_name = str(row.get("product_name") or "").strip()
		business_date = str(row.get("business_date") or "").strip()
		channel = str(row.get("channel") or "").strip()
		store_code = str(row.get("store_code") or "").strip()
		product_code = str(row.get("product_code") or "").strip()
		qty_sold = parse_float(row.get("qty_sold"))
		net_sales_amount = parse_float(row.get("net_sales_amount"))
		if not store_name or not product_name or not business_date or qty_sold <= 0:
			continue

		mapping = resolve_product_mapping(
			product_name,
			product_code=product_code,
			fg_display_by_norm=fg_display_by_norm,
			crosswalk_by_norm=crosswalk_by_norm,
			policies_by_code=policies_by_code,
			policies_by_name=policies_by_name,
			component_recipes_by_key=component_recipes_by_key,
		)
		audit_key = (
			product_name,
			product_code,
			mapping["status"],
			mapping["target_type"],
			mapping["target_key"],
			mapping["mapping_method"],
		)
		if audit_key not in mapping_audit_map:
			mapping_audit_map[audit_key] = {
				"product_name": product_name,
				"product_code": product_code,
				"resolution_status": mapping["status"],
				"target_type": mapping["target_type"],
				"target_key": mapping["target_key"],
				"mapping_method": mapping["mapping_method"],
				"mapping_note": mapping["note"],
				"row_count": 0,
				"qty_sold_total": 0.0,
				"net_sales_amount_total": 0.0,
				"channels": set(),
				"stores": set(),
			}
		audit_row = mapping_audit_map[audit_key]
		audit_row["row_count"] += 1
		audit_row["qty_sold_total"] += qty_sold
		audit_row["net_sales_amount_total"] += net_sales_amount
		audit_row["channels"].add(channel)
		audit_row["stores"].add(store_name)

		if mapping["status"] == "excluded":
			excluded_rows.append(
				{
					"business_date": business_date,
					"channel": channel,
					"store_name": store_name,
					"store_code": store_code,
					"product_name": product_name,
					"product_code": product_code,
					"qty_sold": round(qty_sold, 4),
					"net_sales_amount": round(net_sales_amount, 2),
					"mapping_method": mapping["mapping_method"],
					"exclusion_reason": mapping["target_key"],
					"mapping_note": mapping["note"],
				}
			)
			continue

		if mapping["status"] != "mapped":
			unmapped_rows.append(
				{
					"business_date": business_date,
					"channel": channel,
					"store_name": store_name,
					"store_code": store_code,
					"product_name": product_name,
					"product_code": product_code,
					"qty_sold": round(qty_sold, 4),
					"net_sales_amount": round(net_sales_amount, 2),
					"mapping_method": mapping["mapping_method"],
					"mapping_note": mapping["note"],
				}
			)
			continue

		target_key = mapping["target_key"]
		target_type = mapping["target_type"]
		product_daily_rows.append(
			{
				"business_date": business_date,
				"channel": channel,
				"store_name": store_name,
				"store_code": store_code,
				"product_name": product_name,
				"product_code": product_code,
				"fg_name": target_key if target_type == "fg_recipe" else "",
				"component_recipe_key": target_key if target_type == "component_recipe" else "",
				"target_type": target_type,
				"target_key": target_key,
				"qty_sold": round(qty_sold, 4),
				"net_sales_amount": round(net_sales_amount, 2),
				"mapping_method": mapping["mapping_method"],
				"mapping_note": mapping["note"],
			}
		)

		component_rows = list(mapping["component_rows"])
		if target_type == "fg_recipe":
			component_rows = bom_rows_by_fg_norm.get(normalize_name(target_key), [])
		if not component_rows:
			# No BOM rows for this product — treat as unmapped (crosswalk entry without BOM)
			unmapped_rows.append(
				{
					"business_date": business_date,
					"channel": channel,
					"store_name": store_name,
					"store_code": store_code,
					"product_code": product_code,
					"product_name": product_name,
					"qty_sold": qty_sold,
					"net_sales_amount": net_sales_amount,
					"mapping_method": f"no_bom_components:{target_key}",
					"mapping_note": f"Crosswalk mapped to {target_key} but no BOM rows found",
				}
			)
			continue

		for bom_row in component_rows:
			item_code = bom_row["component_item_code"]
			component_item_name = bom_row["component_item_name"]
			demand_qty = qty_sold * bom_row["qty_per_fg"]
			item_key = (business_date, store_name, channel, item_code)
			if item_key not in item_daily_map:
				item_daily_map[item_key] = {
					"business_date": business_date,
					"store_name": store_name,
					"channel": channel,
					"item_code": item_code,
					"item_name": component_item_name,
					"demand_qty": 0.0,
					"source_targets": set(),
				}
			item_daily_map[item_key]["demand_qty"] += demand_qty
			item_daily_map[item_key]["source_targets"].add(target_key)

			resolved_warehouse = store_warehouse_map.get(
				store_name, f"{store_name} - Bebang Enterprise Inc."
			)
			snapshot_key = (resolved_warehouse, item_code)
			if snapshot_key not in snapshot_map:
				snapshot_map[snapshot_key] = {
					"snapshot_date": snapshot_date.isoformat(),
					"warehouse": resolved_warehouse,
					"item_code": item_code,
					"item_name": component_item_name,
					"total_demand_window": 0.0,
					"channels": set(),
					"source_targets": set(),
					"days_with_sales": set(),
				}
			snapshot_row = snapshot_map[snapshot_key]
			snapshot_row["total_demand_window"] += demand_qty
			snapshot_row["channels"].add(channel)
			snapshot_row["source_targets"].add(target_key)
			snapshot_row["days_with_sales"].add(business_date)

	item_daily_rows: list[dict[str, Any]] = []
	for item_key in sorted(item_daily_map):
		row = item_daily_map[item_key]
		item_daily_rows.append(
			{
				"business_date": row["business_date"],
				"store_name": row["store_name"],
				"channel": row["channel"],
				"item_code": row["item_code"],
				"item_name": row["item_name"],
				"demand_qty": round(row["demand_qty"], 6),
				"source_targets": " | ".join(sorted(row["source_targets"])),
			}
		)

	snapshot_rows: list[dict[str, Any]] = []
	for snapshot_key in sorted(snapshot_map):
		row = snapshot_map[snapshot_key]
		avg_daily_demand = row["total_demand_window"] / float(lookback_days)
		source_reference = {
			"days_with_sales": len(row["days_with_sales"]),
			"source_targets": sorted(row["source_targets"]),
			"total_demand_window": round(row["total_demand_window"], 6),
		}
		snapshot_rows.append(
			{
				"snapshot_date": row["snapshot_date"],
				"warehouse": row["warehouse"],
				"item_code": row["item_code"],
				"avg_daily_demand": round(avg_daily_demand, 6),
				"projected_sales": 0,
				"bom_consumption": round(avg_daily_demand, 6),
				"lookback_days": lookback_days,
				"signal_source": "sales_bom_snapshot",
				"channel_mix": ",".join(sorted(row["channels"])),
				"source_reference": json.dumps(source_reference, sort_keys=True),
			}
		)

	mapping_audit_rows: list[dict[str, Any]] = []
	for audit_key in sorted(mapping_audit_map):
		row = mapping_audit_map[audit_key]
		mapping_audit_rows.append(
			{
				"product_name": row["product_name"],
				"product_code": row["product_code"],
				"resolution_status": row["resolution_status"],
				"target_type": row["target_type"],
				"target_key": row["target_key"],
				"mapping_method": row["mapping_method"],
				"mapping_note": row["mapping_note"],
				"row_count": row["row_count"],
				"qty_sold_total": round(row["qty_sold_total"], 4),
				"net_sales_amount_total": round(row["net_sales_amount_total"], 2),
				"channel_mix": ",".join(sorted(row["channels"])),
				"store_count": len(row["stores"]),
			}
		)

	return {
		"start_date": start_date.isoformat(),
		"end_date": end_date.isoformat(),
		"product_daily_rows": sorted(
			product_daily_rows,
			key=lambda row: (
				row["business_date"],
				row["channel"],
				row["store_name"],
				row["target_key"],
			),
		),
		"item_daily_rows": item_daily_rows,
		"snapshot_rows": sorted(
			snapshot_rows,
			key=lambda row: (row["warehouse"], row["item_code"]),
		),
		"mapping_audit_rows": mapping_audit_rows,
		"excluded_rows": sorted(
			excluded_rows,
			key=lambda row: (
				row["business_date"],
				row["channel"],
				row["store_name"],
				row["product_name"],
			),
		),
		"unmapped_rows": sorted(
			unmapped_rows,
			key=lambda row: (
				row["business_date"],
				row["channel"],
				row["store_name"],
				row["product_name"],
			),
		),
	}


def main() -> int:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--snapshot-date", default=date.today().isoformat(), help="As-of date (YYYY-MM-DD)")
	parser.add_argument("--lookback-days", type=int, default=28, help="Trailing demand window in days")
	parser.add_argument(
		"--output-dir",
		default="",
		help="Optional absolute or relative output directory. Defaults to a dated run-artifact folder.",
	)
	args = parser.parse_args()

	snapshot_date = parse_date_arg(args.snapshot_date)
	if args.lookback_days <= 0:
		raise SystemExit("--lookback-days must be positive")

	output_dir = (
		Path(args.output_dir)
		if args.output_dir
		else DEFAULT_OUTPUT_ROOT / f"{snapshot_date.isoformat()}_store_order_demand_snapshot"
	)
	if not output_dir.is_absolute():
		output_dir = (REPO_ROOT / output_dir).resolve()

	outputs = build_outputs(snapshot_date=snapshot_date, lookback_days=args.lookback_days)

	write_csv(
		output_dir / "store_product_daily_demand.csv",
		[
			"business_date",
			"channel",
			"store_name",
			"store_code",
			"product_name",
			"product_code",
			"fg_name",
			"component_recipe_key",
			"target_type",
			"target_key",
			"qty_sold",
			"net_sales_amount",
			"mapping_method",
			"mapping_note",
		],
		outputs["product_daily_rows"],
	)
	write_csv(
		output_dir / "store_item_daily_demand.csv",
		[
			"business_date",
			"store_name",
			"channel",
			"item_code",
			"item_name",
			"demand_qty",
			"source_targets",
		],
		outputs["item_daily_rows"],
	)
	write_csv(
		output_dir / "store_demand_snapshot.csv",
		[
			"snapshot_date",
			"warehouse",
			"item_code",
			"avg_daily_demand",
			"projected_sales",
			"bom_consumption",
			"lookback_days",
			"signal_source",
			"channel_mix",
			"source_reference",
		],
		outputs["snapshot_rows"],
	)
	write_csv(
		output_dir / "store_product_mapping_audit.csv",
		[
			"product_name",
			"product_code",
			"resolution_status",
			"target_type",
			"target_key",
			"mapping_method",
			"mapping_note",
			"row_count",
			"qty_sold_total",
			"net_sales_amount_total",
			"channel_mix",
			"store_count",
		],
		outputs["mapping_audit_rows"],
	)
	write_csv(
		output_dir / "store_demand_excluded_products.csv",
		[
			"business_date",
			"channel",
			"store_name",
			"store_code",
			"product_name",
			"product_code",
			"qty_sold",
			"net_sales_amount",
			"mapping_method",
			"exclusion_reason",
			"mapping_note",
		],
		outputs["excluded_rows"],
	)
	write_csv(
		output_dir / "store_demand_unmapped_products.csv",
		[
			"business_date",
			"channel",
			"store_name",
			"store_code",
			"product_name",
			"product_code",
			"qty_sold",
			"net_sales_amount",
			"mapping_method",
			"mapping_note",
		],
		outputs["unmapped_rows"],
	)

	summary = {
		"snapshot_date": snapshot_date.isoformat(),
		"lookback_days": args.lookback_days,
		"start_date": outputs["start_date"],
		"end_date": outputs["end_date"],
		"product_daily_rows": len(outputs["product_daily_rows"]),
		"item_daily_rows": len(outputs["item_daily_rows"]),
		"snapshot_rows": len(outputs["snapshot_rows"]),
		"mapping_audit_rows": len(outputs["mapping_audit_rows"]),
		"excluded_products": len(outputs["excluded_rows"]),
		"unmapped_products": len(outputs["unmapped_rows"]),
		"output_dir": str(output_dir),
	}
	(output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

	print(json.dumps(summary, indent=2))
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
