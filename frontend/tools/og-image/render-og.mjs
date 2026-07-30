// Renders og-image.html to public/og-image.jpg at the standard Open Graph size.
//
// Run it with:  npm run og
// Needs playwright-core (a devDependency) and a local Chrome install.
//
// Deliberately a build-time script rather than a runtime dependency — the card only
// changes when the branding does, so the image is committed and served as a static file.
//
// JPEG rather than PNG: the card is gradients plus a grain overlay, which PNG cannot
// compress (it came out at 504 KB). At quality 92 the same image is a fraction of that
// with no visible artefacts on the type.
//
// If you change the artwork, bump the `?v=` on the og:image URL in index.html —
// Facebook, iMessage and X cache scraped previews aggressively and will otherwise keep
// serving the old card for days.

import { dirname, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { chromium } from 'playwright-core';

const here = dirname(fileURLToPath(import.meta.url));
const source = pathToFileURL(resolve(here, 'og-image.html')).href;
const output = resolve(here, '..', '..', 'public', 'og-image.jpg');

const browser = await chromium.launch({ channel: 'chrome', headless: true });
const page = await browser.newPage({
  viewport: { width: 1200, height: 630 },
  deviceScaleFactor: 1,
});

await page.goto(source, { waitUntil: 'load' });
// Local variable fonts need a beat to apply, or the capture uses the fallback stack.
await page.evaluate(() => document.fonts.ready);
await page.waitForTimeout(400);

await page.screenshot({ path: output, type: 'jpeg', quality: 92 });
console.log(`written: ${output}`);

await browser.close();
