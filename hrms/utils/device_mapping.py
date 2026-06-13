"""
Biometric Device to Store Location Mapping
Source: UPDATED_IT_Device_SN_Mapping.xlsx (Feb 2026) + S230 (Apr 2026) + S239 (May 2026) + S244 (May 2026)
Last Updated: 2026-05-11 (S244: added Alabang Town Center UDP3254701583 — joins Cluster 6 South)
"""

# Master device mapping - NEVER return "UNKNOWN"
DEVICE_TO_STORE = {
    'CNYG242061011': 'SM GRAND CENTRAL',
    'CNYG242061071': 'SM MARIKINA',
    'CNYG242061619': 'AYALA FAIRVIEW',
    'CNYG242061620': 'SM SOUTHMALL',
    'CNYG242061718': 'THE TERMINAL',
    'UDP3235200526': 'LCT',
    'UDP3235200594': 'ROBINSON ANTIPOLO',
    'UDP3235200625': 'BGC CAPITAL HOUSE',
    'UDP3235200627': 'MARKET MARKET',
    'UDP3235200629': 'SHAW COMMISSARY',
    'UDP3235200631': 'SM MEGAMALL',
    'UDP3235200633': 'SM MANILA',
    'UDP3235200831': 'SM NORTH EDSA',
    'UDP3235201051': 'SM VALENZUELA',
    'UDP3251200168': 'PASEO',
    'UDP3251200193': 'SM EAST ORTIGAS',
    'UDP3251200195': 'FESTIVAL MALL',
    'UDP3251200197': 'VENICE GRAND CANAL',
    'UDP3251200212': 'PITX',
    'UDP3251400170': 'SM SJDM',
    'UDP3251400192': 'SM MOA',
    'UDP3251600215': 'BF HOMES',
    'UDP3251600219': 'SM TANZA',
    'UDP3251600245': 'BRITTANY OFFICE',  # Fixed spelling
    'UDP3251600317': 'SM BICUTAN',
    'UDP3251600333': 'SM CALOOCAN',
    'UDP3252100358': 'SM SANGANDAAN',
    'UDP3252100384': 'CTTM TOMAS MORATO',
    'UDP3252100385': 'ROBINSON GENERAL TRIAS',
    'UDP3252100422': 'SM MARILAO',
    'UDP3252100496': 'SM CLARK',
    'UDP3252300333': 'AYALA EVO',
    'UDP3252300350': 'ROBINSONS IMUS',
    'UDP3252300354': 'SM PULILAN',
    'UDP3252300355': 'ROBINSONS GALLERIA SOUTH',
    'UDP3252300360': 'AYALA VERMOSA',
    'UDP3252900048': 'SM TAYTAY',
    'UDP3252900145': 'SM STA. ROSA',
    'UDP3252900155': 'STA LUCIA GRAND MALL',
    'UDP3252900163': 'MYTOWN',
    'UDP3252900188': 'D VERDE CALAMBA',
    'UDP3252900249': 'ORTIGAS ESTANCIA',  # S230: matches Frappe tabBranch row + canonical store name
    'UDP3252900251': 'GREENHILLS',
    'UDP3252900282': 'AYALA UP TOWN CENTER',
    'UDP3252900284': 'AYALA SOLENAD',
    'UDP3252900287': 'NAIA T3',
    'UDP3252900298': 'UPTOWN BGC',
    'UDP3252900302': 'ARANETA GATEWAY',
    'UDP3252900305': 'VISTA MALL TAGUIG',
    'UDP3254701502': 'XENTROMALL MONTALBAN',  # S230: matches Frappe tabEmployee.branch for the 12 active Xentro crew + Frappe Company XENTROMALL MONTALBAN - PERPETUAL FOOD CORP.
    'UDP3254800655': '3MD COMMISSARY',  # S239 (2026-05-07): new commissary device at 3MD Logistics Camangyanan facility, Sta Maria, Bulacan — standalone (NOT in cluster 1-9, similar to Shaw Commissary). Renamed 2026-05-07 from CAMANGYANAN BULACAN per CEO directive.
    'UDP3254701583': 'ALABANG TOWN CENTER',  # S244 (2026-05-11): ATC store; joins Cluster 6 South (David Ramal) as D6 alongside Bicutan, BF Homes, Terminal, Festival, Southmall
    'UDP3254800652': 'SM SAN PABLO',  # DTR-step1 (2026-06-13): live device, was syncing to Supabase as UNKNOWN
    'UDP3254701501': 'ROBINSONS DASMA',  # DTR-step1 (2026-06-13): store opened ~2026-06-01, was syncing as UNKNOWN
}

def get_store_name(serial_number: str) -> str:
    """
    Get store name for a device serial number.
    NEVER returns 'UNKNOWN' - raises KeyError if not found.
    """
    store = DEVICE_TO_STORE.get(serial_number)
    if not store:
        raise KeyError(f"Device {serial_number} not in mapping. Update device_mapping.py!")
    return store

def get_all_devices() -> dict:
    """Return complete device mapping"""
    return DEVICE_TO_STORE.copy()
