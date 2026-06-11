# CFO Board Report — Methodology & Handoff Spec (authoritative)

This is the **source of truth** for how a board report must be produced. Any
implementation (the included Python, Codex's version, anything) is **correct
only if it reproduces the reference numbers in Section 7 exactly.** If your code
disagrees with Section 7, the code is wrong — not these rules.

The verified reference implementation already lives in this repo:

```
.claude/skills/property-cfo-analysis/scripts/
  analyze_project.py   # parses the 3 PDFs, applies these rules, writes outputs
  analyze.py           # the deterministic math engine
  generate_pdf.py      # the one-page board PDF renderer
```

`analyze_project.py` has been run against the real 52 Hawkin and 511 Shires
statements and matches Section 7 to the penny. Treat it as the gold standard;
if you rewrite, diff your output against it.

---

## 1. Goal

Input: three PDFs for one property — **balance sheet**, **income statement**,
**general ledger** (from the owner's property-management accounting system).

Output: a one-page board PDF with four headline numbers —
**Total Capital Invested**, **Accrued Interest @ 12%**, **All-In Position**,
**Breakeven Sale Price** — plus profit at a few target sale prices, and an
audit workpaper.

## 2. Cost basis ("how much are we in it for")

```
total_cost_basis = capitalized_project_cost
                 + pnl_operating_expenses
                 - income_already_received
```

- **capitalized_project_cost** = `TOTAL ASSETS - Total Cash` from the balance
  sheet. (Everything capitalized into the asset: building, improvements,
  construction-in-progress, carrying costs. Cash is removed because a negative
  operating-cash balance is financing/timing, not money in the asset.)
- **pnl_operating_expenses** = `Total Expense` from the income statement
  (attorney/professional fees, insurance expense, real-estate tax, postage,
  etc.). These are real dollars spent that are **NOT** in the capitalized
  balance-sheet totals, so they must be added.
- **income_already_received** = `Total Income` from the income statement (e.g.
  forfeited use-&-occupancy booked as "Rent"). Subtracted because the owner has
  already collected it.

**Explicitly excluded from basis:** Accounts Payable and any operating-cash
overdraft. They describe how the deal was *funded/timed*, not costs incurred.

## 3. Interest ("how much is owed")

Interest = **12% simple, actual/365**, accrued **per dated loan draw**, summed.

```
days_out        = (as_of_date - draw_date)            # calendar days, >= 0
draw_interest   = draw_amount * 0.12 * days_out / 365
total_interest  = sum(draw_interest over all outstanding draws)
```

Find draws in the **general ledger's "Loans Payable" account sections** (account
names containing "Loans Payable"). Within each section, decode rows and classify:

- **Receipt** (cash in, credit, balance more negative) -> a **loan draw**;
  accrues from its transaction date.
- **Payment/Check** (cash out, debit) labeled **"Return of Capital"** -> cancels
  outstanding draws of that account **FIFO** (earliest first). Cancelled
  principal earns **no interest** (handles short-lived bridge funding that was
  advanced and repaid quickly).
- **Other Payment/Check** -> a repayment; record as a negative draw that **stops
  accrual** from its date.
- **JE (journal entry)** rows -> **ignored** (bookkeeping reclassifications, not
  cash). Example: the "2470 - Loans Payable" escrow JE that nets to zero.

The default rate is **12%**, overridable per draw if a document specifies
otherwise. Day count is actual/365 (no compounding).

## 4. All-in & breakeven

```
all_in_position    = total_cost_basis + total_interest
breakeven_price    = all_in_position / (1 - selling_cost_pct)   # selling_cost_pct = 0.06
```

Breakeven is the sale price whose net proceeds (after 6% cost of sale) exactly
recover the all-in position. Profit at a target price P:

```
net_proceeds = P * (1 - selling_cost_pct)
profit       = net_proceeds - all_in_position
roi_on_basis = profit / total_cost_basis
```

Target sale prices: round breakeven to the nearest $10,000, then apply
`target_price_offsets` from config (default `[-20000, 0, 20000, 50000]`). These
are illustrative scenarios, not calculations.

## 5. Tie-outs (no-fabrication policy)

Before producing any PDF, validate. If any check fails, write
`exceptions.csv` + `NEEDS_REVIEW.txt` and **do not** produce a board report.

1. Balance-sheet leaf items must sum to `TOTAL ASSETS` (leaves + cash).
2. Income-statement leaves must sum to `Total Income` / `Total Expense`.
3. Each GL loan section's **running balance must chain**: every row's
   `(new_balance - prev_balance)` must equal its amount. This is how rows are
   decoded reliably despite messy PDF text.
4. GL outstanding loan principal must equal the balance sheet's
   `Total Loans Payable`.

## 6. PDF parsing notes (this PMS format)

`pypdf` extracts text with column quirks — handle them:

- **Orphan totals:** subtotal rows (e.g. `Total Building`, `TOTAL ASSETS`) lose
  their inline amount; the values arrive as a trailing block of bare numbers in
  the same order. Map labels->values by order, and verify with tie-out #1.
- **Split dates:** transaction dates extract as `MM/DD/ YYYY` (note the space).
  The `MM/DD/YYYY at HH:MM` form is the *edited-at* timestamp — use the
  transaction date, fall back to the timestamp only if needed.
- **Headers** identify the property: `Properties: <street> <city>, <ST> <zip>`
  and the as-of date: `As of: MM/DD/YYYY`.
- The general-ledger file is detected by a filename containing `general_ledger`,
  `ledger`, or `gl`.

## 7. Reference test cases — your output MUST match these

### 52 Hawkin Road, Medford NJ — as of 2026-06-09
```
capitalized = TOTAL ASSETS 298,483.03 - Total Cash (-6,655.69) = 305,138.72
+ P&L operating expenses (Total Expense)                        =   6,634.18
- income received (Total Income, forfeited U&O "Rent")          = -50,000.00
--------------------------------------------------------------------------
Total Capital Invested .................................. $261,772.90
Accrued Interest @ 12% (actual/365) ..................... $ 37,655.80
All-In Position ......................................... $299,428.70
Breakeven Sale Price (6% cost of sale) .................. $318,541.17
```
Loan draws used for interest (Return-of-Capital bridge excluded):
```
Arknew Funding   170,000.00  @ 2024-10-30
Arknew Funding    33,200.00  @ 2025-12-16   (30,000 + 3,000 + 200)
Arknew Funding    16,800.00  @ 2025-12-18   (Stanger wire)
Oak Tree Equities 10,000.00  @ 2024-12-17
Oak Tree Equities 20,000.00  @ 2026-05-08
EXCLUDED: Oak Tree 162,822.32 advanced 2024-10-10, repaid 2024-10-30
          ("Return of Capital") -> cancels FIFO, no interest
Outstanding principal = 250,000.00 = balance sheet Total Loans Payable  ✓
```

### 511 Shires Way, Egg Harbor NJ — as of 2026-06-09
```
Total Capital Invested .................................. $280,911
Accrued Interest @ 12% .................................. $ 32,479
All-In Position ......................................... $313,390
Breakeven Sale Price .................................... $333,394
```

A correct implementation reproduces these. The included `analyze_project.py`
does. Validate any alternative against both before trusting it.

## 8. Outputs & naming

Per property, write to `outputs/<property>/`:
- `<Property> - Board Summary <YYYY-MM-DD>.pdf`  (named by the inbox folder)
- `board_summary.html`  (quick view)
- `workpaper.csv`  (every line item + per-draw interest — the audit trail)
- `exceptions.csv`, `summary.json`, `deal.json`, `run.log`

## 9. Config (`config/project_config.json`)
```json
{
  "default_interest_rate": 0.12,
  "day_count": 365,
  "selling_cost_pct": 0.06,
  "target_price_offsets": [-20000, 0, 20000, 50000]
}
```

## 10. Run it
```
python .claude/skills/property-cfo-analysis/scripts/analyze_project.py \
  --input-dir  "inbox/<property>" \
  --config     "config/project_config.json" \
  --output-dir "outputs/<property>" \
  --project-name "<property>"
```
The watcher `watch_inbox.py` calls exactly this per folder. No AI runs at
analysis time — the methodology above is the entire "intelligence," frozen in
code.
