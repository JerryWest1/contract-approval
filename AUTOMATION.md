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
   ledger. For each ready property, first resolve its **destination folder**
   (step 4a); **skip** the property if that folder already contains a
   `<Property> - Board Summary *.pdf` (idempotent — never redo work).

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
   - `selling_cost_pct: 0.06`; include 3-4 `target_sale_prices` bracketing the
     breakeven.
   - Run `scripts/analyze.py` then `scripts/generate_pdf.py`.

4. **Save into the property's own folder in the LIGHTHOUSE shared drive** (NOT
   the inbox):

   a. **Resolve the destination folder.** Search LIGHTHOUSE for the property's
      folder by a distinctive part of its name — the street + city (e.g.
      `511 Shires Way, Egg Harbor`, `52 Hawkin Road, Medford`). If a matching
      folder exists, use its **folder ID**. If none exists, **create** a new
      top-level folder in LIGHTHOUSE named `<street>, <city>` and use its ID.

   b. **Upload the board PDF** into that folder. **Do NOT use the chat-style
      Drive connector to upload** — it corrupts binary PDFs. Use the binary-safe
      uploader (service-account key in `GOOGLE_SERVICE_ACCOUNT_JSON`), passing
      the property folder's **ID**:

      ```bash
      pip install -q google-api-python-client google-auth
      python3 .claude/skills/property-cfo-analysis/scripts/upload_to_drive.py \
        --file "deals/<Property Name>/<Property Name> - Board Summary <YYYY-MM-DD>.pdf" \
        --drive "LIGHTHOUSE" \
        --folder "<the property folder's ID>"
      ```
      The connector is fine for reading/listing; only the upload must go through
      this script. After upload, open the link it prints and confirm the PDF
      renders fully (not just the header).

   c. **Tidy the inbox.** Move the property's three source files out of the
      `CFO Report Inbox` into that same property folder (use the connector's
      move-file action). This leaves the inbox empty for the next drop and keeps
      a complete record (sources + board PDF) in the property folder.

5. **Never fabricate figures.** Record assumptions in `deal.json`'s `notes`.

## Notes & guardrails
- One property at a time; if several are ready, process each.
- If a file can't be read or a key figure is missing, upload a short
  `<Property> - NEEDS_REVIEW.txt` into the property's folder explaining what's
  missing, instead of producing a misleading PDF.
- The math and PDF are deterministic (the Python scripts). The only "judgment"
  step is the extraction — keep it faithful to the source documents.
