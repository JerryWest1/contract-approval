# AppFolio CFO Reports → Google Drive (Apify Actor)

Logs into AppFolio with a regular login (no API), exports three financial
reports as PDF, and uploads them to **LIGHTHOUSE › CFO Report Inbox** on Google
Shared Drive. Because Google Drive for Desktop mounts that shared drive at
`G:\Shared drives\LIGHTHOUSE\CFO Report Inbox`, the files appear there
automatically once synced.

## Reports exported

| Report | Basis | Date |
| --- | --- | --- |
| Balance Sheet | Accrual | As of current date |
| Income Statement | Accrual | All time |
| General Ledger | Accrual | All accounts, all time |

## How delivery works

```
Apify (cloud) ──Playwright──▶ AppFolio web portal ──PDF export──▶ Apify
      │
      └── Google Drive API ──▶ LIGHTHOUSE / CFO Report Inbox
                                   │ (Google Drive for Desktop sync)
                                   ▼
                       G:\Shared drives\LIGHTHOUSE\CFO Report Inbox
```

Apify runs in the cloud and **cannot write to the `G:\` drive directly** — the
`G:\` path only exists on a machine running Google Drive for Desktop. Uploading
through the Drive API puts the files in the same folder, and they sync down.

## One-time setup

1. **Google service account**
   - Create a service account in Google Cloud and download its JSON key.
   - Add the service account email as a **Content manager** of the LIGHTHOUSE
     shared drive (Shared Drive → Manage members).
   - Paste the JSON into the `googleServiceAccountJson` input.
2. **AppFolio**
   - Set `appfolioBaseUrl` (e.g. `https://yourcompany.appfolio.com`),
     `appfolioEmail`, `appfolioPassword`.
3. **First run with `debugMode: true`** (default). The Actor saves screenshots
   and HTML to the key-value store at each step so the report URLs / form
   selectors in `src/appfolio.js` can be confirmed against the live portal.

## MFA (monthly)

AppFolio remembers the device for ~30 days, so MFA is only requested about once
a month. When a run reports `MFA_REQUIRED`, re-run once with the fresh code in
the `mfaCode` input. The Actor ticks "remember this device" and saves the
session, so subsequent runs need no code until the next monthly prompt.

## Scheduling

Use Apify Schedules to run on whatever cadence the CFO needs (e.g. monthly).
If a scheduled run hits the monthly MFA prompt it will fail with a clear
`MFA_REQUIRED` message; just re-run once with a code.

## ⚠️ Status / what still needs the live portal

The login flow, report navigation, and PDF-export steps in `src/appfolio.js`
use **best-effort selectors** because AppFolio's exact report URLs and form
fields differ per account and aren't visible without logging in. After the
first `debugMode` run, the saved HTML/screenshots are used to lock down:

- the three `REPORT_PATHS`,
- the login + MFA selectors,
- the accounting-basis / date-range controls,
- the Export → PDF control.

Until those are verified against the real portal, treat this as a scaffold, not
a finished, tested integration. Also confirm automated login is acceptable
under AppFolio's terms for your account.
