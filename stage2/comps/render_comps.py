#!/usr/bin/env python3
"""render_comps.py — one-page board PDF for the Stage-2 comp analysis."""
from datetime import datetime

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

NAVY = HexColor("#0B2545")
SLATE = HexColor("#334155")
LIGHT = HexColor("#F1F5F9")
MIDGRAY = HexColor("#64748B")
LINE = HexColor("#CBD5E1")
GOLD = HexColor("#B8860B")
GREEN = HexColor("#0F766E")
RED = HexColor("#B91C1C")
WHITE = HexColor("#FFFFFF")
PAGE_W, PAGE_H = letter
MARGIN = 0.55 * inch


def usd(x):
    if x is None:
        return "—"
    return ("-$" + f"{abs(x):,.0f}") if x < 0 else ("$" + f"{x:,.0f}")


def render(path, name, address, comps, pricing, economics, notes):
    c = canvas.Canvas(str(path), pagesize=letter)

    band = 0.85 * inch
    c.setFillColor(NAVY)
    c.rect(0, PAGE_H - band, PAGE_W, band, fill=1, stroke=0)
    c.setFillColor(GOLD)
    c.rect(0, PAGE_H - band - 3, PAGE_W, 3, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 17)
    c.drawString(MARGIN, PAGE_H - 0.42 * inch, name)
    c.setFont("Helvetica", 9)
    c.setFillColor(HexColor("#CBD5E1"))
    c.drawString(MARGIN, PAGE_H - 0.62 * inch, address)
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(WHITE)
    c.drawRightString(PAGE_W - MARGIN, PAGE_H - 0.4 * inch,
                      "COMPARABLE SALES & SUGGESTED PRICE")
    c.setFont("Helvetica", 8)
    c.setFillColor(HexColor("#CBD5E1"))
    c.drawRightString(PAGE_W - MARGIN, PAGE_H - 0.58 * inch,
                      "Sold, renovated comps within 2 miles · last 3 months")
    c.drawRightString(PAGE_W - MARGIN, PAGE_H - 0.72 * inch,
                      "Prepared for the Board of Directors")

    y = PAGE_H - band - 0.3 * inch

    # suggested price callout
    h = 0.95 * inch
    c.setFillColor(NAVY)
    c.roundRect(MARGIN, y - h, PAGE_W - 2 * MARGIN, h, 6, fill=1, stroke=0)
    c.setFillColor(HexColor("#CBD5E1"))
    c.setFont("Helvetica-Bold", 9)
    c.drawString(MARGIN + 16, y - 0.25 * inch, "SUGGESTED SALE PRICE (comp-based)")
    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 30)
    c.drawString(MARGIN + 14, y - 0.66 * inch, usd(pricing.get("suggested")))
    c.setFillColor(HexColor("#CBD5E1"))
    c.setFont("Helvetica", 8)
    rng = f"Range {usd(pricing.get('low'))} – {usd(pricing.get('high'))}"
    note_txt = f"{rng}   ·   {pricing.get('basis_note', '')}"
    # keep clear of the right-hand economics block
    avail = PAGE_W - 2 * MARGIN - 32 - (2.35 * inch if economics else 0)
    while (c.stringWidth(note_txt, "Helvetica", 8) > avail
           and len(note_txt) > 12):
        note_txt = note_txt[:-2]
        if c.stringWidth(note_txt + "…", "Helvetica", 8) <= avail:
            note_txt += "…"
            break
    c.drawString(MARGIN + 16, y - 0.84 * inch, note_txt)

    # profit vs all-in (right half of callout)
    if economics:
        rx = PAGE_W - MARGIN - 16
        c.setFillColor(HexColor("#CBD5E1"))
        c.setFont("Helvetica-Bold", 8)
        c.drawRightString(rx, y - 0.25 * inch, "AT THIS PRICE")
        c.setFont("Helvetica", 8.5)
        c.setFillColor(WHITE)
        c.drawRightString(rx, y - 0.43 * inch,
                          f"Net proceeds  {usd(economics['net_proceeds'])}")
        c.drawRightString(rx, y - 0.58 * inch,
                          f"All-in position  {usd(economics['all_in'])}")
        c.setFillColor(GREEN if economics["profit"] >= 0 else RED)
        c.setFont("Helvetica-Bold", 11)
        roi = f"  ({economics['roi']*100:.0f}%)" if economics.get("roi") is not None else ""
        c.drawRightString(rx, y - 0.78 * inch,
                          f"Profit  {usd(economics['profit'])}{roi}")

    y -= h + 0.28 * inch
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(MARGIN, y, "Comparable Sales")
    if economics and economics.get("breakeven"):
        c.setFillColor(MIDGRAY)
        c.setFont("Helvetica", 8)
        c.drawRightString(PAGE_W - MARGIN, y,
                          f"Your breakeven: {usd(economics['breakeven'])}")
    c.setStrokeColor(GOLD)
    c.setLineWidth(1.5)
    c.line(MARGIN, y - 5, MARGIN + 26, y - 5)
    y -= 0.22 * inch

    # comp grid: 2 columns x 3 rows
    gap = 0.22 * inch
    card_w = (PAGE_W - 2 * MARGIN - gap) / 2
    card_h = 1.32 * inch
    positions = []
    for row in range(3):
        for col in range(2):
            positions.append((MARGIN + col * (card_w + gap),
                              y - row * (card_h + 0.14 * inch)))
    for comp, (cx, cy) in zip(comps, positions):
        _draw_card(c, comp, cx, cy, card_w, card_h)

    # footer
    fy = MARGIN - 0.05 * inch
    c.setStrokeColor(LINE)
    c.setLineWidth(0.5)
    c.line(MARGIN, fy + 0.18 * inch, PAGE_W - MARGIN, fy + 0.18 * inch)
    c.setFillColor(MIDGRAY)
    c.setFont("Helvetica", 6.5)
    note = notes[0] if notes else ""
    c.drawString(MARGIN, fy + 0.05 * inch,
                 ("CONFIDENTIAL — comp-based estimate, not an appraisal. "
                  + note)[:155])
    c.drawString(MARGIN, fy - 0.06 * inch,
                 f"Generated {datetime.now():%B %d, %Y}. Photos: Google Street View. "
                 "Sources: Zillow, Redfin.")
    c.drawRightString(PAGE_W - MARGIN, fy + 0.05 * inch, "Office of the CFO")

    c.showPage()
    c.save()
    return path


def _draw_card(c, comp, x, y, w, h):
    c.setFillColor(LIGHT)
    c.roundRect(x, y - h, w, h, 5, fill=1, stroke=0)
    # photo box
    pw, ph = 1.45 * inch, h - 0.2 * inch
    px, py = x + 0.1 * inch, y - h + 0.1 * inch
    drawn = False
    if comp.photo:
        try:
            c.drawImage(ImageReader(str(comp.photo)), px, py, pw, ph,
                        preserveAspectRatio=True, anchor='c', mask='auto')
            drawn = True
        except Exception:
            drawn = False
    if not drawn:
        c.setFillColor(HexColor("#E2E8F0"))
        c.roundRect(px, py, pw, ph, 3, fill=1, stroke=0)
        c.setFillColor(MIDGRAY)
        c.setFont("Helvetica", 7)
        c.drawCentredString(px + pw / 2, py + ph / 2 - 3, "(Street View)")

    tx = px + pw + 0.12 * inch
    tw = x + w - tx - 0.1 * inch
    # source badge
    c.setFillColor(GOLD if comp.source == "Zillow" else GREEN)
    c.setFont("Helvetica-Bold", 6.5)
    c.drawString(tx, y - 0.2 * inch, comp.source.upper())
    if comp.renovated:
        c.setFillColor(MIDGRAY)
        c.drawString(tx + 0.5 * inch, y - 0.2 * inch, "· RENOVATED")
    # sold price
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(tx, y - 0.42 * inch, usd(comp.sold_price))
    c.setFillColor(MIDGRAY)
    c.setFont("Helvetica", 7.5)
    c.drawString(tx, y - 0.57 * inch,
                 f"sold {comp.sold_date}   ·   ${comp.ppsf:,.0f}/sqft")
    # address (wrap to 2 lines)
    c.setFillColor(SLATE)
    c.setFont("Helvetica", 7.5)
    _wrap(c, comp.address, tx, y - 0.72 * inch, tw, 7.5, 2)
    # stats line
    c.setFillColor(SLATE)
    c.setFont("Helvetica", 7.5)
    bits = []
    if comp.beds:
        bits.append(f"{comp.beds:g} bd")
    if comp.baths:
        bits.append(f"{comp.baths:g} ba")
    if comp.sqft:
        bits.append(f"{comp.sqft:,} sqft")
    if comp.year_built:
        bits.append(f"built {comp.year_built}")
    if comp.distance_mi:
        bits.append(f"{comp.distance_mi:.1f} mi")
    c.drawString(tx, y - h + 0.14 * inch, "   ".join(bits))


def _wrap(c, text, x, y, max_w, size, max_lines):
    words = text.split()
    lines, cur = [], ""
    for wd in words:
        test = (cur + " " + wd).strip()
        if c.stringWidth(test, "Helvetica", size) <= max_w:
            cur = test
        else:
            lines.append(cur)
            cur = wd
        if len(lines) == max_lines:
            break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    for i, ln in enumerate(lines[:max_lines]):
        c.drawString(x, y - i * (size + 1.5), ln)
