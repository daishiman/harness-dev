/* QR を含む面のカードで title / desc の実効フォントサイズを両ビルドで採る。
   フォント寸法は表示中かどうかに依らないので、DOM 全体を走査する。 */
import { chromium } from 'playwright';
import fs from 'fs';

const S = '/private/tmp/claude-501/-Users-dm-dev-dev-ObsidianMemo/1c2b7bd2-b336-41c0-9516-e9fea598fe55/scratchpad';
const log = [];
const browser = await chromium.launch({ channel: 'chrome' });
for (const which of ['final', 'old']) {
  const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  await page.goto('file://' + `${S}/qr/${which}/index.html`);
  await page.waitForTimeout(1000);
  const r = await page.evaluate(() => {
    const items = [...document.querySelectorAll('.slider__item')];
    const px = (e) => (e ? Math.round(parseFloat(getComputedStyle(e).fontSize) * 10) / 10 : null);
    const out = [];
    items.forEach((it, i) => {
      const cells = [...it.querySelectorAll('.grid-cell')];
      if (!cells.length) return;
      out.push({
        slide: i + 1,
        qrFace: !!it.querySelector('.qr-img'),
        cells: cells.map((c) => ({
          t: (c.querySelector('.grid-cell-title') || {}).textContent?.trim().slice(0, 12) ?? null,
          tpx: px(c.querySelector('.grid-cell-title')),
          dpx: px(c.querySelector('.grid-cell-desc')),
          dh: c.querySelector('.grid-cell-desc') ? Math.round(c.querySelector('.grid-cell-desc').getBoundingClientRect().height) : null,
        })),
      });
    });
    const cs = getComputedStyle(document.documentElement);
    return { out, root: cs.fontSize, fontScale: cs.getPropertyValue('--font-scale').trim() };
  });
  log.push(`=== ${which} root=${r.root} font-scale=${r.fontScale}`);
  for (const s of r.out) log.push(`  slide${s.slide} qr=${s.qrFace} ` + JSON.stringify(s.cells));
  await ctx.close();
}
await browser.close();
fs.writeFileSync(`${S}/qr/32-fonts.txt`, log.join('\n') + '\n');
