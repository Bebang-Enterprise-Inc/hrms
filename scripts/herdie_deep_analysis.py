#!/usr/bin/env python3
"""
Deep analysis of extracted corporate docs to find all Herdie Hernandez roles.
Reads extracted .md files and applies context-aware parsing for GIS and AOI formats.
"""

import json
import re
from pathlib import Path

EXTRACT_DIR = Path(r"F:\Dropbox\Projects\BEI-ERP\data\Audits\Herdie\01_Evidence\Corporate_Docs\ALL_ENTITIES\extracted")
OUTPUT_DIR = Path(r"F:\Dropbox\Projects\BEI-ERP\data\Audits\Herdie\01_Evidence\Corporate_Docs\ALL_ENTITIES")

HERDIE_PATTERNS = [
    re.compile(r'hernando', re.IGNORECASE),
    re.compile(r'herdie', re.IGNORECASE),
    re.compile(r'129[- ]?368[- ]?335'),
    re.compile(r'H\.?\s*D\.?\s*Hernandez', re.IGNORECASE),  # H.D. Hernandez, H D Hernandez
    re.compile(r'Hernandez,?\s*Hernando', re.IGNORECASE),    # Last, First format
]

# Broader pattern that includes any "Hernandez" -- used for initial scan,
# but confirmed only if context includes first name "Hernando" or "Diokno"
BROAD_HERNANDEZ = re.compile(r'hernandez', re.IGNORECASE)
HERDIE_CONFIRM = re.compile(r'hernando|herdie|diokno|129[- ]?368[- ]?335|H\.?\s*D\.?\s*Hernandez', re.IGNORECASE)


def has_herdie(text: str) -> bool:
    """Check if text contains Herdie specifically (not other Hernandez people)."""
    # Direct match on specific patterns
    if any(p.search(text) for p in HERDIE_PATTERNS):
        return True
    # If "Hernandez" appears, verify it's Herdie by checking full document context
    return False


def has_herdie_in_document(content: str) -> bool:
    """Check if the ENTIRE document refers to Herdie specifically."""
    # Must find either "Hernando" or TIN or "Diokno" somewhere in the document
    if HERDIE_CONFIRM.search(content):
        return True
    return False


def get_company_name(content: str, filename: str) -> str:
    """Extract the corporate name from the document."""
    # GIS: "CORPORATE NAME:" line
    m = re.search(r'CORPORATE\s*NAME\s*:\s*\n?\s*([A-Z][^\n]+)', content, re.IGNORECASE)
    if m:
        name = m.group(1).strip().strip('.')
        if len(name) > 3 and name.upper() != 'N.A' and 'PLEASE PRINT' not in name:
            return name

    # AOI: "Articles of Incorporation of XXXX"
    m = re.search(r'Articles\s+of\s+Incorporation\s*(?:of|OF)\s+([^\n]+)', content, re.IGNORECASE)
    if m:
        name = m.group(1).strip().strip('.')
        if len(name) > 3:
            return name

    # "name of said corporation shall be"
    m = re.search(r'name\s+of\s+said\s+corporation\s+shall\s+be\s*\n?\s*([A-Z][^\n]+)', content, re.IGNORECASE)
    if m:
        name = m.group(1).strip().strip('.')
        if len(name) > 3:
            return name

    # Bylaws: "BY-LAWS OF XXXX"
    m = re.search(r'BY[- ]?LAWS?\s+(?:OF|of)\s+([^\n]+)', content, re.IGNORECASE)
    if m:
        name = m.group(1).strip().strip('.')
        if len(name) > 3 and 'PLEASE PRINT' not in name:
            return name

    # Board resolution: look for company name at top
    m = re.search(r'^([A-Z][A-Z\s&.,\'-]+(?:INC|CORP|OPC)\.?)\s*\n', content, re.MULTILINE)
    if m:
        name = m.group(1).strip().strip('.')
        if len(name) > 3:
            return name

    # Board resolution with entity suffix in filename: "BOARD RESOLUTION ... LCT"
    fn_upper = filename.upper()
    if 'BOARD RESOLUTION' in fn_upper or 'BOARD_RESOLUTION' in fn_upper:
        for entity in ['LCT', 'SMEO', 'SMOA', 'SMM', 'SMV', 'PITX', 'MEGA', 'SHAW', 'MARIKINA', 'NORTH EDSA']:
            if entity in fn_upper:
                return f'BEBANG {entity} INC'
        # Generic board resolution without entity suffix - likely BEI
        return 'BEBANG ENTERPRISE INC'

    # Board resolution: "Board of Directors of XXXX" (skip "the Corporation" which is template)
    m = re.search(r'Board\s+of\s+Directors\s+of\s+(?:the\s+)?([^\(]+?)(?:\s*\(|held)', content, re.IGNORECASE)
    if m:
        name = m.group(1).strip().strip('.,')
        if len(name) > 3 and name.upper() not in ('CORPORATION', 'THE CORPORATION'):
            return name

    # Fallback: filename-based
    return clean_filename(filename)


def clean_filename(filename: str) -> str:
    """Clean company name from filename."""
    name = filename
    for rem in ['AOI', 'GIS', 'By-Laws', 'Bylaws', 'Secretary Certificate', 'Annual',
                '2316', '2023', '2024', '2025', '2026', '(Signed)', '(Not Signed)',
                '01.', '02.', '03.', '04.', '05.', '1.', '2.', '3.', '4.', '5.',
                '.pdf', '.md', '_', 'Copy of ', '(1)', '(2)', '(3)', '(4)',
                'BYLAWS', 'EXTRACTION', 'STATUS', 'v1', 'v2',
                'NODATE', 'Final', '(Final)']:
        name = name.replace(rem, ' ')
    # Remove date patterns like 20240322
    name = re.sub(r'\b20\d{6}\b', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name if len(name) > 2 else filename


def analyze_document(filepath: Path) -> dict | None:
    """Analyze a single extracted document for Herdie's presence."""
    try:
        content = filepath.read_text(encoding='utf-8')
    except:
        return None

    if not has_herdie_in_document(content):
        return None

    company_name = get_company_name(content, filepath.stem)
    roles = set()
    shares = ""
    tin_found = False

    # Check for TIN
    if re.search(r'129[- ]?368[- ]?335', content):
        tin_found = True

    lines = content.split('\n')

    # Determine document type
    is_gis = 'GENERAL INFORMATION SHEET' in content.upper()
    is_aoi = 'ARTICLES OF INCORPORATION' in content.upper() or 'INCORPORAT' in content.upper()
    is_bylaws = 'BY-LAWS' in content.upper() or 'BYLAWS' in content.upper()
    is_sec_cert = 'SECRETARY' in content.upper() and 'CERTIF' in content.upper()

    # ---- GIS parsing ----
    if is_gis:
        # GIS has a DIRECTORS/OFFICERS section
        # Format: numbered entry with name, nationality, INC'R, BOARD, GENDER, STOCKHOLDER, OFFICER columns
        in_directors_section = False
        in_stockholders_section = False

        for i, line in enumerate(lines):
            line_stripped = line.strip()

            if 'DIRECTORS' in line_stripped.upper() and 'OFFICER' in line_stripped.upper():
                in_directors_section = True
                in_stockholders_section = False
                continue
            if 'STOCKHOLDERS' in line_stripped.upper() and ('LIST' in line_stripped.upper() or 'NAME' in line_stripped.upper() or 'TOP 20' in line_stripped.upper()):
                in_stockholders_section = True
                in_directors_section = False
                continue

            if has_herdie(line_stripped):
                if in_directors_section:
                    # In directors/officers section - always a director
                    roles.add('Director')
                    roles.add('Stockholder')
                    # Check context for INC'R = Y
                    context = '\n'.join(lines[max(0,i-2):min(len(lines),i+8)])
                    if re.search(r'\bY\b', context):
                        roles.add('Incorporator')
                    # Check officer title
                    for j in range(i+1, min(len(lines), i+10)):
                        officer_line = lines[j].strip()
                        if 'PRES' in officer_line.upper():
                            roles.add('President')
                        if 'SEC' in officer_line.upper() and 'CORP' in officer_line.upper():
                            roles.add('Corporate Secretary')
                        if 'TREAS' in officer_line.upper():
                            roles.add('Treasurer')
                        if 'N/A' in officer_line.upper() or 'NOTHING FOLLOWS' in officer_line.upper():
                            break
                        if re.match(r'^\d+\.', officer_line):
                            break

                if in_stockholders_section:
                    roles.add('Stockholder')
                    # Look for share count
                    for j in range(i+1, min(len(lines), i+6)):
                        share_line = lines[j].strip()
                        m = re.match(r'^([\d,]+)$', share_line)
                        if m:
                            shares = m.group(1) + " shares"
                            break

    # ---- AOI parsing ----
    if is_aoi:
        # AOI lists incorporators in a section like "names, nationalities and residences of the incorporators"
        in_incorporators = False
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            if 'incorporator' in line_stripped.lower() or 'subscribers' in line_stripped.lower():
                in_incorporators = True
            if has_herdie(line_stripped):
                if in_incorporators:
                    roles.add('Incorporator')
                else:
                    roles.add('Incorporator')  # In AOI, being named is typically as incorporator

        # Check for directors section in AOI
        in_directors = False
        for i, line in enumerate(lines):
            if 'director' in line.lower() and ('shall be' in line.lower() or 'elected' in line.lower() or 'names' in line.lower()):
                in_directors = True
            if in_directors and has_herdie(line):
                roles.add('Director')
            if in_directors and ('eighth' in line.lower() or 'ninth' in line.lower() or
                                'tenth' in line.lower() or 'WITNESS' in line.upper()):
                in_directors = False

        # Check for subscriber/shares section
        for i, line in enumerate(lines):
            if has_herdie(line):
                context = '\n'.join(lines[max(0,i-2):min(len(lines),i+6)])
                # Look for shares
                m = re.search(r'(\d[\d,]*)\s*(?:shares?|shs)', context, re.IGNORECASE)
                if m:
                    shares = m.group(1) + " shares"
                    roles.add('Subscriber')

    # ---- Bylaws parsing ----
    if is_bylaws:
        # Bylaws mention initial directors or are signed by incorporators
        for i, line in enumerate(lines):
            if has_herdie(line):
                context = '\n'.join(lines[max(0,i-5):min(len(lines),i+5)])
                if 'director' in context.lower():
                    roles.add('Director')
                if 'incorporator' in context.lower():
                    roles.add('Incorporator')
                if 'secretary' in context.lower() and 'corporate' in context.lower():
                    roles.add('Corporate Secretary')
                if 'treasurer' in context.lower():
                    roles.add('Treasurer')
                if 'president' in context.lower():
                    roles.add('President')
                # Bylaws are typically signed by directors/incorporators
                if not roles or roles == {'Named in document'}:
                    roles.add('Signatory (Director/Incorporator)')

    # ---- Secretary Certificate parsing ----
    if is_sec_cert:
        for i, line in enumerate(lines):
            if has_herdie(line):
                context = '\n'.join(lines[max(0,i-5):min(len(lines),i+5)])
                if 'corporate secretary' in context.lower():
                    roles.add('Corporate Secretary')
                if 'director' in context.lower():
                    roles.add('Director')
                if 'president' in context.lower():
                    roles.add('President')
                if 'officer' in context.lower():
                    roles.add('Officer')

    # ---- Board Resolution parsing ----
    is_board_res = 'BOARD RESOLUTION' in content.upper()
    if is_board_res:
        for i, line in enumerate(lines):
            if has_herdie(line):
                context = '\n'.join(lines[max(0,i-10):min(len(lines),i+10)]).lower()
                if 'resignation' in context and 'director' in context:
                    roles.add('Director (resigned)')
                elif 'director' in context:
                    roles.add('Director')
                if 'equity' in context or 'vested' in context or 'capital stock' in context:
                    roles.add('Stockholder')
                if 'corporate secretary' in context:
                    roles.add('Corporate Secretary')
                if 'president' in context and 'vice' not in context:
                    roles.add('President')
                # Signatory on board resolution = Director
                if not roles:
                    roles.add('Director (signatory)')

    # If still no roles detected, use broader context
    if not roles:
        for i, line in enumerate(lines):
            if has_herdie(line):
                context = '\n'.join(lines[max(0,i-10):min(len(lines),i+10)]).lower()
                if 'director' in context:
                    roles.add('Director')
                if 'incorporator' in context or 'subscriber' in context:
                    roles.add('Incorporator')
                if 'stockholder' in context or 'shareholder' in context:
                    roles.add('Stockholder')
                if 'corporate secretary' in context:
                    roles.add('Corporate Secretary')
                if 'secretary' in context and 'corporate' not in context:
                    roles.add('Secretary')
                if 'president' in context and 'vice' not in context:
                    roles.add('President')
                if 'treasurer' in context:
                    roles.add('Treasurer')

    if not roles:
        roles.add('Named in document')

    return {
        'source_file': filepath.name,
        'company_name': company_name,
        'roles': sorted(roles),
        'shares': shares,
        'tin_found': tin_found,
        'doc_type': 'GIS' if is_gis else 'AOI' if is_aoi else 'Bylaws' if is_bylaws else 'SecCert' if is_sec_cert else 'Other',
    }


def main():
    md_files = sorted(EXTRACT_DIR.glob("*.md"))
    print(f"Scanning {len(md_files)} extracted files...\n")

    all_matches = []
    for f in md_files:
        result = analyze_document(f)
        if result:
            all_matches.append(result)
            role_str = ', '.join(result['roles'])
            print(f"  [{result['doc_type']}] {result['company_name']}: {role_str} | {result['shares']} | {result['source_file']}")

    print(f"\n{'='*60}")
    print(f"Total document matches: {len(all_matches)}")

    # Consolidate by company
    companies = {}
    # Canonical names for known entities
    canonical_names = {
        'BEI': 'Bebang Enterprise Inc.',
        'III': 'Irresistible Infusions Inc.',
        'TRICERN': 'Tricern Food Corp.',
        'HFFM_SOLENAD': 'HFFM Solenad Food Services, Inc.',
        'HFFM_SOLDEDAD': 'HFFM Soldedad Food Services, Inc.',
        'BEBANG LCT': 'Bebang LCT Inc.',
        'BEBANG SMEO': 'Bebang SMEO Inc.',
        'BEBANG SMOA': 'Bebang SMOA Inc.',
    }

    for m in all_matches:
        # Normalize company name for grouping
        key = normalize_company_name(m['company_name'])
        if key not in companies:
            companies[key] = {
                'company_name': canonical_names.get(key, m['company_name']),
                'roles': set(m['roles']),
                'shares': m['shares'],
                'source_files': [m['source_file']],
                'doc_types': {m['doc_type']},
                'tin_found': m['tin_found'],
            }
        else:
            companies[key]['roles'].update(m['roles'])
            if m['shares'] and not companies[key]['shares']:
                companies[key]['shares'] = m['shares']
            if m['source_file'] not in companies[key]['source_files']:
                companies[key]['source_files'].append(m['source_file'])
            companies[key]['doc_types'].add(m['doc_type'])
            companies[key]['tin_found'] = companies[key]['tin_found'] or m['tin_found']
            # Use canonical if available, otherwise prefer longer name
            if key in canonical_names:
                companies[key]['company_name'] = canonical_names[key]
            elif len(m['company_name']) > len(companies[key]['company_name']):
                companies[key]['company_name'] = m['company_name']

    # Remove "Named in document" if we have more specific roles
    for key, comp in companies.items():
        if len(comp['roles']) > 1 and 'Named in document' in comp['roles']:
            comp['roles'].discard('Named in document')

    sorted_companies = sorted(companies.values(), key=lambda x: x['company_name'])

    print(f"Unique entities: {len(sorted_companies)}")
    print()

    for i, comp in enumerate(sorted_companies, 1):
        roles_str = ', '.join(sorted(comp['roles']))
        print(f"  {i:2d}. {comp['company_name']}")
        print(f"      Roles: {roles_str}")
        if comp['shares']:
            print(f"      Shares: {comp['shares']}")
        print(f"      Docs: {', '.join(comp['source_files'][:3])}")
        print()

    # Add entities mentioned in board resolutions/other docs but not separately documented
    # E3 Board Resolution explicitly names BEI, BKI, and "any other affiliated entity"
    if 'III' in companies:
        iii = companies['III']
        # Add BKI if not already found via separate docs
        if 'BEBANG KITCHEN' not in companies:
            companies['BEBANG KITCHEN'] = {
                'company_name': 'Bebang Kitchen Inc. (BKI)',
                'roles': {'Director (resigned)'},
                'shares': '',
                'source_files': ['E3_Board_Resolution_2026-01-23__1O5iLC57.md'],
                'doc_types': {'Board Resolution'},
                'tin_found': False,
            }
            print(f"\n  Added BKI (mentioned in E3 Board Resolution as entity he resigned from)")

        # Update III shares from E3 board resolution
        if not iii['shares']:
            iii['shares'] = '0.75% (vested equity per Board Res 2026-01)'

    sorted_companies = sorted(companies.values(), key=lambda x: x['company_name'])

    # Write outputs
    write_markdown(sorted_companies)
    write_json(sorted_companies)


def normalize_company_name(name: str) -> str:
    """Normalize company name for grouping."""
    n = name.upper().strip()
    # Remove punctuation
    n = re.sub(r'[.,\(\)]', '', n)
    n = re.sub(r'\s+', ' ', n).strip()

    # Remove trailing file ID patterns like "1AngfLuG"
    n = re.sub(r'\s+[A-Za-z0-9]{8}$', '', n)
    # Remove trailing dates
    n = re.sub(r'\s*DATE REGISTERED.*$', '', n)
    # Remove leading "BOARD RESOLUTION..." prefix -- extract entity from parenthetical
    board_match = re.search(r'BOARD RESOLUTION.*?(?:CLOSURE OF TITF ACCOUNT)\s*\)?\s*(.*)', n)
    if board_match:
        entity_hint = board_match.group(1).strip()
        if entity_hint and entity_hint not in ('', '13R2NHSV'):
            n = f"BEBANG {entity_hint}"
        else:
            # Generic board resolution - skip by returning a merge-able key
            n = "BOARD_RES_GENERIC"

    # "Corporation" as company name = template
    if n == 'CORPORATION':
        n = "BOARD_RES_GENERIC"

    # Clean "BUSINESS/TRADE NAME:" artifact
    if 'BUSINESS/TRADE NAME' in n:
        n = 'BEBANG ENTERPRISE'

    # Known aliases / normalizations
    aliases = {
        'BEBANG ENTERPRISE INC': 'BEI',
        'BEBANG ENTERPRISE': 'BEI',
        'BEI': 'BEI',
        'HFFM SOLENAD FOOD SERVICES INC': 'HFFM_SOLENAD',
        'HFFM SOLENAD FOOD SERVICES': 'HFFM_SOLENAD',
        'HFFM SOLDEDAD FOOD SERVICES INC': 'HFFM_SOLENAD',   # "Soldedad" is OCR error for "Solenad"
        'HFFM SOLDEDAD FOOD SERVICES': 'HFFM_SOLENAD',
        'TRICERN FOOD CORF': 'TRICERN',
        'TRICERN FOOD CORP': 'TRICERN',
        'IRRESISTIBLE INFUSIONS INC': 'III',
        'IRRESISTIBLE INFUSIONS': 'III',
        'E3 BOARD RESOLUTION': 'III',  # E3 = III board resolution
    }
    for pattern, code in aliases.items():
        if pattern in n:
            return code

    # Strip common suffixes for grouping
    for suffix in [' INC', ' CORP', ' OPC', ' CORPORATION', ' INCORPORATED']:
        if n.endswith(suffix):
            n = n[:-len(suffix)]

    return n


def write_markdown(companies: list):
    md_path = OUTPUT_DIR / "HERDIE_ALL_COMPANIES_2026-03-29.md"
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write("# Herdie Hernandez -- All Corporate Roles\n\n")
        f.write("**Subject:** Hernando Diokno Hernandez\n")
        f.write("**TIN:** 129-368-335-000\n")
        f.write("**Generated:** 2026-03-29\n")
        f.write(f"**Source:** Extracted from {len(list(EXTRACT_DIR.glob('*.md')))} corporate documents (AOI, GIS, Bylaws, Secretary Certificates)\n\n")

        f.write("## Summary\n\n")
        f.write(f"Herdie Hernandez appears in **{len(companies)}** distinct corporate entities.\n\n")

        f.write("## All Entities\n\n")
        f.write("| # | Entity Name | Role(s) | Shares | Doc Type(s) | Source Document(s) |\n")
        f.write("|---|-------------|---------|--------|-------------|--------------------|\n")

        for i, comp in enumerate(companies, 1):
            roles_str = ', '.join(sorted(comp['roles']))
            doc_types = ', '.join(sorted(comp['doc_types']))
            sources = '; '.join(comp['source_files'][:3])
            if len(comp['source_files']) > 3:
                sources += f" (+{len(comp['source_files'])-3} more)"
            f.write(f"| {i} | {comp['company_name']} | {roles_str} | {comp['shares']} | {doc_types} | {sources} |\n")

        f.write(f"\n---\n\n**Total entities: {len(companies)}**\n\n")

        # Role summary
        f.write("## Role Summary\n\n")
        role_counts = {}
        for comp in companies:
            for r in comp['roles']:
                role_counts[r] = role_counts.get(r, 0) + 1
        for role, count in sorted(role_counts.items(), key=lambda x: -x[1]):
            f.write(f"- **{role}:** {count} entities\n")

    print(f"\nWritten: {md_path}")


def write_json(companies: list):
    json_path = OUTPUT_DIR / "HERDIE_ALL_COMPANIES_2026-03-29.json"
    data = []
    for i, comp in enumerate(companies, 1):
        data.append({
            'index': i,
            'entity_name': comp['company_name'],
            'roles': sorted(comp['roles']),
            'shares': comp['shares'],
            'tin_found': comp['tin_found'],
            'doc_types': sorted(comp['doc_types']),
            'source_documents': comp['source_files'],
        })

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Written: {json_path}")


if __name__ == '__main__':
    main()
