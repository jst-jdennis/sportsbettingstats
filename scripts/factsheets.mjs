#!/usr/bin/env node
// Renders every /states/<abbr>/factsheet/ page in dist/ to dist/states/<abbr>/factsheet.pdf
// with headless Chromium, after `astro build`. The PDF is the printed page, nothing
// else, so the browser's print and the download agree. Fails the build if any sheet
// is missing or does not render, so the site never links to a PDF that is not there.
import { createServer } from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const DIST = path.join(ROOT, 'dist');
const { default: config } = await import(path.join(ROOT, 'astro.config.mjs'));
const BASE = (config.base ?? '').replace(/\/$/, '');
const SITE = (config.site ?? '').replace(/\/$/, '');

const MIME = { '.html': 'text/html; charset=utf-8', '.css': 'text/css', '.js': 'text/javascript', '.svg': 'image/svg+xml', '.csv': 'text/csv', '.json': 'application/json', '.png': 'image/png', '.woff2': 'font/woff2' };
const server = createServer((req, res) => {
  let p = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
  if (BASE && p.startsWith(BASE)) p = p.slice(BASE.length) || '/';
  if (p.endsWith('/')) p += 'index.html';
  const f = path.join(DIST, p);
  if (!f.startsWith(DIST) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.statusCode = 404; res.end('not found'); return; }
  res.setHeader('Content-Type', MIME[path.extname(f)] ?? 'application/octet-stream');
  fs.createReadStream(f).pipe(res);
});
await new Promise((r) => server.listen(0, '127.0.0.1', r));
const port = server.address().port;

const sheets = fs.readdirSync(path.join(DIST, 'states'), { withFileTypes: true })
  .filter((d) => d.isDirectory() && fs.existsSync(path.join(DIST, 'states', d.name, 'factsheet', 'index.html')))
  .map((d) => d.name).sort();
if (!sheets.length) { console.error('factsheets: no /states/<abbr>/factsheet/ pages in dist; run astro build first'); process.exit(1); }

let chromium;
try { ({ chromium } = await import('playwright')); } catch (e) { console.error('factsheets: the playwright package is not installed (npm ci installs it; CI runs `npx playwright install --with-deps chromium`)'); throw e; }
const browser = await chromium.launch({ executablePath: process.env.WPDC_CHROMIUM || undefined });
const page = await browser.newPage();
page.on('pageerror', (e) => { throw e; });
const footer = `<div style="font-family:system-ui,Arial,sans-serif;font-size:7.5px;color:#555;width:100%;padding:0 0.6in;display:flex;justify-content:space-between"><span>Wagering Policy Data Center, ${SITE}${BASE}/. Every figure is footnoted to its source; pending review means not yet checked by a second reviewer.</span><span>Page <span class="pageNumber"></span> of <span class="totalPages"></span></span></div>`;
const counts = [];
let failed = 0;
for (const abbr of sheets) {
  const url = `http://127.0.0.1:${port}${BASE}/states/${abbr}/factsheet/`;
  const out = path.join(DIST, 'states', abbr, 'factsheet.pdf');
  try {
    const resp = await page.goto(url, { waitUntil: 'load' });
    if (!resp || !resp.ok()) throw new Error(`HTTP ${resp?.status()} for ${url}`);
    await page.emulateMedia({ media: 'print' });
    const pdf = await page.pdf({ path: out, format: 'Letter', preferCSSPageSize: true, printBackground: true, displayHeaderFooter: true, headerTemplate: '<span></span>', footerTemplate: footer, margin: { top: '0.6in', right: '0.6in', bottom: '0.7in', left: '0.6in' } });
    // Chromium writes one /Type /Page object per page and no object streams, so this count is reliable.
    const pages = (pdf.toString('latin1').match(/\/Type\s*\/Page[^s]/g) ?? []).length;
    counts.push({ abbr, pages, bytes: pdf.length });
    if (pdf.length < 5000) throw new Error(`${out} is only ${pdf.length} bytes`);
  } catch (e) {
    failed++;
    console.error(`factsheets: ${abbr}: ${e.message}`);
  }
}
await browser.close();
server.close();
const longest = counts.reduce((a, c) => (c.pages > (a?.pages ?? 0) ? c : a), null);
console.log(`factsheets: ${counts.length} of ${sheets.length} rendered; pages per sheet ${Math.min(...counts.map((c) => c.pages))} to ${longest?.pages} (longest ${longest?.abbr}); ${(counts.reduce((a, c) => a + c.bytes, 0) / 1024 / 1024).toFixed(1)} MB total`);
if (failed) { console.error(`factsheets: ${failed} sheet(s) failed`); process.exit(1); }
