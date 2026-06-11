# START HERE — Real Estate CFO Board Report System

This project turns a property's three financial statements (balance sheet,
income statement, general ledger) into a **one-page board PDF**: total capital
invested, 12% accrued interest, all-in position, and the breakeven sale price.

There are **two ways to run it**. You can use either or both:

| | Local (your PC) | Cloud (Google Drive) |
|---|---|---|
| Trigger | Drop a folder in `inbox\`, run `run_cfo_now.bat` | Drop files in the LIGHTHOUSE `CFO Report Inbox` |
| Engine | Plain Python, **no AI, offline, no limits** | Claude routine reads the PDFs |
| Output | `outputs\<property>\<property> - Board Summary <date>.pdf` | PDF saved into the property's Drive folder |
| Best for | Everyday use, fast, private, unlimited | Phone / hands-off; exceptions |

Full local guide: **`SETUP-LOCAL-WATCHER.md`**.
Cloud routine job spec: **`AUTOMATION.md`**.

---

## Where this lives

- **On GitHub:** https://github.com/jerrywest1/contract-approval
  (default branch `main` — always the current version)
- **On your PC:** `C:\Users\yeruchem\CODE\contract-approval`

The PC folder is a **clone** of the GitHub repo, so the two stay linked: you
pull updates down and (if you want) push changes up.

---

## Open it in VS Code

1. Open **VS Code**.
2. **File → Open Folder…** → choose `C:\Users\yeruchem\CODE\contract-approval` → **Open**.
   (Or in a terminal: `code C:\Users\yeruchem\CODE\contract-approval`.)
3. To read any `.md` file nicely, open it and press **Ctrl+Shift+V** (Markdown preview).
4. To run things, open the built-in terminal: **Terminal → New Terminal**.

### Get the latest version (pull from GitHub)
- **Easy way:** the **Source Control** icon on the left (the branch icon) →
  **… menu → Pull**.
- **Terminal way:** `git pull`

> If `git pull` ever complains that you have local changes, run
> `git stash` first (sets your edits aside safely), then `git pull`. Nothing is
> deleted — `git stash list` shows what was set aside.

---

## Daily use (local)

1. In `inbox\`, make a **folder named exactly how you want the report titled**
   — e.g. `511 Shires Way`.
2. Drop the **3 PDFs** into it. The general-ledger file name must contain
   `general_ledger`, `ledger`, or `gl`.
3. **Double-click `run_cfo_now.bat`** (make a desktop shortcut to it).
4. The report appears in `outputs\511 Shires Way\511 Shires Way - Board Summary <date>.pdf`,
   alongside `workpaper.csv` (the full audit trail) and `summary.json`.

Prefer hands-free? Double-click **`start_watcher_visible.bat`** and minimize the
window — it auto-processes drops while open. (The hidden always-on version is
blocked by this PC's security software, so use the visible window or the
one-click `.bat`.)

---

## What's in the folder

```
contract-approval\
  run_cfo_now.bat              <- one-click: process inbox now (daily driver)
  start_watcher_visible.bat    <- auto-process while window stays open
  stop_watcher.bat             <- stop any running watcher
  install_startup_watcher.ps1  <- (optional) install deps + auto-start
  uninstall_startup_watcher.ps1
  config\project_config.json   <- interest rate, selling-cost %, price spread
  inbox\<property>\            <- you drop the 3 PDFs here
  outputs\<property>\          <- the board PDF + workpaper land here
  logs\                        <- watcher activity logs
  .claude\skills\property-cfo-analysis\scripts\
      analyze_project.py       <- the deterministic analyzer (reads the PDFs)
      watch_inbox.py           <- the folder watcher
      analyze.py               <- the math engine (basis, interest, breakeven)
      generate_pdf.py          <- the board-PDF renderer
      upload_to_drive.py       <- cloud-only: binary-safe Drive upload
  START-HERE.md  SETUP-LOCAL-WATCHER.md  AUTOMATION.md  README.md
```

## Change the assumptions
Edit `config\project_config.json`:
- `default_interest_rate` (0.12 = 12%)
- `selling_cost_pct` (0.06 = 6%)
- `target_price_offsets` — the four sale-price scenarios, relative to breakeven
  rounded to the nearest $10k (e.g. `[-20000, 0, 20000, 50000]`).

Save, then re-run — delete `outputs\<property>\.last_run.json` first to force a
re-run of an already-processed property.
