# Run the Property CFO on your Windows PC (auto-run on file drop)

This sets up the analyzer to live on your computer and run **automatically**:
make a folder for a property, drop in the balance sheet, income statement, and
general ledger, and a board-ready PDF appears in that folder ~30 seconds later.

You only do Steps 1–3 **once**. After that it's just "drop files → get PDF."

---

## What you need (one-time)
- **Claude Code** installed and logged in (you already have this ✅)
- **Python 3** — if you don't have it, open PowerShell and run:
  `winget install Python.Python.3.12`
- **Git** (to download the project) — if missing: `winget install Git.Git`

---

## Step 1 — Put the project on your PC
Open **PowerShell** (press Start, type *PowerShell*, Enter) and run:

```powershell
cd $HOME\Documents
git clone https://github.com/jerrywest1/contract-approval.git
cd contract-approval
git checkout claude/real-estate-cfo-analyzer-1hwv9l
```

You now have the project at `Documents\contract-approval`.

## Step 2 — Run the setup
Still in PowerShell, in that folder:

```powershell
powershell -ExecutionPolicy Bypass -File .\windows\setup.ps1
```

This installs the report libraries and registers a background watcher that
**starts automatically every time you log in**. It also starts it right now.

## Step 3 — That's it
The watcher is running. Leave it — it starts on its own from now on.

---

## How to use it (every time)
1. Open **File Explorer** → `Documents\contract-approval\deals`.
2. Make a **new folder** named after the property, e.g. `141 Birch Avenue`.
3. Drop the **3 files** into that folder (balance sheet, income statement,
   general ledger). PDF, Excel, or CSV all work.
4. Wait ~30 seconds. **`141 Birch Avenue_Board_Summary.pdf`** appears in the
   same folder. Open it, share it.

> Tip: name the files clearly (e.g. `balance_sheet.pdf`, `income_statement.pdf`,
> `general_ledger.pdf`) so the extraction is unambiguous.

---

## Good to know
- **It uses your Claude Code login** each time it runs — no extra setup, but each
  run uses your Claude usage like a normal Claude Code session.
- **Re-run a property:** delete its `..._Board_Summary.pdf` from the folder (and
  the hidden `.cfo_processed` file). It will rebuild next time files settle.
- **See what happened:** each property folder gets a `cfo_run.log`; the watcher's
  overall activity is in `auto_runner.log` at the project root.
- **Review before trusting:** the watcher fills in `deal.json` automatically. Open
  it to see exactly which costs and loan draws were used — that's the audit trail.

## Stop / start / check the watcher
The watcher auto-starts via a shortcut in your **Startup folder**, so no admin
rights are needed.

```powershell
# stop it now: end the background process
Get-Process pythonw -ErrorAction SilentlyContinue | Stop-Process

# turn OFF auto-start at log-in (delete the Startup shortcut)
Remove-Item "$([Environment]::GetFolderPath('Startup'))\PropertyCFO-Watcher.lnk"

# start it again now
powershell -ExecutionPolicy Bypass -File .\windows\setup.ps1
```
To watch it live in a visible window instead, double-click `windows\run_watcher.bat`.

## Saving straight to Google Drive (optional)
If you install **Google Drive for Desktop**, your LIGHTHOUSE shared drive shows up
as a normal folder (e.g. `G:\Shared drives\LIGHTHOUSE\...`). Tell me and I'll have
the watcher also drop a copy into the matching property folder there, so it syncs
to Drive automatically — no manual upload.

## Troubleshooting
- **"claude not found"** in `cfo_run.log` → open a new terminal, confirm `claude`
  works, then re-run `windows\setup.ps1`.
- **No PDF after a minute** → open `deals\<property>\cfo_run.log` to see what
  Claude reported. Usually a file was unreadable or a number was missing.
- **Nothing happens** → make sure the files are inside a **subfolder** of `deals\`,
  not loose in `deals\` itself.
