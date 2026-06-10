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

```
node download-reports.js
```

The three PDFs are written to `G:\Shared drives\LIGHTHOUSE\CFO Report Inbox`
named like `2026-06-10_Balance_Sheet.pdf`.

## Monthly MFA

About once a month AppFolio will ask for MFA again. If a run says it's not
logged in, just run `node download-reports.js login` once more to refresh the
session.

## Options (environment variables)

| Var | Default | Purpose |
| --- | --- | --- |
| `APPFOLIO_URL` | `https://westmarq.appfolio.com` | Portal URL |
| `REPORT_DIR` | `G:\Shared drives\LIGHTHOUSE\CFO Report Inbox` | Where PDFs are saved |
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
