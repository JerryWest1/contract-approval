# Real Estate CFO Analyzer

Drop a property's **balance sheet, income statement, and general ledger** into a
folder and get back a **board-ready one-page PDF** that answers:

1. **How much am I in it for?** — total capital invested (all-in cost basis).
2. **How much interest is owed?** — accrued at **12%/yr simple, actual/365**
   per funding entry (rate overridable per entry).
3. **What must I sell it for?** — the **breakeven sale price** and **profit at
   target prices**.

The PDF is saved locally and uploaded to a **Google Drive subfolder named after
the property** for sharing with board members.

## How it's built (Skills + Agents)

| Piece | Path | Role |
|-------|------|------|
| **CFO subagent** | `.claude/agents/real-estate-cfo.md` | Expert persona that reads your financial files and extracts every cost into structured data. |
| **Skill** | `.claude/skills/property-cfo-analysis/SKILL.md` | The drop-in workflow that orchestrates extraction → math → PDF → Drive upload. |
| **Math engine** | `.claude/skills/.../scripts/analyze.py` | Deterministic, reproducible figures (basis, interest, breakeven, scenarios). |
| **PDF builder** | `.claude/skills/.../scripts/generate_pdf.py` | The one-page board summary. |
| **Methodology** | `.claude/skills/.../references/methodology.md` | Audit trail / worked examples behind every number. |

## Quick start

1. **Create a deal folder** and drop your files in:
   ```
   deals/<Property Name>/inputs/   ← balance sheet, P&L, general ledger
   ```
2. **Ask Claude Code** (in this repo):
   > "Run the property-cfo-analysis skill on deals/<Property Name>"

   Claude (as the CFO agent) reads the files, fills in `deal.json`, then runs:
   ```bash
   python3 .claude/skills/property-cfo-analysis/scripts/analyze.py "deals/<Property Name>/deal.json"
   python3 .claude/skills/property-cfo-analysis/scripts/generate_pdf.py "deals/<Property Name>/results.json"
   ```
3. **Review & share** — the PDF lands in the deal folder and is uploaded to the
   matching Google Drive subfolder.

## Worked example

`deals/Sample - Maple Street Apartments/` is a complete, runnable example
(illustrative data). It produces `Maple_Street_Apartments_Board_Summary.pdf`:

- Total capital invested: **$1,957,600**
- Accrued interest @ 12%: **$541,633**
- All-in position: **$2,499,233**
- Breakeven sale price: **$2,658,759**

## Requirements

Python 3 with two libraries (installed automatically by the skill if missing):

```bash
python3 -m pip install reportlab openpyxl
```

## Customizing

Everything is driven by `deal.json` per property — see the schema and field
rules in `.claude/skills/property-cfo-analysis/SKILL.md`. Common tweaks:

- **Different interest rate** — set `default_interest_rate`, or `interest_rate`
  on a single entry.
- **Costs that don't earn interest** — `"accrues_interest": false` on the entry.
- **Selling-cost assumption** — `selling_cost_pct` (default 6%).
- **Target prices** — `target_sale_prices: [ ... ]`.
