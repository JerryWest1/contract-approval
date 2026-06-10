# Local CFO Watcher — drop 3 PDFs in a folder, get a board report

Runs entirely on your PC. **No Claude at runtime, no internet, no daily run
limits, nothing for security software to flag** — the financial rules (verified
against 52 Hawkin Road to the penny) are frozen into plain Python.

## One-time install (PowerShell)

```powershell
cd C:\Users\yeruchem\CODE
git clone https://github.com/jerrywest1/contract-approval.git
cd contract-approval
powershell -ExecutionPolicy Bypass -File .\install_startup_watcher.ps1
```

That installs `pypdf` + `reportlab`, creates `inbox/`, `outputs/`, `logs/`,
starts the watcher hidden, and adds a Startup shortcut so it runs at every
log-on (no admin rights needed).

## Daily use

1. Open `C:\Users\yeruchem\CODE\contract-approval\inbox\`
2. Make a **folder per property** and drop the 3 PDFs in:

   ```
   inbox\
     52 Hawkin\
       balance_sheet-20260609.pdf
       income_statement_date_range-20260609.pdf
       general_ledger-20260609.pdf
   ```
   The general-ledger file name must contain `general_ledger`, `ledger`, or `gl`.

3. ~30 seconds later, the report is in:

   ```
   outputs\52 Hawkin\
     board_summary.pdf      <- the one-page board report
     board_summary.html     <- quick-view version
     workpaper.csv          <- every line item + interest calc (audit trail)
     exceptions.csv         <- any warnings / tie-out problems
     summary.json           <- headline numbers, machine-readable
     deal.json              <- extracted figures (same schema as the cloud flow)
     run.log                <- what happened on the last run
   ```

Unchanged folders are never rerun. To force a rerun, re-copy the folder or
delete `outputs\<project>\.last_run.json`.

## How the numbers are computed (locked rules)

- **Capital invested** = capitalized assets from the balance sheet (TOTAL
  ASSETS less cash) **plus** P&L operating expenses **minus** income already
  received. A/P and cash overdrafts are excluded (funding/timing items).
- **Interest** = 12% simple, actual/365, per dated loan draw found in the GL's
  "Loans Payable" accounts. "Return of Capital" repayments cancel their draw
  (no interest); journal entries are ignored; other repayments stop accrual
  from their date. Rates/percentages live in `config\project_config.json`.
- **Breakeven** = (capital + interest) ÷ (1 − 6% selling costs).

**No fabrication:** every statement is tied out (leaf items vs. totals, GL
running-balance chain, GL loans vs. balance sheet). If anything doesn't
reconcile, you get `NEEDS_REVIEW.txt` + `exceptions.csv` instead of a PDF.

## Operations

```powershell
# is it running?
Get-CimInstance Win32_Process |
  Where-Object { $_.Name -like 'python*' -and $_.CommandLine -like '*watch_inbox.py*' } |
  Select-Object ProcessId,Name

# watch the log
Get-Content "logs\watcher.log" -Tail 50

# one-off scan (foreground)
python .claude\skills\property-cfo-analysis\scripts\watch_inbox.py --once

# stop now (Startup shortcut stays)        -> double-click stop_watcher.bat
# remove auto-start + stop                 -> powershell -ExecutionPolicy Bypass -File .\uninstall_startup_watcher.ps1
# restart after pulling new code           -> stop_watcher.bat, then start_watcher_hidden.ps1
```

## Troubleshooting

- **No report appears** — check `outputs\<project>\run.log` and
  `exceptions.csv`; most often a missing/oddly-named file (see GL naming rule).
- **`board_summary.pdf` didn't update** — you probably have it open; look for
  `board_summary_YYYYMMDD_HHMMSS.pdf` / `board_summary_latest.pdf`.
- **Files dropped loose in `inbox\`** — they must be inside a project folder:
  `inbox\<property name>\file.pdf`.
- **A statement from a different reporting system** — the parser is tuned to
  your property-management report format. If a statement won't reconcile, the
  run fails clearly; send me the file and I'll extend the parser.
