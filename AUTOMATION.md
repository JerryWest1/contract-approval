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
   - **Count ALL money spent on the property as basis** — both the *capitalized*
     costs on the balance sheet (Building, Improvements, Construction, Carrying)
     AND the *operating expenses* run through the income statement / P&L (e.g.
     attorney & professional fees, insurance expense, real-estate tax, postage).
     These P&L expenses are real dollars spent and are NOT in the capitalized
     balance-sheet totals, so they must be added — do not omit them.
   - Capitalized costs and P&L operating expenses are basis entries
     (`accrues_interest: false`).
   - Loan / hard-money draws use `basis: false` and accrue **12% simple,
     actual/365** interest from each draw date.
   - **Net any income already received** (e.g. forfeited U&O / rent) as a
     negative basis entry.
   - **Do NOT** add accounts payable or operating-cash overdraft as basis — those
     are *funding/timing* items (how the deal was financed), not costs incurred.
   - `selling_cost_pct: 0.06`; include 3–4 `target_sale_prices` bracketing the
     breakeven.
   - Run `scripts/analyze.py` then `scripts/generate_pdf.py`.

4. **Upload** the generated `<Property> - Board Summary <YYYY-MM-DD>.pdf` back
   into the **same Drive folder** it came from. **Do NOT use the chat-style Drive
   connector to upload** — it corrupts binary PDFs. Instead use the binary-safe
   uploader (a service-account credential must be present as
   `GOOGLE_SERVICE_ACCOUNT_JSON`):

   ```bash
   pip install -q google-api-python-client google-auth
   python3 .claude/skills/property-cfo-analysis/scripts/upload_to_drive.py \
     --file "deals/<Property Name>/<Property Name> - Board Summary <YYYY-MM-DD>.pdf" \
     --drive "LIGHTHOUSE" \
     --folder "<the exact Drive folder name this property came from>"
   ```
   The connector is fine for **reading/listing** files; only the **upload** must
   go through this script. After upload, open the link it prints and confirm the
   PDF renders fully (not just the header).

5. **Never fabricate figures.** Record assumptions in `deal.json`'s `notes`.

## Notes & guardrails
- One property at a time; if several are ready, process each.
- If a file can't be read or a key figure is missing, write a short
  `NEEDS_REVIEW.txt` into that property's Drive folder explaining what's missing,
  instead of producing a misleading PDF.
- The math and PDF are deterministic (the Python scripts). The only "judgment"
  step is the extraction — keep it faithful to the source documents.
