#!/usr/bin/env node
/**
 * Node Playwright worker for verify-slides.js.
 */
import { mkdirSync } from 'fs';
import { resolve } from 'path';
import { pathToFileURL } from 'url';
import { configurePluginLocalPlaywright, setupCommand } from './playwright-runtime.js';
import { VIEWPORT } from './utils.js';

configurePluginLocalPlaywright();

const [mode, htmlArg, outputArg] = process.argv.slice(2);
if (!['--check-ratio', '--capture'].includes(mode) || !htmlArg) {
  console.error('usage: verify-slides-playwright.js --check-ratio <html> | --capture <html> <output-dir>');
  process.exit(2);
}
if (mode === '--capture' && !outputArg) {
  console.error('--capture requires output directory');
  process.exit(2);
}

let chromium;
try {
  ({ chromium } = await import('playwright'));
} catch (error) {
  console.error(`playwright unavailable: ${error.message}`);
  console.error(`run: ${setupCommand()}`);
  process.exit(2);
}

let browser;
try {
  browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({
    viewport: { width: VIEWPORT.WIDTH, height: VIEWPORT.HEIGHT },
  });
  await page.goto(pathToFileURL(resolve(htmlArg)).href, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(500);

  const badText = await page.evaluate(() => {
    const text = document.body.innerText || '';
    return ['[object Object]', '[render error:'].filter((pattern) => text.includes(pattern));
  });
  if (badText.length) throw new Error(`可視テキストの型崩れ: ${badText.join(', ')}`);

  const ratio = await page.evaluate(() => {
    const area = document.querySelector('.slide-area');
    if (!area) return { hasSlideArea: false };
    const rect = area.getBoundingClientRect();
    return {
      hasSlideArea: true,
      width: rect.width,
      height: rect.height,
      ratio: rect.height ? rect.width / rect.height : null,
    };
  });
  if (!ratio.hasSlideArea || !ratio.ratio) throw new Error('.slide-area が見つからない');
  if (Math.abs(ratio.ratio - VIEWPORT.ASPECT_RATIO) >= 0.01) {
    throw new Error(
      `アスペクト比不一致: ${ratio.ratio.toFixed(4)} (expected ${VIEWPORT.ASPECT_RATIO.toFixed(4)})`,
    );
  }

  if (mode === '--check-ratio') {
    console.log(
      `16:9 PASS: ${ratio.width.toFixed(0)}x${ratio.height.toFixed(0)} (${ratio.ratio.toFixed(4)})`,
    );
    process.exitCode = 0;
  } else {
    const outputDir = resolve(outputArg);
    mkdirSync(outputDir, { recursive: true });
    const total = await page.locator('.slider__item').count();
    if (total === 0) throw new Error('.slider__item が0件');
    for (let index = 0; index < total; index += 1) {
      await page.evaluate((active) => {
        document.querySelectorAll('.slider__item').forEach((item, itemIndex) => {
          item.classList.toggle('is-active', itemIndex === active);
          item.classList.toggle('active', itemIndex === active);
        });
      }, index);
      await page.waitForTimeout(120);
      const target = page.locator('.slide-area').first();
      const path = resolve(outputDir, `slide_${String(index + 1).padStart(2, '0')}.png`);
      await target.screenshot({ path });
      console.log(`slide ${index + 1}/${total}: ${path}`);
    }
    console.log(`capture PASS: ${total} slides`);
  }
} catch (error) {
  console.error(`verify-slides-playwright: ${error.message}`);
  process.exitCode = 1;
} finally {
  if (browser) await browser.close();
}
