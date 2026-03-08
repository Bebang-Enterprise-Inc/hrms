"""
BEI Weekly Meta Ads Report — Reusable DOCX Template
Brand: Bebang Halo-Halo | Palette: Jelly Green / Yema Gold / Ube Purple
"""
from docx import Document
from docx.shared import Inches, Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from datetime import datetime

PALETTE = {
    'primary': '04400A', 'secondary': 'C8900A', 'accent': '801297',
    'light': 'E6ECE7', 'light_gold': 'F8F0D9', 'light_purple': 'F2E5F5',
    'text': '1A1A1A', 'text_light': '666666', 'bg_alt': 'E6ECE7',
    'bg_page': 'F9F5EB', 'white': 'FFFFFF', 'border': 'D4D0C8',
    'green_mid': '2D7A35', 'error': 'CC0000',
}
_DARK_BG = {PALETTE['primary'], PALETTE['accent'], PALETTE['green_mid']}

# -- Helpers ----------------------------------------------------------------

def hex_to_rgb(h): return RGBColor(int(h[:2], 16), int(h[2:4], 16), int(h[4:6], 16))

def _run(p, text, size=10, bold=False, color=PALETTE['text'], italic=False):
    """Add a styled Calibri run to paragraph p."""
    r = p.add_run(text)
    r.font.size, r.font.name, r.bold, r.italic = Pt(size), 'Calibri', bold, italic
    r.font.color.rgb = hex_to_rgb(color)
    return r

def set_cell_bg(cell, color_hex):
    shading = OxmlElement('w:shd')
    shading.set(qn('w:fill'), color_hex); shading.set(qn('w:val'), 'clear')
    cell._tc.get_or_add_tcPr().append(shading)

def set_cell_border(cell, **kwargs):
    tcPr = cell._tc.get_or_add_tcPr()
    tcBorders = OxmlElement('w:tcBorders')
    for edge, val in kwargs.items():
        el = OxmlElement(f'w:{edge}')
        for k, d in [('w:val', 'single'), ('w:sz', '4'), ('w:color', PALETTE['border'])]:
            el.set(qn(k), val.get(k.split(':')[1], d))
        el.set(qn('w:space'), '0')
        tcBorders.append(el)
    tcPr.append(tcBorders)

def add_styled_para(doc, text, size=10, bold=False, color=None,
                    alignment=None, space_after=6, space_before=0):
    p = doc.add_paragraph()
    _run(p, text, size, bold, color or PALETTE['text'])
    if alignment: p.alignment = alignment
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.space_before = Pt(space_before)
    return p

def add_section_heading(doc, text, level=1):
    if level == 1:
        p = add_styled_para(doc, text, 16, True, PALETTE['primary'], space_before=12, space_after=6)
        pBdr = OxmlElement('w:pBdr'); bottom = OxmlElement('w:bottom')
        for a, v in [('w:val','single'),('w:sz','12'),('w:color',PALETTE['primary']),('w:space','4')]:
            bottom.set(qn(a), v)
        pBdr.append(bottom); p._p.get_or_add_pPr().append(pBdr)
        return p
    if level == 2:
        return add_styled_para(doc, text, 13, True, PALETTE['secondary'], space_before=10, space_after=4)
    return add_styled_para(doc, text, 11, True, PALETTE['primary'], space_before=6, space_after=3)

def create_branded_table(doc, headers, rows, col_widths=None):
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.style = 'Table Grid'; table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(headers):
        c = table.rows[0].cells[i]; set_cell_bg(c, PALETTE['primary'])
        c.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        _run(c.paragraphs[0], h, 9, True, PALETTE['white'])
    for ri, rd in enumerate(rows):
        bg = PALETTE['bg_alt'] if ri % 2 == 0 else PALETTE['white']
        for ci, v in enumerate(rd):
            c = table.rows[ri+1].cells[ci]; set_cell_bg(c, bg)
            _run(c.paragraphs[0], str(v), 9)
    if col_widths:
        for i, w in enumerate(col_widths):
            for r in table.rows: r.cells[i].width = Inches(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(4)
    return table

def format_php(amount):
    if amount is None or amount == 0: return '\u2014'
    return f'(PHP {abs(amount):,.2f})' if amount < 0 else f'PHP {amount:,.2f}'

def _callout(doc, title, body, border_color=None):
    bc = border_color or PALETTE['secondary']
    bg = PALETTE['light_gold'] if bc == PALETTE['secondary'] else PALETTE['light']
    tbl = doc.add_table(rows=1, cols=1); tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = tbl.rows[0].cells[0]; set_cell_bg(cell, bg)
    for edge in ('top','bottom','start','end'):
        set_cell_border(cell, **{edge: {'val':'single','sz':'12','color':bc}})
    _run(cell.paragraphs[0], title, 10, True, bc)
    _run(cell.add_paragraph(), body, 9, color=PALETTE['text'])
    doc.add_paragraph().paragraph_format.space_after = Pt(4)

def _kpi_bar(doc, kpis):
    tbl = doc.add_table(rows=2, cols=len(kpis)); tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, (label, value, color) in enumerate(kpis):
        vc = tbl.rows[0].cells[i]; set_cell_bg(vc, color)
        vc.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        tc = PALETTE['white'] if color in _DARK_BG else PALETTE['text']
        _run(vc.paragraphs[0], str(value), 22, True, tc)
        lc = tbl.rows[1].cells[i]; set_cell_bg(lc, PALETTE['white'])
        lc.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        _run(lc.paragraphs[0], label, 8, True, PALETTE['text_light'])
    doc.add_paragraph().paragraph_format.space_after = Pt(6)

def _cpa_bg(cpa, idx):
    if cpa is not None and cpa < 150: return 'D9F2D9'
    if cpa is not None and cpa > 200: return 'F9D6D6'
    return PALETTE['light_gold'] if cpa is not None else (PALETTE['bg_alt'] if idx%2==0 else PALETTE['white'])

# -- Main generator ---------------------------------------------------------

def generate_weekly_report(data: dict, output_path: str) -> str:
    """Generate branded BEI weekly Meta Ads report DOCX. Returns output_path."""
    doc = Document()
    for s in doc.sections:
        s.page_width, s.page_height = Cm(21), Cm(29.7)
        s.left_margin, s.right_margin = Cm(3.18), Cm(2.54)
        s.top_margin = s.bottom_margin = Cm(1.91)
    ns = doc.styles['Normal']; ns.font.name = 'Calibri'
    ns.font.size = Pt(10); ns.font.color.rgb = hex_to_rgb(PALETTE['text'])
    we = data.get('week_ending', datetime.now().strftime('%Y-%m-%d'))

    # -- 1. Cover Page --
    for _ in range(4): doc.add_paragraph().paragraph_format.space_after = Pt(0)
    cv = doc.add_table(rows=1, cols=1); cv.alignment = WD_TABLE_ALIGNMENT.CENTER
    cc = cv.rows[0].cells[0]; set_cell_bg(cc, PALETTE['primary'])
    p = cc.paragraphs[0]; p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(20)
    r = _run(p, 'BEBANG HALO-HALO', 14, color=PALETTE['white']); r.font.letter_spacing = Pt(3)
    p2 = cc.add_paragraph(); p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _run(p2, 'Weekly Meta Ads Intelligence', 28, True, PALETTE['white'])
    p3 = cc.add_paragraph(); p3.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p3.paragraph_format.space_after = Pt(20)
    _run(p3, f'Week ending {we}', 14, color=PALETTE['light'])
    doc.add_page_break()

    # -- 2. Executive Summary --
    add_section_heading(doc, '1. Executive Summary')
    _callout(doc, 'AI ANALYSIS', data.get('ai_analysis', ''), PALETTE['secondary'])
    _kpi_bar(doc, [
        ('Total Spend', format_php(data.get('total_spend')), PALETTE['primary']),
        ('Purchases', str(data.get('total_purchases', 0)), PALETTE['accent']),
        ('Avg CPA', format_php(data.get('avg_cpa')), PALETTE['green_mid']),
    ])

    # -- 3. Campaign Performance --
    add_section_heading(doc, '2. Campaign Performance')
    campaigns = data.get('campaigns', [])
    if campaigns:
        hdrs = ['Campaign','Objective','Spend (PHP)','Purchases','CPA','CTR','Frequency','Status']
        tbl = doc.add_table(rows=1+len(campaigns), cols=len(hdrs))
        tbl.style = 'Table Grid'; tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        for i, h in enumerate(hdrs):
            c = tbl.rows[0].cells[i]; set_cell_bg(c, PALETTE['primary'])
            c.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            _run(c.paragraphs[0], h, 9, True, PALETTE['white'])
        for idx, cp in enumerate(campaigns):
            cpa = cp.get('cpa_7d'); bg = _cpa_bg(cpa, idx)
            vals = [cp.get('campaign_name',''), cp.get('objective',''),
                    format_php(cp.get('spend_7d')), str(cp.get('purchases_7d',0)),
                    format_php(cpa), f"{cp.get('ctr_7d',0):.2f}%",
                    f"{cp.get('frequency_7d',0):.1f}", cp.get('status','')]
            for ci, v in enumerate(vals):
                c = tbl.rows[idx+1].cells[ci]; set_cell_bg(c, bg)
                _run(c.paragraphs[0], v, 9)
        doc.add_paragraph().paragraph_format.space_after = Pt(4)
    else:
        add_styled_para(doc, 'No campaign data for this period.', color=PALETTE['text_light'])

    # -- 4. Flagged Ads --
    add_section_heading(doc, '3. Flagged Ads')
    flagged = data.get('flagged_ads', [])
    if flagged:
        rows = [[f.get('ad_name',''), f.get('campaign_name',''), f.get('flag_reason',''),
                 format_php(f.get('spend_7d')), format_php(f.get('cpa_7d')),
                 f"{f.get('ctr_7d',0):.2f}%", f"{f.get('frequency',0):.1f}"] for f in flagged]
        t = create_branded_table(doc, ['Ad Name','Campaign','Flag Reason','Spend','CPA','CTR','Freq'], rows)
        for ri, f in enumerate(flagged):
            if any(k in (f.get('flag_reason') or '').lower() for k in ('critical','high')):
                for ci in range(7): set_cell_bg(t.rows[ri+1].cells[ci], 'F9D6D6')
    else:
        add_styled_para(doc, 'No flagged ads this week.', color=PALETTE['text_light'])
    doc.add_page_break()

    # -- 5. Organic Post Winners --
    add_section_heading(doc, '4. Organic Post Winners (Boost Candidates)')
    boosts = data.get('boost_candidates', [])[:5]
    if boosts:
        rows = [[(b.get('post_text') or '')[:80], str(b.get('engagement_score',0)),
                 str(b.get('likes',0)), str(b.get('comments',0)), str(b.get('shares',0))]
                for b in boosts]
        t = create_branded_table(doc, ['Post Text','Score','Likes','Comments','Shares'],
                                 rows, col_widths=[3.0, 0.8, 0.7, 0.7, 0.7])
        for ci in range(5): set_cell_bg(t.rows[1].cells[ci], PALETTE['light_gold'])
    else:
        add_styled_para(doc, 'No boost candidates identified.', color=PALETTE['text_light'])

    # -- 6. Week-over-Week Trend --
    add_section_heading(doc, '5. Week-over-Week Trend')
    trend = data.get('weekly_trend', [])
    if trend:
        rows, prev = [], {}
        def _d(cur, old, php=False):
            if old is None: return ''
            d = cur - old
            if d == 0: return ''
            lbl = format_php(abs(d)) if php else str(abs(d))
            return f" (up {lbl})" if d > 0 else f" (down {lbl})"
        for t in trend:
            cn, sp, pu, cp = t.get('campaign_name',''), t.get('spend',0), t.get('purchases',0), t.get('cpa',0)
            pv = prev.get(cn)
            rows.append([t.get('week',''), cn,
                f"{format_php(sp)}{_d(sp, pv and pv[0], True)}",
                f"{pu}{_d(pu, pv and pv[1])}",
                f"{format_php(cp)}{_d(cp, pv and pv[2], True)}"])
            prev[cn] = (sp, pu, cp)
        create_branded_table(doc, ['Week','Campaign','Spend','Purchases','CPA'],
                             rows, col_widths=[0.8, 1.8, 1.5, 0.9, 1.5])
    else:
        add_styled_para(doc, 'No trend data available.', color=PALETTE['text_light'])
    doc.add_page_break()

    # -- 7. Recommendations --
    add_section_heading(doc, '6. Recommendations')
    recs = data.get('recommendations', [])
    for i, rec in enumerate(recs, 1):
        pri = (rec.get('priority') or 'MEDIUM').upper()
        pc = PALETTE['accent'] if pri == 'HIGH' else (PALETTE['secondary'] if pri == 'MEDIUM' else PALETTE['primary'])
        p = doc.add_paragraph()
        _run(p, f'{i}. [{pri}] ', 10, True, pc)
        _run(p, rec.get('action', ''), 10, True)
        if rec.get('reasoning'):
            p2 = doc.add_paragraph(); p2.paragraph_format.left_indent = Pt(18)
            _run(p2, rec['reasoning'], 9, color=PALETTE['text_light'])
    if not recs:
        add_styled_para(doc, 'No recommendations generated.', color=PALETTE['text_light'])

    # -- 8. KPI Summary Footer --
    doc.add_paragraph()
    add_section_heading(doc, '7. KPI Summary', level=2)
    _kpi_bar(doc, [
        ('Total Spend', format_php(data.get('total_spend')), PALETTE['primary']),
        ('Total Purchases', str(data.get('total_purchases', 0)), PALETTE['secondary']),
        ('Avg CPA', format_php(data.get('avg_cpa')), PALETTE['accent']),
    ])
    doc.add_paragraph()
    fp = doc.add_paragraph(); fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _run(fp, '-- End of Report --', 9, italic=True, color=PALETTE['text_light'])
    fp2 = doc.add_paragraph(); fp2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _run(fp2, f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")} PHT', 8, color=PALETTE['text_light'])

    doc.save(output_path)
    return output_path


# -- Sample data & test -----------------------------------------------------

def _sample_data():
    C = lambda n,o,s,p,cpa,ctr,f: dict(campaign_name=n, objective=o, spend_7d=s,
        purchases_7d=p, cpa_7d=cpa, ctr_7d=ctr, frequency_7d=f, status='ACTIVE')
    return {
        'week_ending': '2026-03-08', 'total_spend': 27785.0, 'total_purchases': 198, 'avg_cpa': 140.33,
        'ai_analysis': ('Lookalike CPA dropped to PHP 128. Retargeting ROAS steady but frequency '
            'climbing (3.2) -- refresh creatives. Broad Interest CPA at PHP 245, consider pausing.'),
        'campaigns': [C('Lookalike 1%','CONVERSIONS',12500,98,127.55,2.34,1.8),
            C('Retargeting 7d','CONVERSIONS',8200,72,113.89,3.12,3.2),
            C('Broad Interest','CONVERSIONS',7085,28,253.04,0.89,2.1)],
        'flagged_ads': [{'ad_name':'Broad_Video_03','campaign_name':'Broad Interest',
            'flag_reason':'HIGH CPA (>200)','spend_7d':3200,'cpa_7d':320,'ctr_7d':0.45,'frequency':2.8}],
        'boost_candidates': [
            {'post_text':'FurMom/FurDads flex nyo mga bebe nyo!','engagement_score':5910,
             'likes':237,'comments':1876,'shares':45,'post_url':''},
            {'post_text':'TAG MO NA BEB!','engagement_score':2982,
             'likes':106,'comments':852,'shares':32,'post_url':''}],
        'weekly_trend': [
            {'week':'Feb 24','campaign_name':'Lookalike 1%','spend':11000,'purchases':85,'cpa':129.41},
            {'week':'Mar 03','campaign_name':'Lookalike 1%','spend':12500,'purchases':98,'cpa':127.55}],
        'recommendations': [
            {'priority':'HIGH','action':'Pause Broad_Video_03','reasoning':'CPA 2.3x above target.'},
            {'priority':'MEDIUM','action':'Boost FurMom flex post','reasoning':'1,876 comments organically.'}],
    }

if __name__ == '__main__':
    import os
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sample_weekly_report.docx')
    generate_weekly_report(_sample_data(), out)
    print(f'Sample report saved to: {out}')
