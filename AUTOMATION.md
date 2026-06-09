# Automation — standing instructions for the cloud CFO routine

This file is the "job description" for the automated cloud run (a Claude Code
**Routine**, or any headless runner). It reuses the `property-cfo-analysis`
skill and the `real-estate-cfo` agent in this repo — the routine is just the
*trigger*; the recipe lives in `.claude/`.

## The job (fired by a webhook when files are dropped in the inbox)

Using the **Google Drive** connector, look **ONLY** inside the dedicated drop
zone: the **`CFO Report Inbox`** folder in the **LIGHTHOUSE** shared drive
(folder ID `18EJXtLspRF4_aiY4SLIU-AdjIVzfpVG9`). The user drops a property's
financial files **directly into this folder**. **Do not scan anywhere else in
the drive.**

1. **Group the inbox files by property.** Each financial document names its
   property in the header (e.g. `Properties: 52 Hawkin Road Medford NJ 08055`).
   Group the loose files in the inbox by that property. A property is **ready**
   when its group has a balance sheet, an income statement, and a general
   ledger. **Skip** any property for which a file named
   `<Property> - Board Summary *.pdf` already exists in the inbox (idempotent —
   never redo work). For each ready, not-yet-done property:

2. **Download** that property's source files into
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

4. **Upload** the generated `<Property> - Board Summary <YYYY-MM-DD>.pdf` into the
   **`CFO Report Inbox`** folder (next to the source files, so the user sees it
   appear where they dropped them). **Do NOT use the chat-style Drive connector
   to upload** — it corrupts binary PDFs. Use the binary-safe uploader (the
   service-account credential is in `GOOGLE_SERVICE_ACCOUNT_JSON`), passing the
   inbox **folder ID**:

   ```bash
   pip install -q google-api-python-client google-auth
   python3 .claude/skills/property-cfo-analysis/scripts/upload_to_drive.py \
     --file "deals/<Property Name>/<Property Name> - Board Summary <YYYY-MM-DD>.pdf" \
     --drive "LIGHTHOUSE" \
     --folder "18EJXtLspRF4_aiY4SLIU-AdjIVzfpVG9"
   ```
   The connector is fine for **reading/listing**; only the **upload** must go
   through this script. After upload, open the link it prints and confirm the PDF
   renders fully (not just the header).

5. **Never fabricate figures.** Record assumptions in `deal.json`'s `notes`.

## Notes & guardrails
- One property at a time; if several are ready, process each.
- If a file can't be read or a key figure is missing, upload a short
  `<Property> - NEEDS_REVIEW.txt` into the `CFO Report Inbox` explaining what's
  missing, instead of producing a misleading PDF.
- The math and PDF are deterministic (the Python scripts). The only "judgment"
  step is the extraction — keep it faithful to the source documents.
