// Renders og-image.html to public/og-image.png at the standard Open Graph size.
//
// Run from this directory:   node render-og.mjs
// Needs playwright-core and a local Chrome:  npm i -D playwright-core
//
// Deliberately a build-time script rather than a runtime dependency — the card only
// changes when the branding does, so the PNG is committed and served as a static file.

import { dirname, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { chromium } from 'playwright-core';

const here = dirname(fileURLToPath(import.meta.url));
const source = pathToFileURL(resolve(here, 'og-image.html')).href;
const output = resolve(here, '..', '..', 'public', 'og-image.png');

const browser = await chromium.launch({ channel: 'chrome', headless: true });
const page = await browser.newPage({
  viewport: { width: 1200, height: 630 },
  deviceScaleFactor: 1,
});

await page.goto(source, { waitUntil: 'load' });
// Local variable fonts need a beat to apply, or the capture uses the fallback stack.
await page.evaluate(() => document.fonts.ready);
await page.waitForTimeout(400);

await page.screenshot({ path: output });
console.log(`written: ${output}`);

await browser.close();
