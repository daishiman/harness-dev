#!/usr/bin/env node
// 生成済みレポートを実ブラウザで4幅 (375/768/1280/1600px、jp-web-design の検収幅) 描画して検証する。
//
//   node .claude/skills/report-design-system/scripts/verify-render.mjs <report.html> [screenshot-dir]
//
// 検証内容:
//   - 全幅: 画面の右端を越える要素が無いこと (キットは html/body を overflow-x:clip にするので scrollWidth では測れない。
//           横スクロール容器 .chartbox / .table-scroll の内側は対象外)、アニメーション完了後の全ページのスクリーンショット保存
//   - 1280/1600: サイドバー目次が表示され、全項目のクリックで該当見出しへ遷移し現在地 (aria-current) が移ること
//   - 375/768: 目次が閉じた状態で始まり、開いて項目を押すと遷移して閉じること
// リポジトリの @playwright/test を使う (無ければ `pnpm install`)。Chrome が入っていればそれを使う。
// 終了コード: 0=合格 1=不合格 2=入力エラー
import { existsSync, mkdirSync } from "node:fs";
import { basename, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { RENDER_WIDTHS } from "./lib.mjs";

const WIDE = 1024; // これ以上でサイドバー (report.css の @media と一致させる)

async function launch() {
  const { chromium } = await import("@playwright/test");
  try {
    return await chromium.launch({ channel: "chrome" });
  } catch {
    return await chromium.launch();
  }
}

async function main(argv) {
  const [file, outArg] = argv;
  if (!file || !existsSync(file)) {
    console.error("使い方: node scripts/verify-render.mjs <report.html> [screenshot-dir]");
    return 2;
  }
  const outDir = resolve(outArg || `${file.replace(/\.html$/, "")}-screens`);
  mkdirSync(outDir, { recursive: true });
  const url = pathToFileURL(resolve(file)).href;
  const browser = await launch();
  let results;
  try {
    // 4幅は互いに独立なので、1つのブラウザで同時に検証する (順に回すより数倍速い)。結果は RENDER_WIDTHS の順で出す
    results = await Promise.all(RENDER_WIDTHS.map(async (width) => {
      const failures = [];
      const page = await browser.newPage({ viewport: { width, height: 900 }, reducedMotion: "reduce" });
      await page.goto(url);
      // 入場アニメーション (遅延つき) の終了を待ってから撮る。途中を撮ると透明な要素を見落とす
      await page.evaluate(() => Promise.all(document.getAnimations().map((a) => a.finished.catch(() => {}))));
      const shot = `${outDir}/${basename(file, ".html")}-${width}.png`;
      await page.screenshot({ path: shot, fullPage: true });

      const over = await page.evaluate(() => {
        const vw = document.documentElement.clientWidth;
        const out = [];
        for (const el of document.querySelectorAll("main *, nav.toc, header, footer")) {
          if (el.closest(".chartbox, .table-scroll") && !el.matches(".chartbox, .table-scroll")) continue;
          const r = el.getBoundingClientRect();
          if (r.width && r.right - vw > 0.5) out.push(`${el.tagName.toLowerCase()}${el.className && typeof el.className === "string" ? "." + el.className.trim().split(/\s+/).join(".") : ""} (+${Math.round(r.right - vw)}px)`);
        }
        return out;
      });
      if (over.length) failures.push(`${width}px: 画面の右端を越える要素があります: ${over.slice(0, 5).join(", ")}`);

      const links = await page.$$eval("nav.toc a[href^='#']", (as) => as.map((a) => a.getAttribute("href")));
      if (!links.length) failures.push(`${width}px: 目次の項目がありません`);

      if (width >= WIDE) {
        const tocBox = await page.locator("nav.toc").boundingBox();
        if (!tocBox || tocBox.width < 150) failures.push(`${width}px: サイドバー目次が表示されていません`);
        for (const href of links) {
          await page.click(`nav.toc a[href="${href}"]`);
          await page.waitForTimeout(80);
          const r = await page.evaluate((h) => {
            const t = document.getElementById(h.slice(1));
            const a = document.querySelector(`nav.toc a[href="${h}"]`);
            const top = t.getBoundingClientRect().top;
            const atBottom = window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 2;
            const current = document.querySelector("nav.toc a[aria-current='location']");
            return { top, atBottom, inView: top >= 0 && top < window.innerHeight, current: current && current.getAttribute("href"), tocStill: a.getBoundingClientRect().width > 0 };
          }, href);
          // 見出しが画面上端付近に来ること。末尾の短いセクションはページ最下部で止まるので表示範囲内なら可
          if (!(Math.abs(r.top) <= 40 || (r.atBottom && r.inView))) failures.push(`${width}px: ${href} へ遷移していません (top=${Math.round(r.top)})`);
          if (!r.atBottom && r.current !== href) failures.push(`${width}px: ${href} を押しても現在地が ${r.current} のままです`);
          if (!r.tocStill) failures.push(`${width}px: 遷移後にサイドバー目次が見えなくなりました`);
        }
      } else {
        const openAtStart = await page.$eval("nav.toc details", (d) => d.open);
        if (openAtStart) failures.push(`${width}px: 狭い画面で目次が開いた状態で始まっています`);
        const target = links[Math.floor(links.length / 2)];
        await page.click("nav.toc summary");
        await page.click(`nav.toc a[href="${target}"]`);
        await page.waitForTimeout(80);
        const r = await page.evaluate((h) => {
          const bar = document.querySelector("nav.toc").getBoundingClientRect().bottom;
          const top = document.getElementById(h.slice(1)).getBoundingClientRect().top;
          return { open: document.querySelector("nav.toc details").open, gap: top - bar };
        }, target);
        if (r.open) failures.push(`${width}px: 項目を押しても目次が閉じません`);
        if (r.gap < 0 || r.gap > 48) failures.push(`${width}px: ${target} が上部バーに隠れるか離れすぎています (gap=${Math.round(r.gap)})`);
      }
      await page.close();
      return { width, shot, failures };
    }));
  } finally {
    await browser.close();
  }
  const failures = results.flatMap((r) => r.failures);
  for (const r of results) console.log(`  ${r.width}px: ${r.shot}`);
  for (const f of failures) console.log(`  NG ${f}`);
  console.log(failures.length ? `描画検証: 不合格 (${failures.length})` : "描画検証: 合格 (スクリーンショットを目視で確認すること)");
  return failures.length ? 1 : 0;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) process.exit(await main(process.argv.slice(2)));
