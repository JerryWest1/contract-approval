# Automation — standing instructions for the cloud CFO routine

This file is the "job description" for the automated cloud run (a Claude Code
**Routine**, or any headless runner). It reuses the `property-cfo-analysis`
skill and the `real-estate-cfo` agent in this repo — the routine is just the
*trigger*; the recipe lives in `.claude/`.

## The job (runs on a schedule, e.g. every 15 minutes)

Using the **Google Drive** connector, look in the **LIGHTHOUSE shared drive**
for property folders (e.g. `52 Hawkin Road, Medford`). For each property folder:

1. **Check if it needs processing.** It needs processing if it contains a
   balance sheet, an income statement, and a general ledger (PDF/Excel/CSV) and
   does **not** already contain a file named like `* Board Summary *.pdf`.
   Skip folders that already have a board summary (idempotent — never redo work).

2. **Download** the source files from that Drive folder into
   `deals/<Property Name>/inputs/`.

3. **Run the skill.** Act as the `real-estate-cfo` agent and follow
   `.claude/skills/property-cfo-analysis/SKILL.md`:
   - Extract every owner cost and each dated loan/advance into
     `deals/<Property Name>/deal.json`.
   - Capitalized costs are basis entries (`accrues_interest: false`).
   - Loan / hard-money draws use `basis: false` and accrue **12% simple,
     actual/365** interest from each draw date.
   - **Net any income already received** (e.g. forfeited U&O / rent) as a
     negative basis entry.
   - `selling_cost_pct: 0.06`; include 3–4 `target_sale_prices` bracketing the
     breakeven.
   - Run `scripts/analyze.py` then `scripts/generate_pdf.py`.

4. **Upload** the generated `<Property> - Board Summary <YYYY-MM-DD>.pdf` back
   into the **same Drive folder** it came from.

5. **Never fabricate figures.** Record assumptions in `deal.json`'s `notes`.

## Notes & guardrails
- One property at a time; if several are ready, process each.
- If a file can't be read or a key figure is missing, write a short
  `NEEDS_REVIEW.txt` into that property's Drive folder explaining what's missing,
  instead of producing a misleading PDF.
- The math and PDF are deterministic (the Python scripts). The only "judgment"
  step is the extraction — keep it faithful to the source documents.
