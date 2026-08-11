/**
 * verify-report-runtime.js — C24 report 実描画入力 bundle 生成器。
 *
 * Usage:
 *   node verify-report-runtime.js report.html --structure report-structure.json --out runtime-bundle.json
 *   node verify-report-runtime.js --self-test
 *
 * exit 0: bundle 生成成功 / 1: runtime acceptance failure / 2: usage or environment failure
 */

import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'fs';
import { tmpdir } from 'os';
import { dirname, relative, resolve } from 'path';
import { pathToFileURL } from 'url';
import {
  configurePluginLocalPlaywright,
  setupCommand,
} from './playwright-runtime.js';

const VIEWPORTS = [899, 900, 901, 1024, 1366, 1600];
configurePluginLocalPlaywright();

function parseArgs(argv) {
  if (argv.includes('--self-test')) return { selfTest: true };
  const html = argv[0];
  const structureIndex = argv.indexOf('--structure');
  const outIndex = argv.indexOf('--out');
  if (!html || structureIndex < 0 || !argv[structureIndex + 1] || outIndex < 0 || !argv[outIndex + 1]) {
    throw new Error('usage: verify-report-runtime.js <report.html> --structure <report-structure.json> --out <bundle.json>');
  }
  return { html, structure: argv[structureIndex + 1], out: argv[outIndex + 1] };
}

function numberPx(value) {
  const n = Number.parseFloat(String(value || ''));
  return Number.isFinite(n) ? n : null;
}

async function loadPlaywright() {
  try {
    return await import('playwright');
  } catch (error) {
    throw new Error(`playwright unavailable; run ${setupCommand()}: ${error.message}`);
  }
}

async function captureMetrics(page, width) {
  await page.setViewportSize({ width, height: 900 });
  await page.evaluate(async () => {
    if (document.fonts?.ready) await document.fonts.ready;
  });
  return page.evaluate(() => {
    const pick = (selector) => document.querySelector(selector);
    const rect = (element) => element ? element.getBoundingClientRect() : null;
    const style = (element) => element ? getComputedStyle(element) : null;
    const body = pick('.report-body') || pick('.report-section p') || document.body;
    const title = pick('.report-title') || pick('h1');
    const layout = pick('.report-layout') || pick('.report');
    const content = pick('.report-content') || pick('.report-main') || pick('.report');
    const sidebar = pick('.report-toc--sidebar');
    const bodyStyle = style(body);
    const titleStyle = style(title);
    const active = pick('.report-toc--sidebar a.is-active, .report-toc--sidebar a[aria-current="location"]');
    return {
      viewport: { width: innerWidth, height: innerHeight },
      bodyFontPx: bodyStyle ? Number.parseFloat(bodyStyle.fontSize) : null,
      bodyLineHeightPx: bodyStyle ? Number.parseFloat(bodyStyle.lineHeight) : null,
      titleFontPx: titleStyle ? Number.parseFloat(titleStyle.fontSize) : null,
      layoutWidthPx: rect(layout)?.width ?? null,
      contentWidthPx: rect(content)?.width ?? null,
      sidebarWidthPx: rect(sidebar)?.width ?? 0,
      sidebarVisible: Boolean(sidebar && rect(sidebar)?.width && style(sidebar)?.display !== 'none'),
      activeHref: active?.getAttribute('href') ?? null,
    };
  });
}

async function captureNavigation(page, sectionIds, tocExpected) {
  const events = [];
  const firstId = sectionIds[0];
  const lastId = sectionIds.at(-1);
  if (firstId) {
    await page.evaluate((id) => { location.hash = `#${id}`; }, firstId);
    await page.waitForTimeout(50);
    events.push({ kind: 'initial-hash', hash: await page.evaluate(() => location.hash) });
  }
  const tocLinkCount = await page.locator('.report-toc--sidebar a[href^="#"]').count();
  if (tocExpected && tocLinkCount === 0) throw new Error('structure requests TOC but sidebar links are absent');
  if (tocLinkCount > 0) {
    const target = page.locator('.report-toc--sidebar a[href^="#"]').last();
    await target.click();
    await page.waitForTimeout(50);
    events.push({ kind: 'toc-click', hash: await page.evaluate(() => location.hash) });
  } else {
    events.push({ kind: 'toc-click', skipped: 'toc-disabled' });
  }
  if (lastId) {
    await page.locator(`#${lastId}`).scrollIntoViewIfNeeded();
    await page.waitForTimeout(100);
    events.push({ kind: 'manual-scroll', activeHref: await page.locator('.report-toc--sidebar a.is-active, .report-toc--sidebar a[aria-current="location"]').first().getAttribute('href').catch(() => null) });
  }
  await page.goBack({ waitUntil: 'domcontentloaded' }).catch(() => null);
  events.push({ kind: 'history-back', hash: await page.evaluate(() => location.hash) });
  await page.goForward({ waitUntil: 'domcontentloaded' }).catch(() => null);
  events.push({ kind: 'history-forward', hash: await page.evaluate(() => location.hash) });
  events.push({ kind: 'font-ready-layout-shift', ready: await page.evaluate(async () => { if (document.fonts?.ready) await document.fonts.ready; return true; }) });
  const printLifecycle = await page.evaluate(() => {
    window.dispatchEvent(new Event('beforeprint'));
    const before = document.querySelector('.report-toc--sidebar a.is-active, .report-toc--sidebar a[aria-current="location"]')?.getAttribute('href') ?? null;
    window.dispatchEvent(new Event('afterprint'));
    const after = document.querySelector('.report-toc--sidebar a.is-active, .report-toc--sidebar a[aria-current="location"]')?.getAttribute('href') ?? null;
    return { before, after };
  });
  events.push({ kind: 'beforeprint-afterprint', ...printLifecycle });
  return events;
}

export async function verifyReportRuntime({ html, structure, out }) {
  const source = JSON.parse(readFileSync(resolve(structure), 'utf8'));
  const sectionIds = (source.sections || []).map((section) => section.id).filter(Boolean);
  const tocExpected = source.meta?.toc !== false && sectionIds.length > 0;
  const { chromium } = await loadPlaywright();
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage();
    await page.goto(pathToFileURL(resolve(html)).href, { waitUntil: 'domcontentloaded' });
    const screenshotsDir = resolve(dirname(out), 'runtime-screenshots');
    mkdirSync(screenshotsDir, { recursive: true });
    const metrics = [];
    const renders = [];
    for (const width of VIEWPORTS) {
      metrics.push(await captureMetrics(page, width));
      const screenshot = resolve(screenshotsDir, `report-${width}.png`);
      await page.screenshot({ path: screenshot, fullPage: true });
      renders.push({ media: 'screen', width, path: relative(process.cwd(), screenshot) });
    }
    const navigation = await captureNavigation(page, sectionIds, tocExpected);
    await page.emulateMedia({ media: 'print' });
    const print = await page.evaluate(() => {
      const report = document.querySelector('.report');
      const toc = document.querySelector('.report-toc--sidebar');
      const tocRect = toc?.getBoundingClientRect();
      return {
        reportWidthPx: report?.getBoundingClientRect().width ?? null,
        tocDisplay: toc ? getComputedStyle(toc).display : null,
        tocVisible: Boolean(tocRect && tocRect.width > 0 && tocRect.height > 0 && getComputedStyle(toc).visibility !== 'hidden'),
      };
    });
    const printScreenshot = resolve(screenshotsDir, 'report-print.png');
    await page.screenshot({ path: printScreenshot, fullPage: true });
    renders.push({ media: 'print', path: relative(process.cwd(), printScreenshot) });
    const findings = [];
    for (const item of metrics) {
      if ([item.bodyFontPx, item.layoutWidthPx, item.contentWidthPx].some((v) => v === null)) {
        findings.push(`viewport ${item.viewport.width}: required computed metric missing`);
      }
      if (item.bodyLineHeightPx !== null && item.bodyFontPx) {
        item.lineHeightRatio = Number((item.bodyLineHeightPx / item.bodyFontPx).toFixed(3));
      }
      if (item.titleFontPx !== null && item.bodyFontPx) {
        item.titleBodyRatio = Number((item.titleFontPx / item.bodyFontPx).toFixed(3));
      }
      item.utilizationRatio = item.viewport.width ? Number(((item.contentWidthPx + item.sidebarWidthPx) / item.viewport.width).toFixed(3)) : null;
      if (item.bodyFontPx !== null && (item.bodyFontPx < 16 || item.bodyFontPx > 18)) findings.push(`viewport ${item.viewport.width}: body font ${item.bodyFontPx}px outside 16-18px`);
      if (item.lineHeightRatio !== undefined && (item.lineHeightRatio < 1.6 || item.lineHeightRatio > 1.8)) findings.push(`viewport ${item.viewport.width}: line-height ratio ${item.lineHeightRatio} outside 1.6-1.8`);
      if (item.titleBodyRatio !== undefined && item.titleBodyRatio > 2.2) findings.push(`viewport ${item.viewport.width}: title/body ratio ${item.titleBodyRatio} exceeds 2.2`);
      if (item.utilizationRatio !== null && item.utilizationRatio < 0.55) findings.push(`viewport ${item.viewport.width}: content utilization ${item.utilizationRatio} below 0.55`);
    }
    if (tocExpected && print.tocVisible) findings.push(`print: sidebar TOC must be hidden (display=${print.tocDisplay})`);
    const bundle = {
      schemaVersion: 1,
      html: relative(process.cwd(), resolve(html)),
      structure: relative(process.cwd(), resolve(structure)),
      viewports: VIEWPORTS,
      metrics,
      renders,
      navigation,
      print,
      findings,
      verdict: findings.length ? 'FAIL' : 'PASS',
    };
    writeFileSync(resolve(out), `${JSON.stringify(bundle, null, 2)}\n`, 'utf8');
    return bundle;
  } finally {
    await browser.close();
  }
}

async function selfTest() {
  const dir = mkdtempSync(resolve(tmpdir(), 'verify-report-runtime-'));
  try {
    const html = resolve(dir, 'report.html');
    const structure = resolve(dir, 'report-structure.json');
    const out = resolve(dir, 'bundle.json');
    writeFileSync(html, '<!doctype html><html><head><style>.report{width:80%}.report-body{font-size:16px;line-height:26px}</style></head><body><main class="report"><h1 class="report-title">Test</h1><section id="s1"><p class="report-body">Body</p></section></main></body></html>');
    writeFileSync(structure, JSON.stringify({ meta: { toc: false }, sections: [{ id: 's1' }] }));
    const result = await verifyReportRuntime({ html, structure, out });
    if (result.metrics.length !== VIEWPORTS.length || result.verdict !== 'PASS') throw new Error('self-test assertion failed');
    console.log('verify-report-runtime: self-test PASS');
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

async function main() {
  try {
    const args = parseArgs(process.argv.slice(2));
    if (args.selfTest) return selfTest();
    const result = await verifyReportRuntime(args);
    console.log(JSON.stringify({ verdict: result.verdict, out: resolve(args.out), findings: result.findings }));
    if (result.verdict !== 'PASS') process.exitCode = 1;
  } catch (error) {
    console.error(`verify-report-runtime: ${error.message}`);
    process.exitCode = 2;
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) main();
