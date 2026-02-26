"""
Roving Employee Registry
Employees authorized to punch at multiple store devices.
Source: IT Biometric Audit Feb 2026 (Ronald Carigal)
Last Updated: 2026-02-25
"""

ROVING_EMPLOYEES = {
    '9000037': {'name': 'SERINAS, KENNETH M.', 'home': 'ARANETA GATEWAY', 'role': 'ROVING'},
    '9000024': {'name': 'NARAL, JEFFREY G.', 'home': 'ARANETA GATEWAY', 'role': 'ROVING'},
    '9000152': {'name': 'MENDOZA, AILEEN L.', 'home': 'ARANETA GATEWAY', 'role': 'ROVING'},
    '9000014': {'name': 'MOLINA JR, RENATO JR', 'home': 'ARANETA GATEWAY', 'role': 'ROVING'},
    '9000784': {'name': 'AGUARINO, JOHN HAYS P.', 'home': 'ARANETA GATEWAY', 'role': 'ROVING'},
    '9000657': {'name': 'DILAPDILAP, AUBREY M.', 'home': 'ARANETA GATEWAY', 'role': 'ROVING'},
    '9000575': {'name': 'GARCIA, JOANNA MARIE E.', 'home': 'AYALA EVO', 'role': 'AREA_SUPERVISOR'},
    '9000108': {'name': 'MOLINA, JEANELE P.', 'home': 'MARKET MARKET', 'role': 'AREA_SUPERVISOR'},
    '9000273': {'name': 'CLOSA, PAULA ROMAINE G.', 'home': 'BF HOMES', 'role': 'AREA_SUPERVISOR'},
    '9000791': {'name': 'MENDOZA, AILYN C.', 'home': 'AYALA EVO', 'role': 'OPENING_TEAM'},
    '9000556': {'name': 'CHAN, JOCELYN M.', 'home': 'BRITTANY OFFICE', 'role': 'AREA_SUPERVISOR'},
    '9000519': {'name': 'MONTIALTO, ERICK RICHMOND B.', 'home': 'ARANETA GATEWAY', 'role': 'AREA_SUPERVISOR'},
    '9000158': {'name': 'CAÑEBA, WARREN D.', 'home': 'AYALA FAIRVIEW TERRACES', 'role': 'AREA_SUPERVISOR'},
    '9000318': {'name': 'NAVARRO, LOVELY N.', 'home': 'GRAND CENTRAL', 'role': 'AREA_SUPERVISOR'},
    '9000714': {'name': 'VILLANUEVA, ANDREI U.', 'home': 'BRITTANY OFFICE', 'role': 'DUTY_MYTOWN'},
    '9001798': {'name': 'MUNOZ, HARRY ANTHONY', 'home': 'SM MOA', 'role': 'OPENING_TEAM'},
    '9001724': {'name': 'MENDOZA, JULES VINCENT S.', 'home': 'SM MARILAO', 'role': 'AREA_SUPERVISOR'},
    '9000859': {'name': 'RUSTRIA, IRA JANE M.', 'home': 'AYALA SOLENAD', 'role': 'AREA_SUPERVISOR'},
    '9000661': {'name': 'TIU, JAMES LOUIE B.', 'home': 'ROBINSON GENERAL TRIAS', 'role': 'AREA_SUPERVISOR'},
    # Wave 15 — IT Transfer Request Feb 25, 2026 (confirmed by Edlice Dela Cruz, Ops)
    '9000220': {'name': 'OLEA, LYNDON D.', 'home': 'BRITTANY OFFICE', 'role': 'PROJECTS_TEAM'},
    '9000508': {'name': 'TEMPLO, JOMARE S.', 'home': 'BRITTANY OFFICE', 'role': 'PROJECTS_TEAM'},
    '9001608': {'name': 'MAYNIGO, MARK ANTHONY S.', 'home': 'BRITTANY OFFICE', 'role': 'PROJECTS_TEAM'},
    '9000287': {'name': 'FERRER, ERIK KEVIN B.', 'home': 'BRITTANY OFFICE', 'role': 'PROJECTS_TEAM'},
    '9000102': {'name': 'MARQUEZ, DANIELL JOSEPH E.', 'home': 'BRITTANY OFFICE', 'role': 'PROJECTS_TEAM'},
    '9000611': {'name': 'VALDEZ, ELIZABETH J.', 'home': 'AYALA EVO', 'role': 'OPENING_TEAM'},
    '9000490': {'name': 'RAMAL, RAMIL DAVID C.', 'home': 'BF HOMES', 'role': 'AREA_SUPERVISOR_TRAINEE'},
}


def is_roving(bio_id: str) -> bool:
    """Check if an employee is authorized to punch at multiple stores."""
    return bio_id in ROVING_EMPLOYEES


def get_roving_info(bio_id: str) -> dict | None:
    """Get roving employee details, or None if not roving."""
    return ROVING_EMPLOYEES.get(bio_id)
