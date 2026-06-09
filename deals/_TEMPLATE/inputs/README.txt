Drop your property's financial files in THIS folder:

  • Balance Sheet        (PDF, Excel, or CSV)
  • Income Statement/P&L  (PDF, Excel, or CSV)
  • General Ledger        (PDF, Excel, or CSV)  <-- most important; dates drive interest

Then open Claude Code in this repo and say, for example:

  "Run the property-cfo-analysis skill on deals/Maple Street Apartments"

Claude will read the files, extract every cost into deal.json, compute your
cost basis + 12% accrued interest + breakeven sale price, and produce a
one-page board PDF (saved here and uploaded to the matching Google Drive
folder).
