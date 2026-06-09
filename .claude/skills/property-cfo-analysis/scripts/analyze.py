#!/usr/bin/env python3
"""
analyze.py — Deterministic financial engine for the property-cfo-analysis skill.

Reads a deal.json (figures extracted from the balance sheet / income statement /
general ledger) and computes:

  * Total cost basis  ........ everything the owner is "in it for"
  * Accrued interest  ........ simple, actual/365, per-entry, default 12%/yr
  * All-in position   ........ basis + accrued interest
  * Breakeven price   ........ price needed to recover the all-in position
                               after selling costs
  * Profit scenarios  ........ net proceeds / profit / ROI at target prices

Interest convention (per user spec):
    interest = amount * annual_rate * (days_out / 365)
    days_out = (as_of_date - entry_date) in calendar days, never negative.

Usage:
    python3 analyze.py path/to/deal.json [-o path/to/results.json]
"""
import argparse
import json
import sys
from datetime import date, datetime

DEFAULT_RATE = 0.12
DAY_COUNT = 365
DEFAULT_SELLING_COST_PCT = 0.06


def parse_date(value):
    if value is None:
        return None
    if isinstance(value, date):
        return value
    s = str(value).strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unrecognized date format: {value!r}")


def money(x):
    return round(float(x or 0), 2)


def analyze(deal):
    prop = deal.get("property", {})
    as_of = parse_date(prop.get("as_of_date")) or date.today()
    default_rate = float(prop.get("default_interest_rate", DEFAULT_RATE))
    day_count = int(prop.get("day_count", DAY_COUNT))
    selling_cost_pct = float(prop.get("selling_cost_pct", DEFAULT_SELLING_COST_PCT))

    entries_out = []
    category_basis = {}
    category_interest = {}
    total_basis = 0.0
    total_interest = 0.0

    for raw in deal.get("entries", []):
        amount = money(raw.get("amount"))
        entry_date = parse_date(raw.get("date"))
        rate = float(raw.get("interest_rate", default_rate))
        accrues = raw.get("accrues_interest", True)
        category = raw.get("category", "Other") or "Other"
        description = raw.get("description", "")

        if entry_date is None or entry_date > as_of:
            days_out = 0
        else:
            days_out = (as_of - entry_date).days

        interest = money(amount * rate * (days_out / day_count)) if accrues else 0.0

        total_basis += amount
        total_interest += interest
        category_basis[category] = money(category_basis.get(category, 0) + amount)
        category_interest[category] = money(category_interest.get(category, 0) + interest)

        entries_out.append({
            "date": entry_date.isoformat() if entry_date else None,
            "description": description,
            "category": category,
            "amount": amount,
            "interest_rate": rate,
            "accrues_interest": bool(accrues),
            "days_out": days_out,
            "accrued_interest": interest,
        })

    total_basis = money(total_basis)
    total_interest = money(total_interest)
    all_in = money(total_basis + total_interest)

    # Breakeven: net proceeds after selling costs must equal all-in position.
    #   net = price * (1 - selling_cost_pct) = all_in  ->  price = all_in / (1 - pct)
    if selling_cost_pct >= 1:
        breakeven_price = None
    else:
        breakeven_price = money(all_in / (1 - selling_cost_pct))

    scenarios = []
    for price in prop.get("target_sale_prices", []) or []:
        price = money(price)
        selling_costs = money(price * selling_cost_pct)
        net_proceeds = money(price - selling_costs)
        profit = money(net_proceeds - all_in)
        roi = round(profit / total_basis, 4) if total_basis else None
        scenarios.append({
            "sale_price": price,
            "selling_costs": selling_costs,
            "net_proceeds": net_proceeds,
            "profit": profit,
            "roi_on_basis": roi,
        })

    categories = []
    for cat in sorted(category_basis, key=lambda c: -category_basis[c]):
        categories.append({
            "category": cat,
            "basis": category_basis[cat],
            "interest": category_interest.get(cat, 0.0),
        })

    return {
        "property": {
            "name": prop.get("name", "Unnamed Property"),
            "address": prop.get("address", ""),
            "as_of_date": as_of.isoformat(),
            "default_interest_rate": default_rate,
            "day_count": day_count,
            "selling_cost_pct": selling_cost_pct,
        },
        "totals": {
            "total_cost_basis": total_basis,
            "total_accrued_interest": total_interest,
            "all_in_position": all_in,
            "breakeven_sale_price": breakeven_price,
            "entry_count": len(entries_out),
        },
        "categories": categories,
        "entries": entries_out,
        "scenarios": scenarios,
        "notes": deal.get("notes", ""),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Compute real-estate investment position.")
    ap.add_argument("deal", help="Path to deal.json")
    ap.add_argument("-o", "--output", help="Path to write results.json (default: alongside deal.json)")
    args = ap.parse_args(argv)

    with open(args.deal) as f:
        deal = json.load(f)

    results = analyze(deal)

    out_path = args.output
    if not out_path:
        import os
        out_path = os.path.join(os.path.dirname(os.path.abspath(args.deal)), "results.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)

    t = results["totals"]
    print(f"Property: {results['property']['name']}")
    print(f"As of:    {results['property']['as_of_date']}")
    print(f"Entries:  {t['entry_count']}")
    print(f"Cost basis (in it for): ${t['total_cost_basis']:,.2f}")
    print(f"Accrued interest:       ${t['total_accrued_interest']:,.2f}")
    print(f"All-in position:        ${t['all_in_position']:,.2f}")
    if t["breakeven_sale_price"] is not None:
        print(f"Breakeven sale price:   ${t['breakeven_sale_price']:,.2f}")
    print(f"Results written to: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
