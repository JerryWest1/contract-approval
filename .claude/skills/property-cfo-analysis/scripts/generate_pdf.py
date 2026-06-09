#!/usr/bin/env python3
"""
generate_pdf.py — Render a single-page, board-ready PDF from results.json.

Designed to be shared with the board of a Fortune 500 company: clean, dense,
professional, one page, US Letter.

Usage:
    python3 generate_pdf.py path/to/results.json [-o path/to/output.pdf]
"""
import argparse
import json
import os
import sys
from datetime import datetime

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas

# Palette — restrained corporate navy / slate / accent gold
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
MARGIN = 0.6 * inch


def usd(x, cents=False):
    if x is None:
        return "—"
    return ("${:,.2f}" if cents else "${:,.0f}").format(x)


def pct(x):
    if x is None:
        return "—"
    return f"{x * 100:.1f}%"


def draw(results, out_path):
    c = canvas.Canvas(out_path, pagesize=letter)
    prop = results["property"]
    totals = results["totals"]

    # ---- Header band ----------------------------------------------------
    band_h = 0.95 * inch
    c.setFillColor(NAVY)
    c.rect(0, PAGE_H - band_h, PAGE_W, band_h, fill=1, stroke=0)
    c.setFillColor(GOLD)
    c.rect(0, PAGE_H - band_h - 3, PAGE_W, 3, fill=1, stroke=0)

    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(MARGIN, PAGE_H - 0.45 * inch, prop["name"])
    c.setFont("Helvetica", 9.5)
    c.setFillColor(HexColor("#CBD5E1"))
    subtitle = prop.get("address") or "Real Estate Investment Position"
    c.drawString(MARGIN, PAGE_H - 0.66 * inch, subtitle)

    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(WHITE)
    c.drawRightString(PAGE_W - MARGIN, PAGE_H - 0.4 * inch, "INVESTMENT POSITION SUMMARY")
    c.setFont("Helvetica", 8.5)
    c.setFillColor(HexColor("#CBD5E1"))
    asof = datetime.fromisoformat(prop["as_of_date"]).strftime("%B %d, %Y")
    c.drawRightString(PAGE_W - MARGIN, PAGE_H - 0.57 * inch, f"As of {asof}")
    c.drawRightString(PAGE_W - MARGIN, PAGE_H - 0.72 * inch, "Prepared for the Board of Directors")

    y = PAGE_H - band_h - 0.35 * inch

    # ---- KPI cards ------------------------------------------------------
    cards = [
        ("TOTAL CAPITAL INVESTED", usd(totals["total_cost_basis"]), "All-in cost basis", SLATE),
        (f"ACCRUED INTEREST @ {pct(prop['default_interest_rate'])}",
         usd(totals["total_accrued_interest"]), "Simple, actual/365", GOLD),
        ("ALL-IN POSITION", usd(totals["all_in_position"]), "Basis + interest owed", NAVY),
    ]
    gap = 0.2 * inch
    card_w = (PAGE_W - 2 * MARGIN - 2 * gap) / 3
    card_h = 0.95 * inch
    cx = MARGIN
    for label, value, sub, accent in cards:
        c.setFillColor(LIGHT)
        c.roundRect(cx, y - card_h, card_w, card_h, 6, fill=1, stroke=0)
        c.setFillColor(accent)
        c.roundRect(cx, y - card_h, 4, card_h, 2, fill=1, stroke=0)
        c.setFillColor(MIDGRAY)
        c.setFont("Helvetica-Bold", 7.5)
        c.drawString(cx + 14, y - 0.22 * inch, label)
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 19)
        c.drawString(cx + 14, y - 0.58 * inch, value)
        c.setFillColor(MIDGRAY)
        c.setFont("Helvetica", 7.5)
        c.drawString(cx + 14, y - 0.78 * inch, sub)
        cx += card_w + gap

    y -= card_h + 0.3 * inch

    # ---- Breakeven callout ---------------------------------------------
    be_h = 0.7 * inch
    c.setFillColor(NAVY)
    c.roundRect(MARGIN, y - be_h, PAGE_W - 2 * MARGIN, be_h, 6, fill=1, stroke=0)
    c.setFillColor(HexColor("#CBD5E1"))
    c.setFont("Helvetica-Bold", 9)
    c.drawString(MARGIN + 16, y - 0.27 * inch, "BREAKEVEN SALE PRICE")
    c.setFont("Helvetica", 7.5)
    c.drawString(MARGIN + 16, y - 0.46 * inch,
                 f"Price required to recover the all-in position after {pct(prop['selling_cost_pct'])} selling costs.")
    c.drawString(MARGIN + 16, y - 0.60 * inch, "Any sale above this figure is profit to the owner.")
    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 26)
    c.drawRightString(PAGE_W - MARGIN - 16, y - 0.46 * inch, usd(totals["breakeven_sale_price"]))

    y -= be_h + 0.32 * inch

    # ---- Two columns: cost basis by category | sale scenarios ----------
    col_gap = 0.35 * inch
    col_w = (PAGE_W - 2 * MARGIN - col_gap) / 2
    left_x = MARGIN
    right_x = MARGIN + col_w + col_gap
    top_y = y

    def section_title(x, yy, text):
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(x, yy, text)
        c.setStrokeColor(GOLD)
        c.setLineWidth(1.5)
        c.line(x, yy - 5, x + 26, yy - 5)

    # Left: cost basis by category
    section_title(left_x, top_y, "Capital Invested by Category")
    ry = top_y - 0.28 * inch
    c.setFont("Helvetica-Bold", 7.5)
    c.setFillColor(MIDGRAY)
    c.drawString(left_x, ry, "CATEGORY")
    c.drawRightString(left_x + col_w, ry, "AMOUNT")
    ry -= 0.06 * inch
    c.setStrokeColor(LINE)
    c.setLineWidth(0.5)
    c.line(left_x, ry, left_x + col_w, ry)
    ry -= 0.18 * inch
    c.setFont("Helvetica", 8.5)
    for cat in results["categories"][:9]:
        c.setFillColor(SLATE)
        name = cat["category"]
        if len(name) > 34:
            name = name[:33] + "…"
        c.drawString(left_x, ry, name)
        c.setFillColor(NAVY)
        c.drawRightString(left_x + col_w, ry, usd(cat["basis"]))
        ry -= 0.205 * inch
    c.setStrokeColor(LINE)
    c.line(left_x, ry + 0.06 * inch, left_x + col_w, ry + 0.06 * inch)
    ry -= 0.04 * inch
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(left_x, ry, "Total Capital Invested")
    c.drawRightString(left_x + col_w, ry, usd(totals["total_cost_basis"]))
    ry -= 0.2 * inch
    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(left_x, ry, f"Accrued Interest @ {pct(prop['default_interest_rate'])}")
    c.drawRightString(left_x + col_w, ry, usd(totals["total_accrued_interest"]))

    # Right: sale scenarios
    section_title(right_x, top_y, "Profit at Target Sale Prices")
    ry = top_y - 0.28 * inch
    c.setFont("Helvetica-Bold", 7.5)
    c.setFillColor(MIDGRAY)
    c.drawString(right_x, ry, "SALE PRICE")
    c.drawRightString(right_x + col_w * 0.66, ry, "NET PROCEEDS")
    c.drawRightString(right_x + col_w, ry, "PROFIT")
    ry -= 0.06 * inch
    c.setStrokeColor(LINE)
    c.line(right_x, ry, right_x + col_w, ry)
    ry -= 0.18 * inch
    scenarios = results.get("scenarios", [])
    if not scenarios:
        c.setFillColor(MIDGRAY)
        c.setFont("Helvetica-Oblique", 8.5)
        c.drawString(right_x, ry, "No target prices provided.")
    for s in scenarios[:8]:
        c.setFillColor(SLATE)
        c.setFont("Helvetica", 8.5)
        c.drawString(right_x, ry, usd(s["sale_price"]))
        c.drawRightString(right_x + col_w * 0.66, ry, usd(s["net_proceeds"]))
        c.setFillColor(GREEN if s["profit"] >= 0 else RED)
        c.setFont("Helvetica-Bold", 8.5)
        profit_txt = usd(s["profit"])
        if s.get("roi_on_basis") is not None:
            profit_txt += f"  ({pct(s['roi_on_basis'])})"
        c.drawRightString(right_x + col_w, ry, profit_txt)
        ry -= 0.225 * inch

    # ---- Footer ---------------------------------------------------------
    fy = MARGIN + 0.15 * inch
    c.setStrokeColor(LINE)
    c.setLineWidth(0.5)
    c.line(MARGIN, fy + 0.22 * inch, PAGE_W - MARGIN, fy + 0.22 * inch)
    c.setFillColor(MIDGRAY)
    c.setFont("Helvetica", 6.8)
    c.drawString(MARGIN, fy + 0.07 * inch,
                 "CONFIDENTIAL — Prepared for internal board review. Interest accrued on a simple, "
                 "actual/365 basis per entry.")
    c.drawString(MARGIN, fy - 0.05 * inch,
                 f"Figures derived from owner-provided financials.  "
                 f"Generated {datetime.now().strftime('%B %d, %Y at %I:%M %p')}.  "
                 f"{totals['entry_count']} ledger entr{'y' if totals['entry_count'] == 1 else 'ies'} analyzed.")
    c.drawRightString(PAGE_W - MARGIN, fy + 0.07 * inch, "Office of the CFO")

    c.showPage()
    c.save()
    return out_path


def main(argv=None):
    ap = argparse.ArgumentParser(description="Render board-ready one-page PDF.")
    ap.add_argument("results", help="Path to results.json")
    ap.add_argument("-o", "--output", help="Output PDF path")
    args = ap.parse_args(argv)

    with open(args.results) as f:
        results = json.load(f)

    out = args.output
    if not out:
        base = results["property"]["name"].replace(" ", "_").replace("/", "-")
        out = os.path.join(os.path.dirname(os.path.abspath(args.results)),
                           f"{base}_Board_Summary.pdf")
    draw(results, out)
    print(f"PDF written to: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
