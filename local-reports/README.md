# AppFolio → CFO Report Inbox (local script)

A small Node + Playwright script that runs **on your PC**, logs into AppFolio
with a saved browser profile, and saves three PDFs straight into
`G:\Shared drives\LIGHTHOUSE\CFO Report Inbox`.

No Apify, no Google service account, no Drive API — because the script runs on
your machine it can write to the `G:\` drive directly, and it logs in from your
own machine/IP so MFA is only needed about once a month.

## Reports

| Report | Basis | Date |
| --- | --- | --- |
| Balance Sheet | Accrual | As of current date |
| Income Statement | Accrual | All time |
| General Ledger | Accrual | All accounts, all time |

## One-time setup (Windows)

1. Install [Node.js](https://nodejs.org) (LTS).
2. Open **Command Prompt** in this folder and run:
   ```
   npm install
   npx playwright install chromium
   ```
3. Log in once:
   ```
   node download-reports.js login
   ```
   A browser window opens — sign into AppFolio and complete MFA. When the
   dashboard loads, the window closes and the session is saved.

## Normal run

Double-click **`run-reports.bat`**. A small popup asks **which property** to run
for — type the property name exactly as it appears in AppFolio, or leave it
blank for **All Properties** (consolidated). Then it downloads all three reports
for that property and hits the inbox.

To run a different property, just run it again and type a different name.

PDFs are written to `G:\Shared drives\LIGHTHOUSE\CFO Report Inbox`, named with
the date, property, and report, e.g.:
```
2026-06-10_Maple_Apartments_Balance_Sheet.pdf
2026-06-10_Maple_Apartments_Income_Statement.pdf
2026-06-10_Maple_Apartments_General_Ledger.pdf
```
(so different properties never overwrite each other.)

Prefer the command line? `node download-reports.js` prompts for the property in
the terminal instead.

## Monthly MFA

About once a month AppFolio will ask for MFA again. If a run says it's not
logged in, just run `node download-reports.js login` once more to refresh the
session.

## Options (environment variables)

| Var | Default | Purpose |
| --- | --- | --- |
| `APPFOLIO_URL` | `https://westmarq.appfolio.com` | Portal URL |
| `REPORT_DIR` | `G:\Shared drives\LIGHTHOUSE\CFO Report Inbox` | Where PDFs are saved |
| `PROPERTY` | _(popup asks)_ | Property name; blank = All Properties |
| `HEADLESS` | _(off)_ | `1` = no visible window (only after login is saved) |
| `DEBUG` | _(off)_ | `1` = save screenshots + HTML to `./debug` each step |

## Scheduling (optional)

Use **Windows Task Scheduler** to run `node download-reports.js` on a schedule
(e.g. monthly). The PC must be on at that time. Point the action at your Node
install with this folder as "Start in". If a scheduled run hits the monthly MFA
prompt it exits cleanly with a message; just run the `login` command once.

## First-run tuning

AppFolio's exact report URLs and the Export→PDF buttons differ per account, so
the selectors in `download-reports.js` are best-effort. Run once with `DEBUG=1`:
the `./debug` folder will hold screenshots + HTML of each step, which we use to
confirm/fix the three `REPORT_PATHS` and the export controls.
```
set DEBUG=1
node download-reports.js
```
