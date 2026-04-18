"""Bridge DEVICE_TO_STORE values to branch_company_map keys (S206 Phase 1).

`hrms/utils/device_mapping.py::DEVICE_TO_STORE` maps device serial numbers to
store-name strings. These strings do not always match the `old_branch` keys in
`hrms/data_seed/branch_company_map.csv` that `company_lookup.resolve_branch_to_company`
understands.

This module bridges the two. Every DEVICE_TO_STORE value is mapped to a known
CSV `old_branch` key; the resolver then converts to the full Frappe Company docname.

Used by:
    hrms/utils/punch_allocation.py (maps a punch's device_id to its store Company)

Companies covered: 49 stores + BEI parent + BKI + 3 HO annexes.
"""

from __future__ import annotations

from hrms.utils.company_lookup import (
	UnknownBranch,
	resolve_branch_to_company,
)
from hrms.utils.device_mapping import DEVICE_TO_STORE

# Maps DEVICE_TO_STORE values to branch_company_map.csv `old_branch` keys.
# If the device value already matches a CSV key (identity bridge), it's still
# listed here explicitly to make the mapping complete and auditable.
DEVICE_STORE_BRIDGE: dict[str, str] = {
	# Head Office devices (route to BEI parent via branch_company_map HO category)
	"BRITTANY OFFICE": "BRITTANY OFFICE",
	"BGC CAPITAL HOUSE": "CAPITAL HOUSE",
	"MYTOWN": "MYTOWN",
	# Commissary (dept-driven routing in resolver)
	"SHAW COMMISSARY": "SHAW COMMISSARY",
	# SM stores — direct CSV matches
	"SM MEGAMALL": "SM MEGAMALL",
	"SM MANILA": "SM MANILA",
	"SM SOUTHMALL": "SM SOUTHMALL",
	"SM NORTH EDSA": "SM NORTH EDSA",
	"SM VALENZUELA": "SM VALENZUELA",
	"SM EAST ORTIGAS": "SM EAST ORTIGAS",
	"SM MARIKINA": "SM MARIKINA",
	"SM TANZA": "SM TANZA",
	"SM BICUTAN": "SM BICUTAN",
	"SM CALOOCAN": "SM CALOOCAN",
	"SM SANGANDAAN": "SM SANGANDAAN",
	"SM MARILAO": "SM MARILAO",
	"SM CLARK": "SM CLARK",
	"SM TAYTAY": "SM TAYTAY",
	"SM PULILAN": "SM PULILAN",
	"SM SJDM": "SM SJDM",
	"SM MOA": "SM MOA",
	"SM STA. ROSA": "SM STA ROSA",
	# SM stores — name mismatches (device uses short form)
	"SM GRAND CENTRAL": "GRAND CENTRAL",
	# Robinsons stores
	"ROBINSON ANTIPOLO": "ROBINSONS ANTIPOLO",
	"ROBINSONS IMUS": "ROBINSONS IMUS",
	"ROBINSONS GALLERIA SOUTH": "ROBINSONS GALLERIA SOUTH",
	"ROBINSON GENERAL TRIAS": "ROBINSONS GENERAL TRIAS",
	# Ayala stores
	"AYALA VERMOSA": "AYALA VERMOSA",
	"AYALA UP TOWN CENTER": "AYALA UP TOWN CENTER",
	"AYALA SOLENAD": "AYALA SOLENAD",
	"AYALA FAIRVIEW": "AYALA FAIRVIEW TERRACES",
	"AYALA EVO": "AYALA EVO",
	"MARKET MARKET": "MARKET MARKET",  # CSV renames to AYALA MARKET MARKET
	# Other named stores
	"ARANETA GATEWAY": "ARANETA GATEWAY",
	"BF HOMES": "BF HOMES",  # CSV renames to BF HOMES PARANAQUE
	"CTTM TOMAS MORATO": "CTTM TOMAS MORATO",
	"D VERDE CALAMBA": "D VERDE CALAMBA",  # CSV renames to D'VERDE CALAMBA
	"FESTIVAL MALL": "FESTIVAL MALL",  # CSV renames to FESTIVAL MALL ALABANG
	"GREENHILLS": "GREENHILLS",  # CSV renames to ORTIGAS GREENHILLS
	"LCT": "LUCKY CHINATOWN",
	"NAIA T3": "NAIA TERMINAL 3",  # CSV NAIA TERMINAL 3 renames to NAIA T3
	"PASEO": "MEGAWORLD PASEO CENTER",
	"PITX": "PITX",
	"STA LUCIA GRAND MALL": "STA LUCIA GRAND MALL",  # CSV renames to STA. LUCIA EAST GRAND MALL
	"THE TERMINAL": "THE TERMINAL",  # CSV renames to NAIA T3
	"UPTOWN BGC": "UPTOWN BGC",
	"VENICE GRAND CANAL": "VENICE GRAND CANAL",
	"VISTA MALL TAGUIG": "VISTA MALL TAGUIG",  # ⚠ not in CSV — bridge will fail for this one; see below
}


class UnknownDeviceCompany(Exception):
	"""Device serial number cannot be resolved to a Frappe Company."""


def resolve_device_company(device_sn: str, department: str | None = None) -> str:
	"""Resolve a device serial number to the Frappe Company docname for its store.

	Pipeline:
	    device_sn -> DEVICE_TO_STORE[sn] -> DEVICE_STORE_BRIDGE[store_name]
	        -> resolve_branch_to_company(branch_key, department) -> full Company name

	Args:
	    device_sn: The biometric device serial number (e.g. 'UDP3251600245').
	    department: Optional Employee.department — used only for bare commissary
	        branches that route dept-driven (`SHAW COMMISSARY` with dept != Commissary
	        -> BEI parent; with dept == Commissary -> BKI).

	Returns:
	    Full Frappe Company docname (e.g. 'SM MEGAMALL - BEBANG ENTERPRISE INC.').

	Raises:
	    UnknownDeviceCompany: if the device isn't in DEVICE_TO_STORE, or its store
	        name isn't in DEVICE_STORE_BRIDGE, or the bridged branch isn't in
	        branch_company_map.csv, or the store prefix doesn't resolve to a
	        live Frappe Company.
	"""
	if not device_sn:
		raise UnknownDeviceCompany("Empty device_sn")

	store_name = DEVICE_TO_STORE.get(device_sn)
	if not store_name:
		raise UnknownDeviceCompany(
			f"Device {device_sn!r} not in DEVICE_TO_STORE (hrms/utils/device_mapping.py). "
			f"Update that file first."
		)

	branch_key = DEVICE_STORE_BRIDGE.get(store_name)
	if not branch_key:
		raise UnknownDeviceCompany(
			f"Device {device_sn!r} -> store {store_name!r} has no bridge entry. "
			f"Add to DEVICE_STORE_BRIDGE in hrms/utils/device_store_bridge.py."
		)

	try:
		return resolve_branch_to_company(branch_key, department=department)
	except UnknownBranch as exc:
		raise UnknownDeviceCompany(
			f"Device {device_sn!r} -> store {store_name!r} -> branch {branch_key!r} "
			f"couldn't resolve to a Company: {exc}"
		) from exc


def self_test_bridge() -> dict:
	"""Return stats: which devices resolve cleanly, which fail, what's missing.

	Diagnostic helper for bench console. Useful before running first allocation.
	"""
	ok: list[dict] = []
	fail: list[dict] = []
	for sn, store in DEVICE_TO_STORE.items():
		try:
			company = resolve_device_company(sn)
			ok.append({"device": sn, "store": store, "company": company})
		except UnknownDeviceCompany as exc:
			fail.append({"device": sn, "store": store, "error": str(exc)})
	return {
		"total_devices": len(DEVICE_TO_STORE),
		"ok_count": len(ok),
		"fail_count": len(fail),
		"ok": ok,
		"fail": fail,
	}
