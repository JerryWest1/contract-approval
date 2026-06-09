import { Actor, log } from 'apify';

const SESSION_KEY = 'APPFOLIO_SESSION';

/**
 * ---------------------------------------------------------------------------
 *  PORTAL-SPECIFIC SELECTORS / URLS  ← VERIFY THESE AGAINST THE LIVE PORTAL
 * ---------------------------------------------------------------------------
 *  AppFolio's exact report paths, form field names, and the "Export to PDF"
 *  control vary by account/version. The values below are best-effort defaults.
 *  Run the Actor once with debugMode=true: it dumps screenshots + HTML for
 *  each step to the key-value store so these can be confirmed and corrected.
 * ---------------------------------------------------------------------------
 */
const REPORT_PATHS = {
    balance_sheet: '/accounting/financials/balance_sheet',
    income_statement: '/accounting/financials/income_statement',
    general_ledger: '/accounting/financials/general_ledger',
};

const LOGIN = {
    emailSelector: 'input[name="user[email]"], #user_email, input[type="email"]',
    passwordSelector: 'input[name="user[password]"], #user_password, input[type="password"]',
    submitSelector: 'button[type="submit"], input[type="submit"]',
    // A selector that only exists once we are logged in (e.g. the top nav).
    loggedInSelector: 'nav, [data-testid="primary-nav"], .navbar',
    // Selectors that indicate an MFA / verification-code challenge.
    mfaSelectors: [
        'input[name="otp"]',
        'input[autocomplete="one-time-code"]',
        'input[name*="verification"]',
        'input[name*="code"]',
    ],
    mfaSubmitSelector: 'button[type="submit"], input[type="submit"]',
};

/** Persist cookies + localStorage so MFA is only needed ~monthly. */
async function saveSession(context) {
    const state = await context.storageState();
    await Actor.setValue(SESSION_KEY, state);
    log.info('Saved AppFolio session state.');
}

/** Restore a previously saved storage state, if any. */
export async function loadSessionState() {
    const state = await Actor.getValue(SESSION_KEY);
    if (state) log.info('Loaded saved AppFolio session state.');
    return state || undefined;
}

async function isLoggedIn(page) {
    return page.locator(LOGIN.loggedInSelector).first().isVisible().catch(() => false);
}

async function detectMfa(page) {
    for (const sel of LOGIN.mfaSelectors) {
        if (await page.locator(sel).first().isVisible().catch(() => false)) return sel;
    }
    return null;
}

/**
 * Ensure we are logged in. Strategy:
 *  1. Try the saved session (covers ~30 days between MFA prompts).
 *  2. If not logged in, submit email/password.
 *  3. If an MFA challenge appears, use the provided mfaCode; if none was
 *     provided, throw a clear "MFA_REQUIRED" error so the operator knows to
 *     re-run once with a fresh code.
 */
export async function login(page, context, { baseUrl, email, password, mfaCode, debug }) {
    await page.goto(baseUrl, { waitUntil: 'domcontentloaded' });

    if (await isLoggedIn(page)) {
        log.info('Already logged in via saved session.');
        return;
    }

    if (debug) await dump(page, '01-login-page');

    await page.fill(LOGIN.emailSelector, email);
    await page.fill(LOGIN.passwordSelector, password);
    await Promise.all([
        page.waitForLoadState('networkidle').catch(() => {}),
        page.click(LOGIN.submitSelector),
    ]);

    const mfaField = await detectMfa(page);
    if (mfaField) {
        if (debug) await dump(page, '02-mfa-challenge');
        if (!mfaCode) {
            throw new Error(
                'MFA_REQUIRED: AppFolio is asking for a verification code. ' +
                'Re-run this Actor once with the "mfaCode" input set to the fresh code; ' +
                'the device will then be remembered for ~30 days.',
            );
        }
        await page.fill(mfaField, mfaCode);
        // Tick "remember this device" if present so MFA stays monthly.
        await page
            .locator('input[type="checkbox"]')
            .first()
            .check()
            .catch(() => {});
        await Promise.all([
            page.waitForLoadState('networkidle').catch(() => {}),
            page.click(LOGIN.mfaSubmitSelector),
        ]);
    }

    if (!(await isLoggedIn(page))) {
        if (debug) await dump(page, '03-login-failed');
        throw new Error('Login failed — could not confirm a logged-in session. Check credentials/selectors.');
    }

    log.info('Login successful.');
    await saveSession(context);
}

/**
 * Export a single report to PDF and return its bytes.
 * Returns { buffer, fileName }.
 */
export async function exportReportPdf(page, context, { baseUrl, report, debug }) {
    const path = REPORT_PATHS[report.key];
    if (!path) throw new Error(`Unknown report key: ${report.key}`);

    await page.goto(baseUrl.replace(/\/$/, '') + path, { waitUntil: 'domcontentloaded' });
    if (debug) await dump(page, `report-${report.key}-01-form`);

    // --- Set report parameters -------------------------------------------
    // Accounting basis (Cash/Accrual). AppFolio usually exposes a radio or select.
    await setBasis(page, report.basis).catch((e) => log.warning(`Basis set skipped: ${e.message}`));

    if (report.dateMode === 'as_of') {
        await setAsOfDate(page, report.asOf).catch((e) => log.warning(`As-of date skipped: ${e.message}`));
    } else if (report.dateMode === 'range') {
        await setDateRange(page, report.range).catch((e) => log.warning(`Date range skipped: ${e.message}`));
    }

    // Run / refresh the report.
    await page
        .locator('button:has-text("Run"), button:has-text("Refresh"), input[value*="Run"]')
        .first()
        .click()
        .catch(() => log.warning('No explicit Run button found — report may auto-run.'));
    await page.waitForLoadState('networkidle').catch(() => {});
    if (debug) await dump(page, `report-${report.key}-02-rendered`);

    // --- Trigger the PDF export and capture the download ------------------
    const downloadPromise = page.waitForEvent('download', { timeout: 60_000 });

    // AppFolio typically has an Export menu with a PDF option.
    await openExportMenu(page);
    await page
        .locator('a:has-text("PDF"), button:has-text("PDF"), [data-format="pdf"]')
        .first()
        .click();

    const download = await downloadPromise;
    const stream = await download.createReadStream();
    const buffer = await streamToBuffer(stream);

    const stamp = new Date().toISOString().slice(0, 10);
    const fileName = `${stamp}_${report.label.replace(/\s+/g, '_')}.pdf`;
    log.info(`Exported ${report.label} (${buffer.length} bytes).`);
    return { buffer, fileName };
}

// --- helpers ---------------------------------------------------------------

async function setBasis(page, basis) {
    if (!basis) return;
    // Try a radio button, then a <select>.
    const radio = page.locator(`label:has-text("${basis}") input, input[value="${basis}"]`).first();
    if (await radio.isVisible().catch(() => false)) {
        await radio.check();
        return;
    }
    const select = page.locator('select[name*="basis"], select[name*="accounting"]').first();
    if (await select.isVisible().catch(() => false)) {
        await select.selectOption({ label: basis });
    }
}

async function setAsOfDate(page, asOf) {
    const value = asOf === 'today' ? new Date().toISOString().slice(0, 10) : asOf;
    const field = page.locator('input[name*="as_of"], input[name*="to_date"], input[type="date"]').first();
    if (await field.isVisible().catch(() => false)) await field.fill(value);
}

async function setDateRange(page, range) {
    // "all_time" → very early start date through today.
    const from = range === 'all_time' ? '2000-01-01' : range.from;
    const to = range === 'all_time' ? new Date().toISOString().slice(0, 10) : range.to;
    const fromField = page.locator('input[name*="from"], input[name*="start"]').first();
    const toField = page.locator('input[name*="to"], input[name*="end"]').first();
    if (await fromField.isVisible().catch(() => false)) await fromField.fill(from);
    if (await toField.isVisible().catch(() => false)) await toField.fill(to);
}

async function openExportMenu(page) {
    const menu = page
        .locator('button:has-text("Export"), button:has-text("Download"), [aria-label="Export"]')
        .first();
    if (await menu.isVisible().catch(() => false)) await menu.click().catch(() => {});
}

async function streamToBuffer(stream) {
    const chunks = [];
    for await (const chunk of stream) chunks.push(chunk);
    return Buffer.concat(chunks);
}

/** Save a screenshot + HTML to the key-value store for debugging selectors. */
async function dump(page, name) {
    try {
        const png = await page.screenshot({ fullPage: true });
        await Actor.setValue(`DEBUG-${name}.png`, png, { contentType: 'image/png' });
        const html = await page.content();
        await Actor.setValue(`DEBUG-${name}.html`, html, { contentType: 'text/html' });
        log.info(`Saved debug artifacts: DEBUG-${name}`);
    } catch (e) {
        log.warning(`Could not dump ${name}: ${e.message}`);
    }
}
