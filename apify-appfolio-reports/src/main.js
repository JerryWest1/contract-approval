import { Actor, log } from 'apify';
import { loadSessionState, login, exportReportPdf } from './appfolio.js';
import { makeDriveClient, uploadPdf } from './drive.js';

await Actor.init();

const input = (await Actor.getInput()) ?? {};
const {
    appfolioBaseUrl,
    appfolioEmail,
    appfolioPassword,
    mfaCode,
    reports = [
        { key: 'balance_sheet', label: 'Balance Sheet', basis: 'Accrual', dateMode: 'as_of', asOf: 'today' },
        { key: 'income_statement', label: 'Income Statement', basis: 'Accrual', dateMode: 'range', range: 'all_time' },
        { key: 'general_ledger', label: 'General Ledger', basis: 'Accrual', dateMode: 'range', range: 'all_time', accounts: 'all' },
    ],
    googleServiceAccountJson,
    driveFolderId = '18EJXtLspRF4_aiY4SLIU-AdjIVzfpVG9',
    debugMode = true,
} = input;

if (!appfolioBaseUrl || !appfolioEmail || !appfolioPassword) {
    throw new Error('appfolioBaseUrl, appfolioEmail and appfolioPassword are required.');
}
if (!googleServiceAccountJson) {
    throw new Error('googleServiceAccountJson is required to upload the PDFs to the shared drive.');
}

const drive = makeDriveClient(googleServiceAccountJson);

// Launch a browser, reusing a saved session so MFA is only needed ~monthly.
const storageState = await loadSessionState();
const browser = await Actor.launchPlaywright({
    useChrome: true,
    launchOptions: { headless: true },
});
const context = await browser.newContext({ storageState, acceptDownloads: true });
const page = await context.newPage();

const results = [];

try {
    await login(page, context, {
        baseUrl: appfolioBaseUrl,
        email: appfolioEmail,
        password: appfolioPassword,
        mfaCode,
        debug: debugMode,
    });

    for (const report of reports) {
        try {
            const { buffer, fileName } = await exportReportPdf(page, context, {
                baseUrl: appfolioBaseUrl,
                report,
                debug: debugMode,
            });

            const uploaded = await uploadPdf(drive, { buffer, fileName, folderId: driveFolderId });
            log.info(`Uploaded ${fileName} → ${uploaded.webViewLink}`);
            results.push({ report: report.label, fileName, status: 'ok', driveLink: uploaded.webViewLink });
        } catch (err) {
            log.error(`Failed report "${report.label}": ${err.message}`);
            results.push({ report: report.label, status: 'error', error: err.message });
        }
    }
} finally {
    await context.close();
    await browser.close();
}

await Actor.pushData(results);

const failed = results.filter((r) => r.status !== 'ok');
log.info(`Done. ${results.length - failed.length}/${results.length} reports delivered to CFO Report Inbox.`);

await Actor.exit();
