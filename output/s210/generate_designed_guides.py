"""BEI Receiving — guide generator.

Produces 3 DOCX (dropped Master Index + merged Cayla+Ian+Denise into one
Team Playbook per CEO directive 2026-04-21: keep it simple, focus on each
person's job, no tech jargon, no session history, consolidate internal docs).

Outputs:
  guides/1_3PL_DOCK_CARD.docx           — 3MD + Pinnacle dock staff (external, print)
  guides/2_SUPPLIER_FAQ.docx             — 98 BEI suppliers (external, email attach)
  guides/3_BEI_TEAM_PLAYBOOK.docx        — Cayla + Ian + Denise (internal)

Run:
    python output/s210/generate_designed_guides.py
"""
from __future__ import annotations

import pathlib
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'F:\Dropbox\Projects\BEI-ERP\.claude\skills\docx-designer-bei-erp\scripts')

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

from bei_docx import (
    PALETTE, add_bei_header, add_callout_box, add_run,
    hex_rgb, remove_cell_borders, set_cell_borders, set_cell_margins,
    set_cell_shading, set_paragraph_spacing, setup_doc,
)

GUIDES_DIR = pathlib.Path(r'F:\Dropbox\Projects\BEI-ERP-s210e\output\s210\guides')

# ---------------------------------------------------------------- URLs
FORM_URL = 'https://docs.google.com/forms/d/e/1FAIpQLSc3UC9f_3gefDYNgpOqNx7UCw_5BDrRh9T8-GQeyHHWSxdITw/viewform'
SHEET_A_URL = 'https://docs.google.com/spreadsheets/d/1dambmiLzSMWOQun7MCymK4nHpuqrarFCAOK0G9-6oIU/edit'
SHEET_B_URL = 'https://docs.google.com/spreadsheets/d/10fqnvF_uDl5ky3MkvXUmWvZ1fYat_p6XFGmVFc3vqrw/edit'
SHEET_C_URL = 'https://docs.google.com/spreadsheets/d/1_Ir5O5AW7hOjcvCTXsP06cF3sai9hcefDFrBOTRHOh0/edit'
SHEET_D_URL = 'https://docs.google.com/spreadsheets/d/1mbJiLW9M9e-AmrXSRRTtbRP-xKI16ah5rakOt6qv2As/edit'


# ---------------------------------------------------------------- helpers
def add_hyperlink(paragraph, url, text, color=PALETTE['primary'],
                  bold=False, size=None, underline=True):
    part = paragraph.part
    r_id = part.relate_to(url,
                          'http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink',
                          is_external=True)
    hyperlink = OxmlElement('w:hyperlink')
    hyperlink.set(qn('r:id'), r_id)
    new_run = OxmlElement('w:r')
    rPr = OxmlElement('w:rPr')
    col = OxmlElement('w:color'); col.set(qn('w:val'), color); rPr.append(col)
    if underline:
        u = OxmlElement('w:u'); u.set(qn('w:val'), 'single'); rPr.append(u)
    rFonts = OxmlElement('w:rFonts')
    rFonts.set(qn('w:ascii'), 'Calibri'); rFonts.set(qn('w:hAnsi'), 'Calibri')
    rPr.append(rFonts)
    if bold:
        b = OxmlElement('w:b'); rPr.append(b)
    if size:
        sz = OxmlElement('w:sz'); sz.set(qn('w:val'), str(int(size * 2))); rPr.append(sz)
    new_run.append(rPr)
    t = OxmlElement('w:t'); t.text = text; t.set(qn('xml:space'), 'preserve')
    new_run.append(t)
    hyperlink.append(new_run)
    paragraph._p.append(hyperlink)
    return hyperlink


def add_button(doc, text, url, width_inches=3.2, bg=None, fg=PALETTE['white'], size=14):
    bg = bg or PALETTE['primary']
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    table.columns[0].width = Inches(width_inches)
    cell = table.cell(0, 0); cell.width = Inches(width_inches)
    set_cell_shading(cell, bg)
    set_cell_borders(cell, bg, size='18')
    set_cell_margins(cell, top=140, bottom=140, left=200, right=200)
    p = cell.paragraphs[0]; p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_paragraph_spacing(p, 0, 0)
    add_hyperlink(p, url, text, color=fg.lstrip('#'), bold=True, size=size, underline=False)
    spacer = doc.add_paragraph(); set_paragraph_spacing(spacer, 0, 80)


def add_intro_callout(doc, title, body_lines):
    """Gold-outlined intro callout — one sentence about the person's job."""
    box = doc.add_table(rows=1, cols=1)
    box.alignment = WD_TABLE_ALIGNMENT.CENTER
    box.autofit = False
    box.columns[0].width = Inches(6.0)
    cell = box.cell(0, 0)
    set_cell_shading(cell, PALETTE['light_gold'])
    set_cell_borders(cell, PALETTE['secondary'], size='18')
    set_cell_margins(cell, top=180, bottom=180, left=240, right=240)
    p = cell.paragraphs[0]; set_paragraph_spacing(p, 0, 80)
    add_run(p, title, bold=True, size=14, color=PALETTE['secondary'])
    for line in body_lines:
        pp = cell.add_paragraph()
        set_paragraph_spacing(pp, 0, 60)
        add_run(pp, line, size=11, color=PALETTE['text'])
    doc.add_paragraph()


def add_numbered_step(doc, num, title, body_text):
    t = doc.add_table(rows=1, cols=2)
    t.alignment = WD_TABLE_ALIGNMENT.LEFT
    t.autofit = False
    t.columns[0].width = Inches(0.55)
    t.columns[1].width = Inches(5.45)
    circle = t.cell(0, 0)
    set_cell_shading(circle, PALETTE['primary'])
    set_cell_borders(circle, PALETTE['primary'], size='12')
    set_cell_margins(circle, top=60, bottom=60, left=0, right=0)
    cp = circle.paragraphs[0]; cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_run(cp, str(num), bold=True, size=15, color=PALETTE['white'])
    set_paragraph_spacing(cp, 0, 0)
    content = t.cell(0, 1)
    remove_cell_borders(content)
    set_cell_margins(content, top=40, bottom=40, left=140, right=40)
    tp = content.paragraphs[0]
    add_run(tp, title, bold=True, size=12, color=PALETTE['primary'])
    set_paragraph_spacing(tp, 0, 40)
    if body_text:
        bp = content.add_paragraph()
        add_run(bp, body_text, size=11, color=PALETTE['text'])
        set_paragraph_spacing(bp, 0, 60)
    spacer = doc.add_paragraph(); set_paragraph_spacing(spacer, 0, 60)


def add_section_header(doc, text, before=200):
    p = doc.add_paragraph()
    set_paragraph_spacing(p, before, 40)
    add_run(p, text, bold=True, size=14, color=PALETTE['primary'])
    hr = doc.add_table(rows=1, cols=1)
    hr.alignment = WD_TABLE_ALIGNMENT.LEFT
    hr.autofit = False
    hr.columns[0].width = Inches(6.0)
    c = hr.cell(0, 0)
    set_cell_shading(c, PALETTE['secondary'])
    set_cell_margins(c, top=0, bottom=0, left=0, right=0)
    hp = c.paragraphs[0]
    add_run(hp, ' ', size=1)
    set_paragraph_spacing(hp, 0, 0)
    doc.add_paragraph()


def add_subsection_header(doc, text):
    p = doc.add_paragraph()
    set_paragraph_spacing(p, 160, 40)
    add_run(p, text, bold=True, size=12, color=PALETTE['secondary'])


def add_zebra_table(doc, headers, rows, col_widths=None, first_col_bold=False):
    n = len(headers)
    t = doc.add_table(rows=1 + len(rows), cols=n)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    if col_widths:
        for i, w in enumerate(col_widths):
            t.columns[i].width = Inches(w)
    for i, h in enumerate(headers):
        c = t.cell(0, i)
        set_cell_shading(c, PALETTE['primary'])
        set_cell_borders(c, PALETTE['primary'], size='6')
        set_cell_margins(c, top=70, bottom=70, left=100, right=100)
        p = c.paragraphs[0]
        add_run(p, h, bold=True, size=10.5, color=PALETTE['white'])
        set_paragraph_spacing(p, 0, 0)
    for ri, row in enumerate(rows):
        bg = PALETTE['white'] if ri % 2 == 0 else PALETTE['bg_alt']
        for i, val in enumerate(row):
            c = t.cell(ri + 1, i)
            set_cell_shading(c, bg)
            set_cell_borders(c, PALETTE['border'], size='4')
            set_cell_margins(c, top=60, bottom=60, left=100, right=100)
            p = c.paragraphs[0]
            add_run(p, str(val), bold=(first_col_bold and i == 0),
                    size=10, color=PALETTE['text'])
            set_paragraph_spacing(p, 0, 0)
    doc.add_paragraph()


def add_title(doc, title, subtitle=None):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_paragraph_spacing(p, 0, 20)
    add_run(p, title, bold=True, size=22, color=PALETTE['primary'])
    if subtitle:
        s = doc.add_paragraph()
        s.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_paragraph_spacing(s, 0, 160)
        add_run(s, subtitle, italic=True, size=12, color=PALETTE['text_light'])
    else:
        doc.add_paragraph()


def add_body(doc, text, size=11, before=40, after=80):
    p = doc.add_paragraph()
    set_paragraph_spacing(p, before, after)
    add_run(p, text, size=size, color=PALETTE['text'])
    return p


def add_footer_note(doc, text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_paragraph_spacing(p, 240, 0)
    add_run(p, text, italic=True, size=9, color=PALETTE['text_light'])


# ------------------------------------------------------------------
# 1. 3PL Dock Card — for 3MD + Pinnacle dock staff
# ------------------------------------------------------------------

def build_supplier_faq():
    doc = Document()
    setup_doc(doc, font_size=11)
    add_bei_header(doc)

    add_title(
        doc,
        'Upload Your Sales Invoice',
        'Fastest path to getting paid — for BEI suppliers',
    )

    add_big_benefit_callout(
        doc,
        'Why this matters for you',
        [
            'BEI used to wait for paper SIs to travel from the 3PL warehouse '
            'to our accounting team before starting your payment — often adding '
            'weeks of delay.',
            '',
            'Upload your SI the moment you deliver. We match it automatically '
            'and queue your payment for release on your contracted Net terms '
            '(15 / 30 / 45 / 60) counted from delivery date. No more paper-chase.',
        ],
    )

    add_section_header(doc, 'How to upload', before=160)

    add_button(doc, 'Open Supplier Upload Form  →', FORM_URL, width_inches=3.8)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_paragraph_spacing(p, 0, 80)
    add_run(p, 'Or type in your browser:  ', size=10, color=PALETTE['text_light'])
    add_hyperlink(p, FORM_URL, FORM_URL, color=PALETTE['primary'], size=10)

    add_numbered_step(doc, 1, 'Pick the warehouse',
                      'Choose 3MD, Pinnacle, or Shaw BLVD — whichever warehouse you delivered to.')
    add_numbered_step(doc, 2, 'PO Number',
                      'Copy from your BEI Purchase Order (e.g. PO-2026-1234).')
    add_numbered_step(doc, 3, 'SI Number, SI Date, Amount',
                      'Type exactly as printed on your Sales Invoice.')
    add_numbered_step(doc, 4, 'Upload SI Copy',
                      'Tap the file button, pick your PDF or phone photo (max 10 MB).')
    add_numbered_step(doc, 5, 'Submit',
                      "That's it — 30 to 60 seconds. Your payment queue starts immediately.")

    add_section_header(doc, 'Frequently asked')

    faqs = [
        ('Can I upload a phone photo instead of a PDF?',
         'Yes. PDF, JPG, and PNG are all accepted up to 10 MB. Just make sure '
         'your SI number, date, line items, and totals are legible.'),
        ('Do I still send the paper SI?',
         'Yes — keep sending paper as you do today. Upload is in addition to '
         'paper, not a replacement. Upload is what speeds up your payment.'),
        ('How fast will I be paid?',
         'Per your contracted payment terms (Net 15, 30, 45, or 60) counted '
         'from the delivery date. Uploading removes the paper-chasing delays '
         'that used to push actual payment past your contract.'),
        ('My upload says "Orphan" — what does that mean?',
         'The system couldn\'t match your upload to a delivery yet. Usually: '
         '(1) you uploaded before the warehouse logged the delivery — we '
         'retry every minute, or (2) a typo in PO or SI — double-check '
         'against your SI. Your upload is never lost.'),
        ('Can I share the link with my team?',
         "Yes. Same link for everyone — share with anyone on your team who "
         'handles BEI invoices. Just don\'t upload the same SI twice.'),
        ('I made a typo — can I fix it?',
         'Submit again with the correct values. Add a note in the Notes field: '
         '"Correction for PO-xxxx SI-yyyy" so our team knows which submission '
         'to keep.'),
        ('Is my upload secure?',
         'Yes. Only BEI staff (accounting, IT, CEO) can see your PDF. It\'s '
         'stored in BEI\'s private Google Drive — not public, not indexed, '
         'not shared externally.'),
        ('What if my delivery covers multiple warehouses on the same day?',
         'Upload the SI once. Our system matches the same SI against every '
         'corresponding delivery record automatically.'),
        ('Where do I find the form link if I lose it?',
         'Bookmark this document, or email Cayla (cayla@bebang.ph) for it '
         'again. Same link always works.'),
    ]
    for q, a in faqs:
        qp = doc.add_paragraph()
        set_paragraph_spacing(qp, 80, 20)
        add_run(qp, q, bold=True, size=11.5, color=PALETTE['secondary'])
        ap = doc.add_paragraph()
        set_paragraph_spacing(ap, 0, 80)
        add_run(ap, a, size=11, color=PALETTE['text'])

    add_section_header(doc, 'Contact', before=160)
    add_body(doc,
             'Questions about the upload tool: sam@bebang.ph (subject "BEI Supplier SI Upload").')
    add_body(doc,
             'Payment status / AP queries: continue using your existing BEI contact.')

    add_footer_note(doc, 'Share this with anyone on your team who handles BEI invoices.  |  v2026-04-21')

    path = GUIDES_DIR / '3_SUPPLIER_FAQ.docx'
    doc.save(str(path))
    return path, 'BEI Supplier SI Upload — Fastest Path to Payment'


def build_dock_card():
    doc = Document()
    setup_doc(doc, font_size=11)
    add_bei_header(doc)

    add_title(doc, 'BEI Deliveries — Dock Card', 'For 3MD and Pinnacle dock staff')

    add_intro_callout(
        doc,
        'Your job in one line',
        [
            "Every BEI delivery you receive gets one row per item in your sheet. "
            "Log it the moment the truck leaves so BEI can pay the supplier without delay.",
        ],
    )

    add_section_header(doc, 'Open your sheet')

    p = doc.add_paragraph()
    set_paragraph_spacing(p, 40, 40)
    add_run(p, '3MD dock — ', bold=True, size=11)
    add_hyperlink(p, SHEET_A_URL, 'BEI 3MD Receiving Log 2026', size=11)

    p = doc.add_paragraph()
    set_paragraph_spacing(p, 0, 120)
    add_run(p, 'Pinnacle dock — ', bold=True, size=11)
    add_hyperlink(p, SHEET_B_URL, 'BEI Pinnacle Receiving Log 2026', size=11)

    add_section_header(doc, 'How to log a delivery')

    add_numbered_step(
        doc, 1, 'Click the Receipts tab',
        "Scroll to the first empty row. One row per item per delivery.",
    )
    add_numbered_step(
        doc, 2, "Don't touch column A — it fills itself",
        "Timestamp is filled automatically the moment you start typing in the row. "
        "Column A is locked so it can't be edited.",
    )
    add_numbered_step(
        doc, 3, 'Fill the 15 columns left to right',
        "RR number, PO number, Supplier name, Material code, Material description, "
        "Qty received, Unit of measure, SI number, Trucker name, Plate number, "
        "Production date, Expiration date, Received by, Notes.",
    )
    add_numbered_step(
        doc, 4, 'One truck, many items? Put header fields on the first row only',
        "PO number, Supplier, SI number, Trucker, Plate — type on line 1 only. "
        "Leave them blank on lines 2, 3, etc. Put the item details on each line.",
    )

    add_zebra_table(
        doc,
        ['RR#', 'PO#', 'Supplier', 'Material', 'Qty', 'Unit'],
        [
            ['RR-0041', 'PO-2026-1234', 'DIMAX', 'FLOUR-25KG', '10', 'BAG'],
            ['(blank)', '(blank)', '(blank)', 'SUGAR-50KG', '5', 'BAG'],
            ['(blank)', '(blank)', '(blank)', 'YEAST-1KG', '2', 'PC'],
        ],
        col_widths=[0.9, 1.3, 1.0, 1.4, 0.6, 0.7],
    )

    add_section_header(doc, 'Tell the supplier to upload their SI')

    add_body(
        doc,
        "After you sign the delivery receipt, hand the trucker this link (or point "
        "them at the QR poster on the wall). The supplier uploads their Sales "
        "Invoice here. Same link for every supplier, every delivery.",
    )

    add_button(doc, 'Open Supplier SI Upload form', FORM_URL, width_inches=3.5)

    add_section_header(doc, 'What to do when things are wrong')

    add_zebra_table(
        doc,
        ['Problem', 'What to do'],
        [
            ['Supplier name on the SI does not match the PO', 'Stop. Call Cayla before receiving the goods.'],
            ['Quantity on the truck is more than the PO balance', 'Stop. Call Cayla.'],
            ['Material you received is not on the PO', 'Stop. Call Cayla. Do not sign.'],
            ['Same delivery has different production dates', 'Log one row per production date.'],
            ['You logged a row with a typo', 'Edit the cell and retype. No need to delete rows.'],
            ['Column A stayed blank after you typed', 'Type anything in column B next to it — column A will fill in.'],
        ],
        col_widths=[2.3, 3.7],
    )

    add_section_header(doc, 'Who to call')

    add_zebra_table(
        doc,
        ['Question', 'Who to call'],
        [
            ['Any PO / supplier question during receiving', 'Cayla'],
            ['Sheet stopped working / cell shows error', 'Ian'],
            ['Delivery expected today that has not arrived by 15:00', 'Ian'],
        ],
        col_widths=[3.5, 2.5],
    )

    add_footer_note(doc, 'Print A4 • Laminate • Post at receiving station')

    path = GUIDES_DIR / '1_3PL_DOCK_CARD.docx'
    doc.save(str(path))
    return path


# ------------------------------------------------------------------
# 2. Supplier FAQ — for 98 BEI suppliers
# ------------------------------------------------------------------
def build_supplier_faq():
    doc = Document()
    setup_doc(doc, font_size=11)
    add_bei_header(doc)

    add_title(doc, 'BEI Supplier SI Upload', 'Faster payment, same paper process')

    add_intro_callout(
        doc,
        'Why upload your SI',
        [
            "Upload your Sales Invoice right after every delivery to BEI (or to our "
            "3PL warehouses at 3MD, Pinnacle, or Shaw). BEI starts your payment "
            "clock the moment we receive your upload — on your contracted terms "
            "(Net 15, 30, 45, or 60 days from delivery).",
            "",
            "Keep sending the paper SI as you do today. The upload is in addition, "
            "not instead.",
        ],
    )

    add_section_header(doc, 'Upload link')

    add_body(
        doc,
        "One link, every supplier, every delivery. Bookmark it. Same link works "
        "from any browser on any phone or laptop — no Google account needed.",
    )
    add_button(doc, 'Open BEI Supplier SI Upload', FORM_URL, width_inches=3.5)

    add_section_header(doc, 'What to type')

    add_numbered_step(
        doc, 1, 'Warehouse',
        "Choose 3MD, Pinnacle, or Shaw — whichever BEI warehouse you delivered to.",
    )
    add_numbered_step(
        doc, 2, 'PO Number',
        "Copy from your BEI Purchase Order (for example: PO-2026-1234).",
    )
    add_numbered_step(
        doc, 3, 'SI Number',
        "Type exactly as printed on your Sales Invoice.",
    )
    add_numbered_step(
        doc, 4, 'Material Code',
        "Pick from the dropdown — copy the Material Code from the PO line you are "
        "invoicing for. If your SI covers several line items, submit one upload per "
        "line item (same PO and SI number, different Material Code each time).",
    )
    add_numbered_step(
        doc, 5, 'Upload SI Copy',
        "Tap the file button. PDF, JPG, or PNG up to 10 MB. Phone photos are fine "
        "as long as the SI number, date, line items, and totals are legible.",
    )
    add_numbered_step(
        doc, 6, 'SI Date, Amount, Submit',
        "Type your SI date and total amount. Hit Submit. 30 to 60 seconds end to end.",
    )

    add_section_header(doc, 'Frequently asked')

    faqs = [
        ("Can I upload a phone photo instead of a PDF?",
         "Yes. PDF, JPG, and PNG up to 10 MB are all accepted."),
        ("Do I still send the paper SI?",
         "Yes. Keep sending paper as you do today. Upload is in addition, not a replacement."),
        ("How fast will I be paid?",
         "On your contracted payment terms counted from the delivery date. "
         "Uploading removes the paper-chasing delays that used to push actual "
         "payment past your contract."),
        ("I made a typo after submitting — can I fix it?",
         "Submit the form again with the correct values. In the Notes field, type "
         "\"Correction for PO-xxxx SI-yyyy\" so we know which submission to keep."),
        ("My SI has multiple items — do I upload once or several times?",
         "Submit one form per line item. Same PO number, same SI number, different "
         "Material Code each time. Each upload is matched to its own delivery line."),
        ("The Material Code I need is not in the dropdown",
         "Pick the closest match and type the correct code in the Notes field. "
         "BEI will add the missing code — it will appear at the next refresh."),
        ("Is my upload secure?",
         "Yes. Only BEI staff can see your PDF. Not public, not indexed, not shared externally."),
        ("Where do I find the form link if I lose it?",
         "Bookmark this document, or email Cayla at cayla@bebang.ph for it again. "
         "Same link always works."),
    ]

    for q, a in faqs:
        qp = doc.add_paragraph(); set_paragraph_spacing(qp, 80, 20)
        add_run(qp, q, bold=True, size=11.5, color=PALETTE['secondary'])
        ap = doc.add_paragraph(); set_paragraph_spacing(ap, 0, 80)
        add_run(ap, a, size=11, color=PALETTE['text'])

    add_section_header(doc, 'Contact')

    add_body(
        doc,
        "Questions about the upload tool: sam@bebang.ph (subject \"BEI Supplier SI Upload\").",
    )
    add_body(
        doc,
        "Questions about your PO or payment status: your usual BEI contact or "
        "cayla@bebang.ph.",
    )

    add_footer_note(doc, 'Share this with anyone on your team who handles BEI invoices.')

    path = GUIDES_DIR / '2_SUPPLIER_FAQ.docx'
    doc.save(str(path))
    return path


# ------------------------------------------------------------------
# 3. BEI Team Playbook — Cayla + Ian + Denise (consolidated)
# ------------------------------------------------------------------
def build_team_playbook():
    doc = Document()
    setup_doc(doc, font_size=11)
    add_bei_header(doc)

    add_title(
        doc,
        'BEI Receiving — Team Playbook',
        'Who does what, when, in which sheet',
    )

    add_intro_callout(
        doc,
        'How this works',
        [
            "The warehouse staff at 3MD and Pinnacle log every delivery in their "
            "sheet. Suppliers upload their Sales Invoice through one shared form. "
            "BEI matches the two automatically so we can pay the supplier on their "
            "contracted terms.",
            "",
            "Three BEI people keep this pipeline clean: Cayla (suppliers), Ian "
            "(daily ops), Denise (finance). Each section below is that person's job.",
        ],
    )

    # Sheet quick access
    add_section_header(doc, 'Sheets the team uses')

    p = doc.add_paragraph(); set_paragraph_spacing(p, 40, 40)
    add_run(p, 'BEI Receiving Master 2026 — ', bold=True, size=11)
    add_hyperlink(p, SHEET_C_URL, 'open', size=11)
    add_run(p, '  (the main dashboard + match queues — everyone opens this)', size=10, color=PALETTE['text_light'])

    p = doc.add_paragraph(); set_paragraph_spacing(p, 0, 40)
    add_run(p, 'BEI 3MD Receiving Log 2026 — ', bold=True, size=11)
    add_hyperlink(p, SHEET_A_URL, 'open', size=11)
    add_run(p, '  (3MD dock logs deliveries here)', size=10, color=PALETTE['text_light'])

    p = doc.add_paragraph(); set_paragraph_spacing(p, 0, 40)
    add_run(p, 'BEI Pinnacle Receiving Log 2026 — ', bold=True, size=11)
    add_hyperlink(p, SHEET_B_URL, 'open', size=11)
    add_run(p, '  (Pinnacle dock logs deliveries here)', size=10, color=PALETTE['text_light'])

    p = doc.add_paragraph(); set_paragraph_spacing(p, 0, 40)
    add_run(p, 'BEI Shaw Transitional Receiving — ', bold=True, size=11)
    add_hyperlink(p, SHEET_D_URL, 'open', size=11)
    add_run(p, '  (Shaw dock logs deliveries here — moves to 3MD eventually)', size=10, color=PALETTE['text_light'])

    p = doc.add_paragraph(); set_paragraph_spacing(p, 0, 120)
    add_run(p, 'BEI Supplier SI Upload form — ', bold=True, size=11)
    add_hyperlink(p, FORM_URL, 'open', size=11)
    add_run(p, '  (suppliers use this link; same link for all 98 suppliers)', size=10, color=PALETTE['text_light'])

    # ============ CAYLA SECTION ============
    add_section_header(doc, 'Cayla — Supplier rollout and upkeep')

    add_subsection_header(doc, 'Your job in one line')
    add_body(
        doc,
        "Get all 98 BEI suppliers uploading their Sales Invoice through the form, "
        "then keep them uploading. The more suppliers uploading, the faster "
        "payments go out, the happier our suppliers stay.",
    )

    add_subsection_header(doc, 'Rollout in 4 waves')

    add_zebra_table(
        doc,
        ['Wave', 'Who', 'Timing', 'Approach'],
        [
            ['1', 'Top 10 Tier A suppliers by volume', 'Week 1',
             'Individual emails. 48h follow-up. Personal call on any non-response.'],
            ['2', 'Rest of Tier A (about 50–70)', 'Week 2',
             'Batch email. Expect 60–70% response rate.'],
            ['3', 'Tier B and C', 'Week 3–4',
             'Can batch. One follow-up after a week.'],
            ['4', 'Stragglers', 'Week 5+',
             'Direct call to anyone who has not uploaded once.'],
        ],
        col_widths=[0.6, 2.0, 0.9, 2.7],
        first_col_bold=True,
    )

    add_subsection_header(doc, 'Email to send to each supplier')

    add_callout_box(
        doc,
        [
            ('Subject: BEI Supplier SI Upload — fastest path to payment', True, 11),
            ('', False, 1),
            ('Hi [Supplier Contact Name],', False, 11),
            ('', False, 1),
            ("BEI has moved to a new process that will get your invoices paid "
             "faster. For every delivery you make to BEI or our 3PL warehouses "
             "(3MD, Pinnacle, Shaw), please upload your Sales Invoice at the "
             "link below right after delivery.", False, 10.5),
            ('', False, 1),
            ('Upload link (bookmark this — same link every delivery):', False, 10.5),
            (FORM_URL, False, 10),
            ('', False, 1),
            ('Attached FAQ answers common questions.', False, 10.5),
            ('', False, 1),
            ('— Cayla | cayla@bebang.ph', True, 10.5),
        ],
        bg_color=PALETTE['bg_alt'],
        border_color=PALETTE['primary'],
    )

    add_body(
        doc,
        "Always attach the Supplier FAQ document to every rollout email. "
        "The FAQ answers most supplier objections before they ask.",
        before=0,
    )

    add_subsection_header(doc, 'How to track adoption')

    add_body(
        doc,
        "Every Monday, open the BEI Receiving Master 2026 sheet and go to the "
        "Dashboard tab. Read the \"SI match rate\" KPI. Target: above 60% by end "
        "of week 2, above 80% by end of week 4.",
    )

    add_body(
        doc,
        "For non-uploaders: in the same sheet, go to the All Receipts Consolidated "
        "tab. Filter SI Matched = FALSE. Group by Supplier. Call the top 5 "
        "non-uploaders each week until they are live.",
    )

    add_subsection_header(doc, 'Common objections and replies')

    add_zebra_table(
        doc,
        ['Supplier says', 'You say'],
        [
            ['"I don\'t have a scanner"', 'Phone photo is fine. PDF, JPG, and PNG are all accepted.'],
            ['"Our accounts staff don\'t use Gmail"', 'Form works in any browser. No Google account needed.'],
            ['"Can I still send paper SI?"', 'Yes. Keep doing it. Upload is in addition, not instead.'],
            ['"My PO number is long / has dashes"', 'Copy-paste from the PO exactly as printed. Form accepts any string.'],
            ['"What if I make a typo after submitting?"', 'Upload again. Type "Correction for PO-xxxx SI-yyyy" in Notes.'],
            ['"I\'m worried about my PDF being seen"', 'Only BEI staff have access. Not public, not indexed.'],
            ['"How do you know it\'s my company?"', 'We match the PO Number you type to your PO in our system. No supplier list exposed.'],
        ],
        col_widths=[2.3, 3.7],
    )

    add_subsection_header(doc, 'Who you escalate to')

    add_zebra_table(
        doc,
        ['Issue', 'Who'],
        [
            ['Tier A supplier refusing to adopt', 'Ian, then Sam'],
            ['Supplier saying they have not been paid after upload', 'Luwi (Accounts Payable)'],
            ['Wrong Material Code in dropdown', 'Ian (will add to the master list)'],
        ],
        col_widths=[3.5, 2.5],
        first_col_bold=True,
    )

    doc.add_page_break()

    # ============ IAN SECTION ============
    add_section_header(doc, 'Ian — Daily receiving ops', before=0)

    add_subsection_header(doc, 'Your job in one line')
    add_body(
        doc,
        "Keep the receiving pipeline clean every day. Anything unresolved — "
        "orphan supplier uploads, stale deliveries, variance queue items — "
        "delays a supplier payment. Fix them as they appear.",
    )

    add_subsection_header(doc, 'Every morning (15 minutes)')

    add_numbered_step(
        doc, 1, 'Open the BEI Receiving Master 2026 Dashboard',
        "Scan today's receipts per warehouse, SI match rate, stale delivery "
        "count, and pending match queue depth. If anything shows \"#N/A\" or "
        "\"#ERROR\", call Cayla or Sam.",
    )
    add_numbered_step(
        doc, 2, 'Clear the Match Queue tab',
        "Each row is a supplier SI upload that did not auto-match to a "
        "delivery. Look at the PO and SI number. Either find the matching "
        "delivery (fix typo or link manually) or dismiss the row with a reason.",
    )
    add_numbered_step(
        doc, 3, 'Resolve the Variance Queue tab',
        "Each row is a delivery with a problem (over/short quantity, aged > 72h "
        "with no SI upload, supplier mismatch). Decide: accept, reject, or "
        "ask the supplier. Mark the row Resolved with a note.",
    )

    add_subsection_header(doc, 'Every afternoon (10 minutes)')

    add_numbered_step(
        doc, 1, 'Confirm today\'s expected deliveries landed',
        "In the BEI Receiving Master sheet, open the Full Open POs tab. "
        "Filter Delivery Needed By = today. For any PO not yet in the "
        "Consolidated Receipts tab, call the supplier.",
    )
    add_numbered_step(
        doc, 2, 'Scan the SCM Chat space',
        "Glance at the day's automated notifications. Unusually high quantities, "
        "off-hours deliveries, or repeated validation failures are patterns "
        "worth a call.",
    )

    add_subsection_header(doc, 'Every Monday morning')

    add_numbered_step(
        doc, 1, 'Supplier adoption review',
        "Open the Consolidated Receipts tab. Compute per-supplier SI match "
        "rate for the last 7 days. Hand the top 5 non-adopters to Cayla so "
        "she can chase them.",
    )
    add_numbered_step(
        doc, 2, 'Material Code coverage check',
        "If suppliers keep writing correct Material Codes in Notes because "
        "the dropdown is missing them, pass the list to Cayla so procurement "
        "can add the codes to the master Item List.",
    )

    add_subsection_header(doc, 'Health thresholds — when to act')

    add_zebra_table(
        doc,
        ['Number', 'Healthy', 'Yellow', 'Red — act now'],
        [
            ['Today\'s receipts per warehouse', 'Matches expected', '1–2 short', 'Zero — call the 3PL to check access'],
            ['SI match rate', 'above 80%', '60–80%', 'below 60% — push Cayla to chase non-uploaders'],
            ['Stale delivery count (over 72h, no SI)', 'under 5', '5–20', 'over 20 — sit down with Cayla'],
            ['Pending match queue depth', 'under 5', '5–15', 'over 15 — you have a backlog; block 30 minutes to clear it'],
        ],
        col_widths=[1.9, 1.1, 1.1, 1.9],
        first_col_bold=True,
    )

    add_subsection_header(doc, 'Who you escalate to')

    add_zebra_table(
        doc,
        ['Issue', 'Who'],
        [
            ['Supplier refusing to upload', 'Cayla'],
            ['PO issue (wrong balance, closed PO, wrong routing)', 'Mae, then Luwi'],
            ['Denise\'s reconciliation finds a mismatch', 'Denise (handle together)'],
            ['Sheet formula broken or data looks off', 'Sam'],
        ],
        col_widths=[3.5, 2.5],
        first_col_bold=True,
    )

    doc.add_page_break()

    # ============ DENISE SECTION ============
    add_section_header(doc, 'Denise — Finance reconciliation', before=0)

    add_intro_callout(
        doc,
        'You take over from Juanna on 2026-04-28',
        [
            "Juanna's last day is 2026-04-27. During that week, sit with her and "
            "walk through one day's reconciliation together before she leaves.",
        ],
    )

    add_subsection_header(doc, 'Your job in one line')
    add_body(
        doc,
        "Confirm that every delivery with a matching supplier SI upload also has "
        "the correct entry in the BEI accounting system, and release payment on "
        "the supplier's contracted Net terms — never later.",
    )

    add_subsection_header(doc, 'Every day (30 minutes)')

    add_numbered_step(
        doc, 1, 'Confirm yesterday\'s receipts match the accounting system',
        "Open the BEI Receiving Master 2026 sheet, Consolidated Receipts tab. "
        "Row count for yesterday vs Purchase Receipts posted yesterday in the "
        "accounting system. They should match (minus variance rows). If the gap "
        "is more than 5%, flag it. Do not hand-fix in the accounting system — "
        "find the root cause in the sheet first.",
    )
    add_numbered_step(
        doc, 2, 'Verify payment requests match supplier uploads',
        "For every SI Matched = TRUE row more than 1 day old, check: "
        "the matching payment request exists, its amount matches the SI upload, "
        "and the scheduled pay date equals the delivery date plus the supplier's "
        "contracted Net terms. Mismatch → correct it, write a note, ping Luwi.",
    )
    add_numbered_step(
        doc, 3, 'Chase deliveries older than 3 days with no SI upload',
        "Filter SI Matched = FALSE and delivery date older than 3 days. "
        "Check the Match Queue tab for typos. If there is genuinely no upload, "
        "email the supplier (copy Cayla). Never release payment without a "
        "matching SI upload.",
    )

    add_subsection_header(doc, 'Every Monday')

    add_numbered_step(
        doc, 1, 'Sheet-vs-accounting reconciliation',
        "Sum the Amount column on last week's SI Matched = TRUE rows. "
        "That total should match the week's stock-in-hand journal entries.",
    )
    add_numbered_step(
        doc, 2, 'Withholding and VAT spot-check',
        "Pick 3 payment requests at random. Confirm the system applied the "
        "supplier's EWT rate and VAT registration status correctly.",
    )

    add_subsection_header(doc, 'Every month (first 3 business days)')

    add_numbered_step(
        doc, 1, 'BIR Form 2307 reconciliation',
        "The total EWT withheld in the accounting system should equal the total "
        "EWT on BIR Form 2307 issued. Any gap usually traces to manual overrides "
        "on a payment request.",
    )
    add_numbered_step(
        doc, 2, 'Paper SI spot-check',
        "Pick 10 random rows from the Supplier SI Uploads tab. Click the Drive "
        "link to confirm the PDF opens, then cross-check against the paper SI "
        "on file.",
    )

    add_subsection_header(doc, 'Hard rules — will bite you otherwise')

    add_zebra_table(
        doc,
        ['Rule', 'What it means'],
        [
            ['Payment releases on delivery + SI upload',
             "Do not wait for paper SI to arrive before queuing payment. That is the old workflow."],
            ['Disputes happen AFTER payment',
             "Short delivery or defective goods? Pay first on the delivery + SI, raise the dispute after. Never withhold payment to force the issue."],
            ['Approval chain while CFO seat is vacant',
             "Payment requests up to 1 million PHP: Luwi prepares, Mae approves. Over 1 million PHP: Luwi prepares, Mae approves, then Sam."],
            ['Never use an Internal Customer for a supplier invoice',
             "Internal Customers are for inter-BEI-entity labor journals only. If a supplier invoice points to an Internal Customer, stop and ask Sam."],
        ],
        col_widths=[2.3, 3.7],
        first_col_bold=True,
    )

    add_subsection_header(doc, 'What you need to take over from Juanna')

    add_body(doc, 'Before 2026-04-27, get from Juanna:', after=20)
    add_body(doc, '• Finance login to the accounting system (tied to your employee account).', before=0, after=20)
    add_body(doc, '• Editor access to the BEI Receiving Master 2026 sheet (ask Cayla or Ian if needed).', before=0, after=20)
    add_body(doc, '• Read access to the Procurement sheet (Ashish will share).', before=0, after=20)
    add_body(doc, '• BIR eFPS credentials (Juanna hands these over directly).', before=0, after=40)

    add_subsection_header(doc, 'Who you escalate to')

    add_zebra_table(
        doc,
        ['Issue', 'Who'],
        [
            ['Accounting system missing a receipt that is in the sheet', 'Ashish'],
            ['Payment amount does not match supplier upload', 'Luwi'],
            ['Supplier payment terms look wrong', 'Cayla'],
            ['BIR interpretation question', 'Sam (until a CFO is hired)'],
        ],
        col_widths=[3.5, 2.5],
        first_col_bold=True,
    )

    add_footer_note(doc, 'Version 2026-04-21 • Juanna last day 2026-04-27 • Denise effective 2026-04-28')

    path = GUIDES_DIR / '3_BEI_TEAM_PLAYBOOK.docx'
    doc.save(str(path))
    return path


def main():
    GUIDES_DIR.mkdir(parents=True, exist_ok=True)
    built = []
    for name, fn in [
        ('3PL_DOCK_CARD', build_dock_card),
        ('SUPPLIER_FAQ', build_supplier_faq),
        ('BEI_TEAM_PLAYBOOK', build_team_playbook),
    ]:
        path = fn()
        built.append((name, path, path.stat().st_size))
        print(f'[OK] {name}: {path.name} ({path.stat().st_size} bytes)')
    return built


if __name__ == '__main__':
    main()
