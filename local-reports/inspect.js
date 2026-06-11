/**
 * Reads the saved debug HTML files and prints every form control (selects with
 * their options, inputs, and the Print/Update buttons) so the exact field names
 * can be wired into download-reports.js. No browser or AppFolio run needed.
 *
 *   node inspect.js
 */
import { readdir, readFile } from 'node:fs/promises';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const dir = join(dirname(fileURLToPath(import.meta.url)), 'debug');

let files = [];
try {
    files = (await readdir(dir)).filter((f) => f.endsWith('-01-form.html'));
} catch {
    console.error('No debug folder found. Run: $env:DEBUG=1 ; node download-reports.js  first.');
    process.exit(1);
}

const attr = (s, name) => (s.match(new RegExp(`${name}="([^"]*)"`)) || [])[1] || '';

for (const f of files.sort()) {
    const html = await readFile(join(dir, f), 'utf8');
    console.log(`\n================== ${f} ==================`);

    for (const m of html.matchAll(/<select\b([^>]*)>([\s\S]*?)<\/select>/gi)) {
        const opts = [...m[2].matchAll(/<option[^>]*>([^<]*)<\/option>/gi)]
            .map((o) => o[1].trim())
            .filter(Boolean);
        console.log(`SELECT name="${attr(m[1], 'name')}" id="${attr(m[1], 'id')}" options=[ ${opts.join(' | ')} ]`);
    }

    for (const m of html.matchAll(/<input\b([^>]*?)\/?>/gi)) {
        const type = attr(m[1], 'type') || 'text';
        if (type === 'hidden') continue;
        console.log(
            `INPUT type="${type}" name="${attr(m[1], 'name')}" id="${attr(m[1], 'id')}"` +
            ` placeholder="${attr(m[1], 'placeholder')}" value="${attr(m[1], 'value')}"`,
        );
    }

    for (const m of html.matchAll(/<(button|a)\b([^>]*)>([\s\S]*?)<\/\1>/gi)) {
        const text = m[3].replace(/<[^>]*>/g, '').trim();
        if (/print|pdf|update|refresh|^run$|select|all|none/i.test(text) || /print|pdf/i.test(m[2])) {
            console.log(`${m[1].toUpperCase()} text="${text.slice(0, 40)}" class="${attr(m[2], 'class').slice(0, 60)}"`);
        }
    }
}
