"""Builds the Phase D invoice fixture set — FICTIONAL companies, people and
numbers, deliberately varied so invoice@1 is not tuned to one template:

    f1_digital_simple.pdf     qty-first table, "Invoice #", side-by-side
                              Bill To / Ship To, $ amounts, no currency label
    f2_scanned_services.pdf   stacked labels, ruled table, "Amount Due",
                              rasterized and skewed ~0.7° (OCR + deskew)
    f3_multipage_parts.pdf    3 pages, whitespace table, header repeated per
                              page, wrapped descriptions, "Continued…"
    f4_po_backed_lab.pdf      PO / receipt / contract refs, PO Line column,
                              Vendor ID, Remit To
    f5_complex_charges.pdf    EUR, discount, freight, handling, surcharge,
                              VAT, amount paid, balance due
    f6_html_software.html     dl header, thead/tbody/tfoot, GBP

Run: python tests/fixtures/invoices/build_invoice_fixtures.py
"""

from __future__ import annotations

import io
from pathlib import Path

import fitz

OUT = Path(__file__).parent


# Unicode TrueType fonts for layouts that need characters outside the
# base-14 PDF fonts' encoding (e.g. the euro sign).
_TTF = {"regular": "C:/Windows/Fonts/arial.ttf", "bold": "C:/Windows/Fonts/arialbd.ttf"}


class Page:
    def __init__(self, page: fitz.Page, unicode_fonts: bool = False):
        self.page = page
        self.unicode = unicode_fonts
        if unicode_fonts:
            page.insert_font(fontname="uar", fontfile=_TTF["regular"])
            page.insert_font(fontname="uarb", fontfile=_TTF["bold"])
            self._fonts = {False: fitz.Font(fontfile=_TTF["regular"]), True: fitz.Font(fontfile=_TTF["bold"])}

    def _name(self, bold: bool) -> str:
        if self.unicode:
            return "uarb" if bold else "uar"
        return "hebo" if bold else "helv"

    def t(self, x, y, s, size=9.5, bold=False):
        self.page.insert_text((x, y), s, fontsize=size, fontname=self._name(bold))

    def r(self, x, y, s, size=9.5, bold=False):
        """Right-aligned at x."""
        if self.unicode:
            width = self._fonts[bold].text_length(s, fontsize=size)
        else:
            width = fitz.get_text_length(s, fontname=self._name(bold), fontsize=size)
        self.t(x - width, y, s, size, bold)

    def line(self, x0, y0, x1, y1, width=0.6):
        self.page.draw_line((x0, y0), (x1, y1), width=width)


def money(value: float, symbol: str = "") -> str:
    return f"{symbol}{value:,.2f}"


# --- F1: clean digital --------------------------------------------------------


def f1() -> fitz.Document:
    doc = fitz.open()
    p = Page(doc.new_page(width=612, height=792))
    p.t(40, 58, "Brightline Office Supply Co.", 15, bold=True)
    p.t(40, 74, "2250 Commerce Drive, Unit 4")
    p.t(40, 87, "Dayton, OH 45414")
    p.t(40, 100, "orders@brightline-supply.example  |  (937) 555-0118")
    p.t(430, 58, "INVOICE", 20, bold=True)
    for y, (label, value) in zip(
        (84, 98, 112, 126),
        [("Invoice #:", "BOS-24-1187"), ("Date:", "02/06/2026"),
         ("Payment Due:", "02/20/2026"), ("Terms:", "Net 14")],
    ):
        p.t(400, y, label, bold=True)
        p.t(480, y, value)
    p.t(40, 150, "Bill To:", bold=True)
    for i, s in enumerate(["Riverbend Dental Group", "Attn: Accounts Payable", "118 Mill Street", "Columbus, OH 43215"]):
        p.t(40, 164 + 13 * i, s)
    p.t(300, 150, "Ship To:", bold=True)
    for i, s in enumerate(["Riverbend Dental Group - Clinic 2", "4410 Olentangy River Rd", "Columbus, OH 43214"]):
        p.t(300, 164 + 13 * i, s)
    cols = [(40, "QTY"), (80, "ITEM"), (150, "DESCRIPTION"), (470, "UNIT PRICE"), (560, "LINE TOTAL")]
    y = 240
    for x, h in cols:
        (p.r if x >= 470 else p.t)(x, y, h, bold=True)
    p.line(40, y + 4, 572, y + 4)
    rows = [
        (10, "PPR-500", "Copy paper, letter, 500 sheets", 6.49),
        (4, "TNR-26A", "Toner cartridge, black", 89.99),
        (2, "CHR-ERG", "Ergonomic task chair", 214.00),
        (25, "PEN-BLU", "Ballpoint pens, blue, box of 12", 3.75),
        (1, "SHF-5T", "Steel shelving unit, 5 tier", 139.50),
    ]
    subtotal = 0.0
    for qty, item, desc, price in rows:
        y += 17
        amount = round(qty * price, 2)
        subtotal += amount
        p.t(40, y, str(qty)); p.t(80, y, item); p.t(150, y, desc)
        p.r(470, y, money(price, "$")); p.r(560, y, money(amount, "$"))
    tax = round(subtotal * 0.0825, 2)
    y += 36
    for label, value in (("Subtotal", subtotal), ("Sales Tax (8.25%)", tax), ("TOTAL", subtotal + tax)):
        p.t(400, y, label + ":", bold=True)
        p.r(560, y, money(value, "$"))
        y += 15
    p.t(40, 740, "Thank you for your business. Please reference the invoice number with your payment.", 8)
    return doc


# --- F2: scanned services (ruled table, skewed raster) -------------------------


def _f2_native() -> fitz.Document:
    doc = fitz.open()
    p = Page(doc.new_page(width=612, height=792))
    p.t(40, 60, "HARBOR MARINE SERVICES LLC", 14, bold=True)
    p.t(40, 76, "Pier 9, 300 Wharf Road, Norfolk, VA 23510")
    p.t(40, 89, "Tel (757) 555-0164   billing@harbormarine.example")
    p.t(420, 60, "SERVICE INVOICE", 13, bold=True)
    for y, (label, value) in zip(
        (130, 145, 160, 175),
        [("Invoice Number:", "HMS-30912"), ("Invoice Date:", "03/03/2026"),
         ("Customer ID:", "C-4471"), ("Due Date:", "04/02/2026")],
    ):
        p.t(40, y, label, bold=True)
        p.t(150, y, value)
    p.t(330, 130, "Customer:", bold=True)
    for i, s in enumerate(["Coastal Ferry Authority", "12 Terminal Way", "Hampton, VA 23669"]):
        p.t(330, 145 + 15 * i, s)
    p.t(40, 205, "All amounts in USD.", 9)
    # Ruled table.
    xs = [40, 80, 360, 430, 500, 572]
    headers = ["Line", "Description", "Hours", "Rate", "Amount"]
    rows = [
        ("1", "Hull inspection and report", 6.0, 95.00),
        ("2", "Engine service, twin diesel", 14.5, 110.00),
        ("3", "Bilge pump replacement", 3.0, 95.00),
        ("4", "Sea trial and sign-off", 2.0, 120.00),
    ]
    top, row_h = 222, 20
    for i in range(len(rows) + 2):
        p.line(xs[0], top + i * row_h, xs[-1], top + i * row_h)
    for x in xs:
        p.line(x, top, x, top + (len(rows) + 1) * row_h)
    for j, h in enumerate(headers):
        p.t(xs[j] + 4, top + 14, h, bold=True)
    subtotal = 0.0
    for i, (line, desc, hours, rate) in enumerate(rows, start=1):
        y = top + i * row_h + 14
        amount = round(hours * rate, 2)
        subtotal += amount
        p.t(xs[0] + 4, y, line); p.t(xs[1] + 4, y, desc)
        p.r(xs[3] - 4, y, f"{hours:.1f}"); p.r(xs[4] - 4, y, money(rate)); p.r(xs[5] - 4, y, money(amount))
    tax = round(subtotal * 0.053, 2)
    y = top + (len(rows) + 1) * row_h + 30
    for label, value in (("Subtotal:", subtotal), ("Tax 5.3%:", tax), ("Amount Due:", subtotal + tax)):
        p.t(400, y, label, bold=True)
        p.r(572, y, money(value))
        y += 16
    p.t(40, 700, "Remit payment within 30 days. Late balances accrue 1.5% monthly.", 8.5)
    return doc


def f2() -> fitz.Document:
    from PIL import Image

    native = _f2_native()
    pix = native[0].get_pixmap(dpi=200)
    image = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
    image = image.rotate(0.7, expand=False, fillcolor=(255, 255, 255), resample=Image.BICUBIC)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_image(page.rect, stream=buffer.getvalue())
    return doc


# --- F3: multi-page, whitespace table, wrapped descriptions -----------------------

F3_LINES = [
    ("10", "HB-1022", "Hex bolt M10 x 60, zinc plated", 200, "EA", 0.42),
    ("20", "NW-1010", "Nylon lock washer M10", 200, "EA", 0.09),
    ("30", "BR-6204", "Deep groove ball bearing 6204-2RS, sealed both sides, for conveyor idler rollers", 24, "EA", 6.85),
    ("40", "VB-A48", "V-belt A48", 12, "EA", 11.20),
    ("50", "CP-0750", "Pipe coupling 3/4 in", 40, "EA", 3.15),
    ("60", "GS-0250", "Gasket sheet, nitrile, 1/16 in x 12 in x 12 in, oil resistant, cut to order", 10, "SH", 18.40),
    ("70", "HC-0500", "Hose clamp 1/2 in", 100, "EA", 0.65),
    ("80", "LB-EP2", "Lithium grease EP2, 14 oz", 24, "TB", 7.95),
    ("90", "SW-3PH", "Motor starter switch 3-phase", 2, "EA", 184.00),
    ("100", "CB-10A", "Circuit breaker 10A", 6, "EA", 22.50),
    ("110", "TR-0240", "Control transformer 240/24V", 1, "EA", 96.00),
    ("120", "FS-3A", "Fuse 3A, time delay", 50, "EA", 1.20),
    ("130", "SP-0612", "Coil spring 6 x 12 mm, stainless steel, heavy duty, for pressure relief valve assemblies", 30, "EA", 2.35),
    ("140", "RV-0150", "Pressure relief valve 150 psi", 4, "EA", 38.75),
    ("150", "GA-0100", "Pressure gauge 0-100 psi", 4, "EA", 24.10),
    ("160", "TF-0500", "PTFE thread tape 1/2 in", 60, "RL", 0.85),
    ("170", "OR-KIT", "O-ring assortment kit", 3, "KT", 42.00),
    ("180", "CH-40R", "Roller chain #40, 10 ft", 5, "EA", 31.60),
    ("190", "SK-40B", "Sprocket #40, 18 tooth, bored", 6, "EA", 16.90),
    ("200", "KY-0316", "Keystock 3/16 in x 12 in", 10, "EA", 2.10),
    ("210", "BG-7210", "Angular contact bearing 7210, matched pair, precision grade for spindle rebuild", 2, "PR", 212.00),
    ("220", "SL-0040", "Shaft seal 40 x 62 x 8", 8, "EA", 5.40),
    ("230", "CL-FLX", "Flexible jaw coupling L100", 2, "EA", 58.00),
    ("240", "SP-ELM", "Spider element L100, urethane", 4, "EA", 9.80),
    ("250", "AB-3322", "Anchor bolt 3/8 x 3", 80, "EA", 0.55),
    ("260", "LT-LED", "LED machine light 24V", 3, "EA", 67.00),
    ("270", "CT-1450", "Cable tie 14 in, UV black, bag of 100", 5, "BG", 12.40),
    ("280", "WR-1414", "Wire rope 1/4 in, galvanized, 7x19 construction, cut length 50 ft", 2, "EA", 74.25),
]


# Additional ordinary catalogue lines so pages 1-2 fill to the bottom, as a
# real multi-page invoice does before it continues.
_SIZES = ["M6 x 20", "M6 x 30", "M8 x 25", "M8 x 40", "M10 x 30", "M12 x 50", "M12 x 80", "1/4-20 x 1", "5/16-18 x 1-1/2", "3/8-16 x 2", "1/2-13 x 3"]
F3_LINES = F3_LINES + [
    (str(290 + 10 * i), f"SC-{1100 + i}", f"Socket head cap screw {size}, alloy steel", 50 + 10 * (i % 4), "EA", round(0.18 + 0.07 * i, 2))
    for i, size in enumerate(_SIZES)
] + [
    (str(400 + 10 * i), f"FW-{2200 + i}", f"Flat washer {size.split(' x ')[0]}, hardened", 100, "EA", round(0.05 + 0.02 * i, 2))
    for i, size in enumerate(_SIZES)
]


def f3() -> fitz.Document:
    doc = fitz.open()
    cols = {"line": 40, "item": 78, "desc": 150, "qty": 430, "uom": 445, "price": 515, "amount": 572}
    per_page = [26, 17, 7]
    start = 0
    subtotal = 0.0
    for page_index, count in enumerate(per_page):
        p = Page(doc.new_page(width=612, height=792))
        p.t(40, 52, "Summit Industrial Parts, Inc.", 14, bold=True)
        p.t(40, 67, "8800 Foundry Lane, Pueblo, CO 81001  -  accounts@summitparts.example")
        p.t(400, 52, "Invoice No.:", bold=True); p.t(470, 52, "SIP-88410")
        p.r(572, 67, f"Page {page_index + 1} of {len(per_page)}", 8.5)
        y = 90
        if page_index == 0:
            for label, value in (("Invoice Date:", "01/28/2026"), ("Due Date:", "02/27/2026"),
                                 ("Customer No.:", "CU-20931"), ("Payment Terms:", "Net 30")):
                p.t(400, y, label, bold=True); p.t(480, y, value)
                y += 13
            p.t(40, 90, "Bill To:", bold=True)
            for i, s in enumerate(["Front Range Aggregates LLC", "PO Box 2201", "Pueblo, CO 81002"]):
                p.t(40, 103 + 13 * i, s)
            y = 170
        header_y = y
        p.t(cols["line"], header_y, "Line", bold=True)
        p.t(cols["item"], header_y, "Item", bold=True)
        p.t(cols["desc"], header_y, "Description", bold=True)
        p.r(cols["qty"], header_y, "Qty", bold=True)
        p.t(cols["uom"], header_y, "UOM", bold=True)
        p.r(cols["price"], header_y, "Unit Price", bold=True)
        p.r(cols["amount"], header_y, "Amount", bold=True)
        p.line(40, header_y + 4, 572, header_y + 4)
        y = header_y + 18
        for line, item, desc, qty, uom, price in F3_LINES[start:start + count]:
            amount = round(qty * price, 2)
            subtotal += amount
            words = desc.split()
            first, rest = [], []
            for word in words:
                (first if fitz.get_text_length(" ".join(first + [word]), fontsize=9.5) < 245 and not rest else rest).append(word)
            p.t(cols["line"], y, line); p.t(cols["item"], y, item); p.t(cols["desc"], y, " ".join(first))
            p.r(cols["qty"], y, str(qty)); p.t(cols["uom"], y, uom)
            p.r(cols["price"], y, money(price)); p.r(cols["amount"], y, money(amount))
            if rest:
                y += 12
                p.t(cols["desc"], y, " ".join(rest))
            y += 17
        start += count
        if page_index < len(per_page) - 1:
            p.t(40, 752, "Continued on next page", 8.5)
    freight, tax = 145.00, round(subtotal * 0.049, 2)
    y += 20
    for label, value in (("Subtotal:", subtotal), ("Freight:", freight), ("Sales Tax 4.9%:", tax),
                         ("Invoice Total:", subtotal + freight + tax), ("Amount Due:", subtotal + freight + tax)):
        p.t(400, y, label, bold=True); p.r(572, y, money(value))
        y += 15
    return doc


# --- F4: PO-backed ---------------------------------------------------------------


def f4() -> fitz.Document:
    doc = fitz.open()
    p = Page(doc.new_page(width=612, height=792))
    p.t(40, 55, "Pacific Lab Instruments", 16, bold=True)
    p.t(40, 70, "5100 Sorrento Valley Blvd, San Diego, CA 92121")
    p.t(40, 83, "Phone: (858) 555-0137")
    p.t(40, 96, "Federal Tax ID: 33-4410982")
    p.t(420, 55, "Invoice", 18, bold=True)
    for y, (label, value) in zip(
        (80, 93, 106, 119, 132, 145),
        [("Invoice No.", "PLI-500233"), ("Invoice Date", "03/11/2026"), ("Vendor ID", "V-008812"),
         ("PO Number", "PO-4500098817"), ("Receipt No.", "GR-771034"), ("Contract No.", "MSA-2024-117")],
    ):
        p.t(390, y, label, bold=True); p.t(470, y, value)
    for x, title, lines in (
        (40, "Bill To:", ["Coastal University Research Labs", "Accounts Payable - Bldg 2", "9500 Gilman Drive", "La Jolla, CA 92093"]),
        (220, "Ship To:", ["Coastal University", "Chemistry Receiving Dock B", "9500 Gilman Drive", "La Jolla, CA 92093"]),
    ):
        p.t(x, 170, title, bold=True)
        for i, s in enumerate(lines):
            p.t(x, 183 + 13 * i, s)
    header = [(40, "Ln"), (62, "PO Line"), (110, "Part Number"), (185, "Description"), (410, "Qty"), (425, "UOM"), (505, "Unit Price"), (572, "Extended")]
    y = 260
    for x, h in header:
        (p.r if h in ("Qty", "Unit Price", "Extended") else p.t)(x, y, h, bold=True)
    p.line(40, y + 4, 572, y + 4)
    rows = [
        ("1", "10", "PLI-PH-220", "Benchtop pH meter with probe", 2, "EA", 685.00),
        ("2", "20", "PLI-CAL-4", "pH calibration buffer set", 6, "SET", 38.50),
        ("3", "30", "PLI-MS-9", "Magnetic stirrer, 9 position", 1, "EA", 1240.00),
        ("4", "40", "PLI-SVC-INST", "On-site installation and IQ/OQ", 1, "LOT", 950.00),
    ]
    subtotal = 0.0
    for ln, po_line, part, desc, qty, uom, price in rows:
        y += 17
        amount = round(qty * price, 2)
        subtotal += amount
        p.t(40, y, ln); p.t(62, y, po_line); p.t(110, y, part); p.t(185, y, desc)
        p.r(410, y, str(qty)); p.t(425, y, uom); p.r(505, y, money(price)); p.r(572, y, money(amount))
    y += 36
    tax = round((subtotal - 950.00) * 0.0775, 2)
    for label, value in (("Subtotal", subtotal), ("Sales Tax 7.75%", tax), ("Total Due", subtotal + tax)):
        p.t(400, y, label + ":", bold=True); p.r(572, y, money(value, "$"))
        y += 15
    p.t(40, 690, "Remit To:", bold=True)
    for i, s in enumerate(["Pacific Lab Instruments", "Lockbox 44102", "Los Angeles, CA 90074"]):
        p.t(40, 703 + 12 * i, s)
    return doc


# --- F5: complex charges, EUR -------------------------------------------------------


def f5() -> fitz.Document:
    doc = fitz.open()
    p = Page(doc.new_page(width=595, height=842), unicode_fonts=True)  # A4
    p.t(40, 60, "Lumen Stage & Events B.V.", 15, bold=True)
    p.t(40, 76, "Keizersgracht 212, 1016 DZ Amsterdam, NL")
    p.t(40, 89, "VAT No.: NL812345678B01")
    p.t(40, 102, "finance@lumen-events.example")
    for y, (label, value) in zip(
        (60, 74, 88, 102, 116),
        [("Invoice Number:", "LSE-2026-0311"), ("Date of Invoice:", "11 March 2026"),
         ("Due Date:", "10 April 2026"), ("Currency:", "EUR"), ("Order Number:", "SO-66120")],
    ):
        p.t(360, y, label, bold=True); p.t(460, y, value)
    p.t(40, 140, "Invoice To:", bold=True)
    for i, s in enumerate(["Northgate Conference Centre Ltd", "Wharf Street 8", "Rotterdam 3011 AB"]):
        p.t(40, 153 + 13 * i, s)
    cols = [(40, "Description"), (330, "Days"), (420, "Rate"), (555, "Amount")]
    y = 220
    for x, h in cols:
        (p.t if h == "Description" else p.r)(x, y, h, bold=True)
    p.line(40, y + 4, 555, y + 4)
    rows = [
        ("LED wall rental, 4 x 3 m", 3, 1450.00),
        ("Line array sound system", 3, 980.00),
        ("Stage lighting package", 3, 760.00),
        ("Technician crew (3 persons)", 3, 1260.00),
    ]
    subtotal = 0.0
    for desc, days, rate in rows:
        y += 17
        amount = round(days * rate, 2)
        subtotal += amount
        p.t(40, y, desc); p.r(330, y, str(days)); p.r(420, y, money(rate, "€")); p.r(555, y, money(amount, "€"))
    discount = round(subtotal * 0.10, 2)
    freight, handling, surcharge = 380.00, 95.00, 60.00
    net = subtotal - discount + freight + handling + surcharge
    vat = round(net * 0.21, 2)
    total = net + vat
    paid = 5000.00
    y += 40
    for label, value in (
        ("Subtotal", subtotal), ("Discount (10%)", -discount), ("Freight", freight),
        ("Handling", handling), ("Fuel Surcharge", surcharge), ("VAT 21%", vat),
        ("Invoice Total", total), ("Amount Paid", -paid), ("Balance Due", total - paid),
    ):
        p.t(360, y, label + ":", bold=True)
        text = money(abs(value), "€")
        p.r(555, y, f"-{text}" if value < 0 else text)
        y += 15
    p.t(40, 780, "Payment by bank transfer. Please quote the invoice number.", 8.5)
    return doc


# --- F6: HTML ---------------------------------------------------------------------

F6_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Invoice NSS-7731</title>
<style>body{font-family:sans-serif} table{border-collapse:collapse} td,th{padding:4px 8px}</style></head>
<body>
<header>
  <h1>Northstar Software Ltd</h1>
  <address>14 Quayside, Newcastle upon Tyne NE1 3DX<br>billing@northstar-software.example<br>+44 191 555 0142</address>
</header>
<main>
  <h2>Tax Invoice</h2>
  <dl class="invoice-meta">
    <dt>Invoice Number</dt><dd>NSS-7731</dd>
    <dt>Issue Date</dt><dd>2026-03-01</dd>
    <dt>Due Date</dt><dd>2026-03-31</dd>
    <dt>Account Number</dt><dd>ACC-30177</dd>
    <dt>Currency</dt><dd>GBP</dd>
  </dl>
  <section>
    <h3>Billed To</h3>
    <address>Tyneside Housing Trust<br>Finance Office<br>2 Grey Street<br>Newcastle NE1 6EE</address>
  </section>
  <table>
    <thead><tr><th>Item</th><th>Description</th><th>Qty</th><th>Unit Price</th><th>Total</th></tr></thead>
    <tbody>
      <tr><td>LIC-PRO</td><td>Northstar Pro licence, annual</td><td>25</td><td>£120.00</td><td>£3,000.00</td></tr>
      <tr><td>SUP-PREM</td><td>Premium support, annual</td><td>1</td><td>£850.00</td><td>£850.00</td></tr>
      <tr><td>TRN-DAY</td><td>On-site training day</td><td>2</td><td>£640.00</td><td>£1,280.00</td></tr>
    </tbody>
    <tfoot>
      <tr><td colspan="4">Subtotal</td><td>£5,130.00</td></tr>
      <tr><td colspan="4">VAT 20%</td><td>£1,026.00</td></tr>
      <tr><td colspan="4">Total Due</td><td>£6,156.00</td></tr>
    </tfoot>
  </table>
  <p>Payment is due within 30 days. Please include the invoice number as the payment reference.</p>
</main>
</body></html>
"""


def main() -> None:
    for name, builder in (
        ("f1_digital_simple.pdf", f1),
        ("f2_scanned_services.pdf", f2),
        ("f3_multipage_parts.pdf", f3),
        ("f4_po_backed_lab.pdf", f4),
        ("f5_complex_charges.pdf", f5),
    ):
        doc = builder()
        doc.set_metadata({"title": name, "creationDate": "D:20260101000000", "modDate": "D:20260101000000"})
        doc.save(OUT / name, garbage=3, deflate=True, no_new_id=True)
        print("wrote", name, doc.page_count, "page(s)")
    (OUT / "f6_html_software.html").write_text(F6_HTML, encoding="utf-8")
    print("wrote f6_html_software.html")


if __name__ == "__main__":
    main()
