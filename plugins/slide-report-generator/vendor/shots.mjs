/*
 * 12 面 x 2 観測点のスクショと、DOM から採った検証値のログ化。
 * Bash の stdout は当てにしないので、結果はすべてファイルへ書く。
 */
import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const S = '/private/tmp/claude-501/-Users-dm-dev-dev-ObsidianMemo/1c2b7bd2-b336-41c0-9516-e9fea598fe55/scratchpad';
const which = process.argv[2]; // final | old
const HTML = `${S}/qr/${which}/index.html`;
const SHOT = `${S}/qr/shots/${which}`;
fs.mkdirSync(SHOT, { recursive: true });
const log = [];
const VIEWPORTS = [{ w: 1920, h: 1080 }, { w: 1280, h: 1024 }];

const browser = await chromium.launch({ channel: 'chrome' });
for (const vp of VIEWPORTS) {
  const ctx = await browser.newContext({ viewport: { width: vp.w, height: vp.h }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  await page.goto('file://' + HTML);
  await page.waitForTimeout(1200);
  log.push(`=== ${which} ${vp.w}x${vp.h} ===`);
  for (let i = 1; i <= 12; i++) {
    if (i > 1) {
      await page.keyboard.press('ArrowRight');
      await page.waitForTimeout(700);
    }
    const st = await page.evaluate(() => {
      const active = document.querySelector('.slider__item.is-active, .slider__item.active, .slider__item[aria-hidden="false"]');
      const all = [...document.querySelectorAll('.slider__item')];
      const idx = all.findIndex((e) => e === active);
      const counter = document.querySelector('.pg-counter__current');
      const total = document.querySelector('.pg-counter__total');
      const target = active || all[0];
      const imgs = [...target.querySelectorAll('img.qr-img')].map((im) => {
        const r = im.getBoundingClientRect();
        return { w: Math.round(r.width), h: Math.round(r.height), nat: im.naturalWidth + 'x' + im.naturalHeight,
          rendering: getComputedStyle(im).imageRendering, complete: im.complete };
      });
      const bg = [...target.querySelectorAll('.ai-bg')].map((d) => {
        const cs = getComputedStyle(d);
        return { size: cs.backgroundSize, pos: cs.backgroundPosition, hasUrl: /url\(/.test(cs.backgroundImage) };
      });
      // 矢印の marker (先端) が実際に参照解決できているか
      const markers = [...target.querySelectorAll('svg [marker-end], svg [marker-start]')].map((e) => {
        const ref = (e.getAttribute('marker-end') || e.getAttribute('marker-start') || '').replace(/^url\(#|\)$/g, '');
        return { ref, resolved: !!target.querySelector('#' + CSS.escape(ref)) };
      });
      // stage の実寸 (レターボックス確認)
      const area = document.querySelector('.slide-area').getBoundingClientRect();
      const cs = getComputedStyle(document.documentElement);
      return {
        idx: idx + 1,
        counter: counter ? counter.textContent.trim() : null,
        total: total ? total.textContent.trim() : null,
        h: (target.querySelector('h1,h2,.main-message') || {}).textContent?.trim().slice(0, 40) || '',
        scrollOver: target.scrollHeight - target.clientHeight,
        contentOver: (() => { const c = target.querySelector('.slider__content'); return c ? c.scrollHeight - c.clientHeight : null; })(),
        imgs, bg, markers,
        stage: Math.round(area.width) + 'x' + Math.round(area.height),
        su: cs.getPropertyValue('--su').trim(), sv: cs.getPropertyValue('--sv').trim(),
        rootFont: getComputedStyle(document.documentElement).fontSize,
      };
    });
    log.push(`  slide${i}: ` + JSON.stringify(st));
    await page.screenshot({ path: `${SHOT}/${vp.w}x${vp.h}-s${String(i).padStart(2, '0')}.png` });
  }
  await ctx.close();
}

// 印刷: 12 面すべてが PDF に出るか
const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
const page = await ctx.newPage();
await page.goto('file://' + HTML);
await page.waitForTimeout(1200);
const pdfPath = `${SHOT}/print.pdf`;
await page.pdf({ path: pdfPath, format: 'A4', landscape: true, printBackground: true });
const buf = fs.readFileSync(pdfPath);
const pageCount = (buf.toString('latin1').match(/\/Type\s*\/Page[^s]/g) || []).length;
log.push(`=== print === pdf=${pdfPath} bytes=${buf.length} pageCount=${pageCount}`);
await ctx.close();
await browser.close();

fs.writeFileSync(`${S}/qr/25-shots-${which}.txt`, log.join('\n') + '\n');
