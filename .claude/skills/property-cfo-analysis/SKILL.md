---
name: property-cfo-analysis
description: >
  Act as an expert real-estate CFO. Use when the user drops a balance sheet,
  income statement, and/or general ledger into a deal folder and wants to know
  how much they are "in it for" (total cost basis), how much interest is owed
  (accrued at 12%/yr simple, actual/365, unless noted), the breakeven sale
  price, and profit at target prices — delivered as a professional one-page PDF
  for a Fortune 500 board, saved to a Google Drive subfolder named after the
  property. Trigger on requests like "analyze this property," "how much am I in
  it for," "what do I need to sell it for," or "make a board summary."
---

# Property CFO Analysis

Turn raw property financials into a board-ready, one-page investment-position
PDF. The skill combines an intelligent extraction step (you, reasoning as a CFO)
with a deterministic math engine and a fixed-format PDF, so the numbers are
always reproducible and audit-traceable.

## Pipeline

```
inputs/ (balance sheet, P&L, general ledger)
        │  1. extract  (you, as the real-estate-cfo agent)
        ▼
deal.json
        │  2. analyze.py   → basis, interest (12% actual/365), breakeven, scenarios
        ▼
results.json
        │  3. generate_pdf.py  → one-page board PDF
        ▼
<Property>_Board_Summary.pdf
        │  4. upload to Google Drive  (shared drive ▸ subfolder = property name)
        ▼
shareable link
```

## How to run it

### Step 0 — Locate the deal
The user drops files into `deals/<Property Name>/inputs/`. If they just attached
files, create `deals/<Property Name>/inputs/` and put them there. Copy
`deals/_TEMPLATE/deal.json` as a starting point.

### Step 1 — Extract figures (act as the CFO)
For best results, hand the extraction to the **real-estate-cfo** subagent (it
holds the detailed extraction rules). Read every file in `inputs/` — PDF, Excel,
CSV, or image — and build `deal.json` capturing **every dollar the owner has put
in**, because the goal is *what must we sell for to make a profit*.

Pull dated line items from the **general ledger** (dates drive interest). Tie GL
totals to the **balance sheet**. Use the **income statement** to find
owner-funded operating shortfalls and carrying costs. Never invent a number; put
assumptions in `notes`.

### Step 2 — Run the math
```bash
python3 .claude/skills/property-cfo-analysis/scripts/analyze.py "deals/<Property>/deal.json"
```
Writes `results.json` next to `deal.json` and prints the headline figures.

### Step 3 — Build the PDF
```bash
python3 .claude/skills/property-cfo-analysis/scripts/generate_pdf.py "deals/<Property>/results.json" -o "deals/<Property>/<Property>_Board_Summary.pdf"
```

### Step 4 — Save to Google Drive
Save into the **shared drive**, in a **subfolder named after the property**:
1. Find the shared drive and locate/create a subfolder matching the property
   name (use the Google Drive MCP tools: find folder → create folder if missing).
2. Upload the PDF into that subfolder.
3. Return the shareable link to the user. Always keep the local copy as the
   reliable fallback.

If reportlab/openpyxl are missing, install with:
`python3 -m pip install reportlab openpyxl`.

## deal.json schema

```json
{
  "property": {
    "name": "Maple Street Apartments",
    "address": "123 Maple St, Austin, TX",
    "as_of_date": "2026-06-09",
    "default_interest_rate": 0.12,
    "day_count": 365,
    "selling_cost_pct": 0.06,
    "target_sale_prices": [2500000, 2750000, 3000000]
  },
  "entries": [
    { "date": "2024-01-15", "description": "Purchase price",
      "category": "Acquisition", "amount": 1500000 },
    { "date": "2024-03-01", "description": "Roof replacement",
      "category": "Capital Improvements", "amount": 85000 },
    { "date": "2024-06-30", "description": "Property tax 2024",
      "category": "Carrying Costs", "amount": 28000,
      "interest_rate": 0.10 },
    { "date": "2024-09-01", "description": "Brokerage deposit (no return)",
      "category": "Other", "amount": 5000, "accrues_interest": false }
  ],
  "notes": "12% default preferred return; property-tax entry carries 10% per loan doc."
}
```

**Field rules**
- `amount` — dollars the owner funded (positive).
- `date` — transaction date; drives `days_out`. Accepts `YYYY-MM-DD`, `MM/DD/YYYY`.
- `interest_rate` — optional per-entry override of the 12% default.
- `accrues_interest` — set `false` for costs that earn no preferred return.
- `category` — free text; rolls up on the PDF (e.g., Acquisition, Capital
  Improvements, Carrying Costs, Soft Costs, Operating).
- `selling_cost_pct` — assumed cost of sale (default 6%) used for breakeven.
- `target_sale_prices` — prices to show profit/ROI for. If omitted, ask the user
  for 2–3 targets, or estimate from comps and note the assumption.

## The math (so you can explain it to the board)

- **Total cost basis** = Σ entry amounts — everything the owner is in it for.
- **Accrued interest** (per entry) = `amount × rate × (days_out ÷ 365)`,
  simple interest, where `days_out` = (as_of_date − entry date). Default
  `rate` = 12%/yr; override per entry when a document says otherwise.
- **All-in position** = cost basis + accrued interest.
- **Breakeven sale price** = `all_in ÷ (1 − selling_cost_pct)` — the price at
  which net proceeds (after selling costs) recover everything owed.
- **Profit at price P** = `P × (1 − selling_cost_pct) − all_in_position`.

See `references/methodology.md` for worked examples and edge cases.
