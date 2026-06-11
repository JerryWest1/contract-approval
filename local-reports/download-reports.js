/**
 * AppFolio → CFO Report Inbox (local Playwright script)
 * --------------------------------------------------------------------------
 * Logs into AppFolio using a saved browser profile (so MFA is only needed
 * about once a month), exports three financial reports as PDF, and saves them
 * directly into a local folder — e.g. the Google Drive Shared Drive that maps
 * to G:\Shared drives\LIGHTHOUSE\CFO Report Inbox.
 *
 * USAGE (Windows / macOS / Linux):
 *   1) npm install
 *   2) npx playwright install chromium
 *   3) node download-reports.js login     ← first time / after monthly MFA
 *        A browser window opens. Log into AppFolio (complete MFA). Once you
 *        reach the dashboard, the window closes automatically and the session
 *        is saved.
 *   4) node download-reports.js           ← normal run; downloads the PDFs
 *
 * CONFIG (environment variables, all optional):
 *   APPFOLIO_URL   default https://westmarq.appfolio.com
 *   REPORT_DIR     default G:\Shared drives\LIGHTHOUSE\CFO Report Inbox
 *   HEADLESS       set to "1" to run without a visible window (after login)
 *   DEBUG          set to "1" to save screenshots+HTML to ./debug each step
 * --------------------------------------------------------------------------
 */

import { chromium } from 'playwright';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { mkdir, writeFile } from 'node:fs/promises';
import { createInterface } from 'node:readline/promises';

const __dirname = dirname(fileURLToPath(import.meta.url));

const BASE_URL = (process.env.APPFOLIO_URL || 'https://westmarq.appfolio.com').replace(/\/$/, '');
const REPORT_DIR =
    process.env.REPORT_DIR || 'G:\\Shared drives\\LIGHTHOUSE\\CFO Report Inbox';
// Which property/portfolio scope to run the reports for. Set via the popup /
// prompt at run time (or the PROPERTY env var). Blank = "All Properties"
// (consolidated company-wide statement).
let PROPERTY = process.env.PROPERTY || '';
const PROFILE_DIR = join(__dirname, 'browser-profile');
const DEBUG_DIR = join(__dirname, 'debug');
const HEADLESS = process.env.HEADLESS === '1';
const DEBUG = process.env.DEBUG === '1';

const MODE = process.argv[2] === 'login' ? 'login' : 'run';

// --- The three CFO reports --------------------------------------------------
const REPORTS = [
    { key: 'balance_sheet', label: 'Balance Sheet', basis: 'Accrual', dateMode: 'as_of' },
    { key: 'income_statement', label: 'Income Statement', basis: 'Accrual', dateMode: 'range' },
    { key: 'general_ledger', label: 'General Ledger', basis: 'Accrual', dateMode: 'range', accounts: 'all' },
];

/**
 * PORTAL-SPECIFIC SELECTORS / URLS  ← verify against the live portal.
 * Run once with DEBUG=1; ./debug will contain screenshots + HTML so these can
 * be confirmed and corrected.
 */
const REPORT_PATHS = {
    balance_sheet: '/buffered_reports/balance_sheet?customize=true',
    income_statement: '/buffered_reports/income_statement_date_range?customize=true',
    general_ledger: '/buffered_reports/general_ledger?customize=true',
};

const LOGGED_IN_SELECTOR = 'nav, [data-testid="primary-nav"], .navbar';

async function isLoggedIn(page) {
    return page.locator(LOGGED_IN_SELECTOR).first().isVisible().catch(() => false);
}

async function dump(page, name) {
    if (!DEBUG) return;
    try {
        await mkdir(DEBUG_DIR, { recursive: true });
        await page.screenshot({ path: join(DEBUG_DIR, `${name}.png`), fullPage: true });
        await writeFile(join(DEBUG_DIR, `${name}.html`), await page.content());
        console.log(`  [debug] saved ${name}`);
    } catch (e) {
        console.warn(`  [debug] could not save ${name}: ${e.message}`);
    }
}

function today() {
    return new Date().toISOString().slice(0, 10);
}

/**
 * Ask which property to run for. If a GUI popup (run-reports.bat) already
 * supplied PROPERTY, or this is a non-interactive scheduled run, skip the
 * console prompt. Empty answer => All Properties (consolidated).
 */
async function promptProperty() {
    if (PROPERTY) return; // already provided (popup / env var)
    if (!process.stdin.isTTY) return; // scheduled / non-interactive
    const rl = createInterface({ input: process.stdin, output: process.stdout });
    const answer = await rl.question(
        'Property to run reports for (press Enter for ALL properties): ',
    );
    rl.close();
    PROPERTY = answer.trim();
}

/** Human-friendly + filesystem-safe label for the chosen scope. */
function propertyLabel() {
    return PROPERTY || 'All Properties';
}

// --- Report parameter setters (best-effort) --------------------------------
async function setBasis(page, basis) {
    if (!basis) return;
    const radio = page.locator(`label:has-text("${basis}") input, input[value="${basis}"]`).first();
    if (await radio.isVisible().catch(() => false)) return radio.check();
    const select = page.locator('select[name*="basis"], select[name*="accounting"]').first();
    if (await select.isVisible().catch(() => false)) await select.selectOption({ label: basis }).catch(() => {});
}

async function setAsOf(page) {
    const field = page.locator('input[name*="as_of"], input[name*="to_date"], input[type="date"]').first();
    if (await field.isVisible().catch(() => false)) await field.fill(today());
}

async function setAllTimeRange(page) {
    const from = page.locator('input[name*="from"], input[name*="start"]').first();
    const to = page.locator('input[name*="to"], input[name*="end"]').first();
    if (await from.isVisible().catch(() => false)) await from.fill('2000-01-01');
    if (await to.isVisible().catch(() => false)) await to.fill(today());
}

/**
 * Select the property / portfolio scope on the report form (best-effort).
 * AppFolio usually exposes this as a searchable dropdown or multi-select.
 * "All Properties" means leave it at / choose the consolidated option.
 */
async function setProperty(page, property) {
    if (!property) return;
    const selectors = [
        'select[name*="propert"]',
        'select[name*="portfolio"]',
        '[aria-label*="Propert"]',
        '[placeholder*="Propert"]',
    ];
    for (const sel of selectors) {
        const el = page.locator(sel).first();
        if (!(await el.isVisible().catch(() => false))) continue;
        // Native <select>: pick by visible label.
        if ((await el.evaluate((n) => n.tagName).catch(() => '')) === 'SELECT') {
            await el.selectOption({ label: property }).catch(() => {});
            return;
        }
        // Searchable combobox: type and pick the matching option.
        await el.click().catch(() => {});
        await page.keyboard.type(property).catch(() => {});
        await page.locator(`text="${property}"`).first().click().catch(() => {});
        return;
    }
}

async function openExportMenu(page) {
    const menu = page
        .locator(
            'button:has-text("Export"), button:has-text("Download"), button:has-text("Actions"), ' +
            '[aria-label="Export"], [aria-label*="Print"], [title*="Print"]',
        )
        .first();
    if (await menu.isVisible().catch(() => false)) await menu.click().catch(() => {});
}

async function exportReport(page, report) {
    console.log(`- ${report.label}...`);
    await page.goto(BASE_URL + REPORT_PATHS[report.key], { waitUntil: 'domcontentloaded' });
    await dump(page, `${report.key}-01-form`);

    await setBasis(page, report.basis);
    await setProperty(page, propertyLabel());
    if (report.dateMode === 'as_of') await setAsOf(page);
    else await setAllTimeRange(page);

    await page
        .locator('button:has-text("Run Report"), button:has-text("Run"), button:has-text("Refresh"), input[value*="Run"]')
        .first()
        .click()
        .catch(() => {});
    // Buffered reports generate server-side; give the report time to render.
    await page.waitForLoadState('networkidle').catch(() => {});
    await page.waitForTimeout(3000);
    await dump(page, `${report.key}-02-rendered`);

    // "Print to PDF" either downloads a file or opens the PDF in a new tab —
    // listen for both, guarded so a timeout can never crash the whole run.
    const downloadPromise = page.waitForEvent('download', { timeout: 60_000 }).catch(() => null);
    const popupPromise = page.waitForEvent('popup', { timeout: 60_000 }).catch(() => null);

    await openExportMenu(page);
    await page
        .locator(
            'a:has-text("Print to PDF"), button:has-text("Print to PDF"), ' +
            'a:has-text("PDF"), button:has-text("PDF"), [data-format="pdf"]',
        )
        .first()
        .click({ timeout: 15_000 });

    const propTag = propertyLabel().replace(/[^\w]+/g, '_');
    const fileName = `${today()}_${propTag}_${report.label.replace(/\s+/g, '_')}.pdf`;
    const dest = join(REPORT_DIR, fileName);

    const result = await Promise.race([
        downloadPromise.then((d) => d && { kind: 'download', d }),
        popupPromise.then((p) => p && { kind: 'popup', p }),
    ]);
    if (!result) throw new Error('Print to PDF produced neither a download nor a new tab within 60s.');

    if (result.kind === 'download') {
        await result.d.saveAs(dest);
    } else {
        // PDF opened in a new tab — wait for its final URL, then fetch the
        // bytes with the logged-in session's cookies and save them.
        const popup = result.p;
        await popup.waitForLoadState('domcontentloaded').catch(() => {});
        // Some flows redirect to a generated file; give it a moment.
        await popup.waitForTimeout(2000);
        const pdfUrl = popup.url();
        const resp = await page.request.get(pdfUrl);
        if (!resp.ok()) throw new Error(`Could not fetch PDF (${resp.status()}) from ${pdfUrl}`);
        await writeFile(dest, await resp.body());
        await popup.close().catch(() => {});
    }
    console.log(`  saved → ${dest}`);
}

// --- Main -------------------------------------------------------------------

/**
 * Get a browser context. Two modes:
 *  - Default: the script's own persistent profile (browser-profile/).
 *  - USE_CHROME=1: attach to YOUR running Chrome via CDP (port 9222), reusing
 *    whatever AppFolio session is already logged in there. Chrome must have
 *    been started with start-chrome-debug.bat for this to work.
 */
async function getContext(headless) {
    if (process.env.USE_CHROME === '1') {
        try {
            const browser = await chromium.connectOverCDP('http://localhost:9222');
            const context = browser.contexts()[0];
            if (!context) throw new Error('Chrome is running but has no open window.');
            console.log('Attached to your existing Chrome session.');
            return { context, attached: true };
        } catch (e) {
            throw new Error(
                'Could not attach to Chrome. Start Chrome with start-chrome-debug.bat ' +
                `first, then re-run. (${e.message})`,
            );
        }
    }
    const context = await chromium.launchPersistentContext(PROFILE_DIR, {
        headless,
        acceptDownloads: true,
        viewport: { width: 1400, height: 1000 },
    });
    return { context, attached: false };
}

async function main() {
    await mkdir(REPORT_DIR, { recursive: true }).catch(() => {});

    // login mode forces a visible window; run mode honors HEADLESS.
    const headless = MODE === 'login' ? false : HEADLESS;
    const { context, attached } = await getContext(headless);
    const page = await context.newPage();

    try {
        await page.goto(BASE_URL, { waitUntil: 'domcontentloaded' });

        if (MODE === 'login') {
            console.log('Log into AppFolio in the open window (complete MFA). Waiting...');
            await page.waitForSelector(LOGGED_IN_SELECTOR, { timeout: 5 * 60_000 });
            console.log('Login detected and saved. You can now run: node download-reports.js');
            return;
        }

        if (!(await isLoggedIn(page))) {
            if (headless) {
                throw new Error(
                    'Not logged in. Run "node download-reports.js login" first (or after the ' +
                    'monthly MFA prompt) to refresh the saved session.',
                );
            }
            console.log('Session expired — log in (and complete MFA) in the window. Waiting...');
            await page.waitForSelector(LOGGED_IN_SELECTOR, { timeout: 5 * 60_000 });
        }

        await promptProperty();
        console.log(`\nRunning reports for: ${propertyLabel()}\n`);

        let ok = 0;
        for (const report of REPORTS) {
            try {
                await exportReport(page, report);
                ok++;
            } catch (e) {
                console.error(`  FAILED ${report.label}: ${e.message}`);
            }
        }
        console.log(`\nDone. ${ok}/${REPORTS.length} reports saved to ${REPORT_DIR}`);
    } finally {
        if (attached) {
            // Attached to the user's own Chrome — close only our tab, never
            // their browser.
            await page.close().catch(() => {});
            await context.browser()?.close().catch(() => {});
        } else {
            await context.close();
        }
    }
}

main().catch((e) => {
    console.error(e.message);
    process.exit(1);
});
