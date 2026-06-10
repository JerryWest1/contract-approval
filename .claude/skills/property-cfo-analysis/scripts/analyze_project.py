#!/usr/bin/env python3
"""
analyze_project.py — Deterministic local analyzer for the CFO inbox watcher.

Reads the three financial PDFs dropped in inbox/<project>/ (balance sheet,
income statement, general ledger), extracts the figures with pypdf, applies the
locked costing rules, and produces the board outputs in outputs/<project>/.

No AI is called at runtime. The intelligence is frozen into these rules, which
were verified against 52 Hawkin Road to reproduce the approved numbers exactly:

  basis    = (TOTAL ASSETS - Total Cash)            # capitalized project cost
           + Total Expense (P&L)                    # operating expenses
           - Total Income (P&L)                     # income already received
  interest = 12% simple, actual/365, per dated loan draw (GL "Loans Payable"
             accounts; cash Receipts = draws; Payments labeled "Return of
             Capital" cancel their draw FIFO; JE rows ignored)
  breakeven = (basis + interest) / (1 - selling_cost_pct)

Fail-clearly policy: every parsed section is tied out (leaves vs. totals, GL
running balance, loans vs. balance sheet). Any tie-out failure writes
exceptions.csv and NEEDS_REVIEW.txt and exits non-zero — no board PDF is
produced from numbers that don't reconcile. No fabrication, ever.

Usage:
  python analyze_project.py --input-dir "inbox/52 Hawkin" \
      --config "config/project_config.json" \
      --output-dir "outputs/52 Hawkin" --project-name "52 Hawkin"
"""
import argparse
import csv
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import analyze as engine            # deterministic math (verified)
import generate_pdf as pdfgen       # board PDF renderer (verified design)

MONEY_RE = re.compile(r"-?\d[\d,]*\.\d{2}")
TXN_TYPES = ("Receipt", "Payment", "eCheck", "Check", "CC Expense", "JE")


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def to_num(tok):
    return round(float(tok.replace(",", "")), 2)


def extract_text(pdf_path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        raise RuntimeError("pypdf is not installed. Run: python -m pip install pypdf")
    reader = PdfReader(str(pdf_path))
    text = "\n".join((page.extract_text() or "") for page in reader.pages)
    if len(text.strip()) < 50:
        raise RuntimeError(
            f"{pdf_path.name}: no extractable text — the PDF appears scanned/"
            "image-only and needs OCR, or is in an unsupported format.")
    return text


def find_source_files(input_dir: Path):
    """Identify the three statements by filename keywords."""
    pdfs = [p for p in input_dir.iterdir()
            if p.is_file() and p.suffix.lower() == ".pdf"]
    def pick(*keys):
        for p in sorted(pdfs):
            name = p.name.lower()
            if any(k in name for k in keys):
                return p
        return None
    bs = pick("balance")
    inc = pick("income", "profit", "p&l", "pnl")
    gl = pick("general_ledger", "ledger", "gl")
    missing = [label for label, f in
               [("balance sheet", bs), ("income statement", inc),
                ("general ledger", gl)] if f is None]
    return bs, inc, gl, missing


# --------------------------------------------------------------------------
# balance sheet
# --------------------------------------------------------------------------
def parse_balance_sheet(text: str, exceptions: list):
    """Return dict with property, as_of, cash, capitalized leaves by category,
    and orphan-mapped totals (TOTAL ASSETS, Total Cash, Total Loans Payable)."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    prop = ""
    as_of = None
    for ln in lines:
        if ln.startswith("Properties:"):
            prop = ln.split(":", 1)[1].strip()
        m = re.match(r"As of:\s*(\d{1,2}/\d{1,2}/\d{4})", ln)
        if m:
            as_of = datetime.strptime(m.group(1), "%m/%d/%Y").date()
    if as_of is None:
        exceptions.append(("error", "balance_sheet", "Could not find 'As of:' date"))

    # leaf lines: "<name> <amount>" ; header lines: name only; total labels
    # appear without inline amounts and their values arrive as a trailing
    # orphan-number block in the same order (pypdf column split).
    noise = re.compile(
        r"^(Properties:|As of:|Accounting Basis|GL Account Map|Level of Detail|"
        r"Include Zero|Account Name|Balance Sheet$|Created on )")
    leaves = []          # (name, amount, section)  section: assets/liabilities
    total_labels = []    # labels lacking inline amounts, in order
    orphans = []         # bare numbers, in order
    section = None
    category = None
    in_cash = False
    for ln in lines:
        if noise.match(ln):
            continue
        if ln == "ASSETS":
            section = "assets"; continue
        if ln.startswith("LIABILITIES"):
            section = "liabilities"; in_cash = False; continue
        if MONEY_RE.fullmatch(ln):
            orphans.append(to_num(ln)); continue
        m = re.match(r"^(.*?)\s+(-?\d[\d,]*\.\d{2})$", ln)
        if m and m.group(1):
            name = m.group(1).strip()
            if name.startswith("Total") or name.startswith("TOTAL"):
                continue  # inline-valued total (rare on this layout)
            leaves.append((name, to_num(m.group(2)), section, category, in_cash))
            continue
        # no inline amount: either a Total label or a group header
        if ln.startswith("Total ") or ln.startswith("TOTAL"):
            total_labels.append(ln)
            if ln == "Total Cash":
                in_cash = False
            continue
        if section == "assets":
            if ln == "Cash":
                in_cash = True; category = "Cash"
            else:
                category = ln
        # liabilities headers (Loans Payable etc.) need no tracking

    totals = {}
    if len(total_labels) == len(orphans):
        totals = dict(zip(total_labels, orphans))
    else:
        exceptions.append(("error", "balance_sheet",
                           f"Subtotal mapping mismatch: {len(total_labels)} labels "
                           f"vs {len(orphans)} values"))

    cash = round(sum(a for _, a, s, _, c in leaves if s == "assets" and c), 2)
    cap_leaves = [(n, a, cat) for n, a, s, cat, c in leaves
                  if s == "assets" and not c]
    capitalized = round(sum(a for _, a, _ in cap_leaves), 2)

    # tie-out: leaves must reproduce TOTAL ASSETS
    ta = totals.get("TOTAL ASSETS")
    if ta is None:
        exceptions.append(("error", "balance_sheet", "TOTAL ASSETS not found"))
    elif abs((capitalized + cash) - ta) > 0.01:
        exceptions.append(("error", "balance_sheet",
                           f"Tie-out failed: leaves {capitalized + cash:,.2f} != "
                           f"TOTAL ASSETS {ta:,.2f}"))

    return {
        "property": prop,
        "as_of": as_of,
        "cash": cash,
        "capitalized": capitalized,
        "cap_leaves": cap_leaves,
        "total_loans_payable": totals.get("Total Loans Payable"),
        "total_assets": ta,
    }


# --------------------------------------------------------------------------
# income statement
# --------------------------------------------------------------------------
def parse_income_statement(text: str, exceptions: list):
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    total_income = total_expense = None
    income_leaves, expense_leaves = [], []
    mode = None
    for ln in lines:
        m = re.match(r"^Total Income\s+(-?\d[\d,]*\.\d{2})$", ln)
        if m:
            total_income = to_num(m.group(1)); continue
        m = re.match(r"^Total Expense\s+(-?\d[\d,]*\.\d{2})$", ln)
        if m:
            total_expense = to_num(m.group(1)); continue
        if ln == "Income":
            mode = "income"; continue
        if ln == "Expense":
            mode = "expense"; continue
        if ln.startswith("Total Operating"):
            mode = None; continue
        m = re.match(r"^(.*?)\s+(-?\d[\d,]*\.\d{2})$", ln)
        if m and mode and not m.group(1).startswith(("Total", "NOI")):
            (income_leaves if mode == "income" else expense_leaves).append(
                (m.group(1).strip(), to_num(m.group(2))))

    if total_income is None:
        total_income = round(sum(a for _, a in income_leaves), 2)
        if not income_leaves:
            exceptions.append(("warning", "income_statement",
                               "No income found; assuming 0"))
    if total_expense is None:
        total_expense = round(sum(a for _, a in expense_leaves), 2)
        if not expense_leaves:
            exceptions.append(("warning", "income_statement",
                               "No expenses found; assuming 0"))

    if income_leaves and abs(sum(a for _, a in income_leaves) - total_income) > 0.01:
        exceptions.append(("error", "income_statement",
                           "Income leaves do not sum to Total Income"))
    if expense_leaves and abs(sum(a for _, a in expense_leaves) - total_expense) > 0.01:
        exceptions.append(("error", "income_statement",
                           "Expense leaves do not sum to Total Expense"))

    return {"total_income": total_income or 0.0,
            "total_expense": total_expense or 0.0,
            "expense_leaves": expense_leaves}


# --------------------------------------------------------------------------
# general ledger — loan accounts
# --------------------------------------------------------------------------
def parse_loan_accounts(text: str, exceptions: list):
    """Find 'Loans Payable' GL account sections and extract dated draws.

    Row decoding is validated by a running-balance chain: each row contributes
    (amount, new_balance) and |new_balance - prev_balance| must equal amount.
    Rules (verified against the approved 52 Hawkin numbers):
      * Receipt rows (cash in)  -> loan draw, accrues from its date
      * Payment/Check rows (cash out) labeled 'Return of Capital'
                                -> cancel outstanding draws FIFO (no interest)
      * other Payment/Check     -> repayment: negative accrual from its date
      * JE rows                 -> ignored (bookkeeping, not cash)
    """
    sections = []
    for m in re.finditer(r"^(\d{3,5}) - (.*Loans? Payable.*)$", text,
                         flags=re.MULTILINE):
        sections.append((m.start(), m.group(2).strip()))
    draws = []          # dicts: account, date, amount, kind
    outstanding_total = 0.0

    for idx, (start, account_name) in enumerate(sections):
        end = sections[idx + 1][0] if idx + 1 < len(sections) else len(text)
        chunk = text[start:end]
        nc = chunk.find("Net Change")
        if nc != -1:
            chunk = chunk[:nc]
        sb = chunk.find("Starting Balance")
        if sb != -1:
            chunk = chunk[sb + len("Starting Balance"):]
        flat = re.sub(r"\s+", " ", chunk)

        tokens = [(m.start(), m.end(), to_num(m.group(0)))
                  for m in MONEY_RE.finditer(flat)]
        display = re.sub(r"^Loans? Payable:?\s*", "", account_name).strip() \
                  or account_name

        rows = []
        prev_balance = 0.0
        i = 0
        while i + 1 < len(tokens):
            amt_tok, bal_tok = tokens[i], tokens[i + 1]
            amount, balance = amt_tok[2], bal_tok[2]
            delta = round(balance - prev_balance, 2)
            if abs(abs(delta) - abs(amount)) > 0.01:
                exceptions.append(("error", "general_ledger",
                                   f"{display}: balance chain broke at token "
                                   f"{amount:,.2f} (balance {balance:,.2f}, "
                                   f"prev {prev_balance:,.2f})"))
                break
            pre = flat[(tokens[i - 1][1] if i > 0 else 0):amt_tok[0]]
            post_end = tokens[i + 2][0] if i + 2 < len(tokens) else len(flat)
            post = flat[bal_tok[1]:post_end]
            rows.append({"amount": abs(amount), "delta": delta,
                         "pre": pre, "post": post, "balance": balance})
            prev_balance = balance
            i += 2

        for row in rows:
            ttype = next((t for t in TXN_TYPES if re.search(
                rf"\b{re.escape(t)}\b", row["pre"])), None)
            row_date = resolve_row_date(row["pre"], row["post"], exceptions,
                                        display)
            if ttype == "JE":
                continue
            if row["delta"] < 0:                       # credit -> draw
                if ttype != "Receipt":
                    exceptions.append(("warning", "general_ledger",
                                       f"{display}: credit of {row['amount']:,.2f} "
                                       f"typed '{ttype}' (expected Receipt) — "
                                       "treated as a draw"))
                draws.append({"account": display, "date": row_date,
                              "amount": row["amount"], "kind": "draw"})
            else:                                      # debit -> repayment
                if re.search(r"return of capital", row["pre"] + row["post"],
                             re.IGNORECASE):
                    cancel_fifo(draws, display, row["amount"], exceptions)
                else:
                    draws.append({"account": display, "date": row_date,
                                  "amount": -row["amount"], "kind": "repayment"})

        outstanding_total = round(
            outstanding_total + sum(d["amount"] for d in draws
                                    if d["account"] == display), 2)
    return draws, outstanding_total


def resolve_row_date(pre: str, post: str, exceptions: list, account: str):
    """Transaction dates extract as 'MM/DD/ YYYY' (split column). Edited-at
    timestamps are 'MM/DD/YYYY at HH:MM' (no gap) — used as fallback."""
    m = re.search(r"(\d{1,2})/(\d{1,2})/\s+(\d{4})", pre)
    if m:
        return date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
    m = re.search(r"(\d{1,2})/(\d{1,2})/(?=\s|$)", pre)
    if m:
        mm, dd = int(m.group(1)), int(m.group(2))
        m2 = re.search(rf"{m.group(1)}/{m.group(2)}/(\d{{4}}) at", pre + post)
        if m2:
            return date(int(m2.group(1)), mm, dd)
        m3 = re.search(r"\b(20\d{2})\b", post)
        if m3:
            return date(int(m3.group(1)), mm, dd)
    exceptions.append(("error", "general_ledger",
                       f"{account}: could not resolve a transaction date"))
    return None


def cancel_fifo(draws, account, amount, exceptions):
    """A 'Return of Capital' repayment removes principal from the earliest
    outstanding draws of the account — cancelled principal earns no interest
    (matches the approved treatment of short-lived bridge funding)."""
    remaining = amount
    for d in draws:
        if d["account"] != account or d["kind"] != "draw" or d["amount"] <= 0:
            continue
        take = min(d["amount"], remaining)
        d["amount"] = round(d["amount"] - take, 2)
        remaining = round(remaining - take, 2)
        if remaining <= 0:
            break
    if remaining > 0.01:
        exceptions.append(("error", "general_ledger",
                           f"{account}: Return of Capital {amount:,.2f} exceeds "
                           f"outstanding draws by {remaining:,.2f}"))


# --------------------------------------------------------------------------
# outputs
# --------------------------------------------------------------------------
def write_exceptions(output_dir: Path, exceptions: list):
    with open(output_dir / "exceptions.csv", "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["severity", "source", "message"])
        w.writerows(exceptions)


def write_workpaper(output_dir: Path, results: dict):
    with open(output_dir / "workpaper.csv", "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "description", "category", "amount",
                    "counts_basis", "interest_rate", "days_out",
                    "accrued_interest"])
        for e in results["entries"]:
            w.writerow([e["date"], e["description"], e["category"],
                        f"{e['amount']:.2f}", e["counts_basis"],
                        e["interest_rate"], e["days_out"],
                        f"{e['accrued_interest']:.2f}"])


def write_html(output_dir: Path, results: dict):
    t = results["totals"]
    p = results["property"]
    rows = "".join(
        f"<tr><td>{c['category']}</td>"
        f"<td style='text-align:right'>${c['basis']:,.0f}</td></tr>"
        for c in results["categories"])
    html = f"""<!doctype html><meta charset="utf-8">
<title>{p['name']} — Board Summary</title>
<body style="font-family:Arial,sans-serif;max-width:720px;margin:2em auto">
<h1 style="margin-bottom:0">{p['name']}</h1>
<p style="color:#666">{p['address']} — as of {p['as_of_date']}</p>
<table cellpadding="6" style="border-collapse:collapse;width:100%">
<tr><td>Total capital invested</td><td style="text-align:right">
<b>${t['total_cost_basis']:,.2f}</b></td></tr>
<tr><td>Accrued interest @ {p['default_interest_rate']*100:.0f}%</td>
<td style="text-align:right"><b>${t['total_accrued_interest']:,.2f}</b></td></tr>
<tr><td>All-in position</td><td style="text-align:right">
<b>${t['all_in_position']:,.2f}</b></td></tr>
<tr style="background:#0B2545;color:#fff"><td>Breakeven sale price</td>
<td style="text-align:right"><b>${t['breakeven_sale_price']:,.2f}</b></td></tr>
</table><h3>Capital by category</h3>
<table cellpadding="6" style="border-collapse:collapse;width:100%">{rows}</table>
</body>"""
    (output_dir / "board_summary.html").write_text(html, encoding="utf-8")


def render_board_pdf(results: dict, output_dir: Path):
    target = output_dir / "board_summary.pdf"
    try:
        pdfgen.draw(results, str(target))
        return target
    except PermissionError:
        fallback = output_dir / (
            f"board_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
        pdfgen.draw(results, str(fallback))
        latest = output_dir / "board_summary_latest.pdf"
        try:
            latest.write_bytes(fallback.read_bytes())
        except PermissionError:
            pass
        return fallback


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input-dir", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--project-name", required=True)
    args = ap.parse_args(argv)

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    exceptions = []

    bs_file, inc_file, gl_file, missing = find_source_files(input_dir)
    if missing:
        exceptions.append(("error", "inputs",
                           "Missing required file(s): " + ", ".join(missing)))
        write_exceptions(output_dir, exceptions)
        (output_dir / "NEEDS_REVIEW.txt").write_text(
            "Cannot run analysis — missing: " + ", ".join(missing) +
            "\nDrop the balance sheet, income statement, and general ledger "
            "PDFs into the project folder.", encoding="utf-8")
        print("ERROR: missing inputs:", ", ".join(missing))
        return 2

    bs = parse_balance_sheet(extract_text(bs_file), exceptions)
    inc = parse_income_statement(extract_text(inc_file), exceptions)
    draws, outstanding = parse_loan_accounts(extract_text(gl_file), exceptions)

    # cross-statement tie-out: GL loan principal vs balance sheet
    if bs.get("total_loans_payable") is not None:
        if abs(outstanding - bs["total_loans_payable"]) > 0.01:
            exceptions.append(("error", "tie_out",
                               f"GL outstanding loans {outstanding:,.2f} != "
                               f"balance sheet Total Loans Payable "
                               f"{bs['total_loans_payable']:,.2f}"))

    if any(sev == "error" for sev, _, _ in exceptions):
        write_exceptions(output_dir, exceptions)
        msgs = "\n".join(f"[{s}] {src}: {m}" for s, src, m in exceptions)
        (output_dir / "NEEDS_REVIEW.txt").write_text(
            "Analysis stopped — the numbers did not reconcile and no board "
            "report was produced (no fabrication policy).\n\n" + msgs,
            encoding="utf-8")
        print("ERROR: tie-outs failed; see exceptions.csv")
        return 2

    # ---- build deal -------------------------------------------------------
    as_of = bs["as_of"] or date.today()
    rate = float(config.get("default_interest_rate", 0.12))
    sell_pct = float(config.get("selling_cost_pct", 0.06))

    entries = []
    for name, amount, category in bs["cap_leaves"]:
        entries.append({"date": as_of.isoformat(), "description": name,
                        "category": category or "Capitalized Costs",
                        "amount": amount, "accrues_interest": False})
    for name, amount in inc["expense_leaves"]:
        entries.append({"date": as_of.isoformat(),
                        "description": f"{name} (P&L)",
                        "category": "Operating Expenses (P&L)",
                        "amount": amount, "accrues_interest": False})
    if not inc["expense_leaves"] and inc["total_expense"]:
        entries.append({"date": as_of.isoformat(),
                        "description": "Operating expenses (P&L)",
                        "category": "Operating Expenses (P&L)",
                        "amount": inc["total_expense"],
                        "accrues_interest": False})
    if inc["total_income"]:
        entries.append({"date": as_of.isoformat(),
                        "description": "Less: income received (P&L)",
                        "category": "Less: Income Received",
                        "amount": -inc["total_income"],
                        "accrues_interest": False})
    for d in draws:
        if abs(d["amount"]) < 0.01 or d["date"] is None:
            continue
        entries.append({"date": d["date"].isoformat(),
                        "description": ("Loan draw" if d["amount"] > 0
                                        else "Loan repayment"),
                        "category": f"Loan: {d['account']}",
                        "amount": d["amount"], "basis": False,
                        "interest_rate": rate})

    deal = {
        "property": {
            "name": args.project_name,
            "address": bs["property"],
            "as_of_date": as_of.isoformat(),
            "default_interest_rate": rate,
            "day_count": int(config.get("day_count", 365)),
            "selling_cost_pct": sell_pct,
            "target_sale_prices": [],
        },
        "entries": entries,
        "notes": ("Deterministic local analysis. Basis = capitalized assets "
                  "(TOTAL ASSETS less cash) + P&L operating expenses - income "
                  "received. Interest: 12% simple actual/365 per dated GL loan "
                  "draw; 'Return of Capital' repayments cancel draws FIFO; JE "
                  "rows ignored. A/P and cash overdraft excluded "
                  "(funding/timing items)."),
    }

    # first pass to learn breakeven, then set bracketing target prices
    results = engine.analyze(deal)
    breakeven = results["totals"]["breakeven_sale_price"]
    if breakeven:
        base = round(breakeven / 10000) * 10000
        offsets = config.get("target_price_offsets", [-20000, 0, 20000, 50000])
        deal["property"]["target_sale_prices"] = [base + o for o in offsets]
        results = engine.analyze(deal)

    # ---- write outputs ----------------------------------------------------
    (output_dir / "deal.json").write_text(json.dumps(deal, indent=2),
                                          encoding="utf-8")
    (output_dir / "summary.json").write_text(
        json.dumps({"project": args.project_name,
                    "generated": datetime.now().isoformat(timespec="seconds"),
                    **results["totals"]}, indent=2), encoding="utf-8")
    write_workpaper(output_dir, results)
    write_html(output_dir, results)
    write_exceptions(output_dir, exceptions)
    pdf_path = render_board_pdf(results, output_dir)

    t = results["totals"]
    print(f"Project: {args.project_name}")
    print(f"Capital invested:  ${t['total_cost_basis']:,.2f}")
    print(f"Accrued interest:  ${t['total_accrued_interest']:,.2f}")
    print(f"All-in position:   ${t['all_in_position']:,.2f}")
    print(f"Breakeven price:   ${t['breakeven_sale_price']:,.2f}")
    print(f"Board PDF:         {pdf_path}")
    if exceptions:
        print(f"Warnings: {len(exceptions)} (see exceptions.csv)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
