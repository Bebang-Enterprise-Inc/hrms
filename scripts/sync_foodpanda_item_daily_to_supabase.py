#!/usr/bin/env python3
"""
Sync FoodPanda item-daily facts from Google Sheets into Supabase.

Source:
    SALES_FACT_ITEM_DAILY sheet in the canonical FoodPanda workbook.

Purpose:
    Populate full-channel cups sold for the sales dashboard using governed,
    store/day item totals instead of approximations.
"""

from __future__ import annotations

import argparse
import os
import subprocess
from collections import defaultdict
from datetime import date
from typing import Any

import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build

SERVICE_ACCOUNT_FILE = "credentials/task-manager-service.json"
GOOGLE_SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
GOOGLE_IMPERSONATE_USER = "sam@bebang.ph"
SPREADSHEET_ID = "1F9Zqn_5r42iLSWkHZqGaFr-a6-zXj5eOg52DJ3Oac78"
SHEET_NAME = "SALES_FACT_ITEM_DAILY"

SUPABASE_PROJECT_ID = "csnniykjrychgajfrgua"
SUPABASE_QUERY_URL = f"https://api.supabase.com/v1/projects/{SUPABASE_PROJECT_ID}/database/query"

STORE_LOCATION_MAP = {
	"Ayala Malls Fairview Terraces": 2220,
	"Ayala UPTC": 2425,
	"Ayala Vermosa": 2428,
	"BF Homes": 2217,
	"CTTM Tomas Morato": 2526,
	"Ever Commonwealth": 2281,
	"Festival Mall Alabang": 2222,
	"Lucky Chinatown": 2311,
	"Megawide PITX": 2179,
	"Megaworld Paseo Center": 2177,
	"Megaworld Venice Grand Canal": 2216,
	"Robinsons Antipolo": 2342,
	"SM Bicutan": 2412,
	"SM Caloocan": 2464,
	"SM Clark": 2646,
	"SM East Ortigas": 2184,
	"SM Grand Central": 2218,
	"SM Mall Of Asia": 2219,
	"SM Manila": 2339,
	"SM Marikina": 2317,
	"SM Marilao": 2413,
	"SM Megamall": 2338,
	"SM North EDSA": 2284,
	"SM Pulilan": 2478,
	"SM Sangandaan": 2482,
	"SM Southmall": 2340,
	"SM Tanza": 2411,
	"SM Valenzuela": 2341,
	"Sta. Lucia East Grand Mall": 2558,
	"The Grid - Rockwell": 2250,
	"The Terminal": 2319,
	"Vista Mall Taguig": 2556,
	"Up Town Mall BGC": 2548,
	"Araneta Gateway": 2557,
	"Ayala Evo": 2426,
	"Ayala Market Market": 2287,
	"Ayala Solenad": 2547,
	"D'Verde Calamba": 2766,
	"Robinson Imus": 2408,
	"Robinson General Trias": 2430,
	"Robinsons Galleria South": 2515,
	"SJDM": 2481,
	"Fairview Terraces": 2220,
	"UP Town Center": 2425,
	"CTTM": 2526,
	"Ever Gotesco": 2281,
	"Festival Mall": 2222,
	"Gateway Mall": 2557,
	"Chinatown": 2311,
	"Market Market": 2287,
	"Paseo De Roxas": 2177,
	"PITX": 2179,
	"Rob Imus": 2408,
	"Rob Gen Trias": 2430,
	"SM North": 2284,
	"Sta. Lucia": 2558,
	"NAIA": 2319,
	"Uptown Mall": 2548,
	"Venice Grand": 2216,
	"Rob Galleria South": 2515,
	"Terminal Alabang": 2319,
	"The Grid": 2250,
	"Vistamall Taguig": 2556,
	"Dverde Calamba": 2766,
	"SM MOA": 2219,
	"Rob Antipolo": 2342,
}


def get_management_token() -> str:
	token = os.environ.get("SUPABASE_MGMT_TOKEN")
	if token:
		return token.strip()
	return subprocess.check_output(
		[
			"doppler",
			"secrets",
			"get",
			"SUPABASE_MGMT_TOKEN",
			"--plain",
			"--project",
			"bei-erp",
			"--config",
			"dev",
		],
		text=True,
	).strip()


def execute_supabase_query(token: str, query: str) -> list[dict[str, Any]] | dict[str, Any]:
	response = requests.post(
		SUPABASE_QUERY_URL,
		headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
		json={"query": query},
		timeout=120,
	)
	response.raise_for_status()
	return response.json()


def get_sheets_service():
	credentials = service_account.Credentials.from_service_account_file(
		SERVICE_ACCOUNT_FILE,
		scopes=GOOGLE_SCOPES,
	).with_subject(os.environ.get("GOOGLE_IMPERSONATE_USER", GOOGLE_IMPERSONATE_USER))
	return build("sheets", "v4", credentials=credentials, cache_discovery=False)


def normalize_store_name(value: Any) -> str:
	name = str(value or "").strip()
	return " ".join(name.replace("’", "'").split())


def parse_float(value: Any) -> float:
	try:
		return float(value or 0)
	except (TypeError, ValueError):
		return 0.0


def build_date_filter(cli_args: argparse.Namespace) -> tuple[str | None, str | None]:
	if cli_args.date:
		return cli_args.date, cli_args.date
	return cli_args.start_date, cli_args.end_date


def extract_rows(start_date: str | None, end_date: str | None) -> list[dict[str, Any]]:
	service = get_sheets_service()
	result = (
		service.spreadsheets()
		.values()
		.get(
			spreadsheetId=SPREADSHEET_ID,
			range=f"'{SHEET_NAME}'!A2:K",
			valueRenderOption="UNFORMATTED_VALUE",
		)
		.execute()
	)
	values = result.get("values", [])
	if not values or len(values) < 2:
		return []

	headers = [str(cell).strip() for cell in values[0]]
	index = {header: idx for idx, header in enumerate(headers)}

	aggregates: dict[tuple[int, str], dict[str, Any]] = {}
	skipped_unmapped = 0
	skipped_dates = 0

	for raw_row in values[1:]:
		if not any(str(cell).strip() for cell in raw_row):
			continue

		def cell(header: str) -> str:
			col = index.get(header)
			return str(raw_row[col]).strip() if col is not None and col < len(raw_row) else ""

		business_date = cell("business_date")
		if not business_date:
			continue
		if start_date and business_date < start_date:
			skipped_dates += 1
			continue
		if end_date and business_date > end_date:
			skipped_dates += 1
			continue

		store_name = normalize_store_name(cell("store_name"))
		location_id = STORE_LOCATION_MAP.get(store_name)
		if not location_id:
			skipped_unmapped += 1
			continue

		qty_sold = round(parse_float(cell("qty_sold")))
		net_sales_amount = parse_float(cell("net_sales_amount"))
		source_mode = cell("source_mode") or "foodpanda_raw_item_lines"

		key = (location_id, business_date)
		bucket = aggregates.setdefault(
			key,
			{
				"location_id": location_id,
				"business_date": business_date,
				"qty_sold": 0,
				"net_sales_amount": 0.0,
				"source_mode": source_mode,
				"source_sheet": SHEET_NAME,
			},
		)
		bucket["qty_sold"] += qty_sold
		bucket["net_sales_amount"] += net_sales_amount
		if bucket["source_mode"] != source_mode:
			bucket["source_mode"] = "mixed"

	rows = sorted(aggregates.values(), key=lambda row: (row["business_date"], row["location_id"]))
	print(f"Extracted {len(rows)} location-day rows from {SHEET_NAME}")
	print(f"Skipped rows with unmapped stores: {skipped_unmapped}")
	print(f"Skipped rows outside target date filter: {skipped_dates}")
	return rows


def escape_text(value: Any) -> str:
	if value in (None, ""):
		return "NULL"
	return "'" + str(value).replace("'", "''") + "'"


def escape_num(value: Any) -> str:
	if value in (None, ""):
		return "NULL"
	return str(value)


def upsert_rows(token: str, rows: list[dict[str, Any]]) -> None:
	if not rows:
		print("No rows to upsert.")
		return

	batch_size = 500
	for batch_start in range(0, len(rows), batch_size):
		batch = rows[batch_start : batch_start + batch_size]
		values = []
		for row in batch:
			values.append(
				"("
				f"{escape_num(row['location_id'])},"
				f"{escape_text(row['business_date'])},"
				f"{escape_num(int(row['qty_sold']))},"
				f"{escape_num(round(float(row['net_sales_amount']), 2))},"
				f"{escape_text(row['source_sheet'])},"
				f"{escape_text(row['source_mode'])},"
				"NOW()"
				")"
			)

		query = f"""
        INSERT INTO public.foodpanda_daily_item_metrics (
            location_id,
            business_date,
            qty_sold,
            net_sales_amount,
            source_sheet,
            source_mode,
            synced_at
        )
        VALUES {",".join(values)}
        ON CONFLICT (location_id, business_date)
        DO UPDATE SET
            qty_sold = EXCLUDED.qty_sold,
            net_sales_amount = EXCLUDED.net_sales_amount,
            source_sheet = EXCLUDED.source_sheet,
            source_mode = EXCLUDED.source_mode,
            synced_at = NOW();
        """
		execute_supabase_query(token, query)
		batch_no = batch_start // batch_size + 1
		print(f"Upserted batch {batch_no} ({len(batch)} rows)")


def main() -> None:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--date", help="Sync a single YYYY-MM-DD business date")
	parser.add_argument("--start-date", help="Inclusive YYYY-MM-DD start date")
	parser.add_argument("--end-date", help="Inclusive YYYY-MM-DD end date")
	args = parser.parse_args()

	start_date, end_date = build_date_filter(args)
	if start_date and not end_date:
		end_date = start_date
	if end_date and not start_date:
		start_date = end_date

	if start_date:
		date.fromisoformat(start_date)
	if end_date:
		date.fromisoformat(end_date)

	rows = extract_rows(start_date, end_date)
	token = get_management_token()
	upsert_rows(token, rows)

	if rows:
		totals = defaultdict(int)
		for row in rows:
			totals["days"] += 1
			totals["cups"] += int(row["qty_sold"])
		print(f"Synced {totals['days']} store/day rows and {totals['cups']} cups.")


if __name__ == "__main__":
	main()
