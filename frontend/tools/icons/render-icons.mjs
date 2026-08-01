// Renders the app icon to the PNGs an installable web app needs.
//
// Run it with:  npm run icons
// Needs playwright-core (a devDependency) and a local Chrome install, same as `npm run og`.
//
// Build-time rather than runtime for the same reason as the OG card: the mark changes
// only when the branding does, so the files are committed and served statically.
//
// Three shapes, and the differences are not decorative:
//
//   any       — the icon as drawn, rounded corners included. Used where the platform
//               shows it as-is.
//   maskable  — full-bleed background with the mark shrunk into the middle. Android
//               crops icons to whatever shape the launcher uses (circle, squircle,
//               teardrop), and anything outside the inner 80% can be cut off. A rounded
//               square supplied here gets its corners clipped and reads as a mistake.
//   apple     — full-bleed and square. iOS applies its own corner radius and does not
//               use the manifest for the home-screen icon at all; it reads
//               <link rel="apple-touch-icon">, and a pre-rounded source ends up with
//               visible dark corners outside the rounding.

import { mkdir } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright-core';

const here = dirname(fileURLToPath(import.meta.url));
const outputDir = resolve(here, '..', '..', 'public', 'icons');

const INK = '#0B0B11';
const PINK = '#FF2E88';
const VIOLET = '#7B3BE8';

/**
 * The wordmark's V, on the app's near-black.
 *
 * @param {number} radius  Corner radius in a 64-unit box. 0 for anything the platform
 *   will mask or round itself.
 * @param {number} inset   How far the mark is pulled in from the edges. Maskable icons
 *   need this: the guaranteed-visible area is the middle 80%.
 */
const icon = ({ radius, inset }) => {
  const scale = (64 - inset * 2) / 64;
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="${PINK}" />
      <stop offset="1" stop-color="${VIOLET}" />
    </linearGradient>
  </defs>
  <rect width="64" height="64" rx="${radius}" fill="${INK}" />
  <g transform="translate(${inset} ${inset}) scale(${scale})">
    <path d="M18 17 L32 45 L46 17" fill="none" stroke="url(#g)" stroke-width="7"
          stroke-linecap="round" stroke-linejoin="round" />
  </g>
</svg>`;
};

const TARGETS = [
  { file: 'icon-192.png', size: 192, radius: 15, inset: 0 },
  { file: 'icon-512.png', size: 512, radius: 15, inset: 0 },
  // 10 units of a 64-unit box ≈ 16% in from each edge, which keeps the mark inside the
  // 80% safe area with room to spare on a circular mask.
  { file: 'icon-maskable-512.png', size: 512, radius: 0, inset: 10 },
  { file: 'apple-touch-icon.png', size: 180, radius: 0, inset: 4 },
];

await mkdir(outputDir, { recursive: true });

const browser = await chromium.launch({ channel: 'chrome', headless: true });

for (const { file, size, radius, inset } of TARGETS) {
  const page = await browser.newPage({
    viewport: { width: size, height: size },
    deviceScaleFactor: 1,
  });
  // A rounded icon needs its corners to be genuinely transparent. Rendering it against
  // the same near-black the icon uses would fill them in, leaving a square that only
  // looks rounded on a dark background and nowhere else — including the install prompt,
  // which is usually white. The full-bleed shapes keep an opaque page behind them.
  const rounded = radius > 0;
  await page.setContent(
    `<style>html,body{margin:0;padding:0;background:${rounded ? 'transparent' : INK}}` +
      `svg{display:block;width:${size}px;height:${size}px}</style>${icon({ radius, inset })}`,
    { waitUntil: 'load' },
  );
  // PNG, unlike the OG card: this is flat colour and a stroke, which PNG compresses to
  // a few kilobytes, and an icon with JPEG artefacts around the mark looks broken.
  await page.screenshot({
    path: resolve(outputDir, file),
    type: 'png',
    omitBackground: rounded,
  });
  console.log(`written: ${file} (${size}x${size})`);
  await page.close();
}

await browser.close();
